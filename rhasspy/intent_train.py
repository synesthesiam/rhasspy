import os
import json
import logging
import tempfile
from urllib.parse import urljoin
from collections import defaultdict
from typing import Dict, List

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

    def _make_examples(self, sentences_by_intent):
        '''Write intent examples to a JSON file.'''
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
