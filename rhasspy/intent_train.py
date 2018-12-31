import os
import json
import logging
from collections import defaultdict
from typing import Dict, List

# -----------------------------------------------------------------------------

class IntentTrainer:
    def train(self, tagged_sentences: Dict[str, List[str]]):
        pass

# -----------------------------------------------------------------------------

class FuzzyWuzzyIntentTrainer:
    def __init__(self, profile):
        self.profile = profile

    def train(self,
              tagged_sentences: Dict[str, List[str]],
              sentences_by_intent):

        examples_path = self.profile.write_path(
            self.profile.get('intent.fuzzywuzzy.examples_json'))

        examples = self._make_examples(sentences_by_intent)
        with open(examples_path, 'w') as examples_file:
            json.dump(examples, examples_file, indent=4)

        logging.debug('Wrote intent examples to %s' % examples_path)

    # -------------------------------------------------------------------------

    def _make_examples(self, sentences_by_intent):
        from fuzzywuzzy import process

        # { intent: [ { 'text': ..., 'slots': { ... } }, ... ] }
        examples = defaultdict(list)

        for intent, intent_sents in sentences_by_intent.items():
            for sentence, entities, tokens in intent_sents:
                slots = defaultdict(list)
                for entity, value in entities:
                    slots[entity].append(value)

                examples[intent].append({ 'text': sentence,
                                          'slots': slots })

        return examples
