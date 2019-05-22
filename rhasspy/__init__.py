#!/usr/bin/env python3
import logging

logger = logging.getLogger("rhasspy")

import sys
import os
import io
import json
import argparse
import threading
import tempfile
import random
import time
import itertools
import wave
import math
import random
from typing import Any, List, Optional, Dict, Set

import pydash

try:
    # Need to import here because they screw with logging
    import flair
except:
    pass

from .core import RhasspyCore
from .actor import ConfigureEvent, Configured, ActorSystem, RhasspyActor
from .profiles import Profile
from .utils import buffer_to_wav, maybe_convert_wav
from .audio_recorder import AudioData, StartStreaming, StopStreaming
from .audio_player import DummyAudioPlayer
from .dialogue import DialogueManager
from .wake import (
    PocketsphinxWakeListener,
    ListenForWakeWord,
    StopListeningForWakeWord,
    WakeWordDetected,
    WakeWordNotDetected,
)


# Configure logging
import logging.config

logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": True,
        "formatters": {
            "rhasspy.format": {"format": "%(levelname)s:%(name)s:%(message)s"}
        },
        "handlers": {
            "rhasspy.handler": {
                "class": "logging.StreamHandler",
                "formatter": "rhasspy.format",
                "stream": "ext://sys.stderr",
            }
        },
        "loggers": {
            "rhasspy": {"handlers": ["rhasspy.handler"], "propagate": False},
            "flair": {
                "handlers": ["rhasspy.handler"],
                "level": "INFO",
                "propagate": False,
            },
        },
        "root": {"handlers": ["rhasspy.handler"]},
    }
)


# -----------------------------------------------------------------------------
# Globals
# -----------------------------------------------------------------------------
mic_stdin_thread = None
mic_stdin_running = False

# -----------------------------------------------------------------------------


def main() -> None:
    global mic_stdin_running, mic_stdin_thread

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Rhasspy")
    parser.add_argument(
        "--profile", "-p", required=True, type=str, help="Name of profile to use"
    )
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
        "--debug", action="store_true", help="Print DEBUG log to console"
    )
    parser.add_argument(
        "--no-check",
        action="store_true",
        help="Don't check profile for necessary files",
    )

    sub_parsers = parser.add_subparsers(dest="command")
    sub_parsers.required = True

    # info
    info_parser = sub_parsers.add_parser("info", help="Profile information")
    info_parser.add_argument(
        "--defaults", action="store_true", help="Only print default settings"
    )

    sentences_parser = sub_parsers.add_parser(
        "sentences", help="Print profile sentences.ini"
    )

    # validate
    # validate_parser = sub_parsers.add_parser(
    #     "validate", help="Validate profile against schema"
    # )

    # wav2text
    wav2text_parser = sub_parsers.add_parser(
        "wav2text", help="WAV file to text transcription"
    )
    wav2text_parser.add_argument("wav_files", nargs="*", help="Paths to WAV files")

    # text2intent
    text2intent_parser = sub_parsers.add_parser(
        "text2intent", help="Text parsed to intent"
    )
    text2intent_parser.add_argument("sentences", nargs="*", help="Sentences to parse")
    text2intent_parser.add_argument(
        "--handle", action="store_true", help="Pass result to intent handler"
    )

    # wav2intent
    wav2intent_parser = sub_parsers.add_parser(
        "wav2intent", help="WAV file to parsed intent"
    )
    wav2intent_parser.add_argument("wav_files", nargs="*", help="Paths to WAV files")
    wav2intent_parser.add_argument(
        "--handle", action="store_true", help="Pass result to intent handler"
    )

    # train
    train_parser = sub_parsers.add_parser("train", help="Re-train profile")

    # record
    # record_parser = sub_parsers.add_parser('record', help='Record test phrases for profile')
    # record_parser.add_argument('--directory', help='Directory to write WAV files and intent JSON files')

    # record-wake
    # record_wake_parser = sub_parsers.add_parser('record-wake', help='Record wake word examples for profile')
    # record_wake_parser.add_argument('--directory', help='Directory to write WAV files')
    # record_wake_parser.add_argument('--negative', action='store_true', help='Record negative examples (not the wake word)')

    # tune
    # tune_parser = sub_parsers.add_parser('tune', help='Tune speech acoustic model for profile')
    # tune_parser.add_argument('--directory', help='Directory with WAV files and intent JSON files')

    # tune-wake
    # tune_wake_parser = sub_parsers.add_parser('tune-wake', help='Tune wake acoustic model for profile')
    # tune_wake_parser.add_argument('--directory', help='Directory with WAV files')

    # test
    # test_parser = sub_parsers.add_parser('test', help='Test speech/intent recognizers for profile')
    # test_parser.add_argument('directory', help='Directory with WAV files and intent JSON files')

    # test-wake
    test_wake_parser = sub_parsers.add_parser(
        "test-wake", help="Test wake word examples for profile"
    )
    test_wake_parser.add_argument("directory", help="Directory with WAV files")
    test_wake_parser.add_argument(
        "--threads", type=int, default=4, help="Number of threads to use"
    )
    test_wake_parser.add_argument(
        "--system", type=str, default=None, help="Override wake word system"
    )

    # mic2wav
    mic2wav_parser = sub_parsers.add_parser("mic2wav", help="Voice command to WAV data")
    mic2wav_parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Maximum number of seconds to record (default=profile)",
    )

    # mic2text
    mic2text_parser = sub_parsers.add_parser(
        "mic2text", help="Voice command to text transcription"
    )
    mic2text_parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Maximum number of seconds to record (default=profile)",
    )

    # mic2intent
    mic2intent_parser = sub_parsers.add_parser(
        "mic2intent", help="Voice command to parsed intent"
    )
    mic2intent_parser.add_argument(
        "--stdin", action="store_true", help="Read audio data from stdin"
    )
    mic2intent_parser.add_argument(
        "--handle", action="store_true", help="Pass result to intent handler"
    )
    mic2intent_parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Maximum number of seconds to record (default=profile)",
    )

    # word2phonemes
    word2phonemes_parser = sub_parsers.add_parser(
        "word2phonemes", help="Get pronunciation(s) for word(s)"
    )
    word2phonemes_parser.add_argument("words", nargs="*", help="Word(s) to pronounce")
    word2phonemes_parser.add_argument(
        "-n", type=int, default=1, help="Maximum number of pronunciations"
    )

    # word2wav
    word2wav_parser = sub_parsers.add_parser("word2wav", help="Pronounce word")
    word2wav_parser.add_argument("word", help="Word to pronounce")

    # wav2mqtt
    wav2mqtt_parser = sub_parsers.add_parser(
        "wav2mqtt", help="Push WAV file(s) to MQTT"
    )
    wav2mqtt_parser.add_argument("wav_files", nargs="*", help="Paths to WAV files")
    wav2mqtt_parser.add_argument(
        "--frames",
        type=int,
        default=480,
        help="WAV frames per MQTT message (default=0 for all)",
    )
    wav2mqtt_parser.add_argument(
        "--site-id", type=str, default="default", help="Hermes siteId (default=default)"
    )
    wav2mqtt_parser.add_argument(
        "--silence-before",
        type=float,
        default=0,
        help="Seconds of silence to add before each WAV",
    )
    wav2mqtt_parser.add_argument(
        "--silence-after",
        type=float,
        default=0,
        help="Seconds of silence to add after each WAV",
    )
    wav2mqtt_parser.add_argument(
        "--pause",
        type=float,
        default=0.01,
        help="Seconds to wait before sending next chunk (default=0.01)",
    )

    # text2wav
    text2wav_parser = sub_parsers.add_parser(
        "text2wav", help="Output WAV file using text to speech system"
    )
    text2wav_parser.add_argument("sentence", help="Sentence to speak")

    # text2speech
    text2speech_parser = sub_parsers.add_parser(
        "text2speech", help="Speak sentences using text to speech system"
    )
    text2speech_parser.add_argument("sentences", nargs="*", help="Sentences to speak")

    # sleep
    sleep_parser = sub_parsers.add_parser("sleep", help="Wait for wake word")

    # download
    download_parser = sub_parsers.add_parser("download", help="Download profile files")
    download_parser.add_argument(
        "--delete", action="store_true", help="Clear download cache before downloading"
    )

    # -------------------------------------------------------------------------

    args = parser.parse_args()

    if args.debug:
        logging.root.setLevel(logging.DEBUG)

    profiles_dirs = [args.system_profiles, args.user_profiles]
    logger.debug(profiles_dirs)

    default_settings = Profile.load_defaults(args.system_profiles)

    # Create rhasspy core
    from .core import RhasspyCore

    core = RhasspyCore(args.profile, args.system_profiles, args.user_profiles)

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

    # Handle command
    if args.command == "info":
        if args.defaults:
            # Print default settings
            json.dump(core.defaults, sys.stdout, indent=4)
        else:
            # Print profile settings
            json.dump(core.profile.json, sys.stdout, indent=4)
    elif args.command == "validate":
        from cerberus import Validator

        schema_path = os.path.join(os.path.dirname(__file__), "profile_schema.json")
        with open(schema_path, "r") as schema_file:
            v = Validator(json.load(schema_file))
            if v.validate(core.profile.json):
                print("VALID")
            else:
                print("INVALID")
                for err in v._errors:
                    print(err)
    elif args.command == "sentences":
        sentences_path = core.profile.read_path(
            core.profile.get("speech_to_text.sentences_ini", "sentences.ini")
        )

        with open(sentences_path, "r") as sentences_file:
            sys.stdout.write(sentences_file.read())
    else:
        # Patch profile
        profile = core.profile
        profile.set("rhasspy.listen_on_start", False)
        profile.set("rhasspy.preload_profile", False)

        if args.command == "wav2mqtt":
            profile.set("mqtt.enabled", True)
        elif args.command in ["mic2intent"] and args.stdin:
            profile.set("microphone.system", "stdin")
            profile.set("microphone.stdin.auto_start", False)
            mic_stdin_running = True
        elif args.command == "text2wav":
            profile.set("sounds.system", "dummy")

        # Set environment variables
        os.environ["RHASSPY_BASE_DIR"] = os.getcwd()
        os.environ["RHASSPY_PROFILE"] = core.profile.name
        os.environ["RHASSPY_PROFILE_DIR"] = core.profile.write_dir()

        # Execute command
        command_funcs = {
            "wav2text": wav2text,
            "text2intent": text2intent,
            "wav2intent": wav2intent,
            "train": train_profile,
            # 'record': record,
            # 'record-wake': record_wake,
            # 'tune': tune,
            # 'tune-wake': tune_wake,
            # 'test': test,
            "test-wake": test_wake,
            "mic2text": mic2text,
            "mic2intent": mic2intent,
            "mic2wav": mic2wav,
            "word2phonemes": word2phonemes,
            "word2wav": word2wav,
            "wav2mqtt": wav2mqtt,
            "text2wav": text2wav,
            "text2speech": text2speech,
            "sleep": sleep,
            "download": download,
        }

        if not args.command in ["test-wake"]:
            # Automatically start core
            core.start()

        if not args.no_check and args.command != "download":
            # Verify that profile has necessary files
            downloaded = core.check_profile()
            if not downloaded:
                logger.fatal(
                    f"Missing required files for {profile.name}. Please run download command and try again."
                )
                sys.exit(1)

        if mic_stdin_running:
            logger.debug("Reading audio data from stdin")
            mic_stdin_thread = threading.Thread(
                target=read_audio_stdin, args=(core,), daemon=True
            )
            mic_stdin_thread.start()

        # Run command
        try:
            command_funcs[args.command](core, profile, args)

            if mic_stdin_thread is not None:
                mic_stdin_running = False
                mic_stdin_thread.join()
        finally:
            core.shutdown()


# -----------------------------------------------------------------------------
# wav2text: transcribe WAV file(s) to text
# -----------------------------------------------------------------------------


def wav2text(core: RhasspyCore, profile: Profile, args: Any) -> None:
    if len(args.wav_files) > 0:
        # Read WAV paths from argument list
        transcriptions = {}
        for wav_path in args.wav_files:
            with open(wav_path, "rb") as wav_file:
                text = core.transcribe_wav(wav_file.read()).text
                transcriptions[wav_path] = text

        # Output JSON
        json.dump(transcriptions, sys.stdout, indent=4)
    else:
        # Read WAV data from stdin
        text = core.transcribe_wav(sys.stdin.buffer.read()).text

        # Output text
        print(text)


# -----------------------------------------------------------------------------
# text2intent: parse text into intent(s)
# -----------------------------------------------------------------------------


def text2intent(core: RhasspyCore, profile: Profile, args: Any) -> None:
    # Parse sentences from command line or stdin
    intents = {}
    sentences = args.sentences if len(args.sentences) > 0 else sys.stdin
    for sentence in sentences:
        sentence = sentence.strip()
        intent = core.recognize_intent(sentence).intent

        if args.handle:
            intent = core.handle_intent(intent).intent

        intents[sentence] = intent

    # Output JSON
    json.dump(intents, sys.stdout, indent=4)


# -----------------------------------------------------------------------------
# wav2intent: transcribe WAV file(s) to text and parse into intent(s)
# -----------------------------------------------------------------------------


def wav2intent(core: RhasspyCore, profile: Profile, args: Any) -> None:
    if len(args.wav_files) > 0:
        # Read WAV paths from argument list
        transcriptions = {}
        for wav_path in args.wav_files:
            with open(wav_path, "rb") as wav_file:
                text = core.transcribe_wav(wav_file.read()).text
                transcriptions[wav_path] = text

        # Parse intents
        intents = {}
        for wav_path, sentence in transcriptions.items():
            intent = core.recognize_intent(sentence).intent

            if args.handle:
                intent = core.handle_intent(intent).intent

            intents[wav_path] = intent

        # Output JSON
        json.dump(intents, sys.stdout, indent=4)
    else:
        # Read WAV data from stdin
        sentence = core.transcribe_wav(sys.stdin.buffer.read()).text
        intent = core.recognize_intent(sentence).intent

        if args.handle:
            intent = core.handle_intent(intent).intent

        # Output JSON
        json.dump(intent, sys.stdout, indent=4)


# -----------------------------------------------------------------------------
# train: re-train profile speech/intent recognizers
# -----------------------------------------------------------------------------


def train_profile(core: RhasspyCore, profile: Profile, args: Any) -> None:
    result = core.train(reload_actors=False)
    print(result)


# -----------------------------------------------------------------------------
# record: record phrases for testing/tuning
# -----------------------------------------------------------------------------

# def record(core:RhasspyCore, profile:Profile, args:Any) -> None:
#     dir_path = args.directory or profile.write_dir('record')
#     dir_name = os.path.split(dir_path)[1]
#     os.makedirs(dir_path, exist_ok=True)

#     tagged_path = profile.read_path(profile.get('training.tagged_sentences'))
#     assert os.path.exists(tagged_path), 'Missing tagged sentences (%s). Need to train?' % tagged_path

#     # Load and parse tagged sentences
#     intent_sentences = []
#     intent_name = ''
#     with open(tagged_path, 'r') as tagged_file:
#         for line in tagged_file:
#             line = line.strip()
#             if len(line) == 0:
#                 continue  # skip blank lines

#             if line.startswith('# intent:'):
#                 intent_name = line.split(':', maxsplit=1)[1]
#             elif line.startswith('-'):
#                 tagged_sentence = line[1:].strip()
#                 sentence, entities = extract_entities(tagged_sentence)
#                 intent_sentences.append((intent_name, sentence, entities))

#     assert len(intent_sentences) > 0, 'No tagged sentences available'
#     print('Loaded %s sentence(s)' % len(intent_sentences))

#     # Record WAV files
#     audio_recorder = core.get_audio_recorder()
#     wav_prefix = dir_name
#     wav_num = 0
#     try:
#         while True:
#             intent_name, sentence, entities = random.choice(intent_sentences)
#             print('Speak the following sentence. Press ENTER to start (CTRL+C to quit).')
#             print(sentence)
#             input()
#             audio_recorder.start_recording(True, False)
#             print('Recording. Press ENTER to stop (CTRL+C to quit).')
#             input()
#             wav_data = audio_recorder.stop_recording(True, False)

#             # Determine WAV file name
#             wav_path = os.path.join(dir_path, '%s-%03d.wav' % (wav_prefix, wav_num))
#             while os.path.exists(wav_path):
#                 wav_num += 1
#                 wav_path = os.path.join(dir_path, '%s-%03d.wav' % (wav_prefix, wav_num))

#             # Write WAV data
#             with open(wav_path, 'wb') as wav_file:
#                 wav_file.write(wav_data)

#             # Write intent (with transcription)
#             intent_path = os.path.join(dir_path, '%s-%03d.wav.json' % (wav_prefix, wav_num))
#             with open(intent_path, 'w') as intent_file:
#                 # Use rasaNLU format
#                 intent = {
#                     'text': sentence,
#                     'intent': { 'name': intent_name },
#                     'entities': [
#                         { 'entity': entity, 'value': value }
#                         for entity, value in entities
#                     ]
#                 }

#                 json.dump(intent, intent_file, indent=4)

#             print('')
#     except KeyboardInterrupt:
#         print('Done')

# -----------------------------------------------------------------------------
# record-wake: record wake word examples
# -----------------------------------------------------------------------------

# def record_wake(core:RhasspyCore, profile:Profile, args:Any) -> None:
#     keyphrase = profile.get('wake.pocketsphinx.keyphrase', '')
#     assert len(keyphrase) > 0, 'No wake word'

#     wav_prefix = keyphrase.replace(' ', '-')
#     base_dir_path = args.directory or profile.write_dir('record')

#     if args.negative:
#         dir_path = os.path.join(base_dir_path, wav_prefix, 'not-wake-word')
#     else:
#         dir_path = os.path.join(base_dir_path, wav_prefix, 'wake-word')

#     os.makedirs(dir_path, exist_ok=True)

#     # Record WAV files
#     audio_recorder = core.get_audio_recorder()
#     wav_num = 0
#     try:
#         while True:
#             # Determine WAV file name
#             wav_path = os.path.join(dir_path, '%s-%02d.wav' % (wav_prefix, wav_num))
#             while os.path.exists(wav_path):
#                 wav_num += 1
#                 wav_path = os.path.join(dir_path, '%s-%02d.wav' % (wav_prefix, wav_num))

#             if args.negative:
#                 print('Speak anything EXCEPT the wake word. Press ENTER to start (CTRL+C to quit).')
#                 print('NOT %s (%s)' % (keyphrase, wav_num))
#             else:
#                 print('Speak your wake word. Press ENTER to start (CTRL+C to quit).')
#                 print('%s (%s)' % (keyphrase, wav_num))

#             input()
#             audio_recorder.start_recording(True, False)
#             print('Recording. Press ENTER to stop (CTRL+C to quit).')
#             input()
#             wav_data = audio_recorder.stop_recording(True, False)

#             # Write WAV data
#             with open(wav_path, 'wb') as wav_file:
#                 wav_file.write(wav_data)

#             print('')
#     except KeyboardInterrupt:
#         print('Done')

# -----------------------------------------------------------------------------
# tune: fine tune speech acoustic model
# -----------------------------------------------------------------------------

# def tune(core:RhasspyCore, profile:Profile, args:Any) -> None:
#     dir_path = args.directory or profile.read_path('record')
#     assert os.path.exists(dir_path), 'Directory does not exist'
#     wav_paths = [os.path.join(dir_path, name)
#                  for name in os.listdir(dir_path)
#                  if name.endswith('.wav')]

#     # Load intents for each WAV
#     wav_intents = {}
#     for wav_path in wav_paths:
#         intent_path = wav_path + '.json'
#         if os.path.exists(intent_path):
#             with open(intent_path, 'r') as intent_file:
#                 wav_intents[wav_path] = json.load(intent_file)

#     # Do tuning
#     tuner = core.get_speech_tuner(profile.name)
#     tuner.preload()

#     print('Tuning speech system with %s WAV file(s)' % len(wav_intents))
#     tune_start = time.time()
#     tuner.tune(wav_intents)
#     print('Finished tuning in %s second(s)' % (time.time() - tune_start))

# -----------------------------------------------------------------------------
# tune-wake: fine tune wake acoustic model
# -----------------------------------------------------------------------------

# def tune_wake(core:RhasspyCore, profile:Profile, args:Any) -> None:
#     keyphrase = profile.get('wake.pocketsphinx.keyphrase', '')
#     assert len(keyphrase) > 0, 'No wake word'

#     wav_prefix = keyphrase.replace(' ', '-')
#     base_dir_path = args.directory or profile.read_path('record')

#     # Path to positive examples
#     true_path = os.path.join(base_dir_path, wav_prefix, 'wake-word')
#     if os.path.exists(true_path):
#         true_wav_paths = [os.path.join(true_path, name)
#                           for name in os.listdir(true_path)
#                           if name.endswith('.wav')]
#     else:
#         true_wav_paths = []

#     # Path to negative examples
#     false_path = os.path.join(base_dir_path, wav_prefix, 'not-wake-word')
#     if os.path.exists(false_path):
#         false_wav_paths = [os.path.join(false_path, name)
#                           for name in os.listdir(false_path)
#                           if name.endswith('.wav')]
#     else:
#         false_wav_paths = []

#     # Do tuning
#     mllr_path = profile.write_path(
#         profile.get('wake.pocketsphinx.mllr_matrix'))

#     tuner = SphinxTrainSpeechTuner(profile)
#     tuner.preload()

#     # Add "transcriptions"
#     wav_intents = {}
#     for wav_path in true_wav_paths:
#         wav_intents[wav_path] = { 'text': keyphrase }

#     for wav_path in false_wav_paths:
#         wav_intents[wav_path] = { 'text': '' }

#     print('Tuning wake word system with %s positive and %s negative example(s)' % (len(true_wav_paths), len(false_wav_paths)))
#     tune_start = time.time()
#     tuner.tune(wav_intents, mllr_path=mllr_path)
#     print('Finished tuning in %s second(s)' % (time.time() - tune_start))

# -----------------------------------------------------------------------------
# test: test speech/intent recognizers
# -----------------------------------------------------------------------------

# def test(core:RhasspyCore, profile:Profile, args:Any) -> None:
#     dir_path = args.directory or profile.read_path('record')
#     assert os.path.exists(dir_path), 'Directory does not exist'
#     wav_paths = [os.path.join(dir_path, name)
#                  for name in os.listdir(dir_path)
#                  if name.endswith('.wav')]

#     # Load intents for each WAV
#     wav_intents = {}
#     for wav_path in wav_paths:
#         intent_path = wav_path + '.json'
#         if os.path.exists(intent_path):
#             with open(intent_path, 'r') as intent_file:
#                 wav_intents[wav_path] = json.load(intent_file)

#     # Transcribe and match intent names/entities
#     decoder = core.get_speech_decoder(profile.name)
#     decoder.preload()

#     recognizer = core.get_intent_recognizer(profile.name)
#     recognizer.preload()

#     # TODO: parallelize
#     results = {}
#     for wav_path, expected_intent in wav_intents.items():
#         # Transcribe
#         decode_start = time.time()
#         with open(wav_path, 'rb') as wav_file:
#             actual_sentence = decoder.transcribe_wav(wav_file.read())

#         decode_sec = time.time() - decode_start

#         # Recognize
#         recognize_start = time.time()
#         actual_intent = recognizer.recognize(actual_sentence)
#         recognize_sec = time.time() - recognize_start

#         wav_name = os.path.split(wav_path)[1]
#         results[wav_name] = {
#             'profile': profile.name,
#             'expected': expected_intent,
#             'actual': actual_intent,
#             'speech': {
#                 'system': profile.get('speech_to_text.system'),
#                 'time_sec': decode_sec
#             },
#             'intent': {
#                 'system': profile.get('intent.system'),
#                 'time_sec': recognize_sec
#             }
#         }

#     json.dump(results, sys.stdout, indent=4)

# -----------------------------------------------------------------------------
# test-wake: test wake word examples
# -----------------------------------------------------------------------------


def test_wake(core: RhasspyCore, profile: Profile, args: Any) -> None:
    base_dir_path = args.directory
    wake_system = args.system or profile.get("wake.system", "pocketsphinx")

    # Path to positive examples
    true_path = os.path.join(base_dir_path, "wake-word")
    true_wav_paths: List[str] = []
    if os.path.exists(true_path):
        true_wav_paths = [
            os.path.join(true_path, name)
            for name in os.listdir(true_path)
            if name.endswith(".wav")
        ]

    # Path to negative examples
    false_path = os.path.join(base_dir_path, "not-wake-word")
    false_wav_paths: List[str] = []
    if os.path.exists(false_path):
        false_wav_paths = [
            os.path.join(false_path, name)
            for name in os.listdir(false_path)
            if name.endswith(".wav")
        ]

    # Spin up actors
    kwargs: Dict[str, Any] = {}
    if not args.debug:
        kwargs = {"logDefs": {"version": 1, "loggers": {"": {}}}}

    system = ActorSystem("multiprocTCPBase", **kwargs)
    detected_paths: Set[str] = set()

    try:
        test_actor = system.createActor(TestWakeActor)
        all_wav_paths = true_wav_paths + false_wav_paths

        start_time = time.time()
        with system.private() as private:
            private.tell(test_actor, ConfigureEvent(profile, transitions=False))
            result = private.listen()
            assert isinstance(result, Configured)

            private.tell(test_actor, (wake_system, args.threads, all_wav_paths))

            # Collect WAV paths that had a positive detection
            detected_paths = private.listen()

        end_time = time.time()
    finally:
        system.shutdown()

    # Compute statistics
    expected_true = len(true_wav_paths)
    expected_false = len(false_wav_paths)

    true_positives = 0
    false_positives = 0
    true_negatives = 0
    false_negatives = 0

    should_be_true = True
    for wav_path in itertools.chain(true_wav_paths, [None], false_wav_paths):
        # Switch between true and false examples
        if wav_path is None:
            should_be_true = not should_be_true
            continue

        detected = wav_path in detected_paths
        if detected:
            if should_be_true:
                true_positives += 1
                status = ""
            else:
                false_positives += 1
                status = ":("
        else:
            if should_be_true:
                false_negatives += 1
                status = ":("
            else:
                true_negatives += 1
                status = ""

    # Report
    result = {
        "system": wake_system,
        "settings": profile.get("wake.%s" % wake_system, {}),
        "detected": list(detected_paths),
        "not_detected": list(set(all_wav_paths) - set(detected_paths)),
        "time_sec": end_time - start_time,
        "statistics": {
            "true_positives": true_positives,
            "true_negatives": true_negatives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
        },
    }

    json.dump(result, sys.stdout, indent=4)


# -----------------------------------------------------------------------------


class TestWakeActor(RhasspyActor):
    def __init__(self):
        RhasspyActor.__init__(self)
        self.actors: List[RhasspyActor] = []
        self.wav_paths: List[str] = []
        self.wav_paths_left: List[str] = []
        self.detected_paths: Set[str] = set()

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, tuple):
            # Start up
            self.parent = sender
            wake_system, num_actors, self.wav_paths = message
            self.wav_paths_left = list(self.wav_paths)

            # Create actors
            wake_class = DialogueManager.get_wake_class(wake_system)
            for i in range(num_actors):
                actor = self.createActor(wake_class)
                self.send(
                    actor,
                    ConfigureEvent(
                        profile=self.profile,
                        preload=True,
                        recorder=self.myAddress,
                        transitions=False,
                        not_detected=True,
                    ),
                )

            self.transition("loaded")

    def in_loaded(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, Configured):
            self.send(sender, ListenForWakeWord())
        elif isinstance(message, StartStreaming):
            if len(self.wav_paths) > 0:
                self.send_random_wav(sender)
        elif isinstance(message, WakeWordDetected):
            # Detected
            wav_path = message.audio_data_info["path"]
            # print('!', end='', flush=True)
            self.detected_paths.add(wav_path)
            if wav_path in self.wav_paths_left:
                self.wav_paths_left.remove(wav_path)

                if len(self.wav_paths) > 0:
                    self.send_random_wav(sender)

        elif isinstance(message, WakeWordNotDetected):
            # Not detected
            wav_path = message.audio_data_info["path"]
            # print('.', end='', flush=True)
            self.wav_paths_left.remove(wav_path)
            if len(self.wav_paths) > 0:
                self.send_random_wav(sender)

        if len(self.wav_paths_left) == 0:
            self.send(self.parent, self.detected_paths)

    def send_random_wav(self, receiver):
        index = random.randint(0, len(self.wav_paths) - 1)
        wav_path = self.wav_paths.pop(index)
        with open(wav_path, "rb") as wav_file:
            audio_data = maybe_convert_wav(wav_file.read())
            self.send(receiver, AudioData(audio_data, path=wav_path))


# -----------------------------------------------------------------------------
# mic2wav: record voice command and output WAV data
# -----------------------------------------------------------------------------


def mic2wav(core: RhasspyCore, profile: Profile, args: Any) -> None:
    # Listen until silence
    wav_data = buffer_to_wav(core.record_command(args.timeout).data)

    # Output WAV data
    sys.stdout.buffer.write(wav_data)


# -----------------------------------------------------------------------------
# mic2text: record voice command, then transcribe
# -----------------------------------------------------------------------------


def mic2text(core: RhasspyCore, profile: Profile, args: Any) -> None:
    # Listen until silence
    wav_data = buffer_to_wav(core.record_command(args.timeout).data)

    # Transcribe
    text = core.transcribe_wav(wav_data).text

    # Output text
    print(text)


# -----------------------------------------------------------------------------
# mic2intent: record voice command, then transcribe/parse
# -----------------------------------------------------------------------------


def read_audio_stdin(core: RhasspyCore, chunk_size: int = 960):
    global mic_stdin_running
    while mic_stdin_running:
        audio_data = sys.stdin.buffer.read(chunk_size)
        core.send_audio_data(AudioData(audio_data))


def mic2intent(core: RhasspyCore, profile: Profile, args: Any) -> None:
    # Listen until silence
    wav_data = buffer_to_wav(core.record_command(args.timeout).data)

    # Transcribe
    sentence = core.transcribe_wav(wav_data).text

    # Parse
    intent = core.recognize_intent(sentence).intent

    if args.handle:
        intent = core.handle_intent(intent).intent

    # Output JSON
    json.dump(intent, sys.stdout, indent=4)


# -----------------------------------------------------------------------------
# word2phonemes: get pronunciation(s) for a word
# -----------------------------------------------------------------------------


def word2phonemes(core: RhasspyCore, profile: Profile, args: Any) -> None:
    words = args.words if len(args.words) > 0 else sys.stdin

    # Get pronunciations for all words
    pronunciations = core.get_word_pronunciations(words, n=args.n).pronunciations

    # Output JSON
    json.dump(pronunciations, sys.stdout, indent=4)


# -----------------------------------------------------------------------------
# word2wav: pronounce word as WAV data
# -----------------------------------------------------------------------------


def word2wav(core: RhasspyCore, profile: Profile, args: Any) -> None:
    # Get pronunciation for word
    all_pronunciations = core.get_word_pronunciations([args.word], n=1).pronunciations
    word_pronunciations = all_pronunciations[args.word]["pronunciations"]

    # Convert from CMU phonemes to eSpeak phonemes
    espeak_str = core.get_word_phonemes(word_pronunciations[0]).phonemes

    # Pronounce as WAV
    wav_data = core.speak_word(espeak_str).wav_data

    # Output WAV data
    sys.stdout.buffer.write(wav_data)


# -----------------------------------------------------------------------------
# wav2mqtt: output WAV data to MQTT via Hermes protocol
# -----------------------------------------------------------------------------


def _send_frame(
    core: RhasspyCore,
    topic: str,
    audio_data: bytes,
    rate: int,
    width: int,
    channels: int,
) -> None:
    with io.BytesIO() as mqtt_buffer:
        with wave.open(mqtt_buffer, mode="wb") as mqtt_file:
            mqtt_file.setframerate(rate)
            mqtt_file.setsampwidth(width)
            mqtt_file.setnchannels(channels)
            mqtt_file.writeframesraw(audio_data)

        # Send audio frame WAV
        mqtt_payload = mqtt_buffer.getvalue()
        core.mqtt_publish(topic, mqtt_payload)


def wav2mqtt(core: RhasspyCore, profile: Profile, args: Any) -> None:
    # hermes/audioServer/<SITE_ID>/audioFrame
    topic = "hermes/audioServer/%s/audioFrame" % args.site_id

    if len(args.wav_files) > 0:
        # Read WAV paths from argument list
        for wav_path in args.wav_files:
            with wave.open(wav_path, "rb") as wav_file:
                rate = wav_file.getframerate()
                width = wav_file.getsampwidth()
                channels = wav_file.getnchannels()

                if args.frames > 0:
                    # Split into chunks
                    chunk_size = args.frames * width * channels
                    if args.silence_before > 0:
                        # Silence
                        num_chunks = int(
                            (args.silence_before * rate * width * channels) / chunk_size
                        )
                        for i in range(num_chunks):
                            _send_frame(
                                core, topic, bytes(chunk_size), rate, width, channels
                            )
                            time.sleep(args.pause)

                    # Read actual audio data
                    audio_data = wav_file.readframes(args.frames)

                    while len(audio_data) > 0:
                        _send_frame(core, topic, audio_data, rate, width, channels)
                        time.sleep(args.pause)

                        # Read next chunk
                        audio_data = wav_file.readframes(args.frames)

                    if args.silence_after > 0:
                        # Silence
                        num_chunks = int(
                            (args.silence_after * rate * width * channels) / chunk_size
                        )
                        for i in range(num_chunks):
                            _send_frame(
                                core, topic, bytes(chunk_size), rate, width, channels
                            )
                            time.sleep(args.pause)
                else:
                    # Send all at once
                    audio_data = wav_file.readframes(wav_file.getnframes())
                    _send_frame(core, topic, audio_data, rate, width, channels)

            print(wav_path)


# -----------------------------------------------------------------------------
# text2wav: speak sentence and output WAV
# -----------------------------------------------------------------------------


def text2wav(core: RhasspyCore, profile: Profile, args: Any) -> None:
    result = core.speak_sentence(args.sentence)
    sys.stdout.buffer.write(result.wav_data)


# -----------------------------------------------------------------------------
# text2speech: speak sentences
# -----------------------------------------------------------------------------


def text2speech(core: RhasspyCore, profile: Profile, args: Any) -> None:
    sentences = args.sentences
    if len(sentences) == 0:
        sentences = sys.stdin

    for sentence in sentences:
        sentence = sentence.strip()
        core.speak_sentence(sentence)


# -----------------------------------------------------------------------------
# sleep: wait for wake word
# -----------------------------------------------------------------------------


def sleep(core: RhasspyCore, profile: Profile, args: Any) -> None:
    result = core.wakeup_and_wait()
    if isinstance(result, WakeWordDetected):
        print(result.name)
    else:
        print("")  # not detected


# -----------------------------------------------------------------------------
# download: download profile files
# -----------------------------------------------------------------------------


def download(core: RhasspyCore, profile: Profile, args: Any) -> None:
    core.download_profile(delete=args.delete)
    print("OK")


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
