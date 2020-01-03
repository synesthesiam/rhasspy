"""Rhasspy web application server."""
import argparse
import asyncio
import atexit
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union
from uuid import uuid4

import attr
import json5
from quart import (Quart, Response, jsonify, request, safe_join, send_file,
                   send_from_directory, websocket)
from quart_cors import cors
from swagger_ui import quart_api_doc

from rhasspy.actor import ActorSystem, ConfigureEvent, RhasspyActor
from rhasspy.core import RhasspyCore
from rhasspy.events import IntentRecognized, ProfileTrainingFailed
from rhasspy.utils import (FunctionLoggingHandler, buffer_to_wav,
                           get_all_intents, get_ini_paths, get_wav_duration,
                           load_phoneme_examples, read_dict, recursive_remove)

# -----------------------------------------------------------------------------
# Quart Web App Setup
# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

loop = asyncio.get_event_loop()

app = Quart("rhasspy")
app.secret_key = str(uuid4())
app = cors(app)

# -----------------------------------------------------------------------------
# Parse Arguments
# -----------------------------------------------------------------------------

parser = argparse.ArgumentParser("Rhasspy")
parser.add_argument(
    "--profile", "-p", required=True, type=str, help="Name of profile to load"
)
parser.add_argument("--host", type=str, help="Host for web server", default="0.0.0.0")
parser.add_argument("--port", type=int, help="Port for web server", default=12101)
parser.add_argument(
    "--system-profiles",
    type=str,
    help="Directory with base profile files (read only)",
    default=os.path.join(os.getcwd(), "profiles"),
)
parser.add_argument(
    "--user-profiles",
    type=str,
    help="Directory with user profile files (read/write)",
    default=os.path.expanduser("~/.config/rhasspy/profiles"),
)
parser.add_argument(
    "--set",
    "-s",
    nargs=2,
    action="append",
    help="Set a profile setting value",
    default=[],
)
parser.add_argument(
    "--ssl", nargs=2, help="Use SSL with <CERT_FILE <KEY_FILE>", default=None
)
parser.add_argument("--log-level", default="DEBUG", help="Set logging level")

args = parser.parse_args()

# Set log level
log_level = getattr(logging, args.log_level.upper())
logging.basicConfig(level=log_level)


logger.debug(args)

system_profiles_dir = os.path.abspath(args.system_profiles)
user_profiles_dir = os.path.abspath(args.user_profiles)

profiles_dirs = [user_profiles_dir, system_profiles_dir]

# -----------------------------------------------------------------------------
# Dialogue Manager Setup
# -----------------------------------------------------------------------------

core = None

# We really, *really* want shutdown to be called
@atexit.register
def shutdown(*_args: Any, **kwargs: Any) -> None:
    """Ensure Rhasspy core is stopped."""
    global core
    if core is not None:
        loop.run_until_complete(loop.create_task(core.shutdown()))
        core = None


async def start_rhasspy() -> None:
    """Create actor system and Rhasspy core."""
    global core

    # Load core
    system = ActorSystem()
    core = RhasspyCore(
        args.profile, system_profiles_dir, user_profiles_dir, actor_system=system
    )

    # Set environment variables
    os.environ["RHASSPY_BASE_DIR"] = os.getcwd()
    os.environ["RHASSPY_PROFILE"] = core.profile.name
    os.environ["RHASSPY_PROFILE_DIR"] = core.profile.write_dir()

    # Add profile settings from the command line
    extra_settings = {}
    for key, value in args.set:
        try:
            value = json.loads(value)
        except Exception:
            pass

        logger.debug("Profile: %s=%s", key, value)
        extra_settings[key] = value
        core.profile.set(key, value)

    # Load observer actor to catch intents
    observer = system.createActor(WebSocketObserver)
    system.ask(observer, ConfigureEvent(core.profile))

    await core.start(observer=observer)
    logger.info("Started")


# -----------------------------------------------------------------------------
# HTTP API
# -----------------------------------------------------------------------------


@app.route("/api/version")
async def api_version() -> Response:
    """Get Rhasspy version."""
    return await send_file(Path("VERSION"))


# -----------------------------------------------------------------------------


@app.route("/api/profiles")
async def api_profiles() -> Response:
    """Get list of available profiles and verify necessary files."""
    assert core is not None
    profile_names = set()
    for profiles_dir in profiles_dirs:
        if not os.path.exists(profiles_dir):
            continue

        for name in os.listdir(profiles_dir):
            profile_dir = os.path.join(profiles_dir, name)
            if os.path.isdir(profile_dir):
                profile_names.add(name)

    missing_files = core.check_profile()
    downloaded = len(missing_files) == 0
    return jsonify(
        {
            "default_profile": core.profile.name,
            "profiles": sorted(profile_names),
            "downloaded": downloaded,
            "missing_files": missing_files,
        }
    )


# -----------------------------------------------------------------------------


@app.route("/api/download-profile", methods=["POST"])
async def api_download_profile() -> str:
    """Downloads the current profile."""
    assert core is not None
    delete = request.args.get("delete", "false").lower() == "true"
    await core.download_profile(delete=delete)

    return "OK"


# -----------------------------------------------------------------------------


@app.route("/api/problems", methods=["GET"])
async def api_problems() -> Response:
    """Returns any problems Rhasspy has found."""
    assert core is not None
    return jsonify(await core.get_problems())


# -----------------------------------------------------------------------------


@app.route("/api/microphones", methods=["GET"])
async def api_microphones() -> Response:
    """Get a dictionary of available recording devices"""
    assert core is not None
    system = request.args.get("system", None)
    return jsonify(await core.get_microphones(system))


# -----------------------------------------------------------------------------


@app.route("/api/test-microphones", methods=["GET"])
async def api_test_microphones() -> Response:
    """Get a dictionary of available, functioning recording devices"""
    assert core is not None
    system = request.args.get("system", None)
    return jsonify(await core.test_microphones(system))


# -----------------------------------------------------------------------------


@app.route("/api/speakers", methods=["GET"])
async def api_speakers() -> Response:
    """Get a dictionary of available playback devices"""
    assert core is not None
    system = request.args.get("system", None)
    return jsonify(await core.get_speakers(system))


# -----------------------------------------------------------------------------


@app.route("/api/listen-for-wake", methods=["POST"])
async def api_listen_for_wake() -> str:
    """Make Rhasspy listen for a wake word"""
    assert core is not None
    core.listen_for_wake()
    return "OK"


# -----------------------------------------------------------------------------


@app.route("/api/listen-for-command", methods=["POST"])
async def api_listen_for_command() -> Response:
    """Wake Rhasspy up and listen for a voice command"""
    assert core is not None
    no_hass = request.args.get("nohass", "false").lower() == "true"

    # Seconds before timing out
    timeout = request.args.get("timeout")
    if timeout is not None:
        timeout = float(timeout)

    # Key/value to set in recognized intent
    entity = request.args.get("entity")
    value = request.args.get("value")

    return jsonify(
        await core.listen_for_command(
            handle=(not no_hass), timeout=timeout, entity=entity, value=value
        )
    )


# -----------------------------------------------------------------------------


@app.route("/api/profile", methods=["GET", "POST"])
async def api_profile() -> Union[str, Response]:
    """Read or write profile JSON directly"""
    assert core is not None
    layers = request.args.get("layers", "all")

    if request.method == "POST":
        # Ensure that JSON is valid
        profile_json = json5.loads(await request.data)
        recursive_remove(core.profile.system_json, profile_json)

        profile_path = Path(core.profile.write_path("profile.json"))
        with open(profile_path, "w") as profile_file:
            json.dump(profile_json, profile_file, indent=4)

        msg = f"Wrote profile to {profile_path}"
        logger.debug(msg)
        return msg

    if layers == "defaults":
        # Read default settings
        return jsonify(core.defaults)

    if layers == "profile":
        # Local settings only
        profile_path = Path(core.profile.read_path("profile.json"))
        return await send_file(profile_path)

    return jsonify(core.profile.json)


# -----------------------------------------------------------------------------


@app.route("/api/lookup", methods=["POST"])
async def api_lookup() -> Response:
    """Get CMU phonemes from dictionary or guessed pronunciation(s)"""
    assert core is not None
    n = int(request.args.get("n", 5))
    assert n > 0, "No pronunciations requested"

    data = await request.data
    word = data.decode().strip().lower()
    assert word, "No word to look up"

    result = await core.get_word_pronunciations([word], n)
    pronunciations = result.pronunciations

    return jsonify(pronunciations[word])


# -----------------------------------------------------------------------------


@app.route("/api/pronounce", methods=["POST"])
async def api_pronounce() -> Union[Response, str]:
    """Pronounce CMU phonemes or word using eSpeak"""
    assert core is not None
    download = request.args.get("download", "false").lower() == "true"

    data = await request.data
    pronounce_str = data.decode().strip()
    assert pronounce_str, "No string to pronounce"

    # phonemes or word
    pronounce_type = request.args.get("type", "phonemes")

    if pronounce_type == "phonemes":
        # Convert from Sphinx to espeak phonemes
        phoneme_result = await core.get_word_phonemes(pronounce_str)
        espeak_str = phoneme_result.phonemes
    else:
        # Speak word directly
        espeak_str = pronounce_str

    speak_result = await core.speak_word(espeak_str)
    wav_data = speak_result.wav_data
    espeak_phonemes = speak_result.phonemes

    if download:
        # Return WAV
        return Response(wav_data)  # , mimetype="audio/wav")

    # Play through speakers
    core.play_wav_data(wav_data)
    return espeak_phonemes


# -----------------------------------------------------------------------------


@app.route("/api/play-wav", methods=["POST"])
async def api_play_wav() -> str:
    """Play WAV data through the configured audio output system"""
    assert core is not None

    if request.content_type == "audio/wav":
        wav_data = await request.data
    else:
        # Interpret as URL
        data = await request.data
        url = data.decode()
        logger.debug("Loading WAV data from %s", url)

        async with core.session.get(url) as response:
            wav_data = await response.read()

    # Play through speakers
    logger.debug("Playing %s byte(s)", len(wav_data))
    core.play_wav_data(wav_data)

    return "OK"


# -----------------------------------------------------------------------------


@app.route("/api/phonemes")
def api_phonemes():
    """Get phonemes and example words for a profile"""
    assert core is not None
    speech_system = core.profile.get("speech_to_text.system", "pocketsphinx")
    examples_path = Path(
        core.profile.read_path(
            core.profile.get(
                f"speech_to_text.{speech_system}.phoneme_examples",
                "phoneme_examples.txt",
            )
        )
    )

    # phoneme -> { word, phonemes }
    logger.debug("Loading phoneme examples from %s", examples_path)
    examples_dict = load_phoneme_examples(examples_path)

    return jsonify(examples_dict)


# -----------------------------------------------------------------------------


@app.route("/api/sentences", methods=["GET", "POST"])
async def api_sentences():
    """Read or write sentences for a profile"""
    assert core is not None

    if request.method == "POST":
        # POST
        if request.mimetype == "application/json":
            # Update multiple ini files at once. Paths as keys (relative to
            # profile directory), sentences as values.
            num_chars = 0
            paths_written = []

            sentences_dict = json5.loads(await request.data)
            for sentences_path, sentences_text in sentences_dict.items():
                # Path is relative to profile directory
                sentences_path = Path(core.profile.write_path(sentences_path))

                if sentences_text.strip():
                    # Overwrite file
                    logger.debug("Writing %s", sentences_path)

                    sentences_path.parent.mkdir(parents=True, exist_ok=True)
                    sentences_path.write_text(sentences_text)

                    num_chars += len(sentences_text)
                    paths_written.append(sentences_path)
                elif sentences_path.is_file():
                    # Remove file
                    logger.debug("Removing %s", sentences_path)
                    sentences_path.unlink()

            return f"Wrote {num_chars} char(s) to {[str(p) for p in paths_written]}"

        # Update sentences.ini only
        sentences_path = Path(
            core.profile.write_path(core.profile.get("speech_to_text.sentences_ini"))
        )

        data = await request.data
        with open(sentences_path, "wb") as sentences_file:
            sentences_file.write(data)
            return f"Wrote {len(data)} byte(s) to {sentences_path}"

    # GET
    sentences_path_rel = core.profile.read_path(
        core.profile.get("speech_to_text.sentences_ini")
    )
    sentences_path = Path(sentences_path_rel)

    if prefers_json():
        # Return multiple .ini files, keyed by path relative to profile
        # directory.
        sentences_dict = {}
        if sentences_path.is_file():
            try:
                # Try user profile dir first
                profile_dir = Path(core.profile.user_profiles_dir) / core.profile.name
                key = str(sentences_path.relative_to(profile_dir))
            except Exception:
                # Fall back to system profile dir
                profile_dir = Path(core.profile.system_profiles_dir) / core.profile.name
                key = str(sentences_path.relative_to(profile_dir))

            sentences_dict[key] = sentences_path.read_text()

        ini_dir = Path(
            core.profile.read_path(core.profile.get("speech_to_text.sentences_dir"))
        )

        # Add all .ini files from sentences_dir
        if ini_dir.is_dir():
            for ini_path in ini_dir.glob("*.ini"):
                key = str(ini_path.relative_to(core.profile.read_path()))
                sentences_dict[key] = ini_path.read_text()

        return jsonify(sentences_dict)

    # Return sentences.ini contents only
    if not sentences_path.is_file():
        return ""  # no sentences yet

    # Return file contents
    return await send_file(sentences_path)


# -----------------------------------------------------------------------------


@app.route("/api/custom-words", methods=["GET", "POST"])
async def api_custom_words():
    """Read or write custom word dictionary for a profile"""
    assert core is not None
    speech_system = core.profile.get("speech_to_text.system", "pocketsphinx")

    if request.method == "POST":
        custom_words_path = Path(
            core.profile.write_path(
                core.profile.get(
                    f"speech_to_text.{speech_system}.custom_words", "custom_words.txt"
                )
            )
        )

        # Update custom words
        lines_written = 0
        with open(custom_words_path, "w") as custom_words_file:
            data = await request.data
            lines = data.decode().splitlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                print(line, file=custom_words_file)
                lines_written += 1

            return f"Wrote {lines_written} line(s) to {custom_words_path}"

    custom_words_path = Path(
        core.profile.read_path(
            core.profile.get(
                f"speech_to_text.{speech_system}.custom_words", "custom_words.txt"
            )
        )
    )

    # Return custom_words
    if prefers_json():
        if not custom_words_path.is_file():
            return jsonify({})  # no custom_words yet

        with open(custom_words_path, "r") as words_file:
            return jsonify(read_dict(words_file))
    else:
        if not custom_words_path.is_file():
            return ""  # no custom_words yet

        # Return file contents
        return await send_file(custom_words_path)


# -----------------------------------------------------------------------------


@app.route("/api/train", methods=["POST"])
async def api_train() -> str:
    """Generate speech/intent artifacts for profile."""
    no_cache = request.args.get("nocache", "false").lower() == "true"

    assert core is not None

    start_time = time.time()
    logger.info("Starting training")

    result = await core.train(no_cache=no_cache)
    if isinstance(result, ProfileTrainingFailed):
        raise Exception(f"Training failed: {result.reason}")

    end_time = time.time()

    return "Training completed in %0.2f second(s)" % (end_time - start_time)


# -----------------------------------------------------------------------------


@app.route("/api/restart", methods=["POST"])
async def api_restart() -> str:
    """Restart Rhasspy actors."""
    assert core is not None
    logger.debug("Restarting Rhasspy")

    # Stop
    await core.shutdown()

    # Start
    await start_rhasspy()
    logger.info("Restarted Rhasspy")

    return "Restarted Rhasspy"


# -----------------------------------------------------------------------------


@app.route("/api/speech-to-text", methods=["POST"])
async def api_speech_to_text() -> str:
    """Transcribe speech from WAV file."""
    no_header = request.args.get("noheader", "false").lower() == "true"
    assert core is not None

    # Prefer 16-bit 16Khz mono, but will convert with sox if needed
    wav_data = await request.data
    if no_header:
        # Wrap in WAV
        wav_data = buffer_to_wav(wav_data)

    start_time = time.perf_counter()
    result = await core.transcribe_wav(wav_data)
    end_time = time.perf_counter()

    if prefers_json():
        return jsonify(
            {
                "text": result.text,
                "likelihood": result.confidence,
                "transcribe_seconds": (end_time - start_time),
                "wav_seconds": get_wav_duration(wav_data),
            }
        )

    return result.text


# -----------------------------------------------------------------------------


@app.route("/api/text-to-intent", methods=["POST"])
async def api_text_to_intent():
    """Recgonize intent from text and optionally handle."""
    assert core is not None
    data = await request.data
    text = data.decode()
    no_hass = request.args.get("nohass", "false").lower() == "true"

    # Convert text to intent
    start_time = time.time()
    intent = (await core.recognize_intent(text)).intent
    intent["speech_confidence"] = 1

    intent_sec = time.time() - start_time
    intent["time_sec"] = intent_sec

    intent_json = json.dumps(intent)
    logger.debug(intent_json)
    await add_ws_event(WS_EVENT_INTENT, intent_json)

    if not no_hass:
        # Send intent to Home Assistant
        intent = (await core.handle_intent(intent)).intent

    return jsonify(intent)


# -----------------------------------------------------------------------------


@app.route("/api/speech-to-intent", methods=["POST"])
async def api_speech_to_intent() -> Response:
    """Transcribe speech, recognize intent, and optionally handle."""
    assert core is not None
    no_hass = request.args.get("nohass", "false").lower() == "true"

    # Prefer 16-bit 16Khz mono, but will convert with sox if needed
    wav_data = await request.data

    # speech -> text
    start_time = time.time()
    transcription = await core.transcribe_wav(wav_data)
    text = transcription.text
    logger.debug(text)

    # text -> intent
    intent = (await core.recognize_intent(text)).intent
    intent["speech_confidence"] = transcription.confidence

    intent_sec = time.time() - start_time
    intent["time_sec"] = intent_sec

    intent_json = json.dumps(intent)
    logger.debug(intent_json)
    await add_ws_event(WS_EVENT_INTENT, intent_json)

    if not no_hass:
        # Send intent to Home Assistant
        intent = (await core.handle_intent(intent)).intent

    return jsonify(intent)


# -----------------------------------------------------------------------------


@app.route("/api/start-recording", methods=["POST"])
async def api_start_recording() -> str:
    """Begin recording voice command."""
    assert core is not None
    buffer_name = request.args.get("name", "")
    core.start_recording_wav(buffer_name)

    return "OK"


@app.route("/api/stop-recording", methods=["POST"])
async def api_stop_recording() -> Response:
    """End recording voice command. Transcribe and handle."""
    assert core is not None
    no_hass = request.args.get("nohass", "false").lower() == "true"

    buffer_name = request.args.get("name", "")
    audio_data = (await core.stop_recording_wav(buffer_name)).data

    wav_data = buffer_to_wav(audio_data)
    logger.debug("Recorded %s byte(s) of audio data", len(wav_data))

    transcription = await core.transcribe_wav(wav_data)
    text = transcription.text
    logger.debug(text)

    intent = (await core.recognize_intent(text)).intent
    intent["speech_confidence"] = transcription.confidence

    intent_json = json.dumps(intent)
    logger.debug(intent_json)
    await add_ws_event(WS_EVENT_INTENT, intent_json)

    if not no_hass:
        # Send intent to Home Assistant
        intent = (await core.handle_intent(intent)).intent

    return jsonify(intent)


# -----------------------------------------------------------------------------


@app.route("/api/unknown-words", methods=["GET"])
async def api_unknown_words() -> Response:
    """Get list of unknown words."""
    assert core is not None
    speech_system = core.profile.get("speech_to_text.system", "pocketsphinx")
    unknown_words = {}
    unknown_path = Path(
        core.profile.read_path(
            core.profile.get(
                f"speech_to_text.{speech_system}.unknown_words", "unknown_words.txt"
            )
        )
    )

    if unknown_path.is_file():
        for line in open(unknown_path, "r"):
            line = line.strip()
            if line:
                word, pronunciation = re.split(r"[ ]+", line, maxsplit=1)
                unknown_words[word] = pronunciation

    return jsonify(unknown_words)


# -----------------------------------------------------------------------------

last_sentence = ""


@app.route("/api/text-to-speech", methods=["POST"])
async def api_text_to_speech() -> Union[bytes, str]:
    """Speak a sentence with text to speech system."""
    global last_sentence
    repeat = request.args.get("repeat", "false").strip().lower() == "true"
    play = request.args.get("play", "true").strip().lower() == "true"
    language = request.args.get("language")
    voice = request.args.get("voice")
    data = await request.data
    sentence = last_sentence if repeat else data.decode().strip()

    assert core is not None
    result = await core.speak_sentence(
        sentence, play=play, language=language, voice=voice
    )

    last_sentence = sentence

    if not play:
        # Return WAV data instead of speaking
        return result.wav_data

    return sentence


# -----------------------------------------------------------------------------


@app.route("/api/slots", methods=["GET", "POST"])
async def api_slots() -> Union[str, Response]:
    """Get the values of all slots."""
    assert core is not None

    if request.method == "POST":
        overwrite_all = request.args.get("overwrite_all", "false").lower() == "true"
        new_slot_values = json5.loads(await request.data)

        word_casing = core.profile.get(
            "speech_to_text.dictionary_casing", "ignore"
        ).lower()
        word_transform = lambda s: s

        if word_casing == "lower":
            word_transform = str.lower
        elif word_casing == "upper":
            word_transform = str.upper

        slots_dir = Path(
            core.profile.write_path(
                core.profile.get("speech_to_text.slots_dir", "slots")
            )
        )

        if overwrite_all:
            # Remote existing values first
            for name in new_slot_values:
                slots_path = safe_join(slots_dir, f"{name}")
                if slots_path.is_file():
                    try:
                        slots_path.unlink()
                    except Exception:
                        logger.exception("api_slots")

        for name, values in new_slot_values.items():
            if isinstance(values, str):
                values = [values]

            slots_path = slots_dir / name

            # Create directories
            slots_path.parent.mkdir(parents=True, exist_ok=True)

            # Merge with existing values
            values = {word_transform(v.strip()) for v in values}
            if slots_path.is_file():
                values.update(
                    word_transform(line.strip())
                    for line in slots_path.read_text().splitlines()
                )

            # Write merged values
            if values:
                with open(slots_path, "w") as slots_file:
                    for value in values:
                        if value:
                            print(value, file=slots_file)

        return "OK"

    # Read slots into dictionary
    slots_dir = Path(
        core.profile.read_path(core.profile.get("speech_to_text.slots_dir", "slots"))
    )

    slots_dict = {}

    if slots_dir.is_dir():
        for slot_file_path in slots_dir.glob("*"):
            if slot_file_path.is_file():
                slot_name = slot_file_path.name
                slots_dict[slot_name] = [
                    line.strip() for line in slot_file_path.read_text().splitlines()
                ]

    return jsonify(slots_dict)


@app.route("/api/slots/<name>", methods=["GET", "POST"])
def api_slots_by_name(name: str) -> Union[str, Response]:
    """Get or set the values of a slot list."""
    assert core is not None
    overwrite_all = request.args.get("overwrite_all", "false").lower() == "true"

    slots_dir = Path(
        core.profile.read_path(core.profile.get("speech_to_text.slots_dir", "slots"))
    )

    if request.method == "POST":
        if overwrite_all:
            # Remote existing values first
            slots_path = safe_join(slots_dir, f"{name}")
            if slots_path.is_file():
                try:
                    slots_path.unlink()
                except Exception:
                    logger.exception("api_slots_by_name")

        slots_path = Path(
            core.profile.write_path(
                core.profile.get("speech_to_text.slots_dir", "slots"), f"{name}"
            )
        )

        # Create directories
        slots_path.parent.mkdir(parents=True, exist_ok=True)

        # Write data
        with open(slots_path, "wb") as slots_file:
            slots_file.write(request.data)

        return f"Wrote {len(request.data)} byte(s) to {slots_path}"

    # Load slots values
    slot_values: List[str] = []
    slot_file_path = slots_dir / name
    if slot_file_path.is_file():
        slot_values = [line.strip() for line in slot_file_path.read_text().splitlines()]

    return jsonify(slot_values)


# -----------------------------------------------------------------------------


@app.route("/api/intents")
def api_intents():
    """Return JSON with information about intents."""
    assert core is not None

    sentences_ini = Path(
        core.profile.read_path(core.profile.get("speech_to_text.sentences_ini"))
    )

    sentences_dir = Path(
        core.profile.read_path(core.profile.get("speech_to_text.sentences_dir"))
    )

    # Load all .ini files and parse
    ini_paths: List[Path] = get_ini_paths(sentences_ini, sentences_dir)
    intents: Dict[str, Any] = get_all_intents(ini_paths)

    def add_type(item, item_dict: Dict[str, Any]):
        """Add item_type to expression dictionary."""
        item_dict["item_type"] = type(item).__name__
        if hasattr(item, "items"):
            # Group, alternative, etc.
            for sub_item, sub_item_dict in zip(item.items, item_dict["items"]):
                add_type(sub_item, sub_item_dict)
        elif hasattr(item, "rule_body"):
            # Rule
            add_type(item.rule_body, item_dict["rule_body"])

    # Convert to dictionary
    intents_dict = {}
    for intent_name, intent_sentences in intents.items():
        sentence_dicts = []
        for sentence in intent_sentences:
            sentence_dict = attr.asdict(sentence)

            # Add item_type field
            add_type(sentence, sentence_dict)
            sentence_dicts.append(sentence_dict)

        intents_dict[intent_name] = sentence_dicts

    # Convert to JSON
    return jsonify(intents_dict)


# -----------------------------------------------------------------------------


@app.route("/process", methods=["GET"])
async def marytts_process():
    """Emulate MaryTTS /process API"""
    global last_sentence

    assert core is not None
    sentence = request.args.get("INPUT_TEXT", "")
    voice = request.args.get("VOICE")
    locale = request.args.get("LOCALE")
    spoken = await core.speak_sentence(
        sentence, play=False, voice=voice, language=locale
    )

    return spoken.wav_data


# -----------------------------------------------------------------------------


@app.errorhandler(Exception)
async def handle_error(err) -> Tuple[str, int]:
    """Return error as text."""
    logger.exception(err)
    return (str(err), 500)


# ---------------------------------------------------------------------
# Static Routes
# ---------------------------------------------------------------------

web_dir = Path("dist")
assert web_dir.is_dir(), f"Missing web directory {web_dir}"


css_dir = web_dir / "css"
js_dir = web_dir / "js"
img_dir = web_dir / "img"
webfonts_dir = web_dir / "webfonts"


@app.route("/css/<path:filename>", methods=["GET"])
async def css(filename) -> Response:
    """CSS static endpoint."""
    return await send_from_directory(css_dir, filename)


@app.route("/js/<path:filename>", methods=["GET"])
async def js(filename) -> Response:
    """Javascript static endpoint."""
    return await send_from_directory(js_dir, filename)


@app.route("/img/<path:filename>", methods=["GET"])
async def img(filename) -> Response:
    """Image static endpoint."""
    return await send_from_directory(img_dir, filename)


@app.route("/webfonts/<path:filename>", methods=["GET"])
async def webfonts(filename) -> Response:
    """Web font static endpoint."""
    return await send_from_directory(webfonts_dir, filename)


# ----------------------------------------------------------------------------
# HTML Page Routes
# ----------------------------------------------------------------------------


@app.route("/", methods=["GET"])
async def index() -> Response:
    """Render main web page."""
    return await send_file(web_dir / "index.html")


@app.route("/swagger.yaml", methods=["GET"])
async def swagger_yaml() -> Response:
    """OpenAPI static endpoint."""
    return await send_file(web_dir / "swagger.yaml")


# -----------------------------------------------------------------------------
# WebSocket API
# -----------------------------------------------------------------------------

WS_EVENT_INTENT = 0
WS_EVENT_LOG = 1

ws_queues: List[List[asyncio.Queue]] = [[], []]
ws_locks: List[asyncio.Lock] = [asyncio.Lock(), asyncio.Lock()]


async def add_ws_event(event_type: int, text: str):
    """Send text out to all websockets for a specific event."""
    async with ws_locks[event_type]:
        for q in ws_queues[event_type]:
            await q.put(text)


# Send logging messages out to websocket
logging.root.addHandler(
    FunctionLoggingHandler(
        lambda msg: asyncio.run_coroutine_threadsafe(
            add_ws_event(WS_EVENT_LOG, msg), loop
        )
    )
)


class WebSocketObserver(RhasspyActor):
    """Observe the dialogue manager and output intents to the websocket."""

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, IntentRecognized):
            # Add slots
            intent_slots = {}
            for ev in message.intent.get("entities", []):
                intent_slots[ev["entity"]] = ev["value"]

            message.intent["slots"] = intent_slots

            # Convert to JSON
            intent_json = json.dumps(message.intent)
            self._logger.debug(intent_json)
            asyncio.run_coroutine_threadsafe(
                add_ws_event(WS_EVENT_INTENT, intent_json), loop
            )


@app.websocket("/api/events/intent")
async def api_events_intent() -> None:
    """Websocket endpoint to receive intents as JSON."""
    # Add new queue for websocket
    q: asyncio.Queue = asyncio.Queue()
    async with ws_locks[WS_EVENT_INTENT]:
        ws_queues[WS_EVENT_INTENT].append(q)

    try:
        while True:
            text = await q.get()
            await websocket.send(text)
    except Exception:
        logger.exception("api_events_intent")

    # Remove queue
    async with ws_locks[WS_EVENT_INTENT]:
        ws_queues[WS_EVENT_INTENT].remove(q)


@app.websocket("/api/events/log")
async def api_events_log() -> None:
    """Websocket endpoint to receive logging messages as text."""
    # Add new queue for websocket
    q: asyncio.Queue = asyncio.Queue()
    async with ws_locks[WS_EVENT_LOG]:
        ws_queues[WS_EVENT_LOG].append(q)

    try:
        while True:
            text = await q.get()
            await websocket.send(text)
    except Exception:
        logger.exception("api_events_log")

    # Remove queue
    async with ws_locks[WS_EVENT_LOG]:
        ws_queues[WS_EVENT_LOG].remove(q)


# -----------------------------------------------------------------------------

# Swagger UI
quart_api_doc(
    app, config_path=(web_dir / "swagger.yaml"), url_prefix="/api", title="Rhasspy API"
)

# -----------------------------------------------------------------------------


def prefers_json() -> bool:
    """True if client prefers JSON over plain text."""
    return quality(request.accept_mimetypes, "application/json") > quality(
        request.accept_mimetypes, "text/plain"
    )


def quality(accept, key: str) -> float:
    """Return Accept quality for media type."""
    for option in accept.options:
        # pylint: disable=W0212
        if accept._values_match(key, option.value):
            return option.quality
    return 0.0


# -----------------------------------------------------------------------------

# Start Rhasspy actors
loop.run_until_complete(start_rhasspy())

# -----------------------------------------------------------------------------

# Start web server
if args.ssl is not None:
    logger.debug("Using SSL with certfile, keyfile = %s", args.ssl)
    certfile = args.ssl[0]
    keyfile = args.ssl[1]
    protocol = "https"
else:
    certfile = None
    keyfile = None
    protocol = "http"

logger.debug("Starting web server at %s://%s:%s", protocol, args.host, args.port)

try:
    app.run(host=args.host, port=args.port, certfile=certfile, keyfile=keyfile)
except KeyboardInterrupt:
    pass
