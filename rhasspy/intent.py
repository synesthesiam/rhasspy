#!/usr/bin/env python3
import os
import sys
import json
import logging
import subprocess
from urllib.parse import urljoin
from typing import Dict, Any, Optional, Tuple, List

from thespian.actors import ActorAddress

from .actor import RhasspyActor
from .profiles import Profile
from .utils import empty_intent

# -----------------------------------------------------------------------------
# Events
# -----------------------------------------------------------------------------

class RecognizeIntent:
    def __init__(self, text: str,
                 receiver:Optional[ActorAddress]=None,
                 handle:bool=True):
        self.text = text
        self.receiver = receiver
        self.handle = handle

class IntentRecognized:
    def __init__(self,
                 intent: Dict[str, Any],
                 handle:bool=True):
        self.intent = intent
        self.handle = handle

# -----------------------------------------------------------------------------

class DummyIntentRecognizer(RhasspyActor):
    '''Always returns an empty intent'''
    def in_started(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, RecognizeIntent):
            intent = empty_intent()
            intent['text'] = message.text
            self.send(message.receiver or sender,
                      IntentRecognized(intent))

# -----------------------------------------------------------------------------
# Remote HTTP Intent Recognizer
# -----------------------------------------------------------------------------

class RemoteRecognizer(RhasspyActor):
    '''HTTP based recognizer for remote rhasspy server'''
    def to_started(self, from_state:str) -> None:
        self.remote_url = self.profile.get('intent.remote.url')

    def in_started(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, RecognizeIntent):
            try:
                intent = self.recognize(message.text)
            except Exception as e:
                self._logger.exception('in_started')
                intent = empty_intent()
                intent['text'] = message.text

            self.send(message.receiver or sender,
                      IntentRecognized(intent, handle=message.handle))

    # -------------------------------------------------------------------------

    def recognize(self, text: str) -> Dict[str, Any]:
        import requests

        params = { 'profile': self.profile.name, 'nohass': True }
        response = requests.post(self.remote_url, params=params, data=text)
        response.raise_for_status()

        return response.json()


# -----------------------------------------------------------------------------
# Fuzzywuzzy-based Intent Recognizer
# https://github.com/seatgeek/fuzzywuzzy
# -----------------------------------------------------------------------------

class FuzzyWuzzyRecognizer(RhasspyActor):
    '''Recognize intents using fuzzy string matching'''

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.examples: Optional[Dict[str, Any]] = None

    def to_started(self, from_state:str) -> None:
        self.load_examples()
        self.transition('loaded')

    def in_loaded(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, RecognizeIntent):
            try:
                self.load_examples()
                intent = self.recognize(message.text)
            except Exception as e:
                self._logger.exception('in_loaded')
                intent = empty_intent()

            self.send(message.receiver or sender,
                      IntentRecognized(intent, handle=message.handle))

    # -------------------------------------------------------------------------

    def recognize(self, text: str) -> Dict[str, Any]:
        if len(text) > 0:
            assert self.examples is not None, 'No examples JSON'
            from fuzzywuzzy import process

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
        intent = empty_intent()
        intent['text'] = text

        return intent

    # -------------------------------------------------------------------------

    def load_examples(self) -> None:
        if self.examples is None:
            '''Load JSON file with intent examples if not already cached'''
            examples_path = self.profile.read_path(
                self.profile.get('intent.fuzzywuzzy.examples_json'))

            if os.path.exists(examples_path):
                with open(examples_path, 'r') as examples_file:
                    self.examples = json.load(examples_file)

                self._logger.debug('Loaded examples from %s' % examples_path)


# -----------------------------------------------------------------------------
# RasaNLU Intent Recognizer (HTTP API)
# https://rasa.com/
# -----------------------------------------------------------------------------

class RasaIntentRecognizer(RhasspyActor):
    '''Uses rasaNLU HTTP API to recognize intents.'''
    def to_started(self, from_state:str) -> None:
        rasa_config = self.profile.get('intent.rasa', {})
        url = rasa_config.get('url', 'http://locahost:5000')
        self.project_name = rasa_config.get('project_name', 'rhasspy_%s' % self.profile.name)
        self.parse_url = urljoin(url, 'parse')

    def in_started(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, RecognizeIntent):
            try:
                intent = self.recognize(message.text)
            except Exception as e:
                self._logger.exception('in_started')
                intent = empty_intent()
                intent['text'] = message.text

            self.send(message.receiver or sender,
                      IntentRecognized(intent, handle=message.handle))

    # -------------------------------------------------------------------------

    def recognize(self, text: str) -> Dict[str, Any]:
        import requests

        response = requests.post(
            self.parse_url,
            json={ 'q': text, 'project': self.project_name })

        response.raise_for_status()

        return response.json()


# -----------------------------------------------------------------------------
# Mycroft Adapt Intent Recognizer
# http://github.com/MycroftAI/adapt
# -----------------------------------------------------------------------------

class AdaptIntentRecognizer(RhasspyActor):
    '''Recognize intents with Mycroft Adapt.'''

    def __init__(self) -> None:
        RhasspyActor.__init__(self)
        self.engine = None

    def to_started(self, from_state:str) -> None:
        self.load_engine()
        self.transition('loaded')

    def in_loaded(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, RecognizeIntent):
            try:
                self.load_engine()
                intent = self.recognize(message.text)
            except Exception as e:
                self._logger.exception('in_loaded')
                intent = empty_intent()

            self.send(message.receiver or sender,
                      IntentRecognized(intent, handle=message.handle))

    # -------------------------------------------------------------------------

    def recognize(self, text: str) -> Dict[str, Any]:
        # Get all intents
        assert self.engine is not None, 'Adapt engine not loaded'
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

    # -------------------------------------------------------------------------

    def load_engine(self) -> None:
        '''Configure Adapt engine if not already cached'''
        if self.engine is None:
            from adapt.intent import IntentBuilder
            from adapt.engine import IntentDeterminationEngine

            config_path = self.profile.read_path('adapt_config.json')
            if not os.path.exists(config_path):
                return

            # Create empty engine
            self.engine = IntentDeterminationEngine()
            assert self.engine is not None

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

            self._logger.debug('Loaded engine from config file %s' % config_path)

# -----------------------------------------------------------------------------
# Command Intent Recognizer
# -----------------------------------------------------------------------------

class CommandRecognizer(RhasspyActor):
    '''Command-line based recognizer'''
    def to_started(self, from_state:str) -> None:
        program = os.path.expandvars(self.profile.get('intent.command.program'))
        arguments = [os.path.expandvars(str(a))
                     for a in self.profile.get('intent.command.arguments', [])]

        self.command = [program] + arguments

    def in_started(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, RecognizeIntent):
            try:
                self._logger.debug(self.command)

                # Text -> STDIN -> STDOUT -> JSON
                output = subprocess.check_output(
                    self.command, input=message.text.encode()).decode()

                intent = json.loads(output)

            except Exception as e:
                self._logger.exception('in_started')
                intent = empty_intent()
                intent['text'] = message.text

            self.send(message.receiver or sender,
                      IntentRecognized(intent, handle=message.handle))
