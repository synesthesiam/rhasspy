#!/usr/bin/env python3
import os
import sys
import json
import logging
from urllib.parse import urljoin
from typing import Dict, Any, Optional, Tuple, List

from profiles import Profile

# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class IntentRecognizer:
    '''Base class for intent recognizers'''

    def __init__(self, profile: Profile) -> None:
        self.profile = profile

    def preload(self):
        '''Cache anything useful upfront.'''
        pass

    def recognize(self, text: str) -> Dict[str, Any]:
        '''Recognize intent from text.'''
        pass

# -----------------------------------------------------------------------------
# Remote HTTP Intent Recognizer
# -----------------------------------------------------------------------------

class RemoteRecognizer(IntentRecognizer):
    '''HTTP based recognizer for remote rhasspy server'''

    def recognize(self, text:str) -> Dict[str, Any]:
        import requests

        remote_url = self.profile.get('intent.remote.url')
        params = { 'profile': self.profile.name, 'nohass': True }
        response = requests.post(remote_url, params=params, data=text)

        response.raise_for_status()

        return response.json()


# -----------------------------------------------------------------------------
# Fuzzywuzzy-based Intent Recognizer
# https://github.com/seatgeek/fuzzywuzzy
# -----------------------------------------------------------------------------

class FuzzyWuzzyRecognizer(IntentRecognizer):
    '''Recognize intents using fuzzy string matching'''

    def __init__(self, profile: Profile) -> None:
        IntentRecognizer.__init__(self, profile)
        self.examples: Optional[Dict[str, Any]] = None

    def preload(self):
        self._maybe_load_examples()

    # -------------------------------------------------------------------------

    def recognize(self, text: str) -> Dict[str, Any]:
        from fuzzywuzzy import process

        self._maybe_load_examples()
        assert self.examples is not None

        # sentence -> (sentence, intent, slots)
        choices: Dict[str, Tuple[str, str, Dict[str, List[str]]]] = {}
        for intent, intent_examples in self.examples.items():
            for example in intent_examples:
                example_text = example['text']
                choices[example_text] = (example_text, intent, example['slots'])

        # Find closest matching sentence
        best_text, best_score = process.extractOne(text, choices.keys())

        if best_text in choices:
            # (text, intent, slots)
            best_text, best_intent, best_slots = choices[best_text]

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

        # Empty intent
        return {
            'text': '',
            'intent': { 'name': '' },
            'entities': {}
        }

    # -------------------------------------------------------------------------

    def _maybe_load_examples(self):
        '''Load JSON file with intent examples if not already cached'''
        if self.examples is None:
            examples_path = self.profile.read_path(
                self.profile.get('intent.fuzzywuzzy.examples_json'))

            assert os.path.exists(examples_path), 'No examples JSON'

            with open(examples_path, 'r') as examples_file:
                self.examples = json.load(examples_file)

            logger.debug('Loaded examples from %s' % examples_path)


# -----------------------------------------------------------------------------
# RasaNLU Intent Recognizer (HTTP API)
# https://rasa.com/
# -----------------------------------------------------------------------------

class RasaIntentRecognizer(IntentRecognizer):
    '''Uses rasaNLU HTTP API to recognize intents.'''

    def recognize(self, text: str) -> Dict[str, Any]:
        import requests

        rasa_config = self.profile.get('intent.rasa', {})
        url = rasa_config.get('url', 'http://locahost:5000')
        project_name = rasa_config.get('project_name', 'rhasspy_%s' % self.profile.name)

        parse_url = urljoin(url, 'parse')
        response = requests.post(parse_url, json={ 'q': text, 'project': project_name })
        response.raise_for_status()

        return response.json()


# -----------------------------------------------------------------------------
# Mycroft Adapt Intent Recognizer
# http://github.com/MycroftAI/adapt
# -----------------------------------------------------------------------------

class AdaptIntentRecognizer(IntentRecognizer):
    '''Recognize intents with Mycroft Adapt.'''

    def __init__(self, profile: Profile) -> None:
        IntentRecognizer.__init__(self, profile)
        self.engine = None

    def preload(self):
        self._maybe_load_engine()

    # -------------------------------------------------------------------------

    def recognize(self, text: str) -> Dict[str, Any]:
        self._maybe_load_engine()
        assert self.engine is not None

        try:
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
                        { 'entity': name, 'value': value } for name, value in slots.items()
                    ]
                }
        except Exception as e:
            logger.exception('adapt recognize')

        # Empty intent
        return {
            'text': '',
            'intent': { 'name': '' },
            'entities': []
        }

    # -------------------------------------------------------------------------

    def _maybe_load_engine(self):
        '''Configure Adapt engine if not already cached'''
        if self.engine is None:
            from adapt.intent import IntentBuilder
            from adapt.engine import IntentDeterminationEngine

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

            logger.debug('Loaded engine from config file %s' % config_path)
