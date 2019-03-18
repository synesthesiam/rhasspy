import os
import re
import tempfile
import subprocess
import logging
import shutil
import json
import time
from collections import defaultdict
from typing import Dict, List, Any, Tuple, Set, Optional

from .actor import RhasspyActor
from .profiles import Profile
from .pronounce import GetWordPronunciations, WordPronunciations
from .train import TrainingSentence
from .utils import read_dict, lcm, sanitize_sentence, open_maybe_gzip

# -----------------------------------------------------------------------------
# Events
# -----------------------------------------------------------------------------


class TrainSpeech:
    def __init__(
        self, sentences_by_intent, receiver: Optional[RhasspyActor] = None
    ) -> None:
        self.sentences_by_intent = sentences_by_intent
        self.receiver = receiver


class SpeechTrainingComplete:
    def __init__(self, sentences_by_intent) -> None:
        self.sentences_by_intent = sentences_by_intent


class SpeechTrainingFailed:
    def __init__(self, reason: str) -> None:
        self.reason = reason


# -----------------------------------------------------------------------------


class UnknownWordsException(Exception):
    def __init__(self, unknown_words: List[str]) -> None:
        self.unknown_words = unknown_words

    def __repr__(self):
        return f"Unknown words: {self.unknown_words}"


# -----------------------------------------------------------------------------


class DummySpeechTrainer(RhasspyActor):
    """Passes sentences along"""

    def to_started(self, from_state: str) -> None:
        self.sentence_casing = self.profile.get("training.sentences.casing", "")
        tokenizer = self.profile.get("training.tokenizer", "regex")
        regex_config = self.profile.get(f"training.{tokenizer}", {})
        self.replace_patterns = regex_config.get("replace", [])
        self.split_pattern = regex_config.get("split", r"\s+")

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, TrainSpeech):
            self.send(
                message.receiver or sender,
                SpeechTrainingComplete(message.sentences_by_intent),
            )


# -----------------------------------------------------------------------------
# Speech system trainer for Pocketsphinx.
# Uses mitlm (ARPA model) and phonetisaurus (pronunciations).
# -----------------------------------------------------------------------------


class PocketsphinxSpeechTrainer(RhasspyActor):
    """Trains an ARPA language model using opengrm."""

    def to_started(self, from_state: str) -> None:
        self.word_pronouncer: RhasspyActor = self.config["word_pronouncer"]
        self.unknown_words: Dict[str, Dict[str, Any]] = {}
        self.receiver: Optional[RhasspyActor] = None
        self.sentence_casing = self.profile.get("training.sentences.casing", "")
        self.dictionary_upper: bool = self.profile.get(
            "speech_to_text.dictionary_upper", False
        )

        tokenizer = self.profile.get("training.tokenizer", "regex")
        regex_config = self.profile.get(f"training.{tokenizer}", {})
        self.replace_patterns = regex_config.get("replace", [])
        self.split_pattern = regex_config.get("split", r"\s+")

        # Unknown words
        self.guess_unknown = self.profile.get(
            "training.unknown_words.guess_pronunciations", True
        )
        self.fail_on_unknown = self.profile.get(
            "training.unknown_words.fail_when_present", True
        )

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, TrainSpeech):
            self.receiver = message.receiver or sender
            self.sentences_by_intent = message.sentences_by_intent
            self.transition("writing_dictionary")

    def to_writing_dictionary(self, from_state: str) -> None:
        unknown = self.write_dictionary(self.sentences_by_intent)

        self.unknown_words = {word: {} for word in unknown}

        has_unknown_words = len(self.unknown_words) > 0

        if has_unknown_words:
            unknown_words = list(self.unknown_words.keys())
            self._logger.warning(
                f"There are {len(unknown_words)} unknown word(s): {unknown_words}"
            )
        else:
            # Remove unknown dictionary
            unknown_path = self.profile.read_path(
                self.profile.get("speech_to_text.pocketsphinx.unknown_words")
            )

            if os.path.exists(unknown_path):
                os.unlink(unknown_path)

        # Proceed or guess pronunciations
        if self.guess_unknown and has_unknown_words:
            self.transition("unknown_words")
        else:
            self.transition("writing_sentences")

    def to_unknown_words(self, from_state: str) -> None:
        words = list(self.unknown_words.keys())
        self.send(self.word_pronouncer, GetWordPronunciations(words, n=1))

    def in_unknown_words(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, WordPronunciations):
            try:
                self.unknown_words = message.pronunciations
                self.write_unknown_words(self.unknown_words)

                if self.fail_on_unknown:
                    # Fail when unknown words are present
                    raise UnknownWordsException(list(self.unknown_words.keys()))
                else:
                    # Add guessed pronunciations to main dictionary
                    unknown_path = self.profile.read_path(
                        self.profile.get("speech_to_text.pocketsphinx.unknown_words")
                    )

                    if os.path.exists(unknown_path):
                        dictionary_path = self.profile.write_path(
                            self.profile.get(
                                "speech_to_text.pocketsphinx.dictionary",
                                "dictionary.txt",
                            )
                        )

                        with open(dictionary_path, "a") as dictionary_file:
                            with open(unknown_path, "r") as unknown_file:
                                self._logger.debug(
                                    "Adding unknown word pronunciations to user dictionary"
                                )
                                dictionary_file.write(unknown_file.read())

                    # Proceed with training
                    self.transition("writing_sentences")
            except Exception as e:
                if isinstance(e, UnknownWordsException):
                    self._logger.exception(
                        f"Training failed due to unknown words: {e.unknown_words}"
                    )
                else:
                    self._logger.exception("Unexpected error")

                self.send(self.receiver, SpeechTrainingFailed(repr(e)))
                self.transition("started")

    def to_writing_sentences(self, from_state: str) -> None:
        try:
            self.write_sentences(self.sentences_by_intent)
            self.transition("writing_language_model")
        except Exception as e:
            self._logger.exception("writing sentences")
            self.send(self.receiver, SpeechTrainingFailed(repr(e)))
            self.transition("started")

    def to_writing_language_model(self, from_state: str) -> None:
        try:
            self.write_language_model()
            self.send(self.receiver, SpeechTrainingComplete(self.sentences_by_intent))
            self.transition("started")
        except Exception as e:
            self._logger.exception("writing language model")
            self.send(self.receiver, SpeechTrainingFailed(repr(e)))
            self.transition("started")

    # -------------------------------------------------------------------------

    def write_dictionary(self, sentences_by_intent: Dict[str, Any]) -> Set[str]:
        """Writes all required words to a CMU dictionary.
        Unknown words have their pronunciations guessed and written to a separate dictionary.
        Fails if any unknown words are found."""

        start_time = time.time()
        words_needed: Set[str] = set()

        # Extract entities from tagged sentences
        for intent_name, intent_sents in sentences_by_intent.items():
            for intent_sent in intent_sents:
                # Collect all used words
                for word in intent_sent["tokens"]:
                    # Dictionary uses upper-case letters
                    if self.dictionary_upper:
                        word = word.upper()
                    else:
                        word = word.lower()

                    words_needed.add(word)

        # Load base and custom dictionaries
        base_dictionary_path = self.profile.read_path(
            self.profile.get(
                "speech_to_text.pocketsphinx.base_dictionary", "base_dictionary.txt"
            )
        )

        custom_path = self.profile.read_path(
            self.profile.get(
                "speech_to_text.pocketsphinx.custom_words", "custom_words.txt"
            )
        )

        word_dict: Dict[str, List[str]] = {}
        for word_dict_path in [base_dictionary_path, custom_path]:
            if os.path.exists(word_dict_path):
                self._logger.debug(f"Loading dictionary from {word_dict_path}")
                with open(word_dict_path, "r") as dictionary_file:
                    read_dict(dictionary_file, word_dict)

        # Add words from wake word if using pocketsphinx
        if self.profile.get("wake.system") == "pocketsphinx":
            wake_keyphrase = self.profile.get("wake.pocketsphinx.keyphrase", "")
            if len(wake_keyphrase) > 0:
                self._logger.debug(f"Adding words from keyphrase: {wake_keyphrase}")
                _, wake_tokens = sanitize_sentence(
                    wake_keyphrase,
                    self.sentence_casing,
                    self.replace_patterns,
                    self.split_pattern,
                )

                for word in wake_tokens:
                    # Dictionary uses upper-case letters
                    if self.dictionary_upper:
                        word = word.upper()
                    else:
                        word = word.lower()

                    words_needed.add(word)

        # Write out dictionary with only the necessary words (speeds up loading)
        dictionary_path = self.profile.write_path(
            self.profile.get("speech_to_text.pocketsphinx.dictionary", "dictionary.txt")
        )

        words_written = 0
        with open(dictionary_path, "w") as dictionary_file:
            for word in sorted(words_needed):
                if not word in word_dict:
                    continue

                for i, pronounce in enumerate(word_dict[word]):
                    if i < 1:
                        print(word, pronounce, file=dictionary_file)
                    else:
                        print("%s(%s)" % (word, i + 1), pronounce, file=dictionary_file)

                words_written += 1

        dictionary_time = time.time() - start_time
        self._logger.debug(
            f"Wrote {words_written} word(s) to {dictionary_path} in {dictionary_time} second(s)"
        )

        # Check for unknown words
        return words_needed - word_dict.keys()

    # -------------------------------------------------------------------------

    def write_unknown_words(self, unknown_words: Dict[str, Dict[str, Any]]) -> None:
        unknown_path = self.profile.write_path(
            self.profile.get(
                "speech_to_text.pocketsphinx.unknown_words", "unknown_words.txt"
            )
        )

        with open(unknown_path, "w") as unknown_file:
            for word, word_pron in unknown_words.items():
                pronunciations = word_pron["pronunciations"]
                phonemes = pronunciations[0]

                # Dictionary uses upper-case letters
                if self.dictionary_upper:
                    word = word.upper()
                else:
                    word = word.lower()

                print(word, phonemes, file=unknown_file)

    # -------------------------------------------------------------------------

    def write_sentences(self, sentences_by_intent: Dict[str, Any]) -> None:
        """Writes all raw sentences to a text file.
        Optionally balances (repeats) sentences so all intents have the same number."""

        # Repeat sentences so that all intents will contain the same number
        balance_sentences = self.profile.get(
            "training.sentences.balance_by_intent", True
        )
        if balance_sentences:
            # Use least common multiple
            lcm_sentences = lcm(*(len(sents) for sents in sentences_by_intent.values()))
        else:
            lcm_sentences = 0  # no repeats

        # Write sentences to text file
        sentences_text_path = self.profile.write_path(
            self.profile.get("speech_to_text.sentences_text", "sentences.txt.gz")
        )

        num_sentences = 0
        write_sorted = self.profile.get("training.sentences.write_sorted", False)
        write_weights = self.profile.get("training.sentences.write_weights", True)

        with open_maybe_gzip(sentences_text_path, "w") as sentences_text_file:
            if write_sorted:
                # Cache sentences and weights
                sentences_to_write = []
                for intent_name, intent_sents in sentences_by_intent.items():
                    num_repeats = max(1, lcm_sentences // len(intent_sents))
                    for intent_sent in intent_sents:
                        sentences_to_write.append(
                            (num_repeats, intent_sent["sentence"])
                        )

                # Do sort
                sentences_to_write = sorted(sentences_to_write, key=lambda x: x[1])
                for num_repeats, sentence in sentences_to_write:
                    if write_weights:
                        print(num_repeats, sentence, file=sentences_text_file)
                    else:
                        print(sentence, file=sentences_text_file)
            else:
                # Unsorted
                for intent_name, intent_sents in sentences_by_intent.items():
                    for intent_sent in intent_sents:
                        if write_weights:
                            num_repeats = max(1, lcm_sentences // len(intent_sents))
                            print(
                                num_repeats,
                                intent_sent["sentence"],
                                file=sentences_text_file,
                            )
                        else:
                            print(intent_sent["sentence"], file=sentences_text_file)

                        num_sentences = num_sentences + 1

        self._logger.debug(
            "Wrote %s sentence(s) to %s" % (num_sentences, sentences_text_path)
        )

    # -------------------------------------------------------------------------

    def write_language_model(self) -> None:
        """Generates an ARPA language model using mitlm"""
        sentences_text_path = self.profile.read_path(
            self.profile.get("speech_to_text.sentences_text", "sentences.txt.gz")
        )

        # Extract file name only (will be made relative to container path)
        sentences_text_path = sentences_text_path
        lm_dest_path = self.profile.write_path(
            self.profile.get(
                "speech_to_text.pocketsphinx.language_model", "language_model.txt"
            )
        )

        # Use mitlm
        start_time = time.time()
        subprocess.check_call(
            [
                "estimate-ngram",
                "-o",
                "3",
                "-text",
                sentences_text_path,
                "-wl",
                lm_dest_path,
            ]
        )

        lm_time = time.time() - start_time
        self._logger.debug(
            f"Wrote language model to {lm_dest_path} in {lm_time} seconds(s)"
        )


# -----------------------------------------------------------------------------
# Command-line based speed trainer.
# -----------------------------------------------------------------------------


class CommandSpeechTrainer(RhasspyActor):
    """Trains a speech to text system via command line."""

    def to_started(self, from_state: str) -> None:
        program = os.path.expandvars(
            self.profile.get("training.speech_to_text.command.program")
        )
        arguments = [
            os.path.expandvars(str(a))
            for a in self.profile.get("training.speech_to_text.command.arguments", [])
        ]

        self.command = [program] + arguments

        self.sentence_casing = self.profile.get("training.sentences.casing", "")
        tokenizer = self.profile.get("training.tokenizer", "regex")
        regex_config = self.profile.get(f"training.{tokenizer}", {})
        self.replace_patterns = regex_config.get("replace", [])
        self.split_pattern = regex_config.get("split", r"\s+")

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, TrainSpeech):
            try:
                self.train(message.sentences_by_intent)
                self.send(
                    message.receiver or sender,
                    SpeechTrainingComplete(message.sentences_by_intent),
                )
            except Exception as e:
                self._logger.exception("train")
                self.send(message.receiver or sender, SpeechTrainingFailed(repr(e)))

    # -------------------------------------------------------------------------

    def train(self, sentences_by_intent):
        self._logger.debug(self.command)

        try:
            # JSON -> STDIN
            input = json.dumps(
                {
                    intent_name: [s.json() for s in sentences]
                    for intent_name, sentences in sentences_by_intent.items()
                }
            ).encode()

            subprocess.run(self.command, input=input, check=True)
        except:
            self._logger.exception("train")
