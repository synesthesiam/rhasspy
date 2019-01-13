import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
import time
from typing import List, Dict, Optional, Any, Callable

import pydash

# Internal imports
from profiles import Profile
from audio_player import AudioPlayer
from audio_recorder import AudioRecorder
from command_listener import CommandListener
from stt import SpeechDecoder
from intent import IntentRecognizer
from pronounce import WordPronounce
from wake import WakeListener
from intent_handler import IntentHandler
from train import SentenceGenerator
from tune import SpeechTuner
from mqtt import HermesMqtt

# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class Rhasspy:
    '''Core class for Rhasspy functionality. Loads profiles and caches stuff.'''

    def __init__(self,
                 profiles_dirs: List[str],
                 default_profile_name: Optional[str] = None) -> None:

        '''profiles_dirs: List of directories to search for profiles.
        default_profile_name: name of default profile.'''

        self.profiles_dirs = profiles_dirs
        self.default_profile_name = default_profile_name

        self.audio_recorder: Optional[AudioRecorder] = None
        self.audio_player: Optional[AudioPlayer] = None
        self.command_listener: Optional[CommandListener] = None

        self.speech_decoders: Dict[str, SpeechDecoder] = {}
        self.intent_recognizers: Dict[str, IntentRecognizer] = {}
        self.word_pronouncers: Dict[str, WordPronounce] = {}
        self.wake_listeners: Dict[str, WakeListener] = {}
        self.intent_handlers: Dict[str, IntentHandler] = {}
        self.sentence_generators: Dict[str, SentenceGenerator] = {}
        self.speech_tuners: Dict[str, SpeechTuner] = {}

        # ---------------------------------------------------------------------

        logger.debug('Profiles dirs: %s' % self.profiles_dirs)

        # Load default settings
        self.defaults_json = Profile.load_defaults(self.profiles_dirs)

        # Load profiles
        self.profiles: Dict[str, Profile] = {}
        for profiles_dir in self.profiles_dirs:
            if not os.path.exists(profiles_dir):
                continue

            # Check each directory
            for name in os.listdir(profiles_dir):
                profile_dir = os.path.join(profiles_dir, name)
                if os.path.isdir(profile_dir):
                    logger.debug('Loading profile from %s' % profile_dir)
                    profile = Profile(name, self.profiles_dirs)
                    self.profiles[name] = profile
                    logger.info('Loaded profile %s' % name)

        # Get default profile
        if self.default_profile_name is None:
            self.default_profile_name = \
                self.get_default('rhasspy.default_profile', 'en')

        assert self.default_profile_name is not None
        self.default_profile = self.profiles[self.default_profile_name]

        # Load MQTT client
        self.mqtt_client: HermesMqtt = HermesMqtt(self)

    # -------------------------------------------------------------------------

    def get_default(self, path: str, default=None):
        '''Gets a default setting or default value'''
        return pydash.get(self.defaults_json, path, default)

    # -------------------------------------------------------------------------

    def get_audio_player(self) -> AudioPlayer:
        '''Gets the shared audio player'''
        if self.audio_player is None:
            system = self.get_default('sounds.system', 'dummy')
            assert system in ['aplay', 'hermes', 'dummy'], 'Unknown sound system: %s' % system
            if system == 'aplay':
                from audio_player import APlayAudioPlayer
                device = self.get_default('sounds.aplay.device')
                self.audio_player = APlayAudioPlayer(self, device)
            elif system == 'heremes':
                from audio_player import HeremesAudioPlayer
                self.audio_player = HeremesAudioPlayer(self)
            elif system == 'dummy':
                self.audio_player = AudioPlayer(self)

        return self.audio_player

    # -------------------------------------------------------------------------

    def get_audio_recorder(self) -> AudioRecorder:
        '''Gets the shared audio recorder'''
        if self.audio_recorder is None:
            # Determine which microphone system to use
            system = self.default_profile.get('microphone.system')
            assert system in ['arecord', 'pyaudio', 'hermes'], 'Unknown microphone system: %s' % system
            if system == 'arecord':
                from audio_recorder import ARecordAudioRecorder
                device = self.get_default('microphone.arecord.device')
                self.audio_recorder = ARecordAudioRecorder(self, device)
                logger.debug('Using arecord for microphone')
            elif system == 'pyaudio':
                from audio_recorder import PyAudioRecorder
                device = self.get_default('microphone.pyaudio.device')
                self.audio_recorder = PyAudioRecorder(self, device)
                logger.debug('Using PyAudio for microphone')
            elif system == 'hermes':
                from audio_recorder import HermesAudioRecorder
                self.audio_recorder = HermesAudioRecorder(self, device)
                logger.debug('Using Hermes for microphone')

        return self.audio_recorder

    # -------------------------------------------------------------------------

    def get_speech_decoder(self, profile_name: str) -> SpeechDecoder:
        '''Gets the speech transcriber for a profile (WAV to text)'''
        decoder = self.speech_decoders.get(profile_name)
        if decoder is None:
            profile = self.profiles[profile_name]
            system = profile.get('speech_to_text.system')
            assert system in ['dummy', 'pocketsphinx', 'remote'], 'Invalid speech to text system: %s' % system
            if system == 'pocketsphinx':
                from stt import PocketsphinxDecoder
                decoder = PocketsphinxDecoder(profile)
            elif system == 'remote':
                from stt import RemoteDecoder
                decoder = RemoteDecoder(profile)
            elif system == 'dummy':
                # Does nothing
                decoder = SpeechDecoder(profile)

            # Cache decoder
            self.speech_decoders[profile_name] = decoder

        return decoder

    # -------------------------------------------------------------------------

    def get_speech_tuner(self, profile_name: str) -> SpeechTuner:
        '''Gets the speech tuner for a profile (acoustic model)'''
        tuner = self.speech_tuners.get(profile_name)
        if tuner is None:
            profile = self.profiles[profile_name]
            system = profile.get('tuning.system')
            assert system in ['dummy', 'sphinxtrain'], 'Invalid speech tuning system: %s' % system
            if system == 'sphinxtrain':
                from tune import SphinxTrainSpeechTuner
                tuner = SphinxTrainSpeechTuner(profile)
            elif system == 'dummy':
                # Does nothing
                tuner = SpeechTuner(profile)

            # Cache tuner
            self.speech_tuners[profile_name] = tuner

        return tuner

    # -------------------------------------------------------------------------

    def get_intent_recognizer(self, profile_name: str) -> IntentRecognizer:
        '''Gets the intent recognizer for a profile (text to intent dict)'''
        recognizer = self.intent_recognizers.get(profile_name)
        if recognizer is None:
            profile = self.profiles[profile_name]
            system = profile.get('intent.system')
            assert system in ['dummy', 'fuzzywuzzy', 'adapt', 'rasa', 'remote'], 'Invalid intent system: %s' % system
            if system == 'fuzzywuzzy':
                # Use fuzzy string matching locally
                from intent import FuzzyWuzzyRecognizer
                recognizer = FuzzyWuzzyRecognizer(profile)
            elif system == 'adapt':
                # Use Mycroft Adapt locally
                from intent import AdaptIntentRecognizer
                recognizer = AdaptIntentRecognizer(profile)
                pass
            elif system == 'rasa':
                # Use rasaNLU remotely
                from intent import RasaIntentRecognizer
                recognizer = RasaIntentRecognizer(profile)
                pass
            elif system == 'remote':
                # Use remote rhasspy server
                from intent import RemoteRecognizer
                recognizer = RemoteRecognizer(profile)
            elif system == 'dummy':
                # Does nothing
                recognizer = IntentRecognizer(profile)

            # Cache recognizer
            self.intent_recognizers[profile_name] = recognizer

        return recognizer

    # -------------------------------------------------------------------------

    def get_word_pronouncer(self, profile_name: str) -> WordPronounce:
        '''Gets a word lookup/pronounce-er for a profile'''
        word_pron = self.word_pronouncers.get(profile_name)
        if word_pron is None:
            from pronounce import PhonetisaurusPronounce
            profile = self.profiles[profile_name]
            word_pron = PhonetisaurusPronounce(profile)
            self.word_pronouncers[profile_name] = word_pron

        return self.word_pronouncers[profile_name]

    # -------------------------------------------------------------------------

    def get_command_listener(self):
        '''Gets the shared voice command listener (VAD + silence bracketing).'''
        if self.command_listener is None:
            self.command_listener = CommandListener(
                self.get_audio_recorder(), 16000)

        return self.command_listener

    # -------------------------------------------------------------------------

    def get_wake_listener(self, profile_name: str,
                          callback: Callable[[str, str], None] = None) -> WakeListener:
        '''Gets the wake/hot word listener for a profile.'''
        wake = self.wake_listeners.get(profile_name)
        if wake is None:
            callback = callback or self._handle_wake
            profile = self.profiles[profile_name]
            system = profile.get('wake.system')
            assert system in ['dummy', 'pocketsphinx', 'nanomsg', 'hermes'], 'Invalid wake system: %s' % system
            if system == 'pocketsphinx':
                # Use pocketsphinx locally
                from wake import PocketsphinxWakeListener
                wake = PocketsphinxWakeListener(
                    self, self.get_audio_recorder(), profile, callback)
            elif system == 'nanomsg':
                # Use remote system via nanomsg
                from wake import NanomsgWakeListener
                wake = NanomsgWakeListener(
                    self, self.get_audio_recorder(), profile, callback)
            elif system == 'hermes':
                # Use remote system via MQTT
                from wake import HermesWakeListener
                wake = HermesWakeListener(
                    self, self.get_audio_recorder(), profile)
            elif system == 'dummy':
                # Does nothing
                wake = WakeListener(self, self.get_audio_recorder(), profile)

            self.wake_listeners[profile_name] = wake

        return wake

    def _handle_wake(self, profile_name: str, keyphrase: str, **kwargs):
        '''Listens for a voice command after wake word is detected, and forwards it to Home Assistant.'''
        logger.debug('%s %s' % (profile_name, keyphrase))
        profile = self.profiles[profile_name]

        audio_player = self.get_audio_player()
        audio_player.play_file(profile.get('sounds.wake', ''))

        # Listen for a command
        wav_data = self.get_command_listener().listen_for_command()

        # Beep
        audio_player.play_file(profile.get('sounds.recorded', ''))

        # speech -> intent
        intent = self.wav_to_intent(wav_data, profile_name)

        logger.debug(intent)

        # Handle intent
        no_hass = kwargs.get('no_hass', False)
        if not no_hass:
            self.get_intent_handler(profile_name).handle_intent(intent)

        # Listen for wake word again
        wake = self.get_wake_listener(profile_name)
        wake.start_listening()

    # -------------------------------------------------------------------------

    def get_intent_handler(self, profile_name: str) -> IntentHandler:
        '''Gets intent handler for a profile (e.g., send to Home Assistant).'''
        intent_handler = self.intent_handlers.get(profile_name)
        if intent_handler is None:
            from intent_handler import HomeAssistantIntentHandler
            profile = self.profiles[profile_name]
            intent_handler = HomeAssistantIntentHandler(profile)

            self.intent_handlers[profile_name] = intent_handler

        return intent_handler

    # -------------------------------------------------------------------------

    def get_sentence_generator(self, profile_name: str) -> SentenceGenerator:
        '''Gets sentence generator for training.'''
        sent_gen = self.sentence_generators.get(profile_name)
        if sent_gen is None:
            from train import JsgfSentenceGenerator
            profile = self.profiles[profile_name]
            sent_gen = JsgfSentenceGenerator(profile)

            self.sentence_generators[profile_name] = sent_gen

        return sent_gen

    # -------------------------------------------------------------------------

    def preload_profile(self, profile_name: str):
        '''Preloads all of a profile's stuff, like speech/intent recognizers'''
        self.get_speech_decoder(profile_name).preload()
        self.get_intent_recognizer(profile_name).preload()
        self.get_wake_listener(profile_name).preload()
        self.get_intent_handler(profile_name).preload()
        self.get_sentence_generator(profile_name).preload()
        self.get_speech_tuner(profile_name).preload()

    def reload_profile(self, profile_name: str):
        '''Clears caches for a profile and reloads its JSON from disk.
        Does preloading if this is the default profile.'''
        self.speech_decoders.pop(profile_name, None)
        self.intent_recognizers.pop(profile_name, None)
        self.wake_listeners.pop(profile_name, None)
        self.intent_handlers.pop(profile_name, None)
        self.sentence_generators.pop(profile_name, None)
        self.speech_tuners.pop(profile_name, None)
        self.profiles.pop(profile_name, None)

        for profiles_dir in self.profiles_dirs:
            if not os.path.exists(profiles_dir):
                continue

            for name in os.listdir(profiles_dir):
                profile_dir = os.path.join(profiles_dir, name)
                if (name == profile_name) and os.path.isdir(profile_dir):
                    logger.debug('Loading profile from %s' % profile_dir)
                    profile = Profile(name, self.profiles_dirs)
                    self.profiles[name] = profile
                    logger.info('Loaded profile %s' % name)

                    # Pre-load if default profile
                    if (profile_name == self.default_profile_name) \
                       and self.get_default('rhasspy.preload_profile'):
                        self.preload_profile(profile_name)

                    return

    # -------------------------------------------------------------------------

    def train_profile(self, profile_name: str):
        '''Re-trains speech/intent recognizers for a profile.'''
        profile = self.profiles[profile_name]

        # Generate sentences
        logger.info('Generating sentences')
        sent_gen = self.get_sentence_generator(profile_name)
        tagged_sentences = sent_gen.generate_sentences()

        # Write tagged sentences to Markdown file
        tagged_path = profile.write_path(
            profile.get('training.tagged_sentences'))

        with open(tagged_path, 'w') as tagged_file:
            for intent, intent_sents in tagged_sentences.items():
                print('# intent:%s' % intent, file=tagged_file)
                for sentence in intent_sents:
                    print('- %s' % sentence, file=tagged_file)
                print('', file=tagged_file)

        logger.debug('Wrote tagged sentences to %s' % tagged_path)

        # Train speech system
        logger.info('Training speech to text system')
        stt_system = profile.get('speech_to_text.system')
        assert stt_system in ['pocketsphinx'], 'Invalid speech to text system: %s' % stt_system
        word_pron = self.get_word_pronouncer(profile_name)

        if stt_system == 'pocketsphinx':
            from stt_train import PocketsphinxSpeechTrainer
            stt_trainer = PocketsphinxSpeechTrainer(profile, word_pron)

        sentences_by_intent = stt_trainer.train(tagged_sentences)

        # Train intent recognizer
        logger.info('Training intent recognizer')
        intent_system = profile.get('intent.system')
        assert intent_system in ['fuzzywuzzy', 'rasa', 'adapt'], 'Invalid intent system: %s' % intent_system

        if intent_system == 'fuzzywuzzy':
            from intent_train import FuzzyWuzzyIntentTrainer
            intent_trainer = FuzzyWuzzyIntentTrainer(profile)
        elif intent_system == 'rasa':
            from intent_train import RasaIntentTrainer
            intent_trainer = RasaIntentTrainer(profile)
        elif intent_system == 'adapt':
            from intent_train import AdaptIntentTrainer
            intent_trainer = AdaptIntentTrainer(profile)

        intent_trainer.train(tagged_sentences, sentences_by_intent)

    # -------------------------------------------------------------------------

    def wav_to_intent(self, wav_data: bytes, profile_name: str) -> Dict[str, Any]:
        '''Transcribes WAV data and does intent recognition for profile'''
        decoder = self.get_speech_decoder(profile_name)
        recognizer = self.get_intent_recognizer(profile_name)

        # WAV -> text
        start_time = time.time()
        text = decoder.transcribe_wav(wav_data)

        decode_time = time.time() - start_time
        self.get_mqtt_client().text_captured(text, seconds=decode_time)

        # text -> intent (JSON)
        intent = recognizer.recognize(text)

        intent_sec = time.time() - start_time
        intent['time_sec'] = intent_sec

        logger.debug(text)

        return intent

    # -------------------------------------------------------------------------

    def get_mqtt_client(self):
        return self.mqtt_client
