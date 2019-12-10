"""Support for voice command recording."""
import json
import math
import os
import subprocess
import threading
import uuid
from datetime import timedelta
from typing import Any, Dict, List, Optional, Type

import webrtcvad

from rhasspy.actor import RhasspyActor, WakeupMessage
from rhasspy.audio_recorder import AudioData, StartStreaming, StopStreaming
from rhasspy.mqtt import MqttMessage, MqttSubscribe
from rhasspy.utils import convert_wav

# -----------------------------------------------------------------------------


class ListenForCommand:
    """Tell Rhasspy to listen for a voice command."""

    def __init__(
        self,
        receiver: Optional[RhasspyActor] = None,
        handle: bool = True,
        timeout: Optional[float] = None,
        entities: List[Dict[str, Any]] = None,
    ) -> None:
        self.receiver = receiver
        self.handle = handle
        self.timeout = timeout
        self.entities = entities or []


class VoiceCommand:
    """Response to ListenForCommand."""

    def __init__(self, data: bytes, timeout: bool = False, handle: bool = True) -> None:
        self.data = data
        self.timeout = timeout
        self.handle = handle


# -----------------------------------------------------------------------------


def get_command_class(system: str) -> Type[RhasspyActor]:
    """Return class type for profile command listener."""
    assert system in ["dummy", "webrtcvad", "command", "oneshot", "hermes"], (
        "Unknown voice command system: %s" % system
    )

    if system == "webrtcvad":
        # Use WebRTCVAD locally
        return WebrtcvadCommandListener

    if system == "command":
        # Use external program
        return CommandCommandListener

    if system == "oneshot":
        # Use one-shot listener locally
        return OneShotCommandListener

    if system == "hermes":
        # Use MQTT listener
        return HermesCommandListener

    # Use dummy listener as a fallback
    return DummyCommandListener


# -----------------------------------------------------------------------------


class DummyCommandListener(RhasspyActor):
    """Always sends an empty voice command."""

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, ListenForCommand):
            self.send(message.receiver or sender, VoiceCommand(bytes()))


# -----------------------------------------------------------------------------
# webrtcvad based voice command listener
# https://github.com/wiseman/py-webrtcvad
# -----------------------------------------------------------------------------


class WebrtcvadCommandListener(RhasspyActor):
    """Listens to microphone for voice commands bracketed by silence."""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.after_phrase: bool = False
        self.buffer: bytes = bytes()
        self.buffer_count: int = 0
        self.chunk: bytes = bytes()
        self.chunk_size: int = 960
        self.handle = True
        self.in_phrase: bool = False
        self.min_phrase_buffers: int = 0
        self.min_sec: float = 2
        self.receiver: Optional[RhasspyActor] = None
        self.recorder: Optional[RhasspyActor] = None
        self.sample_rate: int = 16000
        self.seconds_per_buffer: float = 0
        self.settings: Dict[str, Any] = {}
        self.silence_buffers: int = 0
        self.silence_sec: float = 0.5
        self.speech_buffers: int = 5
        self.speech_buffers_left: int = 0
        self.throwaway_buffers: int = 10
        self.throwaway_buffers_left: int = 0
        self.timeout_sec: float = 30
        self.vad_mode: int = 0
        self.vad: Optional[webrtcvad.Vad] = None

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.recorder = self.config["recorder"]

        self.settings = self.profile.get("command.webrtcvad")
        self.sample_rate = self.settings["sample_rate"]  # 16Khz
        self.chunk_size = self.settings["chunk_size"]  # 10,20,30 ms
        self.vad_mode = self.settings["vad_mode"]  # 0-3 (aggressiveness)
        self.min_sec = self.settings["min_sec"]  # min seconds that command must last
        self.silence_sec = self.settings[
            "silence_sec"
        ]  # min seconds of silence after command
        self.timeout_sec = self.settings[
            "timeout_sec"
        ]  # max seconds that command can last
        self.throwaway_buffers = self.settings["throwaway_buffers"]
        self.speech_buffers = self.settings["speech_buffers"]

        self.seconds_per_buffer = self.chunk_size / self.sample_rate

        self.vad = webrtcvad.Vad()
        assert self.vad is not None
        self.vad.set_mode(self.vad_mode)

        self.handle = True

        self.transition("loaded")

    # -------------------------------------------------------------------------

    def in_loaded(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in loaded state."""
        if isinstance(message, ListenForCommand):
            if message.timeout is not None:
                # Use message timeout
                self.timeout_sec = message.timeout
            else:
                # Use default timeout
                self.timeout_sec = self.settings["timeout_sec"]

            self._logger.debug("Will timeout in %s second(s)", self.timeout_sec)
            self.receiver = message.receiver or sender
            self.transition("listening")
            self.handle = message.handle
            self.send(self.recorder, StartStreaming(self.myAddress))

    def to_listening(self, from_state: str) -> None:
        """Transition to listening state."""
        self.wakeupAfter(timedelta(seconds=self.timeout_sec))

        # Reset state
        self.chunk = bytes()
        self.silence_buffers = int(
            math.ceil(self.silence_sec / self.seconds_per_buffer)
        )
        self.min_phrase_buffers = int(math.ceil(self.min_sec / self.seconds_per_buffer))
        self.throwaway_buffers_left = self.throwaway_buffers
        self.speech_buffers_left = self.speech_buffers
        self.in_phrase = False
        self.after_phrase = False
        self.buffer_count = 0

    def in_listening(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in listening state."""
        if isinstance(message, WakeupMessage):
            # Timeout
            self._logger.warning("Timeout")
            self.send(self.recorder, StopStreaming(self.myAddress))
            self.send(
                self.receiver,
                VoiceCommand(self.buffer or bytes(), timeout=True, handle=self.handle),
            )

            self.buffer = bytes()
            self.transition("loaded")
        elif isinstance(message, AudioData):
            self.chunk += message.data
            if len(self.chunk) >= self.chunk_size:
                # Ensure audio data is properly chunked (for webrtcvad)
                data = self.chunk[: self.chunk_size]
                self.chunk = self.chunk[self.chunk_size :]

                # Process chunk
                finished = self.process_data(data)

                if finished:
                    # Stop recording
                    self.send(self.recorder, StopStreaming(self.myAddress))

                    # Response
                    self.send(
                        self.receiver,
                        VoiceCommand(self.buffer, timeout=False, handle=self.handle),
                    )

                    self.buffer = bytes()
                    self.transition("loaded")

    def to_stopped(self, from_state: str) -> None:
        """Transition to stopped state."""
        # Stop recording
        self.send(self.recorder, StopStreaming(self.myAddress))

    # -------------------------------------------------------------------------

    def process_data(self, data: bytes) -> bool:
        """Process a single audio chunk."""
        finished = False

        self.buffer_count += 1

        # Throw away first N buffers (noise)
        if self.throwaway_buffers_left > 0:
            self.throwaway_buffers_left -= 1
            return False

        # Detect speech in chunk
        assert self.vad is not None
        is_speech = self.vad.is_speech(data, self.sample_rate)

        if is_speech and self.speech_buffers_left > 0:
            self.speech_buffers_left -= 1
        elif is_speech and not self.in_phrase:
            # Start of phrase
            self._logger.debug("Voice command started")
            self.in_phrase = True
            self.after_phrase = False
            self.min_phrase_buffers = int(
                math.ceil(self.min_sec / self.seconds_per_buffer)
            )
            self.buffer = data
        elif self.in_phrase and (self.min_phrase_buffers > 0):
            # In phrase, before minimum seconds
            self.buffer += data
            self.min_phrase_buffers -= 1
        elif self.in_phrase and is_speech:
            # In phrase, after minimum seconds
            self.buffer += data
        elif not is_speech:
            # Outside of speech
            if not self.in_phrase:
                # Reset
                self.speech_buffers_left = self.speech_buffers
            elif self.after_phrase and (self.silence_buffers > 0):
                # After phrase, before stop
                self.silence_buffers -= 1
                self.buffer += data
            elif self.after_phrase and (self.silence_buffers <= 0):
                # Phrase complete
                self._logger.debug("Voice command finished")
                finished = True
                self.buffer += data
            elif self.in_phrase and (self.min_phrase_buffers <= 0):
                # Transition to after phrase
                self.after_phrase = True
                self.silence_buffers = int(
                    math.ceil(self.silence_sec / self.seconds_per_buffer)
                )

        return finished


# -----------------------------------------------------------------------------
# Command-line Voice Command Listener
# -----------------------------------------------------------------------------


class CommandCommandListener(RhasspyActor):
    """Command-line based voice command listener"""

    def __init__(self):
        RhasspyActor.__init__(self)
        self.receiver: Optional[RhasspyActor] = None
        self.command: List[str] = []
        self.listen_proc = None

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        program = os.path.expandvars(self.profile.get("command.command.program"))
        arguments = [
            os.path.expandvars(str(a))
            for a in self.profile.get("command.command.arguments", [])
        ]

        self.command = [program] + arguments

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, ListenForCommand):
            self.receiver = message.receiver or sender
            self.listen_proc = subprocess.Popen(self.command, stdout=subprocess.PIPE)

            def post_result() -> None:
                # STDOUT -> WAV data
                try:
                    wav_data, _ = self.listen_proc.communicate()
                except Exception:
                    wav_data = bytes()
                    self._logger.exception("post_result")

                # Actor will forward
                audio_data = convert_wav(wav_data)
                self.send(
                    self.myAddress, VoiceCommand(audio_data, handle=message.handle)
                )

            self.transition("listening")

            # Wait for program in a separate thread
            threading.Thread(target=post_result, daemon=True).start()

    def in_listening(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in listening state."""
        if isinstance(message, VoiceCommand):
            # Pass downstream to receiver
            self.send(self.receiver, message)
            self.transition("started")


# -----------------------------------------------------------------------------
# One Shot Command Listener
# -----------------------------------------------------------------------------


class OneShotCommandListener(RhasspyActor):
    """Assumes entire voice command comes in first audio data"""

    def __init__(self):
        RhasspyActor.__init__(self)
        self.receiver: Optional[RhasspyActor] = None
        self.recorder: Optional[RhasspyActor] = None
        self.timeout_sec: float = 30
        self.handle: bool = False

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.recorder = self.config["recorder"]
        self.timeout_sec = self.profile.get("command.oneshot.timeout_sec", 30)

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, ListenForCommand):
            self.receiver = message.receiver or sender
            self.handle = message.handle
            self.transition("listening")

            if message.timeout is not None:
                # Use message timeout
                timeout_sec = message.timeout
            else:
                # Use default timeout
                timeout_sec = self.timeout_sec

            self.send(self.recorder, StartStreaming(self.myAddress))
            self.wakeupAfter(timedelta(seconds=timeout_sec))

    def in_listening(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in listening state."""
        if isinstance(message, AudioData):
            assert self.receiver is not None
            self.transition("started")
            self.send(self.recorder, StopStreaming(self.myAddress))
            self._logger.debug("Received %s byte(s) of audio data", len(message.data))
            self.send(self.receiver, VoiceCommand(message.data, self.handle))
        elif isinstance(message, WakeupMessage):
            # Timeout
            self._logger.warning("Timeout")
            self.send(self.recorder, StopStreaming(self.myAddress))
            self.send(
                self.receiver, VoiceCommand(bytes(), timeout=True, handle=self.handle)
            )

            self.transition("started")


# -----------------------------------------------------------------------------
# MQTT-Based Command Listener (Hermes Protocol)
# https://docs.snips.ai/ressources/hermes-protocol
# -----------------------------------------------------------------------------


class HermesCommandListener(RhasspyActor):
    """Records between startListening/stopListening messages."""

    def __init__(self):
        RhasspyActor.__init__(self)
        self.receiver: Optional[RhasspyActor] = None
        self.recorder: Optional[RhasspyActor] = None
        self.mqtt: Optional[RhasspyActor] = None
        self.handle: bool = False
        self.buffer: bytes = bytes()
        self.timeout_id: str = ""
        self.timeout_sec: float = 30
        self.site_ids: List[str] = []
        self.start_topic = "hermes/asr/startListening"
        self.stop_topic = "hermes/asr/stopListening"

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.recorder = self.config["recorder"]
        self.mqtt = self.config["mqtt"]
        self.timeout_sec = self.profile.get("command.hermes.timeout_sec", 30)

        # Subscribe to MQTT topics
        self.site_ids = self.profile.get("mqtt.site_id", "default").split(",")
        self.send(self.mqtt, MqttSubscribe(self.start_topic))
        self.send(self.mqtt, MqttSubscribe(self.stop_topic))

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, ListenForCommand):
            self.buffer = bytes()
            self.receiver = message.receiver or sender
            self.handle = message.handle
            self.transition("listening")

            if message.timeout is not None:
                # Use message timeout
                timeout_sec = message.timeout
            else:
                # Use default timeout
                timeout_sec = self.timeout_sec

            self.send(self.recorder, StartStreaming(self.myAddress))
            self.timeout_id = str(uuid.uuid4())
            self.wakeupAfter(timedelta(seconds=timeout_sec), payload=self.timeout_id)
        elif isinstance(message, MqttMessage):
            # startListening
            if message.topic == self.start_topic:
                payload_json = json.loads(message.payload)
                if payload_json.get("siteId", "default") in self.site_ids:
                    # Wake up Rhasspy
                    self._logger.debug("Received startListening")
                    self.send(self._parent, ListenForCommand())

    def in_listening(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in listening state."""
        if isinstance(message, AudioData):
            self.buffer += message.data
        elif isinstance(message, WakeupMessage):
            if message.payload == self.timeout_id:
                # Timeout
                self._logger.warning("Timeout")
                self.send(self.recorder, StopStreaming(self.myAddress))
                self.send(
                    self.receiver,
                    VoiceCommand(self.buffer, timeout=True, handle=self.handle),
                )
                self.transition("started")
        elif isinstance(message, MqttMessage):
            if message.topic == self.stop_topic:
                # stopListening
                payload_json = json.loads(message.payload)
                if payload_json.get("siteId", "default") in self.site_ids:
                    self._logger.debug("Received stopListening")
                    self.send(self.recorder, StopStreaming(self.myAddress))
                    self.send(
                        self.receiver, VoiceCommand(self.buffer, handle=self.handle)
                    )
                    self.transition("started")
