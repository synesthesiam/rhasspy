import os
import json
from datetime import timedelta
from typing import Dict, Any, Optional, List, Type

from .actor import (
    RhasspyActor,
    ConfigureEvent,
    Configured,
    StateTransition,
    ActorExitRequest,
    WakeupMessage,
    ChildActorExited,
)
from .wake import (
    ListenForWakeWord,
    StopListeningForWakeWord,
    WakeWordDetected,
    WakeWordNotDetected,
    get_wake_class,
)
from .command_listener import ListenForCommand, VoiceCommand, get_command_class
from .audio_recorder import (
    StartRecordingToBuffer,
    StopRecordingToBuffer,
    AudioData,
    get_microphone_class,
)
from .audio_player import PlayWavFile, PlayWavData, WavPlayed, get_sound_class
from .stt import TranscribeWav, WavTranscription, get_decoder_class
from .stt_train import (
    TrainSpeech,
    SpeechTrainingComplete,
    SpeechTrainingFailed,
    get_speech_trainer_class,
)
from .intent import RecognizeIntent, IntentRecognized, get_recognizer_class
from .intent_train import (
    TrainIntent,
    IntentTrainingComplete,
    IntentTrainingFailed,
    get_intent_trainer_class,
)
from .intent_handler import HandleIntent, IntentHandled, get_intent_handler_class
from .train import GenerateSentences, SentencesGenerated, SentenceGenerationFailed
from .pronounce import GetWordPhonemes, SpeakWord, GetWordPronunciations
from .tts import SpeakSentence, get_speech_class
from .mqtt import MqttPublish
from .utils import buffer_to_wav

# -----------------------------------------------------------------------------


class GetMicrophones:
    def __init__(self, system: Optional[str] = None) -> None:
        self.system = system


class TestMicrophones:
    def __init__(self, system: Optional[str] = None) -> None:
        self.system = system


class GetSpeakers:
    def __init__(self, system: Optional[str] = None) -> None:
        self.system = system


class TrainProfile:
    def __init__(
        self, receiver: Optional[RhasspyActor] = None, reload_actors: bool = True
    ) -> None:
        self.receiver = receiver
        self.reload_actors = reload_actors


class ProfileTrainingFailed:
    def __init__(self, reason: str):
        self.reason = reason

    def __repr__(self):
        return f"FAILED: {self.reason}"


class ProfileTrainingComplete:
    def __repr__(self):
        return "OK"


class Ready:
    def __init__(self, timeout: bool = False, problems: Dict[str, Any] = {}) -> None:
        self.timeout = timeout
        self.problems = problems


class GetVoiceCommand:
    def __init__(
        self, receiver: Optional[RhasspyActor] = None, timeout: Optional[float] = None
    ) -> None:
        self.receiver = receiver
        self.timeout = timeout


class GetActorStates:
    pass


class GetProblems:
    pass


class Problems:
    def __init__(self, problems: Dict[str, Any] = {}):
        self.problems = problems


# -----------------------------------------------------------------------------


class DialogueManager(RhasspyActor):
    """Manages the overall state of Rhasspy."""

    def to_started(self, from_state: str) -> None:
        self.site_id: str = self.profile.get("mqtt.site_id", "default")
        self.preload: bool = self.config.get("preload", False)
        self.timeout_sec: Optional[float] = self.config.get("load_timeout_sec", None)
        self.send_ready: bool = self.config.get("ready", False)
        self.wake_receiver: Optional[RhasspyActor] = None
        self.intent_receiver: Optional[RhasspyActor] = None
        self.training_receiver: Optional[RhasspyActor] = None
        self.handle: bool = True
        self.actors: Dict[str, RhasspyActor] = {}
        self.actor_states: Dict[str, str] = {}
        self.reload_actors_after_training = True
        self.problems: Dict[str, Any] = {}
        self.mqtt: Optional[RhasspyActor] = None
        self.observer: Optional[RhasspyActor] = self.config.get("observer", None)

        if self.profile.get("mqtt.enabled", False):
            self.transition("loading_mqtt")
        else:
            self.transition("loading")

    def to_loading_mqtt(self, from_state: str) -> None:
        self._logger.debug("Loading MQTT first")

        # MQTT client *first*
        from .mqtt import HermesMqtt

        self.mqtt_class = HermesMqtt
        self.mqtt = self.createActor(self.mqtt_class)
        self.actors["mqtt"] = self.mqtt

        self.send(
            self.mqtt, ConfigureEvent(self.profile, preload=self.preload, **self.actors)
        )

        if self.timeout_sec is not None:
            self._logger.debug(
                f"Loading...will time out after {self.timeout_sec} second(s)"
            )
            self.wakeupAfter(timedelta(seconds=self.timeout_sec))

    def in_loading_mqtt(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, Configured) and (sender == self.mqtt):
            self.problems[message.name] = message.problems
            self.transition("loading")
        elif isinstance(message, WakeupMessage):
            self._logger.warning("MQTT actor did not load! Trying to keep going...")
            self.transition("loading")

    def to_loading(self, from_state: str) -> None:
        # Load all of the other actors
        self.load_actors()

    def in_loading(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, Configured):
            self.problems[message.name] = message.problems

            # Remove sender
            sender_name = None
            for name, actor in self.wait_actors.items():
                if actor == sender:
                    sender_name = name
                    break

            if sender_name is not None:
                del self.wait_actors[sender_name]
                self._logger.debug(f"{sender_name} started")

            if len(self.wait_actors) == 0:
                self._logger.info("Actors loaded")
                self.transition("ready")

                # Inform all actors that we're ready
                for actor in self.actors.values():
                    self.send(actor, Ready())

                # Inform parent actor that we're ready
                if self.send_ready:
                    self.send(self._parent, Ready())
        elif isinstance(message, WakeupMessage):
            wait_names = list(self.wait_actors.keys())
            self._logger.warning(
                f"Actor timeout! Still waiting on {wait_names} Loading anyway..."
            )
            self.transition("ready")

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

    def to_ready(self, from_state: str) -> None:
        if self.profile.get("rhasspy.listen_on_start", False):
            self._logger.info("Automatically listening for wake word")
            self.transition("asleep")
            self.send(self.wake, ListenForWakeWord())

    def in_ready(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, ListenForWakeWord):
            self._logger.info("Listening for wake word")
            self.wake_receiver = message.receiver or sender
            self.send(self.wake, ListenForWakeWord())
            self.transition("asleep")
        else:
            self.handle_any(message, sender)

    def in_asleep(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, WakeWordDetected):
            self._logger.debug("Awake!")
            self.transition("awake")
            if self.wake_receiver is not None:
                self.send(self.wake_receiver, message)
        elif isinstance(message, WakeWordNotDetected):
            self._logger.debug("Wake word NOT detected. Staying asleep.")
            self.transition("ready")
            if self.wake_receiver is not None:
                self.send(self.wake_receiver, message)
        else:
            self.handle_any(message, sender)

    def to_awake(self, from_state: str) -> None:
        self.send(self.wake, StopListeningForWakeWord())

        # Wake up beep
        wav_path = os.path.expandvars(self.profile.get("sounds.wake", None))
        if wav_path is not None:
            self.send(self.player, PlayWavFile(wav_path))

        # Listen for a voice command
        self.send(self.command, ListenForCommand(self.myAddress, handle=self.handle))

    def in_awake(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, VoiceCommand):
            # Recorded beep
            wav_path = os.path.expandvars(self.profile.get("sounds.recorded", None))
            if wav_path is not None:
                self.send(self.player, PlayWavFile(wav_path))

            # speech -> text
            wav_data = buffer_to_wav(message.data)
            self.send(self.decoder, TranscribeWav(wav_data, handle=message.handle))
            self.transition("decoding")
        else:
            self.handle_any(message, sender)

    # -------------------------------------------------------------------------
    # Recognition
    # -------------------------------------------------------------------------

    def in_decoding(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, WavTranscription):
            # text -> intent
            self._logger.debug(f"{message.text} (confidence={message.confidence})")

            # Send to MQTT
            payload = json.dumps(
                {
                    "siteId": self.site_id,
                    "text": message.text,
                    "likelihood": 1,
                    "seconds": 0,
                }
            ).encode()

            self.send(
                self.mqtt,
                MqttPublish(
                    "rhasspy/speech-to-text/transcription", message.text.encode()
                ),
            )
            self.send(self.mqtt, MqttPublish("hermes/asr/textCaptured", payload))

            # Pass to intent recognizer
            self.send(
                self.recognizer,
                RecognizeIntent(
                    message.text, confidence=message.confidence, handle=message.handle
                ),
            )
            self.transition("recognizing")
        else:
            self.handle_any(message, sender)

    def in_recognizing(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, IntentRecognized):
            # Handle intent
            self._logger.debug(message.intent)
            if message.handle:
                # Forward to Home Assistant
                self.send(self.handler, HandleIntent(message.intent))

                # Forward to MQTT (hermes)
                self.send(self.mqtt, message)

                # Forward to observer
                if self.observer:
                    self.send(self.observer, message)

                self.transition("handling")
            else:
                self._logger.debug("Not actually handling intent")
                if self.intent_receiver is not None:
                    self.send(self.intent_receiver, message.intent)
                self.transition("ready")
        else:
            self.handle_any(message, sender)

    def in_handling(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, IntentHandled):
            if self.intent_receiver is not None:
                self.send(self.intent_receiver, message.intent)

            self.transition("ready")
        else:
            self.handle_any(message, sender)

    # -------------------------------------------------------------------------
    # Training
    # -------------------------------------------------------------------------

    def in_training_sentences(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, SentencesGenerated):
            # Train speech system
            self.transition("training_speech")
            self.send(self.speech_trainer, TrainSpeech(message.intent_fst))
        elif isinstance(message, SentenceGenerationFailed):
            self.transition("ready")
            self.send(self.training_receiver, ProfileTrainingFailed(message.reason))
        else:
            self.handle_forward(message, sender)

    def in_training_speech(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, SpeechTrainingComplete):
            self.transition("training_intent")
            self.send(self.intent_trainer, TrainIntent(message.intent_fst))
        elif isinstance(message, SpeechTrainingFailed):
            self.transition("ready")
            self.send(self.training_receiver, ProfileTrainingFailed(message.reason))
        else:
            self.handle_forward(message, sender)

    def in_training_intent(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, IntentTrainingComplete):
            self._logger.info("Training complete")

            if self.reload_actors_after_training:
                self._logger.debug("Reloading actors")

                # Wake listener
                self.send(self.wake, ActorExitRequest())
                self.wake: RhasspyActor = self.createActor(self.wake_class)
                self.actors["wake"] = self.wake

                # Speech decoder
                self.send(self.decoder, ActorExitRequest())
                self.decoder: RhasspyActor = self.createActor(self.decoder_class)
                self.actors["decoder"] = self.decoder

                # Intent recognizer
                self.send(self.recognizer, ActorExitRequest())
                self.recognizer: RhasspyActor = self.createActor(self.recognizer_class)
                self.actors["recognizer"] = self.recognizer

                # Configure actors
                self.wait_actors: Dict[str, RhasspyActor] = {
                    "wake": self.wake,
                    "decoder": self.decoder,
                    "recognizer": self.recognizer,
                }

                for name, actor in self.wait_actors.items():
                    if actor in [self.mqtt]:
                        continue  # skip

                    self.send(
                        actor,
                        ConfigureEvent(
                            self.profile, preload=self.preload, **self.actors
                        ),
                    )

                self.transition("training_loading")
            else:
                self.transition("ready")
                self.send(self.training_receiver, ProfileTrainingComplete())
        elif isinstance(message, IntentTrainingFailed):
            self.transition("ready")
            self.send(self.training_receiver, ProfileTrainingFailed(message.reason))

    def in_training_loading(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, Configured):
            self.problems[message.name] = message.problems
            self.wait_actors = {
                name: actor
                for name, actor in self.wait_actors.items()
                if actor != sender
            }

            if len(self.wait_actors) == 0:
                self._logger.info("Actors reloaded")
                self.transition("ready")
                self.send(self.training_receiver, ProfileTrainingComplete())
        else:
            self.handle_forward(message, sender)

    # -------------------------------------------------------------------------

    def handle_any(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, ListenForCommand):
            # Force voice command
            self.intent_receiver = message.receiver or sender
            self.transition("awake")
        elif isinstance(message, GetVoiceCommand):
            # Record voice command, but don't do anything with it
            self.send(
                self.command,
                ListenForCommand(message.receiver or sender, timeout=message.timeout),
            )
        elif isinstance(message, TranscribeWav):
            # speech -> text
            self.send(
                self.decoder,
                TranscribeWav(message.wav_data, sender, handle=message.handle),
            )
        elif isinstance(message, RecognizeIntent):
            # text -> intent
            self.send(
                self.recognizer,
                RecognizeIntent(
                    message.text,
                    confidence=message.confidence,
                    receiver=sender,
                    handle=message.handle,
                ),
            )
        elif isinstance(message, HandleIntent):
            # intent -> action
            self.send(self.handler, HandleIntent(message.intent, sender))

            # Forward to MQTT (hermes)
            self.send(self.mqtt, IntentRecognized(message.intent))
        elif isinstance(message, GetWordPhonemes):
            # eSpeak -> CMU
            self.send(
                self.word_pronouncer, GetWordPhonemes(message.word, receiver=sender)
            )
        elif isinstance(message, SpeakWord):
            # eSpeak -> WAV
            self.send(self.word_pronouncer, SpeakWord(message.word, receiver=sender))
        elif isinstance(message, GetWordPronunciations):
            # word -> [CMU]
            self.send(
                self.word_pronouncer,
                GetWordPronunciations(message.words, n=message.n, receiver=sender),
            )
        elif isinstance(message, SpeakSentence):
            # text -> speech
            self.send(self.speech, SpeakSentence(message.sentence, receiver=sender))
        elif isinstance(message, TrainProfile):
            # Training
            self.reload_actors_after_training = message.reload_actors
            self.send(self.wake, StopListeningForWakeWord())
            self.training_receiver = message.receiver or sender
            self.transition("training_sentences")
            self.send(self.sentence_generator, GenerateSentences())
        elif isinstance(message, StartRecordingToBuffer):
            # Record WAV
            self.send(self.recorder, message)
        elif isinstance(message, StopRecordingToBuffer):
            # Stop recording WAV
            self.send(
                self.recorder,
                StopRecordingToBuffer(message.buffer_name, message.receiver or sender),
            )
        elif isinstance(message, StateTransition):
            # Track state of every actor
            self.handle_transition(message, sender)
        elif isinstance(message, GetActorStates):
            self.send(sender, self.actor_states)
        elif isinstance(message, WakeupMessage):
            pass
        elif isinstance(message, WavPlayed):
            pass
        elif isinstance(message, GetProblems):
            # Report problems from child actors
            self.send(sender, Problems(self.problems))
        else:
            self.handle_forward(message, sender)

    def handle_transition(self, message: StateTransition, sender: RhasspyActor) -> None:
        self.actor_states[message.name] = message.to_state
        topic = "rhasspy/%s/transition/%s" % (self.profile.name, message.name)
        payload = message.to_state.encode()
        self.send(self.mqtt, MqttPublish(topic, payload))

    def handle_forward(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, GetMicrophones):
            # Get all microphones
            recorder_class = self.recorder_class
            if message.system is not None:
                recorder_class = get_microphone_class(message.system)

            mics = recorder_class.get_microphones()
            self.send(sender, mics)
        elif isinstance(message, TestMicrophones):
            # Get working microphones
            recorder_system = self.profile.get("microphone.system", "pyaudio")
            if message.system is not None:
                recorder_system = message.system

            recorder_class = get_microphone_class(recorder_system)
            test_path = "microphone.%s.test_chunk_size" % recorder_system
            chunk_size = int(self.profile.get(test_path, 1024))

            test_mics = recorder_class.test_microphones(chunk_size)
            self.send(sender, test_mics)
        elif isinstance(message, GetSpeakers):
            # Get all speakers
            player_class = self.player_class
            if message.system is not None:
                player_class = get_sound_class(message.system)

            speakers = player_class.get_speakers()
            self.send(sender, speakers)
        elif isinstance(message, PlayWavData) or isinstance(message, PlayWavFile):
            # Forward to audio player
            self.send(self.player, message)
        elif isinstance(message, MqttPublish):
            # Forward directly
            self.send(self.mqtt, message)
        elif isinstance(message, AudioData):
            # Forward to audio recorder
            self.send(self.recorder, message)
        elif not (
            isinstance(message, StateTransition)
            or isinstance(message, ChildActorExited)
        ):
            self._logger.warning("Unhandled message: %s" % message)

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    def load_actors(self) -> None:
        self._logger.debug("Loading actors")

        # Microphone
        mic_system = self.profile.get("microphone.system", "dummy")
        self.recorder_class = get_microphone_class(mic_system)
        self.recorder: RhasspyActor = self.createActor(self.recorder_class)
        self.actors["recorder"] = self.recorder

        # Audio player
        player_system = self.profile.get("sounds.system", "dummy")
        self.player_class = get_sound_class(player_system)
        self.player: RhasspyActor = self.createActor(self.player_class)
        self.actors["player"] = self.player

        # Text to Speech
        speech_system = self.profile.get("text_to_speech.system", "dummy")
        self.speech_class = get_speech_class(speech_system)
        self.speech: RhasspyActor = self.createActor(self.speech_class)
        self.actors["speech"] = self.speech

        # Wake listener
        wake_system = self.profile.get("wake.system", "dummy")
        self.wake_class = get_wake_class(wake_system)
        self.wake: RhasspyActor = self.createActor(self.wake_class)
        self.actors["wake"] = self.wake

        # Command listener
        command_system = self.profile.get("command.system", "dummy")
        self.command_class = get_command_class(command_system)
        self.command: RhasspyActor = self.createActor(self.command_class)
        self.actors["command"] = self.command

        # Speech decoder
        decoder_system = self.profile.get("speech_to_text.system", "dummy")
        self.decoder_class = get_decoder_class(decoder_system)
        self.decoder: RhasspyActor = self.createActor(self.decoder_class)
        self.actors["decoder"] = self.decoder

        # Intent recognizer
        recognizer_system = self.profile.get("intent.system", "dummy")
        self.recognizer_class = get_recognizer_class(recognizer_system)
        self.recognizer: RhasspyActor = self.createActor(self.recognizer_class)
        self.actors["recognizer"] = self.recognizer

        # Intent handler
        handler_system = self.profile.get("handle.system", "dummy")
        self.handler_class = get_intent_handler_class(handler_system)
        self.handler: RhasspyActor = self.createActor(self.handler_class)
        self.actors["handler"] = self.handler

        self.hass_handler: Optional[RhasspyActor] = None
        forward_to_hass = self.profile.get("handle.forward_to_hass", False)
        if (handler_system != "hass") and forward_to_hass:
            # Create a separate actor just for home assistant
            from .intent_handler import HomeAssistantIntentHandler

            self.hass_handler = self.createActor(HomeAssistantIntentHandler)

        self.actors["hass_handler"] = self.hass_handler

        # Sentence generator
        from .train import JsgfSentenceGenerator

        self.sentence_generator_class = JsgfSentenceGenerator
        self.sentence_generator: RhasspyActor = self.createActor(
            self.sentence_generator_class
        )
        self.actors["sentence_generator"] = self.sentence_generator

        # Speech trainer
        speech_trainer_system = self.profile.get(
            "training.speech_to_text.system", "auto"
        )
        self.speech_trainer_class = get_speech_trainer_class(
            speech_trainer_system, decoder_system
        )

        self.speech_trainer: RhasspyActor = self.createActor(self.speech_trainer_class)
        self.actors["speech_trainer"] = self.speech_trainer

        # Intent trainer
        intent_trainer_system = self.profile.get("training.intent.system", "auto")
        self.intent_trainer_class = get_intent_trainer_class(
            intent_trainer_system, recognizer_system
        )

        self.intent_trainer: RhasspyActor = self.createActor(self.intent_trainer_class)
        self.actors["intent_trainer"] = self.intent_trainer

        # Word pronouncer
        from .pronounce import PhonetisaurusPronounce

        self.word_pronouncer_class = PhonetisaurusPronounce
        self.word_pronouncer: RhasspyActor = self.createActor(
            self.word_pronouncer_class
        )
        self.actors["word_pronouncer"] = self.word_pronouncer

        # Configure actors
        self.wait_actors: Dict[str, RhasspyActor] = {}
        for name, actor in self.actors.items():
            if actor in [self.mqtt]:
                continue  # skip

            self.send(
                actor, ConfigureEvent(self.profile, preload=self.preload, **self.actors)
            )
            self.wait_actors[name] = actor

        actor_names = list(self.wait_actors.keys())
        self._logger.debug(f"Actors created. Waiting for {actor_names} to start.")
