"""Training for intent recognizers."""
import json
import os
import subprocess
import tempfile
from collections import Counter, defaultdict
from io import StringIO
from typing import Any, Callable, Dict, List, Set, Type
from urllib.parse import urljoin

from rhasspy.actor import RhasspyActor
from rhasspy.events import IntentTrainingComplete, IntentTrainingFailed, TrainIntent
from rhasspy.utils import make_sentences_by_intent, load_converters

# -----------------------------------------------------------------------------


def get_intent_trainer_class(
    trainer_system: str, recognizer_system: str = "dummy"
) -> Type[RhasspyActor]:
    """Get type for profile intent trainer."""

    assert trainer_system in [
        "dummy",
        "fsticuffs",
        "fuzzywuzzy",
        "adapt",
        "rasa",
        "auto",
        "command",
    ], f"Invalid intent training system: {trainer_system}"

    if trainer_system == "auto":
        # Use intent recognizer system
        if recognizer_system == "fsticuffs":
            # Use OpenFST acceptor locally
            return FsticuffsIntentTrainer
        if recognizer_system == "fuzzywuzzy":
            # Use fuzzy string matching locally
            return FuzzyWuzzyIntentTrainer
        if recognizer_system == "adapt":
            # Use Mycroft Adapt locally
            return AdaptIntentTrainer
        if recognizer_system == "rasa":
            # Use Rasa NLU remotely
            return RasaIntentTrainer
        if recognizer_system == "command":
            # Use command-line intent trainer
            return CommandIntentTrainer
    if trainer_system == "fsticuffs":
        # Use OpenFST acceptor locally
        return FsticuffsIntentTrainer
    if trainer_system == "fuzzywuzzy":
        # Use fuzzy string matching locally
        return FuzzyWuzzyIntentTrainer
    if trainer_system == "adapt":
        # Use Mycroft Adapt locally
        return AdaptIntentTrainer
    if trainer_system == "rasa":
        # Use Rasa NLU remotely
        return RasaIntentTrainer
    if trainer_system == "command":
        # Use command-line intent trainer
        return CommandIntentTrainer

    return DummyIntentTrainer


# -----------------------------------------------------------------------------


class DummyIntentTrainer(RhasspyActor):
    """Always reports successful training."""

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, TrainIntent):
            self.send(message.receiver or sender, IntentTrainingComplete())


# -----------------------------------------------------------------------------
# OpenFST-based intent recognizer
# https://www.openfst.org
# -----------------------------------------------------------------------------


class FsticuffsIntentTrainer(DummyIntentTrainer):
    """No training needed. Intent graph will be used directly during recognition."""

    pass


# -----------------------------------------------------------------------------
# Fuzzywuzzy-based Intent Trainer
# https://github.com/seatgeek/fuzzywuzzy
# -----------------------------------------------------------------------------


class FuzzyWuzzyIntentTrainer(RhasspyActor):
    """Save examples to JSON for fuzzy string matching later."""

    def __init__(self):
        RhasspyActor.__init__(self)
        self.converters: Dict[str, Callable[..., Any]] = {}

    def to_started(self, from_state: str) -> None:
        # Load user-defined converters
        self.converters = load_converters(self.profile)

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, TrainIntent):
            try:
                self.train(message.intent_graph)
                self.send(message.receiver or sender, IntentTrainingComplete())
            except Exception as e:
                self._logger.exception("train")
                self.send(message.receiver or sender, IntentTrainingFailed(repr(e)))

    def train(self, intent_graph) -> None:
        """Save examples to JSON file."""
        examples_path = self.profile.write_path(
            self.profile.get("intent.fuzzywuzzy.examples_json")
        )

        sentences_by_intent = make_sentences_by_intent(
            intent_graph, extra_converters=self.converters
        )
        with open(examples_path, "w") as examples_file:
            json.dump(sentences_by_intent, examples_file, indent=4)

        self._logger.debug("Wrote intent examples to %s", examples_path)


# -----------------------------------------------------------------------------
# Rasa NLU Intent Trainer (HTTP API)
# https://rasa.com/
# -----------------------------------------------------------------------------


class RasaIntentTrainer(RhasspyActor):
    """Uses Rasa NLU HTTP API to train a recognizer."""

    def __init__(self):
        RhasspyActor.__init__(self)
        self.converters: Dict[str, Callable[..., Any]] = {}

    def to_started(self, from_state: str) -> None:
        # Load user-defined converters
        self.converters = load_converters(self.profile)

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, TrainIntent):
            try:
                self.train(message.intent_graph)
                self.send(message.receiver or sender, IntentTrainingComplete())
            except Exception as e:
                self._logger.exception("train")
                self.send(message.receiver or sender, IntentTrainingFailed(repr(e)))

    # -------------------------------------------------------------------------

    def train(self, intent_graph) -> None:
        """Convert examples to Markdown and POST to RasaNLU server."""
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
        sentences_by_intent = make_sentences_by_intent(
            intent_graph, extra_converters=self.converters
        )

        # Write to YAML/Markdown file
        with open(examples_md_path, "w") as examples_md_file:
            for intent_name, intent_sents in sentences_by_intent.items():
                # Rasa Markdown training format
                print(f"## intent:{intent_name}", file=examples_md_file)
                for intent_sent in intent_sents:
                    raw_index = 0
                    index_entity = {e["raw_start"]: e for e in intent_sent["entities"]}
                    entity = None
                    sentence_tokens = []
                    entity_tokens = []
                    for raw_token in intent_sent["raw_tokens"]:
                        token = raw_token
                        if entity and (raw_index >= entity["raw_end"]):
                            # Finish current entity
                            last_token = entity_tokens[-1]
                            entity_tokens[-1] = f"{last_token}]({entity['entity']})"
                            sentence_tokens.extend(entity_tokens)
                            entity = None
                            entity_tokens = []

                        new_entity = index_entity.get(raw_index)
                        if new_entity:
                            # Begin new entity
                            assert entity is None, "Unclosed entity"
                            entity = new_entity
                            entity_tokens = []
                            token = f"[{token}"

                        if entity:
                            # Add to current entity
                            entity_tokens.append(token)
                        else:
                            # Add directly to sentence
                            sentence_tokens.append(token)

                        raw_index += len(raw_token) + 1

                    if entity:
                        # Finish final entity
                        last_token = entity_tokens[-1]
                        entity_tokens[-1] = f"{last_token}]({entity['entity']})"
                        sentence_tokens.extend(entity_tokens)

                    # Print single example
                    print("-", " ".join(sentence_tokens), file=examples_md_file)

                # Newline between intents
                print("", file=examples_md_file)

        # Create training YAML file
        with tempfile.NamedTemporaryFile(
            suffix=".json", mode="w+", delete=False
        ) as training_file:

            training_config = StringIO()
            training_config.write(f'language: "{language}"\n')
            training_config.write('pipeline: "pretrained_embeddings_spacy"\n')

            # Write markdown directly into YAML.
            # Because reasons.
            with open(examples_md_path, "r") as examples_md_file:
                blank_line = False
                for line in examples_md_file:
                    line = line.strip()
                    if line:
                        if blank_line:
                            print("", file=training_file)
                            blank_line = False

                        print(f"  {line}", file=training_file)
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

            self._logger.debug("POSTed training data to %s", training_url)

            try:
                response.raise_for_status()

                model_dir = rasa_config.get("model_dir", "")
                model_file = os.path.join(model_dir, response.headers["filename"])
                self._logger.debug("Received model %s", model_file)

                # Replace model
                model_url = urljoin(url, "model")
                requests.put(model_url, json={"model_file": model_file})
            except Exception:
                # Rasa gives quite helpful error messages, so extract them from the response.
                raise Exception(
                    f'{response.reason}: {json.loads(response.content)["message"]}'
                )


# -----------------------------------------------------------------------------
# Mycroft Adapt Intent Trainer
# http://github.com/MycroftAI/adapt
# -----------------------------------------------------------------------------


class AdaptIntentTrainer(RhasspyActor):
    """Configure a Mycroft Adapt engine."""

    def __init__(self):
        RhasspyActor.__init__(self)
        self.converters: Dict[str, Callable[..., Any]] = {}

    def to_started(self, from_state: str) -> None:
        # Load user-defined converters
        self.converters = load_converters(self.profile)

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, TrainIntent):
            try:
                self.train(message.intent_graph)
                self.send(message.receiver or sender, IntentTrainingComplete())
            except Exception as e:
                self._logger.exception("train")
                self.send(message.receiver or sender, IntentTrainingFailed(repr(e)))

    # -------------------------------------------------------------------------

    def train(self, intent_graph) -> None:
        """Create intents, entities, and keywords."""
        # Load "stop" words (common words that are excluded from training)
        stop_words: Set[str] = set()
        stop_words_path = self.profile.read_path("stop_words.txt")
        if os.path.exists(stop_words_path):
            with open(stop_words_path, "r") as stop_words_file:
                stop_words = {line.strip() for line in stop_words_file if line.strip()}

        # { intent: [ { 'text': ..., 'entities': { ... } }, ... ] }
        sentences_by_intent = make_sentences_by_intent(
            intent_graph, extra_converters=self.converters
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
                entity_tokens: Set[str] = set()

                # Group slot values by entity
                slot_entities: Dict[str, List[str]] = defaultdict(list)
                for sent_ent in intent_sent["entities"]:
                    slot_entities[sent_ent["entity"]].append(sent_ent["raw_value"])

                # Add entities
                for entity_name, entity_values in slot_entities.items():
                    # Prefix entity name with intent name
                    entity_name = f"{intent_name}.{entity_name}"
                    if entity_name not in entities:
                        entities[entity_name] = set()

                    entities[entity_name].update(entity_values)
                    entity_counts[entity_name] += 1

                    # Split entity values by whitespace
                    for value in entity_values:
                        entity_tokens.update(value.split())

                # Get all non-stop words that are not part of entity values
                words = set(intent_sent["raw_tokens"]) - entity_tokens - stop_words

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

            if required_words:
                # Create entity for required keywords
                entity_name = f"{intent_name}RequiredKeyword"
                entities[entity_name] = required_words
                intent["require"].append(entity_name)

            if optional_words:
                # Create entity for required keywords
                entity_name = f"{intent_name}OptionalKeyword"
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

        self._logger.debug("Wrote adapt configuration to %s", config_path)


# -----------------------------------------------------------------------------
# Command-line Based Intent Trainer
# -----------------------------------------------------------------------------


class CommandIntentTrainer(RhasspyActor):
    """Calls out to a command-line program to do intent system training."""

    def __init__(self):
        RhasspyActor.__init__(self)
        self.command: List[str] = []
        self.converters: Dict[str, Callable[..., Any]] = {}

    def to_started(self, from_state: str) -> None:
        """Transition to started state."""
        program = os.path.expandvars(
            self.profile.get("training.intent.command.program")
        )
        arguments = [
            os.path.expandvars(str(a))
            for a in self.profile.get("training.intent.command.arguments", [])
        ]

        # Load user-defined converters
        self.converters = load_converters(self.profile)

        self.command = [program] + arguments

    def in_started(self, message: Any, sender: RhasspyActor) -> None:
        """Handle messages in started state."""
        if isinstance(message, TrainIntent):
            try:
                self.train(message.intent_fst)
                self.send(message.receiver or sender, IntentTrainingComplete())
            except Exception as e:
                self._logger.exception("train")
                self.send(message.receiver or sender, IntentTrainingFailed(repr(e)))

    def train(self, intent_fst) -> None:
        """Run external trainer."""
        try:
            self._logger.debug(self.command)

            # { intent: [ { 'text': ..., 'entities': { ... } }, ... ] }
            sentences_by_intent = make_sentences_by_intent(intent_fst)
            json_sentences = {
                intent: [r.asdict() for r in sentences_by_intent[intent]]
                for intent in sentences_by_intent
            }

            # JSON -> STDIN
            json_input = json.dumps(json_sentences).encode()

            subprocess.run(self.command, input=json_input, check=True)
        except Exception:
            self._logger.exception("train")
