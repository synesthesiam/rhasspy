import os
import json
import logging
import tempfile
import subprocess
import re
from urllib.parse import urljoin
from collections import defaultdict, Counter
from typing import Dict, List, Set, Any, Optional

from .actor import RhasspyActor
from .utils import open_maybe_gzip

# -----------------------------------------------------------------------------
# Events
# -----------------------------------------------------------------------------


class TrainIntent:
    def __init__(self, intent_fst, receiver: Optional[RhasspyActor] = None) -> None:
        self.intent_fst = intent_fst
        self.receiver = receiver


class IntentTrainingComplete:
    pass


class IntentTrainingFailed:
    def __init__(self, reason: str) -> None:
        self.reason = reason


# -----------------------------------------------------------------------------


class DummyIntentTrainer(RhasspyActor):
    """Does nothing."""

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, TrainIntent):
            self.send(message.receiver or sender, IntentTrainingComplete())


# -----------------------------------------------------------------------------
# OpenFST-based intent recognizer
# https://www.openfst.org
# -----------------------------------------------------------------------------


class FsticuffsIntentTrainer(DummyIntentTrainer):
    """No training needed. Intent FST will be used directly during recognition."""

    pass


# -----------------------------------------------------------------------------
# Fuzzywuzzy-based Intent Trainer
# https://github.com/seatgeek/fuzzywuzzy
# -----------------------------------------------------------------------------


class FuzzyWuzzyIntentTrainer(RhasspyActor):
    """Save examples to JSON for fuzzy string matching later."""

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, TrainIntent):
            try:
                self.train(message.sentences_by_intent)
                self.send(message.receiver or sender, IntentTrainingComplete())
            except Exception as e:
                self._logger.exception("train")
                self.send(message.receiver or sender, IntentTrainingFailed(repr(e)))

    def train(self, sentences_by_intent: Dict[str, Any]) -> None:
        examples_path = self.profile.write_path(
            self.profile.get("intent.fuzzywuzzy.examples_json")
        )

        examples = self._make_examples(sentences_by_intent)
        with open(examples_path, "w") as examples_file:
            json.dump(examples, examples_file, indent=4)

        self._logger.debug("Wrote intent examples to %s" % examples_path)

    # -------------------------------------------------------------------------

    def _make_examples(self, sentences_by_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Write intent examples to a JSON file."""
        from fuzzywuzzy import process

        # { intent: [ { 'text': ..., 'slots': { ... } }, ... ] }
        examples: Dict[str, Any] = defaultdict(list)

        for intent, intent_sents in sentences_by_intent.items():
            for intent_sent in intent_sents:
                slots: Dict[str, List[str]] = defaultdict(list)
                for sent_ent in intent_sent["entities"]:
                    slots[sent_ent["entity"]].append(sent_ent["value"])

                examples[intent].append(
                    {"text": intent_sent["sentence"], "slots": slots}
                )

        return examples


# -----------------------------------------------------------------------------
# RasaNLU Intent Trainer (HTTP API)
# https://rasa.com/
# -----------------------------------------------------------------------------


class RasaIntentTrainer(RhasspyActor):
    """Uses rasaNLU HTTP API to train a recognizer."""

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, TrainIntent):
            try:
                self.train(message.sentences_by_intent)
                self.send(message.receiver or sender, IntentTrainingComplete())
            except Exception as e:
                self._logger.exception("train")
                self.send(message.receiver or sender, IntentTrainingFailed(repr(e)))

    # -------------------------------------------------------------------------

    def train(self, sentences_by_intent: Dict[str, Any]) -> None:
        import requests

        # Load settings
        language = self.profile.get("language", "en")
        rasa_config = self.profile.get("intent.rasa", {})

        url = rasa_config.get("url", "http://locahost:5000")
        project_name = rasa_config.get("project_name", "rhasspy")

        # Create markdown examples
        examples_md_path = self.profile.write_path(
            rasa_config.get("examples_markdown", "intent_examples.md")
        )

        with open(examples_md_path, "w") as examples_md_file:
            for intent_name, intent_sents in sentences_by_intent.items():
                # Rasa Markdown training format
                print("## intent:%s" % intent_name, file=examples_md_file)
                for intent_sent in intent_sents:
                    print("-", intent_sent["tagged_sentence"], file=examples_md_file)

                print("", file=examples_md_file)

        # Create training YAML file
        with tempfile.NamedTemporaryFile(
            suffix=".yml", mode="w+", delete=False
        ) as training_file:
            print('language: "%s"\n' % language, file=training_file)
            print('pipeline: "spacy_sklearn"\n', file=training_file)
            print("data: |", file=training_file)

            # Write markdown directly into YAML.
            # Because reasons.
            with open(examples_md_path, "r") as examples_md_file:
                blank_line = False
                for line in examples_md_file:
                    line = line.strip()
                    if len(line) > 0:
                        if blank_line:
                            print("", file=training_file)
                            blank_line = False

                        print("  %s" % line, file=training_file)
                    else:
                        blank_line = True

            # Do training via HTTP API
            training_url = urljoin(url, "train")
            training_file.seek(0)
            training_data = open(training_file.name, "rb").read()
            response = requests.post(
                training_url,
                data=training_data,
                params={"project": project_name},
                headers={"Content-Type": "application/x-yml"},
            )

            self._logger.debug(
                "POSTed %s byte(s) to %s" % (len(training_data), training_url)
            )
            response.raise_for_status()


# -----------------------------------------------------------------------------
# Mycroft Adapt Intent Trainer
# http://github.com/MycroftAI/adapt
# -----------------------------------------------------------------------------


class AdaptIntentTrainer(RhasspyActor):
    """Configure a Mycroft Adapt engine."""

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, TrainIntent):
            try:
                self.train(message.sentences_by_intent)
                self.send(message.receiver or sender, IntentTrainingComplete())
            except Exception as e:
                self._logger.exception("train")
                self.send(message.receiver or sender, IntentTrainingFailed(repr(e)))

    # -------------------------------------------------------------------------

    def train(self, sentences_by_intent: Dict[str, Any]) -> None:
        # Load "stop" words (common words that are excluded from training)
        stop_words: Set[str] = set()
        stop_words_path = self.profile.read_path("stop_words.txt")
        if os.path.exists(stop_words_path):
            with open(stop_words_path, "r") as stop_words_file:
                stop_words = set(
                    [line.strip() for line in stop_words_file if len(line.strip()) > 0]
                )

        # Generate intent configuration
        entities: Dict[str, Set[str]] = {}
        intents: Dict[str, Dict[str, Any]] = {}

        for intent_name, intent_sents in sentences_by_intent.items():
            intent: Dict[str, Any] = {
                "name": intent_name,
                "require": [],
                "optionally": [],
            }

            # Track word usage by sentence to determine required vs. optional words
            word_counts: Dict[str, int] = Counter()
            entity_counts: Dict[str, int] = Counter()

            # Process sentences for this intent
            for intent_sent in intent_sents:
                sentence, slots, word_tokens = (
                    intent_sent["sentence"],
                    intent_sent["entities"],
                    intent_sent["tokens"],
                )
                entity_tokens: Set[str] = set()

                # Group slot values by entity
                slot_entities: Dict[str, List[str]] = defaultdict(list)
                for sent_ent in slots:
                    slot_entities[sent_ent["entity"]].append(sent_ent["value"])

                # Add entities
                for entity_name, entity_values in slot_entities.items():
                    # Prefix entity name with intent name
                    entity_name = "{0}.{1}".format(intent_name, entity_name)
                    if not entity_name in entities:
                        entities[entity_name] = set()

                    entities[entity_name].update(entity_values)
                    entity_counts[entity_name] += 1

                    # Split entity values by whitespace
                    for value in entity_values:
                        entity_tokens.update(re.split(r"\s", value))

                # Get all non-stop words that are not part of entity values
                words = set(word_tokens) - entity_tokens - stop_words

                # Increment count for words
                for word in words:
                    word_counts[word] += 1

            # Decide on required vs. optional for words and entities
            num_sentences = len(intent_sents)

            required_words = set()
            optional_words = set()
            for word, count in word_counts.items():
                assert count <= num_sentences, "Invalid word count"
                if count == num_sentences:
                    # Word exists in all sentences
                    required_words.add(word)
                else:
                    # Word only exists in some sentences
                    optional_words.add(word)

            if len(required_words) > 0:
                # Create entity for required keywords
                entity_name = "{0}RequiredKeyword".format(intent_name)
                entities[entity_name] = required_words
                intent["require"].append(entity_name)

            if len(optional_words) > 0:
                # Create entity for required keywords
                entity_name = "{0}OptionalKeyword".format(intent_name)
                entities[entity_name] = optional_words
                intent["optionally"].append(entity_name)

            # Add required/optional entities
            for name, count in entity_counts.items():
                assert count <= num_sentences, "Invalid entity count"
                if count == num_sentences:
                    # Entity exists in all sentences
                    intent["require"].append(name)
                else:
                    # Entity only exists in some sentences
                    intent["optionally"].append(name)

            intents[intent_name] = intent

        # ---------------------------------------------------------------------

        # Write configuration file
        config = {
            "intents": intents,
            # Convert sets to lists because JSON serializer is super whiny
            "entities": {name: list(values) for name, values in entities.items()},
        }

        config_path = self.profile.write_path("adapt_config.json")
        with open(config_path, "w") as config_file:
            json.dump(config, config_file, indent=4)

        self._logger.debug("Wrote adapt configuration to %s" % config_path)


# -----------------------------------------------------------------------------
# Command-line Based Intent Trainer
# -----------------------------------------------------------------------------


class CommandIntentTrainer(RhasspyActor):
    """Calls out to a command-line program to do intent system training."""

    def to_started(self, from_state: str) -> None:
        program = os.path.expandvars(
            self.profile.get("training.intent.command.program")
        )
        arguments = [
            os.path.expandvars(str(a))
            for a in self.profile.get("training.intent.command.arguments", [])
        ]

        self.command = [program] + arguments

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, TrainIntent):
            try:
                self.train(message.sentences_by_intent)
                self.send(message.receiver or sender, IntentTrainingComplete())
            except Exception as e:
                self._logger.exception("train")
                self.send(message.receiver or sender, IntentTrainingFailed(repr(e)))

    def train(self, sentences_by_intent: Dict[str, Any]) -> None:
        try:
            self._logger.debug(self.command)

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
