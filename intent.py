#!/usr/bin/env python3
import os
import re
import json
import logging
import tempfile
from collections import Counter, defaultdict
from urllib.parse import urljoin

logging.basicConfig(level=logging.DEBUG)

import requests
from thespian.actors import Actor, ActorSystem

from profiles import Profile

# -----------------------------------------------------------------------------

class TrainIntentRecognizer:
    def __init__(self, sentences_by_intent):
        self.sentences_by_intent = sentences_by_intent

class IntentRecognizerTrained:
    pass

class RecognizeIntent:
    def __init__(self, text):
        self.text = text

class IntentRecognized:
    def __init__(self, intent):
        self.intent = intent

# -----------------------------------------------------------------------------
# Fuzzywuzzy-based Intent Parser
# https://github.com/seatgeek/fuzzywuzzy
# -----------------------------------------------------------------------------

class FuzzyWuzzyIntentActor(Actor):
    def __init__(self):
        self.profile = None
        self.examples = None

    def receiveMessage(self, message, sender):
        try:
            if isinstance(message, Profile):
                self.profile = profile
            if isinstance(message, TrainIntentRecognizer):
                self.train(message.sentences_by_intent)
                self.send(sender, IntentRecognizerTrained())
            elif isinstance(message, RecognizeIntent):
                self.maybe_load_examples()
                intent = self.recognize(message.text)
                self.send(sender, IntentRecognized(intent))
        except Exception as e:
            logging.exception('receiveMessage')

    # -------------------------------------------------------------------------

    def train(self, sentences_by_intent):
        assert self.profile is not None, 'No profile'
        from fuzzywuzzy import process

        # { intent: [ { 'text': ..., 'slots': { ... } }, ... ] }
        examples = defaultdict(list)

        for intent, intent_sents in sentences_by_intent.items():
            for tagged, sentence, entities, tokens in intent_sents:
                slots = defaultdict(list)
                for entity, value in entities.items():
                    slots[entity].append(value)

                examples[intent].append({
                    'text': sentence,
                    'slots': slots
                })

        # Write examples JSON file
        fuzzy_config = profile.intent.get('fuzzywuzzy', {})
        examples_path = profile.write_path(fuzzy_config.get('examples_json', 'intent_examples_json'))

        with open(examples_path, 'w') as examples_file:
            json.dump(examples, examples_file, indent=4)

        logging.debug('Write fuzzywuzzy examples to %s' % examples_path)

    # -------------------------------------------------------------------------

    def maybe_load_examples(self):
        assert self.profile is not None, 'No profile'

        fuzzy_config = profile.intent.get('fuzzywuzzy', {})
        examples_path = profile.read_path(fuzzy_config.get('examples_json', 'intent_examples_json'))
        assert os.path.exists(examples_path), 'No examples JSON'

        with open(examples_path, 'r') as examples_file:
            self.examples = json.load(examples_file)

        logging.debug('Loaded examples from %s' % examples_path)

    # -------------------------------------------------------------------------

    def recognize(self, text):
        assert self.examples is not None, 'No examples'
        from fuzzywuzzy import process

        # sentence -> (sentence, intent, slots)
        choices = {}
        for intent, intent_examples in self.examples.items():
            for example in intent_examples:
                example_text = example['text']
                choices[example_text] = (example_text, intent, example['slots'])

        # Find closest matching sentence
        best_text, best_score = process.extractOne(text, choices.keys())

        # (text, intent, slots)
        best_text, best_intent, best_slots = choices.get(best_text)

        # Try to match RasaNLU format for future compatibility
        confidence = best_score / 100
        return {
            'text': best_text,
            'intent': {
                'name': best_intent,
                'confidence': confidence
            },
            'entities': [
                { 'entity': name, 'value': values[0] }
                for name, values in best_slots.items()
            ]
        }

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

# -----------------------------------------------------------------------------
# RasaNLU Intent Recognizer
# https://rasa.com/
# -----------------------------------------------------------------------------

class RasaIntentActor(Actor):
    def __init__(self):
        self.profile = None

    def receiveMessage(self, message, sender):
        try:
            if isinstance(message, Profile):
                self.profile = profile
            if isinstance(message, TrainIntentRecognizer):
                self.train(message.sentences_by_intent)
                self.send(sender, IntentRecognizerTrained())
            elif isinstance(message, RecognizeIntent):
                intent = self.recognize(message.text)
                self.send(sender, IntentRecognized(intent))
        except Exception as e:
            logging.exception('receiveMessage')

    # -------------------------------------------------------------------------

    def train(self, sentences_by_intent):
        assert self.profile is not None

        # Load settings
        language = self.profile.json.get('language', 'en')
        rasa_config = self.profile.intent.get('rasa', {})
        url = rasa_config.get('url', 'http://locahost:5000')
        project_name = rasa_config.get('project_name', 'rhasspy')

        # Create markdown examples
        examples_md_path = self.profile.write_path(
            rasa_config.get('examples_markdown', 'intent_examples.md'))

        with open(examples_md_path, 'w') as examples_md_file:
            for intent_name, intent_sents in sentences_by_intent.items():
                # Rasa Markdown training format
                print('## intent:%s' % intent_name, file=examples_md_file)
                for tagged, sentence, slots, tokens in intent_sents:
                    print('-', tagged, file=examples_md_file)

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

            logging.debug('POSTed %s byte(s) to %s' % (len(training_data), training_url))
            response.raise_for_status()

    # -------------------------------------------------------------------------

    def recognize(self, text):
        assert self.profile is not None
        rasa_config = self.profile.intent.get('rasa', {})
        url = rasa_config.get('url', 'http://locahost:5000')
        project_name = rasa_config.get('project_name', 'rhasspy')

        parse_url = urljoin(url, 'parse')
        response = requests.post(parse_url, json={ 'q': text, 'project': project_name })
        response.raise_for_status()

        return response.json()

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

if __name__ == '__main__':
    sentences_by_intent = {
        'GetTime': [
            ('tell me the time', 'tell me the time', {}, ['tell', 'me', 'the', 'time']),
            ('what time is it', 'what time is it', {}, ['what', 'time', 'is', 'it']),
            ('what time is it', 'what is the time', {}, ['what', 'is', 'the', 'time'])
        ],

        'ChangeLightColor': [
            ('set the [bedroom light](name) to [red](color)',
             'set the bedroom light to red',
             { 'name': ['bedroom light'], 'color': ['red'] },
             ['set', 'the', 'bedroom', 'light', 'to', 'red']),

            ('make the [bedroom light](name) [green](color)',
             'make the bedroom light green',
             { 'name': ['bedroom light'], 'color': ['green'] },
             ['make', 'the', 'bedroom', 'light', 'green']),

            ('turn the [kitchen light](name) to [blue](color)',
             'turn the kitchen light to blue',
             { 'name': ['kitchen light'], 'color': ['blue'] },
             ['turn', 'the', 'kitchen', 'light', 'blue'])
        ]
    }

    profile = Profile('en', ['profiles'])

    # Start actor system
    system = ActorSystem('multiprocQueueBase')

    try:
        # Test FuzzyWuzzy
        fuzzy_actor = system.createActor(FuzzyWuzzyIntentActor)

        # Load profile
        system.tell(fuzzy_actor, profile)

        # Train
        system.ask(fuzzy_actor, TrainIntentRecognizer(sentences_by_intent))

        # Recognize
        result = system.ask(fuzzy_actor, RecognizeIntent('what is the current time'))
        assert result.intent['intent']['name'] == 'GetTime'
        print(result.intent)

        result = system.ask(fuzzy_actor, RecognizeIntent('please set the bedroom light to blue'))
        assert result.intent['intent']['name'] == 'ChangeLightColor'
        print(result.intent)

        # ---------------------------------------------------------------------

        # Test Mycroft Adapt
        adapt_actor = system.createActor(AdaptIntentActor)

        # Load profile
        system.tell(adapt_actor, profile)

        # Train
        system.ask(adapt_actor, TrainIntentRecognizer(sentences_by_intent))

        # Recognize
        result = system.ask(adapt_actor, RecognizeIntent('what is the current time'))
        assert result.intent['intent']['name'] == 'GetTime'
        print(result.intent)

        result = system.ask(adapt_actor, RecognizeIntent('please set the bedroom light to blue'))
        assert result.intent['intent']['name'] == 'ChangeLightColor'
        print(result.intent)

        # ---------------------------------------------------------------------
        # rasa_actor = system.createActor(RasaIntentActor)

        # # Load profile
        # system.tell(rasa_actor, profile)

        # # Train
        # system.ask(rasa_actor, TrainIntentRecognizer(sentences_by_intent))

        # # Recognize
        # result = system.ask(rasa_actor, RecognizeIntent('what is the current time'))
        # assert result.intent['intent']['name'] == 'GetTime'
        # print(result.intent)

        # result = system.ask(rasa_actor, RecognizeIntent('please set the bedroom light to blue'))
        # assert result.intent['intent']['name'] == 'ChangeLightColor'
        # print(result.intent)
    finally:
        # Shut down actor system
        system.shutdown()
