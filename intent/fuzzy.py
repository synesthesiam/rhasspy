#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, os.path.abspath('..'))

import json

from thespian.actors import Actor

from profile import Profile

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
