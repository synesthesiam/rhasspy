import json
from datetime import timedelta
from typing import Dict, Any, Optional, List, Type

from thespian.actors import ActorAddress, ActorExitRequest, WakeupMessage

from .actor import RhasspyActor, ConfigureEvent, Configured, StateTransition
from .wake import ListenForWakeWord, StopListeningForWakeWord, WakeWordDetected, WakeWordNotDetected
from .command_listener import ListenForCommand, VoiceCommand
from .audio_recorder import StartRecordingToBuffer, StopRecordingToBuffer, AudioData
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
    def __init__(self, system:Optional[str]=None) -> None:
        self.system = system

class TestMicrophones:
    def __init__(self, system:Optional[str]=None) -> None:
        self.system = system

class TrainProfile:
    def __init__(self, receiver:Optional[ActorAddress]=None) -> None:
        self.receiver = receiver

class ProfileTrainingFailed:
    pass

class ProfileTrainingComplete:
    pass

class Ready:
    def __init__(self, timeout:bool=False) -> None:
        self.timeout = timeout

class GetVoiceCommand:
    def __init__(self,
                 receiver:Optional[ActorAddress]=None,
                 timeout:Optional[float]=None):
        self.receiver = receiver
        self.timeout = timeout

class GetActorStates:
    pass

# -----------------------------------------------------------------------------

class DialogueManager(RhasspyActor):
    '''Manages the overall state of Rhasspy.'''

    def to_started(self, from_state:str) -> None:
        self.site_id:str = self.profile.get('mqtt.site_id', 'default')
        self.preload:bool = self.config.get('preload', False)
        self.timeout_sec:Optional[float] = self.config.get('load_timeout_sec', None)
        self.send_ready:bool = self.config.get('ready', False)
        self.wake_receiver:Optional[ActorAddress] = None
        self.intent_receiver:Optional[ActorAddress] = None
        self.training_receiver:Optional[ActorAddress] = None
        self.handle:bool = True
        self.actors: Dict[str, ActorAddress] = {}
        self.actor_states:Dict[str, str] = {}

        self.transition('loading_mqtt')

    def to_loading_mqtt(self, from_state:str) -> None:
        self._logger.debug('Loading MQTT first')

        # MQTT client *first*
        from .mqtt import HermesMqtt
        self.mqtt_class = HermesMqtt
        self.mqtt:ActorAddress = self.createActor(self.mqtt_class)
        self.actors['mqtt'] = self.mqtt

        self.send(self.mqtt, ConfigureEvent(self.profile,
                                            preload=self.preload,
                                            **self.actors))

        if self.timeout_sec is not None:
            self._logger.debug(f'Loading...will time out after {self.timeout_sec} second(s)')
            self.wakeupAfter(timedelta(seconds=self.timeout_sec))

    def in_loading_mqtt(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, Configured) and (sender == self.mqtt):
            self.transition('loading')
        elif isinstance(message, WakeupMessage):
            self._logger.warning('MQTT actor did not load! Trying to keep going...')
            self.transition('loading')

    def to_loading(self, from_state:str) -> None:
        # Load all of the other actors
        self.load_actors()

    def in_loading(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, Configured):
            # Remove sender
            sender_name = None
            for name, actor in self.wait_actors.items():
                if actor == sender:
                    sender_name = name
                    break

            if sender_name is not None:
                del self.wait_actors[sender_name]
                self._logger.debug(f'{sender_name} started')

            if len(self.wait_actors) == 0:
                self._logger.info('Actors loaded')
                self.transition('ready')

                # Inform all actors that we're ready
                for actor in self.actors.values():
                    self.send(actor, Ready())

                # Inform parent actor that we're ready
                if self.send_ready:
                    self.send(self._parent, Ready())
        elif isinstance(message, WakeupMessage):
            self._logger.warning('Actor timeout! Loading anyway...')
            self.transition('ready')

            # Inform all actors that we're ready
            for actor in self.actors.values():
                self.send(actor, Ready(timeout=True))

            # Inform parent actor that we're ready
            if self.send_ready:
                self.send(self._parent, Ready(timeout=True))

        elif isinstance(message, StateTransition):
            self.handle_transition(message, sender)

    # -------------------------------------------------------------------------
    # Wake
    # -------------------------------------------------------------------------

    def to_ready(self, from_state:str) -> None:
        if self.profile.get('rhasspy.listen_on_start', False):
            self._logger.info('Automatically listening for wake word')
            self.transition('asleep')
            self.send(self.wake, ListenForWakeWord())

    def in_ready(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, ListenForWakeWord):
            self._logger.info('Listening for wake word')
            self.wake_receiver = message.receiver or sender
            self.send(self.wake, ListenForWakeWord())
            self.transition('asleep')
        else:
            self.handle_any(message, sender)

    def in_asleep(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, WakeWordDetected):
            self._logger.debug('Awake!')
            self.transition('awake')
            if self.wake_receiver is not None:
                self.send(self.wake_receiver, message)
        elif isinstance(message, WakeWordNotDetected):
            self._logger.debug('Wake word NOT detected. Staying asleep.')
            self.transition('ready')
            if self.wake_receiver is not None:
                self.send(self.wake_receiver, message)
        else:
            self.handle_any(message, sender)

    def to_awake(self, from_state:str) -> None:
        self.send(self.wake, StopListeningForWakeWord())

        # Wake up beep
        wav_path = self.profile.get('sounds.wake', None)
        if wav_path is not None:
            self.send(self.player, PlayWavFile(wav_path))

        # Listen for a voice command
        self.send(self.command, ListenForCommand(self.myAddress, handle=self.handle))

    def in_awake(self, message: Any, sender: ActorAddress) -> None:
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

    def in_decoding(self, message: Any, sender: ActorAddress) -> None:
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

    def in_recognizing(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, IntentRecognized):
            # Handle intent
            self._logger.debug(message.intent)
            if message.handle:
                # Forward to Home Assistant
                self.send(self.handler, HandleIntent(message.intent))

                # Forward to MQTT (hermes)
                self.send(self.mqtt, message)

                self.transition('handling')
            else:
                self._logger.debug('Not actually handling intent')
                if self.intent_receiver is not None:
                    self.send(self.intent_receiver, message.intent)
                self.transition('ready')
        else:
            self.handle_any(message, sender)

    def in_handling(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, IntentHandled):
            if self.intent_receiver is not None:
                self.send(self.intent_receiver, message.intent)

            self.transition('ready')
        else:
            self.handle_any(message, sender)

    # -------------------------------------------------------------------------
    # Training
    # -------------------------------------------------------------------------

    def in_training_sentences(self, message: Any, sender: ActorAddress) -> None:
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
        else:
            self.handle_forward(message, sender)

    def in_training_speech(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, SpeechTrainingComplete):
            self.transition('training_intent')
            self.send(self.intent_trainer,
                      TrainIntent(message.tagged_sentences,
                                  message.sentences_by_intent))
        elif isinstance(message, SpeechTrainingFailed):
            self.transition('ready')
            self.send(self.training_receiver, ProfileTrainingFailed())
        else:
            self.handle_forward(message, sender)

    def in_training_intent(self, message: Any, sender: ActorAddress) -> None:
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
            self.wait_actors: Dict[ActorAddress, str] = {
                'wake': self.wake,
                'decoder': self.decoder,
                'recognizer': self.recognizer
            }

            for name, actor in self.wait_actors.items():
                if actor in [self.mqtt]:
                    continue # skip

                self.send(actor, ConfigureEvent(self.profile,
                                                preload=self.preload,
                                                **self.actors))

            self._logger.info('Training complete')
            self.transition('training_loading')

    def in_training_loading(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, Configured):
            self.wait_actors = {
                name: actor for name, actor in self.wait_actors.items()
                if actor != sender
            }

            if len(self.wait_actors) == 0:
                self._logger.info('Actors reloaded')
                self.transition('ready')
                self.send(self.training_receiver,
                          ProfileTrainingComplete())
        else:
            self.handle_forward(message, sender)

    # -------------------------------------------------------------------------

    def handle_any(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, ListenForCommand):
            # Force voice command
            self.intent_receiver = message.receiver or sender
            self.transition('awake')
        elif isinstance(message, GetVoiceCommand):
            # Record voice command, but don't do anything with it
            self.send(self.command,
                      ListenForCommand(message.receiver or sender,
                                       timeout=message.timeout))
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

            # Forward to MQTT (hermes)
            self.send(self.mqtt, IntentRecognized(message.intent))
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
        elif isinstance(message, StateTransition):
            # Track state of every actor
            self.handle_transition(message, sender)
        elif isinstance(message, GetActorStates):
            self.send(sender, self.actor_states)
        elif isinstance(message, WakeupMessage):
            pass
        else:
            self.handle_forward(message, sender)

    def handle_transition(self, message:StateTransition, sender:ActorAddress) -> None:
        self.actor_states[message.name] = message.to_state
        topic = 'rhasspy/%s/transition/%s' % (self.profile.name, message.name)
        payload = message.to_state.encode()
        self.send(self.mqtt, MqttPublish(topic, payload))

    def handle_forward(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, GetMicrophones):
            # Get all microphones
            recorder_class = self.recorder_class
            if message.system is not None:
                recorder_class = DialogueManager.get_microphone_class(message.system)

            mics = recorder_class.get_microphones()
            self.send(sender, mics)
        elif isinstance(message, TestMicrophones):
            # Get working microphones
            recorder_system = self.profile.get('microphone.system', 'pyaudio')
            if message.system is not None:
                recorder_system = message.system

            recorder_class = DialogueManager.get_microphone_class(recorder_system)
            test_path = 'microphone.%s.test_chunk_size' % recorder_system
            chunk_size = int(self.profile.get(test_path, 1024))

            test_mics = recorder_class.test_microphones(chunk_size)
            self.send(sender, test_mics)
        elif isinstance(message, PlayWavData) \
             or isinstance(message, PlayWavFile):
            # Forward to audio player
            self.send(self.player, message)
        elif isinstance(message, MqttPublish):
            # Forward directly
            self.send(self.mqtt, message)
        elif isinstance(message, AudioData):
            # Forward to audio recorder
            self.send(self.recorder, message)
        else:
            self._logger.warning('Unhandled message: %s' % message)

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    def load_actors(self) -> None:
        self._logger.debug('Loading actors')

        # Microphone
        mic_system = self.profile.get('microphone.system', 'dummy')
        self.recorder_class = DialogueManager.get_microphone_class(mic_system)
        self.recorder:ActorAddress = self.createActor(self.recorder_class)
        self.actors['recorder'] = self.recorder

        # Audio player
        player_system = self.profile.get('sounds.system', 'dummy')
        self.player_class = DialogueManager.get_sound_class(player_system)
        self.player:ActorAddress = self.createActor(self.player_class)
        self.actors['player'] = self.player

        # Wake listener
        wake_system = self.profile.get('wake.system', 'dummy')
        self.wake_class = DialogueManager.get_wake_class(wake_system)
        self.wake:ActorAddress = self.createActor(self.wake_class)
        self.actors['wake'] = self.wake

        # Command listener
        command_system = self.profile.get('command.system', 'dummy')
        self.command_class = DialogueManager.get_command_class(command_system)
        self.command:ActorAddress = self.createActor(self.command_class)
        self.actors['command'] = self.command

        # Speech decoder
        decoder_system = self.profile.get('speech_to_text.system', 'dummy')
        self.decoder_class = DialogueManager.get_decoder_class(decoder_system)
        self.decoder:ActorAddress = self.createActor(self.decoder_class)
        self.actors['decoder'] = self.decoder

        # Intent recognizer
        recognizer_system = self.profile.get('intent.system', 'dummy')
        self.recognizer_class = DialogueManager.get_recognizer_class(recognizer_system)
        self.recognizer:ActorAddress = self.createActor(self.recognizer_class)
        self.actors['recognizer'] = self.recognizer

        # Intent handler
        handler_system = self.profile.get('handle.system', 'dummy')
        self.handler_class = DialogueManager.get_intent_handler_class(handler_system)
        self.handler:ActorAddress = self.createActor(self.handler_class)
        self.actors['handler'] = self.handler

        self.hass_handler:ActorAddress = self.handler
        if handler_system != 'hass':
            # Create a separate actor just for home assistant
            from .intent_handler import HomeAssistantIntentHandler
            self.hass_handler = self.createActor(HomeAssistantIntentHandler)

        self.actors['hass_handler'] = self.hass_handler

        # Sentence generator
        from .train import JsgfSentenceGenerator
        self.sentence_generator_class = JsgfSentenceGenerator
        self.sentence_generator:ActorAddress = self.createActor(self.sentence_generator_class)
        self.actors['sentence_generator'] = self.sentence_generator

        # Speech trainer
        speech_trainer_system = self.profile.get('training.speech_to_text.system', 'auto')
        self.speech_trainer_class = DialogueManager.get_speech_trainer_class(
            speech_trainer_system, decoder_system)

        self.speech_trainer:ActorAddress = self.createActor(self.speech_trainer_class)
        self.actors['speech_trainer'] = self.speech_trainer

        # Intent trainer
        intent_trainer_system = self.profile.get('training.intent.system', 'auto')
        self.intent_trainer_class = DialogueManager.get_intent_trainer_class(
            intent_trainer_system, recognizer_system)

        self.intent_trainer:ActorAddress = self.createActor(self.intent_trainer_class)
        self.actors['intent_trainer'] = self.intent_trainer

        # Word pronouncer
        from .pronounce import PhonetisaurusPronounce
        self.word_pronouncer_class = PhonetisaurusPronounce
        self.word_pronouncer:ActorAddress = self.createActor(self.word_pronouncer_class)
        self.actors['word_pronouncer'] = self.word_pronouncer

        # Configure actors
        self.wait_actors:Dict[str, ActorAddress] = {}
        for name, actor in self.actors.items():
            if actor in [self.mqtt]:
                continue # skip

            self.send(actor, ConfigureEvent(self.profile,
                                            preload=self.preload,
                                            **self.actors))
            self.wait_actors[name] = actor

        actor_names = list(self.wait_actors.keys())
        self._logger.debug(f'Actors created. Waiting for {actor_names} to start.')

    # -------------------------------------------------------------------------

    @classmethod
    def get_sound_class(cls, system:str) -> Type[RhasspyActor]:
        assert system in ['aplay', 'hermes', 'dummy'], \
            'Unknown sound system: %s' % system

        if system == 'aplay':
            from .audio_player import APlayAudioPlayer
            return APlayAudioPlayer
        elif system == 'hermes':
            from .audio_player import HermesAudioPlayer
            return HermesAudioPlayer
        else:
            from .audio_player import DummyAudioPlayer
            return DummyAudioPlayer

    @classmethod
    def get_wake_class(cls, system:str) -> Type[RhasspyActor]:
        assert system in ['dummy', 'pocketsphinx', 'hermes',
                          'snowboy', 'precise', 'command'], \
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
        elif system == 'command':
            # Use command-line listener
            from .wake import CommandWakeListener
            return CommandWakeListener
        else:
            # Does nothing
            from .wake import DummyWakeListener
            return DummyWakeListener

    @classmethod
    def get_microphone_class(cls, system: str) -> Type[RhasspyActor]:
        assert system in ['arecord', 'pyaudio', 'dummy',
                          'hermes', 'stdin'], \
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
        elif system == 'stdin':
            from .audio_recorder import StdinAudioRecorder
            return StdinAudioRecorder
        else:
            from .audio_recorder import DummyAudioRecorder
            return DummyAudioRecorder

    @classmethod
    def get_command_class(cls, system: str) -> Type[RhasspyActor]:
        assert system in ['dummy', 'webrtcvad', 'command', 'oneshot'], \
            'Unknown voice command system: %s' % system

        if system == 'webrtcvad':
            from .command_listener import WebrtcvadCommandListener
            return WebrtcvadCommandListener
        elif system == 'command':
            from .command_listener import CommandCommandListener
            return CommandCommandListener
        elif system == 'oneshot':
            from .command_listener import OneShotCommandListener
            return OneShotCommandListener
        else:
            from .command_listener import DummyCommandListener
            return DummyCommandListener

    @classmethod
    def get_decoder_class(cls, system: str) -> Type[RhasspyActor]:
        assert system in ['dummy', 'pocketsphinx', 'remote', 'command'], \
            'Invalid speech to text system: %s' % system

        if system == 'pocketsphinx':
            from .stt import PocketsphinxDecoder
            return PocketsphinxDecoder
        elif system == 'remote':
            from .stt import RemoteDecoder
            return RemoteDecoder
        elif system == 'command':
            from .stt import CommandDecoder
            return CommandDecoder
        else:
            from .stt import DummyDecoder
            return DummyDecoder

    @classmethod
    def get_recognizer_class(cls, system: str) -> Type[RhasspyActor]:
        assert system in ['dummy', 'fuzzywuzzy', 'adapt', 'rasa', 'remote', 'command'], \
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
        elif system == 'command':
            # Use command line
            from .intent import CommandRecognizer
            return CommandRecognizer
        else:
            # Does nothing
            from .intent import DummyIntentRecognizer
            return DummyIntentRecognizer

    @classmethod
    def get_intent_trainer_class(cls, trainer_system: str,
                                 recognizer_system: str='dummy') -> Type[RhasspyActor]:

        assert trainer_system in ['dummy', 'fuzzywuzzy', 'adapt', 'auto', 'command'], \
            'Invalid intent training system: %s' % trainer_system

        if trainer_system == 'auto':
            # Use intent recognizer system
            if recognizer_system == 'fuzzywuzzy':
                # Use fuzzy string matching locally
                from .intent_train import FuzzyWuzzyIntentTrainer
                return FuzzyWuzzyIntentTrainer
            elif recognizer_system == 'adapt':
                # Use Mycroft Adapt locally
                from .intent_train import AdaptIntentTrainer
                return AdaptIntentTrainer
            elif recognizer_system == 'rasa':
                # Use rasaNLU remotely
                from .intent_train import RasaIntentTrainer
                return RasaIntentTrainer
            elif recognizer_system == 'command':
                # Use command-line intent trainer
                from .intent_train import CommandIntentTrainer
                return CommandIntentTrainer
        elif trainer_system == 'fuzzywuzzy':
            # Use fuzzy string matching locally
            from .intent_train import FuzzyWuzzyIntentTrainer
            return FuzzyWuzzyIntentTrainer
        elif trainer_system == 'adapt':
            # Use Mycroft Adapt locally
            from .intent_train import AdaptIntentTrainer
            return AdaptIntentTrainer
        elif trainer_system == 'rasa':
            # Use rasaNLU remotely
            from .intent_train import RasaIntentTrainer
            return RasaIntentTrainer
        elif trainer_system == 'command':
            # Use command-line intent trainer
            from .intent_train import CommandIntentTrainer
            return CommandIntentTrainer

        # Use dummy trainer as a fallback
        from .intent_train import DummyIntentTrainer
        return DummyIntentTrainer

    @classmethod
    def get_speech_trainer_class(cls, trainer_system: str,
                                 decoder_system: str='dummy') -> Type[RhasspyActor]:

        assert trainer_system in ['dummy', 'pocketsphinx', 'auto', 'command'], \
            'Invalid speech training system: %s' % trainer_system

        if trainer_system == 'auto':
            # Use speech decoder system
            if decoder_system == 'pocketsphinx':
                # Use opengrm/phonetisaurus
                from .stt_train import PocketsphinxSpeechTrainer
                return PocketsphinxSpeechTrainer
            elif decoder_system == 'command':
                # Use command-line speech trainer
                from .stt_train import CommandSpeechTrainer
                return CommandSpeechTrainer
        elif trainer_system == 'pocketsphinx':
            # Use opengrm/phonetisaurus
            from .stt_train import PocketsphinxSpeechTrainer
            return PocketsphinxSpeechTrainer
        elif trainer_system == 'command':
            # Use command-line speech trainer
            from .stt_train import CommandSpeechTrainer
            return CommandSpeechTrainer

        # Use dummy trainer as a fallback
        from .stt_train import DummySpeechTrainer
        return DummySpeechTrainer

    @classmethod
    def get_intent_handler_class(cls, system: str) -> Type[RhasspyActor]:
        assert system in ['dummy', 'hass', 'command'], \
            'Invalid intent handler system: %s' % system

        if system == 'hass':
            # Use Home Assistant directly
            from .intent_handler import HomeAssistantIntentHandler
            return HomeAssistantIntentHandler
        elif system == 'command':
            # Use command-line speech trainer
            from .intent_handler import CommandIntentHandler
            return CommandIntentHandler
        else:
            # Use dummy handlers as a fallback
            from .intent_handler import DummyIntentHandler
            return DummyIntentHandler
