import os
import io
import time
import wave
import logging
import tempfile
import subprocess
from typing import Any, Optional, Tuple, Type, Dict

from .actor import RhasspyActor
from .profiles import Profile
from .utils import convert_wav

# -----------------------------------------------------------------------------


class TranscribeWav:
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
    def __init__(self, text: str, handle: bool = True, confidence: float = 1) -> None:
        self.text = text
        self.confidence = confidence
        self.handle = handle


# -----------------------------------------------------------------------------


def get_decoder_class(system: str) -> Type[RhasspyActor]:
    assert system in ["dummy", "pocketsphinx", "kaldi", "remote", "command"], (
        "Invalid speech to text system: %s" % system
    )

    if system == "pocketsphinx":
        # Use pocketsphinx locally
        return PocketsphinxDecoder
    elif system == "kaldi":
        # Use kaldi locally
        return KaldiDecoder
    elif system == "remote":
        # Use remote Rhasspy server
        return RemoteDecoder
    elif system == "command":
        # Use external program
        return CommandDecoder

    # Use dummy decoder as a fallback
    return DummyDecoder


# -----------------------------------------------------------------------------


class DummyDecoder(RhasspyActor):
    """Always returns an emptry transcription"""

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
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

    def to_started(self, from_state: str) -> None:
        self.min_confidence = self.profile.get(
            "speech_to_text.pocketsphinx.min_confidence", 0.0
        )
        self.preload = self.config.get("preload", False)
        if self.preload:
            with self._lock:
                try:
                    self.load_decoder()
                except Exception as e:
                    self._logger.warning(f"preload: {e}")

        self.transition("loaded")

    def in_loaded(self, message: Any, sender: RhasspyActor) -> None:
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
            except:
                self._logger.exception("transcribing wav")

                # Send empty transcription back
                self.send(
                    message.receiver or sender,
                    WavTranscription("", handle=message.handle),
                )

    # -------------------------------------------------------------------------

    def load_decoder(self) -> None:
        if self.decoder is None:
            # Load decoder
            import pocketsphinx

            ps_config = self.profile.get("speech_to_text.pocketsphinx", {})

            # Load decoder settings
            hmm_path = self.profile.read_path(
                ps_config.get("acoustic_model", "acoustic_model")
            )
            dict_path = self.profile.read_path(
                ps_config.get("dictionary", "dictionary.txt")
            )
            lm_path = self.profile.read_path(
                ps_config.get("language_model", "language_model.txt")
            )

            self._logger.debug(
                "Loading decoder with hmm=%s, dict=%s, lm=%s"
                % (hmm_path, dict_path, lm_path)
            )

            decoder_config = pocketsphinx.Decoder.default_config()
            decoder_config.set_string("-hmm", hmm_path)
            decoder_config.set_string("-dict", dict_path)
            decoder_config.set_string("-lm", lm_path)
            decoder_config.set_string("-logfn", "/dev/null")

            mllr_path = self.profile.read_path(ps_config["mllr_matrix"])
            if os.path.exists(mllr_path):
                self._logger.debug(
                    "Using tuned MLLR matrix for acoustic model: %s" % mllr_path
                )
                decoder_config.set_string("-mllr", mllr_path)

            self.decoder = pocketsphinx.Decoder(decoder_config)

    def transcribe_wav(self, wav_data: bytes) -> Tuple[str, float]:
        # Ensure 16-bit 16Khz mono
        assert self.decoder is not None
        data_size = len(wav_data)
        with io.BytesIO(wav_data) as wav_io:
            with wave.open(wav_io, "rb") as wav_file:
                rate, width, channels = (
                    wav_file.getframerate(),
                    wav_file.getsampwidth(),
                    wav_file.getnchannels(),
                )
                self._logger.debug(
                    "rate=%s, width=%s, channels=%s." % (rate, width, channels)
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

        self._logger.debug("Decoded WAV in %s second(s)" % (end_time - start_time))

        hyp = self.decoder.hyp()
        if hyp is not None:
            confidence = self.decoder.get_logmath().exp(hyp.prob)
            self._logger.debug(f"Transcription confidence: {confidence}")
            if confidence >= self.min_confidence:
                # Return best transcription
                self._logger.debug(hyp.hypstr)
                return hyp.hypstr, confidence
            else:
                self._logger.warning(
                    f"Transcription did not meet confidence threshold: {confidence} < {self.min_confidence}"
                )

        # No transcription
        return "", 0

    # -------------------------------------------------------------------------

    def get_problems(self) -> Dict[str, Any]:
        problems: Dict[str, Any] = {}

        try:
            import pocketsphinx
        except:
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

    def to_started(self, from_state: str) -> None:
        self.remote_url = self.profile.get("speech_to_text.remote.url")

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, TranscribeWav):
            text = self.transcribe_wav(message.wav_data)
            self.send(message.receiver or sender, WavTranscription(text))

    def transcribe_wav(self, wav_data: bytes) -> str:
        import requests

        headers = {"Content-Type": "audio/wav"}
        self._logger.debug(
            "POSTing %d byte(s) of WAV data to %s" % (len(wav_data), self.remote_url)
        )
        # Pass profile name through
        params = {"profile": self.profile.name}
        response = requests.post(
            self.remote_url, headers=headers, data=wav_data, params=params
        )

        try:
            response.raise_for_status()
        except Exception as e:
            self._logger.exception("transcribe_wav")
            return ""

        return response.text


# -----------------------------------------------------------------------------
# Kaldi Decoder
# http://kaldi-asr.org
# -----------------------------------------------------------------------------


class KaldiDecoder(RhasspyActor):
    """Kaldi based decoder"""

    def to_started(self, from_state: str) -> None:
        self.kaldi_dir = os.path.expandvars(
            self.profile.get("speech_to_text.kaldi.kaldi_dir", "/opt/kaldi")
        )

        model_dir_name = self.profile.get(
            "training.speech_to_text.kaldi.model_dir",
            self.profile.get("speech_to_text.kaldi.model_dir", "model"),
        )

        self.model_dir = self.profile.read_path(model_dir_name)

        self.graph_dir = os.path.join(
            self.model_dir, self.profile.get("speech_to_text.kaldi.graph_dir", "graph")
        )
        self.decode_command = [
            "bash",
            self.profile.read_path(model_dir_name, "decode.sh"),
            self.kaldi_dir,
            self.model_dir,
            self.graph_dir,
        ]

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, TranscribeWav):
            text = self.transcribe_wav(message.wav_data)
            self.send(message.receiver or sender, WavTranscription(text))

    def transcribe_wav(self, wav_data: bytes) -> str:
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

        except Exception as e:
            self._logger.exception("transcribe_wav")
            return ""


# -----------------------------------------------------------------------------
# Command Decoder
# -----------------------------------------------------------------------------


class CommandDecoder(RhasspyActor):
    """Command-line based decoder"""

    def to_started(self, from_state: str) -> None:
        program = os.path.expandvars(self.profile.get("speech_to_text.command.program"))
        arguments = [
            os.path.expandvars(str(a))
            for a in self.profile.get("speech_to_text.command.arguments", [])
        ]

        self.command = [program] + arguments

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, TranscribeWav):
            text = self.transcribe_wav(message.wav_data)
            self.send(message.receiver or sender, WavTranscription(text))

    def transcribe_wav(self, wav_data: bytes) -> str:
        try:
            self._logger.debug(self.command)

            # WAV -> STDIN -> STDOUT -> text
            return (
                subprocess.check_output(self.command, input=wav_data).decode().strip()
            )

        except Exception as e:
            self._logger.exception("transcribe_wav")
            return ""
