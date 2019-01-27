from typing import Dict, Any

from thespian.actors import ActorAddress

from .actor import RhasspyActor, ConfigureEvent, Configured
from .wake import ListenForWakeWord, WakeWordDetected
from .command_listener import ListenForCommand, VoiceCommand
from .audio_player import PlayWavFile
from .stt import TranscribeWav, WavTranscription
from .intent import RecognizeIntent, IntentRecognized
from .intent_handler import HandleIntent, IntentHandled
from .utils import buffer_to_wav

# -----------------------------------------------------------------------------

class GetMicrophones:
    pass

class TestMicrophones:
    pass

# -----------------------------------------------------------------------------

class DialogueManager(RhasspyActor):

    def to_started(self, from_state):
        self.intent_receiver = None
        self.load_actors()
        self.transition('loading')

    def in_loading(self, message, sender):
        if isinstance(message, Configured):
            self.wait_actors.remove(sender)
            if len(self.wait_actors) == 0:
                self._logger.info('Actors loaded')
                self.transition('ready')

    def to_ready(self, from_state):
        if self.profile.get('rhasspy.listen_on_start', False):
            self._logger.info('Automatically listening for wake word')
            self.transition('asleep')
            self.send(self.wake, ListenForWakeWord(self.myAddress))

    def in_ready(self, message, sender):
        if isinstance(message, ListenForWake):
            self._logger.info('Listening for wake word')
            self.transition('asleep')
        else:
            self.handle_any(message, sender)

    def in_asleep(self, message, sender):
        if isinstance(message, WakeWordDetected):
            self._logger.debug('Awake!')
            self.transition('awake')
        else:
            self.handle_any(message, sender)

    def to_awake(self, from_state):
        # Wake up beep
        wav_path = self.profile.get('sounds.wake', None)
        if wav_path is not None:
            self.send(self.player, PlayWavFile(wav_path))

        # Listen for a voice command
        self.send(self.command, ListenForCommand(self.myAddress))

    def in_awake(self, message, sender):
        if isinstance(message, VoiceCommand):
            # Recorded beep
            wav_path = self.profile.get('sounds.recorded', None)
            if wav_path is not None:
                self.send(self.player, PlayWavFile(wav_path))

            # speech -> text
            wav_data = buffer_to_wav(message.data)
            self.send(self.decoder, TranscribeWav(wav_data))
            self.transition('decoding')
        else:
            self.handle_any(message, sender)

    def in_decoding(self, message, sender):
        if isinstance(message, WavTranscription):
            # text -> intent
            self._logger.debug(message.text)
            self.send(self.recognizer, RecognizeIntent(message.text))
            self.transition('recognizing')
        else:
            self.handle_any(message, sender)

    def in_recognizing(self, message, sender):
        if isinstance(message, IntentRecognized):
            # Handle intent
            self._logger.debug(message.intent)
            self.send(self.handler, HandleIntent(message.intent))
            self.transition('handling')
        else:
            self.handle_any(message, sender)

    def in_handling(self, message, sender):
        if isinstance(message, IntentHandled):
            if self.intent_receiver is not None:
                self.send(self.intent_receiver, message.intent)

            self.transition('ready')
        else:
            self.handle_any(message, sender)

    # -------------------------------------------------------------------------

    def handle_any(self, message, sender):
        if isinstance(message, GetMicrophones):
            mics = self.recorder_class.get_microphones()
            self.send(sender, mics)
        elif isinstance(message, TestMicrophones):
            chunk_size = int(self.profile.get('microphone.%s.test_chunk_size', 1024))
            test_mics = self.recorder_class.test_microphones(chunk_size)
            self.send(sender, test_mics)
        elif isinstance(message, ListenForCommand):
            self.intent_receiver = message.receiver or sender
            self.transition('awake')
        else:
            self._logger.warn('Unhandled message: %s' % message)

    # -------------------------------------------------------------------------

    def load_actors(self):
        self.actors: Dict[str, ActorAddress] = {}

        # Microphone
        mic_system = self.profile.get('microphone.system', 'dummy')
        self.recorder_class = self._get_microphone_class(mic_system)
        self.recorder = self.createActor(self.recorder_class)
        self.actors['recorder'] = self.recorder

        # Audio player
        player_system = self.profile.get('sounds.system', 'dummy')
        self.player_class = self._get_sound_class(player_system)
        self.player = self.createActor(self.player_class)
        self.actors['player'] = self.player

        # Wake listener
        wake_system = self.profile.get('wake.system', 'dummy')
        self.wake_class = self._get_wake_class(wake_system)
        self.wake = self.createActor(self.wake_class)
        self.actors['wake'] = self.wake

        # Command listener
        command_system = self.profile.get('command.system', 'dummy')
        self.command_class = self._get_command_class(command_system)
        self.command = self.createActor(self.command_class)
        self.actors['command'] = self.command

        # Speech decoder
        decoder_system = self.profile.get('speech_to_text.system', 'dummy')
        self.decoder_class = self._get_decoder_class(decoder_system)
        self.decoder = self.createActor(self.decoder_class)
        self.actors['decoder'] = self.decoder

        # Intent recognizer
        recognizer_system = self.profile.get('intent.system', 'dummy')
        self.recognizer_class = self._get_recognizer_class(recognizer_system)
        self.recognizer = self.createActor(self.recognizer_class)
        self.actors['recognizer'] = self.recognizer

        # Intent handler
        from .intent_handler import HomeAssistantIntentHandler
        self.handler_class = HomeAssistantIntentHandler
        self.handler = self.createActor(self.handler_class)
        self.actors['handler'] = self.handler

        # Configure actors
        self.wait_actors = []
        for name, actor in self.actors.items():
            self.send(actor, ConfigureEvent(self.profile, **self.actors))
            self.wait_actors.append(actor)

        self._logger.debug('Actors created')

    # -------------------------------------------------------------------------

    def _get_sound_class(self, system):
        assert system in ['aplay', 'hermes', 'dummy'], \
            'Unknown sound system: %s' % system

        if system == 'aplay':
            from .audio_player import APlayAudioPlayer
            return APlayAudioPlayer
        # elif system == 'heremes':
        #     from audio_player import HeremesAudioPlayer
        #     self.audio_player = HeremesAudioPlayer(self)
        # elif system == 'dummy':
        #     self.audio_player = AudioPlayer(self)

    def _get_wake_class(self, system):
        assert system in ['dummy', 'pocketsphinx', 'nanomsg',
                          'hermes', 'snowboy', 'precise'], \
                          'Invalid wake system: %s' % system

        if system == 'pocketsphinx':
            # Use pocketsphinx locally
            from .wake import PocketsphinxWakeListener
            return PocketsphinxWakeListener
        elif system == 'nanomsg':
            # Use remote system via nanomsg
            from .wake import NanomsgWakeListener
            return NanomsgWakeListener
        elif system == 'hermes':
            # Use remote system via MQTT
            from .wake import HermesWakeListener
            return HermesWakeListener
        elif system == 'snowboy':
            # Use snowboy locally
            from .wake import SnowboyWakeListener
            return SnowboyWakeListener
        elif system == 'precise':
            # Use Mycroft Precise locally
            from .wake import PreciseWakeListener
            return PreciseWakeListener
        elif system == 'dummy':
            # Does nothing
            return WakeListener

    def _get_microphone_class(self, system: str):
        assert system in ['arecord', 'pyaudio', 'hermes', 'dummy'], \
            'Unknown microphone system: %s' % system

        if system == 'arecord':
            from audio_recorder import ARecordAudioRecorder
            return ARecordAudioRecorder
        elif system == 'pyaudio':
            from .audio_recorder import PyAudioRecorder
            return PyAudioRecorder
        elif system == 'hermes':
            from audio_recorder import HermesAudioRecorder
            return HermesAudioRecorder
        else:
            from audio_recorder import AudioRecorder
            return AudioRecorder

    def _get_command_class(self, system: str):
        from .command_listener import WebrtcvadCommandListener
        return WebrtcvadCommandListener

    def _get_decoder_class(self, system: str):
        assert system in ['dummy', 'pocketsphinx', 'remote'], \
            'Invalid speech to text system: %s' % system

        if system == 'pocketsphinx':
            from .stt import PocketsphinxDecoder
            return PocketsphinxDecoder
        elif system == 'remote':
            from .stt import RemoteDecoder
            return RemoteDecoder
        else:
            # TODO
            pass

    def _get_recognizer_class(self, system: str):
        assert system in ['dummy', 'fuzzywuzzy', 'adapt', 'rasa', 'remote'], \
            'Invalid intent system: %s' % system

        if system == 'fuzzywuzzy':
            # Use fuzzy string matching locally
            from .intent import FuzzyWuzzyRecognizer
            return FuzzyWuzzyRecognizer
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
