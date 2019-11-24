"""Manages Rhasspy sleep/wake state and control flow."""
import json
import os
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Type

import pywrapfst as fst

from rhasspy.actor import (
    ActorExitRequest,
    ChildActorExited,
    Configured,
    ConfigureEvent,
    RhasspyActor,
    StateTransition,
    WakeupMessage,
)
from rhasspy.audio_player import PlayWavData, PlayWavFile, WavPlayed, get_sound_class
from rhasspy.audio_recorder import (
    AudioData,
    HTTPAudioRecorder,
    StartRecordingToBuffer,
    StopRecordingToBuffer,
    get_microphone_class,
)
from rhasspy.command_listener import ListenForCommand, VoiceCommand, get_command_class
from rhasspy.intent import IntentRecognized, RecognizeIntent, get_recognizer_class
from rhasspy.intent_handler import HandleIntent, IntentHandled, get_intent_handler_class
from rhasspy.intent_train import (
    IntentTrainingComplete,
    IntentTrainingFailed,
    TrainIntent,
    get_intent_trainer_class,
)
from rhasspy.mqtt import MqttPublish
from rhasspy.pronounce import GetWordPhonemes, GetWordPronunciations, SpeakWord
from rhasspy.stt import TranscribeWav, WavTranscription, get_decoder_class
from rhasspy.stt_train import get_speech_trainer_class

from rhasspy.train import train_profile
from rhasspy.tts import SpeakSentence, get_speech_class
from rhasspy.utils import buffer_to_wav
from rhasspy.wake import (
    ListenForWakeWord,
    StopListeningForWakeWord,
    WakeWordDetected,
    WakeWordNotDetected,
    get_wake_class,
)

# -----------------------------------------------------------------------------


class GetMicrophones:
    """Request list of micrphones."""

    def __init__(self, system: Optional[str] = None) -> None:
        self.system = system


class TestMicrophones:
    """Request live microphones."""

    def __init__(self, system: Optional[str] = None) -> None:
        self.system = system


class GetSpeakers:
    """Request list of audio players."""

    def __init__(self, system: Optional[str] = None) -> None:
        self.system = system


class TrainProfile:
    """Request training for profile."""

    def __init__(
        self, receiver: Optional[RhasspyActor] = None, reload_actors: bool = True
    ) -> None:
        self.receiver = receiver
        self.reload_actors = reload_actors


class ProfileTrainingFailed:
    """Response when training fails."""

    def __init__(self, reason: str):
        self.reason = reason

    def __repr__(self):
        return f"FAILED: {self.reason}"


class ProfileTrainingComplete:
    """Response when training succeeds."""

    def __repr__(self):
        return "OK"


class Ready:
    """Emitted when all actors have been loaded."""

    def __init__(
        self, timeout: bool = False, problems: Optional[Dict[str, Any]] = None
    ) -> None:
        self.timeout = timeout
        self.problems = problems or {}


class GetVoiceCommand:
    """Request to record a voice command."""

    def __init__(
        self, receiver: Optional[RhasspyActor] = None, timeout: Optional[float] = None
    ) -> None:
        self.receiver = receiver
        self.timeout = timeout


class GetActorStates:
    """Request for actors' current states."""

    pass


class GetProblems:
    """Request any problems during startup."""

    pass


class Problems:
    """Response to GetProblems."""

    def __init__(self, problems: Optional[Dict[str, Any]] = None):
        self.problems = problems or {}


# -----------------------------------------------------------------------------


class DialogueManager(RhasspyActor):
    """Manages the overall state of Rhasspy."""

    def __init__(self):
        RhasspyActor.__init__(self)

        # Child actors
        self.actors: Dict[str, RhasspyActor] = {}

        # Actor states
        self.actor_states: Dict[str, str] = {}

        # Voice command recorder
        self.command_class: Optional[Type] = None
        self._command: Optional[RhasspyActor] = None

        # Speech to text
        self.decoder_class: Optional[Type] = None
        self._decoder: Optional[RhasspyActor] = None

        # Intent handling
        self.handle: bool = True
        self.handler_class: Optional[Type] = None
        self._handler: Optional[RhasspyActor] = None
        self.hass_handler: Optional[RhasspyActor] = None
        self.intent_receiver: Optional[RhasspyActor] = None

        # Intent recognizer training
        self.intent_trainer_class: Optional[Type] = None
        self._intent_trainer: Optional[RhasspyActor] = None

        # MQTT
        self.mqtt_class: Optional[Type] = None
        self.mqtt: Optional[RhasspyActor] = None

        # For websockets
        self.observer: Optional[RhasspyActor] = None

        # Audio player
        self.player_class: Optional[Type] = None
        self._player: Optional[RhasspyActor] = None

        # External setting to pre-load speech/intent artifacts
        self.preload: bool = False

        # Problems during startup
        self.problems: Dict[str, Any] = {}

        # Intent recognition
        self.recognizer_class: Optional[Type] = None
        self._recognizer: Optional[RhasspyActor] = None

        # Audio recording
        self.recorder_class: Optional[Type] = None
        self._recorder: Optional[RhasspyActor] = None

        # Post-training reload
        self.reload_actors_after_training = True

        # Send Ready when actors are loaded
        self.send_ready: bool = False

        # MQTT site id
        self.site_id: str = "default"

        # Text to speech
        self.speech_class: Optional[Type] = None
        self._speech: Optional[RhasspyActor] = None
        self.speech_trainer_class: Optional[Type] = None
        self._speech_trainer: Optional[RhasspyActor] = None

        # Load timeout
        self.timeout_sec: Optional[float] = None

        # Result of training
        self.training_receiver: Optional[RhasspyActor] = None

        # Loading actors
        self.wait_actors: Dict[str, RhasspyActor] = {}

        # Wake word
        self.wake_class: Optional[Type] = None
        self._wake: Optional[RhasspyActor] = None
        self.wake_receiver: Optional[RhasspyActor] = None

        # Word pronunciations
        self.word_pronouncer_class: Optional[Type] = None
        self._word_pronouncer: Optional[RhasspyActor] = None

    # -------------------------------------------------------------------------

    @property
    def command(self) -> RhasspyActor:
        """Get actor for voice command listener."""
        assert self._command is not None
        return self._command

    @property
    def decoder(self) -> RhasspyActor:
        """Get actor for speech to text."""
        assert self._decoder is not None
        return self._decoder

    @property
    def handler(self) -> RhasspyActor:
        """Get actor for intent handling."""
        assert self._handler is not None
        return self._handler

    @property
    def intent_trainer(self) -> RhasspyActor:
        """Get actor for intent recognizer training."""
        assert self._intent_trainer is not None
        return self._intent_trainer

    @property
    def player(self) -> RhasspyActor:
        """Get actor for playing audio."""
        assert self._player is not None
        return self._player

    @property
    def recognizer(self) -> RhasspyActor:
        """Get actor for intent recognition."""
        assert self._recognizer is not None
        return self._recognizer

    @property
    def recorder(self) -> RhasspyActor:
        """Get actor for audio recording."""
        assert self._recorder is not None
        return self._recorder

    @property
    def speech(self) -> RhasspyActor:
        """Get actor for text to speech."""
        assert self._speech is not None
        return self._speech

    @property
    def speech_trainer(self) -> RhasspyActor:
        """Get actor for speech to text training."""
        assert self._speech_trainer is not None
        return self._speech_trainer

    @property
    def wake(self) -> RhasspyActor:
        """Get actor for wake word detection."""
        assert self._wake is not None
        return self._wake

    @property
    def word_pronouncer(self) -> RhasspyActor:
        """Get actor for pronouncing words."""
        assert self._word_pronouncer is not None
        return self._word_pronouncer

    # -------------------------------------------------------------------------

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.site_id = self.profile.get("mqtt.site_id", "default")
        self.preload = self.config.get("preload", False)
        self.timeout_sec = self.config.get("load_timeout_sec", None)
        self.send_ready = self.config.get("ready", False)
        self.observer = self.config.get("observer", None)

        if self.profile.get("mqtt.enabled", False):
            self.transition("loading_mqtt")
        else:
            self.transition("loading")

    def to_loading_mqtt(self, from_state: str) -> None:
        """Transition to loading_mqtt state."""
        self._logger.debug("Loading MQTT first")

        # MQTT client *first*
        from rhasspy.mqtt import HermesMqtt

        self.mqtt_class = HermesMqtt
        self.mqtt = self.createActor(self.mqtt_class)
        self.actors["mqtt"] = self.mqtt

        self.send(
            self.mqtt, ConfigureEvent(self.profile, preload=self.preload, **self.actors)
        )

        if self.timeout_sec is not None:
            self._logger.debug(
                "Loading...will time out after %s second(s)", self.timeout_sec
            )
            self.wakeupAfter(timedelta(seconds=self.timeout_sec))

    def in_loading_mqtt(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in loading_mqtt state."""
        if isinstance(message, Configured) and (sender == self.mqtt):
            self.problems[message.name] = message.problems
            self.transition("loading")
        elif isinstance(message, WakeupMessage):
            self._logger.warning("MQTT actor did not load! Trying to keep going...")
            self.transition("loading")

    def to_loading(self, from_state: str) -> None:
        """Transiton to loading state."""
        # Load all of the other actors
        self.load_actors()

    def in_loading(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in loading state."""
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
                self._logger.debug("%s started", sender_name)

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
                "Actor timeout! Still waiting on %s Loading anyway...", wait_names
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
        """Transition to ready state."""
        if self.profile.get("rhasspy.listen_on_start", False):
            self._logger.info("Automatically listening for wake word")
            self.transition("asleep")
            self.send(self.wake, ListenForWakeWord())

    def in_ready(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in ready state."""
        if isinstance(message, ListenForWakeWord):
            self._logger.info("Listening for wake word")
            self.wake_receiver = message.receiver or sender
            self.send(self.wake, ListenForWakeWord())
            self.transition("asleep")
        else:
            self.handle_any(message, sender)

    def in_asleep(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in asleep state."""
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
        """Transition to awake state."""
        self.send(self.wake, StopListeningForWakeWord())

        # Wake up beep
        wav_path = os.path.expandvars(self.profile.get("sounds.wake", None))
        if wav_path is not None:
            self.send(self.player, PlayWavFile(wav_path))

        # Listen for a voice command
        self.send(self.command, ListenForCommand(self.myAddress, handle=self.handle))

    def in_awake(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in awake state."""
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
        """Handle messages in decoding state."""
        if isinstance(message, WavTranscription):
            # text -> intent
            self._logger.debug("%s (confidence=%s)", message.text, message.confidence)

            if self.recorder_class == HTTPAudioRecorder:
                # Forward to audio recorder
                self.send(self.recorder, message)

            # Send to MQTT
            payload = json.dumps(
                {
                    "siteId": self.site_id,
                    "text": message.text,
                    "likelihood": 1,
                    "seconds": 0,
                }
            ).encode()

            if self.mqtt is not None:
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
        """Handle messages in recognizing state."""
        if isinstance(message, IntentRecognized):
            if self.recorder_class == HTTPAudioRecorder:
                # Forward to audio recorder
                self.send(self.recorder, message)

            # Handle intent
            self._logger.debug(message.intent)
            if message.handle:
                # Forward to Home Assistant
                self.send(self.handler, HandleIntent(message.intent))

                # Forward to MQTT (hermes)
                if self.mqtt is not None:
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
        """Handle messages in handling state."""
        if isinstance(message, IntentHandled):
            if self.intent_receiver is not None:
                self.send(self.intent_receiver, message.intent)

            self.transition("ready")
        else:
            self.handle_any(message, sender)

    # -------------------------------------------------------------------------
    # Training
    # -------------------------------------------------------------------------

    def to_training_sentences(self, from_state: str) -> None:
        """Transition to training_sentences state."""
        # Use doit to train
        saved_argv = sys.argv
        try:
            # Store doit database in profile directory
            sys.argv = [
                sys.argv[0],
                "--db-file",
                str(self.profile.write_path(".doit.db")),
            ]

            train_profile(Path(self.profile.read_path()), self.profile)
            self.transition("training_intent")

            intent_fst_path = self.profile.read_path(
                self.profile.get("intent.fsticuffs.intent_fst", "intent.fst")
            )

            intent_fst = fst.Fst.read(str(intent_fst_path))
            self.send(self.intent_trainer, TrainIntent(intent_fst))
        except Exception as e:
            self.transition("ready")
            self.send(self.training_receiver, ProfileTrainingFailed(str(e)))
        finally:
            # Restore sys.argv
            sys.argv = saved_argv

    def in_training_intent(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in training_intent state."""
        if isinstance(message, IntentTrainingComplete):
            self._logger.info("Training complete")

            if self.reload_actors_after_training:
                self._logger.debug("Reloading actors")

                # Wake listener
                self.send(self.wake, ActorExitRequest())
                self._wake = self.createActor(self.wake_class)
                self.actors["wake"] = self.wake

                # Speech decoder
                self.send(self.decoder, ActorExitRequest())
                self._decoder = self.createActor(self.decoder_class)
                self.actors["decoder"] = self.decoder

                # Intent recognizer
                self.send(self.recognizer, ActorExitRequest())
                self._recognizer = self.createActor(self.recognizer_class)
                self.actors["recognizer"] = self.recognizer

                # Configure actors
                self.wait_actors = {
                    "wake": self.wake,
                    "decoder": self.decoder,
                    "recognizer": self.recognizer,
                }

                for actor in self.wait_actors.values():
                    if actor == self.mqtt:
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
        """Handle messages in training_loading state."""
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
        """Handle messages in any state."""
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
            if self.mqtt is not None:
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
            # self.send(self.sentence_generator, GenerateSentences())
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
        """Report state transition of actor."""
        self.actor_states[message.name] = message.to_state
        topic = "rhasspy/%s/transition/%s" % (self.profile.name, message.name)
        payload = message.to_state.encode()

        if self.mqtt is not None:
            self.send(self.mqtt, MqttPublish(topic, payload))

    def handle_forward(self, message: Any, sender: RhasspyActor) -> None:
        """Forward messages to appropriate actor."""
        if isinstance(message, GetMicrophones):
            # Get all microphones
            recorder_class = self.recorder_class
            if message.system is not None:
                recorder_class = get_microphone_class(message.system)

            try:
                assert recorder_class is not None
                mics = recorder_class.get_microphones()
            except Exception:
                self._logger.exception("get_microphones")
                mics = {}

            self.send(sender, mics)
        elif isinstance(message, TestMicrophones):
            # Get working microphones
            recorder_system = self.profile.get("microphone.system", "pyaudio")
            if message.system is not None:
                recorder_system = message.system

            recorder_class = get_microphone_class(recorder_system)
            test_path = "microphone.%s.test_chunk_size" % recorder_system
            chunk_size = int(self.profile.get(test_path, 1024))

            assert recorder_class is not None
            test_mics = recorder_class.test_microphones(chunk_size)
            self.send(sender, test_mics)
        elif isinstance(message, GetSpeakers):
            # Get all speakers
            player_class = self.player_class
            if message.system is not None:
                player_class = get_sound_class(message.system)

            assert player_class is not None
            speakers = player_class.get_speakers()
            self.send(sender, speakers)
        elif isinstance(message, (PlayWavData, PlayWavFile)):
            # Forward to audio player
            self.send(self.player, message)
        elif isinstance(message, MqttPublish):
            # Forward directly
            if self.mqtt is not None:
                self.send(self.mqtt, message)
        elif isinstance(message, AudioData):
            # Forward to audio recorder
            self.send(self.recorder, message)
        elif not isinstance(message, (StateTransition, ChildActorExited)):
            self._logger.warning("Unhandled message: %s", message)

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    def load_actors(self) -> None:
        """Load all system actors."""
        self._logger.debug("Loading actors")

        # Microphone
        mic_system = self.profile.get("microphone.system", "dummy")
        self.recorder_class = get_microphone_class(mic_system)
        self._recorder = self.createActor(self.recorder_class)
        self.actors["recorder"] = self.recorder

        # Audio player
        player_system = self.profile.get("sounds.system", "dummy")
        self.player_class = get_sound_class(player_system)
        self._player = self.createActor(self.player_class)
        self.actors["player"] = self.player

        # Text to Speech
        speech_system = self.profile.get("text_to_speech.system", "dummy")
        self.speech_class = get_speech_class(speech_system)
        self._speech = self.createActor(self.speech_class)
        self.actors["speech"] = self.speech

        # Wake listener
        wake_system = self.profile.get("wake.system", "dummy")
        self.wake_class = get_wake_class(wake_system)
        self._wake = self.createActor(self.wake_class)
        self.actors["wake"] = self.wake

        # Command listener
        command_system = self.profile.get("command.system", "dummy")
        self.command_class = get_command_class(command_system)
        self._command = self.createActor(self.command_class)
        self.actors["command"] = self.command

        # Speech decoder
        decoder_system = self.profile.get("speech_to_text.system", "dummy")
        self.decoder_class = get_decoder_class(decoder_system)
        self._decoder = self.createActor(self.decoder_class)
        self.actors["decoder"] = self.decoder

        # Intent recognizer
        recognizer_system = self.profile.get("intent.system", "dummy")
        self.recognizer_class = get_recognizer_class(recognizer_system)
        self._recognizer = self.createActor(self.recognizer_class)
        self.actors["recognizer"] = self.recognizer

        # Intent handler
        handler_system = self.profile.get("handle.system", "dummy")
        self.handler_class = get_intent_handler_class(handler_system)
        self._handler = self.createActor(self.handler_class)
        self.actors["handler"] = self.handler

        self.hass_handler = None
        forward_to_hass = self.profile.get("handle.forward_to_hass", False)
        if (handler_system != "hass") and forward_to_hass:
            # Create a separate actor just for home assistant
            from rhasspy.intent_handler import HomeAssistantIntentHandler

            self.hass_handler = self.createActor(HomeAssistantIntentHandler)
            self.actors["hass_handler"] = self.hass_handler

        # Speech trainer
        speech_trainer_system = self.profile.get(
            "training.speech_to_text.system", "auto"
        )
        self.speech_trainer_class = get_speech_trainer_class(
            speech_trainer_system, decoder_system
        )

        self._speech_trainer = self.createActor(self.speech_trainer_class)
        self.actors["speech_trainer"] = self.speech_trainer

        # Intent trainer
        intent_trainer_system = self.profile.get("training.intent.system", "auto")
        self.intent_trainer_class = get_intent_trainer_class(
            intent_trainer_system, recognizer_system
        )

        self._intent_trainer = self.createActor(self.intent_trainer_class)
        self.actors["intent_trainer"] = self.intent_trainer

        # Word pronouncer
        from rhasspy.pronounce import PhonetisaurusPronounce

        self.word_pronouncer_class = PhonetisaurusPronounce
        self._word_pronouncer = self.createActor(self.word_pronouncer_class)
        self.actors["word_pronouncer"] = self.word_pronouncer

        # Configure actors
        self.wait_actors = {}
        for name, actor in self.actors.items():
            if (actor is None) or (actor == self.mqtt):
                continue  # skip

            self.send(
                actor, ConfigureEvent(self.profile, preload=self.preload, **self.actors)
            )
            self.wait_actors[name] = actor

        actor_names = list(self.wait_actors.keys())
        self._logger.debug("Actors created. Waiting for %s to start.", actor_names)
