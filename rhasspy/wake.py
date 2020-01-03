"""Wake word support."""
import json
import os
import re
import shutil
import struct
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Type

from rhasspy.actor import RhasspyActor
from rhasspy.events import (AudioData, ListenForWakeWord, MqttMessage,
                            MqttSubscribe, PauseListeningForWakeWord,
                            ResumeListeningForWakeWord, StartStreaming,
                            StopListeningForWakeWord, StopStreaming,
                            WakeWordDetected, WakeWordNotDetected)
from rhasspy.utils import read_dict

# -----------------------------------------------------------------------------


def get_wake_class(system: str) -> Type[RhasspyActor]:
    """Get type for profile wake system."""
    assert system in [
        "dummy",
        "pocketsphinx",
        "hermes",
        "snowboy",
        "precise",
        "porcupine",
        "command",
    ], f"Invalid wake system: {system}"

    if system == "pocketsphinx":
        # Use pocketsphinx locally
        return PocketsphinxWakeListener
    if system == "hermes":
        # Use remote system via MQTT
        return HermesWakeListener
    if system == "snowboy":
        # Use snowboy locally
        return SnowboyWakeListener
    if system == "precise":
        # Use Mycroft Precise locally
        return PreciseWakeListener
    if system == "porcupine":
        # Use Picovoice's porcupine locally
        return PorcupineWakeListener
    if system == "command":
        # Use command-line listener
        return CommandWakeListener

    # Use dummy listener as a fallback
    return DummyWakeListener


# -----------------------------------------------------------------------------


class DummyWakeListener(RhasspyActor):
    """Does nothing"""

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        pass


# -----------------------------------------------------------------------------
# Pocketsphinx based wake word listener
# https://github.com/cmusphinx/pocketsphinx
# -----------------------------------------------------------------------------,
class PocketsphinxWakeListener(RhasspyActor):
    """Listens for a wake word with pocketsphinx."""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.receivers: List[RhasspyActor] = []
        self.decoder = None
        self.decoder_started: bool = False
        self.preload = False
        self.not_detected = False
        self.chunk_size = 960
        self.recorder: Optional[RhasspyActor] = None
        self.threshold = 0.0
        self.keyphrase = ""

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.recorder = self.config["recorder"]
        self.preload = self.config.get("preload", False)
        self.not_detected = self.config.get("not_detected", False)
        self.chunk_size = self.profile.get("wake.pocketsphinx.chunk_size", 960)
        if self.preload:
            with self._lock:
                try:
                    self.load_decoder()
                except Exception:
                    self._logger.exception("loading wake decoder")

        self.transition("loaded")

    def in_loaded(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in loaded state."""
        if isinstance(message, ListenForWakeWord):
            self.load_decoder()
            self.receivers.append(message.receiver or sender)
            self.transition("listening")

            if message.record:
                self.send(self.recorder, StartStreaming(self.myAddress))

    def in_listening(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in listening state."""
        if isinstance(message, AudioData):
            if not self.decoder_started:
                assert self.decoder is not None
                self.decoder.start_utt()
                self.decoder_started = True

            audio_data = message.data
            chunk = audio_data[: self.chunk_size]
            detected = False
            while chunk:
                result = self.process_data(chunk)
                if result is not None:
                    detected = True
                    self._logger.debug("Hotword detected (%s)", self.keyphrase)
                    detected_msg = WakeWordDetected(
                        self.keyphrase, audio_data_info=message.info
                    )
                    for receiver in self.receivers:
                        self.send(receiver, detected_msg)

                    break

                audio_data = audio_data[self.chunk_size :]
                chunk = audio_data[: self.chunk_size]

            # End utterance
            if detected and self.decoder_started:
                assert self.decoder is not None
                self.decoder.end_utt()
                self.decoder_started = False

            if not detected and self.not_detected:
                # Report non-detection
                not_detected_msg = WakeWordNotDetected(
                    self.keyphrase, audio_data_info=message.info
                )
                for receiver in self.receivers:
                    self.send(receiver, not_detected_msg)
        elif isinstance(message, StopListeningForWakeWord):
            if message.clear_all:
                self.receivers.clear()
            else:
                try:
                    self.receivers.remove(message.receiver or sender)
                except ValueError:
                    pass

            if not self.receivers:
                # End utterance
                if self.decoder_started:
                    assert self.decoder is not None
                    self.decoder.end_utt()
                    self.decoder_started = False

                if message.record:
                    self.send(self.recorder, StopStreaming(self.myAddress))

                self.transition("loaded")
        elif isinstance(message, PauseListeningForWakeWord):
            self.transition("paused")

    def in_paused(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in paused state."""
        if isinstance(message, ResumeListeningForWakeWord):
            self.transition("listening")

    # -------------------------------------------------------------------------

    def process_data(self, data: bytes) -> Optional[str]:
        """Process single chunk of audio."""
        assert self.decoder is not None
        self.decoder.process_raw(data, False, False)
        hyp = self.decoder.hyp()
        if hyp:
            if self.decoder_started:
                self.decoder.end_utt()
                self.decoder_started = False

            return hyp.hypstr

        return None

    # -------------------------------------------------------------------------

    def load_decoder(self) -> None:
        """Loads speech decoder if not cached."""
        if self.decoder is None:
            import pocketsphinx

            # Load decoder settings (use speech-to-text configuration as a fallback)
            hmm_path = self.profile.read_path(
                self.profile.get("wake.pocketsphinx.acoustic_model", None)
                or self.profile.get("speech_to_text.pocketsphinx.acoustic_model")
            )

            dict_path = self.profile.read_path(
                self.profile.get("wake.pocketsphinx.dictionary", None)
                or self.profile.get("speech_to_text.pocketsphinx.dictionary")
            )

            self.threshold = float(
                self.profile.get("wake.pocketsphinx.threshold", 1e-40)
            )
            self.keyphrase = self.profile.get("wake.pocketsphinx.keyphrase", "")
            assert self.keyphrase, "No wake keyphrase"

            # Verify that keyphrase words are in dictionary
            keyphrase_words = re.split(r"\s+", self.keyphrase)
            with open(dict_path, "r") as dict_file:
                word_dict = read_dict(dict_file)

            dict_upper = self.profile.get("speech_to_text.dictionary_upper", False)
            for word in keyphrase_words:
                if dict_upper:
                    word = word.upper()
                else:
                    word = word.lower()

                if word not in word_dict:
                    self._logger.warning("%s not in dictionary", word)

            self._logger.debug(
                "Loading wake decoder with hmm=%s, dict=%s", hmm_path, dict_path
            )

            decoder_config = pocketsphinx.Decoder.default_config()
            decoder_config.set_string("-hmm", hmm_path)
            decoder_config.set_string("-dict", dict_path)
            decoder_config.set_string("-keyphrase", self.keyphrase)
            decoder_config.set_string("-logfn", "/dev/null")
            decoder_config.set_float("-kws_threshold", self.threshold)

            mllr_path = self.profile.read_path(
                self.profile.get("wake.pocketsphinx.mllr_matrix")
            )

            if os.path.exists(mllr_path):
                self._logger.debug(
                    "Using tuned MLLR matrix for acoustic model: %s", mllr_path
                )
                decoder_config.set_string("-mllr", mllr_path)

            self.decoder = pocketsphinx.Decoder(decoder_config)
            self.decoder_started = False


# -----------------------------------------------------------------------------
# Snowboy wake listener
# https://snowboy.kitt.ai
# -----------------------------------------------------------------------------


class SnowboyWakeListener(RhasspyActor):
    """Listen for wake word with snowboy."""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.receivers: List[RhasspyActor] = []
        self.detectors: List[Any] = []
        self.preload = False
        self.not_detected = False
        self.chunk_size = 960
        self.recorder: Optional[RhasspyActor] = None
        self.apply_frontend = False
        self.models: Dict[str, Any] = {}
        self.model_names: List[str] = []

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.recorder = self.config["recorder"]
        self.preload = self.config.get("preload", False)
        self.not_detected = self.config.get("not_detected", False)
        self.chunk_size = self.profile.get("wake.snowboy.chunk_size", 960)
        if self.preload:
            try:
                self.load_detectors()
            except Exception as e:
                self._logger.warning("preload: %s", e)

        self.transition("loaded")

    def in_loaded(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in loaded state."""
        if isinstance(message, ListenForWakeWord):
            try:
                self.load_detectors()
                self.receivers.append(message.receiver or sender)
                self.transition("listening")
                if message.record:
                    self.send(self.recorder, StartStreaming(self.myAddress))
            except Exception:
                self._logger.exception("in_loaded")

    def in_listening(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in listening state."""
        if isinstance(message, AudioData):
            audio_data = message.data
            chunk = audio_data[: self.chunk_size]
            detected = []
            while chunk:
                for detector_index, result_index in enumerate(self.process_data(chunk)):
                    if result_index > 0:
                        detected.append(detector_index)

                if detected:
                    # Don't process the rest of the audio data if hotword has
                    # already been detected.
                    break

                audio_data = audio_data[self.chunk_size :]
                chunk = audio_data[: self.chunk_size]

            # Handle results
            if detected:
                # Detected
                detected_names = [self.model_names[i] for i in detected]
                self._logger.debug("Hotword(s) detected: %s", detected_names)

                # Send events
                for model_name in detected_names:
                    detected_event = WakeWordDetected(
                        model_name, audio_data_info=message.info
                    )
                    for receiver in self.receivers:
                        self.send(receiver, detected_event)
            elif self.not_detected:
                # Not detected
                for model_name in self.model_names:
                    not_detected_event = WakeWordNotDetected(
                        model_name, audio_data_info=message.info
                    )
                    for receiver in self.receivers:
                        self.send(receiver, not_detected_event)
        elif isinstance(message, StopListeningForWakeWord):
            if message.clear_all:
                self.receivers.clear()
            else:
                try:
                    self.receivers.remove(message.receiver or sender)
                except ValueError:
                    pass

            if not self.receivers:
                if message.record:
                    self.send(self.recorder, StopStreaming(self.myAddress))
                self.transition("loaded")
        elif isinstance(message, PauseListeningForWakeWord):
            self.transition("paused")

    def in_paused(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in paused state."""
        if isinstance(message, ResumeListeningForWakeWord):
            self.transition("listening")

    # -------------------------------------------------------------------------

    def process_data(self, data: bytes) -> Iterable[int]:
        """Process single chunk of audio data."""
        try:
            for detector in self.detectors:
                # Return is:
                # -2 silence
                # -1 error
                #  0 voice
                #  n index n-1
                yield detector.RunDetection(data)
        except Exception:
            self._logger.exception("process_data")

        # All silences
        return [-2] * len(self.detectors)

    # -------------------------------------------------------------------------

    def load_detectors(self) -> None:
        """Load snowboy detector."""
        if not self.detectors:
            from snowboy import snowboydetect, snowboydecoder

            # Load model names and settings
            self.models = self._parse_models()
            self.model_names = sorted(self.models)

            # Create snowboy detectors
            for model_name in self.model_names:
                model_settings = self.models[model_name]
                model_path = Path(self.profile.read_path(model_name))
                assert model_path.is_file(), f"Missing {model_path}"
                self._logger.debug("Loading snowboy model from %s", model_path)

                detector = snowboydetect.SnowboyDetect(
                    snowboydecoder.RESOURCE_FILE.encode(), str(model_path).encode()
                )

                detector.SetSensitivity(str(model_settings["sensitivity"]).encode())
                detector.SetAudioGain(float(model_settings["audio_gain"]))
                detector.ApplyFrontend(bool(model_settings["apply_frontend"]))

                self.detectors.append(detector)
                self._logger.debug(
                    "Loaded snowboy model %s (%s)", model_name, model_settings
                )

    # -------------------------------------------------------------------------

    def _parse_models(self) -> Dict[str, Dict[str, Any]]:
        # Default sensitivity
        sensitivity: str = str(self.profile.get("wake.snowboy.sensitivity", "0.5"))

        # Default audio gain
        audio_gain: float = float(self.profile.get("wake.snowboy.audio_gain", "1.0"))

        # Default frontend
        apply_frontend: bool = self.profile.get("wake.snowboy.apply_frontend", False)

        model_names: List[str] = self.profile.get(
            "wake.snowboy.model", "snowboy/snowboy.umdl"
        ).split(",")

        model_settings: Dict[str, Dict[str, Any]] = self.profile.get(
            "wake.snowboy.model_settings", {}
        )

        models_dict = {}

        for model_name in model_names:
            # Add default settings
            settings = model_settings.get(model_name, {})
            if "sensitivity" not in settings:
                settings["sensitivity"] = sensitivity

            if "audio_gain" not in settings:
                settings["audio_gain"] = audio_gain

            if "apply_frontend" not in settings:
                settings["apply_frontend"] = apply_frontend

            models_dict[model_name] = settings

        return models_dict

    # -------------------------------------------------------------------------

    def get_problems(self) -> Dict[str, Any]:
        """Get problems at startup."""
        problems: Dict[str, Any] = {}
        try:
            # pylint: disable=W0611
            from snowboy import snowboydetect, snowboydecoder  # noqa: F401
        except Exception:
            problems[
                "snowboy not installed"
            ] = "The snowboy Python library is not installed. Try pip3 install snowboy"

        # Verify that all snowboy models exist
        models = self._parse_models()
        model_paths = [
            Path(self.profile.read_path(model_name)) for model_name in models
        ]

        for model_path in model_paths:
            if not model_path.is_file():
                problems[
                    "Missing model"
                ] = f"Snowboy model could not be loaded from {model_path}"

        return problems


# -----------------------------------------------------------------------------
# Mycroft Precise wake listener
# https://github.com/MycroftAI/mycroft-precise
# -----------------------------------------------------------------------------


class PreciseWakeListener(RhasspyActor):
    """Listens for a wake word using Mycroft Precise."""

    def __init__(self) -> None:
        # pylint: disable=E0401
        from precise_runner import ReadWriteStream

        RhasspyActor.__init__(self)
        self.audio_buffer: bytes = bytes()
        self.audio_info: Dict[Any, Any] = {}
        self.chunk_delay = 0
        self.chunk_size = 2048
        self.detected: bool = False
        self.engine = None
        self.engine_path = ""
        self.model_name = ""
        self.model_path = ""
        self.prediction_sem = threading.Semaphore()
        self.preload = False
        self.receivers: List[RhasspyActor] = []
        self.recorder: Optional[RhasspyActor] = None
        self.runner = None
        self.send_not_detected = False
        self.stream: Optional[ReadWriteStream] = None

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.recorder = self.config["recorder"]
        self.preload = self.config.get("preload", False)
        self.send_not_detected = self.config.get("not_detected", False)
        self.chunk_size = self.profile.get("wake.precise.chunk_size", 2048)
        self.chunk_delay = self.profile.get("wake.precise.chunk_delay", 0)

        if self.preload:
            try:
                self.load_runner()
            except Exception:
                pass

        self.transition("loaded")

    def in_loaded(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in loaded state."""
        if isinstance(message, ListenForWakeWord):
            try:
                self.load_runner()
                self.receivers.append(message.receiver or sender)
                self.transition("listening")
                if message.record:
                    self.send(self.recorder, StartStreaming(self.myAddress))
            except Exception:
                self._logger.exception("in_loaded")

    def in_listening(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in listening state."""
        try:
            if isinstance(message, AudioData):
                self.audio_info = message.info
                self.detected = False
                self.audio_buffer += message.data
                num_chunks = len(self.audio_buffer) // self.chunk_size

                if num_chunks > 0:
                    assert self.stream is not None
                    self.prediction_sem = threading.Semaphore()
                    for _ in range(num_chunks):
                        chunk = self.audio_buffer[: self.chunk_size]
                        self.stream.write(chunk)
                        self.audio_buffer = self.audio_buffer[self.chunk_size :]

                    if self.send_not_detected:
                        # Wait for all chunks to finish processing
                        for _ in range(num_chunks):
                            self.prediction_sem.acquire(timeout=0.1)

                        # Wait a little bit for the precise engine to finish processing
                        time.sleep(self.chunk_delay)
                        if not self.detected:
                            # Not detected
                            not_detected_event = WakeWordNotDetected(
                                self.model_name, audio_data_info=message.info
                            )
                            for receiver in self.receivers:
                                self.send(receiver, not_detected_event)
            elif isinstance(message, StopListeningForWakeWord):
                if message.clear_all:
                    self.receivers.clear()
                else:
                    try:
                        self.receivers.remove(message.receiver or sender)
                    except ValueError:
                        pass

                if not self.receivers:
                    if message.record:
                        self.send(self.recorder, StopStreaming(self.myAddress))
                    self.transition("loaded")
            elif isinstance(message, str):
                # Detected
                self._logger.debug("Hotword detected (%s)", self.model_name)
                detected_event = WakeWordDetected(
                    self.model_name, audio_data_info=self.audio_info
                )
                for receiver in self.receivers:
                    self.send(receiver, detected_event)
            elif isinstance(message, PauseListeningForWakeWord):
                self.transition("paused")
        except Exception:
            self._logger.exception("in_listening")

    def in_paused(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in paused state."""
        if isinstance(message, ResumeListeningForWakeWord):
            self.transition("listening")

    def to_stopped(self, from_state: str) -> None:
        """Transition to stopped state."""
        self.stream = None

        if self.runner is not None:
            self.runner.stop()

    # -------------------------------------------------------------------------

    def load_runner(self) -> None:
        """Load precise runner."""
        if self.engine is None:
            # pylint: disable=E0401
            from precise_runner import PreciseEngine

            self.model_name = self.profile.get("wake.precise.model", "hey-mycroft-2.pb")
            self.model_path = self.profile.read_path(self.model_name)
            self.engine_path = os.path.expandvars(
                self.profile.get("wake.precise.engine_path", "precise-engine")
            )

            self._logger.debug("Loading Precise engine at %s", self.engine_path)
            self.engine = PreciseEngine(
                self.engine_path, self.model_path, chunk_size=self.chunk_size
            )

        if self.runner is None:
            # pylint: disable=E0401
            from precise_runner import PreciseRunner, ReadWriteStream

            self.stream = ReadWriteStream()

            sensitivity = float(self.profile.get("wake.precise.sensitivity", 0.5))
            trigger_level = int(self.profile.get("wake.precise.trigger_level", 3))

            def on_prediction(prob: float) -> None:
                self.prediction_sem.release()

            def on_activation() -> None:
                self.detected = True
                self.send(self.myAddress, "activated")

            self.runner = PreciseRunner(
                self.engine,
                stream=self.stream,
                sensitivity=sensitivity,
                trigger_level=trigger_level,
                on_activation=on_activation,
                on_prediction=on_prediction,
            )

            assert self.runner is not None
            self.runner.start()

            self._logger.debug(
                "Loaded Mycroft Precise (model=%s, sensitivity=%s, trigger_level=%s)",
                self.model_path,
                sensitivity,
                trigger_level,
            )

    # -------------------------------------------------------------------------

    def get_problems(self) -> Dict[str, Any]:
        """Get problems at startup."""
        problems: Dict[str, Any] = {}
        try:
            # pylint: disable=E0401,W0611
            from precise_runner import PreciseRunner, ReadWriteStream  # noqa: F401
        except Exception:
            problems[
                "precise_runner not installed"
            ] = "The precise_runner Python library is not installed. Try pip3 install precise_runner"

        engine_path = os.path.expandvars(
            self.profile.get("wake.precise.engine_path", "precise-engine")
        )

        if not os.path.exists(engine_path) and not shutil.which(engine_path):
            problems[
                "Missing precise-engine"
            ] = 'The Mycroft Precise engine is not installed. Follow the <a href="https://github.com/MycroftAI/mycroft-precise#binary-install">binary install instructions</a>.'

        model_name = self.profile.get("wake.precise.model", "hey-mycroft-2.pb")
        model_path = self.profile.read_path(model_name)
        if not os.path.exists(model_path):
            problems[
                "Missing model"
            ] = f"Your Mycroft Precise model could not be loaded from {model_path}"

        return problems


# -----------------------------------------------------------------------------
# MQTT-based wake listener (Hermes protocol)
# https://docs.snips.ai/reference/hermes
# -----------------------------------------------------------------------------


class HermesWakeListener(RhasspyActor):
    """Listens for a wake word using MQTT."""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.receivers: List[RhasspyActor] = []
        self.site_ids = "default"
        self.wakeword_id = "default"
        self.wake_topic = ""
        self.mqtt: Optional[RhasspyActor] = None

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.mqtt = self.config["mqtt"]

        # Subscribe to wake topic
        self.site_ids = self.profile.get("mqtt.site_id", "default").split(",")
        self.wakeword_id = self.profile.get("wake.hermes.wakeword_id", "default")
        self.wake_topic = f"hermes/hotword/{self.wakeword_id}/detected"
        self.send(self.mqtt, MqttSubscribe(self.wake_topic))

        self.transition("loaded")

    def in_loaded(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in loaded state."""
        if isinstance(message, ListenForWakeWord):
            self.receivers.append(message.receiver or sender)
            self.transition("listening")

    def in_listening(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in listening state."""
        if isinstance(message, MqttMessage):
            if message.topic == self.wake_topic:
                # Check site ID
                payload = json.loads(message.payload.decode())
                payload_site_id = payload.get("siteId", "")
                if payload_site_id not in self.site_ids:
                    self._logger.debug(
                        "Got detected message, but wrong site id (%s)", payload_site_id
                    )
                    return

                # Pass downstream to receivers
                self._logger.debug("Hotword detected (%s)", self.wakeword_id)
                result = WakeWordDetected(self.wakeword_id)
                for receiver in self.receivers:
                    self.send(receiver, result)
        elif isinstance(message, StopListeningForWakeWord):
            if message.clear_all:
                self.receivers.clear()
            else:
                try:
                    self.receivers.remove(message.receiver or sender)
                except ValueError:
                    pass

            if not self.receivers:
                self.transition("loaded")
        elif isinstance(message, PauseListeningForWakeWord):
            self.transition("paused")

    def in_paused(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in paused state."""
        if isinstance(message, ResumeListeningForWakeWord):
            self.transition("listening")


# -----------------------------------------------------------------------------
# Porcupine Wake Listener
# https://github.com/Picovoice/Porcupine
# -----------------------------------------------------------------------------


class PorcupineWakeListener(RhasspyActor):
    """Wake word listener that uses picovoice's porcupine library"""

    def __init__(self):
        RhasspyActor.__init__(self)
        self.audio_buffer: bytes = bytes()
        self.chunk_format = ""
        self.chunk_size = 1024
        self.handle = None
        self.keyword_paths: List[Path] = []
        self.library_path = ""
        self.model_path = ""
        self.preload: bool = False
        self.receivers: List[RhasspyActor] = []
        self.recorder: Optional[RhasspyActor] = None
        self.sensitivities = []
        self.wake_proc = None

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.recorder = self.config["recorder"]
        self.library_path = self.profile.read_path(
            self.profile.get(
                "wake.porcupine.library_path", "porcupine/libpv_porcupine.so"
            )
        )
        self.model_path = self.profile.read_path(
            self.profile.get(
                "wake.porcupine.model_path", "porcupine/porcupine_params.pv"
            )
        )
        self.keyword_paths = [
            Path(self.profile.read_path(p))
            for p in self.profile.get(
                "wake.porcupine.keyword_path", "porcupine/porcupine.ppn"
            ).split(",")
        ]
        self.sensitivities = [
            float(s)
            for s in str(self.profile.get("wake.porcupine.sensitivity", "0.5")).split(
                ","
            )
        ]

        self.preload = self.config.get("preload", False)

        if self.preload:
            try:
                self.load_handle()
            except Exception:
                self._logger.exception("loading wake handle")

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, ListenForWakeWord):
            try:
                self.load_handle()
                self.receivers.append(message.receiver or sender)
                self.transition("listening")
                if message.record:
                    self.send(self.recorder, StartStreaming(self.myAddress))
            except Exception:
                self._logger.exception("loading wake handle")

    def in_listening(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in listening state."""
        if isinstance(message, AudioData):
            self.audio_buffer += message.data
            num_chunks = len(self.audio_buffer) // self.chunk_size

            if num_chunks > 0:
                assert self.handle is not None
                for _ in range(num_chunks):
                    chunk = self.audio_buffer[: self.chunk_size]
                    unpacked_chunk = struct.unpack_from(self.chunk_format, chunk)
                    self.audio_buffer = self.audio_buffer[self.chunk_size :]

                    # Process chunk
                    keyword_index = self.handle.process(unpacked_chunk)
                    if keyword_index:
                        if len(self.keyword_paths) == 1:
                            keyword_index = 0

                        wakeword_name = str(keyword_index)
                        if keyword_index < len(self.keyword_paths):
                            wakeword_name = self.keyword_paths[keyword_index].stem

                        # Pass downstream to receivers
                        self._logger.debug("Hotword detected (%s)", keyword_index)
                        result = WakeWordDetected(wakeword_name)
                        for receiver in self.receivers:
                            self.send(receiver, result)

        elif isinstance(message, WakeWordDetected):
            # Pass downstream to receivers
            self._logger.debug("Hotword detected (%s)", message.name)
            for receiver in self.receivers:
                self.send(receiver, message)
        elif isinstance(message, WakeWordNotDetected):
            # Pass downstream to receivers
            for receiver in self.receivers:
                self.send(receiver, message)
        elif isinstance(message, StopListeningForWakeWord):
            if message.clear_all:
                self.receivers.clear()
            else:
                try:
                    self.receivers.remove(message.receiver or sender)
                except ValueError:
                    pass

            if not self.receivers:
                if message.record:
                    self.send(self.recorder, StopStreaming(self.myAddress))

                if self.handle is not None:
                    self.handle.delete()
                    self.handle = None

                self.transition("started")
        elif isinstance(message, PauseListeningForWakeWord):
            self.transition("paused")

    def in_paused(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in paused state."""
        if isinstance(message, ResumeListeningForWakeWord):
            self.transition("listening")

    def load_handle(self):
        """Load porcupine library."""
        if self.handle is None:
            for kw_path in self.keyword_paths:
                assert kw_path.is_file(), f"Missing {kw_path}"

            from porcupine import Porcupine

            self.handle = Porcupine(
                self.library_path,
                self.model_path,
                keyword_file_paths=[str(p) for p in self.keyword_paths],
                sensitivities=self.sensitivities,
            )

            # 16-bit
            self.chunk_size = self.handle.frame_length * 2
            self.chunk_format = "h" * self.handle.frame_length
            self._logger.debug(
                "Loaded porcupine (keyword=%s). Expecting sample rate=%s, frame length=%s",
                self.keyword_paths,
                self.handle.sample_rate,
                self.handle.frame_length,
            )


# -----------------------------------------------------------------------------
# Command Wake Listener
# -----------------------------------------------------------------------------


class CommandWakeListener(RhasspyActor):
    """Command-line based wake word listener"""

    def __init__(self):
        RhasspyActor.__init__(self)
        self.receivers: List[RhasspyActor] = []
        self.wake_proc = None
        self.command: List[str] = []

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        program = os.path.expandvars(self.profile.get("wake.command.program"))
        arguments = [
            os.path.expandvars(str(a))
            for a in self.profile.get("wake.command.arguments", [])
        ]

        self.command = [program] + arguments

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, ListenForWakeWord):
            self.receivers.append(message.receiver or sender)
            self.wake_proc = subprocess.Popen(self.command, stdout=subprocess.PIPE)

            def post_result() -> None:
                # STDOUT -> text
                try:
                    out, _ = self.wake_proc.communicate()
                    wakeword_id = out.decode().strip()
                except Exception:
                    wakeword_id = ""
                    self._logger.exception("post_result")

                # Actor will forward
                if wakeword_id:
                    self.send(self.myAddress, WakeWordDetected(wakeword_id))
                else:
                    self.send(self.myAddress, WakeWordNotDetected(wakeword_id))

            self.transition("listening")

            # Wait for program in a separate thread
            threading.Thread(target=post_result, daemon=True).start()

    def in_listening(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in listening state."""
        if isinstance(message, WakeWordDetected):
            # Pass downstream to receivers
            self._logger.debug("Hotword detected (%s)", message.name)
            for receiver in self.receivers:
                self.send(receiver, message)
        elif isinstance(message, WakeWordNotDetected):
            # Pass downstream to receivers
            for receiver in self.receivers:
                self.send(receiver, message)
        elif isinstance(message, StopListeningForWakeWord):
            if message.clear_all:
                self.receivers.clear()
            else:
                try:
                    self.receivers.remove(message.receiver or sender)
                except ValueError:
                    pass

            if not self.receivers:
                if self.wake_proc is not None:
                    self.wake_proc.terminate()

                self.transition("started")
        elif isinstance(message, PauseListeningForWakeWord):
            self.transition("paused")

    def in_paused(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in paused state."""
        if isinstance(message, ResumeListeningForWakeWord):
            self.transition("listening")
