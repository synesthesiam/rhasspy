"""Manages Rhasspy sleep/wake state and control flow."""
import json
import os
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

import pydash
import requests
import rhasspynlu

from rhasspy.actor import (
    ActorExitRequest,
    ChildActorExited,
    Configured,
    ConfigureEvent,
    RhasspyActor,
    StateTransition,
    WakeupMessage,
)
from rhasspy.audio_player import get_sound_class
from rhasspy.audio_recorder import HTTPAudioRecorder, get_microphone_class
from rhasspy.command_listener import get_command_class
from rhasspy.events import (
    AudioData,
    GetActorStates,
    GetMicrophones,
    GetProblems,
    GetSpeakers,
    GetVoiceCommand,
    GetWordPhonemes,
    GetWordPronunciations,
    HandleIntent,
    IntentHandled,
    IntentRecognized,
    IntentTrainingComplete,
    IntentTrainingFailed,
    ListenForCommand,
    ListenForWakeWord,
    MqttPublish,
    MqttSubscribe,
    MqttMessage,
    PlayWavData,
    PlayWavFile,
    Problems,
    ProfileTrainingComplete,
    ProfileTrainingFailed,
    Ready,
    RecognizeIntent,
    SpeakSentence,
    SpeakWord,
    StartRecordingToBuffer,
    StopListeningForWakeWord,
    StopRecordingToBuffer,
    TestMicrophones,
    TrainIntent,
    TrainProfile,
    TranscribeWav,
    VoiceCommand,
    WakeWordDetected,
    WakeWordNotDetected,
    WavPlayed,
    WavTranscription,
    ActivateWakeWordDetection,
    DeactivateWakeWordDetection,
)
from rhasspy.intent import get_recognizer_class
from rhasspy.intent_handler import get_intent_handler_class
from rhasspy.intent_train import get_intent_trainer_class
from rhasspy.stt import get_decoder_class
from rhasspy.stt_train import get_speech_trainer_class
from rhasspy.train import train_profile
from rhasspy.tts import get_speech_class
from rhasspy.utils import buffer_to_wav
from rhasspy.wake import get_wake_class

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

        # MQTT site id and subscription topics
        self.site_id: str = "default"
        self.hotword_toggle_on_topic = "hermes/hotword/toggleOn"
        self.hotword_toggle_off_topic = "hermes/hotword/toggleOff"

        # Text to speech
        self.speech_class: Optional[Type] = None
        self._speech: Optional[RhasspyActor] = None
        self.speech_trainer_class: Optional[Type] = None
        self._speech_trainer: Optional[RhasspyActor] = None

        # Load timeout
        self.timeout_sec: Optional[float] = None

        # Timeout when listening for voice commands
        self.listen_timeout_sec: Optional[float] = None
        self.listen_entities: List[Dict[str, Any]] = []

        # Result of training
        self.training_receiver: Optional[RhasspyActor] = None

        # Loading actors
        self.wait_actors: Dict[str, RhasspyActor] = {}

        # Wake word
        self.wake_class: Optional[Type] = None
        self._wake: Optional[RhasspyActor] = None
        self.wake_receiver: Optional[RhasspyActor] = None
        self.wake_active: bool = False

        # Name of most recently detected wake word
        self.wake_detected_name: Optional[str] = None

        # Word pronunciations
        self.word_pronouncer_class: Optional[Type] = None
        self._word_pronouncer: Optional[RhasspyActor] = None

        # Webhooks
        self.webhooks: Dict[str, List[str]] = {}

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
        self.wake_active = self.profile.get("rhasspy.listen_on_start", False)

        # Load web hooks
        self.webhooks = self.profile.get("webhooks", {})
        for hook_event in self.webhooks:
            # Convert all URLs to lists
            hook_url = self.webhooks[hook_event]
            if isinstance(hook_url, str):
                self.webhooks[hook_event] = [hook_url]

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
        assert self.mqtt is not None
        self.actors["mqtt"] = self.mqtt

        self.send(
            self.mqtt, ConfigureEvent(self.profile, preload=self.preload, **self.actors)
        )

        if self.timeout_sec is not None:
            self._logger.debug(
                "Loading...will time out after %s second(s)", self.timeout_sec
            )
            self.wakeupAfter(timedelta(seconds=self.timeout_sec))

        # Subscribe to MQTT topics
        self.send(self.mqtt, MqttSubscribe(self.hotword_toggle_on_topic))
        self.send(self.mqtt, MqttSubscribe(self.hotword_toggle_off_topic))

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

            if not self.wait_actors:
                self._logger.debug("Actors loaded")
                self.transition("ready")

                # Inform all actors that we're ready
                for actor in self.actors.values():
                    self.send(actor, Ready())

                # Inform parent actor that we're ready
                if self.send_ready:
                    self.send(self._parent, Ready())
        elif isinstance(message, WakeupMessage):
            wait_names = list(self.wait_actors)
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
        self.handle = True
        if self.wake_active:
            self._logger.info("Automatically listening for wake word")
            self.transition("asleep")
            self.send(self.wake, ListenForWakeWord())

    def in_ready(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in ready state."""
        start_listening:bool = False

        if isinstance(message, ActivateWakeWordDetection):
            self.set_wake_active(True)
            start_listening = True
        elif isinstance(message, ListenForWakeWord):
            start_listening = True
        else:
            self.handle_any(message, sender)

        if start_listening:
            self._logger.info("Listening for wake word")
            self.wake_receiver = message.receiver or sender
            self.send(self.wake, ListenForWakeWord())
            self.transition("asleep")

    def to_asleep(self, from_state: str) -> None:
        """Transition to asleep state."""
        self.listen_entities = []

    def in_asleep(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in asleep state."""
        if isinstance(message, WakeWordDetected):
            self._logger.debug("Awake!")
            self.wake_detected_name = message.name
            self.transition("awake")
            if self.wake_receiver is not None:
                self.send(self.wake_receiver, message)

            awake_hooks = self.webhooks.get("awake", [])
            if awake_hooks:
                hook_json = {"wakewordId": message.name, "siteId": self.site_id}
                for hook_url in awake_hooks:
                    self._logger.debug("POST-ing to %s", hook_url)
                    requests.post(hook_url, json=hook_json)
        elif isinstance(message, WakeWordNotDetected):
            self._logger.debug("Wake word NOT detected. Staying asleep.")
            self.transition("ready")
            if self.wake_receiver is not None:
                self.send(self.wake_receiver, message)
        elif isinstance(message, DeactivateWakeWordDetection):
            self.set_wake_active(False)
            self.transition("ready")
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
        self.send(
            self.command,
            ListenForCommand(
                self.myAddress, handle=self.handle, timeout=self.listen_timeout_sec
            ),
        )

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
                    "wakeId": self.wake_detected_name or "",
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

            if not pydash.get(message.intent, "intent.name", ""):
                if self.profile.get("intent.error_sound", True):
                    # Play error sound when not recognized
                    wav_path = os.path.expandvars(
                        self.profile.get("sounds.error", None)
                    )
                    if wav_path is not None:
                        self.send(self.player, PlayWavFile(wav_path))

            if self.recorder_class == HTTPAudioRecorder:
                # Forward to audio recorder
                self.send(self.recorder, message)

            message.intent["wakeId"] = self.wake_detected_name or ""
            message.intent["siteId"] = self.site_id

            # Augment with extra entities
            entities = message.intent.get("entities", [])
            entities.extend(self.listen_entities)
            message.intent["entities"] = entities

            slots = message.intent.get("slots", {})
            for entity_dict in self.listen_entities:
                slots[entity_dict["entity"]] = entity_dict["value"]

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

            code, errors = train_profile(Path(self.profile.read_path()), self.profile)
            if code != 0:
                raise Exception("\n".join(errors))

            self.transition("training_intent")

            intent_graph_path = self.profile.read_path(
                self.profile.get("intent.fsticuffs.intent_graph", "intent.json")
            )

            with open(intent_graph_path, "r") as graph_file:
                json_graph = json.load(graph_file)
                intent_graph = rhasspynlu.json_to_graph(json_graph)
                self.send(self.intent_trainer, TrainIntent(intent_graph))
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

            if not self.wait_actors:
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
            self.handle = message.handle
            self.intent_receiver = message.receiver or sender
            self.listen_timeout_sec = message.timeout
            self.listen_entities = message.entities
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
            self.send(
                self.speech,
                SpeakSentence(
                    message.sentence,
                    receiver=sender,
                    play=message.play,
                    voice=message.voice,
                    language=message.language,
                    siteId=message.siteId,
                ),
            )
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
        elif isinstance(message, ActivateWakeWordDetection):
            # activate wake word detection
            self.set_wake_active(True)
        elif isinstance(message, DeactivateWakeWordDetection):
            # deactivate wake word detection
            self.set_wake_active(False)
        elif isinstance(message, MqttMessage):
            # handle mqtt message
            self.handle_mqtt_message(message, sender)
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
        topic = f"rhasspy/{self.profile.name}/transition/{message.name}"
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
            test_path = f"microphone.{recorder_system}.test_chunk_size"
            chunk_size = int(self.profile.get(test_path, 1024))

            assert recorder_class is not None
            test_mics = recorder_class.test_microphones(chunk_size)  # type: ignore
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

    def handle_mqtt_message(self, message: MqttMessage, sender: RhasspyActor) -> None:
        """Handle MQTT message."""
        if message.topic == self.hotword_toggle_on_topic:
            payload_json = json.loads(message.payload)
            if payload_json.get("siteId", "default") == self.site_id:
                # activate wake word detection
                self.send(self, ActivateWakeWordDetection())
        elif message.topic == self.hotword_toggle_off_topic:
            payload_json = json.loads(message.payload)
            if payload_json.get("siteId", "default") == self.site_id:
                # deactivate wake word detection
                self.send(self, DeactivateWakeWordDetection())


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

        actor_names = list(self.wait_actors)
        self._logger.debug("Actors created. Waiting for %s to start.", actor_names)

    def set_wake_active(self, active:bool) -> None:
        """Activate/Deactivate the wake word detection"""
        if self.wake_active != active:
            self.wake_active = active
            if active:
                self._logger.info("Activated wake word detection")
            else:
                self._logger.info("Deactivated wake word detection")
