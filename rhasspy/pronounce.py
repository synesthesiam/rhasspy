#!/usr/bin/env python3
import os
import re
import logging
import subprocess
import tempfile
from collections import defaultdict
from typing import Dict, Tuple, List, Optional, Any

from rhasspy.actor import RhasspyActor
from rhasspy.utils import read_dict, load_phoneme_map
from rhasspy.profiles import Profile

# -----------------------------------------------------------------------------
# Events
# -----------------------------------------------------------------------------


class SpeakWord:
    def __init__(self, word: str, receiver: Optional[RhasspyActor] = None) -> None:
        self.word = word
        self.receiver = receiver


class WordSpoken:
    def __init__(self, word: str, wav_data: bytes, phonemes: str) -> None:
        self.word = word
        self.wav_data = wav_data
        self.phonemes = phonemes


class GetWordPhonemes:
    def __init__(self, word: str, receiver: Optional[RhasspyActor] = None) -> None:
        self.word = word
        self.receiver = receiver


class WordPhonemes:
    def __init__(self, word: str, phonemes: str) -> None:
        self.word = word
        self.phonemes = phonemes


class GetWordPronunciations:
    def __init__(
        self, words: List[str], n: int = 5, receiver: Optional[RhasspyActor] = None
    ) -> None:
        self.words = words
        self.n = n
        self.receiver = receiver


class WordPronunciations:
    def __init__(self, pronunciations: Dict[str, Dict[str, Any]]) -> None:
        self.pronunciations = pronunciations


class PronunciationFailed:
    def __init__(self, reason: str) -> None:
        self.reason = reason


# -----------------------------------------------------------------------------
# Dummy word pronouncer
# -----------------------------------------------------------------------------


class DummyWordPronounce:
    """Returns junk."""


# -----------------------------------------------------------------------------
# Phonetisaurus based word pronouncer
# https://github.com/AdolfVonKleist/Phonetisaurus
# -----------------------------------------------------------------------------


class PhonetisaurusPronounce(RhasspyActor):
    """Uses phonetisaurus/espeak to pronounce words."""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.speed = 80  # wpm for speaking
        self.base_dict: Optional[Dict[str, List[str]]] = None

    def to_started(self, from_state: str) -> None:
        self.speech_system = self.profile.get("speech_to_text.system", "pocketsphinx")

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, SpeakWord):
            espeak_phonemes, wav_data = self.speak(message.word)
            self.send(
                message.receiver or sender,
                WordSpoken(message.word, wav_data, espeak_phonemes),
            )
        elif isinstance(message, GetWordPronunciations):
            try:
                pronunciations = self.pronounce(message.words, message.n)
                self.send(
                    message.receiver or sender, WordPronunciations(pronunciations)
                )
            except Exception as e:
                self._logger.exception("pronounce")
                self.send(message.receiver or sender, PronunciationFailed(repr(e)))
        elif isinstance(message, GetWordPhonemes):
            phonemes = self.translate_phonemes(message.word)
            self.send(message.receiver or sender, WordPhonemes(message.word, phonemes))

    # -------------------------------------------------------------------------

    def speak(self, espeak_str: str, voice: Optional[str] = None) -> Tuple[str, bytes]:

        # Use eSpeak to pronounce word
        espeak_command = ["espeak", "-s", str(self.speed), "-x"]

        voice = self._get_voice(voice)

        if voice is not None:
            espeak_command.extend(["-v", str(voice)])

        espeak_command.append(espeak_str)

        # Write WAV to temporary file
        with tempfile.NamedTemporaryFile(suffix=".wav", mode="wb+") as wav_file:
            espeak_command.extend(["-w", wav_file.name])
            self._logger.debug(repr(espeak_command))

            # Generate WAV data
            espeak_phonemes = subprocess.check_output(espeak_command).decode().strip()
            wav_file.seek(0)
            wav_data = wav_file.read()

        return espeak_phonemes, wav_data

    # -------------------------------------------------------------------------

    def translate_phonemes(self, phonemes: str) -> str:
        # Load map from Sphinx to eSpeak phonemes
        map_path = self.profile.read_path(
            self.profile.get("text_to_speech.espeak.phoneme_map")
        )

        phoneme_map = load_phoneme_map(map_path)

        # Convert from Sphinx to espeak phonemes
        espeak_str = "[['%s]]" % "".join(
            phoneme_map.get(p, p) for p in phonemes.split()
        )

        return espeak_str

    # -------------------------------------------------------------------------

    def pronounce(self, words: List[str], n: int = 5) -> Dict[str, Dict[str, Any]]:
        assert n > 0, "No pronunciations requested"
        assert len(words) > 0, "No words to look up"

        self._logger.debug("Getting pronunciations for %s" % words)

        # Load base and custom dictionaries
        base_dictionary_path = self.profile.read_path(
            self.profile.get(f"speech_to_text.{self.speech_system}.base_dictionary")
        )

        # Load base dictionary once
        if (self.base_dict is None) and os.path.exists(base_dictionary_path):
            self.base_dict = defaultdict(list)
            with open(base_dictionary_path, "r") as dictionary_file:
                read_dict(dictionary_file, self.base_dict)

        custom_path = self.profile.read_path(
            self.profile.get(f"speech_to_text.{self.speech_system}.custom_words")
        )

        word_dict: Dict[str, List[str]] = defaultdict(list)
        if os.path.exists(custom_path):
            with open(custom_path, "r") as dictionary_file:
                read_dict(dictionary_file, word_dict)

        # Mix in base dictionary
        if self.base_dict:
            for word, prons in self.base_dict.items():
                word_dict[word].extend(prons)
        else:
            self._logger.warning("Missing base dictionary")

        pronunciations = self._lookup_words(words, word_dict, n)

        # Get phonemes from eSpeak
        for word in words:
            espeak_command = ["espeak", "-q", "-x"]

            voice = self._get_voice()
            if voice is not None:
                espeak_command.extend(["-v", voice])

            espeak_command.append(word)

            self._logger.debug(repr(espeak_command))
            espeak_str = subprocess.check_output(espeak_command).decode().strip()
            pronunciations[word]["phonemes"] = espeak_str

        return pronunciations

    # -------------------------------------------------------------------------

    def _lookup_words(
        self, words: List[str], word_dict: Dict[str, List[str]], n: int = 5
    ) -> Dict[str, Dict[str, Any]]:
        """Look up or guess word pronunciations."""

        pronunciations: Dict[str, Dict[str, Any]] = {}

        # Dictionary uses upper-case letters
        dictionary_upper = self.profile.get("speech_to_text.dictionary_upper", False)

        # Check words against dictionary
        unknown_words = set()
        for word in words:
            if dictionary_upper:
                lookup_word = word.upper()
            else:
                lookup_word = word.lower()

            pronounces = list(word_dict.get(lookup_word, []))
            in_dictionary = len(pronounces) > 0

            pronunciations[word] = {
                "in_dictionary": in_dictionary,
                "pronunciations": pronounces,
            }
            if not in_dictionary:
                unknown_words.add(word)

        # Guess pronunciations for unknown word
        if len(unknown_words) > 0:
            # Path to phonetisaurus FST
            g2p_path = self.profile.read_path(
                self.profile.get(
                    f"speech_to_text.{self.speech_system}.g2p_model", "g2p.fst"
                )
            )

            g2p_casing = self.profile.get("speech_to_text.g2p_casing", "").lower()

            # Case-sensitive mapping from upper/lower cased word back to original casing
            word_map: Dict[str, str] = {}

            with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt") as wordlist_file:
                # Write words to a temporary word list file
                for word in unknown_words:
                    original_word = word
                    if g2p_casing == "upper":
                        # FST was trained with upper-case letters
                        word = word.upper()
                    elif g2p_casing == "lower":
                        # FST was trained with loser-case letters
                        word = word.lower()

                    print(word, file=wordlist_file)
                    word_map[word] = original_word

                wordlist_file.seek(0)

                # Output phonetisaurus results to temporary file
                with tempfile.NamedTemporaryFile(
                    mode="w+", suffix=".txt"
                ) as pronounce_file:
                    # Use phonetisaurus to guess pronunciations
                    g2p_command = [
                        "phonetisaurus-apply",
                        "--model",
                        g2p_path,
                        "--word_list",
                        wordlist_file.name,
                        "--nbest",
                        str(n),
                    ]

                    self._logger.debug(repr(g2p_command))
                    subprocess.check_call(g2p_command, stdout=pronounce_file)

                    pronounce_file.seek(0)

                    # Read results
                    ws_pattern = re.compile(r"\s+")

                    for line in pronounce_file:
                        parts = ws_pattern.split(line)
                        word = word_map[parts[0].strip()]
                        phonemes = " ".join(parts[1:]).strip()
                        pronunciations[word]["pronunciations"].append(phonemes)

        return pronunciations

    # -------------------------------------------------------------------------

    def _get_voice(self, voice: Optional[str] = None) -> Optional[str]:
        """Uses either the provided voice, the profile's text to speech voice,
        or the profile's language."""
        return (
            voice
            or self.profile.get("text_to_speech.espeak.voice")
            or self.profile.get("language")
        )
