"""Text to speech support."""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict, Optional, Type, List
from urllib.parse import urljoin

import requests

from rhasspy.actor import Configured, ConfigureEvent, RhasspyActor
from rhasspy.audio_player import PlayWavData, WavPlayed

# -----------------------------------------------------------------------------


class SpeakSentence:
    """Request to speak a sentence."""

    def __init__(self, sentence: str, receiver: Optional[RhasspyActor] = None) -> None:
        self.sentence = sentence
        self.receiver = receiver


class SentenceSpoken:
    """Response when sentence is spoken."""

    def __init__(self, wav_data: bytes):
        self.wav_data = wav_data


# -----------------------------------------------------------------------------


def get_speech_class(system: str) -> Type[RhasspyActor]:
    """Get class for profile text to speech system."""
    assert system in [
        "dummy",
        "espeak",
        "marytts",
        "flite",
        "picotts",
        "command",
        "wavenet",
    ], ("Invalid text to speech system: %s" % system)

    if system == "espeak":
        # Use eSpeak directly
        return EspeakSentenceSpeaker
    if system == "marytts":
        # Use MaryTTS
        return MaryTTSSentenceSpeaker
    if system == "flite":
        # Use CMU's Flite
        return FliteSentenceSpeaker
    if system == "picotts":
        # Use SVOX PicoTTS
        return PicoTTSSentenceSpeaker
    if system == "command":
        # Use command-line text-to-speech system
        return CommandSentenceSpeaker
    if system == "wavenet":
        # Use WaveNet text-to-speech system
        return GoogleWaveNetSentenceSpeaker

    # Use dummy as a fallback
    return DummySentenceSpeaker


# -----------------------------------------------------------------------------


class DummySentenceSpeaker(RhasspyActor):
    """Always returns an empty WAV buffer."""

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, SpeakSentence):
            self.send(message.receiver or sender, SentenceSpoken(bytes()))


# -----------------------------------------------------------------------------
# eSpeak Text to Speech
# http://espeak.sourceforge.net
# -----------------------------------------------------------------------------


class EspeakSentenceSpeaker(RhasspyActor):
    """Speak sentences using eSpeak."""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.voice = None
        self.player: Optional[RhasspyActor] = None
        self.receiver: Optional[RhasspyActor] = None
        self.wav_data = bytes()

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.voice = self.profile.get(
            "text_to_speech.espeak.voice", None
        ) or self.profile.get("language", None)
        self.player = self.config["player"]
        self.transition("ready")

    def in_ready(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in ready state."""
        if isinstance(message, SpeakSentence):
            self.receiver = message.receiver or sender
            self.wav_data = self.speak(message.sentence)
            self.transition("speaking")
            self.send(self.player, PlayWavData(self.wav_data))

    def in_speaking(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in speaking state."""
        if isinstance(message, WavPlayed):
            self.transition("ready")
            self.send(self.receiver, SentenceSpoken(self.wav_data))

    # -------------------------------------------------------------------------

    def speak(self, sentence: str) -> bytes:
        """Get WAV buffer for sentence."""
        try:
            espeak_cmd = ["espeak"]
            if self.voice is not None:
                espeak_cmd.extend(["-v", str(self.voice)])

            espeak_cmd.append("--stdout")
            espeak_cmd.append(sentence)
            self._logger.debug(espeak_cmd)

            return subprocess.check_output(espeak_cmd)
        except Exception:
            self._logger.exception("speak")
            return bytes()

    # -------------------------------------------------------------------------

    def get_problems(self) -> Dict[str, Any]:
        """Get problems at startup."""
        problems: Dict[str, Any] = {}
        if not shutil.which("espeak"):
            problems[
                "Missing espeak"
            ] = "The espeak text to speech system is not installed. Try sudo apt-get install espeak"

        return problems


# -----------------------------------------------------------------------------
# Flite Text to Speech
# http://www.festvox.org/flite
# -----------------------------------------------------------------------------


class FliteSentenceSpeaker(RhasspyActor):
    """Speak sentences using flite."""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.voice = ""
        self.player: Optional[RhasspyActor] = None
        self.receiver: Optional[RhasspyActor] = None
        self.wav_data = bytes()

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.voice = self.profile.get("text_to_speech.flite.voice", "kal16")
        self.player = self.config["player"]
        self.transition("ready")

    def in_ready(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in ready state."""
        if isinstance(message, SpeakSentence):
            self.receiver = message.receiver or sender
            self.wav_data = self.speak(message.sentence)
            self.transition("speaking")
            self.send(self.player, PlayWavData(self.wav_data))

    def in_speaking(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in speaking state."""
        if isinstance(message, WavPlayed):
            self.transition("ready")
            self.send(self.receiver, SentenceSpoken(self.wav_data))

    # -------------------------------------------------------------------------

    def speak(self, sentence: str) -> bytes:
        """Get WAV buffer for sentence."""
        try:
            flite_cmd = ["flite", "-t", sentence, "-o", "/dev/stdout"]
            if len(self.voice) > 0:
                flite_cmd.extend(["-voice", str(self.voice)])

            self._logger.debug(flite_cmd)

            return subprocess.check_output(flite_cmd)
        except Exception:
            self._logger.exception("speak")
            return bytes()

    # -------------------------------------------------------------------------

    def get_problems(self) -> Dict[str, Any]:
        """Get problems at startup."""
        problems: Dict[str, Any] = {}
        if not shutil.which("flite"):
            problems[
                "Missing flite"
            ] = "The flite text to speech system is not installed. Try sudo apt-get install flite"

        return problems


# -----------------------------------------------------------------------------
# PicoTTS
# https://en.wikipedia.org/wiki/SVOX
# -----------------------------------------------------------------------------


class PicoTTSSentenceSpeaker(RhasspyActor):
    """Speak sentences using picotts."""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.player: Optional[RhasspyActor] = None
        self.receiver: Optional[RhasspyActor] = None
        self.language = ""
        self.temp_dir = None
        self.wav_path = ""
        self.wav_data = bytes()

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.player = self.config["player"]
        self.language = self.profile.get("text_to_speech.picotts.language", "")
        self.temp_dir = tempfile.TemporaryDirectory()
        self.wav_path = os.path.join(self.temp_dir.name, "output.wav")
        os.symlink("/dev/stdout", self.wav_path)

        self.transition("ready")

    def in_ready(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in ready state."""
        if isinstance(message, SpeakSentence):
            self.receiver = message.receiver or sender
            self.wav_data = self.speak(message.sentence)
            self.transition("speaking")
            self.send(self.player, PlayWavData(self.wav_data))

    def in_speaking(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in speaking state."""
        if isinstance(message, WavPlayed):
            self.transition("ready")
            self.send(self.receiver, SentenceSpoken(self.wav_data))

    def to_stopped(self, from_state: str) -> None:
        """Transition to stopped state."""
        self.temp_dir.cleanup()

    # -------------------------------------------------------------------------

    def speak(self, sentence: str) -> bytes:
        """Get WAV buffer for sentence."""
        try:
            pico_cmd = ["pico2wave", "-w", self.wav_path]
            if len(self.language) > 0:
                pico_cmd.extend(["-l", str(self.language)])

            pico_cmd.append(sentence)
            self._logger.debug(pico_cmd)

            return subprocess.check_output(pico_cmd)
        except Exception:
            self._logger.exception("speak")
            return bytes()

    # -------------------------------------------------------------------------

    def get_problems(self) -> Dict[str, Any]:
        """Get problems at startup."""
        problems: Dict[str, Any] = {}
        if not shutil.which("pico2wave"):
            problems[
                "Missing pico2wave"
            ] = "The pico text to speech system is not installed. Try sudo apt-get install libttspico-utils"

        return problems


# -----------------------------------------------------------------------------
# MaryTTS Server
# http://mary.dfki.de
# -----------------------------------------------------------------------------


class MaryTTSSentenceSpeaker(RhasspyActor):
    """Speak sentence with remote MaryTTS server."""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.url = ""
        self.voice = None
        self.locale = ""
        self.player: Optional[RhasspyActor] = None
        self.receiver: Optional[RhasspyActor] = None
        self.wav_data = bytes()

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.url = self.profile.get(
            "text_to_speech.marytts.url", "http://localhost:59125"
        )

        if "process" not in self.url:
            self.url = urljoin(self.url, "process")

        self.voice = self.profile.get("text_to_speech.marytts.voice", None)
        self.locale = self.profile.get("text_to_speech.marytts.locale", "en-US")

        self.player = self.config["player"]
        self.transition("ready")

    def in_ready(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in ready state."""
        if isinstance(message, SpeakSentence):
            self.receiver = message.receiver or sender
            self.wav_data = self.speak(message.sentence)
            self.transition("speaking")
            self.send(self.player, PlayWavData(self.wav_data))

    def in_speaking(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in speaking state."""
        if isinstance(message, WavPlayed):
            self.transition("ready")
            self.send(self.receiver, SentenceSpoken(self.wav_data))

    # -------------------------------------------------------------------------

    def speak(self, sentence: str) -> bytes:
        """Get WAV buffer for sentence."""
        try:
            params = {
                "INPUT_TEXT": sentence,
                "INPUT_TYPE": "TEXT",
                "AUDIO": "WAVE",
                "OUTPUT_TYPE": "AUDIO",
                "LOCALE": self.locale,
            }

            if self.voice is not None:
                params["VOICE"] = self.voice

            self._logger.debug(params)

            result = requests.get(self.url, params=params)
            result.raise_for_status()
            return result.content
        except Exception:
            self._logger.exception("speak")
            return bytes()

    # -------------------------------------------------------------------------

    def get_problems(self) -> Dict[str, Any]:
        """Get problems at startup."""
        problems: Dict[str, Any] = {}
        try:
            url = self.url
            if url.endswith("/process"):
                url = url[:-8]

            requests.get(url)
        except Exception:
            problems[
                "Can't contact server"
            ] = f"Unable to reach your MaryTTS server at {self.url}. Is it running?"

        return problems


# -----------------------------------------------------------------------------
# Command Text to Speech
# -----------------------------------------------------------------------------


class CommandSentenceSpeaker(RhasspyActor):
    """Command-line based text to speech"""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.command: List[str] = []
        self.player: Optional[RhasspyActor] = None
        self.receiver: Optional[RhasspyActor] = None
        self.wav_data = bytes()

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        program = os.path.expandvars(self.profile.get("text_to_speech.command.program"))
        arguments = [
            os.path.expandvars(str(a))
            for a in self.profile.get("text_to_speech.command.arguments", [])
        ]

        self.command = [program] + arguments
        self.player = self.config["player"]
        self.transition("ready")

    def in_ready(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in ready state."""
        if isinstance(message, SpeakSentence):
            self.receiver = message.receiver or sender
            self.wav_data = self.speak(message.sentence)
            self.transition("speaking")
            self.send(self.player, PlayWavData(self.wav_data))

    def in_speaking(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in speaking state."""
        if isinstance(message, WavPlayed):
            self.transition("ready")
            self.send(self.receiver, SentenceSpoken(self.wav_data))

    # -------------------------------------------------------------------------

    def speak(self, sentence: str) -> bytes:
        """Get WAV buffer for sentence."""
        try:
            self._logger.debug(self.command)

            # text -> STDIN -> STDOUT -> WAV
            return subprocess.run(
                self.command,
                check=True,
                input=sentence.encode(),
                stdout=subprocess.PIPE,
            ).stdout

        except Exception:
            self._logger.exception("speak")
            return bytes()


# -----------------------------------------------------------------------------
# Google WaveNet
# https://cloud.google.com/text-to-speech/docs/wavenet
#
# Contributed by Romkabouter (https://github.com/Romkabouter)
# -----------------------------------------------------------------------------


class GoogleWaveNetSentenceSpeaker(RhasspyActor):
    """Uses Google's WaveNet text to speech cloud API (online)"""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.wav_data: bytes = bytes()
        self.cache_dir = ""
        self.url = ""
        self.voice = ""
        self.gender = ""
        self.sample_rate = 0
        self.language_code = ""
        self.player: Optional[RhasspyActor] = None
        self.receiver: Optional[RhasspyActor] = None
        self.fallback_actor: Optional[RhasspyActor] = None
        self.credentials_json = ""

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.cache_dir = self.profile.write_dir(
            self.profile.get("text_to_speech.wavenet.cache_dir", "tts/googlewavenet")
        )

        # Create cache directory in profile if it doesn't exist
        os.makedirs(self.cache_dir, exist_ok=True)

        # Load settings
        self.url = self.profile.get(
            "text_to_speech.wavenet.url",
            "https://texttospeech.googleapis.com/v1/text:synthesize",
        )
        self.voice = self.profile.get("text_to_speech.wavenet.voice", "Wavenet-C")
        self.gender = self.profile.get("text_to_speech.wavenet.gender", "FEMALE")
        self.sample_rate = int(
            self.profile.get("text_to_speech.wavenet.sample_rate", 22050)
        )
        self.language_code = self.profile.get(
            "text_to_speech.wavenet.language_code", "en-US"
        )

        self.player = self.config["player"]

        # Create a child actor as a fallback.
        # This will load the appropriate settings, etc.
        fallback_tts = self.profile.get("text_to_speech.wavenet.fallback_tts", "espeak")
        assert fallback_tts != "wavenet", "Cannot fall back from wavenet to wavenet"
        if fallback_tts:
            self._logger.debug(
                "Using %s as a fallback text to speech system", fallback_tts
            )
            fallback_class = get_speech_class(fallback_tts)
            self.fallback_actor = self.createActor(fallback_class)
            self.send(self.fallback_actor, ConfigureEvent(self.profile, **self.config))

        self.transition("ready")

    def in_ready(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in rady state."""
        if isinstance(message, SpeakSentence):
            self.wav_data = bytes()
            self.receiver = message.receiver or sender
            try:
                self.wav_data = self.speak(message.sentence)
                self.transition("speaking")
                self.send(self.player, PlayWavData(self.wav_data))
            except Exception:
                self._logger.exception("speak")

                # Try fallback system
                try:
                    assert (
                        self.fallback_actor is not None
                    ), "No fallback text to speech system"

                    self._logger.debug("Falling back to %s", self.fallback_actor)
                    self.transition("speaking")
                    self.send(self.fallback_actor, SpeakSentence(message.sentence))
                except Exception:
                    # Give up
                    self.transition("ready")
                    self.send(self.receiver, SentenceSpoken(bytes()))
        elif isinstance(message, Configured):
            # Fallback actor is configured
            pass

    def in_speaking(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in speaking state."""
        if isinstance(message, WavPlayed):
            self.transition("ready")
            self.send(self.receiver, SentenceSpoken(self.wav_data))
        elif isinstance(message, SentenceSpoken):
            # From fallback actor
            self.transition("ready")
            self.send(self.receiver, message)

    # -------------------------------------------------------------------------

    def speak(self, sentence: str) -> bytes:
        """Get WAV buffer for sentence."""
        # Try to pull WAV from cache first
        sentence_hash = self._get_sentence_hash(sentence)
        cached_wav_path = os.path.join(
            self.cache_dir, "{}.wav".format(sentence_hash.hexdigest())
        )

        if os.path.isfile(cached_wav_path):
            # Use WAV file from cache
            self._logger.debug("Using WAV from cache: %s", cached_wav_path)
            with open(cached_wav_path, mode="rb") as cached_wav_file:
                return cached_wav_file.read()

        # Call out to Google for WAV data
        self.credentials_json = self.profile.read_path(
            self.profile.get(
                "text_to_speech.wavenet.credentials_json",
                "tts/googlewavenet/credentials.json",
            )
        )

        # Verify credentials JSON file
        self._logger.debug("Trying credentials at %s", self.credentials_json)
        with open(self.credentials_json, "r") as credentials_file:
            json.load(credentials_file)

        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.credentials_json

        self._logger.debug(
            "Calling Wavenet (lang=%s, voice=%s, gender=%s, rate=%s)",
            self.language_code,
            self.voice,
            self.gender,
            self.sample_rate,
        )

        from google.cloud import texttospeech

        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.types.SynthesisInput(text=sentence)
        voice = texttospeech.types.VoiceSelectionParams(
            language_code=self.language_code,
            name=self.language_code + "-" + self.voice,
            ssml_gender=self.gender,
        )
        audio_config = texttospeech.types.AudioConfig(
            audio_encoding="LINEAR16", sample_rate_hertz=self.sample_rate
        )

        response = client.synthesize_speech(synthesis_input, voice, audio_config)

        # Save to cache
        with open(cached_wav_path, "wb") as cached_wav_file:
            cached_wav_file.write(response.audio_content)

        return response.audio_content

    # -------------------------------------------------------------------------

    def _get_sentence_hash(self, sentence: str):
        """Get hash for cache."""
        m = hashlib.md5()
        m.update(
            "_".join(
                [
                    sentence,
                    self.language_code + "-" + self.voice,
                    self.gender,
                    str(self.sample_rate),
                    self.language_code,
                ]
            ).encode("utf-8")
        )

        return m
