#!/usr/bin/env python3
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
from typing import Any, Union, Tuple, Dict, List

from flask import (
    Flask,
    request,
    Response,
    jsonify,
    safe_join,
    send_file,
    send_from_directory,
)
from flask_cors import CORS
from flask_sockets import Sockets
import requests
import pydash
import gevent
from gevent import pywsgi
from gevent.queue import Queue as GQueue
from gevent.lock import RLock
from geventwebsocket.handler import WebSocketHandler


from jsgf2fst import read_slots

from rhasspy.profiles import Profile
from rhasspy.core import RhasspyCore
from rhasspy.dialogue import ProfileTrainingFailed
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

app = Flask("rhasspy")
app.secret_key = str(uuid4())
CORS(app)
sockets = Sockets(app)

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
        core.shutdown()
        core = None


def start_rhasspy() -> None:
    global core

    default_settings = Profile.load_defaults(system_profiles_dir)

    # Load core
    core = RhasspyCore(args.profile, system_profiles_dir, user_profiles_dir)

    # Set environment variables
    os.environ["RHASSPY_BASE_DIR"] = os.getcwd()
    os.environ["RHASSPY_PROFILE"] = core.profile.name
    os.environ["RHASSPY_PROFILE_DIR"] = core.profile.write_dir()
    if not os.path.exists(os.environ["RHASSPY_TTS_DIR"]):
        os.mkdir(os.environ["RHASSPY_TTS_DIR"])

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

    core.start()
    logger.info("Started")


# -----------------------------------------------------------------------------

start_rhasspy()

# -----------------------------------------------------------------------------
# HTTP API
# -----------------------------------------------------------------------------


@app.route("/api/profiles")
def api_profiles() -> Response:
    """Get list of available profiles"""
    assert core is not None
    profile_names = set()
    for profiles_dir in profiles_dirs:
        if not os.path.exists(profiles_dir):
            continue

        for name in os.listdir(profiles_dir):
            profile_dir = os.path.join(profiles_dir, name)
            if os.path.isdir(profile_dir):
                profile_names.add(name)

    check_path = core.profile.read_path("check-profile.sh")
    assert os.path.exists(check_path), "Missing profile check script"
    check_cmd = ["bash", check_path, core.profile.write_path()]
    logger.debug(check_cmd)

    downloaded = True
    try:
        output = subprocess.check_output(check_cmd, stderr=subprocess.STDOUT).decode()
    except subprocess.CalledProcessError as e:
        output = e.output.decode()
        logger.warning(output)
        downloaded = False

    return jsonify(
        {
            "default_profile": core.profile.name,
            "profiles": sorted(list(profile_names)),
            "downloaded": downloaded,
        }
    )


# -----------------------------------------------------------------------------


@app.route("/api/download-profile", methods=["POST"])
def api_download_profile() -> str:
    """Downloads the current profile."""
    assert core is not None
    delete = request.args.get("delete", "false").lower() == "true"

    download_script = os.path.abspath(core.profile.read_path("download-profile.sh"))
    logger.debug(download_script)
    assert os.path.exists(download_script), "Profile download script is missing."
    download_cmd = ["bash", download_script, core.profile.write_path()]

    if delete:
        download_cmd.append("--delete")

    logger.debug(download_cmd)

    try:
        output = subprocess.check_output(
            download_cmd, stderr=subprocess.STDOUT
        ).decode()
    except subprocess.CalledProcessError as e:
        logger.exception("download profile")
        output = e.output.decode()
        logger.error(output)
        raise Exception(output)

    return output


# -----------------------------------------------------------------------------


@app.route("/api/microphones", methods=["GET"])
def api_microphones() -> Response:
    """Get a dictionary of available recording devices"""
    assert core is not None
    system = request.args.get("system", None)
    return jsonify(core.get_microphones(system))


# -----------------------------------------------------------------------------


@app.route("/api/test-microphones", methods=["GET"])
def api_test_microphones() -> Response:
    """Get a dictionary of available, functioning recording devices"""
    assert core is not None
    system = request.args.get("system", None)
    return jsonify(core.test_microphones(system))


# -----------------------------------------------------------------------------


@app.route("/api/speakers", methods=["GET"])
def api_speakers() -> Response:
    """Get a dictionary of available playback devices"""
    assert core is not None
    system = request.args.get("system", None)
    return jsonify(core.get_speakers(system))


# -----------------------------------------------------------------------------


@app.route("/api/listen-for-wake", methods=["POST"])
def api_listen_for_wake() -> str:
    """Make Rhasspy listen for a wake word"""
    assert core is not None
    core.listen_for_wake()
    return "OK"


# -----------------------------------------------------------------------------


@app.route("/api/listen-for-command", methods=["POST"])
def api_listen_for_command() -> Response:
    """Wake Rhasspy up and listen for a voice command"""
    assert core is not None
    no_hass = request.args.get("nohass", "false").lower() == "true"
    return jsonify(core.listen_for_command(handle=not no_hass))


# -----------------------------------------------------------------------------


@app.route("/api/profile", methods=["GET", "POST"])
def api_profile() -> Union[str, Response]:
    """Read or write profile JSON directly"""
    assert core is not None
    layers = request.args.get("layers", "all")

    if request.method == "POST":
        # Ensure that JSON is valid
        profile_json = json.loads(request.data)
        # from cerberus import Validator

        # schema_path = os.path.join(
        #     os.path.dirname(__file__), "rhasspy", "profile_schema.json"
        # )

        # with open(schema_path, "r") as schema_file:
        #     v = Validator(json.load(schema_file))
        #     profile_dict = json.loads(request.data)
        #     if not v.validate(profile_dict):
        #         print(json.dumps(profile_dict, indent=4))
        #         raise Exception(str(v._errors[0].info))

        recursive_remove(core.defaults, profile_json)

        profile_path = os.path.abspath(core.profile.write_path("profile.json"))
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
        profile_path = core.profile.read_path("profile.json")
        return send_file(open(profile_path, "rb"), mimetype="application/json")
    else:
        return jsonify(core.profile.json)


# -----------------------------------------------------------------------------


@app.route("/api/lookup", methods=["POST"])
def api_lookup() -> Response:
    """Get CMU phonemes from dictionary or guessed pronunciation(s)"""
    assert core is not None
    n = int(request.args.get("n", 5))
    assert n > 0, "No pronunciations requested"

    word = request.data.decode("utf-8").strip().lower()
    assert len(word) > 0, "No word to look up"

    pronunciations = core.get_word_pronunciations([word], n).pronunciations
    return jsonify(pronunciations[word])


# -----------------------------------------------------------------------------


@app.route("/api/pronounce", methods=["POST"])
def api_pronounce() -> Union[Response, str]:
    """Pronounce CMU phonemes or word using eSpeak"""
    assert core is not None
    download = request.args.get("download", "false").lower() == "true"

    pronounce_str = request.data.decode("utf-8").strip()
    assert len(pronounce_str) > 0, "No string to pronounce"

    # phonemes or word
    pronounce_type = request.args.get("type", "phonemes")

    if pronounce_type == "phonemes":
        # Convert from Sphinx to espeak phonemes
        espeak_str = core.get_word_phonemes(pronounce_str).phonemes
    else:
        # Speak word directly
        espeak_str = pronounce_str

    result = core.speak_word(espeak_str)
    wav_data = result.wav_data
    espeak_phonemes = result.phonemes

    if download:
        # Return WAV
        return Response(wav_data, mimetype="audio/wav")
    else:
        # Play through speakers
        core.play_wav_data(wav_data)
        return espeak_phonemes


# -----------------------------------------------------------------------------


@app.route("/api/play-wav", methods=["POST"])
def api_play_wav() -> str:
    """Play WAV data through the configured audio output system"""
    assert core is not None

    # Play through speakers
    logger.debug(f"Playing {len(request.data)} byte(s)")
    core.play_wav_data(request.data)

    return "OK"


# -----------------------------------------------------------------------------


@app.route("/api/phonemes")
def api_phonemes():
    """Get phonemes and example words for a profile"""
    assert core is not None
    examples_path = core.profile.read_path(
        core.profile.get("text_to_speech.phoneme_examples", "phoneme_examples.txt")
    )

    # phoneme -> { word, phonemes }
    logger.debug("Loading phoneme examples from %s" % examples_path)
    examples_dict = load_phoneme_examples(examples_path)

    return jsonify(examples_dict)


# -----------------------------------------------------------------------------


@app.route("/api/sentences", methods=["GET", "POST"])
def api_sentences():
    """Read or write sentences for a profile"""
    assert core is not None

    if request.method == "POST":
        # Update sentences
        sentences_path = core.profile.write_path(
            core.profile.get("speech_to_text.sentences_ini")
        )

        with open(sentences_path, "wb") as sentences_file:
            sentences_file.write(request.data)
            return "Wrote %s byte(s) to %s" % (len(request.data), sentences_path)

    # Return sentences
    sentences_path = core.profile.read_path(
        core.profile.get("speech_to_text.sentences_ini")
    )

    if not os.path.exists(sentences_path):
        return ""  # no sentences yet

    # Return file contents
    return send_file(open(sentences_path, "rb"), mimetype="text/plain")


# -----------------------------------------------------------------------------


@app.route("/api/custom-words", methods=["GET", "POST"])
def api_custom_words():
    """Read or write custom word dictionary for a profile"""
    assert core is not None
    if request.method == "POST":
        custom_words_path = core.profile.write_path(
            core.profile.get("speech_to_text.pocketsphinx.custom_words")
        )

        # Update custom words
        lines_written = 0
        with open(custom_words_path, "w") as custom_words_file:
            lines = request.data.decode().splitlines()
            for line in lines:
                line = line.strip()
                if len(line) == 0:
                    continue

                print(line, file=custom_words_file)
                lines_written += 1

            return "Wrote %s line(s) to %s" % (lines_written, custom_words_path)

    custom_words_path = core.profile.read_path(
        core.profile.get("speech_to_text.pocketsphinx.custom_words")
    )

    # Return custom_words
    if not os.path.exists(custom_words_path):
        return ""  # no custom_words yet

    # Return file contents
    return send_file(open(custom_words_path, "rb"), mimetype="text/plain")


# -----------------------------------------------------------------------------


@app.route("/api/train", methods=["POST"])
def api_train() -> str:
    assert core is not None
    start_time = time.time()
    logger.info("Starting training")

    result = gevent.spawn(core.train).get()
    if isinstance(result, ProfileTrainingFailed):
        raise Exception(f"Training failed: {result.reason}")

    end_time = time.time()

    return "Training completed in %0.2f second(s)" % (end_time - start_time)


# -----------------------------------------------------------------------------


@app.route("/api/restart", methods=["POST"])
def api_restart() -> str:
    assert core is not None
    logger.debug("Restarting Rhasspy")

    # Stop
    core.shutdown()

    # Start
    start_rhasspy()
    logger.info("Restarted Rhasspy")

    return "Restarted Rhasspy"


# -----------------------------------------------------------------------------

# Get text from a WAV file
@app.route("/api/speech-to-text", methods=["POST"])
def api_speech_to_text() -> str:
    """speech -> text"""
    assert core is not None
    # Prefer 16-bit 16Khz mono, but will convert with sox if needed
    wav_data = request.data
    return core.transcribe_wav(wav_data).text


# -----------------------------------------------------------------------------

# Get intent from text
@app.route("/api/text-to-intent", methods=["POST"])
def api_text_to_intent():
    """text -> intent"""
    assert core is not None
    text = request.data.decode()
    no_hass = request.args.get("nohass", "false").lower() == "true"

    # Convert text to intent
    start_time = time.time()
    intent = core.recognize_intent(text).intent
    intent["speech_confidence"] = 1

    intent_sec = time.time() - start_time
    intent["time_sec"] = intent_sec

    intent_json = json.dumps(intent)
    logger.debug(intent_json)
    add_ws_event(WS_EVENT_INTENT, intent_json)

    if not no_hass:
        # Send intent to Home Assistant
        intent = core.handle_intent(intent).intent

    return jsonify(intent)


# -----------------------------------------------------------------------------

# Get intent from a WAV file
@app.route("/api/speech-to-intent", methods=["POST"])
def api_speech_to_intent() -> Response:
    """speech -> text -> intent"""
    assert core is not None
    no_hass = request.args.get("nohass", "false").lower() == "true"

    # Prefer 16-bit 16Khz mono, but will convert with sox if needed
    wav_data = request.data

    # speech -> text
    start_time = time.time()
    transcription = core.transcribe_wav(wav_data)
    text = transcription.text
    logger.debug(text)

    # text -> intent
    intent = core.recognize_intent(text).intent
    intent["speech_confidence"] = transcription.confidence

    intent_sec = time.time() - start_time
    intent["time_sec"] = intent_sec

    intent_json = json.dumps(intent)
    logger.debug(intent_json)
    add_ws_event(WS_EVENT_INTENT, intent_json)

    if not no_hass:
        # Send intent to Home Assistant
        intent = core.handle_intent(intent).intent

    return jsonify(intent)


# -----------------------------------------------------------------------------

# Start recording a WAV file to a temporary buffer
@app.route("/api/start-recording", methods=["POST"])
def api_start_recording() -> str:
    """Begin recording voice command"""
    assert core is not None
    buffer_name = request.args.get("name", "")
    core.start_recording_wav(buffer_name)

    return "OK"


# Stop recording WAV file, transcribe, and get intent
@app.route("/api/stop-recording", methods=["POST"])
def api_stop_recording() -> Response:
    """End recording voice command. Transcribe and handle."""
    assert core is not None
    no_hass = request.args.get("nohass", "false").lower() == "true"

    buffer_name = request.args.get("name", "")
    audio_data = core.stop_recording_wav(buffer_name).data

    wav_data = buffer_to_wav(audio_data)
    logger.debug("Recorded %s byte(s) of audio data" % len(wav_data))

    transcription = core.transcribe_wav(wav_data)
    text = transcription.text
    logger.debug(text)

    intent = core.recognize_intent(text).intent
    intent["speech_confidence"] = transcription.confidence

    intent_json = json.dumps(intent)
    logger.debug(intent_json)
    add_ws_event(WS_EVENT_INTENT, intent_json)

    if not no_hass:
        # Send intent to Home Assistant
        intent = core.handle_intent(intent).intent

    return jsonify(intent)


# -----------------------------------------------------------------------------


@app.route("/api/unknown_words", methods=["GET"])
def api_unknown_words() -> Response:
    """Get list of unknown words"""
    assert core is not None
    unknown_words = {}
    unknown_path = core.profile.read_path(
        core.profile.get("speech_to_text.pocketsphinx.unknown_words")
    )

    if os.path.exists(unknown_path):
        for line in open(unknown_path, "r"):
            line = line.strip()
            if len(line) > 0:
                word, pronunciation = re.split(r"\s+", line, maxsplit=1)
                unknown_words[word] = pronunciation

    return jsonify(unknown_words)


# -----------------------------------------------------------------------------


@app.route("/api/text-to-speech", methods=["POST"])
def api_text_to_speech() -> str:
    """Speaks a sentence with text to speech system"""
    sentence = request.data.decode().strip()

    assert core is not None
    core.speak_sentence(sentence)

    return sentence


# -----------------------------------------------------------------------------


@app.route("/api/slots", methods=["GET", "POST"])
def api_slots() -> Union[str, Response]:
    """Get the values of all slots"""
    assert core is not None
    overwrite_all = request.args.get("overwrite_all", "false").lower() == "true"
    new_slot_values = json.loads(request.data)

    slots_dir = core.profile.read_path(
        core.profile.get("speech_to_text.slots_dir", "slots")
    )

    if request.method == "POST":
        if overwrite_all:
            # Remote existing values first
            for name in new_slot_values.keys():
                slots_path = safe_join(slots_dir, f"{name}")
                if os.path.exists(slots_path):
                    try:
                        os.unlink(slots_path)
                    except:
                        logger.exception("api_slots")

        for name, values in new_slot_values.items():
            slots_path = core.profile.write_path(
                core.profile.get("speech_to_text.slots_dir", "slots"), f"{name}"
            )

            # Create directories
            os.makedirs(os.path.split(slots_path)[0], exist_ok=True)

            # Write data
            with open(slots_path, "w") as slots_file:
                for value in values:
                    value = value.strip()
                    if len(value) > 0:
                        print(value, file=slots_file)

        return "OK"

    # Load slots values
    slots_dir = core.profile.read_path(core.profile.get("speech_to_text.slots_dir"))

    return jsonify(read_slots(slots_dir))


@app.route("/api/slots/<name>", methods=["GET", "POST"])
def api_slots_by_name(name: str) -> Union[str, Response]:
    """Get or sets the values of a slot list"""
    assert core is not None
    overwrite_all = request.args.get("overwrite_all", "false").lower() == "true"

    slots_dir = core.profile.read_path(
        core.profile.get("speech_to_text.slots_dir", "slots")
    )

    if request.method == "POST":
        if overwrite_all:
            # Remote existing values first
            slots_path = safe_join(slots_dir, f"{name}")
            if os.path.exists(slots_path):
                try:
                    os.unlink(slots_path)
                except:
                    logger.exception("api_slots_by_name")

        slots_path = core.profile.write_path(
            core.profile.get("speech_to_text.slots_dir", "slots"), f"{name}"
        )

        # Create directories
        os.makedirs(os.path.split(slots_path)[0], exist_ok=True)

        # Write data
        with open(slots_path, "wb") as slots_file:
            slots_file.write(request.data)

        return f"Wrote {len(request.data)} byte(s) to {slots_path}"

    # Load slots values
    slot_values = read_slots(slots_dir)

    return "\n".join(slot_values.get(name, []))


# -----------------------------------------------------------------------------


@app.errorhandler(Exception)
def handle_error(err) -> Tuple[str, int]:
    logger.exception(err)
    return (str(err), 500)


# ---------------------------------------------------------------------
# Static Routes
# ---------------------------------------------------------------------

web_dir = os.path.join(os.getcwd(), "dist")


@app.route("/css/<path:filename>", methods=["GET"])
def css(filename) -> Response:
    return send_from_directory(os.path.join(web_dir, "css"), filename)


@app.route("/js/<path:filename>", methods=["GET"])
def js(filename) -> Response:
    return send_from_directory(os.path.join(web_dir, "js"), filename)


@app.route("/img/<path:filename>", methods=["GET"])
def img(filename) -> Response:
    return send_from_directory(os.path.join(web_dir, "img"), filename)


@app.route("/webfonts/<path:filename>", methods=["GET"])
def webfonts(filename) -> Response:
    return send_from_directory(os.path.join(web_dir, "webfonts"), filename)


# ----------------------------------------------------------------------------
# HTML Page Routes
# ----------------------------------------------------------------------------


@app.route("/", methods=["GET"])
def index() -> Response:
    return send_file(os.path.join(web_dir, "index.html"))


@app.route("/swagger.yaml", methods=["GET"])
def swagger_yaml() -> Response:
    return send_file(os.path.join(web_dir, "swagger.yaml"))


# -----------------------------------------------------------------------------

# Swagger/OpenAPI documentation
from flask_swagger_ui import get_swaggerui_blueprint

SWAGGER_URL = "/api"
API_URL = "/swagger.yaml"

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL, API_URL, config={"app_name": "Rhasspy API"}
)

app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

# -----------------------------------------------------------------------------
# WebSocket API
# -----------------------------------------------------------------------------

WS_EVENT_INTENT = 0
WS_EVENT_LOG = 1

ws_queues: List[Dict[Any, GQueue]] = [{}, {}]
ws_locks: List[RLock] = [RLock(), RLock()]


def add_ws_event(event_type: int, text: str):
    with ws_locks[event_type]:
        for queue in ws_queues[event_type].values():
            queue.put(text)


logging.root.addHandler(
    FunctionLoggingHandler(lambda msg: add_ws_event(WS_EVENT_LOG, msg))
)


@sockets.route("/api/events/intent")
def api_events_intent(ws) -> None:
    # Add new queue for websocket
    q = GQueue()
    with ws_locks[WS_EVENT_INTENT]:
        ws_queues[WS_EVENT_INTENT][ws] = q

    try:
        while not ws.closed:
            text = q.get()
            ws.send(text)
    except Exception as e:
        logging.exception("api_events_intent")

    # Remove queue
    with ws_locks[WS_EVENT_INTENT]:
        del ws_queues[WS_EVENT_INTENT][ws]


@sockets.route("/api/events/log")
def api_events_log(ws) -> None:
    # Add new queue for websocket
    q = GQueue()
    with ws_locks[WS_EVENT_LOG]:
        ws_queues[WS_EVENT_LOG][ws] = q

    try:
        while not ws.closed:
            text = q.get()
            ws.send(text)
    except Exception as e:
        logging.exception("api_events_log")

    # Remove queue
    with ws_locks[WS_EVENT_LOG]:
        del ws_queues[WS_EVENT_LOG][ws]


# -----------------------------------------------------------------------------

# Start web server
logging.debug(f"Starting web server at http://{args.host}:{args.port}")
server = pywsgi.WSGIServer((args.host, args.port), app, handler_class=WebSocketHandler)
logging.getLogger("geventwebsocket").setLevel(logging.INFO)

try:
    server.serve_forever()
except KeyboardInterrupt:
    pass
