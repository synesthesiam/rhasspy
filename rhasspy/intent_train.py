#!/usr/bin/env python3
import os
import json
import logging
import tempfile
import subprocess
import re
import shutil
import time
import random
import copy
from io import StringIO
from urllib.parse import urljoin
from collections import defaultdict, Counter
from typing import Dict, List, Set, Any, Optional, Type

from rhasspy.actor import RhasspyActor
from rhasspy.utils import make_sentences_by_intent, lcm, sample_sentences_by_intent

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
def get_intent_trainer_class(
    trainer_system: str, recognizer_system: str = "dummy"
) -> Type[RhasspyActor]:

    assert trainer_system in [
        "dummy",
        "fsticuffs",
        "fuzzywuzzy",
        "adapt",
        "rasa",
        "flair",
        "auto",
        "command",
    ], ("Invalid intent training system: %s" % trainer_system)

    if trainer_system == "auto":
        # Use intent recognizer system
        if recognizer_system == "fsticuffs":
            # Use OpenFST acceptor locally
            return FsticuffsIntentTrainer
        elif recognizer_system == "fuzzywuzzy":
            # Use fuzzy string matching locally
            return FuzzyWuzzyIntentTrainer
        elif recognizer_system == "adapt":
            # Use Mycroft Adapt locally
            return AdaptIntentTrainer
        elif recognizer_system == "flair":
            # Use flair locally
            return FlairIntentTrainer
        elif recognizer_system == "rasa":
            # Use Rasa NLU remotely
            return RasaIntentTrainer
        elif recognizer_system == "command":
            # Use command-line intent trainer
            return CommandIntentTrainer
    elif trainer_system == "fsticuffs":
        # Use OpenFST acceptor locally
        return FsticuffsIntentTrainer
    elif trainer_system == "fuzzywuzzy":
        # Use fuzzy string matching locally
        return FuzzyWuzzyIntentTrainer
    elif trainer_system == "adapt":
        # Use Mycroft Adapt locally
        return AdaptIntentTrainer
    elif trainer_system == "rasa":
        # Use Rasa NLU remotely
        return RasaIntentTrainer
    elif trainer_system == "flair":
        # Use flair RNN locally
        return FlairIntentTrainer
    elif trainer_system == "command":
        # Use command-line intent trainer
        return CommandIntentTrainer

    return DummyIntentTrainer


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
                self.train(message.intent_fst)
                self.send(message.receiver or sender, IntentTrainingComplete())
            except Exception as e:
                self._logger.exception("train")
                self.send(message.receiver or sender, IntentTrainingFailed(repr(e)))

    def train(self, intent_fst) -> None:
        examples_path = self.profile.write_path(
            self.profile.get("intent.fuzzywuzzy.examples_json")
        )

        sentences_by_intent: Dict[str, Any] = make_sentences_by_intent(intent_fst)
        with open(examples_path, "w") as examples_file:
            json.dump(sentences_by_intent, examples_file, indent=4)

        self._logger.debug("Wrote intent examples to %s" % examples_path)


# -----------------------------------------------------------------------------
# Rasa NLU Intent Trainer (HTTP API)
# https://rasa.com/
# -----------------------------------------------------------------------------


class RasaIntentTrainer(RhasspyActor):
    """Uses Rasa NLU HTTP API to train a recognizer."""

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, TrainIntent):
            try:
                self.train(message.intent_fst)
                self.send(message.receiver or sender, IntentTrainingComplete())
            except Exception as e:
                self._logger.exception("train")
                self.send(message.receiver or sender, IntentTrainingFailed(repr(e)))

    # -------------------------------------------------------------------------

    def train(self, intent_fst) -> None:
        from rhasspy.train.jsgf2fst import fstprintall
        import requests

        # Load settings
        language = self.profile.get("language", "en")
        rasa_config = self.profile.get("intent.rasa", {})

        url = rasa_config.get("url", "http://localhost:5005")
        project_name = rasa_config.get("project_name", "rhasspy")

        # Create markdown examples
        examples_md_path = self.profile.write_path(
            rasa_config.get("examples_markdown", "intent_examples.md")
        )

        # Build Markdown sentences
        sentences_by_intent: Dict[str, Any] = defaultdict(list)
        for symbols in fstprintall(intent_fst, exclude_meta=False):
            intent_name = ""
            strings = []
            for sym in symbols:
                if sym.startswith("<"):
                    continue  # <eps>
                elif sym.startswith("__label__"):
                    intent_name = sym[9:]
                elif sym.startswith("__begin__"):
                    strings.append("[")
                elif sym.startswith("__end__"):
                    strings[-1] = strings[-1].strip()
                    tag = sym[7:]
                    strings.append(f"]({tag})")
                    strings.append(" ")
                else:
                    strings.append(sym)
                    strings.append(" ")

            sentence = "".join(strings).strip()
            sentences_by_intent[intent_name].append(sentence)

        # Write to YAML file
        with open(examples_md_path, "w") as examples_md_file:
            for intent_name, intent_sents in sentences_by_intent.items():
                # Rasa Markdown training format
                print(f"## intent:{intent_name}", file=examples_md_file)
                for intent_sent in intent_sents:
                    print("-", intent_sent, file=examples_md_file)

                    print("", file=examples_md_file)

        # Create training YAML file
        with tempfile.NamedTemporaryFile(
            suffix=".json", mode="w+", delete=False
        ) as training_file:

            training_config = StringIO()
            training_config.write('language: "%s"\n' % language)
            training_config.write('pipeline: "pretrained_embeddings_spacy"\n')

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
            training_url = urljoin(url, "model/train")
            training_file.seek(0)
            with open(training_file.name, "rb") as training_data:

                training_body = {
                    "config": training_config.getvalue(),
                    "nlu": training_data.read().decode("utf-8"),
                }
                training_config.close()

                response = requests.post(
                    training_url,
                    data=json.dumps(training_body),
                    params=json.dumps({"project": project_name}),
                    headers={"Content-Type": "application/json"},
                )

            self._logger.debug(f"POSTed training data to {training_url}")

            try:
                response.raise_for_status()
            except:
                # Rasa gives quite helpful error messages, so extract them from the response.
                raise Exception(
                    f"{response.reason}: {json.loads(response.content)['message']}"
                )


# -----------------------------------------------------------------------------
# Mycroft Adapt Intent Trainer
# http://github.com/MycroftAI/adapt
# -----------------------------------------------------------------------------


class AdaptIntentTrainer(RhasspyActor):
    """Configure a Mycroft Adapt engine."""

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, TrainIntent):
            try:
                self.train(message.intent_fst)
                self.send(message.receiver or sender, IntentTrainingComplete())
            except Exception as e:
                self._logger.exception("train")
                self.send(message.receiver or sender, IntentTrainingFailed(repr(e)))

    # -------------------------------------------------------------------------

    def train(self, intent_fst) -> None:
        from rhasspy.train.jsgf2fst import fstprintall, symbols2intent

        # Load "stop" words (common words that are excluded from training)
        stop_words: Set[str] = set()
        stop_words_path = self.profile.read_path("stop_words.txt")
        if os.path.exists(stop_words_path):
            with open(stop_words_path, "r") as stop_words_file:
                stop_words = set(
                    [line.strip() for line in stop_words_file if len(line.strip()) > 0]
                )

        # { intent: [ { 'text': ..., 'entities': { ... } }, ... ] }
        sentences_by_intent: Dict[str, Any] = make_sentences_by_intent(intent_fst)

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
                    intent_sent.get("raw_text", intent_sent["text"]),
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
# Flair Intent Trainer
# https://github.com/zalandoresearch/flair
# -----------------------------------------------------------------------------


class FlairIntentTrainer(RhasspyActor):
    """Trains a classification and NER model using flair"""

    def __init__(self):
        RhasspyActor.__init__(self)

    def to_started(self, from_state: str) -> None:
        pass

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, TrainIntent):
            try:
                self.train(message.intent_fst)
                self.send(message.receiver or sender, IntentTrainingComplete())
            except Exception as e:
                self._logger.exception("train")
                self.send(message.receiver or sender, IntentTrainingFailed(repr(e)))

    def train(self, intent_fst) -> None:
        from flair.data import Sentence, Token
        from flair.models import SequenceTagger, TextClassifier
        from flair.embeddings import (
            FlairEmbeddings,
            StackedEmbeddings,
            DocumentRNNEmbeddings,
        )
        from flair.data import TaggedCorpus
        from flair.trainers import ModelTrainer

        # Directory to look for downloaded embeddings
        cache_dir = self.profile.read_path(
            self.profile.get("intent.flair.cache_dir", "flair/cache")
        )

        os.makedirs(cache_dir, exist_ok=True)

        # Directory to store generated models
        data_dir = self.profile.write_path(
            self.profile.get("intent.flair.data_dir", "flair/data")
        )

        if os.path.exists(data_dir):
            shutil.rmtree(data_dir)

        self.embeddings = self.profile.get("intent.flair.embeddings", [])
        assert len(self.embeddings) > 0, "No word embeddings"

        # Create directories to write training data to
        class_data_dir = os.path.join(data_dir, "classification")
        ner_data_dir = os.path.join(data_dir, "ner")
        os.makedirs(class_data_dir, exist_ok=True)
        os.makedirs(ner_data_dir, exist_ok=True)

        # Convert FST to training data
        class_data_path = os.path.join(class_data_dir, "train.txt")
        ner_data_path = os.path.join(ner_data_dir, "train.txt")

        # { intent: [ { 'text': ..., 'entities': { ... } }, ... ] }
        sentences_by_intent: Dict[str, Any] = {}

        # Get sentences for training
        do_sampling = self.profile.get("intent.flair.do_sampling", True)
        start_time = time.time()

        if do_sampling:
            # Sample from each intent FST
            num_samples = int(self.profile.get("intent.flair.num_samples", 10000))
            intent_map_path = self.profile.read_path(
                self.profile.get("training.intent.intent_map", "intent_map.json")
            )

            with open(intent_map_path, "r") as intent_map_file:
                intent_map = json.load(intent_map_file)

            # Gather FSTs for all known intents
            fsts_dir = self.profile.write_dir(
                self.profile.get("speech_to_text.fsts_dir")
            )

            intent_fst_paths = {
                intent_id: os.path.join(fsts_dir, f"{intent_id}.fst")
                for intent_id in intent_map.keys()
            }

            # Generate samples
            self._logger.debug(
                f"Generating {num_samples} sample(s) from {len(intent_fst_paths)} intent(s)"
            )

            sentences_by_intent = sample_sentences_by_intent(
                intent_fst_paths, num_samples
            )
        else:
            # Exhaustively generate all sentences
            self._logger.debug(
                "Generating all possible sentences (may take a long time)"
            )
            sentences_by_intent = make_sentences_by_intent(intent_fst)

        sentence_time = time.time() - start_time
        self._logger.debug(f"Generated sentences in {sentence_time} second(s)")

        # Get least common multiple in order to balance sentences by intent
        lcm_sentences = lcm(*(len(sents) for sents in sentences_by_intent.values()))

        # Generate examples
        class_sentences = []
        ner_sentences: Dict[str, List[Sentence]] = defaultdict(list)
        for intent_name, intent_sents in sentences_by_intent.items():
            num_repeats = max(1, lcm_sentences // len(intent_sents))
            for intent_sent in intent_sents:
                # Only train an intent classifier if there's more than one intent
                if len(sentences_by_intent) > 1:
                    # Add balanced copies
                    for i in range(num_repeats):
                        class_sent = Sentence(labels=[intent_name])
                        for word in intent_sent["tokens"]:
                            class_sent.add_token(Token(word))

                        class_sentences.append(class_sent)

                if len(intent_sent["entities"]) == 0:
                    continue  # no entities, no sequence tagger

                # Named entity recognition (NER) example
                token_idx = 0
                entity_start = {ev["start"]: ev for ev in intent_sent["entities"]}
                entity_end = {ev["end"]: ev for ev in intent_sent["entities"]}
                entity = None

                word_tags = []
                for word in intent_sent["tokens"]:
                    # Determine tag label
                    tag = "O" if not entity else f"I-{entity}"
                    if token_idx in entity_start:
                        entity = entity_start[token_idx]["entity"]
                        tag = f"B-{entity}"

                    word_tags.append((word, tag))

                    # word ner
                    token_idx += len(word) + 1

                    if (token_idx - 1) in entity_end:
                        entity = None

                # Add balanced copies
                for i in range(num_repeats):
                    ner_sent = Sentence()
                    for word, tag in word_tags:
                        token = Token(word)
                        token.add_tag("ner", tag)
                        ner_sent.add_token(token)

                    ner_sentences[intent_name].append(ner_sent)

        # Start training
        max_epochs = int(self.profile.get("intent.flair.max_epochs", 100))

        # Load word embeddings
        self._logger.debug(f"Loading word embeddings from {cache_dir}")
        word_embeddings = [
            FlairEmbeddings(os.path.join(cache_dir, "embeddings", e))
            for e in self.embeddings
        ]

        if len(class_sentences) > 0:
            self._logger.debug("Training intent classifier")

            # Random 80/10/10 split
            class_train, class_dev, class_test = self._split_data(class_sentences)
            class_corpus = TaggedCorpus(class_train, class_dev, class_test)

            # Intent classification
            doc_embeddings = DocumentRNNEmbeddings(
                word_embeddings,
                hidden_size=512,
                reproject_words=True,
                reproject_words_dimension=256,
            )

            classifier = TextClassifier(
                doc_embeddings,
                label_dictionary=class_corpus.make_label_dictionary(),
                multi_label=False,
            )

            self._logger.debug(
                f"Intent classifier has {len(class_sentences)} example(s)"
            )
            trainer = ModelTrainer(classifier, class_corpus)
            trainer.train(class_data_dir, max_epochs=max_epochs)
        else:
            self._logger.info("Skipping intent classifier training")

        if len(ner_sentences) > 0:
            self._logger.debug(f"Training {len(ner_sentences)} NER sequence tagger(s)")

            # Named entity recognition
            stacked_embeddings = StackedEmbeddings(word_embeddings)

            for intent_name, intent_ner_sents in ner_sentences.items():
                ner_train, ner_dev, ner_test = self._split_data(intent_ner_sents)
                ner_corpus = TaggedCorpus(ner_train, ner_dev, ner_test)

                tagger = SequenceTagger(
                    hidden_size=256,
                    embeddings=stacked_embeddings,
                    tag_dictionary=ner_corpus.make_tag_dictionary(tag_type="ner"),
                    tag_type="ner",
                    use_crf=True,
                )

                ner_intent_dir = os.path.join(ner_data_dir, intent_name)
                os.makedirs(ner_intent_dir, exist_ok=True)

                self._logger.debug(
                    f"NER tagger for {intent_name} has {len(intent_ner_sents)} example(s)"
                )
                trainer = ModelTrainer(tagger, ner_corpus)
                trainer.train(ner_intent_dir, max_epochs=max_epochs)
        else:
            self._logger.info("Skipping NER sequence tagger training")

    # -------------------------------------------------------------------------

    def _split_data(self, data, split=0.1):
        """Randomly splits a data set into train, dev, and test sets"""

        random.shuffle(data)
        split_index = int(len(data) * split)

        # 1 - (2*split)
        train = data[(split_index * 2) :]

        # split
        dev = data[:split_index]

        # split
        test = data[split_index : (split_index * 2)]

        return train, dev, test


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
                self.train(message.intent_fst)
                self.send(message.receiver or sender, IntentTrainingComplete())
            except Exception as e:
                self._logger.exception("train")
                self.send(message.receiver or sender, IntentTrainingFailed(repr(e)))

    def train(self, intent_fst) -> None:
        try:
            self._logger.debug(self.command)

            # { intent: [ { 'text': ..., 'entities': { ... } }, ... ] }
            sentences_by_intent: Dict[str, Any] = make_sentences_by_intent(intent_fst)

            # JSON -> STDIN
            input = json.dumps({sentences_by_intent}).encode()

            subprocess.run(self.command, input=input, check=True)
        except:
            self._logger.exception("train")
