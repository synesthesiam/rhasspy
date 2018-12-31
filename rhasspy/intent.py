#!/usr/bin/env python3
import os
import sys
import json
import logging
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
# Fuzzywuzzy-based Intent Parser
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
