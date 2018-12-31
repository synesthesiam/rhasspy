import os
import json
import logging
import tempfile
import re
from urllib.parse import urljoin
from collections import defaultdict, Counter
from typing import Dict, List, Set, Any

from stt_train import SpeechTrainer

# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class IntentTrainer:
    def __init__(self, profile) -> None:
        self.profile = profile

    def train(self,
              tagged_sentences: Dict[str, List[str]],
              sentences_by_intent: SpeechTrainer.SBI_TYPE):
        '''Trains an intent recognizer uses tagged sentences with
        Markdown-style entites (grouped by intent).

        Also provided are the same sentences, grouped by intent,
        sanitized and tokenized (see stt_train).'''
        pass

# -----------------------------------------------------------------------------
# Fuzzywuzzy-based Intent Trainer
# https://github.com/seatgeek/fuzzywuzzy
# -----------------------------------------------------------------------------

class FuzzyWuzzyIntentTrainer(IntentTrainer):
    '''Save examples to JSON for fuzzy string matching later.'''

    def train(self,
              tagged_sentences: Dict[str, List[str]],
              sentences_by_intent: SpeechTrainer.SBI_TYPE):

        examples_path = self.profile.write_path(
            self.profile.get('intent.fuzzywuzzy.examples_json'))

        examples = self._make_examples(sentences_by_intent)
        with open(examples_path, 'w') as examples_file:
            json.dump(examples, examples_file, indent=4)

        logger.debug('Wrote intent examples to %s' % examples_path)

    # -------------------------------------------------------------------------

    def _make_examples(self, sentences_by_intent: SpeechTrainer.SBI_TYPE) -> Dict[str, Any]:
        '''Write intent examples to a JSON file.'''
        from fuzzywuzzy import process

        # { intent: [ { 'text': ..., 'slots': { ... } }, ... ] }
        examples: Dict[str, Any] = defaultdict(list)

        for intent, intent_sents in sentences_by_intent.items():
            for sentence, entities, tokens in intent_sents:
                slots: Dict[str, List[str]] = defaultdict(list)
                for entity, value in entities:
                    slots[entity].append(value)

                examples[intent].append({ 'text': sentence,
                                          'slots': slots })

        return examples


# -----------------------------------------------------------------------------
# RasaNLU Intent Trainer (HTTP API)
# https://rasa.com/
# -----------------------------------------------------------------------------

class RasaIntentTrainer(IntentTrainer):
    '''Uses rasaNLU HTTP API to train a recognizer.'''

    def train(self,
              tagged_sentences: Dict[str, List[str]],
              sentences_by_intent: SpeechTrainer.SBI_TYPE):

        import requests

        # Load settings
        language = self.profile.get('language', 'en')
        rasa_config = self.profile.get('intent.rasa', {})

        url = rasa_config.get('url', 'http://locahost:5000')
        project_name = rasa_config.get('project_name', 'rhasspy')

        # Create markdown examples
        examples_md_path = self.profile.write_path(
            rasa_config.get('examples_markdown', 'intent_examples.md'))

        with open(examples_md_path, 'w') as examples_md_file:
            for intent_name, intent_sents in tagged_sentences.items():
                # Rasa Markdown training format
                print('## intent:%s' % intent_name, file=examples_md_file)
                for sentence in intent_sents:
                    print('-', sentence, file=examples_md_file)

                print('', file=examples_md_file)

        # Create training YAML file
        with tempfile.NamedTemporaryFile(suffix='.yml', mode='w+', delete=False) as training_file:
            print('language: "%s"\n' % language, file=training_file)
            print('pipeline: "spacy_sklearn"\n', file=training_file)
            print('data: |', file=training_file)

            # Write markdown directly into YAML.
            # Because reasons.
            with open(examples_md_path, 'r') as examples_md_file:
                blank_line = False
                for line in examples_md_file:
                    line = line.strip()
                    if len(line) > 0:
                        if blank_line:
                            print('', file=training_file)
                            blank_line = False

                        print('  %s' % line, file=training_file)
                    else:
                        blank_line = True

            # Do training via HTTP API
            training_url = urljoin(url, 'train')
            training_file.seek(0)
            training_data = open(training_file.name, 'rb').read()
            response = requests.post(training_url,
                                     data=training_data,
                                     params={ 'project': project_name },
                                     headers={ 'Content-Type': 'application/x-yml' })

            logger.debug('POSTed %s byte(s) to %s' % (len(training_data), training_url))
            response.raise_for_status()


# -----------------------------------------------------------------------------
# Mycroft Adapt Intent Trainer
# http://github.com/MycroftAI/adapt
# -----------------------------------------------------------------------------

class AdaptIntentTrainer(IntentTrainer):
    '''Configure a Mycroft Adapt engine.'''

    def train(self,
              tagged_sentences: Dict[str, List[str]],
              sentences_by_intent: SpeechTrainer.SBI_TYPE):

        # Load "stop" words (common words that are excluded from training)
        stop_words: Set[str] = set()
        stop_words_path = self.profile.read_path('stop_words.txt')
        if os.path.exists(stop_words_path):
            with open(stop_words_path, 'r') as stop_words_file:
                stop_words = set([line.strip() for line in stop_words_file
                                  if len(line.strip()) > 0])

        # Generate intent configuration
        entities: Dict[str, Set[str]] = {}
        intents: Dict[str, Dict[str, Any]] = {}

        for intent_name, intent_sents in sentences_by_intent.items():
            intent = {
                'name': intent_name,
                'require': [],
                'optionally': []
            }

            # Track word usage by sentence to determine required vs. optional words
            word_counts: Dict[str, int] = Counter()
            entity_counts: Dict[str, int] = Counter()

            # Process sentences for this intent
            for sentence, slots, word_tokens in intent_sents:
                entity_tokens: Set[str] = set()

                # Group slot values by entity
                slot_entities: Dict[str, List[str]] = defaultdict(list)
                for entity_name, entity_value in slots:
                    slot_entities[entity_name].append(entity_value)

                # Add entities
                for entity_name, entity_values in slot_entities.items():
                    # Prefix entity name with intent name
                    entity_name = '{0}.{1}'.format(intent_name, entity_name)
                    if not entity_name in entities:
                        entities[entity_name] = set()

                    entities[entity_name].update(entity_values)
                    entity_counts[entity_name] += 1

                    # Split entity values by whitespace
                    for value in entity_values:
                        entity_tokens.update(re.split(r'\s', value))

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
                assert count <= num_sentences, 'Invalid word count'
                if count == num_sentences:
                    # Word exists in all sentences
                    required_words.add(word)
                else:
                    # Word only exists in some sentences
                    optional_words.add(word)

            if len(required_words) > 0:
                # Create entity for required keywords
                entity_name = '{0}RequiredKeyword'.format(intent_name)
                entities[entity_name] = required_words
                intent['require'].append(entity_name)

            if len(optional_words) > 0:
                # Create entity for required keywords
                entity_name = '{0}OptionalKeyword'.format(intent_name)
                entities[entity_name] = optional_words
                intent['optionally'].append(entity_name)

            # Add required/optional entities
            for name, count in entity_counts.items():
                assert count <= num_sentences, 'Invalid entity count'
                if count == num_sentences:
                    # Entity exists in all sentences
                    intent['require'].append(name)
                else:
                    # Entity only exists in some sentences
                    intent['optionally'].append(name)

            intents[intent_name] = intent

        # ---------------------------------------------------------------------

        # Write configuration file
        config = {
            'intents': intents,

            # Convert sets to lists because JSON serializer is super whiny
            'entities': { name: list(values)
                          for name, values in entities.items() }
        }

        config_path = self.profile.write_path('adapt_config.json')
        with open(config_path, 'w') as config_file:
            json.dump(config, config_file, indent=4)

        logger.debug('Wrote adapt configuration to %s' % config_path)
