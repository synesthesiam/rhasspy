import json
from typing import Dict, Any

from thespian.actors import ActorAddress, ActorExitRequest

from .actor import RhasspyActor, ConfigureEvent, Configured
from .wake import ListenForWakeWord, StopListeningForWakeWord, WakeWordDetected
from .command_listener import ListenForCommand, VoiceCommand
from .audio_recorder import StartRecordingToBuffer, StopRecordingToBuffer
from .audio_player import PlayWavFile, PlayWavData
from .stt import TranscribeWav, WavTranscription
from .stt_train import TrainSpeech, SpeechTrainingComplete, SpeechTrainingFailed
from .intent import RecognizeIntent, IntentRecognized
from .intent_train import TrainIntent, IntentTrainingComplete
from .intent_handler import HandleIntent, IntentHandled
from .train import GenerateSentences, SentencesGenerated
from .pronounce import GetWordPhonemes, SpeakWord, GetWordPronunciations
from .mqtt import MqttPublish
from .utils import buffer_to_wav

# -----------------------------------------------------------------------------

class GetMicrophones:
    def __init__(self, system=None):
        self.system = system

class TestMicrophones:
    def __init__(self, system=None):
        self.system = system

class TrainProfile:
    def __init__(self, receiver=None):
        self.receiver = receiver

class ProfileTrainingFailed:
    pass

class ProfileTrainingComplete:
    pass

class Ready:
    pass

# -----------------------------------------------------------------------------

class DialogueManager(RhasspyActor):
    '''Manages the overall state of Rhasspy.'''

    def to_started(self, from_state):
        self.site_id = self.profile.get('mqtt.site_id')
        self.preload = self.config.get('preload', False)
        self.send_ready = self.config.get('ready', False)
        self.wake_receiver = None
        self.intent_receiver = None
        self.training_receiver = None
        self.handle = True

        self.load_actors()
        self.transition('loading')

    def in_loading(self, message, sender):
        if isinstance(message, Configured):
            self.wait_actors.remove(sender)
            if len(self.wait_actors) == 0:
                self._logger.info('Actors loaded')
                self.transition('ready')

                # Inform all actors that we're ready
                for actor in self.actors.values():
                    self.send(actor, Ready())

                # Inform parent actor that we're ready
                if self.send_ready:
                    self.send(self._parent, Ready())

    # -------------------------------------------------------------------------
    # Wake
    # -------------------------------------------------------------------------

    def to_ready(self, from_state):
        if self.profile.get('rhasspy.listen_on_start', False):
            self._logger.info('Automatically listening for wake word')
            self.transition('asleep')
            self.send(self.wake, ListenForWakeWord())

    def in_ready(self, message, sender):
        if isinstance(message, ListenForWakeWord):
            self._logger.info('Listening for wake word')
            self.wake_receiver = message.receiver or sender
            self.send(self.wake, ListenForWakeWord())
            self.transition('asleep')
        else:
            self.handle_any(message, sender)

    def in_asleep(self, message, sender):
        if isinstance(message, WakeWordDetected):
            self._logger.debug('Awake!')
            self.transition('awake')
            if self.wake_receiver is not None:
                self.send(self.wake_receiver, message)
        else:
            self.handle_any(message, sender)

    def to_awake(self, from_state):
        self.send(self.wake, StopListeningForWakeWord())

        # Wake up beep
        wav_path = self.profile.get('sounds.wake', None)
        if wav_path is not None:
            self.send(self.player, PlayWavFile(wav_path))

        # Listen for a voice command
        self.send(self.command, ListenForCommand(self.myAddress, handle=self.handle))

    def in_awake(self, message, sender):
        if isinstance(message, VoiceCommand):
            # Recorded beep
            wav_path = self.profile.get('sounds.recorded', None)
            if wav_path is not None:
                self.send(self.player, PlayWavFile(wav_path))

            # speech -> text
            wav_data = buffer_to_wav(message.data)
            self.send(self.decoder, TranscribeWav(wav_data, handle=message.handle))
            self.transition('decoding')
        else:
            self.handle_any(message, sender)

    # -------------------------------------------------------------------------
    # Recognition
    # -------------------------------------------------------------------------

    def in_decoding(self, message, sender):
        if isinstance(message, WavTranscription):
            # text -> intent
            self._logger.debug(message.text)

            # Send to MQTT
            payload = json.dumps({
                'siteId': self.site_id,
                'text': message.text,
                'likelihood': 1,
                'seconds': 0
            }).encode()

            self.send(self.mqtt, MqttPublish('hermes/asr/textCaptured', payload))

            # Pass to intent recognizer
            self.send(self.recognizer, RecognizeIntent(message.text, handle=message.handle))
            self.transition('recognizing')
        else:
            self.handle_any(message, sender)

    def in_recognizing(self, message, sender):
        if isinstance(message, IntentRecognized):
            # Handle intent
            self._logger.debug(message.intent)
            if message.handle:
                self.send(self.handler, HandleIntent(message.intent))
                self.transition('handling')
            else:
                self._logger.debug('Not actually handling intent')
                if self.intent_receiver is not None:
                    self.send(self.intent_receiver, message.intent)
                self.transition('ready')
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
    # Training
    # -------------------------------------------------------------------------

    def in_training_sentences(self, message, sender):
        if isinstance(message, SentencesGenerated):
            tagged_sentences = message.tagged_sentences

            # Write tagged sentences to Markdown file
            tagged_path = self.profile.write_path(
                self.profile.get('training.tagged_sentences'))

            with open(tagged_path, 'w') as tagged_file:
                for intent, intent_sents in tagged_sentences.items():
                    print('# intent:%s' % intent, file=tagged_file)
                    for sentence in intent_sents:
                        print('- %s' % sentence, file=tagged_file)
                    print('', file=tagged_file)

            self._logger.debug('Wrote tagged sentences to %s' % tagged_path)

            # Train speech system
            self.transition('training_speech')
            self.send(self.speech_trainer,
                      TrainSpeech(message.tagged_sentences))

    def in_training_speech(self, message, sender):
        if isinstance(message, SpeechTrainingComplete):
            self.transition('training_intent')
            self.send(self.intent_trainer,
                      TrainIntent(message.tagged_sentences,
                                  message.sentences_by_intent))
        elif isinstance(message, SpeechTrainingFailed):
            self.transition('ready')
            self.send(self.training_receiver, ProfileTrainingFailed())

    def in_training_intent(self, message, sender):
        if isinstance(message, IntentTrainingComplete):
            self._logger.debug('Reloading actors')

            # Wake listener
            self.send(self.wake, ActorExitRequest())
            self.wake = self.createActor(self.wake_class)
            self.actors['wake'] = self.wake

            # Speech decoder
            self.send(self.decoder, ActorExitRequest())
            self.decoder = self.createActor(self.decoder_class)
            self.actors['decoder'] = self.decoder

            # Intent recognizer
            self.send(self.recognizer, ActorExitRequest())
            self.recognizer = self.createActor(self.recognizer_class)
            self.actors['recognizer'] = self.recognizer

            # Configure actors
            self.wait_actors = []
            for actor in [self.wake, self.decoder, self.recognizer]:
                self.send(actor, ConfigureEvent(self.profile,
                                                preload=self.preload,
                                                **self.actors))
                self.wait_actors.append(actor)

            self._logger.info('Training complete')
            self.transition('training_loading')

    def in_training_loading(self, message, sender):
        if isinstance(message, Configured):
            self.wait_actors.remove(sender)
            if len(self.wait_actors) == 0:
                self._logger.info('Actors reloaded')
                self.transition('ready')
                self.send(self.training_receiver,
                          ProfileTrainingComplete())

    # -------------------------------------------------------------------------

    def handle_any(self, message, sender):
        if isinstance(message, GetMicrophones):
            # Get all microphones
            recorder_class = self.recorder_class
            if message.system is not None:
                recorder_class = self._get_microphone_class(message.system)

            mics = recorder_class.get_microphones()
            self.send(sender, mics)
        elif isinstance(message, TestMicrophones):
            # Get working microphones
            recorder_system = self.profile.get('microphone.system', 'pyaudio')
            if message.system is not None:
                recorder_system = message.system

            recorder_class = self._get_microphone_class(recorder_system)
            test_path = 'microphone.%s.test_chunk_size' % recorder_system
            chunk_size = int(self.profile.get(test_path, 1024))

            test_mics = recorder_class.test_microphones(chunk_size)
            self.send(sender, test_mics)
        elif isinstance(message, ListenForCommand):
            # Force voice command
            self.intent_receiver = message.receiver or sender
            self.transition('awake')
        elif isinstance(message, TranscribeWav):
            # speech -> text
            self.send(self.decoder,
                      TranscribeWav(message.wav_data, sender, handle=message.handle))
        elif isinstance(message, RecognizeIntent):
            # text -> intent
            self.send(self.recognizer, RecognizeIntent(message.text, sender, message.handle))
        elif isinstance(message, HandleIntent):
            # intent -> action
            self.send(self.handler, HandleIntent(message.intent, sender))
        elif isinstance(message, GetWordPhonemes):
            # eSpeak -> CMU
            self.send(self.word_pronouncer,
                      GetWordPhonemes(message.word, receiver=sender))
        elif isinstance(message, SpeakWord):
            # eSpeak -> WAV
            self.send(self.word_pronouncer,
                      SpeakWord(message.word, receiver=sender))
        elif isinstance(message, GetWordPronunciations):
            # word -> [CMU]
            self.send(self.word_pronouncer,
                      GetWordPronunciations(message.word,
                                            n=message.n,
                                            receiver=sender))
        elif isinstance(message, PlayWavData):
            # Forward to audio player
            self.send(self.player, message)
        elif isinstance(message, TrainProfile):
            # Training
            self.send(self.wake, StopListeningForWakeWord())
            self.training_receiver = message.receiver or sender
            self.transition('training_sentences')
            self.send(self.sentence_generator, GenerateSentences())
        elif isinstance(message, StartRecordingToBuffer):
            # Record WAV
            self.send(self.recorder, message)
        elif isinstance(message, StopRecordingToBuffer):
            # Stop recording WAV
            self.send(self.recorder,
                      StopRecordingToBuffer(message.buffer_name,
                                            message.receiver or sender))
        elif isinstance(message, MqttPublish):
            # Forward directly
            self.send(self.mqtt, message)
        else:
            self._logger.warn('Unhandled message: %s' % message)

    # -------------------------------------------------------------------------
    # Utilities
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

        # Sentence generator
        from .train import JsgfSentenceGenerator
        self.sentence_generator_class = JsgfSentenceGenerator
        self.sentence_generator = self.createActor(self.sentence_generator_class)
        self.actors['sentence_generator'] = self.sentence_generator

        # Speech trainer
        from .stt_train import PocketsphinxSpeechTrainer
        self.speech_trainer_class = PocketsphinxSpeechTrainer
        self.speech_trainer = self.createActor(self.speech_trainer_class)
        self.actors['speech_trainer'] = self.speech_trainer

        # Intent trainer
        self.intent_trainer_class = self._get_intent_trainer_class(recognizer_system)
        self.intent_trainer = self.createActor(self.intent_trainer_class)
        self.actors['intent_trainer'] = self.intent_trainer

        # Word pronouncer
        from .pronounce import PhonetisaurusPronounce
        self.word_pronouncer_class = PhonetisaurusPronounce
        self.word_pronouncer = self.createActor(self.word_pronouncer_class)
        self.actors['word_pronouncer'] = self.word_pronouncer

        # MQTT client
        from .mqtt import HermesMqtt
        self.mqtt_class = HermesMqtt
        self.mqtt = self.createActor(self.mqtt_class)
        self.actors['mqtt'] = self.mqtt

        # Configure actors
        self.wait_actors = []
        for name, actor in self.actors.items():
            self.send(actor, ConfigureEvent(self.profile,
                                            preload=self.preload,
                                            **self.actors))
            self.wait_actors.append(actor)

        self._logger.debug('Actors created')

    # -------------------------------------------------------------------------

    def _get_sound_class(self, system):
        assert system in ['aplay', 'hermes', 'dummy'], \
            'Unknown sound system: %s' % system

        if system == 'aplay':
            from .audio_player import APlayAudioPlayer
            return APlayAudioPlayer
        elif system == 'heremes':
            from .audio_player import HermesAudioPlayer
            return HermesAudioPlayer
        elif system == 'dummy':
            from .audio_player import DummyAudioPlayer
            return DummyAudioPlayer

    def _get_wake_class(self, system):
        assert system in ['dummy', 'pocketsphinx', 'hermes',
                          'snowboy', 'precise'], \
                          'Invalid wake system: %s' % system

        if system == 'pocketsphinx':
            # Use pocketsphinx locally
            from .wake import PocketsphinxWakeListener
            return PocketsphinxWakeListener
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
            from .wake import DummyWakeListener
            return DummyWakeListener

    def _get_microphone_class(self, system: str):
        assert system in ['arecord', 'pyaudio', 'dummy', 'hermes'], \
            'Unknown microphone system: %s' % system

        if system == 'arecord':
            from .audio_recorder import ARecordAudioRecorder
            return ARecordAudioRecorder
        elif system == 'pyaudio':
            from .audio_recorder import PyAudioRecorder
            return PyAudioRecorder
        elif system == 'hermes':
            from .audio_recorder import HermesAudioRecorder
            return HermesAudioRecorder
        else:
            from .audio_recorder import DummyAudioRecorder
            return DummyAudioRecorder

    def _get_command_class(self, system: str):
        assert system in ['dummy', 'webrtcvad'], \
            'Unknown voice command system: %s' % system

        if system == 'webrtcvad':
            from .command_listener import WebrtcvadCommandListener
            return WebrtcvadCommandListener
        else:
            from .command_listener import DummyCommandListener
            return DummyCommandListener

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
            from .stt import DummyDecoder
            return DummyDecoder

    def _get_recognizer_class(self, system: str):
        assert system in ['dummy', 'fuzzywuzzy', 'adapt', 'rasa', 'remote'], \
            'Invalid intent system: %s' % system

        if system == 'fuzzywuzzy':
            # Use fuzzy string matching locally
            from .intent import FuzzyWuzzyRecognizer
            return FuzzyWuzzyRecognizer
        elif system == 'adapt':
            # Use Mycroft Adapt locally
            from .intent import AdaptIntentRecognizer
            return AdaptIntentRecognizer
        elif system == 'rasa':
            # Use rasaNLU remotely
            from .intent import RasaIntentRecognizer
            return RasaIntentRecognizer
        elif system == 'remote':
            # Use remote rhasspy server
            from .intent import RemoteRecognizer
            return RemoteRecognizer
        else:
            # Does nothing
            from .intent import DummyIntentRecognizer
            return DummyIntentRecognizer

    def _get_intent_trainer_class(self, system: str):
        assert system in ['dummy', 'fuzzywuzzy', 'adapt', 'rasa'], \
            'Invalid intent system: %s' % system

        if system == 'fuzzywuzzy':
            # Use fuzzy string matching locally
            from .intent_train import FuzzyWuzzyIntentTrainer
            return FuzzyWuzzyIntentTrainer
        elif system == 'adapt':
            # Use Mycroft Adapt locally
            from .intent_train import AdaptIntentTrainer
            return AdaptIntentTrainer
        elif system == 'rasa':
            # Use rasaNLU remotely
            from .intent_train import RasaIntentTrainer
            return RasaIntentRecognizer
        else:
            # Does nothing
            from .intent_train import DummyIntentTrainer
            return DummyIntentTrainer
