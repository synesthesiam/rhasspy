#!/usr/bin/env python3
import os
import sys
import re
import json
import logging
import subprocess
import shutil
import concurrent.futures
from urllib.parse import urljoin
from typing import Dict, Any, Optional, Tuple, List, Set, Type

from .actor import RhasspyActor
from .profiles import Profile
from .utils import empty_intent

# -----------------------------------------------------------------------------
# Events
# -----------------------------------------------------------------------------


class RecognizeIntent:
    def __init__(
        self,
        text: str,
        receiver: Optional[RhasspyActor] = None,
        handle: bool = True,
        confidence: float = 1,
    ) -> None:
        self.text = text
        self.confidence = confidence
        self.receiver = receiver
        self.handle = handle


class IntentRecognized:
    def __init__(self, intent: Dict[str, Any], handle: bool = True) -> None:
        self.intent = intent
        self.handle = handle


# -----------------------------------------------------------------------------


def get_recognizer_class(system: str) -> Type[RhasspyActor]:
    assert system in [
        "dummy",
        "fsticuffs",
        "fuzzywuzzy",
        "adapt",
        "rasa",
        "remote",
        "flair",
        "command",
    ], ("Invalid intent system: %s" % system)

    if system == "fsticuffs":
        # Use OpenFST locally
        return FsticuffsRecognizer
    elif system == "fuzzywuzzy":
        # Use fuzzy string matching locally
        return FuzzyWuzzyRecognizer
    elif system == "adapt":
        # Use Mycroft Adapt locally
        return AdaptIntentRecognizer
    elif system == "rasa":
        # Use Rasa NLU remotely
        return RasaIntentRecognizer
    elif system == "remote":
        # Use remote rhasspy server
        return RemoteRecognizer
    elif system == "flair":
        # Use flair locally
        return FlairRecognizer
    elif system == "command":
        # Use command line
        return CommandRecognizer
    else:
        # Does nothing
        return DummyIntentRecognizer


# -----------------------------------------------------------------------------


class DummyIntentRecognizer(RhasspyActor):
    """Always returns an empty intent"""

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, RecognizeIntent):
            intent = empty_intent()
            intent["text"] = message.text
            intent["speech_confidence"] = message.confidence
            self.send(message.receiver or sender, IntentRecognized(intent))


# -----------------------------------------------------------------------------
# Remote HTTP Intent Recognizer
# -----------------------------------------------------------------------------


class RemoteRecognizer(RhasspyActor):
    """HTTP based recognizer for remote rhasspy server"""

    def to_started(self, from_state: str) -> None:
        self.remote_url = self.profile.get("intent.remote.url")

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, RecognizeIntent):
            try:
                intent = self.recognize(message.text)
            except Exception as e:
                self._logger.exception("in_started")
                intent = empty_intent()
                intent["text"] = message.text

            intent["speech_confidence"] = message.confidence
            self.send(
                message.receiver or sender,
                IntentRecognized(intent, handle=message.handle),
            )

    # -------------------------------------------------------------------------

    def recognize(self, text: str) -> Dict[str, Any]:
        import requests

        params = {"profile": self.profile.name, "nohass": True}
        response = requests.post(self.remote_url, params=params, data=text.encode())
        response.raise_for_status()

        return response.json()


# -----------------------------------------------------------------------------
# OpenFST Intent Recognizer
# https://www.openfst.org
# -----------------------------------------------------------------------------


class FsticuffsRecognizer(RhasspyActor):
    """Recognize intents using OpenFST"""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.fst: Optional[Any] = None
        self.words: Set[str] = set()

    def to_started(self, from_state: str) -> None:
        self.preload: bool = self.config.get("preload", False)
        if self.preload:
            try:
                self.load_fst()
            except Exception as e:
                self._logger.warning(f"preload: {e}")

        self.transition("loaded")

    def in_loaded(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, RecognizeIntent):
            try:
                self.load_fst()
                intent = self.recognize(message.text)
            except Exception as e:
                self._logger.exception("in_loaded")
                intent = empty_intent()

            intent["speech_confidence"] = message.confidence
            self.send(
                message.receiver or sender,
                IntentRecognized(intent, handle=message.handle),
            )

    # -------------------------------------------------------------------------

    def recognize(self, text: str) -> Dict[str, Any]:
        from jsgf2fst import fstaccept

        # Assume lower case, white-space separated tokens
        tokens = re.split("\s+", text.lower())

        if self.profile.get("intent.fsticuffs.ignore_unknown_words", True):
            tokens = [w for w in tokens if w in self.words]

        intents = fstaccept(self.fst, tokens)
        self._logger.debug(f"Got {len(intents)} intent(s)")

        if len(intents) > 0:
            self._logger.debug(intents)

        return intents[0]

    # -------------------------------------------------------------------------

    def load_fst(self):
        if self.fst is None:
            import pywrapfst as fst

            fst_path = self.profile.read_path(
                self.profile.get("intent.fsticuffs.intent_fst", "intent.fst")
            )

            self.fst = fst.Fst.read(fst_path)

            # Add words from FST
            in_symbols = self.fst.input_symbols()
            self.words = set()
            for i in range(in_symbols.num_symbols()):
                word = in_symbols.find(i).decode()
                self.words.add(word)

    # -------------------------------------------------------------------------

    def get_problems(self) -> Dict[str, Any]:
        problems: Dict[str, Any] = {}

        try:
            import pywrapfst as fst
        except:
            problems[
                "openfst not installed"
            ] = "openfst Python library not installed. Try pip3 install openfst"

        if not shutil.which("fstminimize"):
            problems[
                "Missing OpenFST tools"
            ] = "OpenFST command-line tools not installed. Try sudo apt-get install libfst-tools"

        fst_path = self.profile.read_path(
            self.profile.get("intent.fsticuffs.intent_fst", "intent.fst")
        )

        if not os.path.exists(fst_path):
            problems[
                "Missing intent FST"
            ] = f"Intent finite state transducer (FST) not found at {fst_path}. Did you train your profile?"

        return problems


# -----------------------------------------------------------------------------
# Fuzzywuzzy-based Intent Recognizer
# https://github.com/seatgeek/fuzzywuzzy
# -----------------------------------------------------------------------------


class FuzzyWuzzyRecognizer(RhasspyActor):
    """Recognize intents using fuzzy string matching"""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.examples: Optional[Dict[str, Any]] = None

    def to_started(self, from_state: str) -> None:
        self.min_confidence = self.profile.get("intent.fuzzywuzzy.min_confidence", 0)
        self.preload: bool = self.config.get("preload", False)
        if self.preload:
            try:
                self.load_examples()
            except Exception as e:
                self._logger.warning(f"preload: {e}")

        self.transition("loaded")

    def in_loaded(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, RecognizeIntent):
            try:
                self.load_examples()
                intent = self.recognize(message.text)
            except Exception as e:
                self._logger.exception("in_loaded")
                intent = empty_intent()

            intent["speech_confidence"] = message.confidence
            self.send(
                message.receiver or sender,
                IntentRecognized(intent, handle=message.handle),
            )

    # -------------------------------------------------------------------------

    def recognize(self, text: str) -> Dict[str, Any]:
        confidence = 0
        if len(text) > 0:
            assert self.examples is not None, "No examples JSON"

            choices: Dict[str, Tuple[str, str, Dict[str, List[str]]]] = {}
            with concurrent.futures.ProcessPoolExecutor() as executor:
                future_to_name = {}
                for intent_name, intent_examples in self.examples.items():
                    sentences = []
                    for example in intent_examples:
                        example_text = example["text"]
                        choices[example_text] = (
                            example_text,
                            intent_name,
                            example["entities"],
                        )
                        sentences.append(example_text)

                    future = executor.submit(_get_best_fuzzy, text, sentences)
                    future_to_name[future] = intent_name

            # Process them as they complete
            best_text = ""
            best_score = None
            for future in concurrent.futures.as_completed(future_to_name):
                intent_name = future_to_name[future]
                text, score = future.result()
                if (best_score is None) or (score > best_score):
                    best_text = text
                    best_score = score

            if best_text in choices:
                confidence = (best_score / 100) if best_score else 1
                if confidence >= self.min_confidence:
                    # (text, intent, slots)
                    best_text, best_intent, best_entities = choices[best_text]

                    # Try to match RasaNLU format for future compatibility
                    return {
                        "text": best_text,
                        "intent": {"name": best_intent, "confidence": confidence},
                        "entities": best_entities,
                    }
                else:
                    self._logger.warning(
                        f"Intent did not meet confidence threshold: {confidence} < {self.min_confidence}"
                    )

        # Empty intent
        intent = empty_intent()
        intent["text"] = text
        intent["intent"]["confidence"] = confidence

        return intent

    # -------------------------------------------------------------------------

    def load_examples(self) -> None:
        if self.examples is None:
            """Load JSON file with intent examples if not already cached"""
            examples_path = self.profile.read_path(
                self.profile.get("intent.fuzzywuzzy.examples_json")
            )

            if os.path.exists(examples_path):
                with open(examples_path, "r") as examples_file:
                    self.examples = json.load(examples_file)

                self._logger.debug("Loaded examples from %s" % examples_path)


# -----------------------------------------------------------------------------


def _get_best_fuzzy(text, sentences):
    from fuzzywuzzy import process

    return process.extractOne(text, sentences)


# -----------------------------------------------------------------------------
# RasaNLU Intent Recognizer (HTTP API)
# https://rasa.com/
# -----------------------------------------------------------------------------


class RasaIntentRecognizer(RhasspyActor):
    """Uses Rasa NLU HTTP API to recognize intents."""

    def to_started(self, from_state: str) -> None:
        rasa_config = self.profile.get("intent.rasa", {})
        url = rasa_config.get("url", "http://localhost:5005")
        self.project_name = rasa_config.get(
            "project_name", "rhasspy_%s" % self.profile.name
        )
        self.parse_url = urljoin(url, "model/parse")

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, RecognizeIntent):
            try:
                intent = self.recognize(message.text)
                logging.debug(repr(intent))
            except Exception as e:
                self._logger.exception("in_started")
                intent = empty_intent()
                intent["text"] = message.text

            self.send(
                message.receiver or sender,
                IntentRecognized(intent, handle=message.handle),
            )

    # -------------------------------------------------------------------------

    def recognize(self, text: str) -> Dict[str, Any]:
        import requests

        response = requests.post(
            self.parse_url, json={"text": text, "project": self.project_name}
        )

        try:
            response.raise_for_status()
        except:
            # Rasa gives quite helpful error messages, so extract them from the response.
            raise Exception(
                f"{response.reason}: {json.loads(response.content)['message']}"
            )

        return response.json()


# -----------------------------------------------------------------------------
# Mycroft Adapt Intent Recognizer
# http://github.com/MycroftAI/adapt
# -----------------------------------------------------------------------------


class AdaptIntentRecognizer(RhasspyActor):
    """Recognize intents with Mycroft Adapt."""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.engine = None

    def to_started(self, from_state: str) -> None:
        self.preload: bool = self.config.get("preload", False)
        if self.preload:
            try:
                self.load_engine()
            except Exception as e:
                self._logger.warning(f"preload: {e}")

        self.transition("loaded")

    def in_loaded(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, RecognizeIntent):
            try:
                self.load_engine()
                intent = self.recognize(message.text)
            except Exception as e:
                self._logger.exception("in_loaded")
                intent = empty_intent()

            intent["speech_confidence"] = message.confidence
            self.send(
                message.receiver or sender,
                IntentRecognized(intent, handle=message.handle),
            )

    # -------------------------------------------------------------------------

    def recognize(self, text: str) -> Dict[str, Any]:
        # Get all intents
        assert self.engine is not None, "Adapt engine not loaded"
        intents = [intent for intent in self.engine.determine_intent(text) if intent]

        if len(intents) > 0:
            # Return the best intent only
            intent = max(intents, key=lambda x: x.get("confidence", 0))
            intent_type = intent["intent_type"]
            entity_prefix = "{0}.".format(intent_type)

            slots = {}
            for key, value in intent.items():
                if key.startswith(entity_prefix):
                    key = key[len(entity_prefix) :]
                    slots[key] = value

            # Try to match RasaNLU format for future compatibility
            return {
                "text": text,
                "intent": {
                    "name": intent_type,
                    "confidence": intent.get("confidence", 0),
                },
                "entities": [
                    {"entity": name, "value": value} for name, value in slots.items()
                ],
            }

        return empty_intent()

    # -------------------------------------------------------------------------

    def load_engine(self) -> None:
        """Configure Adapt engine if not already cached"""
        if self.engine is None:
            from adapt.intent import IntentBuilder
            from adapt.engine import IntentDeterminationEngine

            assert self.engine is not None
            config_path = self.profile.read_path("adapt_config.json")
            if not os.path.exists(config_path):
                return

            # Create empty engine
            self.engine = IntentDeterminationEngine()
            assert self.engine is not None

            # { intents: { ... }, entities: [ ... ] }
            with open(config_path, "r") as config_file:
                config = json.load(config_file)

            # Register entities
            for entity_name, entity_values in config["entities"].items():
                for value in entity_values:
                    self.engine.register_entity(value, entity_name)

            # Register intents
            for intent_name, intent_config in config["intents"].items():
                intent = IntentBuilder(intent_name)
                for required_entity in intent_config["require"]:
                    intent.require(required_entity)

                for optional_entity in intent_config["optionally"]:
                    intent.optionally(optional_entity)

                self.engine.register_intent_parser(intent.build())

            self._logger.debug("Loaded engine from config file %s" % config_path)


# -----------------------------------------------------------------------------
# Flair Intent Recognizer
# https://github.com/zalandoresearch/flair
# -----------------------------------------------------------------------------


class FlairRecognizer(RhasspyActor):
    """Flair based recognizer"""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)

        self.class_model: Optional[TextClassifier] = None
        self.ner_models: Optional[Dict[str, SequenceTagger]] = None
        self.intent_map: Optional[Dict[str, str]] = None

    def to_started(self, from_state: str) -> None:
        self.preload: bool = self.config.get("preload", False)
        if self.preload:
            try:
                # Pre-load models
                self.load_models()
            except Exception as e:
                self._logger.warning(f"preload: {e}")

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, RecognizeIntent):
            try:
                self.load_models()
                intent = self.recognize(message.text)
            except Exception as e:
                self._logger.exception("in_started")
                intent = empty_intent()
                intent["text"] = message.text

            intent["speech_confidence"] = message.confidence
            self.send(
                message.receiver or sender,
                IntentRecognized(intent, handle=message.handle),
            )

    def recognize(self, text: str) -> Dict[str, Any]:
        from flair.data import Sentence

        intent = empty_intent()
        sentence = Sentence(text)

        if self.class_model is not None:
            self.class_model.predict(sentence)
            assert len(sentence.labels) > 0, "No intent predicted"

            label = sentence.labels[0]
            intent_id = label.value
            intent["intent"]["confidence"] = label.score
        else:
            # Assume first intent
            intent_id = next(iter(self.intent_map.keys()))
            intent["intent"]["confidence"] = 1

        intent["intent"]["name"] = self.intent_map[intent_id]

        if intent_id in self.ner_models:
            # Predict entities
            self.ner_models[intent_id].predict(sentence)
            ner_dict = sentence.to_dict(tag_type="ner")
            for named_entity in ner_dict["entities"]:
                intent["entities"].append(
                    {
                        "entity": named_entity["type"],
                        "value": named_entity["text"],
                        "start": named_entity["start_pos"],
                        "end": named_entity["end_pos"],
                        "confidence": named_entity["confidence"],
                    }
                )

        return intent

    # -------------------------------------------------------------------------

    def load_models(self) -> None:
        from flair.models import TextClassifier, SequenceTagger

        # Load mapping from intent id to user intent name
        if self.intent_map is None:
            intent_map_path = self.profile.read_path(
                self.profile.get("training.intent.intent_map", "intent_map.json")
            )

            with open(intent_map_path, "r") as intent_map_file:
                self.intent_map = json.load(intent_map_file)

        data_dir = self.profile.read_path(
            self.profile.get("intent.flair.data_dir", "flair_data")
        )

        # Only load intent classifier if there is more than one intent
        if (self.class_model is None) and (len(self.intent_map) > 1):
            class_model_path = os.path.join(
                data_dir, "classification", "final-model.pt"
            )
            self._logger.debug(f"Loading classification model from {class_model_path}")
            self.class_model = TextClassifier.load_from_file(class_model_path)
            self._logger.debug("Loaded classification model")

        if self.ner_models is None:
            ner_models = {}
            ner_data_dir = os.path.join(data_dir, "ner")
            for file_name in os.listdir(ner_data_dir):
                ner_model_dir = os.path.join(ner_data_dir, file_name)
                if os.path.isdir(ner_model_dir):
                    # Assume directory is intent name
                    intent_name = file_name
                    if intent_name not in self.intent_map:
                        self._logger.warning(
                            f"{intent_name} was not found in intent map"
                        )

                    ner_model_path = os.path.join(ner_model_dir, "final-model.pt")
                    self._logger.debug(f"Loading NER model from {ner_model_path}")
                    ner_models[intent_name] = SequenceTagger.load_from_file(
                        ner_model_path
                    )

            self._logger.debug("Loaded NER model(s)")
            self.ner_models = ner_models


# -----------------------------------------------------------------------------
# Command Intent Recognizer
# -----------------------------------------------------------------------------


class CommandRecognizer(RhasspyActor):
    """Command-line based recognizer"""

    def to_started(self, from_state: str) -> None:
        program = os.path.expandvars(self.profile.get("intent.command.program"))
        arguments = [
            os.path.expandvars(str(a))
            for a in self.profile.get("intent.command.arguments", [])
        ]

        self.command = [program] + arguments

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        if isinstance(message, RecognizeIntent):
            try:
                self._logger.debug(self.command)

                # Text -> STDIN -> STDOUT -> JSON
                output = subprocess.check_output(
                    self.command, input=message.text.encode()
                ).decode()

                intent = json.loads(output)

            except Exception as e:
                self._logger.exception("in_started")
                intent = empty_intent()
                intent["text"] = message.text

            intent["speech_confidence"] = message.confidence
            self.send(
                message.receiver or sender,
                IntentRecognized(intent, handle=message.handle),
            )
