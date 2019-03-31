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

from jsgf import parser, expansions, rules

from .actor import RhasspyActor
from .profiles import Profile
from .utils import SentenceEntity, extract_entities, sanitize_sentence, open_maybe_gzip

# -----------------------------------------------------------------------------
# Classes
# -----------------------------------------------------------------------------


class TrainingSentence:
    def __init__(
        self,
        sentence: str,
        entities: List[SentenceEntity],
        tokens: List[str],
        tagged_sentence: str,
    ) -> None:
        self.sentence = sentence
        self.entities = entities
        self.tokens = tokens
        self.tagged_sentence = tagged_sentence

    def json(self):
        return {
            "sentence": self.sentence,
            "entities": [e.__dict__ for e in self.entities],
            "tokens": self.tokens,
            "tagged_sentence": self.tagged_sentence,
        }


# -----------------------------------------------------------------------------
# Events
# -----------------------------------------------------------------------------


class GenerateSentences:
    def __init__(self, receiver: Optional[RhasspyActor] = None) -> None:
        self.receiver = receiver


class SentencesGenerated:
    def __init__(self, sentences_by_intent) -> None:
        self.sentences_by_intent = sentences_by_intent


class SentenceGenerationFailed:
    def __init__(self, reason: str) -> None:
        self.reason = reason


# -----------------------------------------------------------------------------
# jsgf-gen based sentence generator
# https://github.com/synesthesiam/jsgf-gen
# -----------------------------------------------------------------------------


class JsgfSentenceGenerator(RhasspyActor):
    """Uses jsgf-gen to generate sentences."""

    def to_started(self, from_state: str) -> None:
        self.language = self.profile.get("language", "en")

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, GenerateSentences):
            try:
                sentences_by_intent = self.generate_sentences()
                self.send(
                    message.receiver or sender, SentencesGenerated(sentences_by_intent)
                )
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

        start_time = time.time()
        with open(ini_path, "r") as ini_file:
            grammar_paths = self._make_grammars(ini_file, grammars_dir)

        grammar_time = time.time() - start_time
        self._logger.debug(
            f"Generated {len(grammar_paths)} grammar(s) in {grammar_time} second(s)"
        )

        # intent -> training sentences
        sentences_by_intent: Dict[str, List[Any]] = defaultdict(list)

        # Ready slots values
        slots_dirs = self.profile.read_paths(
            self.profile.get("speech_to_text.slots_dir")
        )

        self._logger.debug(f"Loading slot values from {slots_dirs}")

        # colors -> [red, green, blue]
        slot_values = JsgfSentenceGenerator.load_slots(slots_dirs)

        # Load all grammars
        grammars = {}
        for f_name in os.listdir(grammars_dir):
            self._logger.debug(f"Parsing JSGF grammar {f_name}")
            grammar = parser.parse_grammar_file(os.path.join(grammars_dir, f_name))
            grammars[grammar.name] = grammar

        global_rule_map = {
            f"{grammar.name}.{rule.name}": rule
            for grammar in grammars.values()
            for rule in grammar.rules
        }

        # Generate sentences concurrently
        start_time = time.time()
        with concurrent.futures.ProcessPoolExecutor() as executor:
            future_to_name = {
                executor.submit(
                    _jsgf_generate,
                    self.profile,
                    name,
                    grammars,
                    global_rule_map,
                    slot_values,
                ): name
                for name, grammar in grammars.items()
            }

            # Add to the list as they get done
            for future in concurrent.futures.as_completed(future_to_name):
                name = future_to_name[future]
                sentences_by_intent[name] = future.result()

        num_sentences = sum(len(s) for s in sentences_by_intent.values())
        sentence_time = time.time() - start_time
        self._logger.debug(
            f"Generated {num_sentences} sentence(s) for {len(sentences_by_intent)} intent(s) in {sentence_time} second(s)"
        )

        return sentences_by_intent

    # -------------------------------------------------------------------------

    @classmethod
    def load_slots(cls, slots_dirs):
        # colors -> [red, green, blue]
        slot_values = defaultdict(set)
        for slots_dir in slots_dirs:
            if os.path.exists(slots_dir):
                for slot_file_name in os.listdir(slots_dir):
                    slot_path = os.path.join(slots_dir, slot_file_name)
                    if os.path.isfile(slot_path):
                        slot_name = os.path.splitext(slot_file_name)[0]
                        with open(slot_path, "r") as slot_file:
                            for line in slot_file:
                                line = line.strip()
                                if len(line) > 0:
                                    slot_values[slot_name].add(line)

        # Convert sets to lists for easier JSON serialization
        return {name: list(values) for name, values in slot_values.items()}

    # -------------------------------------------------------------------------

    def _make_grammars(self, ini_file: TextIO, grammar_dir: str) -> Dict[str, str]:
        """Create JSGF grammars for each intent from sentence ini file.
        Returns paths to all generated grammars (name -> path)."""
        config = configparser.ConfigParser(
            allow_no_value=True, strict=False, delimiters=["="]
        )

        config.optionxform = lambda x: str(x)  # case sensitive
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


# -----------------------------------------------------------------------------


def _jsgf_generate(
    profile, grammar_name, grammars, global_rule_map, slot_values
) -> List[Any]:
    # Sentence sanitize settings
    sentence_casing = profile.get("training.sentences.casing", "")
    tokenizer = profile.get("training.tokenizer", "regex")
    regex_config = profile.get(f"training.{tokenizer}", {})
    replace_patterns = regex_config.get("replace", [])
    split_pattern = regex_config.get("split", r"\s+")

    # Extract grammar/rules
    grammar = grammars[grammar_name]
    rule_map = {rule.name: rule for rule in grammar.rules}
    for name, rule in global_rule_map.items():
        rule_map[name] = rule

    top_rule = rule_map[grammar_name]

    # Generate sentences
    training_sentences: List[Any] = []
    for tagged_sentence, _ in _make_tagged_sentences(top_rule, rule_map):
        tagged_sentences = []

        # Check for template replacements ($name$)
        if "-" in tagged_sentence:
            chunks = re.split(r"-([^-]+)-", tagged_sentence)
            replacements = []
            for i, chunk in enumerate(chunks):
                if ((i % 2) != 0) and (chunk in slot_values):
                    replacements.append(slot_values[chunk])
                else:
                    replacements.append([chunk])

            # Create all combinations of replacements
            for replacement in itertools.product(*replacements):
                tagged_sentences.append("".join(replacement))
        else:
            # No replacements
            tagged_sentences.append(tagged_sentence)

        for tagged_sentence in tagged_sentences:
            # Template -> untagged sentence + entities
            untagged_sentence, entities = extract_entities(tagged_sentence)

            # Split sentence into words (tokens)
            sanitized_sentence, tokens = sanitize_sentence(
                untagged_sentence, sentence_casing, replace_patterns, split_pattern
            )
            training_sentences.append(
                {
                    "sentence": sanitized_sentence,
                    "entities": [e.json() for e in entities],
                    "tokens": tokens,
                    "tagged_sentence": tagged_sentence,
                }
            )

    # Save to JSON
    json_path = profile.write_path("sentences", f"{grammar_name}.json")
    os.makedirs(os.path.split(json_path)[0], exist_ok=True)
    with open(json_path, "w") as json_file:
        json.dump(training_sentences, json_file, indent=4)

    return training_sentences


# -----------------------------------------------------------------------------


def _make_tagged_sentences(rule, rule_map):
    if isinstance(rule, rules.Rule):
        # Unpack
        return _make_tagged_sentences(rule.expansion, rule_map)
    elif isinstance(rule, expansions.AlternativeSet):
        # (a | b | c)
        alt_strs = []
        for child in rule.children:
            alt_strs.extend(_make_tagged_sentences(child, rule_map))
        return alt_strs
    elif isinstance(rule, expansions.RequiredGrouping):
        # (abc)
        group_strs = []
        for child in rule.children:
            group_strs.extend(_make_tagged_sentences(child, rule_map))

        if rule.tag:
            return [(s[0], rule.tag) for s in group_strs]
        else:
            return group_strs
    elif isinstance(rule, expansions.Literal):
        # a
        return [(rule.text, rule.tag)]
    elif isinstance(rule, expansions.OptionalGrouping):
        # [a]
        return [("", rule.tag)] + _make_tagged_sentences(rule.child, rule_map)
    elif isinstance(rule, expansions.Sequence):
        # a b c
        seq_strs = []
        for child in rule.children:
            seq_strs.append(_make_tagged_sentences(child, rule_map))

        # Do all combinations
        sentences = []
        for sent_tuple in itertools.product(*seq_strs):
            sentence = []
            for word, tag in sent_tuple:
                word = word.strip()
                if len(word) > 0:
                    if tag:
                        word = f"[{word}]({tag})"

                    sentence.append(word)

            if len(sentence) > 0:
                sentences.append((" ".join(sentence), rule.tag))

        return sentences

    elif isinstance(rule, expansions.NamedRuleRef):
        # <OtherGrammar.otherRule>
        ref_rule = rule_map.get(rule.name, None)
        if ref_rule is None:
            grammar_name = rule.rule.grammar.name
            ref_rule = rule_map[f"{grammar_name}.{rule.name}"]

        return _make_tagged_sentences(ref_rule, rule_map)
    else:
        # Unsupported
        assert False, rule.__class__


# -----------------------------------------------------------------------------
