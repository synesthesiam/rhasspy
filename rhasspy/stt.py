"""Speech to text."""
import io
import os
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type

from rhasspy.actor import RhasspyActor
from rhasspy.utils import convert_wav

# -----------------------------------------------------------------------------


class TranscribeWav:
    """Request to transcribe text from WAV buffer."""

    def __init__(
        self,
        wav_data: bytes,
        receiver: Optional[RhasspyActor] = None,
        handle: bool = True,
    ) -> None:
        self.wav_data = wav_data
        self.receiver = receiver
        self.handle = handle


class WavTranscription:
    """Response to TranscribeWav."""

    def __init__(self, text: str, handle: bool = True, confidence: float = 1) -> None:
        self.text = text
        self.confidence = confidence
        self.handle = handle


# -----------------------------------------------------------------------------


def get_decoder_class(system: str) -> Type[RhasspyActor]:
    """Get type for profile speech to text decoder."""
    assert system in ["dummy", "pocketsphinx", "kaldi", "remote", "command"], (
        "Invalid speech to text system: %s" % system
    )

    if system == "pocketsphinx":
        # Use pocketsphinx locally
        return PocketsphinxDecoder
    if system == "kaldi":
        # Use kaldi locally
        return KaldiDecoder
    if system == "remote":
        # Use remote Rhasspy server
        return RemoteDecoder
    if system == "command":
        # Use external program
        return CommandDecoder

    # Use dummy decoder as a fallback
    return DummyDecoder


# -----------------------------------------------------------------------------


class DummyDecoder(RhasspyActor):
    """Always returns an emptry transcription"""

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, TranscribeWav):
            self.send(message.receiver or sender, WavTranscription(""))


# -----------------------------------------------------------------------------
# Pocketsphinx based WAV to text decoder
# https://github.com/cmusphinx/pocketsphinx
# -----------------------------------------------------------------------------


class PocketsphinxDecoder(RhasspyActor):
    """Pocketsphinx based WAV to text decoder."""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.decoder = None
        self.min_confidence: float = 0
        self.preload: bool = False
        self.decoder = None

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.min_confidence = self.profile.get(
            "speech_to_text.pocketsphinx.min_confidence", 0.0
        )
        self.open_transcription = self.profile.get(
            "speech_to_text.pocketsphinx.open_transcription", False
        )
        self.preload = self.config.get("preload", False)
        if self.preload:
            with self._lock:
                try:
                    self.load_decoder()
                except Exception as e:
                    self._logger.warning("preload: %s", e)

        self.transition("loaded")

    def in_loaded(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in loaded state."""
        if isinstance(message, TranscribeWav):
            try:
                self.load_decoder()
                text, confidence = self.transcribe_wav(message.wav_data)
                self.send(
                    message.receiver or sender,
                    WavTranscription(
                        text, confidence=confidence, handle=message.handle
                    ),
                )
            except Exception:
                self._logger.exception("transcribing wav")

                # Send empty transcription back
                self.send(
                    message.receiver or sender,
                    WavTranscription("", handle=message.handle),
                )

    # -------------------------------------------------------------------------

    def load_decoder(self) -> None:
        """Load Pocketsphinx HMM/LM/Dictionary."""
        if self.decoder is None:
            # Load decoder
            import pocketsphinx

            ps_config = self.profile.get("speech_to_text.pocketsphinx", {})

            # Load decoder settings
            hmm_path = self.profile.read_path(
                ps_config.get("acoustic_model", "acoustic_model")
            )

            if self.open_transcription:
                self._logger.debug("Open transcription mode")

                # Use base language model/dictionary
                dict_path = self.profile.read_path(
                    ps_config.get("base_dictionary", "base_dictionary.txt")
                )
                lm_path = self.profile.read_path(
                    ps_config.get("base_language_model", "base_language_model.txt")
                )
            else:
                # Custom voice commands
                dict_path = self.profile.read_path(
                    ps_config.get("dictionary", "dictionary.txt")
                )
                lm_path = self.profile.read_path(
                    ps_config.get("language_model", "language_model.txt")
                )

            self._logger.debug(
                "Loading decoder with hmm=%s, dict=%s, lm=%s",
                hmm_path,
                dict_path,
                lm_path,
            )

            decoder_config = pocketsphinx.Decoder.default_config()
            decoder_config.set_string("-hmm", hmm_path)
            decoder_config.set_string("-dict", dict_path)
            decoder_config.set_string("-lm", lm_path)
            decoder_config.set_string("-logfn", "/dev/null")

            mllr_path = self.profile.read_path(ps_config["mllr_matrix"])
            if os.path.exists(mllr_path):
                self._logger.debug(
                    "Using tuned MLLR matrix for acoustic model: %s", mllr_path
                )
                decoder_config.set_string("-mllr", mllr_path)

            self.decoder = pocketsphinx.Decoder(decoder_config)

    def transcribe_wav(self, wav_data: bytes) -> Tuple[str, float]:
        """Get text from WAV buffer."""
        # Ensure 16-bit 16Khz mono
        assert self.decoder is not None
        with io.BytesIO(wav_data) as wav_io:
            with wave.open(wav_io, "rb") as wav_file:
                rate, width, channels = (
                    wav_file.getframerate(),
                    wav_file.getsampwidth(),
                    wav_file.getnchannels(),
                )
                self._logger.debug(
                    "rate=%s, width=%s, channels=%s.", rate, width, channels
                )

                if (rate != 16000) or (width != 2) or (channels != 1):
                    self._logger.info("Need to convert to 16-bit 16Khz mono.")
                    # Use converted data
                    audio_data = convert_wav(wav_data)
                else:
                    # Use original data
                    audio_data = wav_file.readframes(wav_file.getnframes())

        # Process data as an entire utterance
        start_time = time.time()
        self.decoder.start_utt()
        self.decoder.process_raw(audio_data, False, True)
        self.decoder.end_utt()
        end_time = time.time()

        self._logger.debug("Decoded WAV in %s second(s)", end_time - start_time)

        hyp = self.decoder.hyp()
        if hyp is not None:
            confidence = self.decoder.get_logmath().exp(hyp.prob)
            self._logger.debug("Transcription confidence: %s", confidence)
            if confidence >= self.min_confidence:
                # Return best transcription
                self._logger.debug(hyp.hypstr)
                return hyp.hypstr, confidence

            self._logger.warning(
                "Transcription did not meet confidence threshold: %s < %s",
                confidence,
                self.min_confidence,
            )

        # No transcription
        return "", 0

    # -------------------------------------------------------------------------

    def get_problems(self) -> Dict[str, Any]:
        """Get problems at startup."""
        problems: Dict[str, Any] = {}

        try:
            import pocketsphinx
        except Exception:
            problems[
                "Missing pocketsphinx"
            ] = "pocketsphinx Python library not installed. Try pip3 install pocketsphinx"

        ps_config = self.profile.get("speech_to_text.pocketsphinx", {})
        hmm_path = self.profile.read_path(
            ps_config.get("acoustic_model", "acoustic_model")
        )

        if not os.path.exists(hmm_path):
            problems[
                "Missing acoustic model"
            ] = f"Acoustic model directory not found at {hmm_path}. Did you download your profile?"

        base_dict_path = self.profile.read_path(
            ps_config.get("base_dictionary", "base_dictionary.txt")
        )

        if not os.path.exists(base_dict_path):
            problems[
                "Missing base dictionary"
            ] = f"Base dictionary not found at {base_dict_path}. Did you download your profile?"

        dict_path = self.profile.read_path(
            ps_config.get("dictionary", "dictionary.txt")
        )

        if not os.path.exists(dict_path):
            problems[
                "Missing dictionary"
            ] = f"Dictionary not found at {dict_path}. Did you train your profile?"

        lm_path = self.profile.read_path(
            ps_config.get("language_model", "language_model.txt")
        )

        if not os.path.exists(lm_path):
            problems[
                "Missing language model"
            ] = f"Language model not found at {lm_path}. Did you train your profile?"

        return problems


# -----------------------------------------------------------------------------
# HTTP based decoder on remote Rhasspy server
# -----------------------------------------------------------------------------


class RemoteDecoder(RhasspyActor):
    """Forwards speech to text request to a rmemote Rhasspy server"""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.remote_url = ""

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.remote_url = self.profile.get("speech_to_text.remote.url")

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, TranscribeWav):
            text = self.transcribe_wav(message.wav_data)
            self.send(message.receiver or sender, WavTranscription(text))

    def transcribe_wav(self, wav_data: bytes) -> str:
        """POST to remote server and return response."""
        import requests

        headers = {"Content-Type": "audio/wav"}
        self._logger.debug(
            "POSTing %d byte(s) of WAV data to %s", len(wav_data), self.remote_url
        )
        # Pass profile name through
        params = {"profile": self.profile.name}
        response = requests.post(
            self.remote_url, headers=headers, data=wav_data, params=params
        )

        try:
            response.raise_for_status()
        except Exception:
            self._logger.exception("transcribe_wav")
            return ""

        return response.text


# -----------------------------------------------------------------------------
# Kaldi Decoder
# http://kaldi-asr.org
# -----------------------------------------------------------------------------


class KaldiDecoder(RhasspyActor):
    """Kaldi based decoder"""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.kaldi_dir: Optional[Path] = None
        self.model_dir: Optional[Path] = None
        self.graph_dir: Optional[Path] = None
        self.decode_path: Optional[Path] = None
        self.decode_command: List[str] = []

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.kaldi_dir = Path(
            os.path.expandvars(
                self.profile.get("speech_to_text.kaldi.kaldi_dir", "/opt/kaldi")
            )
        )

        model_dir_name = self.profile.get(
            "training.speech_to_text.kaldi.model_dir",
            self.profile.get("speech_to_text.kaldi.model_dir", "model"),
        )

        self.model_dir = Path(self.profile.read_path(model_dir_name))

        self.open_transcription = self.profile.get(
            "speech_to_text.kaldi.open_transcription", False
        )

        if self.open_transcription:
            self.graph_dir = self.model_dir / self.profile.get(
                "speech_to_text.kaldi.base_graph", "base_graph"
            )
        else:
            self.graph_dir = self.model_dir / self.profile.get(
                "speech_to_text.kaldi.graph", "graph"
            )

        self.decode_path = Path(self.profile.read_path(model_dir_name, "decode.sh"))

        self.decode_command = [
            "bash",
            str(self.decode_path),
            str(self.kaldi_dir),
            str(self.model_dir),
            str(self.graph_dir),
        ]

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, TranscribeWav):
            text = self.transcribe_wav(message.wav_data)
            self.send(message.receiver or sender, WavTranscription(text))

    def transcribe_wav(self, wav_data: bytes) -> str:
        """Get text from WAV by calling external Kaldi script."""
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", mode="wb+") as wav_file:
                # Ensure 16-bit 16Khz mono
                subprocess.run(
                    [
                        "sox",
                        "-t",
                        "wav",
                        "-",
                        "-r",
                        "16000",
                        "-e",
                        "signed-integer",
                        "-b",
                        "16",
                        "-c",
                        "1",
                        "-t",
                        "wav",
                        wav_file.name,
                    ],
                    check=True,
                    input=wav_data,
                )

                wav_file.seek(0)

                command = self.decode_command + [wav_file.name]
                self._logger.debug(command)

                try:
                    return (
                        subprocess.check_output(command, stderr=subprocess.STDOUT)
                        .decode()
                        .strip()
                    )
                except subprocess.CalledProcessError as e:
                    output = e.output.decode()
                    self._logger.error(output)
                    raise Exception(output)

        except Exception:
            self._logger.exception("transcribe_wav")
            return ""

    def get_problems(self) -> Dict[str, Any]:
        """Get problems at startup."""
        problems: Dict[str, Any] = {}

        assert self.kaldi_dir is not None
        if not self.kaldi_dir.is_dir():
            problems[
                "Missing Kaldi"
            ] = f"Kaldi not found at {self.kaldi_dir}. See http://kaldi-asr.org"

        assert self.graph_dir is not None
        hclg_path = self.graph_dir / "HCLG.fst"
        if not hclg_path.is_file():
            problems[
                "Missing HCLG.fst"
            ] = f"Graph not found at {hclg_path}. Did you train your profile?"

        conf_path = self.model_dir / "online" / "conf" / "online.conf"
        if not conf_path.is_file():
            problems[
                "Missing online.conf"
            ] = f"Configuration file not found at {conf_path}. Did you train your profile?"

        return problems


# -----------------------------------------------------------------------------
# Command Decoder
# -----------------------------------------------------------------------------


class CommandDecoder(RhasspyActor):
    """Command-line based decoder"""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.command: List[str] = []

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        program = os.path.expandvars(self.profile.get("speech_to_text.command.program"))
        arguments = [
            os.path.expandvars(str(a))
            for a in self.profile.get("speech_to_text.command.arguments", [])
        ]

        self.command = [program] + arguments

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, TranscribeWav):
            text = self.transcribe_wav(message.wav_data)
            self.send(message.receiver or sender, WavTranscription(text))

    def transcribe_wav(self, wav_data: bytes) -> str:
        """Get text from WAV using external program."""
        try:
            self._logger.debug(self.command)

            # WAV -> STDIN -> STDOUT -> text
            return (
                subprocess.run(
                    self.command, check=True, input=wav_data, stdout=subprocess.PIPE
                )
                .stdout.decode()
                .strip()
            )

        except Exception:
            self._logger.exception("transcribe_wav")
            return ""
