import json
import os
import subprocess
from collections import defaultdict
from typing import Any, Dict, List, Optional, Type

import pywrapfst as fst

from rhasspy.actor import RhasspyActor
from rhasspy.train.jsgf2fst import symbols2intent, fstprintall

# -----------------------------------------------------------------------------
# Events
# -----------------------------------------------------------------------------


class TrainSpeech:
    def __init__(
        self, intent_fst: fst.Fst, receiver: Optional[RhasspyActor] = None
    ) -> None:
        self.intent_fst = intent_fst
        self.receiver = receiver


class SpeechTrainingComplete:
    def __init__(self, intent_fst: fst.Fst) -> None:
        self.intent_fst = intent_fst


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


def get_speech_trainer_class(
    trainer_system: str, decoder_system: str = "dummy"
) -> Type[RhasspyActor]:

    assert trainer_system in ["dummy", "pocketsphinx", "kaldi", "auto", "command"], (
        "Invalid speech training system: %s" % trainer_system
    )

    if trainer_system == "auto":
        # Use speech decoder system
        if decoder_system == "pocketsphinx":
            # Use opengrm/phonetisaurus
            return PocketsphinxSpeechTrainer
        elif decoder_system == "kaldi":
            # Use opengrm/phonetisaurus
            return KaldiSpeechTrainer
        elif decoder_system == "command":
            # Use command-line speech trainer
            return CommandSpeechTrainer
    elif trainer_system == "pocketsphinx":
        # Use opengrm/phonetisaurus
        return PocketsphinxSpeechTrainer
    elif trainer_system == "kaldi":
        # Use opengrm/phonetisaurus/kaldi
        return KaldiSpeechTrainer
    elif trainer_system == "command":
        # Use command-line speech trainer
        return CommandSpeechTrainer

    # Use dummy trainer as a fallback
    return DummySpeechTrainer


# -----------------------------------------------------------------------------


class DummySpeechTrainer(RhasspyActor):
    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, TrainSpeech):
            self.send(
                message.receiver or sender, SpeechTrainingComplete(message.intent_fst)
            )


# -----------------------------------------------------------------------------
# Speech system trainer for Pocketsphinx.
# Uses opengrm (ARPA model) and phonetisaurus (pronunciations).
# -----------------------------------------------------------------------------


class PocketsphinxSpeechTrainer(RhasspyActor):
    """Trains an ARPA language model using opengrm."""

    def __init__(self, system: str = "pocketsphinx") -> None:
        RhasspyActor.__init__(self)
        self.system = system

    def to_started(self, from_state: str) -> None:
        self.word_pronouncer: RhasspyActor = self.config["word_pronouncer"]
        self.unknown_words: Dict[str, Dict[str, Any]] = {}
        self.receiver: Optional[RhasspyActor] = None

        self.dictionary_casing = self.profile.get(
            "speech_to_text.dictionary_casing", ""
        )
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
        pass


# -----------------------------------------------------------------------------
# Kaldi based speed trainer.
# http://kaldi-asr.org
# -----------------------------------------------------------------------------


class KaldiSpeechTrainer(PocketsphinxSpeechTrainer):
    """Trains a speech to text system via Kaldi scripts."""

    def __init__(self):
        PocketsphinxSpeechTrainer.__init__(self, system="kaldi")

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        pass


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

        self.dictionary_casing = self.profile.get(
            "speech_to_text.dictionary_casing", ""
        )
        tokenizer = self.profile.get("training.tokenizer", "regex")
        regex_config = self.profile.get(f"training.{tokenizer}", {})
        self.replace_patterns = regex_config.get("replace", [])
        self.split_pattern = regex_config.get("split", r"\s+")

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, TrainSpeech):
            try:
                self.train(message.intent_fst)
                self.send(
                    message.receiver or sender,
                    SpeechTrainingComplete(message.intent_fst),
                )
            except Exception as e:
                self._logger.exception("train")
                self.send(message.receiver or sender, SpeechTrainingFailed(repr(e)))

    # -------------------------------------------------------------------------

    def train(self, intent_fst: fst.Fst):
        self._logger.debug(self.command)

        try:
            # { intent: [ { 'text': ..., 'entities': { ... } }, ... ] }
            sentences_by_intent: Dict[str, Any] = defaultdict(list)

            for symbols in fstprintall(intent_fst, exclude_meta=False):
                intent = symbols2intent(symbols)
                intent_name = intent["intent"]["name"]
                sentences_by_intent[intent_name].append(intent)

            # JSON -> STDIN
            input = json.dumps(sentences_by_intent).encode()

            subprocess.run(self.command, input=input, check=True)
        except Exception:
            self._logger.exception("train")
