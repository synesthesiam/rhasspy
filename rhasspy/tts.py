"""Text to speech support."""
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Type
from urllib.parse import urljoin

import requests

from rhasspy.actor import Configured, ConfigureEvent, RhasspyActor
from rhasspy.events import (
    PauseListeningForWakeWord,
    PlayWavData,
    ResumeListeningForWakeWord,
    SentenceSpoken,
    SpeakSentence,
    WavPlayed,
)
from rhasspy.utils import hass_request_kwargs

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
        "hass_tts",
    ], f"Invalid text to speech system: {system}"

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
    if system == "hass_tts":
        # Use Home Assistant TTS platform
        return HomeAssistantSentenceSpeaker

    # Use dummy as a fallback
    return DummySentenceSpeaker


# -----------------------------------------------------------------------------


class DummySentenceSpeaker(RhasspyActor):
    """Always returns an empty WAV buffer."""

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, SpeakSentence):
            self.send(message.receiver or sender, SentenceSpoken())


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
        self.wake_on_start = False
        self.disable_wake = True
        self.enable_wake = False
        self.wake: Optional[RhasspyActor] = None

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.voice = self.profile.get(
            "text_to_speech.espeak.voice", None
        ) or self.profile.get("language", None)
        self.player = self.config["player"]
        self.wake = self.config.get("wake")
        self.wake_on_start = self.profile.get("rhasspy.listen_on_start", False)
        self.disable_wake = self.profile.get("text_to_speech.disable_wake", True)
        self.transition("ready")

    def in_ready(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in ready state."""
        if isinstance(message, SpeakSentence):
            self.receiver = message.receiver or sender
            voice = message.voice or message.language or self.voice
            self.wav_data = self.speak(message.sentence, voice=voice)

            if message.play:
                self.enable_wake = False
                if self.wake and self.disable_wake:
                    # Disable wake word
                    self.send(self.wake, PauseListeningForWakeWord())
                    self.enable_wake = self.wake_on_start

                self.transition("speaking")
                self.send(
                    self.player, PlayWavData(self.wav_data, siteId=message.siteId)
                )
            else:
                self.transition("ready")
                self.send(self.receiver, SentenceSpoken(self.wav_data))

    def in_speaking(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in speaking state."""
        if isinstance(message, WavPlayed):
            self.transition("ready")
            self.send(self.receiver, SentenceSpoken(self.wav_data))

            if self.wake and self.enable_wake:
                # Re-enable wake word
                self.send(self.wake, ResumeListeningForWakeWord())

    # -------------------------------------------------------------------------

    def speak(self, sentence: str, voice: Optional[str] = None) -> bytes:
        """Get WAV buffer for sentence."""
        try:
            espeak_cmd = ["espeak"]
            if voice:
                espeak_cmd.extend(["-v", str(voice)])

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
        self.wake_on_start = False
        self.disable_wake = True
        self.enable_wake = False
        self.wake: Optional[RhasspyActor] = None

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.voice = self.profile.get("text_to_speech.flite.voice", "kal16")
        self.player = self.config["player"]
        self.wake = self.config.get("wake")
        self.wake_on_start = self.profile.get("rhasspy.listen_on_start", False)
        self.disable_wake = self.profile.get("text_to_speech.disable_wake", True)
        self.transition("ready")

    def in_ready(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in ready state."""
        if isinstance(message, SpeakSentence):
            self.receiver = message.receiver or sender
            voice = message.voice or message.language or self.voice
            self.wav_data = self.speak(message.sentence, voice=voice)

            if message.play:
                self.enable_wake = False
                if self.wake and self.disable_wake:
                    # Disable wake word
                    self.send(self.wake, PauseListeningForWakeWord())
                    self.enable_wake = self.wake_on_start

                self.transition("speaking")
                self.send(
                    self.player, PlayWavData(self.wav_data, siteId=message.siteId)
                )
            else:
                self.transition("ready")
                self.send(self.receiver, SentenceSpoken(self.wav_data))

    def in_speaking(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in speaking state."""
        if isinstance(message, WavPlayed):
            self.transition("ready")
            self.send(self.receiver, SentenceSpoken(self.wav_data))

            if self.wake and self.enable_wake:
                # Re-enable wake word
                self.send(self.wake, ResumeListeningForWakeWord())

    # -------------------------------------------------------------------------

    def speak(self, sentence: str, voice: Optional[str] = None) -> bytes:
        """Get WAV buffer for sentence."""
        try:
            flite_cmd = ["flite", "-t", sentence, "-o", "/dev/stdout"]
            if voice:
                flite_cmd.extend(["-voice", str(voice)])

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
        self.language: str = ""
        self.wav_data: bytes = bytes()
        self.wake_on_start = False
        self.disable_wake = True
        self.enable_wake = False
        self.wake: Optional[RhasspyActor] = None

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.player = self.config["player"]
        self.language = self.profile.get("text_to_speech.picotts.language", "")
        self.wake = self.config.get("wake")
        self.wake_on_start = self.profile.get("rhasspy.listen_on_start", False)
        self.disable_wake = self.profile.get("text_to_speech.disable_wake", True)

        self.transition("ready")

    def in_ready(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in ready state."""
        if isinstance(message, SpeakSentence):
            self.receiver = message.receiver or sender
            language = message.language or message.voice or self.language
            self.wav_data = self.speak(message.sentence, language=language)

            if message.play:
                self.enable_wake = False
                if self.wake and self.disable_wake:
                    # Disable wake word
                    self.send(self.wake, PauseListeningForWakeWord())
                    self.enable_wake = self.wake_on_start

                self.transition("speaking")
                self.send(
                    self.player, PlayWavData(self.wav_data, siteId=message.siteId)
                )
            else:
                self.transition("ready")
                self.send(self.receiver, SentenceSpoken(self.wav_data))

    def in_speaking(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in speaking state."""
        if isinstance(message, WavPlayed):
            self.transition("ready")
            self.send(self.receiver, SentenceSpoken(self.wav_data))

            if self.wake and self.enable_wake:
                # Re-enable wake word
                self.send(self.wake, ResumeListeningForWakeWord())

    # -------------------------------------------------------------------------

    def speak(self, sentence: str, language: Optional[str] = None) -> bytes:
        """Get WAV buffer for sentence."""
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", mode="wb") as wav_file:
                pico_cmd = ["pico2wave", "-w", wav_file.name]
                if language:
                    pico_cmd.extend(["-l", str(language)])

                pico_cmd.append(sentence)
                self._logger.debug(pico_cmd)

                subprocess.check_call(pico_cmd)
                return open(wav_file.name, "rb").read()
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
        self.voice: Optional[str] = None
        self.locale: str = ""
        self.player: Optional[RhasspyActor] = None
        self.receiver: Optional[RhasspyActor] = None
        self.wav_data = bytes()
        self.effects: Dict[str, Any] = {}
        self.wake_on_start = False
        self.disable_wake = True
        self.enable_wake = False
        self.wake: Optional[RhasspyActor] = None

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.url = self.profile.get(
            "text_to_speech.marytts.url", "http://localhost:59125"
        )

        if "process" not in self.url:
            self.url = urljoin(self.url, "process")

        self.voice = self.profile.get("text_to_speech.marytts.voice", None)
        self.locale = self.profile.get("text_to_speech.marytts.locale", "en-US")
        self.effects = self.profile.get("text_to_speech.marytts.effects", {})

        self.player = self.config["player"]
        self.wake = self.config.get("wake")
        self.wake_on_start = self.profile.get("rhasspy.listen_on_start", False)
        self.disable_wake = self.profile.get("text_to_speech.disable_wake", True)
        self.transition("ready")

    def in_ready(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in ready state."""
        if isinstance(message, SpeakSentence):
            self.receiver = message.receiver or sender
            voice = message.voice or self.voice
            locale = message.language or self.locale or "en-US"
            self.wav_data = self.speak(message.sentence, locale, voice=voice)

            if message.play:
                self.enable_wake = False
                if self.wake and self.disable_wake:
                    # Disable wake word
                    self.send(self.wake, PauseListeningForWakeWord())
                    self.enable_wake = self.wake_on_start

                self.transition("speaking")
                self.send(
                    self.player, PlayWavData(self.wav_data, siteId=message.siteId)
                )
            else:
                self.transition("ready")
                self.send(self.receiver, SentenceSpoken(self.wav_data))

    def in_speaking(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in speaking state."""
        if isinstance(message, WavPlayed):
            self.transition("ready")
            self.send(self.receiver, SentenceSpoken(self.wav_data))

            if self.wake and self.enable_wake:
                # Re-enable wake word
                self.send(self.wake, ResumeListeningForWakeWord())

    # -------------------------------------------------------------------------

    def speak(self, sentence: str, locale: str, voice: Optional[str] = None) -> bytes:
        """Get WAV buffer for sentence."""
        try:
            params = {
                "INPUT_TEXT": sentence,
                "INPUT_TYPE": "TEXT",
                "AUDIO": "WAVE",
                "OUTPUT_TYPE": "AUDIO",
                "LOCALE": locale,
            }
            params.update(self.effects)

            if voice is not None:
                params["VOICE"] = voice

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
        self.wake_on_start = False
        self.disable_wake = True
        self.enable_wake = False
        self.wake: Optional[RhasspyActor] = None

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        program = os.path.expandvars(self.profile.get("text_to_speech.command.program"))
        arguments = [
            os.path.expandvars(str(a))
            for a in self.profile.get("text_to_speech.command.arguments", [])
        ]

        self.command = [program] + arguments
        self.player = self.config["player"]
        self.wake = self.config.get("wake")
        self.wake_on_start = self.profile.get("rhasspy.listen_on_start", False)
        self.disable_wake = self.profile.get("text_to_speech.disable_wake", True)
        self.transition("ready")

    def in_ready(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in ready state."""
        if isinstance(message, SpeakSentence):
            self.receiver = message.receiver or sender
            self.wav_data = self.speak(message.sentence)

            if message.play:
                self.enable_wake = False
                if self.wake and self.disable_wake:
                    # Disable wake word
                    self.send(self.wake, PauseListeningForWakeWord())
                    self.enable_wake = self.wake_on_start

                self.transition("speaking")
                self.send(
                    self.player, PlayWavData(self.wav_data, siteId=message.siteId)
                )
            else:
                self.transition("ready")
                self.send(self.receiver, SentenceSpoken(self.wav_data))

    def in_speaking(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in speaking state."""
        if isinstance(message, WavPlayed):
            self.transition("ready")
            self.send(self.receiver, SentenceSpoken(self.wav_data))

            if self.wake and self.enable_wake:
                # Re-enable wake word
                self.send(self.wake, ResumeListeningForWakeWord())

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

        self.wake_on_start = False
        self.disable_wake = True
        self.enable_wake = False
        self.wake: Optional[RhasspyActor] = None

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
        self.wake = self.config.get("wake")
        self.wake_on_start = self.profile.get("rhasspy.listen_on_start", False)
        self.disable_wake = self.profile.get("text_to_speech.disable_wake", True)

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
                voice = message.voice or self.voice
                language_code = message.language or self.language_code
                self.wav_data = self.speak(message.sentence, voice, language_code)

                if message.play:
                    self.enable_wake = False
                    if self.wake and self.disable_wake:
                        # Disable wake word
                        self.send(self.wake, PauseListeningForWakeWord())
                        self.enable_wake = self.wake_on_start

                    self.transition("speaking")
                    self.send(
                        self.player, PlayWavData(self.wav_data, siteId=message.siteId)
                    )
                else:
                    self.transition("ready")
                    self.send(self.receiver, SentenceSpoken(self.wav_data))
            except Exception:
                self._logger.exception("speak")

                # Try fallback system
                try:
                    assert (
                        self.fallback_actor is not None
                    ), "No fallback text to speech system"

                    self._logger.debug("Falling back to %s", self.fallback_actor)
                    self.transition("speaking")
                    self.send(
                        self.fallback_actor,
                        SpeakSentence(
                            message.sentence,
                            play=message.play,
                            voice=message.voice,
                            language=message.language,
                            siteId=message.siteId,
                        ),
                    )
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

            if self.wake and self.enable_wake:
                # Re-enable wake word
                self.send(self.wake, ResumeListeningForWakeWord())
        elif isinstance(message, SentenceSpoken):
            # From fallback actor
            self.transition("ready")
            self.send(self.receiver, message)

    # -------------------------------------------------------------------------

    def speak(self, sentence: str, voice: str, language_code: str) -> bytes:
        """Get WAV buffer for sentence."""
        # Try to pull WAV from cache first
        sentence_hash = self._get_sentence_hash(sentence, voice, language_code)
        cached_wav_path = os.path.join(
            self.cache_dir, f"{sentence_hash.hexdigest()}.wav"
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
            language_code,
            voice,
            self.gender,
            self.sample_rate,
        )

        # pylint: disable=E0401
        from google.cloud import texttospeech

        client = texttospeech.TextToSpeechClient()

        # pylint: disable=E1101
        synthesis_input = texttospeech.types.SynthesisInput(text=sentence)

        # pylint: disable=E1101
        voice_params = texttospeech.types.VoiceSelectionParams(
            language_code=language_code,
            name=language_code + "-" + voice,
            ssml_gender=self.gender,
        )

        # pylint: disable=E1101
        audio_config = texttospeech.types.AudioConfig(
            audio_encoding="LINEAR16", sample_rate_hertz=self.sample_rate
        )

        response = client.synthesize_speech(synthesis_input, voice_params, audio_config)

        # Save to cache
        with open(cached_wav_path, "wb") as cached_wav_file:
            cached_wav_file.write(response.audio_content)

        return response.audio_content

    # -------------------------------------------------------------------------

    def _get_sentence_hash(self, sentence: str, voice: str, language_code: str):
        """Get hash for cache."""
        m = hashlib.md5()
        m.update(
            "_".join(
                [
                    sentence,
                    language_code + "-" + voice,
                    self.gender,
                    str(self.sample_rate),
                    language_code,
                ]
            ).encode("utf-8")
        )

        return m


# -----------------------------------------------------------------------------
# HomeAssistant TTS
# https://www.home-assistant.io/integrations/tts
# -----------------------------------------------------------------------------


class HomeAssistantSentenceSpeaker(RhasspyActor):
    """Use Home Assistant TTS platform to generate speech"""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.command: List[str] = []
        self.hass_config: Dict[str, Any] = {}
        self.pem_file: Optional[str] = ""
        self.platform: Optional[str] = None

        self.player: Optional[RhasspyActor] = None
        self.receiver: Optional[RhasspyActor] = None
        self.wav_data = bytes()
        self.wake_on_start = False
        self.disable_wake = True
        self.enable_wake = False
        self.wake: Optional[RhasspyActor] = None

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.hass_config = self.profile.get("home_assistant", {})

        # PEM file for self-signed HA certificates
        self.pem_file = self.hass_config.get("pem_file", "")
        if self.pem_file:
            self.pem_file = os.path.expandvars(self.pem_file)
            self._logger.debug("Using PEM file at %s", self.pem_file)
        else:
            self.pem_file = None  # disabled

        self.platform = self.profile.get("text_to_speech.hass_tts.platform")

        self.player = self.config["player"]
        self.wake = self.config.get("wake")
        self.wake_on_start = self.profile.get("rhasspy.listen_on_start", False)
        self.disable_wake = self.profile.get("text_to_speech.disable_wake", True)
        self.transition("ready")

    def in_ready(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in ready state."""
        if isinstance(message, SpeakSentence):
            self.receiver = message.receiver or sender
            self.wav_data = self.speak(message.sentence)

            if message.play:
                self.enable_wake = False
                if self.wake and self.disable_wake:
                    # Disable wake word
                    self.send(self.wake, PauseListeningForWakeWord())
                    self.enable_wake = self.wake_on_start

                self.transition("speaking")
                self.send(
                    self.player, PlayWavData(self.wav_data, siteId=message.siteId)
                )
            else:
                self.transition("ready")
                self.send(self.receiver, SentenceSpoken(self.wav_data))

    def in_speaking(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in speaking state."""
        if isinstance(message, WavPlayed):
            self.transition("ready")
            self.send(self.receiver, SentenceSpoken(self.wav_data))

            if self.wake and self.enable_wake:
                # Re-enable wake word
                self.send(self.wake, ResumeListeningForWakeWord())

    # -------------------------------------------------------------------------

    def speak(self, sentence: str) -> bytes:
        """Get WAV buffer for sentence."""
        try:
            tts_url = urljoin(self.hass_config["url"], "api/tts_get_url")

            # Send to Home Assistant
            kwargs = hass_request_kwargs(self.hass_config, self.pem_file)
            kwargs["json"] = {"platform": self.platform, "message": sentence}

            if self.pem_file is not None:
                kwargs["verify"] = self.pem_file

            # POST to /api/tts_get_url
            response = requests.post(tts_url, **kwargs)
            response.raise_for_status()

            response_json = response.json()
            self._logger.debug(response_json)

            # Download MP3
            audio_url = response_json["url"]
            kwargs = hass_request_kwargs(self.hass_config, self.pem_file)

            if self.pem_file is not None:
                kwargs["verify"] = self.pem_file

            # GET audio data
            response = requests.get(audio_url, **kwargs)
            response.raise_for_status()

            audio_bytes = response.content
            self._logger.debug("Received %s byte(s) of audio data", len(audio_bytes))

            # Convert to WAV
            if audio_url.endswith(".mp3"):
                lame_command = ["lame", "--decode", "-", "-"]
                self._logger.debug(lame_command)

                return subprocess.run(
                    lame_command, input=audio_bytes, check=True, stdout=subprocess.PIPE
                ).stdout

            # Assume WAV
            return audio_bytes
        except Exception:
            self._logger.exception("speak")
            return bytes()

    def get_problems(self) -> Dict[str, Any]:
        """Get problems at startup."""
        problems: Dict[str, Any] = {}

        if not shutil.which("lame"):
            problems[
                "Missing LAME MP3 encoding"
            ] = "LAME MP3 encoder is not installed. Try apt-get install lame"

        if not self.platform:
            problems[
                "Missing platform name"
            ] = "Expected Home Assistant TTS platform name in text_to_speech.hass_tts.platform"

        api_url = urljoin(self.hass_config["url"], "api/")
        try:
            kwargs = hass_request_kwargs(self.hass_config, self.pem_file)
            requests.get(api_url, **kwargs)
        except Exception:
            problems[
                "Can't contact server"
            ] = f"Unable to reach your Home Assistant at {api_url}. Is it running?"

        return problems
