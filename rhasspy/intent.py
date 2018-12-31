#!/usr/bin/env python3
import os
import sys
import json
import logging
from typing import Dict, Any, Optional

# from thespian.actors import Actor

from profile import Profile

# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class IntentRecognizer:
    def preload(self):
        pass

    def recognize(self, text: str) -> Dict[str, Any]:
        pass

    def train(self, sentences_by_intent: Dict[str, Any]):
        pass

# -----------------------------------------------------------------------------
# Fuzzywuzzy-based Intent Parser
# https://github.com/seatgeek/fuzzywuzzy
# -----------------------------------------------------------------------------

class FuzzyWuzzyRecognizer(IntentRecognizer):
    def __init__(self, profile: Profile):
        self.profile = profile
        self.examples: Optional[Dict[str, Any]] = None

    def preload(self):
        self._maybe_load_examples()

    # -------------------------------------------------------------------------

    def train(self, sentences_by_intent):
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
        examples_path = self.profile.write_path(
            self.profile.get('intent.fuzzywuzzy.examples_json'))

        with open(examples_path, 'w') as examples_file:
            json.dump(examples, examples_file, indent=4)

        logger.debug('Write fuzzywuzzy examples to %s' % examples_path)

    # -------------------------------------------------------------------------

    def recognize(self, text: str) -> Dict[str, Any]:
        from fuzzywuzzy import process

        self._maybe_load_examples()

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

    # -------------------------------------------------------------------------

    def _maybe_load_examples(self):
        if self.examples is None:
            examples_path = self.profile.read_path(
                self.profile.get('intent.fuzzywuzzy.examples_json'))

            assert os.path.exists(examples_path), 'No examples JSON'

            with open(examples_path, 'r') as examples_file:
                self.examples = json.load(examples_file)

            logger.debug('Loaded examples from %s' % examples_path)

# -----------------------------------------------------------------------------
# class FuzzyWuzzyIntentActor(Actor):
#     def __init__(self):
#         self.profile = None
#         self.examples = None

#     def receiveMessage(self, message, sender):
#         try:
#             if isinstance(message, Profile):
#                 self.profile = profile
#             if isinstance(message, TrainIntentRecognizer):
#                 self.train(message.sentences_by_intent)
#                 self.send(sender, IntentRecognizerTrained())
#             elif isinstance(message, RecognizeIntent):
#                 self.maybe_load_examples()
#                 intent = self.recognize(message.text)
#                 self.send(sender, IntentRecognized(intent))
#         except Exception as e:
#             logger.exception('receiveMessage')

    # -------------------------------------------------------------------------

