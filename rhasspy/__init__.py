#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import argparse
import threading
import tempfile
import random
import time
import logging
import itertools

from utils import extract_entities
from audio_recorder import WavAudioRecorder
from wake import PocketsphinxWakeListener
from tune import SphinxTrainSpeechTuner

# -----------------------------------------------------------------------------

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Rhasspy Voice Assistant')
    parser.add_argument('--profile', type=str, help='Name of profile to use', default=None)
    parser.add_argument('--debug', action='store_true', help='Print DEBUG log to console')

    sub_parsers = parser.add_subparsers(dest='command')
    sub_parsers.required = True

    # info
    info_parser = sub_parsers.add_parser('info', help='Profile information')
    info_parser.add_argument('--defaults', action='store_true', help='Only print default settings')

    # wav2text
    wav2text_parser = sub_parsers.add_parser('wav2text', help='WAV file to text transcription')
    wav2text_parser.add_argument('wav_files', nargs='*', help='Paths to WAV files')

    # text2intent
    text2intent_parser = sub_parsers.add_parser('text2intent', help='Text parsed to intent')
    text2intent_parser.add_argument('sentences', nargs='*', help='Sentences to parse')

    # wav2intent
    wav2intent_parser = sub_parsers.add_parser('wav2intent', help='WAV file to parsed intent')
    wav2intent_parser.add_argument('wav_files', nargs='*', help='Paths to WAV files')

    # train
    train_parser = sub_parsers.add_parser('train', help='Re-train profile')

    # record
    record_parser = sub_parsers.add_parser('record', help='Record test phrases for profile')
    record_parser.add_argument('--directory', help='Directory to write WAV files and intent JSON files')

    # record-wake
    record_wake_parser = sub_parsers.add_parser('record-wake', help='Record wake word examples for profile')
    record_wake_parser.add_argument('--directory', help='Directory to write WAV files')
    record_wake_parser.add_argument('--negative', action='store_true', help='Record negative examples (not the wake word)')

    # tune
    tune_parser = sub_parsers.add_parser('tune', help='Tune speech acoustic model for profile')
    tune_parser.add_argument('--directory', help='Directory with WAV files and intent JSON files')

    # tune-wake
    tune_wake_parser = sub_parsers.add_parser('tune-wake', help='Tune wake acoustic model for profile')
    tune_wake_parser.add_argument('--directory', help='Directory with WAV files')

    # test
    test_parser = sub_parsers.add_parser('test', help='Test speech/intent recognizers for profile')
    test_parser.add_argument('directory', help='Directory with WAV files and intent JSON files')

    # test-wake
    test_wake_parser = sub_parsers.add_parser('test-wake', help='Test wake word examples for profile')
    test_wake_parser.add_argument('--directory', help='Directory with WAV files')

    # mic2wav
    mic2wav_parser = sub_parsers.add_parser('mic2wav', help='Voice command to WAV data')

    # mic2text
    mic2text_parser = sub_parsers.add_parser('mic2text', help='Voice command to text transcription')

    # mic2intent
    mic2intent_parser = sub_parsers.add_parser('mic2intent', help='Voice command to parsed intent')

    # word2phonemes
    word2phonemes_parser = sub_parsers.add_parser('word2phonemes', help='Get pronunciation(s) for word(s)')
    word2phonemes_parser.add_argument('words', nargs='*', help='Word(s) to pronounce')
    word2phonemes_parser.add_argument('-n', type=int, default=1, help='Maximum number of pronunciations')

    # word2wav
    word2wav_parser = sub_parsers.add_parser('word2wav', help='Pronounce word')
    word2wav_parser.add_argument('word', help='Word to pronounce')

    # sleep
    sleep_parser = sub_parsers.add_parser('sleep', help='Wait for wake word')

    # -------------------------------------------------------------------------

    args = parser.parse_args()

    # Like PATH, searched in reverse order
    profiles_dirs = [path for path in
                     os.environ.get('RHASSPY_PROFILES', 'profiles')\
                     .split(':') if len(path.strip()) > 0]

    profiles_dirs.reverse()

    # Create rhasspy core
    from .core import Rhasspy
    core = Rhasspy(profiles_dirs)

    # Load profile
    if args.profile is not None:
        profile = core.profiles[args.profile]
    else:
        profile = core.default_profile

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)

    # Execute command
    command_funcs = {
        'info': info,
        'wav2text': wav2text,
        'text2intent': text2intent,
        'wav2intent': wav2intent,
        'train': train,
        'record': record,
        'record-wake': record_wake,
        'tune': tune,
        'tune-wake': tune_wake,
        'test': test,
        'test-wake': test_wake,
        'mic2text': mic2text,
        'mic2intent': mic2intent,
        'mic2wav': mic2wav,
        'word2phonemes': word2phonemes,
        'word2wav': word2wav,
        'sleep': sleep
    }

    command_funcs[args.command](core, profile, args)

# -----------------------------------------------------------------------------
# info: print profile JSON
# -----------------------------------------------------------------------------

def info(core, profile, args):
    if args.defaults:
        # Print default settings
        json.dump(core.defaults_json, sys.stdout, indent=4)
    else:
        # Print profile settings
        json.dump(profile.json, sys.stdout, indent=4)

# -----------------------------------------------------------------------------
# wav2text: transcribe WAV file(s) to text
# -----------------------------------------------------------------------------

def wav2text(core, profile, args):
    decoder = core.get_speech_decoder(profile.name)

    if len(args.wav_files) > 0:
        # Read WAV paths from argument list
        transcriptions = {}
        for wav_path in args.wav_files:
            with open(wav_path, 'rb') as wav_file:
                text = decoder.transcribe_wav(wav_file.read())
                transcriptions[wav_path] = text

        # Output JSON
        json.dump(transcriptions, sys.stdout, indent=4)
    else:
        # Read WAV data from stdin
        text = decoder.transcribe_wav(sys.stdin.buffer.read())

        # Output text
        print(text)

# -----------------------------------------------------------------------------
# text2intent: parse text into intent(s)
# -----------------------------------------------------------------------------

def text2intent(core, profile, args):
    recognizer = core.get_intent_recognizer(profile.name)

    # Parse sentences from command line or stdin
    intents = {}
    sentences = args.sentences if len(args.sentences) > 0 else sys.stdin
    for sentence in sentences:
        sentence = sentence.strip()
        intent = recognizer.recognize(sentence)
        intents[sentence] = intent

    # Output JSON
    json.dump(intents, sys.stdout, indent=4)

# -----------------------------------------------------------------------------
# wav2intent: transcribe WAV file(s) to text and parse into intent(s)
# -----------------------------------------------------------------------------

def wav2intent(core, profile, args):
    decoder = core.get_speech_decoder(profile.name)
    recognizer = core.get_intent_recognizer(profile.name)

    if len(args.wav_files) > 0:
        # Read WAV paths from argument list
        transcriptions = {}
        for wav_path in args.wav_files:
            with open(wav_path, 'rb') as wav_file:
                text = decoder.transcribe_wav(wav_file.read())
                transcriptions[wav_path] = text

        # Parse intents
        intents = {}
        for wav_path, sentence in transcriptions.items():
            intent = recognizer.recognize(sentence)
            intents[wav_path] = intent

        # Output JSON
        json.dump(intents, sys.stdout, indent=4)
    else:
        # Read WAV data from stdin
        sentence = decoder.transcribe_wav(sys.stdin.buffer.read())
        intent = recognizer.recognize(sentence)

        # Output JSON
        json.dump(intent, sys.stdout, indent=4)

# -----------------------------------------------------------------------------
# train: re-train profile speech/intent recognizers
# -----------------------------------------------------------------------------

def train(core, profile, args):
    core.train_profile(profile.name)

# -----------------------------------------------------------------------------
# record: record phrases for testing/tuning
# -----------------------------------------------------------------------------

def record(core, profile, args):
    dir_path = args.directory or profile.write_dir('record')
    dir_name = os.path.split(dir_path)[1]
    os.makedirs(dir_path, exist_ok=True)

    tagged_path = profile.read_path(profile.get('training.tagged_sentences'))
    assert os.path.exists(tagged_path), 'Missing tagged sentences (%s). Need to train?' % tagged_path

    # Load and parse tagged sentences
    intent_sentences = []
    intent_name = ''
    with open(tagged_path, 'r') as tagged_file:
        for line in tagged_file:
            line = line.strip()
            if len(line) == 0:
                continue  # skip blank lines

            if line.startswith('# intent:'):
                intent_name = line.split(':', maxsplit=1)[1]
            elif line.startswith('-'):
                tagged_sentence = line[1:].strip()
                sentence, entities = extract_entities(tagged_sentence)
                intent_sentences.append((intent_name, sentence, entities))

    assert len(intent_sentences) > 0, 'No tagged sentences available'
    print('Loaded %s sentence(s)' % len(intent_sentences))

    # Record WAV files
    audio_recorder = core.get_audio_recorder()
    wav_prefix = dir_name
    wav_num = 0
    try:
        while True:
            intent_name, sentence, entities = random.choice(intent_sentences)
            print('Speak the following sentence. Press ENTER to start (CTRL+C to quit).')
            print(sentence)
            input()
            audio_recorder.start_recording(True, False)
            print('Recording. Press ENTER to stop (CTRL+C to quit).')
            input()
            wav_data = audio_recorder.stop_recording(True, False)

            # Determine WAV file name
            wav_path = os.path.join(dir_path, '%s-%03d.wav' % (wav_prefix, wav_num))
            while os.path.exists(wav_path):
                wav_num += 1
                wav_path = os.path.join(dir_path, '%s-%03d.wav' % (wav_prefix, wav_num))

            # Write WAV data
            with open(wav_path, 'wb') as wav_file:
                wav_file.write(wav_data)

            # Write intent (with transcription)
            intent_path = os.path.join(dir_path, '%s-%03d.wav.json' % (wav_prefix, wav_num))
            with open(intent_path, 'w') as intent_file:
                # Use rasaNLU format
                intent = {
                    'text': sentence,
                    'intent': { 'name': intent_name },
                    'entities': [
                        { 'entity': entity, 'value': value }
                        for entity, value in entities
                    ]
                }

                json.dump(intent, intent_file, indent=4)

            print('')
    except KeyboardInterrupt:
        print('Done')

# -----------------------------------------------------------------------------
# record-wake: record wake word examples
# -----------------------------------------------------------------------------

def record_wake(core, profile, args):
    keyphrase = profile.get('wake.pocketsphinx.keyphrase', '')
    assert len(keyphrase) > 0, 'No wake word'

    wav_prefix = keyphrase.replace(' ', '-')
    base_dir_path = args.directory or profile.write_dir('record')

    if args.negative:
        dir_path = os.path.join(base_dir_path, wav_prefix, 'not-wake-word')
    else:
        dir_path = os.path.join(base_dir_path, wav_prefix, 'wake-word')

    os.makedirs(dir_path, exist_ok=True)

    # Record WAV files
    audio_recorder = core.get_audio_recorder()
    wav_num = 0
    try:
        while True:
            # Determine WAV file name
            wav_path = os.path.join(dir_path, '%s-%02d.wav' % (wav_prefix, wav_num))
            while os.path.exists(wav_path):
                wav_num += 1
                wav_path = os.path.join(dir_path, '%s-%02d.wav' % (wav_prefix, wav_num))

            if args.negative:
                print('Speak anything EXCEPT the wake word. Press ENTER to start (CTRL+C to quit).')
                print('NOT %s (%s)' % (keyphrase, wav_num))
            else:
                print('Speak your wake word. Press ENTER to start (CTRL+C to quit).')
                print('%s (%s)' % (keyphrase, wav_num))

            input()
            audio_recorder.start_recording(True, False)
            print('Recording. Press ENTER to stop (CTRL+C to quit).')
            input()
            wav_data = audio_recorder.stop_recording(True, False)

            # Write WAV data
            with open(wav_path, 'wb') as wav_file:
                wav_file.write(wav_data)

            print('')
    except KeyboardInterrupt:
        print('Done')

# -----------------------------------------------------------------------------
# tune: fine tune speech acoustic model
# -----------------------------------------------------------------------------

def tune(core, profile, args):
    dir_path = args.directory or profile.read_path('record')
    assert os.path.exists(dir_path), 'Directory does not exist'
    wav_paths = [os.path.join(dir_path, name)
                 for name in os.listdir(dir_path)
                 if name.endswith('.wav')]

    # Load intents for each WAV
    wav_intents = {}
    for wav_path in wav_paths:
        intent_path = wav_path + '.json'
        if os.path.exists(intent_path):
            with open(intent_path, 'r') as intent_file:
                wav_intents[wav_path] = json.load(intent_file)

    # Do tuning
    tuner = core.get_speech_tuner(profile.name)
    tuner.preload()

    print('Tuning speech system with %s WAV file(s)' % len(wav_intents))
    tune_start = time.time()
    tuner.tune(wav_intents)
    print('Finished tuning in %s second(s)' % (time.time() - tune_start))

# -----------------------------------------------------------------------------
# tune-wake: fine tune wake acoustic model
# -----------------------------------------------------------------------------

def tune_wake(core, profile, args):
    keyphrase = profile.get('wake.pocketsphinx.keyphrase', '')
    assert len(keyphrase) > 0, 'No wake word'

    wav_prefix = keyphrase.replace(' ', '-')
    base_dir_path = args.directory or profile.read_path('record')

    # Path to positive examples
    true_path = os.path.join(base_dir_path, wav_prefix, 'wake-word')
    if os.path.exists(true_path):
        true_wav_paths = [os.path.join(true_path, name)
                          for name in os.listdir(true_path)
                          if name.endswith('.wav')]
    else:
        true_wav_paths = []

    # Path to negative examples
    false_path = os.path.join(base_dir_path, wav_prefix, 'not-wake-word')
    if os.path.exists(false_path):
        false_wav_paths = [os.path.join(false_path, name)
                          for name in os.listdir(false_path)
                          if name.endswith('.wav')]
    else:
        false_wav_paths = []

    # Do tuning
    mllr_path = profile.write_path(
        profile.get('wake.pocketsphinx.mllr_matrix'))

    tuner = SphinxTrainSpeechTuner(profile)
    tuner.preload()

    # Add "transcriptions"
    wav_intents = {}
    for wav_path in true_wav_paths:
        wav_intents[wav_path] = { 'text': keyphrase }

    for wav_path in false_wav_paths:
        wav_intents[wav_path] = { 'text': '' }

    print('Tuning wake word system with %s positive and %s negative example(s)' % (len(true_wav_paths), len(false_wav_paths)))
    tune_start = time.time()
    tuner.tune(wav_intents, mllr_path=mllr_path)
    print('Finished tuning in %s second(s)' % (time.time() - tune_start))

# -----------------------------------------------------------------------------
# test: test speech/intent recognizers
# -----------------------------------------------------------------------------

def test(core, profile, args):
    dir_path = args.directory or profile.read_path('record')
    assert os.path.exists(dir_path), 'Directory does not exist'
    wav_paths = [os.path.join(dir_path, name)
                 for name in os.listdir(dir_path)
                 if name.endswith('.wav')]

    # Load intents for each WAV
    wav_intents = {}
    for wav_path in wav_paths:
        intent_path = wav_path + '.json'
        if os.path.exists(intent_path):
            with open(intent_path, 'r') as intent_file:
                wav_intents[wav_path] = json.load(intent_file)

    # Transcribe and match intent names/entities
    decoder = core.get_speech_decoder(profile.name)
    decoder.preload()

    recognizer = core.get_intent_recognizer(profile.name)
    recognizer.preload()

    # TODO: parallelize
    results = {}
    for wav_path, expected_intent in wav_intents.items():
        # Transcribe
        decode_start = time.time()
        with open(wav_path, 'rb') as wav_file:
            actual_sentence = decoder.transcribe_wav(wav_file.read())

        decode_sec = time.time() - decode_start

        # Recognize
        recognize_start = time.time()
        actual_intent = recognizer.recognize(actual_sentence)
        recognize_sec = time.time() - recognize_start

        wav_name = os.path.split(wav_path)[1]
        results[wav_name] = {
            'profile': profile.name,
            'expected': expected_intent,
            'actual': actual_intent,
            'speech': {
                'system': profile.get('speech_to_text.system'),
                'time_sec': decode_sec
            },
            'intent': {
                'system': profile.get('intent.system'),
                'time_sec': recognize_sec
            }
        }

    json.dump(results, sys.stdout, indent=4)

# -----------------------------------------------------------------------------
# test-wake: test wake word examples
# -----------------------------------------------------------------------------

def test_wake(core, profile, args):
    keyphrase = profile.get('wake.pocketsphinx.keyphrase', '')
    assert len(keyphrase) > 0, 'No wake word'

    wav_prefix = keyphrase.replace(' ', '-')
    base_dir_path = args.directory or profile.read_path('record')

    # Path to positive examples
    true_path = os.path.join(base_dir_path, wav_prefix, 'wake-word')
    if os.path.exists(true_path):
        true_wav_paths = [os.path.join(true_path, name)
                          for name in os.listdir(true_path)
                          if name.endswith('.wav')]
    else:
        true_wav_paths = []

    # Path to negative examples
    false_path = os.path.join(base_dir_path, wav_prefix, 'not-wake-word')
    if os.path.exists(false_path):
        false_wav_paths = [os.path.join(false_path, name)
                          for name in os.listdir(false_path)
                          if name.endswith('.wav')]
    else:
        false_wav_paths = []

    # Instantiate wake listener
    wake_listener = PocketsphinxWakeListener(
        core, audio_recorder=None, profile=profile, detected_callback=None)

    wake_listener.preload()

    # TODO: parallelize
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

        done_event = threading.Event()
        audio_recorder = WavAudioRecorder(
            core,
            wav_path,
            lambda wp: done_event.set())

        wake_listener.audio_recorder = audio_recorder

        detected = False
        def callback(profile_name, keyphrase):
            nonlocal detected
            detected = True

        wake_listener.callback = callback

        # Listen and wait until WAV is finished playing
        wake_listener.start_listening()
        done_event.wait()
        audio_recorder.stop_recording(False, True)

        # Wait for listener to finish up
        while wake_listener.is_listening:
            time.sleep(0.1)

        if detected:
            if should_be_true:
                true_positives += 1
                status = ''
            else:
                false_positives += 1
                status = ':('
        else:
            if should_be_true:
                false_negatives += 1
                status = ':('
            else:
                true_negatives += 1
                status = ''

        print('%s %s ' % (wav_path, status))

    print('')
    print('True positives: %s' % true_positives)
    print('True negatives: %s' % true_negatives)
    print('False positives: %s' % false_positives)
    print('False negatives: %s' % false_negatives)

# -----------------------------------------------------------------------------
# mic2wav: record voice command and output WAV data
# -----------------------------------------------------------------------------

def mic2wav(core, profile, args):
    # Listen until silence
    command_listener = core.get_command_listener()
    wav_data = command_listener.listen_for_command()

    # Output WAV data
    sys.stdout.buffer.write(wav_data)

# -----------------------------------------------------------------------------
# mic2text: record voice command, then transcribe
# -----------------------------------------------------------------------------

def mic2text(core, profile, args):
    # Listen until silence
    command_listener = core.get_command_listener()
    wav_data = command_listener.listen_for_command()

    # Transcribe
    decoder = core.get_speech_decoder(profile.name)
    text = decoder.transcribe_wav(wav_data)

    # Output text
    print(text)

# -----------------------------------------------------------------------------
# mic2intent: record voice command, then transcribe/parse
# -----------------------------------------------------------------------------

def mic2intent(core, profile, args):
    # Listen until silence
    command_listener = core.get_command_listener()
    wav_data = command_listener.listen_for_command()

    # Transcribe
    decoder = core.get_speech_decoder(profile.name)
    sentence = decoder.transcribe_wav(wav_data)

    # Parse
    recognizer = core.get_intent_recognizer(profile.name)
    intent = recognizer.recognize(sentence)

    # Output JSON
    json.dump(intent, sys.stdout, indent=4)

# -----------------------------------------------------------------------------
# word2phonemes: get pronunciation(s) for a word
# -----------------------------------------------------------------------------

def word2phonemes(core, profile, args):
    word_pron = core.get_word_pronouncer(profile.name)

    words = args.words if len(args.words) > 0 else sys.stdin
    all_pronunciations = {}

    # Get pronunciations for all words
    for word in words:
        word = word.strip()
        _, word_pronunciations, _ = word_pron.pronounce(word, n=args.n)
        all_pronunciations[word] = word_pronunciations

    # Output JSON
    json.dump(all_pronunciations, sys.stdout, indent=4)

# -----------------------------------------------------------------------------
# word2wav: pronounce word as WAV data
# -----------------------------------------------------------------------------

def word2wav(core, profile, args):
    word_pron = core.get_word_pronouncer(profile.name)

    # Get pronunciation for word
    _, word_pronunciations, _ = word_pron.pronounce(args.word, n=1)

    # Convert from CMU phonemes to eSpeak phonemes
    espeak_str = word_pron.translate_phonemes(word_pronunciations[0])

    # Pronounce as WAV
    _, wav_data = word_pron.speak(espeak_str)

    # Output WAV data
    sys.stdout.buffer.write(wav_data)

# -----------------------------------------------------------------------------
# sleep: wait for wake word
# -----------------------------------------------------------------------------

def sleep(core, profile, args):
    wake_event = threading.Event()

    def handle_wake(profile_name: str, keyphrase: str):
        print(keyphrase)
        wake_event.set()

    wake = core.get_wake_listener(profile.name, handle_wake)
    wake.start_listening()

    try:
        wake_event.wait()
    except KeyboardInterrupt:
        pass

# -----------------------------------------------------------------------------

if __name__ == '__main__':
    main()
