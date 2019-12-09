"""Support for intent recognition."""
import concurrent.futures
import json
import logging
import os
import re
import shutil
import subprocess
from typing import Any, Dict, List, Optional, Set, Tuple, Type
from urllib.parse import urljoin

import networkx as nx
import pywrapfst as fst
import pydash
import requests

from rhasspy.actor import RhasspyActor
from rhasspy.tts import SpeakSentence
from rhasspy.utils import empty_intent, hass_request_kwargs

# -----------------------------------------------------------------------------
# Events
# -----------------------------------------------------------------------------


class RecognizeIntent:
    """Request to recognize an intent."""

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
    """Response to RecognizeIntent."""

    def __init__(self, intent: Dict[str, Any], handle: bool = True) -> None:
        self.intent = intent
        self.handle = handle


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
        "flair",
        "conversation",
        "command",
    ], ("Invalid intent system: %s" % system)

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

    if system == "flair":
        # Use flair locally
        return FlairRecognizer

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
        self.fst: Optional[Any] = None
        self.graph: Optional[Any] = None
        self.words: Set[str] = set()
        self.stop_words: Set[str] = set()
        self.fuzzy: bool = True
        self.preload: bool = False

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.preload = self.config.get("preload", False)
        if self.preload:
            try:
                self.load_fst()
            except Exception as e:
                self._logger.warning("preload: %s", e)

        # True if fuzzy search should be used (default)
        self.fuzzy = self.profile.get("intent.fsticuffs.fuzzy", True)
        self.transition("loaded")

    def in_loaded(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in loaded state."""
        if isinstance(message, RecognizeIntent):
            try:
                self.load_fst()

                if self.fuzzy:
                    # Fuzzy search
                    intent = self.recognize_fuzzy(message.text)
                else:
                    # Strict search
                    intent = self.recognize(message.text)
            except Exception:
                self._logger.exception("in_loaded")
                intent = empty_intent()

            intent["speech_confidence"] = message.confidence
            self.send(
                message.receiver or sender,
                IntentRecognized(intent, handle=message.handle),
            )

    # -------------------------------------------------------------------------

    def recognize(self, text: str) -> Dict[str, Any]:
        """Use FST as acceptor."""
        from rhasspy.train.jsgf2fst import fstaccept

        # Assume lower case, white-space separated tokens
        tokens = re.split(r"\s+", text.lower())

        if self.profile.get("intent.fsticuffs.ignore_unknown_words", True):
            tokens = [w for w in tokens if w in self.words]

        intents = fstaccept(self.fst, tokens)
        self._logger.debug("Got %s intent(s)", len(intents))

        if len(intents) > 0:
            self._logger.debug(intents)

        return intents[0]

    def recognize_fuzzy(self, text: str, eps: str = "<eps>") -> Dict[str, Any]:
        """Do fuzzy breadth-first search on FST as graph."""
        from rhasspy.train.jsgf2fst import symbols2intent

        # Assume lower case, white-space separated tokens
        tokens = re.split(r"\s+", text)

        if self.profile.get("intent.fsticuffs.ignore_unknown_words", True):
            # Filter tokens
            tokens = [w for w in tokens if w in self.words]

        # Only run search if there are any tokens
        intents = []
        if len(tokens) > 0:
            intent_symbols_and_costs = FsticuffsRecognizer._get_symbols_and_costs(
                self.graph, tokens, stop_words=self.stop_words, eps=eps
            )
            for symbols, cost in intent_symbols_and_costs.values():
                intent = symbols2intent(symbols, eps=eps)
                intent["intent"]["confidence"] = (len(tokens) - cost) / len(tokens)
                intents.append(intent)

            intents = sorted(
                intents, key=lambda i: i["intent"]["confidence"], reverse=True
            )

        self._logger.debug("Recognized %s intent(s)", len(intents))

        # Use first intent
        if len(intents) > 0:
            intent = intents[0]

            # Add slots
            intent["slots"] = {}
            for ev in intent["entities"]:
                intent["slots"][ev["entity"]] = ev["value"]

            # Add alternative intents
            intent["intents"] = []
            for other_intent in intents[1:]:
                intent["intents"].append(other_intent)

            self._logger.debug(intents)
        else:
            intent = empty_intent()
            intent["text"] = text

        return intent

    # -------------------------------------------------------------------------

    @classmethod
    def _get_symbols_and_costs(
        cls,
        intent_graph: nx.MultiDiGraph,
        tokens: List[str],
        stop_words: Set[str] = None,
        eps: str = "<eps>",
    ) -> Dict[str, Tuple[List[str], float]]:
        """Get FST paths and costs via BFS."""
        stop_words = stop_words or set()

        # node -> attrs
        n_data = intent_graph.nodes(data=True)

        # start state
        start_node = [n for n, data in n_data if data["start"]][0]

        # intent -> (symbols, cost)
        intent_symbols_and_costs: Dict[str, Tuple[List[str], float]] = {}

        # Lowest cost so far
        best_cost: float = len(n_data)

        # (node, in_tokens, out_tokens, cost, intent_name)
        q: List[Tuple[int, List[str], List[str], float, str]] = [
            (start_node, tokens, [], 0, "")
        ]

        # BFS it up
        while len(q) > 0:
            q_node, q_in_tokens, q_out_tokens, q_cost, q_intent = q.pop()

            # Update best intent cost on final state.
            # Don't bother reporting intents that failed to consume any tokens.
            if (n_data[q_node]["final"]) and (q_cost < len(tokens)):
                best_intent_cost = intent_symbols_and_costs.get(q_intent, (None, None))[
                    1
                ]
                final_cost: float = q_cost + len(
                    q_in_tokens
                )  # remaning tokens count against

                if (best_intent_cost is None) or (final_cost < best_intent_cost):
                    intent_symbols_and_costs[q_intent] = (q_out_tokens, final_cost)

                if final_cost < best_cost:
                    best_cost = final_cost

            if q_cost > best_cost:
                continue

            # Process child edges
            for next_node, edges in intent_graph[q_node].items():
                for edge_data in edges.values():
                    in_label = edge_data["in_label"]
                    out_label = edge_data["out_label"]
                    next_in_tokens = q_in_tokens[:]
                    next_out_tokens = q_out_tokens[:]
                    next_cost = q_cost
                    next_intent = q_intent

                    if out_label.startswith("__label__"):
                        next_intent = out_label[9:]

                    if in_label != eps:
                        if (len(next_in_tokens) > 0) and (
                            in_label == next_in_tokens[0]
                        ):
                            # Consume matching token immediately
                            next_in_tokens.pop(0)

                            if out_label != eps:
                                next_out_tokens.append(out_label)
                        else:
                            # Consume non-matching tokens and increase cost unless stop word
                            while (len(next_in_tokens) > 0) and (
                                in_label != next_in_tokens[0]
                            ):
                                bad_token = next_in_tokens.pop(0)
                                if bad_token not in stop_words:
                                    next_cost += 1
                                else:
                                    # Need a non-zero cost for stop words to
                                    # avoid case where two FST paths are
                                    # identical, save for stop words.
                                    next_cost += 0.1

                            if len(next_in_tokens) > 0:
                                # Consume matching token
                                next_in_tokens.pop(0)

                                if out_label != eps:
                                    next_out_tokens.append(out_label)
                            else:
                                # No matching token
                                continue
                    else:
                        # Consume epsilon
                        if out_label != eps:
                            next_out_tokens.append(out_label)

                    q.append(
                        (
                            next_node,
                            next_in_tokens,
                            next_out_tokens,
                            next_cost,
                            next_intent,
                        )
                    )

        return intent_symbols_and_costs

    # -------------------------------------------------------------------------

    @classmethod
    def _fst_to_graph(cls, the_fst: fst.Fst) -> nx.MultiDiGraph:
        """Convert a finite state transducer to a directed graph."""
        zero_weight = fst.Weight.Zero(the_fst.weight_type())
        in_symbols = the_fst.input_symbols()
        out_symbols = the_fst.output_symbols()

        g = nx.MultiDiGraph()

        # Add nodes
        for state in the_fst.states():
            # Mark final states
            is_final = the_fst.final(state) != zero_weight
            g.add_node(state, final=is_final, start=False)

            # Add edges
            for arc in the_fst.arcs(state):
                in_label = in_symbols.find(arc.ilabel).decode()
                out_label = out_symbols.find(arc.olabel).decode()

                g.add_edge(state, arc.nextstate, in_label=in_label, out_label=out_label)

        # Mark start state
        g.add_node(the_fst.start(), start=True)

        return g

    # -------------------------------------------------------------------------

    def load_fst(self):
        """Load intent FST."""
        if self.fst is None:
            fst_path = self.profile.read_path(
                self.profile.get("intent.fsticuffs.intent_fst", "intent.fst")
            )

            self.fst = fst.Fst.read(fst_path)

            # Add words from FST
            in_symbols = self.fst.input_symbols()
            self.words = set()
            for i in range(in_symbols.num_symbols()):
                key = in_symbols.get_nth_key(i)
                word = in_symbols.find(key).decode()
                self.words.add(word)

            # Convert to graph
            self.graph = FsticuffsRecognizer._fst_to_graph(self.fst)

            stop_words_path = self.profile.read_path("stop_words.txt")
            if os.path.exists(stop_words_path):
                self._logger.debug(f"Using stop words at {stop_words_path}")
                with open(stop_words_path, "r") as stop_words_file:
                    self.stop_words = {
                        line.strip()
                        for line in stop_words_file
                        if len(line.strip()) > 0
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

            intent["speech_confidence"] = message.confidence
            self.send(
                message.receiver or sender,
                IntentRecognized(intent, handle=message.handle),
            )

    # -------------------------------------------------------------------------

    def recognize(self, text: str) -> Dict[str, Any]:
        """Find sentence with lowest string-edit distance."""
        confidence = 0
        if len(text) > 0:
            assert self.examples is not None, "No examples JSON"

            choices: Dict[str, Tuple[str, Dict[str, Any]]] = {}
            with concurrent.futures.ProcessPoolExecutor() as executor:
                future_to_name = {}
                for intent_name, intent_examples in self.examples.items():
                    sentences = []
                    for example in intent_examples:
                        example_text = example.get("raw_text", example["text"])
                        logging.debug(example_text)
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

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        rasa_config = self.profile.get("intent.rasa", {})
        url = rasa_config.get("url", "http://localhost:5005")
        self.project_name = rasa_config.get(
            "project_name", "rhasspy_%s" % self.profile.name
        )
        self.parse_url = urljoin(url, "model/parse")

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, RecognizeIntent):
            try:
                intent = self.recognize(message.text)
                logging.debug(repr(intent))
            except Exception:
                self._logger.exception("in_started")
                intent = empty_intent()
                intent["text"] = message.text

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
# Flair Intent Recognizer
# https://github.com/zalandoresearch/flair
# -----------------------------------------------------------------------------


class FlairRecognizer(RhasspyActor):
    """Flair based recognizer"""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)

        try:
            from flair.models import TextClassifier, SequenceTagger
        except Exception:
            pass

        self.class_model: Optional[TextClassifier] = None
        self.ner_models: Optional[Dict[str, SequenceTagger]] = None
        self.intent_map: Optional[Dict[str, str]] = None
        self.preload = False

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        self.preload = self.config.get("preload", False)
        if self.preload:
            try:
                # Pre-load models
                self.load_models()
            except Exception as e:
                self._logger.warning("preload: %s", e)

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, RecognizeIntent):
            try:
                self.load_models()
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

    def recognize(self, text: str) -> Dict[str, Any]:
        """Run intent classifier and then named-entity recognizer."""
        from flair.data import Sentence

        intent = empty_intent()
        sentence = Sentence(text)

        assert self.intent_map is not None
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

        assert self.ner_models is not None
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
        """Load intent classifier and named entity recognizers."""
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
            self._logger.debug("Loading classification model from %s", class_model_path)
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
                            "%s was not found in intent map", intent_name
                        )

                    ner_model_path = os.path.join(ner_model_dir, "final-model.pt")
                    self._logger.debug("Loading NER model from %s", ner_model_path)
                    ner_models[intent_name] = SequenceTagger.load_from_file(
                        ner_model_path
                    )

            self._logger.debug("Loaded NER model(s)")
            self.ner_models = ner_models


# -----------------------------------------------------------------------------
# Home Assistant Conversation
# https://www.home-assistant.io/integrations/conversation
# -----------------------------------------------------------------------------


class HomeAssistantConversationRecognizer(RhasspyActor):
    """Use Home Assistant's conversation component."""

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.hass_config: Dict[str, Any] = {}
        self.pem_file: bool = ""
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

            intent["speech_confidence"] = message.confidence
            self.send(
                message.receiver or sender,
                IntentRecognized(intent, handle=message.handle),
            )
