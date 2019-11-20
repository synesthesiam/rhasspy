#!/usr/bin/env python3
import json
import logging
import os
import re
import shutil
import struct
import subprocess
import threading
import time
from typing import Any, Dict, List, Optional, Type
from uuid import uuid4

from rhasspy.actor import RhasspyActor
from rhasspy.audio_recorder import AudioData, StartStreaming, StopStreaming
from rhasspy.mqtt import MqttMessage, MqttSubscribe
from rhasspy.profiles import Profile
from rhasspy.utils import ByteStream, read_dict

# -----------------------------------------------------------------------------


class ListenForWakeWord:
    def __init__(self, receiver: Optional[RhasspyActor] = None, record=True) -> None:
        self.receiver = receiver
        self.record = record


class StopListeningForWakeWord:
    def __init__(self, receiver: Optional[RhasspyActor] = None, record=True) -> None:
        self.receiver = receiver
        self.record = record


class WakeWordDetected:
    def __init__(self, name: str, audio_data_info: Dict[Any, Any] = {}) -> None:
        self.name = name
        self.audio_data_info = audio_data_info


class WakeWordNotDetected:
    def __init__(self, name: str, audio_data_info: Dict[Any, Any] = {}) -> None:
        self.name = name
        self.audio_data_info = audio_data_info


# -----------------------------------------------------------------------------


def get_wake_class(system: str) -> Type[RhasspyActor]:
    assert system in [
        "dummy",
        "pocketsphinx",
        "hermes",
        "snowboy",
        "precise",
        "porcupine",
        "command",
    ], ("Invalid wake system: %s" % system)

    if system == "pocketsphinx":
        # Use pocketsphinx locally
        return PocketsphinxWakeListener
    elif system == "hermes":
        # Use remote system via MQTT
        return HermesWakeListener
    elif system == "snowboy":
        # Use snowboy locally
        return SnowboyWakeListener
    elif system == "precise":
        # Use Mycroft Precise locally
        return PreciseWakeListener
    elif system == "porcupine":
        # Use Picovoice's porcupine locally
        return PorcupineWakeListener
    elif system == "command":
        # Use command-line listener
        return CommandWakeListener

    # Use dummy listener as a fallback
    return DummyWakeListener


# -----------------------------------------------------------------------------


class DummyWakeListener(RhasspyActor):
    """Does nothing"""

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        pass


# -----------------------------------------------------------------------------
# Pocketsphinx based wake word listener
# https://github.com/cmusphinx/pocketsphinx
# -----------------------------------------------------------------------------


class PocketsphinxWakeListener(RhasspyActor):
    """Listens for a wake word with pocketsphinx."""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.receivers: List[RhasspyActor] = []
        self.decoder = None
        self.decoder_started: bool = False

    def to_started(self, from_state: str) -> None:
        self.recorder = self.config["recorder"]
        self.preload: bool = self.config.get("preload", False)
        self.not_detected: bool = self.config.get("not_detected", False)
        self.chunk_size: int = self.profile.get("wake.pocketsphinx.chunk_size", 960)
        if self.preload:
            with self._lock:
                try:
                    self.load_decoder()
                except:
                    self._logger.exception("loading wake decoder")

        self.transition("loaded")

    def in_loaded(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, ListenForWakeWord):
            self.load_decoder()
            self.receivers.append(message.receiver or sender)
            self.transition("listening")

            if message.record:
                self.send(self.recorder, StartStreaming(self.myAddress))

    def in_listening(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, AudioData):
            if not self.decoder_started:
                assert self.decoder is not None
                self.decoder.start_utt()
                self.decoder_started = True

            audio_data = message.data
            chunk = audio_data[: self.chunk_size]
            detected = False
            while len(chunk) > 0:
                result = self.process_data(chunk)
                if result is not None:
                    detected = True
                    self._logger.debug("Hotword detected (%s)" % self.keyphrase)
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
            self.receivers.remove(message.receiver or sender)
            if len(self.receivers) == 0:
                # End utterance
                if self.decoder_started:
                    assert self.decoder is not None
                    self.decoder.end_utt()
                    self.decoder_started = False

                if message.record:
                    self.send(self.recorder, StopStreaming(self.myAddress))

                self.transition("loaded")

    # -------------------------------------------------------------------------

    def process_data(self, data: bytes) -> Optional[str]:
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
            assert len(self.keyphrase) > 0, "No wake keyphrase"

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

                if not word in word_dict:
                    self._logger.warn("%s not in dictionary" % word)

            self._logger.debug(
                "Loading wake decoder with hmm=%s, dict=%s" % (hmm_path, dict_path)
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
                    "Using tuned MLLR matrix for acoustic model: %s" % mllr_path
                )
                decoder_config.set_string("-mllr", mllr_path)

            self.decoder = pocketsphinx.Decoder(decoder_config)
            self.decoder_started = False


# -----------------------------------------------------------------------------
# Snowboy wake listener
# https://snowboy.kitt.ai
# -----------------------------------------------------------------------------


class SnowboyWakeListener(RhasspyActor):
    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.receivers: List[RhasspyActor] = []
        self.detector = None

    def to_started(self, from_state: str) -> None:
        self.recorder = self.config["recorder"]
        self.preload = self.config.get("preload", False)
        self.not_detected: bool = self.config.get("not_detected", False)
        self.chunk_size: int = self.profile.get("wake.snowboy.chunk_size", 960)
        self.apply_frontend: bool = self.profile.get(
            "wake.snowboy.apply_frontend", False
        )
        if self.preload:
            try:
                self.load_detector()
            except Exception as e:
                self._logger.warning(f"preload: {e}")

        self.transition("loaded")

    def in_loaded(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, ListenForWakeWord):
            try:
                self.load_detector()
                self.receivers.append(message.receiver or sender)
                self.transition("listening")
                if message.record:
                    self.send(self.recorder, StartStreaming(self.myAddress))
            except Exception as e:
                self._logger.exception("in_loaded")

    def in_listening(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, AudioData):
            audio_data = message.data
            chunk = audio_data[: self.chunk_size]
            detected = False
            while len(chunk) > 0:
                index = self.process_data(chunk)
                if index > 0:
                    detected = True
                    break

                audio_data = audio_data[self.chunk_size :]
                chunk = audio_data[: self.chunk_size]

            if detected:
                # Detected
                self._logger.debug("Hotword detected (%s)" % self.model_name)
                detected_event = WakeWordDetected(
                    self.model_name, audio_data_info=message.info
                )
                for receiver in self.receivers:
                    self.send(receiver, detected_event)
            elif self.not_detected:
                # Not detected
                not_detected_event = WakeWordNotDetected(
                    self.model_name, audio_data_info=message.info
                )
                for receiver in self.receivers:
                    self.send(receiver, not_detected_event)
        elif isinstance(message, StopListeningForWakeWord):
            self.receivers.remove(message.receiver or sender)
            if len(self.receivers) == 0:
                if message.record:
                    self.send(self.recorder, StopStreaming(self.myAddress))
                self.transition("loaded")

    # -------------------------------------------------------------------------

    def process_data(self, data: bytes) -> int:
        assert self.detector is not None
        try:
            # Return is:
            # -2 silence
            # -1 error
            #  0 voice
            #  n index n-1
            return self.detector.RunDetection(data)
        except Exception as e:
            self._logger.exception("process_data")

        return -2

    # -------------------------------------------------------------------------

    def load_detector(self) -> None:
        if self.detector is None:
            from snowboy import snowboydetect, snowboydecoder

            self.model_name = self.profile.get("wake.snowboy.model", "snowboy.umdl")
            model_path = os.path.realpath(self.profile.read_path(self.model_name))
            assert os.path.exists(
                model_path
            ), f"Can't find snowboy model file (expected at {model_path})"

            sensitivity = float(self.profile.get("wake.snowboy.sensitivity", 0.5))
            audio_gain = float(self.profile.get("wake.snowboy.audio_gain", 1.0))

            self._logger.debug(f"Loading snowboy model from {model_path}")

            self.detector = snowboydetect.SnowboyDetect(
                snowboydecoder.RESOURCE_FILE.encode(), model_path.encode()
            )

            assert self.detector is not None

            sensitivity_str = str(sensitivity).encode()
            self.detector.SetSensitivity(sensitivity_str)
            self.detector.SetAudioGain(audio_gain)
            self.detector.ApplyFrontend(self.apply_frontend)

            self._logger.debug(
                "Loaded snowboy (model=%s, sensitivity=%s, audio_gain=%s)"
                % (model_path, sensitivity, audio_gain)
            )

    # -------------------------------------------------------------------------

    def get_problems(self) -> Dict[str, Any]:
        problems: Dict[str, Any] = {}
        try:
            from snowboy import snowboydetect, snowboydecoder
        except:
            problems[
                "snowboy not installed"
            ] = "The snowboy Python library is not installed. Try pip3 install snowboy"

        model_path = self.profile.read_path(
            self.profile.get("wake.snowboy.model", "snowboy.umdl")
        )
        if not os.path.exists(model_path):
            problems[
                "Missing model"
            ] = f"Your snowboy model could not be loaded from {model_path}"

        return problems


# -----------------------------------------------------------------------------
# Mycroft Precise wake listener
# https://github.com/MycroftAI/mycroft-precise
# -----------------------------------------------------------------------------


class PreciseWakeListener(RhasspyActor):
    """Listens for a wake word using Mycroft Precise."""

    def __init__(self) -> None:
        from precise_runner import ReadWriteStream

        RhasspyActor.__init__(self)
        self.receivers: List[RhasspyActor] = []
        self.stream: Optional[ReadWriteStream] = None
        self.engine = None
        self.runner = None
        self.prediction_sem = threading.Semaphore()
        self.audio_buffer: bytes = bytes()
        self.detected: bool = False
        self.audio_info: Dict[Any, Any] = {}

    def to_started(self, from_state: str) -> None:
        self.recorder = self.config["recorder"]
        self.preload = self.config.get("preload", False)
        self.send_not_detected: bool = self.config.get("not_detected", False)
        self.chunk_size: int = self.profile.get("wake.precise.chunk_size", 2048)
        self.chunk_delay: float = self.profile.get("wake.precise.chunk_delay", 0)

        if self.preload:
            try:
                self.load_runner()
            except:
                pass

        self.transition("loaded")

    def in_loaded(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, ListenForWakeWord):
            try:
                self.load_runner()
                self.receivers.append(message.receiver or sender)
                self.transition("listening")
                if message.record:
                    self.send(self.recorder, StartStreaming(self.myAddress))
            except Exception as e:
                self._logger.exception("in_loaded")

    def in_listening(self, message: Any, sender: RhasspyActor) -> None:
        try:
            if isinstance(message, AudioData):
                self.audio_info = message.info
                self.detected = False
                self.audio_buffer += message.data
                num_chunks = len(self.audio_buffer) // self.chunk_size

                if num_chunks > 0:
                    assert self.stream is not None
                    self.prediction_sem = threading.Semaphore()
                    for i in range(num_chunks):
                        chunk = self.audio_buffer[: self.chunk_size]
                        self.stream.write(chunk)
                        self.audio_buffer = self.audio_buffer[self.chunk_size :]

                    if self.send_not_detected:
                        # Wait for all chunks to finish processing
                        for i in range(num_chunks):
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
                self.receivers.remove(message.receiver or sender)
                if len(self.receivers) == 0:
                    if message.record:
                        self.send(self.recorder, StopStreaming(self.myAddress))
                    self.transition("loaded")
            elif isinstance(message, str):
                # Detected
                self._logger.debug("Hotword detected (%s)" % self.model_name)
                detected_event = WakeWordDetected(
                    self.model_name, audio_data_info=self.audio_info
                )
                for receiver in self.receivers:
                    self.send(receiver, detected_event)
        except Exception as e:
            self._logger.exception("in_listening")

    def to_stopped(self, from_state: str) -> None:
        self.stream = None

        if self.runner is not None:
            self.runner.stop()

    # -------------------------------------------------------------------------

    def load_runner(self) -> None:
        if self.engine is None:
            from precise_runner import PreciseEngine

            self.model_name = self.profile.get("wake.precise.model", "hey-mycroft-2.pb")
            self.model_path = self.profile.read_path(self.model_name)
            self.engine_path = os.path.expandvars(
                self.profile.get("wake.precise.engine_path", "precise-engine")
            )

            self._logger.debug(f"Loading Precise engine at {self.engine_path}")
            self.engine = PreciseEngine(
                self.engine_path, self.model_path, chunk_size=self.chunk_size
            )

        if self.runner is None:
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
                "Loaded Mycroft Precise (model=%s, sensitivity=%s, trigger_level=%s)"
                % (self.model_path, sensitivity, trigger_level)
            )

    # -------------------------------------------------------------------------

    def get_problems(self) -> Dict[str, Any]:
        problems: Dict[str, Any] = {}
        try:
            from precise_runner import PreciseRunner, ReadWriteStream
        except:
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
# https://docs.snips.ai/ressources/hermes-protocol
# -----------------------------------------------------------------------------


class HermesWakeListener(RhasspyActor):
    """Listens for a wake word using MQTT."""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.receivers: List[RhasspyActor] = []

    def to_started(self, from_state: str) -> None:
        self.mqtt = self.config["mqtt"]

        # Subscribe to wake topic
        self.site_ids = self.profile.get("mqtt.site_id", "default").split(",")
        self.wakeword_id: str = self.profile.get("wake.hermes.wakeword_id", "default")
        self.wake_topic = "hermes/hotword/%s/detected" % self.wakeword_id
        self.send(self.mqtt, MqttSubscribe(self.wake_topic))

        self.transition("loaded")

    def in_loaded(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, ListenForWakeWord):
            self.receivers.append(message.receiver or sender)
            self.transition("listening")

    def in_listening(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, MqttMessage):
            if message.topic == self.wake_topic:
                # Check site ID
                payload = json.loads(message.payload.decode())
                payload_site_id = payload.get("siteId", "")
                if payload_site_id not in self.site_ids:
                    self._logger.debug(
                        "Got detected message, but wrong site id (%s)" % payload_site_id
                    )
                    return

                # Pass downstream to receivers
                self._logger.debug("Hotword detected (%s)" % self.wakeword_id)
                result = WakeWordDetected(self.wakeword_id)
                for receiver in self.receivers:
                    self.send(receiver, result)
        elif isinstance(message, StopListeningForWakeWord):
            self.receivers.remove(message.receiver or sender)
            if len(self.receivers) == 0:
                self.transition("loaded")


# -----------------------------------------------------------------------------
# Porcupine Wake Listener
# https://github.com/Picovoice/Porcupine
# -----------------------------------------------------------------------------


class PorcupineWakeListener(RhasspyActor):
    """Wake word listener that uses picovoice's porcupine library"""

    def __init__(self):
        RhasspyActor.__init__(self)
        self.receivers: List[RhasspyActor] = []
        self.wake_proc = None

    def to_started(self, from_state: str) -> None:
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
            self.profile.read_path(
                self.profile.get(
                    "wake.porcupine.keyword_path", "porcupine/porcupine.ppn"
                )
            )
        ]
        self.sensitivities = [
            float(self.profile.get("wake.porcupine.sensitivity", 0.5))
        ]

        self.preload: bool = self.config.get("preload", False)
        self.audio_buffer: bytes = bytes()
        self.chunk_size = 1024
        self.handle = None

        if self.preload:
            try:
                self.load_handle()
            except Exception as e:
                self._logger.exception("loading wake handle")

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, ListenForWakeWord):
            try:
                self.load_handle()
                self.receivers.append(message.receiver or sender)
                self.transition("listening")
                if message.record:
                    self.send(self.recorder, StartStreaming(self.myAddress))
            except Exception as e:
                self._logger.exception("loading wake handle")

    def in_listening(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, AudioData):
            self.audio_buffer += message.data
            num_chunks = len(self.audio_buffer) // self.chunk_size

            if num_chunks > 0:
                assert self.handle is not None
                for i in range(num_chunks):
                    chunk = self.audio_buffer[: self.chunk_size]
                    chunk = struct.unpack_from(self.chunk_format, chunk)
                    self.audio_buffer = self.audio_buffer[self.chunk_size :]

                    # Process chunk
                    keyword_index = self.handle.process(chunk)
                    if keyword_index:
                        # Pass downstream to receivers
                        self._logger.debug(f"Hotword detected ({keyword_index})")
                        result = WakeWordDetected(str(keyword_index))
                        for receiver in self.receivers:
                            self.send(receiver, result)

        elif isinstance(message, WakeWordDetected):
            # Pass downstream to receivers
            self._logger.debug("Hotword detected (%s)" % message.name)
            for receiver in self.receivers:
                self.send(receiver, message)
        elif isinstance(message, WakeWordNotDetected):
            # Pass downstream to receivers
            for receiver in self.receivers:
                self.send(receiver, message)
        elif isinstance(message, StopListeningForWakeWord):
            self.receivers.remove(message.receiver or sender)
            if len(self.receivers) == 0:
                if message.record:
                    self.send(self.recorder, StopStreaming(self.myAddress))

                if self.handle is not None:
                    self.handle.delete()
                    self.handle = None

                self.transition("started")

    def load_handle(self):
        if self.handle is None:
            from porcupine import Porcupine

            self.handle = Porcupine(
                self.library_path,
                self.model_path,
                keyword_file_paths=self.keyword_paths,
                sensitivities=self.sensitivities,
            )

            # 16-bit
            self.chunk_size = self.handle.frame_length * 2
            self.chunk_format = "h" * self.handle.frame_length
            self._logger.debug(
                f"Loaded porcupine (keyword={self.keyword_paths[0]}). Expecting sample rate={self.handle.sample_rate}, frame length={self.handle.frame_length}"
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

    def to_started(self, from_state: str) -> None:
        program = os.path.expandvars(self.profile.get("wake.command.program"))
        arguments = [
            os.path.expandvars(str(a))
            for a in self.profile.get("wake.command.arguments", [])
        ]

        self.command = [program] + arguments

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, ListenForWakeWord):
            self.receivers.append(message.receiver or sender)
            self.wake_proc = subprocess.Popen(self.command, stdout=subprocess.PIPE)

            def post_result() -> None:
                # STDOUT -> text
                try:
                    out, _ = self.wake_proc.communicate()
                    wakeword_id = out.decode().strip()
                except:
                    wakeword_id = ""
                    self._logger.exception("post_result")

                # Actor will forward
                if len(wakeword_id) > 0:
                    self.send(self.myAddress, WakeWordDetected(wakeword_id))
                else:
                    self.send(self.myAddress, WakeWordNotDetected(wakeword_id))

            self.transition("listening")

            # Wait for program in a separate thread
            threading.Thread(target=post_result, daemon=True).start()

    def in_listening(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, WakeWordDetected):
            # Pass downstream to receivers
            self._logger.debug("Hotword detected (%s)" % message.name)
            for receiver in self.receivers:
                self.send(receiver, message)
        elif isinstance(message, WakeWordNotDetected):
            # Pass downstream to receivers
            for receiver in self.receivers:
                self.send(receiver, message)
        elif isinstance(message, StopListeningForWakeWord):
            self.receivers.remove(message.receiver or sender)
            if len(self.receivers) == 0:
                if self.wake_proc is not None:
                    self.wake_proc.terminate()

                self.transition("started")
