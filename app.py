#!/usr/bin/env python3
import logging
logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

import os
import sys
import subprocess
import uuid
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

from flask import Flask, request, Response, jsonify, send_file, send_from_directory
from flask_cors import CORS
import requests
import pydash
from thespian.actors import ActorSystem

from rhasspy.core import RhasspyCore
from rhasspy.stt import TranscribeWav
from rhasspy.intent import RecognizeIntent
from rhasspy.intent_handler import HandleIntent
# from rhasspy.pronounce import WordPronounce
from rhasspy.utils import recursive_update, buffer_to_wav, load_phoneme_examples

# -----------------------------------------------------------------------------

system = ActorSystem('multiprocQueueBase')

# We really, *really* want shutdown to be called
@atexit.register
def shutdown(*args, **kwargs):
    global system
    if system is not None:
        system.shutdown()
        system = None

from rhasspy.actor import ConfigureEvent
from rhasspy.audio_recorder import PyAudioRecorder, StartRecordingToBuffer, StopRecordingToBuffer

# -----------------------------------------------------------------------------
# Flask Web App Setup
# -----------------------------------------------------------------------------

app = Flask('rhasspy')
app.secret_key = str(uuid.uuid4())
CORS(app)

# -----------------------------------------------------------------------------
# Parse Arguments
# -----------------------------------------------------------------------------

parser = argparse.ArgumentParser('Rhasspy')
parser.add_argument('--default', '-d', nargs=2,
                    action='append',
                    help='Set a default setting value',
                    default=[])

parser.add_argument('--set', '-s', nargs=2,
                    action='append',
                    help='Set a profile setting value',
                    default=[])

arg_str = os.environ.get('RHASSPY_ARGS', '')
args = parser.parse_args(shlex.split(arg_str))
logger.debug(args)

# -----------------------------------------------------------------------------
# Core Setup
# -----------------------------------------------------------------------------

core = None

def start_rhasspy():
    global core

    # Like PATH, searched in reverse order
    profiles_dirs = [path for path in
                    os.environ.get('RHASSPY_PROFILES', 'profiles')\
                    .split(':') if len(path.strip()) > 0]

    profiles_dirs.reverse()

    # Check for default profile
    default_profile_name = os.environ.get('RHASSPY_PROFILE', None)

    # Create top-level actor
    core = RhasspyCore(system, profiles_dirs, default_profile_name)

    # Add defaults from the command line
    for key, value in args.default:
        try:
            value = json.loads(value)
        except:
            pass

        logger.debug('Default: {0}={1}'.format(key, value))
        core.defaults_json = \
            pydash.set_(core.defaults_json, key, value)

    # Add profile settings from the command line
    extra_settings = {}
    for key, value in args.set:
        try:
            value = json.loads(value)
        except:
            pass

        logger.debug('Profile: {0}={1}'.format(key, value))
        extra_settings[key] = value

    for profile in core.profiles.values():
        for key, value in extra_settings.items():
            profile.json = pydash.set_(profile.json, key, value)

    # Pre-load default profile
    if core.get_default('rhasspy.preload_profile', False):
        logger.info('Preloading default profile (%s)' % core.default_profile_name)
        # core.preload_profile(core.default_profile_name)

#     if core.get_default('mqtt.enabled', False):
#         core.get_mqtt_client().start_client()
#         for i in range(20):
#             time.sleep(0.1)
#             if core.get_mqtt_client().connected:
#                 break

#     # Listen for wake word
#     if core.get_default('rhasspy.listen_on_start', False):
#         logger.info('Automatically listening for wake word')
#         wake = core.get_wake_listener(core.default_profile_name)
#         wake.start_listening()
#         core.get_mqtt_client().rhasspy_asleep(core.default_profile_name)

start_rhasspy()

# -----------------------------------------------------------------------------

def request_to_profile(request):
    '''Gets profile from HTTP request'''
    profile_name = request.args.get('profile', core.default_profile_name)
    return core.profiles[profile_name]

# -----------------------------------------------------------------------------
# HTTP API
# -----------------------------------------------------------------------------

@app.route('/api/profiles')
def api_profiles():
    '''Get list of available profiles'''
    return jsonify({
        'default_profile': core.default_profile_name,
        'profiles': sorted(core.profiles.keys())
    })

# -----------------------------------------------------------------------------

@app.route('/api/microphones', methods=['GET'])
def api_microphones():
    '''Get a dictionary of available recording devices'''
    profile = request_to_profile(request)
    mics = core.get_microphones(profile.name)
    return jsonify(mics)

# -----------------------------------------------------------------------------

@app.route('/api/test-microphones', methods=['GET'])
def api_test_microphones():
    '''Get a dictionary of available, functioning recording devices'''
    profile = request_to_profile(request)
    mics = core.test_microphones(profile.name)
    return jsonify(mics)

# -----------------------------------------------------------------------------

@app.route('/api/listen-for-wake', methods=['POST'])
def api_listen_for_wake():
    profile = request_to_profile(request)
    no_hass = request.args.get('nohass', 'false').lower() == 'true'

    wake = core.get_wake_listener(profile.name)
    wake.start_listening(no_hass=no_hass)

    return profile.name

# -----------------------------------------------------------------------------

@app.route('/api/listen-for-command', methods=['POST'])
def api_listen_for_command():
    profile = request_to_profile(request)
    no_hass = request.args.get('nohass', 'false').lower() == 'true'

    intent = core._handle_wake(profile.name, 'api', no_hass=no_hass)

    return jsonify(intent)

# -----------------------------------------------------------------------------

@app.route('/api/profile', methods=['GET', 'POST'])
def api_profile():
    '''Read or write profile JSON directly'''
    layers = request.args.get('layers', 'all')

    if request.method == 'POST':
        # Ensure that JSON is valid
        json.loads(request.data)

        if layers == 'defaults':
            # Write default settings
            for profiles_dir in core.profiles_dirs:
                profile_path = os.path.join(profiles_dir, 'defaults.json')
                try:
                    with open(profile_path, 'wb') as profile_file:
                        profile_file.write(request.data)
                    break
                except:
                    pass
        else:
            # Write local profile settings
            profile = request_to_profile(request)
            profile_path = profile.write_path('profile.json')
            with open(profile_path, 'wb') as profile_file:
                profile_file.write(request.data)

        msg = 'Wrote %d byte(s) to %s' % (len(request.data), profile_path)
        logger.debug(msg)
        return msg

    if layers == 'defaults':
        # Read default settings
        return jsonify(core.defaults_json)
    elif layers == 'profile':
        # Local settings only
        profile = request_to_profile(request)
        profile_path = profile.read_path('profile.json')
        return send_file(open(profile_path, 'rb'),
                         mimetype='application/json')
    else:
        profile = request_to_profile(request)
        return jsonify(profile.json)

# -----------------------------------------------------------------------------

@app.route('/api/lookup', methods=['POST'])
def api_lookup():
    '''Get CMU phonemes from dictionary or guessed pronunciation(s)'''
    n = int(request.args.get('n', 5))
    assert n > 0, 'No pronunciations requested'

    word = request.data.decode('utf-8').strip().lower()
    assert len(word) > 0, 'No word to look up'

    voice = request.args.get('voice', None)
    profile = request_to_profile(request)

    word_pron = core.get_word_pronouncer(profile.name)
    in_dictionary, pronunciations, espeak_str = word_pron.pronounce(word)

    return jsonify({
        'in_dictionary': in_dictionary,
        'pronunciations': pronunciations,
        'espeak_phonemes': espeak_str
    })

# -----------------------------------------------------------------------------

@app.route('/api/pronounce', methods=['POST'])
def api_pronounce():
    '''Pronounce CMU phonemes or word using eSpeak'''
    profile = request_to_profile(request)
    download = request.args.get('download', 'false').lower() == 'true'
    voice = request.args.get('voice', None)

    pronounce_str = request.data.decode('utf-8').strip()
    assert len(pronounce_str) > 0, 'No string to pronounce'

    word_pron = core.get_word_pronouncer(profile.name)

    # phonemes or word
    pronounce_type = request.args.get('type', 'phonemes')

    if pronounce_type == 'phonemes':
        # Convert from Sphinx to espeak phonemes
        espeak_str = word_pron.translate_phonemes(pronounce_str)
    else:
        # Speak word directly
        espeak_str = pronounce_str

    espeak_phonemes, wav_data = word_pron.speak(espeak_str, voice)

    if download:
        return Response(wav_data, mimetype='audio/wav')
    else:
        core.get_audio_player().play_data(wav_data)
        return espeak_phonemes

# -----------------------------------------------------------------------------

@app.route('/api/phonemes')
def api_phonemes():
    '''Get phonemes and example words for a profile'''
    profile = request_to_profile(request)
    examples_path = profile.read_path(
        profile.get('text_to_speech.phoneme_examples'))

    # phoneme -> { word, phonemes }
    logger.debug('Loading phoneme examples from %s' % examples_path)
    examples_dict = load_phoneme_examples(examples_path)

    return jsonify(examples_dict)

# -----------------------------------------------------------------------------

@app.route('/api/sentences', methods=['GET', 'POST'])
def api_sentences():
    '''Read or write sentences for a profile'''
    profile = request_to_profile(request)

    if request.method == 'POST':
        # Update sentences
        sentences_path = profile.write_path(
            profile.get('speech_to_text.sentences_ini'))

        with open(sentences_path, 'wb') as sentences_file:
            sentences_file.write(request.data)
            return 'Wrote %s byte(s) to %s' % (len(request.data), sentences_path)

    # Return sentences
    sentences_path = profile.read_path(
        profile.get('speech_to_text.sentences_ini'))

    if not os.path.exists(sentences_path):
        return ''  # no sentences yet

    # Return file contents
    return send_file(open(sentences_path, 'rb'),
                     mimetype='text/plain')

# -----------------------------------------------------------------------------

@app.route('/api/custom-words', methods=['GET', 'POST'])
def api_custom_words():
    '''Read or write custom word dictionary for a profile'''
    profile = request_to_profile(request)
    custom_words_path = profile.write_path(
        profile.get('speech_to_text.pocketsphinx.custom_words'))

    if request.method == 'POST':
        # Update custom words
        with open(custom_words_path, 'wb') as custom_words_file:
            custom_words_file.write(request.data)
            return 'Wrote %s byte(s) to %s' % (len(request.data), custom_words_path)

    # Return custom_words
    if not os.path.exists(custom_words_path):
        return ''  # no custom_words yet

    # Return file contents
    return send_file(open(custom_words_path, 'rb'),
                     mimetype='text/plain')

# -----------------------------------------------------------------------------

@app.route('/api/train', methods=['POST'])
def api_train():
    profile = request_to_profile(request)

    start_time = time.time()
    logger.info('Starting training')
    core.train_profile(profile.name)
    end_time = time.time()

    core.reload_profile(profile.name)

    return 'Training completed in %0.2f second(s)' % (end_time - start_time)

# -----------------------------------------------------------------------------

@app.route('/api/reload', methods=['POST'])
def api_reload():
    profile = request_to_profile(request)
    core.reload_profile(profile.name)

    return 'Reloaded profile "%s"' % profile.name

# -----------------------------------------------------------------------------

@app.route('/api/restart', methods=['POST'])
def api_restart():
    logger.debug('Restarting Rhasspy')

    global core
    core.get_audio_recorder().stop_all()

    for wake_listener in core.wake_listeners.values():
        wake_listener.stop_listening()

    del core

    start_rhasspy()
    logger.info('Restarted Rhasspy')

    return 'Restarted Rhasspy'

# -----------------------------------------------------------------------------

# Get text from a WAV file
@app.route('/api/speech-to-text', methods=['POST'])
def api_speech_to_text():
    profile = request_to_profile(request)

    # Prefer 16-bit 16Khz mono, but will convert with sox if needed
    wav_data = request.data
    decoder = core.get_speech_decoder(profile.name)
    result = system.ask(decoder, TranscribeWav(wav_data))

    return result.text

# -----------------------------------------------------------------------------

# Get intent from text
@app.route('/api/text-to-intent', methods=['POST'])
def api_text_to_intent():
    profile = request_to_profile(request)
    text = request.data.decode()
    no_hass = request.args.get('nohass', 'false').lower() == 'true'

    recognizer = core.get_intent_recognizer(profile.name)

    # Convert text to intent
    start_time = time.time()
    result = system.ask(recognizer, RecognizeIntent(text))
    intent = result.intent

    intent_sec = time.time() - start_time
    intent['time_sec'] = intent_sec

    if not no_hass:
        # Send intent to Home Assistant
        handler = core.get_intent_handler(profile.name)
        intent = system.ask(handler, HandleIntent(intent)).intent

    return jsonify(intent)

# -----------------------------------------------------------------------------

# Get intent from a WAV file
@app.route('/api/speech-to-intent', methods=['POST'])
def api_speech_to_intent():
    profile = request_to_profile(request)
    no_hass = request.args.get('nohass', 'false').lower() == 'true'

    # Prefer 16-bit 16Khz mono, but will convert with sox if needed
    wav_data = request.data
    intent = core.wav_to_intent(wav_data, profile.name)

    if not no_hass:
        # Send intent to Home Assistant
        handler = core.get_intent_handler(profile.name)
        intent = system.ask(handler, HandleIntent(intent)).intent

    return jsonify(intent)

# -----------------------------------------------------------------------------

# Start recording a WAV file to a temporary buffer
@app.route('/api/start-recording', methods=['POST'])
def api_start_recording():
    device = request.args.get('device', None)
    profile = request_to_profile(request)

    buffer_name = request.args.get('name', '')
    system.tell(core.get_audio_recorder(profile.name, device),
                StartRecordingToBuffer(buffer_name))

    return 'OK'

# Stop recording WAV file, transcribe, and get intent
@app.route('/api/stop-recording', methods=['POST'])
def api_stop_recording():
    device = request.args.get('device', None)
    profile = request_to_profile(request)
    no_hass = request.args.get('nohass', 'false').lower() == 'true'

    buffer_name = request.args.get('name', '')
    recorder = core.get_audio_recorder(profile.name, device)
    result = system.ask(recorder, StopRecordingToBuffer(buffer_name))

    wav_data = buffer_to_wav(result.data)
    logger.debug('Recorded %s byte(s) of audio data' % len(wav_data))

    intent = core.wav_to_intent(wav_data, profile.name)

    if not no_hass:
        # Send intent to Home Assistant
        handler = core.get_intent_handler(profile.name)
        intent = system.ask(handler, HandleIntent(intent)).intent

    return jsonify(intent)

# -----------------------------------------------------------------------------

@app.route('/api/unknown_words', methods=['GET'])
def api_unknown_words():
    profile = request_to_profile(request)

    unknown_words = {}
    unknown_path = profile.read_path(
        profile.get('speech_to_text.pocketsphinx.unknown_words'))

    if os.path.exists(unknown_path):
        for line in open(unknown_path, 'r'):
            line = line.strip()
            if len(line) > 0:
                word, pronunciation = re.split(r'\s+', line, maxsplit=1)
                unknown_words[word] = pronunciation

    return jsonify(unknown_words)

# -----------------------------------------------------------------------------

@app.errorhandler(Exception)
def handle_error(err):
    logger.exception(err)
    return (str(err), 500)

# ---------------------------------------------------------------------
# Static Routes
# ---------------------------------------------------------------------

web_dir = os.path.join(os.path.dirname(__file__), 'dist')

@app.route('/css/<path:filename>', methods=['GET'])
def css(filename):
    return send_from_directory(os.path.join(web_dir, 'css'), filename)

@app.route('/js/<path:filename>', methods=['GET'])
def js(filename):
    return send_from_directory(os.path.join(web_dir, 'js'), filename)

@app.route('/img/<path:filename>', methods=['GET'])
def img(filename):
    return send_from_directory(os.path.join(web_dir, 'img'), filename)

@app.route('/webfonts/<path:filename>', methods=['GET'])
def webfonts(filename):
    return send_from_directory(os.path.join(web_dir, 'webfonts'), filename)

# ----------------------------------------------------------------------------
# HTML Page Routes
# ----------------------------------------------------------------------------

@app.route('/', methods=['GET'])
def index():
    return send_file(os.path.join(web_dir, 'index.html'))

@app.route('/swagger.yaml', methods=['GET'])
def swagger_yaml():
    return send_file(os.path.join(web_dir, 'swagger.yaml'))

# -----------------------------------------------------------------------------

# Swagger/OpenAPI documentation
from flask_swagger_ui import get_swaggerui_blueprint

SWAGGER_URL = '/api'
API_URL = '/swagger.yaml'

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL, API_URL,
    config={'app_name': 'Rhasspy API'})

app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

# -----------------------------------------------------------------------------
