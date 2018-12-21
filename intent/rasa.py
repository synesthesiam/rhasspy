#!/usr/bin/env python3
import os
import sys
sys.path.insert(0, os.path.abspath('..'))

import logging
import tempfile
from urllib.parse import urljoin

import requests
from thespian.actors import Actor

from profile import Profile

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
