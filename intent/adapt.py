#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, os.path.abspath('..'))

import json
import logging

from thespian.actors import Actor

from profile import Profile

# -----------------------------------------------------------------------------
# Mycroft Adapt Intent Parser
# http://github.com/MycroftAI/adapt
# -----------------------------------------------------------------------------

class AdaptIntentActor(Actor):
    def __init__(self):
        self.profile = None
        self.engine = None

    def receiveMessage(self, message, sender):
        try:
            if isinstance(message, Profile):
                self.profile = profile
            if isinstance(message, TrainIntentRecognizer):
                self.train(message.sentences_by_intent)
                self.send(sender, IntentRecognizerTrained())
            elif isinstance(message, RecognizeIntent):
                self.maybe_load_engine()
                intent = self.recognize(message.text)
                self.send(sender, IntentRecognized(intent))
        except Exception as e:
            logging.exception('receiveMessage')

    # -------------------------------------------------------------------------

    def train(self, sentences_by_intent):
        assert self.profile is not None, 'No profile'

        # Load "stop" words (common words that are excluded from training)
        stop_words = set()
        stop_words_path = self.profile.read_path('stop_words.txt')
        if os.path.exists(stop_words_path):
            with open(stop_words_path, 'r') as stop_words_file:
                stop_words = set([line.strip() for line in stop_words_file
                                  if len(line.strip()) > 0])

        # Generate intent configuration
        entities = {}
        intents = {}

        for intent_name, intent_sents in sentences_by_intent.items():
            intent = {
                'name': intent_name,
                'require': [],
                'optionally': []
            }

            # Track word usage by sentence to determine required vs. optional words
            word_counts = Counter()
            entity_counts = Counter()

            # Process sentences for this intent
            for tagged, sentence, slots, word_tokens in intent_sents:
                entity_tokens = set()

                # Add entities
                for entity_name, entity_values in slots.items():
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

        logging.debug('Wrote adapt configuration to %s' % config_path)

        # Will reload engine before next recognition
        self.engine = None

    # -------------------------------------------------------------------------

    def maybe_load_engine(self):
        from adapt.intent import IntentBuilder
        from adapt.engine import IntentDeterminationEngine

        if self.engine is None:
            assert self.profile is not None, 'No profile'
            config_path = self.profile.read_path('adapt_config.json')
            assert os.path.exists(config_path), 'Configuration file missing. Need to train.'

            # Create empty engine
            self.engine = IntentDeterminationEngine()

            # { intents: { ... }, entities: { ... } }
            with open(config_path, 'r') as config_file:
                config = json.load(config_file)

            # Register entities
            for entity_name, entity_values in config['entities'].items():
                for value in entity_values:
                    self.engine.register_entity(value, entity_name)

            # Register intents
            for intent_name, intent_config in config['intents'].items():
                intent = IntentBuilder(intent_name)
                for required_entity in intent_config['require']:
                    intent.require(required_entity)

                for optional_entity in intent_config['optionally']:
                    intent.optionally(optional_entity)

                self.engine.register_intent_parser(intent.build())

            logging.debug('Loaded engine from config file %s' % config_path)

    # -------------------------------------------------------------------------

    def recognize(self, text):
        assert self.engine is not None, 'No engine'

        # Get all intents
        intents =  [intent for intent in
                    self.engine.determine_intent(text)
                    if intent]

        if len(intents) > 0:
            # Return the best intent only
            intent = max(intents, key=lambda x: x.get('confidence', 0))
            intent_type = intent['intent_type']
            entity_prefix = '{0}.'.format(intent_type)

            slots = {}
            for key, value in intent.items():
                if key.startswith(entity_prefix):
                    key = key[len(entity_prefix):]
                    slots[key] = value

            # Try to match RasaNLU format for future compatibility
            return {
                'text': text,
                'intent': {
                    'name': intent_type,
                    'confidence': intent.get('confidence', 0)
                },
                'entities': [
                    { name: value } for name, value in slots.items()
                ]
            }

        # Empty intent
        return {
            'text': '',
            'intent': {},
            'entities': []
        }
