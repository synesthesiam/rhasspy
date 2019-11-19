#!/usr/bin/env python3
import asyncio
import os
import logging
import sys
import subprocess
import json
import re
import gzip
import time
import io
import wave
import tempfile
import threading
import functools
import argparse
import shlex
import time
import atexit
from uuid import uuid4
from collections import defaultdict
from pathlib import Path
from typing import Any, Union, Tuple, Dict, List

from quart import (
    Quart,
    request,
    Response,
    jsonify,
    safe_join,
    send_file,
    send_from_directory,
    websocket,
)
from quart_cors import cors
import pydash

from rhasspy.profiles import Profile
from rhasspy.core import RhasspyCore
from rhasspy.actor import RhasspyActor, ActorSystem, ConfigureEvent
from rhasspy.dialogue import ProfileTrainingFailed
from rhasspy.intent import IntentRecognized
from rhasspy.utils import (
    recursive_update,
    recursive_remove,
    buffer_to_wav,
    load_phoneme_examples,
    FunctionLoggingHandler,
)

# -----------------------------------------------------------------------------
# Flask Web App Setup
# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)
logging.root.setLevel(logging.DEBUG)

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

args = parser.parse_args()
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
def shutdown(*args: Any, **kwargs: Any) -> None:
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
        except:
            pass

        logger.debug("Profile: {0}={1}".format(key, value))
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
            "profiles": sorted(list(profile_names)),
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
    return jsonify(await core.listen_for_command(handle=not no_hass))


# -----------------------------------------------------------------------------


@app.route("/api/profile", methods=["GET", "POST"])
async def api_profile() -> Union[str, Response]:
    """Read or write profile JSON directly"""
    assert core is not None
    layers = request.args.get("layers", "all")

    if request.method == "POST":
        # Ensure that JSON is valid
        profile_json = await request.json
        recursive_remove(core.profile.system_json, profile_json)

        profile_path = Path(core.profile.write_path("profile.json"))
        with open(profile_path, "w") as profile_file:
            json.dump(profile_json, profile_file, indent=4)

        msg = "Wrote profile to %s" % profile_path
        logger.debug(msg)
        return msg

    if layers == "defaults":
        # Read default settings
        return jsonify(core.defaults)
    elif layers == "profile":
        # Local settings only
        profile_path = Path(core.profile.read_path("profile.json"))
        return send_file(profile_path)  # , mimetype="application/json")
    else:
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
    assert len(word) > 0, "No word to look up"

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
    assert len(pronounce_str) > 0, "No string to pronounce"

    # phonemes or word
    pronounce_type = request.args.get("type", "phonemes")

    if pronounce_type == "phonemes":
        # Convert from Sphinx to espeak phonemes
        result = await core.get_word_phonemes(pronounce_str)
        espeak_str = result.phonemes
    else:
        # Speak word directly
        espeak_str = pronounce_str

    result = await core.speak_word(espeak_str)
    wav_data = result.wav_data
    espeak_phonemes = result.phonemes

    if download:
        # Return WAV
        return Response(wav_data)  # , mimetype="audio/wav")
    else:
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
            wav_data = await response.content

    # Play through speakers
    logger.debug("Playing %s byte(s)", len(wav_data))
    core.play_wav_data(wav_data)

    return "OK"


# -----------------------------------------------------------------------------


@app.route("/api/phonemes")
def api_phonemes():
    """Get phonemes and example words for a profile"""
    assert core is not None
    examples_path = Path(
        core.profile.read_path(
            core.profile.get("text_to_speech.phoneme_examples", "phoneme_examples.txt")
        )
    )

    # phoneme -> { word, phonemes }
    logger.debug("Loading phoneme examples from %s" % examples_path)
    examples_dict = load_phoneme_examples(examples_path)

    return jsonify(examples_dict)


# -----------------------------------------------------------------------------


@app.route("/api/sentences", methods=["GET", "POST"])
async def api_sentences():
    """Read or write sentences for a profile"""
    assert core is not None

    if request.method == "POST":
        # Update sentences
        sentences_path = Path(
            core.profile.write_path(core.profile.get("speech_to_text.sentences_ini"))
        )

        data = await request.data
        with open(sentences_path, "wb") as sentences_file:
            sentences_file.write(data)
            return "Wrote %s byte(s) to %s" % (len(data), sentences_path)

    # Return sentences
    sentences_path = Path(
        core.profile.read_path(core.profile.get("speech_to_text.sentences_ini"))
    )

    if not sentences_path.exists():
        return ""  # no sentences yet

    # Return file contents
    return await send_file(sentences_path)  # , mimetype="text/plain")


# -----------------------------------------------------------------------------


@app.route("/api/custom-words", methods=["GET", "POST"])
async def api_custom_words():
    """Read or write custom word dictionary for a profile"""
    assert core is not None
    if request.method == "POST":
        custom_words_path = Path(
            core.profile.write_path(
                core.profile.get("speech_to_text.pocketsphinx.custom_words")
            )
        )

        # Update custom words
        lines_written = 0
        with open(custom_words_path, "w") as custom_words_file:
            data = await request.data
            lines = data.decode().splitlines()
            for line in lines:
                line = line.strip()
                if len(line) == 0:
                    continue

                print(line, file=custom_words_file)
                lines_written += 1

            return "Wrote %s line(s) to %s" % (lines_written, custom_words_path)

    custom_words_path = Path(
        core.profile.read_path(
            core.profile.get("speech_to_text.pocketsphinx.custom_words")
        )
    )

    # Return custom_words
    if custom_words_path.exists():
        return ""  # no custom_words yet

    # Return file contents
    return await send_file(custom_words_path)  # , mimetype="text/plain")


# -----------------------------------------------------------------------------


@app.route("/api/train", methods=["POST"])
async def api_train() -> str:
    no_cache = request.args.get("nocache", "false").lower() == "true"

    assert core is not None

    if no_cache:
        # Delete doit database
        db_path = Path(core.profile.write_path(".doit.db"))
        if db_path.exists():
            logger.debug("Clearing training cache")
            db_path.unlink()

    start_time = time.time()
    logger.info("Starting training")

    result = await core.train()
    if isinstance(result, ProfileTrainingFailed):
        raise Exception(f"Training failed: {result.reason}")

    end_time = time.time()

    return "Training completed in %0.2f second(s)" % (end_time - start_time)


# -----------------------------------------------------------------------------


@app.route("/api/restart", methods=["POST"])
async def api_restart() -> str:
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
    """speech -> text"""
    no_header = request.args.get("noheader", "false").lower() == "true"
    assert core is not None

    # Prefer 16-bit 16Khz mono, but will convert with sox if needed
    wav_data = await request.data
    if no_header:
        # Wrap in WAV
        wav_data = buffer_to_wav(wav_data)

    result = await core.transcribe_wav(wav_data)
    return result.text


# -----------------------------------------------------------------------------


@app.route("/api/text-to-intent", methods=["POST"])
async def api_text_to_intent():
    """text -> intent"""
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
    """speech -> text -> intent"""
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
    """Begin recording voice command"""
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
    logger.debug("Recorded %s byte(s) of audio data" % len(wav_data))

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


@app.route("/api/unknown_words", methods=["GET"])
async def api_unknown_words() -> Response:
    """Get list of unknown words"""
    assert core is not None
    unknown_words = {}
    unknown_path = Path(
        core.profile.read_path(
            core.profile.get("speech_to_text.pocketsphinx.unknown_words")
        )
    )

    if unknown_path.exists():
        for line in open(unknown_path, "r"):
            line = line.strip()
            if len(line) > 0:
                word, pronunciation = re.split(r"[ ]+", line, maxsplit=1)
                unknown_words[word] = pronunciation

    return jsonify(unknown_words)


# -----------------------------------------------------------------------------

last_sentence = ""


@app.route("/api/text-to-speech", methods=["POST"])
async def api_text_to_speech() -> str:
    """Speaks a sentence with text to speech system"""
    global last_sentence
    repeat = request.args.get("repeat", "false").strip().lower() == "true"
    data = await request.data
    sentence = last_sentence if repeat else data.decode().strip()

    assert core is not None
    await core.speak_sentence(sentence)

    last_sentence = sentence

    return sentence


# -----------------------------------------------------------------------------


@app.route("/api/slots", methods=["GET", "POST"])
async def api_slots() -> Union[str, Response]:
    """Get the values of all slots"""
    assert core is not None

    slots_dir = Path(
        core.profile.read_path(core.profile.get("speech_to_text.slots_dir"))
    )

    if request.method == "POST":
        overwrite_all = request.args.get("overwrite_all", "false").lower() == "true"
        new_slot_values = await request.json

        if overwrite_all:
            # Remote existing values first
            for name in new_slot_values.keys():
                slots_path = safe_join(slots_dir, f"{name}")
                if slots_path.exists():
                    try:
                        slots_path.unlink()
                    except:
                        logger.exception("api_slots")

        for name, values in new_slot_values.items():
            if isinstance(values, str):
                values = [values]

            slots_path = Path(
                core.profile.write_path(
                    core.profile.get("speech_to_text.slots_dir", "slots"), f"{name}"
                )
            )

            # Create directories
            slots_path.parent.mkdir(parents=True, exist_ok=True)

            # Write data
            with open(slots_path, "w") as slots_file:
                for value in values:
                    value = value.strip()
                    if len(value) > 0:
                        print(value, file=slots_file)

        return "OK"

    # Read slots into dictionary
    slots_dict = {}
    for slot_file_path in slots_dir.glob("*"):
        if slot_file_path.is_file():
            slot_name = slot_file_path.name
            slots_dict[slot_name] = [
                line.strip() for line in slot_file_path.read_text().splitlines()
            ]

    return jsonify(slots_dict)


@app.route("/api/slots/<name>", methods=["GET", "POST"])
def api_slots_by_name(name: str) -> Union[str, Response]:
    """Get or sets the values of a slot list"""
    assert core is not None
    overwrite_all = request.args.get("overwrite_all", "false").lower() == "true"

    slots_dir = Path(
        core.profile.read_path(core.profile.get("speech_to_text.slots_dir", "slots"))
    )

    if request.method == "POST":
        if overwrite_all:
            # Remote existing values first
            slots_path = safe_join(slots_dir, f"{name}")
            if slots_path.exists():
                try:
                    slots_path.unlink()
                except:
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
    slot_values = read_slots(slots_dir)

    return "\n".join(slot_values.get(name, []))


# -----------------------------------------------------------------------------


@app.errorhandler(Exception)
async def handle_error(err) -> Tuple[str, int]:
    logger.exception(err)
    return (str(err), 500)


# ---------------------------------------------------------------------
# Static Routes
# ---------------------------------------------------------------------

web_dir = os.path.join(os.getcwd(), "dist")


@app.route("/css/<path:filename>", methods=["GET"])
async def css(filename) -> Response:
    return await send_from_directory(os.path.join(web_dir, "css"), filename)


@app.route("/js/<path:filename>", methods=["GET"])
async def js(filename) -> Response:
    return await send_from_directory(os.path.join(web_dir, "js"), filename)


@app.route("/img/<path:filename>", methods=["GET"])
async def img(filename) -> Response:
    return await send_from_directory(os.path.join(web_dir, "img"), filename)


@app.route("/webfonts/<path:filename>", methods=["GET"])
async def webfonts(filename) -> Response:
    return await send_from_directory(os.path.join(web_dir, "webfonts"), filename)


# ----------------------------------------------------------------------------
# HTML Page Routes
# ----------------------------------------------------------------------------


@app.route("/", methods=["GET"])
async def index() -> Response:
    return await send_file(os.path.join(web_dir, "index.html"))


@app.route("/swagger.yaml", methods=["GET"])
async def swagger_yaml() -> Response:
    return await send_file(os.path.join(web_dir, "swagger.yaml"))


# -----------------------------------------------------------------------------

# Swagger/OpenAPI documentation
# from flask_swagger_ui import get_swaggerui_blueprint

# SWAGGER_URL = "/api"
# API_URL = "/swagger.yaml"

# swaggerui_blueprint = get_swaggerui_blueprint(
#     SWAGGER_URL, API_URL, config={"app_name": "Rhasspy API"}
# )

# app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

# -----------------------------------------------------------------------------
# WebSocket API
# -----------------------------------------------------------------------------

WS_EVENT_INTENT = 0
WS_EVENT_LOG = 1

ws_queues: List[asyncio.Queue] = [[], []]
ws_locks: List[asyncio.Lock] = [asyncio.Lock(), asyncio.Lock()]


async def add_ws_event(event_type: int, text: str):
    async with ws_locks[event_type]:
        for queue in ws_queues[event_type]:
            await queue.put(text)


logging.root.addHandler(
    FunctionLoggingHandler(
        lambda msg: loop.call_soon_threadsafe(
            loop.create_task(add_ws_event(WS_EVENT_LOG, msg))
        )
    )
)


class WebSocketObserver(RhasspyActor):
    """Observes the dialogue manager and outputs intents to the websocket."""

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, IntentRecognized):
            # Add slots
            intent_slots = {}
            for ev in message.intent.get("entities", []):
                intent_slots[ev["entity"]] = ev["value"]

            message.intent["slots"] = intent_slots

            # Convert to JSON
            intent_json = json.dumps(message.intent)
            self._logger.debug(intent_json)
            loop.call_soon_threadsafe(
                loop.create_task(add_ws_event(WS_EVENT_INTENT, intent_json))
            )


@app.websocket("/api/events/intent")
async def api_events_intent(ws) -> None:
    # Add new queue for websocket
    q = asyncio.Queue()
    async with ws_locks[WS_EVENT_LOG]:
        ws_queues[WS_EVENT_LOG].append(q)

    try:
        while True:
            text = await q.get()
            await websocket.send(text)
    except Exception as e:
        logger.exception("api_events_intent")

    # Remove queue
    async with ws_locks[WS_EVENT_INTENT]:
        ws_queues[WS_EVENT_INTENT].remove(q)


@app.websocket("/api/events/log")
async def api_events_log() -> None:
    # Add new queue for websocket
    q = asyncio.Queue()
    async with ws_locks[WS_EVENT_LOG]:
        ws_queues[WS_EVENT_LOG].append(q)

    try:
        while True:
            text = await q.get()
            await websocket.send(text)
    except Exception as e:
        logger.exception("api_events_log")

    # Remove queue
    async with ws_locks[WS_EVENT_LOG]:
        ws_queues[WS_EVENT_LOG].remove(q)


# -----------------------------------------------------------------------------

loop.run_until_complete(start_rhasspy())

# -----------------------------------------------------------------------------

# Start web server
if args.ssl is not None:
    logger.debug(f"Using SSL with certfile, keyfile = {args.ssl}")
    certfile = args.ssl[0]
    keyfile = args.ssl[1]
    protocol = "https"
else:
    certfile = None
    keyfile = None
    protocol = "http"

logger.debug(f"Starting web server at {protocol}://{args.host}:{args.port}")

try:
    app.run(host=args.host, port=args.port, certfile=certfile, keyfile=keyfile)
except KeyboardInterrupt:
    pass
