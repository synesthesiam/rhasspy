import os
import re
import configparser
import subprocess
import itertools
import logging
import time
import json
import concurrent.futures
from collections import defaultdict
from typing import TextIO, Dict, List, Tuple, Any, Optional

from jsgf import parser
from jsgf2fst import jsgf2fst, read_slots, make_intent_fst

from .actor import RhasspyActor
from .profiles import Profile

# -----------------------------------------------------------------------------
# Events
# -----------------------------------------------------------------------------


class GenerateSentences:
    def __init__(self, receiver: Optional[RhasspyActor] = None) -> None:
        self.receiver = receiver


class SentencesGenerated:
    def __init__(self, intent_fst) -> None:
        self.intent_fst = intent_fst


class SentenceGenerationFailed:
    def __init__(self, reason: str) -> None:
        self.reason = reason


# -----------------------------------------------------------------------------
# OpenFST based sentence generator
# https://github.com/synesthesiam/jsgf2fst
# -----------------------------------------------------------------------------


class JsgfSentenceGenerator(RhasspyActor):
    """Uses jsgf2fst to generate sentences."""

    def to_started(self, from_state: str) -> None:
        self.language = self.profile.get("language", "en")

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, GenerateSentences):
            try:
                intent_fst = self.generate_sentences()
                self.send(message.receiver or sender, SentencesGenerated(intent_fst))
            except Exception as e:
                self._logger.exception("generate")
                self.send(message.receiver or sender, SentenceGenerationFailed(repr(e)))

    # -------------------------------------------------------------------------

    def generate_sentences(self) -> Dict[str, Any]:
        ini_path = self.profile.read_path(
            self.profile.get("speech_to_text.sentences_ini")
        )

        grammars_dir = self.profile.write_dir(
            self.profile.get("speech_to_text.grammars_dir")
        )

        fsts_dir = self.profile.write_dir(self.profile.get("speech_to_text.fsts_dir"))

        start_time = time.time()
        with open(ini_path, "r") as ini_file:
            grammar_paths = self._make_grammars(ini_file, grammars_dir)

        grammar_time = time.time() - start_time
        self._logger.debug(
            f"Generated {len(grammar_paths)} grammar(s) in {grammar_time} second(s)"
        )

        # Create intent map
        # TODO: Ensure that keys are valid identifiers (no spaces, etc.)
        intent_map = {intent_name: intent_name for intent_name in grammar_paths.keys()}
        intent_map_path = self.profile.write_path(
            self.profile.get("training.intent.intent_map", "intent_map.json")
        )

        with open(intent_map_path, "w") as intent_map_file:
            json.dump(intent_map, intent_map_file)

        # Ready slots values
        slots_dir = self.profile.read_path(self.profile.get("speech_to_text.slots_dir"))

        self._logger.debug(f"Loading slot values from {slots_dir}")

        # $colors -> [red, green, blue, ...]
        slots = read_slots(slots_dir)

        # Load all grammars
        grammars = []
        for f_name in os.listdir(grammars_dir):
            self._logger.debug(f"Parsing JSGF grammar {f_name}")
            grammar = parser.parse_grammar_file(os.path.join(grammars_dir, f_name))
            grammars.append(grammar)

        # Generate FSTs
        start_time = time.time()
        grammar_fsts = jsgf2fst(grammars, slots=slots)
        for grammar_name, grammar_fst in grammar_fsts.items():
            fst_path = os.path.join(fsts_dir, grammar_name) + ".fst"
            grammar_fst.write(fst_path)

        # Join into master intent FST
        intent_fst_path = self.profile.write_path(
            self.profile.get("intent.fsticuffs.intent_fst")
        )

        intent_fst = make_intent_fst(grammar_fsts)
        intent_fst.write(intent_fst_path)
        self._logger.debug(f"Wrote intent FST to {intent_fst_path}")

        fst_time = time.time() - start_time
        self._logger.debug(f"Generated FSTs in {fst_time} second(s)")

        return intent_fst

    # -------------------------------------------------------------------------

    def _make_grammars(self, ini_file: TextIO, grammar_dir: str) -> Dict[str, str]:
        """Create JSGF grammars for each intent from sentence ini file.
        Returns paths to all generated grammars (name -> path)."""
        config = configparser.ConfigParser(
            allow_no_value=True, strict=False, delimiters=["="]
        )

        # Make case sensitive
        config.optionxform = lambda x: str(x)  # type: ignore
        config.read_file(ini_file)

        os.makedirs(grammar_dir, exist_ok=True)

        delete_before_training = self.profile.get(
            "training.grammars.delete_before_training", True
        )
        if delete_before_training:
            for file_name in os.listdir(grammar_dir):
                if file_name.endswith(".gram"):
                    file_path = os.path.join(grammar_dir, file_name)
                    if os.path.isfile(file_path):
                        self._logger.debug(f"Removing old grammar file: {file_name}")
                        os.unlink(file_path)

        # Process configuration sections
        grammar_rules = {}

        for sec_name in config.sections():
            sentences: List[str] = []
            rules: List[str] = []
            for k, v in config[sec_name].items():
                if v is None:
                    # Collect non-valued keys as sentences
                    sentences.append("({0})".format(k.strip()))
                else:
                    # Collect key/value pairs as JSGF rules
                    rule = "<{0}> = ({1});".format(k, v)
                    rules.append(rule)

            if len(sentences) > 0:
                # Combine all sentences into one big rule (same name as section)
                sentences_rule = "public <{0}> = ({1});".format(
                    sec_name, " | ".join(sentences)
                )
                rules.insert(0, sentences_rule)

            grammar_rules[sec_name] = rules

        # Write JSGF grammars
        grammar_paths = {}
        for name, rules in grammar_rules.items():
            grammar_path = os.path.join(grammar_dir, "{0}.gram".format(name))

            # Only overwrite grammar file if it contains rules or doesn't yet exist
            if (len(rules) > 0) or not os.path.exists(grammar_path):
                with open(grammar_path, "w") as grammar_file:
                    # JSGF header
                    print(f"#JSGF V1.0 UTF-8 {self.language};", file=grammar_file)
                    print("grammar {0};".format(name), file=grammar_file)
                    print("", file=grammar_file)

                    # Grammar rules
                    for rule in rules:
                        # Handle special case where sentence starts with ini
                        # reserved character '['. In this case, use '\[' to pass
                        # it through to the JSGF grammar, where we deal with it
                        # here.
                        rule = re.sub(r"\\\[", "[", rule)
                        print(rule, file=grammar_file)

            grammar_paths[name] = grammar_path

        return grammar_paths
