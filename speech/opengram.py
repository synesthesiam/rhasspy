#!/usr/bin/env python3
import os
import io
import re
import subprocess
import logging
import tempfile
from typing import List

from thespian.actors import Actor

from events import TrainLanguageModel, LanguageModelTrained

# -----------------------------------------------------------------------------
# Opengrm ARPA Language Modeler
# http://www.opengrm.org/twiki/bin/view/GRM/NGramLibrary
# -----------------------------------------------------------------------------

class OpengrmLanguageModelActor(Actor):
    def receiveMessage(self, message, sender):
        try:
            if isinstance(message, TrainLanguageModel):
                lm = self.train_language_model(message.sentences)
                self.send(sender, LanguageModelTrained(lm))
        except Exception as e:
            logging.exception('receiveMessage')

    # -------------------------------------------------------------------------

    def train_language_model(self, sentences: List[str]) -> str:
        with tempfile.TemporaryDirectory() as temp_dir:
            sentences_text_path = os.path.join(temp_dir, 'sentences.txt')
            with open(sentences_text_path, 'w') as sentences_file:
                sentences_file.writelines(sentences)

            # Create temporary artifacts here
            working_dir = temp_dir

            # Generate symbols
            subprocess.check_call(['ngramsymbols',
                                  'sentences.txt',
                                  'sentences.syms'],
                                  cwd=working_dir)

            # Convert to archive (FAR)
            subprocess.check_call(['farcompilestrings',
                                  '-symbols=sentences.syms',
                                  '-keep_symbols=1',
                                  'sentences.txt',
                                  'sentences.far'],
                                  cwd=working_dir)

            # Generate trigram counts
            subprocess.check_call(['ngramcount',
                                  '-order=3',
                                  'sentences.far',
                                  'sentences.cnts'],
                                  cwd=working_dir)

            # Create trigram model
            subprocess.check_call(['ngrammake',
                                  'sentences.cnts',
                                  'sentences.mod'],
                                  cwd=working_dir)

            # Convert to ARPA format
            subprocess.check_call(['ngramprint',
                                  '--ARPA',
                                  'sentences.mod',
                                  'sentences.arpa'],
                                  cwd=working_dir)

            # Return ARPA language model
            with open(os.path.join(working_dir, 'sentences.arpa'), 'r') as arpa_file:
                return arpa_file.read()
