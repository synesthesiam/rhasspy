import os
import subprocess
import tempfile
from urllib.parse import urljoin
from typing import Any, Optional

import requests

from .actor import RhasspyActor
from .profiles import Profile
from .audio_player import PlayWavData, WavPlayed

# -----------------------------------------------------------------------------


class SpeakSentence:
    def __init__(self, sentence: str, receiver: Optional[RhasspyActor] = None) -> None:
        self.sentence = sentence
        self.receiver = receiver


class SentenceSpoken:
    pass


# -----------------------------------------------------------------------------


class DummySentenceSpeaker(RhasspyActor):
    """Does nothing."""

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, SpeakSentence):
            self.send(message.receiver or sender, SentenceSpoken())


# -----------------------------------------------------------------------------
# eSpeak Text to Speech
# http://espeak.sourceforge.net
# -----------------------------------------------------------------------------


class EspeakSentenceSpeaker(RhasspyActor):
    def to_started(self, from_state: str) -> None:
        self.voice = self.profile.get(
            "text_to_speech.espeak.voice", None
        ) or self.profile.get("language", None)
        self.player: RhasspyActor = self.config["player"]
        self.receiver: Optional[RhasspyActor] = None
        self.transition("ready")

    def in_ready(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, SpeakSentence):
            self.receiver = message.receiver or sender
            wav_data = self.speak(message.sentence)
            self.transition("speaking")
            self.send(self.player, PlayWavData(wav_data))

    def in_speaking(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, WavPlayed):
            self.transition("ready")
            self.send(self.receiver, SentenceSpoken())

    # -------------------------------------------------------------------------

    def speak(self, sentence: str) -> bytes:
        try:
            espeak_cmd = ["espeak"]
            if self.voice is not None:
                espeak_cmd.extend(["-v", str(self.voice)])

            espeak_cmd.append("--stdout")
            espeak_cmd.append(sentence)
            self._logger.debug(espeak_cmd)

            return subprocess.check_output(espeak_cmd)
        except:
            self._logger.exception("speak")
            return bytes()


# -----------------------------------------------------------------------------
# Flite Text to Speech
# http://www.festvox.org/flite
# -----------------------------------------------------------------------------


class FliteSentenceSpeaker(RhasspyActor):
    def to_started(self, from_state: str) -> None:
        self.voice = self.profile.get("text_to_speech.flite.voice", "kal16")
        self.player: RhasspyActor = self.config["player"]
        self.receiver: Optional[RhasspyActor] = None
        self.transition("ready")

    def in_ready(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, SpeakSentence):
            self.receiver = message.receiver or sender
            wav_data = self.speak(message.sentence)
            self.transition("speaking")
            self.send(self.player, PlayWavData(wav_data))

    def in_speaking(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, WavPlayed):
            self.transition("ready")
            self.send(self.receiver, SentenceSpoken())

    # -------------------------------------------------------------------------

    def speak(self, sentence: str) -> bytes:
        try:
            flite_cmd = ["flite", "-t", sentence, "-o", "/dev/stdout"]
            if len(self.voice) > 0:
                flite_cmd.extend(["-voice", str(self.voice)])

            self._logger.debug(flite_cmd)

            return subprocess.check_output(flite_cmd)
        except:
            self._logger.exception("speak")
            return bytes()


# -----------------------------------------------------------------------------
# PicoTTS
# https://en.wikipedia.org/wiki/SVOX
# -----------------------------------------------------------------------------


class PicoTTSSentenceSpeaker(RhasspyActor):
    def to_started(self, from_state: str) -> None:
        self.player: RhasspyActor = self.config["player"]
        self.receiver: Optional[RhasspyActor] = None

        self.language = self.profile.get("text_to_speech.picotts.language", "")
        self.temp_dir = tempfile.TemporaryDirectory()
        self.wav_path = os.path.join(self.temp_dir.name, "output.wav")
        os.symlink("/dev/stdout", self.wav_path)

        self.transition("ready")

    def in_ready(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, SpeakSentence):
            self.receiver = message.receiver or sender
            wav_data = self.speak(message.sentence)
            self.transition("speaking")
            self.send(self.player, PlayWavData(wav_data))

    def in_speaking(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, WavPlayed):
            self.transition("ready")
            self.send(self.receiver, SentenceSpoken())

    def to_stopped(self, from_state: str) -> None:
        self.temp_dir.cleanup()

    # -------------------------------------------------------------------------

    def speak(self, sentence: str) -> bytes:
        try:
            pico_cmd = ["pico2wave", "-w", self.wav_path]
            if len(self.language) > 0:
                pico_cmd.extend(["-l", str(self.language)])

            pico_cmd.append(sentence)
            self._logger.debug(pico_cmd)

            return subprocess.check_output(pico_cmd)
        except:
            self._logger.exception("speak")
            return bytes()


# -----------------------------------------------------------------------------
# MaryTTS Server
# http://mary.dfki.de
# -----------------------------------------------------------------------------


class MaryTTSSentenceSpeaker(RhasspyActor):
    def to_started(self, from_state: str) -> None:
        self.url = self.profile.get(
            "text_to_speech.marytts.url", "http://localhost:59125"
        )

        if not "process" in self.url:
            self.url = urljoin(self.url, "process")

        self.voice = self.profile.get("text_to_speech.marytts.voice", None)
        self.locale = self.profile.get("text_to_speech.marytts.locale", "en-US")

        self.player: RhasspyActor = self.config["player"]
        self.receiver: Optional[RhasspyActor] = None
        self.transition("ready")

    def in_ready(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, SpeakSentence):
            self.receiver = message.receiver or sender
            wav_data = self.speak(message.sentence)
            self.transition("speaking")
            self.send(self.player, PlayWavData(wav_data))

    def in_speaking(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, WavPlayed):
            self.transition("ready")
            self.send(self.receiver, SentenceSpoken())

    # -------------------------------------------------------------------------

    def speak(self, sentence: str) -> bytes:
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
        except:
            self._logger.exception("speak")
            return bytes()


# -----------------------------------------------------------------------------
# Command Text to Speech
# -----------------------------------------------------------------------------


class CommandSentenceSpeaker(RhasspyActor):
    """Command-line based text to speech"""

    def to_started(self, from_state: str) -> None:
        program = os.path.expandvars(self.profile.get("text_to_speech.command.program"))
        arguments = [
            os.path.expandvars(str(a))
            for a in self.profile.get("text_to_speech.command.arguments", [])
        ]

        self.command = [program] + arguments
        self.player: RhasspyActor = self.config["player"]
        self.receiver: Optional[RhasspyActor] = None
        self.transition("ready")

    def in_ready(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, SpeakSentence):
            self.receiver = message.receiver or sender
            wav_data = self.speak(message.sentence)
            self.transition("speaking")
            self.send(self.player, PlayWavData(wav_data))

    def in_speaking(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, WavPlayed):
            self.transition("ready")
            self.send(self.receiver, SentenceSpoken())

    # -------------------------------------------------------------------------

    def speak(self, sentence: str) -> bytes:
        try:
            self._logger.debug(self.command)

            # text -> STDIN -> STDOUT -> WAV
            return subprocess.check_output(self.command, input=sentence.encode())

        except:
            self._logger.exception("speak")
            return bytes()
