"""Support for microphone and audio streaming input."""
import audioop
import io
import json
import re
import shlex
import subprocess
import sys
import threading
import time
import wave
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, List, Optional, Type

from rhasspy.actor import RhasspyActor
from rhasspy.intent import IntentRecognized
from rhasspy.mqtt import MqttMessage, MqttSubscribe
from rhasspy.stt import WavTranscription
from rhasspy.utils import convert_wav

# -----------------------------------------------------------------------------
# Events
# -----------------------------------------------------------------------------


class AudioData:
    """Raw 16-bit 16Khz audio data."""

    def __init__(self, data: bytes, **kwargs: Any) -> None:
        self.data = data
        self.info = kwargs


class StartStreaming:
    """Tells microphone to begin recording. Emits AudioData chunks."""

    def __init__(self, receiver: Optional[RhasspyActor] = None) -> None:
        self.receiver = receiver


class StopStreaming:
    """Tells microphone to stop recording."""

    def __init__(self, receiver: Optional[RhasspyActor] = None) -> None:
        self.receiver = receiver


class StartRecordingToBuffer:
    """Tells microphone to record audio data to named buffer."""

    def __init__(self, buffer_name: str) -> None:
        self.buffer_name = buffer_name


class StopRecordingToBuffer:
    """Tells microphone to stop recording to buffer and emit AudioData."""

    def __init__(
        self, buffer_name: str, receiver: Optional[RhasspyActor] = None
    ) -> None:
        self.buffer_name = buffer_name
        self.receiver = receiver


# -----------------------------------------------------------------------------


def get_microphone_class(system: str) -> Type[RhasspyActor]:
    """Get class type for profile microphone."""
    assert system in [
        "arecord",
        "pyaudio",
        "dummy",
        "hermes",
        "stdin",
        "http",
        "gstreamer",
    ], ("Unknown microphone system: %s" % system)

    if system == "arecord":
        # Use arecord locally
        return ARecordAudioRecorder

    if system == "pyaudio":
        # Use PyAudio locally
        return PyAudioRecorder

    if system == "hermes":
        # Use MQTT
        return HermesAudioRecorder

    if system == "stdin":
        # Use STDIN
        return StdinAudioRecorder

    if system == "http":
        # Use HTTP
        return HTTPAudioRecorder

    if system == "gstreamer":
        # Use GStreamer
        return GStreamerAudioRecorder

    # Use dummy recorder as a fallback
    return DummyAudioRecorder


# -----------------------------------------------------------------------------
# Dummy audio recorder
# -----------------------------------------------------------------------------


class DummyAudioRecorder(RhasspyActor):
    """Does not record. Returns only empty audio buffers."""

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, StopRecordingToBuffer):
            # Return empty buffer
            self._logger.warning("Dummy microphone system only returns empty buffers!")
            self.send(message.receiver or sender, AudioData(bytes()))

    @classmethod
    def get_microphones(cls) -> Dict[Any, Any]:
        """Get description of available microphones."""
        return {}

    @classmethod
    def test_microphones(cls, chunk_size: int) -> Dict[Any, Any]:
        """Test microphones and return results."""
        return {}


# -----------------------------------------------------------------------------
# PyAudio based audio recorder
# https://people.csail.mit.edu/hubert/pyaudio/
# -----------------------------------------------------------------------------


class PyAudioRecorder(RhasspyActor):
    """Records from microphone using pyaudio"""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.mic = None
        self.audio = None
        self.receivers: List[RhasspyActor] = []
        self.buffers: Dict[str, bytes] = defaultdict(bytes)
        self.device_index = None
        self.frames_per_buffer = 480

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.device_index = self.config.get("device") or self.profile.get(
            "microphone.pyaudio.device"
        )

        if self.device_index is not None:
            try:
                self.device_index = int(self.device_index)
            except Exception:
                self.device_index = -1

            if self.device_index < 0:
                # Default device
                self.device_index = None

        self.frames_per_buffer = int(
            self.profile.get("microphone.pyaudio.frames_per_buffer", 480)
        )

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, StartStreaming):
            self.receivers.append(message.receiver or sender)
            self.transition("recording")
        elif isinstance(message, StartRecordingToBuffer):
            self.buffers[message.buffer_name] = bytes()
            self.transition("recording")

    def to_recording(self, from_state: str) -> None:
        """Transition to recording state."""
        try:
            import pyaudio

            # Start audio system
            def stream_callback(data, frame_count, time_info, status):
                if len(data) > 0:
                    # Send to this actor to avoid threading issues
                    self.send(self.myAddress, AudioData(data))

                return (data, pyaudio.paContinue)

            self.audio = pyaudio.PyAudio()
            assert self.audio is not None
            data_format = self.audio.get_format_from_width(2)  # 16-bit
            self.mic = self.audio.open(
                format=data_format,
                channels=1,
                rate=16000,
                input_device_index=self.device_index,
                input=True,
                stream_callback=stream_callback,
                frames_per_buffer=self.frames_per_buffer,
            )

            assert self.mic is not None
            self.mic.start_stream()
            self._logger.debug(
                "Recording from microphone (PyAudio, device=%s)", self.device_index
            )
        except Exception:
            self._logger.exception("to_recording")
            self.transition("started")

    # -------------------------------------------------------------------------

    def in_recording(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in recording state."""
        if isinstance(message, AudioData):
            # Forward to subscribers
            for receiver in self.receivers:
                self.send(receiver, message)

            # Append to buffers
            for buffer_name in self.buffers:
                self.buffers[buffer_name] += message.data
        elif isinstance(message, StartStreaming):
            self.receivers.append(message.receiver or sender)
        elif isinstance(message, StartRecordingToBuffer):
            self.buffers[message.buffer_name] = bytes()
        elif isinstance(message, StopStreaming):
            if message.receiver is None:
                # Clear all receivers
                self.receivers.clear()
            else:
                self.receivers.remove(message.receiver)
        elif isinstance(message, StopRecordingToBuffer):
            if message.buffer_name is None:
                # Clear all buffers
                self.buffers.clear()
            else:
                # Respond with buffer
                buffer = self.buffers.pop(message.buffer_name, bytes())
                self.send(message.receiver or sender, AudioData(buffer))

        # Check to see if anyone is still listening
        if (len(self.receivers) == 0) and (len(self.buffers) == 0):
            # Terminate audio recording
            if self.mic is not None:
                self.mic.stop_stream()
                self.mic = None

            if self.audio is not None:
                self.audio.terminate()
                self.audio = None

            self.transition("started")
            self._logger.debug("Stopped recording from microphone (PyAudio)")

    def to_stopped(self, from_state: str) -> None:
        """Transition to stopped state."""
        try:
            if self.mic is not None:
                self.mic.stop_stream()
                self.mic = None
                self._logger.debug("Stopped recording from microphone (PyAudio)")

            if self.audio is not None:
                self.audio.terminate()
                self.audio = None
        except Exception:
            self._logger.exception("to_stopped")

    # -------------------------------------------------------------------------

    @classmethod
    def get_microphones(cls) -> Dict[Any, Any]:
        """Get description of available microphones."""
        import pyaudio

        mics: Dict[Any, Any] = {}
        audio = pyaudio.PyAudio()
        default_name = audio.get_default_input_device_info().get("name")
        for i in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(i)
            mics[i] = info["name"]

            if mics[i] == default_name:
                mics[i] = mics[i] + "*"

        audio.terminate()

        return mics

    # -------------------------------------------------------------------------

    @classmethod
    def test_microphones(cls, chunk_size: int) -> Dict[Any, Any]:
        """Test microphones and return results."""
        import pyaudio

        # Thanks to the speech_recognition library!
        # https://github.com/Uberi/speech_recognition/blob/master/speech_recognition/__init__.py
        result = {}
        audio = pyaudio.PyAudio()
        try:
            default_name = audio.get_default_input_device_info().get("name")
            for device_index in range(audio.get_device_count()):
                device_info = audio.get_device_info_by_index(device_index)
                device_name = device_info.get("name")
                if device_name == default_name:
                    device_name = device_name + "*"

                try:
                    # read audio
                    pyaudio_stream = audio.open(
                        input_device_index=device_index,
                        channels=1,
                        format=pyaudio.paInt16,
                        rate=16000,
                        input=True,
                    )
                    try:
                        buffer = pyaudio_stream.read(chunk_size)
                        if not pyaudio_stream.is_stopped():
                            pyaudio_stream.stop_stream()
                    finally:
                        pyaudio_stream.close()
                except Exception:
                    result[device_index] = "%s (error)" % device_name
                    continue

                # compute RMS of debiased audio
                energy = -audioop.rms(buffer, 2)
                energy_bytes = bytes([energy & 0xFF, (energy >> 8) & 0xFF])
                debiased_energy = audioop.rms(
                    audioop.add(buffer, energy_bytes * (len(buffer) // 2), 2), 2
                )

                if debiased_energy > 30:  # probably actually audio
                    result[device_index] = "%s (working!)" % device_name
                else:
                    result[device_index] = "%s (no sound)" % device_name
        finally:
            audio.terminate()

        return result


# -----------------------------------------------------------------------------
# ARecord based audio recorder
# -----------------------------------------------------------------------------


class ARecordAudioRecorder(RhasspyActor):
    """Records from microphone using arecord"""

    def __init__(self) -> None:
        # Chunk size is set to 30 ms for webrtcvad
        RhasspyActor.__init__(self)
        self.record_proc: Any = None
        self.receivers: List[RhasspyActor] = []
        self.buffers: Dict[str, bytes] = {}
        self.recording_thread: Any = None
        self.is_recording: bool = True
        self.device_name: Optional[str] = None
        self.chunk_size: int = 960

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.device_name = self.config.get("device") or self.profile.get(
            "microphone.arecord.device"
        )

        if self.device_name is not None:
            self.device_name = str(self.device_name)
            if len(self.device_name) == 0:
                self.device_name = None

        self.chunk_size = int(
            self.profile.get("microphone.arecord.chunk_size", self.chunk_size)
        )

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, StartStreaming):
            self.receivers.append(message.receiver or sender)
            self.transition("recording")
        elif isinstance(message, StartRecordingToBuffer):
            self.buffers[message.buffer_name] = bytes()
            self.transition("recording")

    def to_recording(self, from_state: str) -> None:
        """Transition to recording state."""
        # 16-bit 16Khz mono WAV
        arecord_cmd = [
            "arecord",
            "-q",
            "-r",
            "16000",
            "-f",
            "S16_LE",
            "-c",
            "1",
            "-t",
            "raw",
        ]

        if self.device_name is not None:
            # Use specific ALSA device
            arecord_cmd.extend(["-D", self.device_name])

        self._logger.debug(arecord_cmd)

        def process_data() -> None:
            self.record_proc = subprocess.Popen(arecord_cmd, stdout=subprocess.PIPE)
            assert self.record_proc is not None
            while self.is_recording:
                # Pull from process STDOUT
                data = self.record_proc.stdout.read(self.chunk_size)
                if len(data) > 0:
                    # Send to this actor to avoid threading issues
                    self.send(self.myAddress, AudioData(data))
                else:
                    # Avoid 100% CPU usage
                    time.sleep(0.01)

        # Start recording
        try:
            self.is_recording = True
            self.recording_thread = threading.Thread(target=process_data, daemon=True)
            assert self.recording_thread is not None
            self.recording_thread.start()

            self._logger.debug("Recording from microphone (arecord)")
        except Exception:
            self._logger.exception("to_recording")
            self.is_recording = False
            self.recording_thread = None
            self.transition("started")

    def in_recording(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in recording state."""
        if isinstance(message, AudioData):
            # Forward to subscribers
            for receiver in self.receivers:
                self.send(receiver, message)

            # Append to buffers
            for buffer_name in self.buffers:
                self.buffers[buffer_name] += message.data
        elif isinstance(message, StartStreaming):
            self.receivers.append(message.receiver or sender)
        elif isinstance(message, StartRecordingToBuffer):
            self.buffers[message.buffer_name] = bytes()
        elif isinstance(message, StopStreaming):
            if message.receiver is None:
                # Clear all receivers
                self.receivers.clear()
            else:
                self.receivers.remove(message.receiver)
        elif isinstance(message, StopRecordingToBuffer):
            if message.buffer_name is None:
                # Clear all buffers
                self.buffers.clear()
            else:
                # Respond with buffer
                buffer = self.buffers.pop(message.buffer_name, bytes())
                self.send(message.receiver or sender, AudioData(buffer))

        # Check to see if anyone is still listening
        if (len(self.receivers) == 0) and (len(self.buffers) == 0):
            # Terminate audio recording
            self.is_recording = False
            self.record_proc.terminate()
            self.record_proc = None
            self.transition("started")
            self._logger.debug("Stopped recording from microphone (arecord)")

    def to_stopped(self, from_state: str) -> None:
        """Transition to stopped state."""
        if self.is_recording:
            self.is_recording = False
            if self.record_proc is not None:
                self.record_proc.terminate()
            self._logger.debug("Stopped recording from microphone (arecord)")

    # -------------------------------------------------------------------------

    @classmethod
    def get_microphones(cls) -> Dict[Any, Any]:
        """Get description of available microphones."""
        output = subprocess.check_output(["arecord", "-L"]).decode().splitlines()

        mics: Dict[Any, Any] = {}
        name, description = None, None

        # Parse output of arecord -L
        first_mic = True
        for line in output:
            line = line.rstrip()
            if re.match(r"^\s", line):
                description = line.strip()
                if first_mic:
                    description = description + "*"
                    first_mic = False
            else:
                if name is not None:
                    mics[name] = description

                name = line.strip()

        return mics

    # -------------------------------------------------------------------------

    @classmethod
    def test_microphones(cls, chunk_size: int) -> Dict[Any, Any]:
        """Test microphones and return results."""
        # Thanks to the speech_recognition library!
        # https://github.com/Uberi/speech_recognition/blob/master/speech_recognition/__init__.py
        mics = ARecordAudioRecorder.get_microphones()
        result = {}
        for device_id, device_name in mics.items():
            try:
                # read audio
                arecord_cmd = [
                    "arecord",
                    "-q",
                    "-D",
                    device_id,
                    "-r",
                    "16000",
                    "-f",
                    "S16_LE",
                    "-c",
                    "1",
                    "-t",
                    "raw",
                ]

                proc = subprocess.Popen(arecord_cmd, stdout=subprocess.PIPE)
                buffer = proc.stdout.read(chunk_size * 2)
                proc.terminate()
            except Exception:
                result[device_id] = "%s (error)" % device_name
                continue

            # compute RMS of debiased audio
            energy = -audioop.rms(buffer, 2)
            energy_bytes = bytes([energy & 0xFF, (energy >> 8) & 0xFF])
            debiased_energy = audioop.rms(
                audioop.add(buffer, energy_bytes * (len(buffer) // 2), 2), 2
            )

            if debiased_energy > 30:  # probably actually audio
                result[device_id] = "%s (working!)" % device_name
            else:
                result[device_id] = "%s (no sound)" % device_name

        return result


# -----------------------------------------------------------------------------
# MQTT based audio "recorder" for Snips.AI Hermes Protocol
# https://docs.snips.ai/ressources/hermes-protocol
# -----------------------------------------------------------------------------


class HermesAudioRecorder(RhasspyActor):
    """Receives audio data from MQTT via Hermes protocol."""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.receivers: List[RhasspyActor] = []
        self.buffers: Dict[str, bytes] = {}
        self.mqtt: Optional[RhasspyActor] = None
        self.site_ids: List[str] = []
        self.site_id = "default"
        self.topic_audio_frame = ""

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.mqtt = self.config["mqtt"]
        self.site_ids = self.profile.get("mqtt.site_id", "default").split(",")
        if len(self.site_ids) > 0:
            self.site_id = self.site_ids[0]
        else:
            self.site_id = "default"
        self.topic_audio_frame = "hermes/audioServer/%s/audioFrame" % self.site_id
        self.send(self.mqtt, MqttSubscribe(self.topic_audio_frame))

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, StartStreaming):
            self.receivers.append(message.receiver or sender)
            self.transition("recording")
        elif isinstance(message, StartRecordingToBuffer):
            self.buffers[message.buffer_name] = bytes()
            self.transition("recording")

    def to_recording(self, from_state: str) -> None:
        """Transiiton to recording state."""
        self._logger.debug("Recording from microphone (hermes)")

    def in_recording(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in recording state."""
        if isinstance(message, MqttMessage):
            if message.topic == self.topic_audio_frame:
                # Extract audio data
                with io.BytesIO(message.payload) as wav_buffer:
                    with wave.open(wav_buffer, mode="rb") as wav_file:
                        rate, width, channels = (
                            wav_file.getframerate(),
                            wav_file.getsampwidth(),
                            wav_file.getnchannels(),
                        )
                        if (rate != 16000) or (width != 2) or (channels != 1):
                            audio_data = convert_wav(message.payload)
                        else:
                            # Use original data
                            audio_data = wav_file.readframes(wav_file.getnframes())

                        data_message = AudioData(audio_data)

                # Forward to subscribers
                for receiver in self.receivers:
                    self.send(receiver, data_message)

                # Append to buffers
                for buffer_name in self.buffers:
                    self.buffers[buffer_name] += audio_data
        elif isinstance(message, StartStreaming):
            self.receivers.append(message.receiver or sender)
        elif isinstance(message, StartRecordingToBuffer):
            self.buffers[message.buffer_name] = bytes()
        elif isinstance(message, StopStreaming):
            if message.receiver is None:
                # Clear all receivers
                self.receivers.clear()
            else:
                self.receivers.remove(message.receiver)
        elif isinstance(message, StopRecordingToBuffer):
            if message.buffer_name is None:
                # Clear all buffers
                self.buffers.clear()
            else:
                # Respond with buffer
                buffer = self.buffers.pop(message.buffer_name, bytes())
                self.send(message.receiver or sender, AudioData(buffer))

    # -----------------------------------------------------------------------------

    @classmethod
    def get_microphones(cls) -> Dict[Any, Any]:
        """Get description of available microphones."""
        return {}

    @classmethod
    def test_microphones(cls, chunk_size: int) -> Dict[Any, Any]:
        """Test microphones and return results."""
        return {}


# -----------------------------------------------------------------------------
# STDIN Microphone Recorder
# -----------------------------------------------------------------------------


class StdinAudioRecorder(RhasspyActor):
    """Records audio data from standard in."""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.receivers: List[RhasspyActor] = []
        self.buffers: Dict[str, bytes] = {}
        self.is_recording: bool = False
        self.chunk_size = 960

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.chunk_size = int(
            self.profile.get("microphone.stdin.chunk_size", self.chunk_size)
        )

        if self.profile.get("microphone.stdin.auto_start", True):
            threading.Thread(target=self.process_data, daemon=True).start()

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, StartStreaming):
            self.receivers.append(message.receiver or sender)
            self.transition("recording")
        elif isinstance(message, StartRecordingToBuffer):
            self.buffers[message.buffer_name] = bytes()
            self.transition("recording")

    def to_recording(self, from_state: str) -> None:
        """Transition to recording state."""
        self.is_recording = True
        self._logger.debug("Recording from microphone (stdin)")

    def in_recording(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in recording state."""
        if isinstance(message, AudioData):
            # Forward to subscribers
            for receiver in self.receivers:
                self.send(receiver, message)

            # Append to buffers
            for buffer_name in self.buffers:
                self.buffers[buffer_name] += message.data
        elif isinstance(message, StartStreaming):
            self.receivers.append(message.receiver or sender)
        elif isinstance(message, StartRecordingToBuffer):
            self.buffers[message.buffer_name] = bytes()
        elif isinstance(message, StopStreaming):
            if message.receiver is None:
                # Clear all receivers
                self.receivers.clear()
            else:
                self.receivers.remove(message.receiver)
        elif isinstance(message, StopRecordingToBuffer):
            if message.buffer_name is None:
                # Clear all buffers
                self.buffers.clear()
            else:
                # Respond with buffer
                buffer = self.buffers.pop(message.buffer_name, bytes())
                self.send(message.receiver or sender, AudioData(buffer))

        # Check to see if anyone is still listening
        if (len(self.receivers) == 0) and (len(self.buffers) == 0):
            # Terminate audio recording
            self.is_recording = False
            self.transition("started")
            self._logger.debug("Stopped recording from microphone (stdin)")

    def to_stopped(self, from_state: str) -> None:
        """Transition to stopped state."""
        if self.is_recording:
            self.is_recording = False
            self._logger.debug("Stopped recording from microphone (stdin)")

    # -------------------------------------------------------------------------

    def process_data(self):
        """Forward single audio chunk."""
        while True:
            data = sys.stdin.buffer.read(self.chunk_size)
            if self.is_recording and (len(data) > 0):
                # Actor will forward
                self.send(self.myAddress, AudioData(data))

    # -------------------------------------------------------------------------

    @classmethod
    def get_microphones(cls) -> Dict[Any, Any]:
        """Get description of available microphones."""
        return {}

    # -------------------------------------------------------------------------

    @classmethod
    def test_microphones(cls, chunk_size: int) -> Dict[Any, Any]:
        """Test microphones and return results."""
        return {}


# -----------------------------------------------------------------------------
# HTTP Stream Recorder
# -----------------------------------------------------------------------------


class HTTPStreamServer(BaseHTTPRequestHandler):
    """Receive audio via chunked transfer encoding."""

    def __init__(self, *args, recorder=None, **kwargs):
        self.recorder = recorder
        BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

    def do_GET(self):
        """Handle GET requests."""
        text = self.recorder.get_response or ""

        self.send_response(200)
        self.end_headers()
        self.wfile.write(text.encode())

    def do_POST(self):
        """Handle POST requests."""
        try:
            self.recorder.get_response = None
            self.recorder.logger.debug("Receiving audio data")
            num_bytes = 0

            while True:
                # Assume chunked transfer encoding
                chunk_size_str = self.rfile.readline().decode().strip()
                if len(chunk_size_str) == 0:
                    break

                chunk_size = int(chunk_size_str, 16)
                if chunk_size <= 0:
                    break

                audio_chunk = self.rfile.read(chunk_size)

                # Consume \r\n
                self.rfile.read(2)

                num_bytes += len(audio_chunk)
                message = AudioData(audio_chunk)

                # Forward to subscribers
                for receiver in self.recorder.receivers:
                    self.recorder.send(receiver, message)

                # Append to buffers
                for buffer_name in self.recorder.buffers:
                    self.recorder.buffers[buffer_name] += message.data

                if (self.recorder.stop_after != "never") and (
                    self.recorder.get_response is not None
                ):
                    # Stop
                    self.send_response(200)
                    self.end_headers()
                    return

            self.send_response(200)
            self.end_headers()
            self.wfile.write(str(num_bytes).encode())
        except Exception:
            self.recorder.logger.exception("do_POST")


class HTTPAudioRecorder(RhasspyActor):
    """Records audio from HTTP stream."""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.receivers: List[RhasspyActor] = []
        self.buffers: Dict[str, bytes] = defaultdict(bytes)

        self.port = 12333
        self.host = "127.0.0.1"
        self.stop_after = "never"

        self.server = None
        self.server_thread: Optional[threading.Thread] = None
        self.get_response: Optional[str] = None

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.stop_after = str(
            self.profile.get("microphone.http.stop_after", "never")
        ).lower()

        self.get_response = None

        if self.server is None:
            self.host = str(self.profile.get("microphone.http.host", self.host))
            self.port = int(self.profile.get("microphone.http.port", self.port))

            # Start web server
            def make_server(*args, **kwargs):
                return HTTPStreamServer(*args, recorder=self, **kwargs)

            def server_proc():
                try:
                    self.server = HTTPServer((self.host, self.port), make_server)

                    # Can't use serve_forever because it will *never* stop.
                    while self.server is not None:
                        self.server.handle_request()
                except Exception:
                    self._logger.exception("server_proc")

            self.server_thread = threading.Thread(target=server_proc, daemon=True)
            assert self.server_thread is not None
            self.server_thread.start()

            self._logger.debug(
                "Listening for HTTP audio stream at http://%s:%s", self.host, self.port
            )

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, StartStreaming):
            self.receivers.append(message.receiver or sender)
            self.transition("recording")
        elif isinstance(message, StartRecordingToBuffer):
            self.buffers[message.buffer_name] = bytes()
            self.transition("recording")
        elif isinstance(message, WavTranscription):
            if self.stop_after == "text":
                self.get_response = message.text
        elif isinstance(message, IntentRecognized):
            if self.stop_after == "intent":
                self.get_response = json.dumps(message.intent)

    def in_recording(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in recording state."""
        if isinstance(message, StartStreaming):
            self.receivers.append(message.receiver or sender)
        elif isinstance(message, StartRecordingToBuffer):
            self.buffers[message.buffer_name] = bytes()
        elif isinstance(message, StopStreaming):
            if message.receiver is None:
                # Clear all receivers
                self.receivers.clear()
            else:
                self.receivers.remove(message.receiver)
        elif isinstance(message, StopRecordingToBuffer):
            if message.buffer_name is None:
                # Clear all buffers
                self.buffers.clear()
            else:
                # Respond with buffer
                buffer = self.buffers.pop(message.buffer_name, bytes())
                self.send(message.receiver or sender, AudioData(buffer))

        # Check to see if anyone is still listening
        if (len(self.receivers) == 0) and (len(self.buffers) == 0):
            self.transition("started")

    def to_stopped(self, from_state: str) -> None:
        """Transition to stopped state."""
        import requests

        try:
            if self.server is not None:
                self.server = None

                # Absoultely *ridiculous* workaround to stop the HTTPServer.
                # The shutdown() method doesn't work.
                # server_close() doesn't work.
                # socket.close() doesn't work.
                requests.get(f"http://{self.host}:{self.port}")

                self.server_thread.join()
                self.server_thread = None
        except Exception:
            self._logger.exception("to_stopped")

    @property
    def logger(self):
        """Get actor's logger."""
        return self._logger

    # -------------------------------------------------------------------------

    @classmethod
    def get_microphones(cls) -> Dict[Any, Any]:
        """Get description of available microphones."""
        return {}

    @classmethod
    def test_microphones(cls, chunk_size: int) -> Dict[Any, Any]:
        """Test microphones and return results."""
        return {}


# -----------------------------------------------------------------------------
# GStreamer Recorder
# -----------------------------------------------------------------------------


class GStreamerAudioRecorder(RhasspyActor):
    """Records audio from gstreamer."""

    DEFAULT_PIPELINE = (
        "udpsrc port=12333"
        + " ! rawaudioparse use-sink-caps=false format=pcm pcm-format=s16le sample-rate=16000 num-channels=1"
        + " ! queue"
        + " ! audioconvert"
        + " ! audioresample"
    )

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.receivers: List[RhasspyActor] = []
        self.buffers: Dict[str, bytes] = defaultdict(bytes)

        self.gstreamer_proc = None
        self.gstreamer_thread: Optional[threading.Thread] = None
        self.chunk_size: int = 960
        self.command: List[str] = []

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        if self.gstreamer_proc is None:
            self.command = (
                ["gst-launch-1.0"]
                + shlex.split(
                    str(
                        self.profile.get(
                            "microphone.gstreamer.pipeline",
                            GStreamerAudioRecorder.DEFAULT_PIPELINE,
                        )
                    )
                )
                + ["!", "fdsink", "fd=1"]
            )

            self.chunk_size = int(
                self.profile.get("microphone.gstreamer.chunk_size", self.chunk_size)
            )

            def gstreamer_thread_proc():
                try:
                    self._logger.debug(self.command)
                    self.gstreamer_proc = subprocess.Popen(
                        self.command, stdout=subprocess.PIPE
                    )

                    first_audio = True

                    while True:
                        chunk = self.gstreamer_proc.stdout.read(self.chunk_size)
                        if len(chunk) > 0:
                            if first_audio:
                                self._logger.debug("Receiving audio")
                                first_audio = False

                            message = AudioData(chunk)

                            # Forward to subscribers
                            for receiver in self.receivers:
                                self.send(receiver, message)

                            # Append to buffers
                            for buffer_name in self.buffers:
                                self.buffers[buffer_name] += message.data
                        else:
                            # Avoid 100% CPU
                            time.sleep(0.01)
                except Exception:
                    if self.gstreamer_proc is not None:
                        self._logger.exception(
                            "gstreamer_thread:Optional[threading.Thread]"
                        )

            self.gstreamer_thread = threading.Thread(
                target=gstreamer_thread_proc, daemon=True
            )
            assert self.gstreamer_thread is not None
            self.gstreamer_thread.start()

            self._logger.debug("Listening for GStreamer audio")

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, StartStreaming):
            self.receivers.append(message.receiver or sender)
            self.transition("recording")
        elif isinstance(message, StartRecordingToBuffer):
            self.buffers[message.buffer_name] = bytes()
            self.transition("recording")

    def in_recording(self, message: Any, sender: RhasspyActor) -> None:
        """Transition to recording state."""
        if isinstance(message, StartStreaming):
            self.receivers.append(message.receiver or sender)
        elif isinstance(message, StartRecordingToBuffer):
            self.buffers[message.buffer_name] = bytes()
        elif isinstance(message, StopStreaming):
            if message.receiver is None:
                # Clear all receivers
                self.receivers.clear()
            else:
                self.receivers.remove(message.receiver)
        elif isinstance(message, StopRecordingToBuffer):
            if message.buffer_name is None:
                # Clear all buffers
                self.buffers.clear()
            else:
                # Respond with buffer
                buffer = self.buffers.pop(message.buffer_name, bytes())
                self.send(message.receiver or sender, AudioData(buffer))

        # Check to see if anyone is still listening
        if (len(self.receivers) == 0) and (len(self.buffers) == 0):
            self.transition("started")

    def to_stopped(self, from_state: str) -> None:
        """Transition to stopped state."""
        try:
            if self.gstreamer_proc is not None:
                proc = self.gstreamer_proc
                self.gstreamer_proc = None
                proc.terminate()
                proc.wait()
        except Exception:
            self._logger.exception("to_stopped")

    # -------------------------------------------------------------------------

    @classmethod
    def get_microphones(cls) -> Dict[Any, Any]:
        """Get description of available microphones."""
        return {}

    @classmethod
    def test_microphones(cls, chunk_size: int) -> Dict[Any, Any]:
        """Test microphones and return results."""
        return {}
