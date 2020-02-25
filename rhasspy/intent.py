"""Support for intent recognition."""
import concurrent.futures
import json
import logging
import os
import re
import shutil
import subprocess
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type
from urllib.parse import urljoin

import networkx as nx
import pydash
import requests
from rhasspynlu import json_to_graph, recognize

from rhasspy.actor import RhasspyActor
from rhasspy.events import IntentRecognized, RecognizeIntent, SpeakSentence
from rhasspy.utils import empty_intent, hass_request_kwargs, load_converters

# -----------------------------------------------------------------------------


def get_recognizer_class(system: str) -> Type[RhasspyActor]:
    """Get class for profile intent recognizer."""
    assert system in [
        "dummy",
        "fsticuffs",
        "fuzzywuzzy",
        "adapt",
        "rasa",
        "remote",
        "conversation",
        "command",
    ], f"Invalid intent system: {system}"

    if system == "fsticuffs":
        # Use OpenFST locally
        return FsticuffsRecognizer

    if system == "fuzzywuzzy":
        # Use fuzzy string matching locally
        return FuzzyWuzzyRecognizer

    if system == "adapt":
        # Use Mycroft Adapt locally
        return AdaptIntentRecognizer
    if system == "rasa":
        # Use Rasa NLU remotely
        return RasaIntentRecognizer

    if system == "remote":
        # Use remote rhasspy server
        return RemoteRecognizer

    if system == "conversation":
        # Use HA conversation
        return HomeAssistantConversationRecognizer

    if system == "command":
        # Use command line
        return CommandRecognizer

    # Does nothing
    return DummyIntentRecognizer


# -----------------------------------------------------------------------------


class DummyIntentRecognizer(RhasspyActor):
    """Always returns an empty intent."""

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, RecognizeIntent):
            intent = empty_intent()
            intent["text"] = message.text
            intent["speech_confidence"] = message.confidence
            self.send(message.receiver or sender, IntentRecognized(intent))


# -----------------------------------------------------------------------------
# Remote HTTP Intent Recognizer
# -----------------------------------------------------------------------------


class RemoteRecognizer(RhasspyActor):
    """HTTP based recognizer for remote Rhasspy server."""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.remote_url = ""

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.remote_url = self.profile.get("intent.remote.url")

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, RecognizeIntent):
            try:
                intent = self.recognize(message.text)
            except Exception:
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
        """POST to remote server and return response."""

        params = {"profile": self.profile.name, "nohass": True}
        response = requests.post(self.remote_url, params=params, data=text.encode())
        response.raise_for_status()

        return response.json()


# -----------------------------------------------------------------------------
# OpenFST Intent Recognizer
# https://www.openfst.org
# -----------------------------------------------------------------------------


class FsticuffsRecognizer(RhasspyActor):
    """Recognize intents using OpenFST."""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.graph: Optional[nx.DiGraph] = None
        self.words: Set[str] = set()
        self.stop_words: Set[str] = set()
        self.fuzzy: bool = True
        self.converters: Dict[str, Callable[..., Any]] = {}
        self.preload: bool = False

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.preload = self.config.get("preload", False)
        if self.preload:
            try:
                self.load_graph()
            except Exception as e:
                self._logger.warning("preload: %s", e)

        # True if fuzzy search should be used (default)
        self.fuzzy = self.profile.get("intent.fsticuffs.fuzzy", True)

        # Load user-defined converters
        self.converters = load_converters(self.profile)

        self.transition("loaded")

    def in_loaded(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in loaded state."""
        if isinstance(message, RecognizeIntent):
            try:
                self.load_graph()

                # Assume lower case, white-space separated tokens
                text = message.text
                tokens = re.split(r"\s+", text)

                if self.profile.get("intent.fsticuffs.ignore_unknown_words", True):
                    # Filter tokens
                    tokens = [w for w in tokens if w in self.words]

                recognitions = recognize(
                    tokens,
                    self.graph,
                    fuzzy=self.fuzzy,
                    stop_words=self.stop_words,
                    extra_converters=self.converters,
                )
                assert recognitions, "No intent recognized"

                # Use first intent
                recognition = recognitions[0]

                # Convert to JSON
                intent = recognition.asdict()
            except Exception:
                self._logger.exception("in_loaded")
                intent = empty_intent()
                intent["text"] = message.text
                intent["raw_text"] = message.text

            intent["speech_confidence"] = message.confidence
            self.send(
                message.receiver or sender,
                IntentRecognized(intent, handle=message.handle),
            )

    # -------------------------------------------------------------------------

    def load_graph(self):
        """Load intent graph from JSON file."""
        if self.graph is None:
            graph_path = self.profile.read_path(
                self.profile.get("intent.fsticuffs.intent_graph", "intent.json")
            )

            with open(graph_path, "r") as graph_file:
                json_graph = json.load(graph_file)

            self.graph = json_to_graph(json_graph)

            # Add words from FST
            self.words = set()
            for _, data in self.graph.nodes(data=True):
                if "word" in data:
                    self.words.add(data["word"])

            # Load stop words
            stop_words_path = self.profile.read_path("stop_words.txt")
            if os.path.exists(stop_words_path):
                self._logger.debug("Using stop words at %s", stop_words_path)
                with open(stop_words_path, "r") as stop_words_file:
                    self.stop_words = {
                        line.strip() for line in stop_words_file if line.strip()
                    }

    # -------------------------------------------------------------------------

    def get_problems(self) -> Dict[str, Any]:
        """Get problems at startup."""
        problems: Dict[str, Any] = {}

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
        self.min_confidence: float = 0
        self.preload = False

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.min_confidence = self.profile.get("intent.fuzzywuzzy.min_confidence", 0)
        self.preload = self.config.get("preload", False)
        if self.preload:
            try:
                self.load_examples()
            except Exception as e:
                self._logger.warning("preload: %s", e)

        self.transition("loaded")

    def in_loaded(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in loaded state."""
        if isinstance(message, RecognizeIntent):
            try:
                self.load_examples()
                intent = self.recognize(message.text)
            except Exception:
                self._logger.exception("in_loaded")
                intent = empty_intent()
                intent["text"] = message.text

            intent["raw_text"] = message.text
            intent["speech_confidence"] = message.confidence
            self.send(
                message.receiver or sender,
                IntentRecognized(intent, handle=message.handle),
            )

    # -------------------------------------------------------------------------

    def recognize(self, text: str) -> Dict[str, Any]:
        """Find sentence with lowest string-edit distance."""
        confidence = 0
        if text:
            assert self.examples is not None, "No examples JSON"

            choices: Dict[str, Tuple[str, Dict[str, Any]]] = {}
            with concurrent.futures.ProcessPoolExecutor() as executor:
                future_to_name = {}
                for intent_name, intent_examples in self.examples.items():
                    sentences = []
                    for example in intent_examples:
                        example_text = example.get("raw_text", example["text"])
                        choices[example_text] = (example_text, example)
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
                    best_text, best_intent = choices[best_text]

                    # Update confidence and return example intent
                    best_intent["intent"]["confidence"] = confidence
                    return best_intent

                self._logger.warning(
                    "Intent did not meet confidence threshold: %s < %s",
                    confidence,
                    self.min_confidence,
                )

        # Empty intent
        intent = empty_intent()
        intent["text"] = text
        intent["intent"]["confidence"] = confidence

        return intent

    # -------------------------------------------------------------------------

    def load_examples(self) -> None:
        """Load JSON file with intent examples if not already cached"""
        if self.examples is None:
            examples_path = self.profile.read_path(
                self.profile.get("intent.fuzzywuzzy.examples_json")
            )

            if os.path.exists(examples_path):
                with open(examples_path, "r") as examples_file:
                    self.examples = json.load(examples_file)

                self._logger.debug("Loaded examples from %s", examples_path)


# -----------------------------------------------------------------------------


def _get_best_fuzzy(text, sentences):
    """Find sentence with lowest string-edit distance."""
    from fuzzywuzzy import process

    return process.extractOne(text, sentences)


# -----------------------------------------------------------------------------
# Rasa NLU Intent Recognizer (HTTP API)
# https://rasa.com/
# -----------------------------------------------------------------------------


class RasaIntentRecognizer(RhasspyActor):
    """Uses Rasa NLU HTTP API to recognize intents."""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.project_name = ""
        self.parse_url = ""
        self.min_confidence: float = 0

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        rasa_config = self.profile.get("intent.rasa", {})
        url = rasa_config.get("url", "http://localhost:5005")
        self.project_name = rasa_config.get(
            "project_name", f"rhasspy_{self.profile.name}"
        )
        self.min_confidence = rasa_config.get("min_confidence", 0)
        self.parse_url = urljoin(url, "model/parse")

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, RecognizeIntent):
            try:
                intent = self.recognize(message.text)
                intent["intent"]["name"] = intent["intent"]["name"] or ""
                logging.debug(repr(intent))
                confidence = intent["intent"]["confidence"]
                if confidence < self.min_confidence:
                    intent["intent"]["name"] = ""

                    self._logger.warning(
                        "Intent did not meet confidence threshold: %s < %s",
                        confidence,
                        self.min_confidence,
                    )
            except Exception:
                self._logger.exception("in_started")
                intent = empty_intent()
                intent["text"] = message.text

            intent["raw_text"] = message.text
            self.send(
                message.receiver or sender,
                IntentRecognized(intent, handle=message.handle),
            )

    # -------------------------------------------------------------------------

    def recognize(self, text: str) -> Dict[str, Any]:
        """POST to RasaNLU server and return response."""

        response = requests.post(
            self.parse_url, json={"text": text, "project": self.project_name}
        )

        try:
            response.raise_for_status()
        except Exception:
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
        self.preload = False

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.preload = self.config.get("preload", False)
        if self.preload:
            try:
                self.load_engine()
            except Exception as e:
                self._logger.warning("preload: %s", e)

        self.transition("loaded")

    def in_loaded(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in loaded state."""
        if isinstance(message, RecognizeIntent):
            try:
                self.load_engine()
                intent = self.recognize(message.text)
            except Exception:
                self._logger.exception("in_loaded")
                intent = empty_intent()
                intent["text"] = message.text

            intent["raw_text"] = message.text
            intent["speech_confidence"] = message.confidence
            self.send(
                message.receiver or sender,
                IntentRecognized(intent, handle=message.handle),
            )

    # -------------------------------------------------------------------------

    def recognize(self, text: str) -> Dict[str, Any]:
        """Use Adapt engine to recognize intent."""
        # Get all intents
        assert self.engine is not None, "Adapt engine not loaded"
        intents = [intent for intent in self.engine.determine_intent(text) if intent]

        if intents:
            # Return the best intent only
            intent = max(intents, key=lambda x: x.get("confidence", 0))
            intent_type = intent["intent_type"]
            entity_prefix = f"{intent_type}."

            slots = {}
            for key, value in intent.items():
                if key.startswith(entity_prefix):
                    key = key[len(entity_prefix) :]
                    slots[key] = value

            # Try to match Rasa NLU format for future compatibility
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
        """Configure Adapt engine if not already cached."""
        if self.engine is None:
            # pylint: disable=E0401
            from adapt.intent import IntentBuilder
            from adapt.engine import IntentDeterminationEngine

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

            self._logger.debug("Loaded engine from config file %s", config_path)


# -----------------------------------------------------------------------------
# Home Assistant Conversation
# https://www.home-assistant.io/integrations/conversation
# -----------------------------------------------------------------------------


class HomeAssistantConversationRecognizer(RhasspyActor):
    """Use Home Assistant's conversation component."""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.hass_config: Dict[str, Any] = {}
        self.pem_file: Optional[str] = ""
        self.handle_speech: bool = True

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

        self.handle_speech = self.profile.get("intent.conversation.handle_speech", True)

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, RecognizeIntent):
            post_url = urljoin(self.hass_config["url"], "api/conversation/process")

            # Send to Home Assistant
            kwargs = hass_request_kwargs(self.hass_config, self.pem_file)
            kwargs["json"] = {"text": message.text}

            if self.pem_file is not None:
                kwargs["verify"] = self.pem_file

            # POST to /api/conversation/process
            response = requests.post(post_url, **kwargs)
            response.raise_for_status()

            response_json = response.json()

            # Extract speech
            if self.handle_speech:
                speech = pydash.get(response_json, "speech.plain.speech", "")
                if speech:
                    # Forward to TTS system
                    self._logger.debug("Handling speech")
                    self.send(sender, SpeakSentence(speech))

            # Return empty intent since conversation doesn't give it to us
            intent = empty_intent()
            intent["text"] = message.text
            intent["raw_text"] = message.text
            intent["speech_confidence"] = message.confidence
            self.send(message.receiver or sender, IntentRecognized(intent))


# -----------------------------------------------------------------------------
# Command Intent Recognizer
# -----------------------------------------------------------------------------


class CommandRecognizer(RhasspyActor):
    """Command-line based recognizer"""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.command: List[str] = []

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        program = os.path.expandvars(self.profile.get("intent.command.program"))
        arguments = [
            os.path.expandvars(str(a))
            for a in self.profile.get("intent.command.arguments", [])
        ]

        self.command = [program] + arguments

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, RecognizeIntent):
            try:
                self._logger.debug(self.command)

                # Text -> STDIN -> STDOUT -> JSON
                output = subprocess.run(
                    self.command,
                    check=True,
                    input=message.text.encode(),
                    stdout=subprocess.PIPE,
                ).stdout.decode()

                intent = json.loads(output)

            except Exception:
                self._logger.exception("in_started")
                intent = empty_intent()
                intent["text"] = message.text

            intent["raw_text"] = message.text
            intent["speech_confidence"] = message.confidence
            self.send(
                message.receiver or sender,
                IntentRecognized(intent, handle=message.handle),
            )
