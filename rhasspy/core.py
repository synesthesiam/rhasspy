import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import logging
import time
from typing import List, Dict, Optional

import pydash
# from thespian.actors import Actor, ActorAddress

from profiles import Profile
from audio_player import AudioPlayer, APlayAudioPlayer
from audio_recorder import AudioRecorder
from command_listener import CommandListener
from stt import SpeechDecoder, PocketsphinxDecoder, RemoteDecoder
from intent import IntentRecognizer, FuzzyWuzzyRecognizer
from pronounce import WordPronounce, PhonetisaurusPronounce
from wake import WakeListener, PocketsphinxWakeListener
from intent_handler import IntentHandler, HomeAssistantIntentHandler

# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class Rhasspy:
    def __init__(self,
                 profiles_dirs: List[str],
                 default_profile_name: Optional[str] = None):

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

        self.default_profile = self.profiles[self.default_profile_name]

    # -------------------------------------------------------------------------

    def get_default(self, path: str, default=None):
        return pydash.get(self.defaults_json, path, default)

    # -------------------------------------------------------------------------

    def get_audio_player(self) -> AudioPlayer:
        if self.audio_player is None:
            device = self.get_default('sounds.aplay.device')
            self.audio_player = APlayAudioPlayer(device)

        return self.audio_player

    # -------------------------------------------------------------------------

    def get_audio_recorder(self) -> AudioRecorder:
        if self.audio_recorder is None:
            system = self.default_profile.get('microphone.system')
            assert system in ['arecord', 'pyaudio'], 'Unknown microphone system: %s' % system
            if system == 'arecord':
                from .audio_recorder import ARecordAudioRecorder
                device = self.get_default('microphone.arecord.device')
                self.audio_recorder = ARecordAudioRecorder(device)
                logger.debug('Using arecord for microphone')
            elif system == 'pyaudio':
                from .audio_recorder import PyAudioRecorder
                device = self.get_default('microphone.pyaudio.device')
                self.audio_recorder = PyAudioRecorder(device)
                logger.debug('Using PyAudio for microphone')

        return self.audio_recorder

    # -------------------------------------------------------------------------

    def get_speech_decoder(self, profile_name: str) -> SpeechDecoder:
        decoder = self.speech_decoders.get(profile_name)
        if decoder is None:
            profile = self.profiles[profile_name]
            system = profile.get('speech_to_text.system')
            assert system in ['dummy', 'pocketsphinx', 'remote'], 'Invalid speech to text system: %s' % system
            if system == 'pocketsphinx':
                decoder = PocketsphinxDecoder(profile)
            elif system == 'remote':
                decoder = RemoteDecoder(profile)
            elif system == 'dummy':
                # Does nothing
                decoder = SpeechDecoder(profile)

            # Cache decoder
            self.speech_decoders[profile_name] = decoder

        return decoder

    # -------------------------------------------------------------------------

    def get_intent_recognizer(self, profile_name: str) -> IntentRecognizer:
        recognizer = self.intent_recognizers.get(profile_name)
        if recognizer is None:
            profile = self.profiles[profile_name]
            system = profile.get('intent.system')
            assert system in ['dummy', 'fuzzywuzzy', 'rasa', 'remote'], 'Invalid intent system: %s' % system
            if system == 'fuzzywuzzy':
                recognizer = FuzzyWuzzyRecognizer(profile)
            elif system == 'rasa':
                # TODO
                pass
            elif system == 'remote':
                # TODO
                pass
            elif system == 'dummy':
                # Does nothing
                recognizer = IntentRecognizer(profile)

            # Cache recognizer
            self.intent_recognizers[profile_name] = recognizer

        return recognizer

    # -------------------------------------------------------------------------

    def get_word_pronouncer(self, profile_name: str) -> WordPronounce:
        word_pron = self.word_pronouncers.get(profile_name)
        if word_pron is None:
            profile = self.profiles[profile_name]
            word_pron = PhonetisaurusPronounce(profile)
            self.word_pronouncers[profile_name] = word_pron

        return self.word_pronouncers[profile_name]

    # -------------------------------------------------------------------------

    def get_command_listener(self):
        if self.command_listener is None:
            self.command_listener = CommandListener(self.get_audio_recorder(), 16000)

        return self.command_listener

    # -------------------------------------------------------------------------

    def get_wake_listener(self, profile_name: str) -> WakeListener:
        wake = self.wake_listeners.get(profile_name)
        if wake is None:
            profile = self.profiles[profile_name]
            system = profile.get('wake.system')
            assert system in ['dummy', 'pocketsphinx'], 'Invalid wake system: %s' % system
            if system == 'pocketsphinx':
                wake = PocketsphinxWakeListener(
                    self.get_audio_recorder(), profile, self._handle_wake)
            elif system == 'dummy':
                # Does nothing
                wake = WakeListener(self.get_audio_recorder(), profile)

            self.wake_listeners[profile_name] = wake

        return wake

    def _handle_wake(self, profile_name: str, keyphrase: str, **kwargs):
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

    # -------------------------------------------------------------------------

    def get_intent_handler(self, profile_name: str) -> IntentHandler:
        intent_handler = self.intent_handlers.get(profile_name)
        if intent_handler is None:
            profile = self.profiles[profile_name]
            intent_handler = HomeAssistantIntentHandler(profile)

            self.intent_handlers[profile_name] = intent_handler

        return intent_handler

    # -------------------------------------------------------------------------

    def preload_profile(self, profile_name: str):
        self.get_speech_decoder(profile_name).preload()
        self.get_intent_recognizer(profile_name).preload()
        self.get_wake_listener(profile_name).preload()
        self.get_intent_handler(profile_name).preload()

    def reload_profile(self, profile_name: str):
        self.speech_decoders.pop(profile_name, None)
        self.intent_recognizers.pop(profile_name, None)
        self.wake_listeners.pop(profile_name, None)
        self.intent_handlers.pop(profile_name, None)
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
        from generate_jsgf import get_tagged_sentences
        profile = self.profiles[profile_name]

        # Generate sentences
        logger.info('Generating sentences')
        tagged_sentences = get_tagged_sentences(profile)

        # Train speech system
        logger.info('Training speech to text system')
        stt_system = profile.get('speech_to_text.system')
        assert stt_system in ['pocketsphinx'], 'Invalid speech to text system: %s' % stt_system

        if stt_system == 'pocketsphinx':
            from stt_train import PocketsphinxSpeechTrainer
            stt_trainer = PocketsphinxSpeechTrainer(self, profile)

        sentences_by_intent = stt_trainer.train(tagged_sentences)

        # Train intent recognizer
        logger.info('Training intent recognizer')
        intent_system = profile.get('intent.system')
        assert intent_system in ['fuzzywuzzy'], 'Invalid intent system: %s' % intent_system

        if intent_system == 'fuzzywuzzy':
            from intent_train import FuzzyWuzzyIntentTrainer
            intent_trainer = FuzzyWuzzyIntentTrainer(profile)

        intent_trainer.train(tagged_sentences, sentences_by_intent)

    # -------------------------------------------------------------------------

    def wav_to_intent(self, wav_data: bytes, profile_name: str):
        '''Transcribes WAV data and does intent recognition for profile'''
        decoder = self.get_speech_decoder(profile_name)
        recognizer = self.get_intent_recognizer(profile_name)

        # WAV -> text
        start_time = time.time()
        text = decoder.transcribe_wav(wav_data)

        # text -> intent (JSON)
        intent = recognizer.recognize(text)

        intent_sec = time.time() - start_time
        intent['time_sec'] = intent_sec

        logger.debug(text)

        return intent


# -----------------------------------------------------------------------------

# class StartRhasspy:
#     def __init__(self,
#                  profiles_dirs: List[str],
#                  default_profile_name: Optional[str] = None):

#         self.profiles_dirs = profiles_dirs
#         self.default_profile_name = default_profile_name

# class ProfileEvent:
#     def __init__(self, name: str, event):
#         self.name = name
#         self.event = event

# -----------------------------------------------------------------------------

# class RhasspyActor(Actor):

#     def __init__(self):
#         self.default_profile_name: Optional[str] = None
#         self.profiles_dirs: List[str] = ['profiles']
#         self.profiles: Dict[str, Profile] = {}
#         self.profile_actors: Dict[str, ActorAddress] = {}

#     # -------------------------------------------------------------------------

#     def receiveMessage(self, message, sender):
#         try:
#             if isinstance(message, StartRhasspy):
#                 self.profiles_dirs = message.profiles_dirs
#                 self.default_profile_name = message.default_profile_name
#                 self.load_settings()
#                 self.load_profiles()

#         except Exception as ex:
#             logger.exception('receiveMessage')

#     # -------------------------------------------------------------------------

#     def load_settings(self):
#         logger.debug('Profiles dirs: %s' % self.profiles_dirs)

#         # Load default settings
#         self.defaults_json = Profile.load_defaults(self.profiles_dirs)

#         # Load default profile
#         if self.default_profile_name is None:
#             self.default_profile_name = \
#                 defaults_json['rhasspy'].get('default_profile', 'en')

#         self.default_profile = self.load_profile(self.default_profile_name)

#     # -------------------------------------------------------------------------

#     def load_profiles(self):
#         for profile_dir in self.profiles_dirs:
#             profile_name = os.path.split(profile_dir)[1]
#             profile = Profile(profile_name, self.profiles_dir)
#             self.profiles[profile_name] = profile

#             # Create actor
#             actor = self.createActor(ProfileActor)
#             self.profile_actors[profile_name] = actor
#             self.send(actor, profile)

    # # -------------------------------------------------------------------------

    # def load_default(self):
    #     if self.default_profile.rhasspy.get('preload_profile', False):
    #         try:
    #             # Load speech to text decoder
    #             decoder = maybe_load_decoder(default_profile)
    #             self.stt_decoders[default_profile.name] = decoder
    #         except Exception as e:
    #             logger.error('Failed to pre-load profile')

    #     if self.default_profile.rhasspy.get('listen_on_start', False):
    #         # Start listening for wake word
    #         listen_for_wake(default_profile)

    # def listen_for_wake(profile, no_hass=False, device_index=None):
    #     global listen_for_wake_func
    #     system = profile.wake.get('system', None)

    #     if system == 'pocketsphinx':
    #         global decoders
    #         listen_for_wake_func = wake.pocketsphinx_wake(
    #             profile, wake_decoders, functools.partial(wake_word_detected, profile, no_hass),
    #             device_index=device_index)

    #         # Start listening
    #         listen_for_wake_func()

    #         return profile.wake
    #     else:
    #         assert False, 'Unknown wake word system: %s' % system

    # def wake_word_detected(profile, no_hass):
    #     global listen_for_wake_func

    #     # Listen until silence
    #     listen_for_command(profile, no_hass)

    #     # Start listening again
    #     listen_for_wake_func()

    # def listen_for_command(profile, no_hass):
    #     utils.play_wav(profile.sounds.get('wake', ''))

    #     try:
    #         # Listen until silence
    #         from command_listener import CommandListener
    #         listener = CommandListener()
    #         recorded_data = listener.listen()

    #         utils.play_wav(profile.sounds.get('recorded', ''))

    #         # Convert to WAV
    #         with io.BytesIO() as wav_data:
    #             with wave.open(wav_data, mode='wb') as wav_file:
    #                 wav_file.setframerate(listener.sample_rate)
    #                 wav_file.setsampwidth(listener.sample_width)
    #                 wav_file.setnchannels(listener.channels)
    #                 wav_file.writeframesraw(recorded_data)

    #             wav_data.seek(0)

    #             # Get intent/send to Home Assistant
    #             intent = speech_to_intent(profile, wav_data.read(), no_hass)

    #             if not no_hass:
    #                 # Send intent to Home Assistant
    #                 utils.send_intent(profile.home_assistant, intent)

    #             return intent
    #     except:
    #         logger.exception('Error processing command')

    #     return {}

    # # Cached rasaNLU projects
    # # profile -> project
    # intent_projects = {}

    # # Cached fuzzywuzzy examples
    # # profile -> examples
    # intent_examples = {}

    # def get_intent(profile, text):
    #     system = profile.intent.get('system', 'fuzzywuzzy')

    #     if system == 'rasa':
    #         rasa_config = profile.intent[system]

    #         # Use rasaNLU
    #         global intent_projects

    #         project = intent_projects.get(profile.name, None)
    #         if project is None:
    #             import rasa_nlu
    #             from rasa_nlu.project import Project
    #             project_dir = profile.read_path(rasa_config['project_dir'])
    #             project_name = rasa_config['project_name']

    #             project = Project(project=project_name,
    #                               project_dir=project_dir)

    #             intent_projects[profile.name] = project

    #         return project.parse(text)
    #     elif system == 'remote':
    #         remote_url = profile.intent[system]['url']
    #         headers = { 'Content-Type': 'text/plain' }

    #         # Pass profile name through
    #         params = { 'profile': profile.name, 'nohass': True }
    #         response = requests.post(remote_url, headers=headers,
    #                                 data=text, params=params)

    #         response.raise_for_status()

    #         # Return intent directly
    #         return response.json()
    #     else:
    #         fuzzy_config = profile.intent[system]

    #         # Use fuzzywuzzy
    #         global intent_examples

    #         if not profile.name in intent_examples:
    #             examples_path = profile.read_path(fuzzy_config['examples_json'])
    #             with open(examples_path, 'r') as examples_file:
    #                 intent_examples[profile.name] = json.load(examples_file)

    #         text, intent_name, slots = best_intent(intent_examples[profile.name], text)

    #         # Try to match RasaNLU format for future compatibility
    #         intent = {
    #             'text': text,
    #             'intent': {
    #                 'name': intent_name,
    #             },
    #             'entities': [
    #                 { 'entity': name, 'value': values[0] } for name, values in slots.items()
    #             ]
    #         }

    #         return intent

    # def speech_to_intent(profile, wav_data, no_hass=False):
    #     global decoders

    #     # speech to text
    #     decoder = transcribe_wav(profile, wav_data, decoders.get(profile.name))
    #     decoders[profile.name] = decoder

    #     # text to intent
    #     if decoder.hyp() is not None:
    #         text = decoder.hyp().hypstr
    #         intent = get_intent(profile, text)
    #         logger.debug(intent)

    #         if not no_hass:
    #             # Send intent to Home Assistant
    #             utils.send_intent(profile.home_assistant, intent)

    #         return intent

    #     return None
