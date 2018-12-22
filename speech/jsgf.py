#!/usr/bin/env python3
import os
import io
import re
import subprocess
import logging
import tempfile
from typing import List

from thespian.actors import Actor

from events import GenerateSentences, SentencesGenerated

# -----------------------------------------------------------------------------
# JSGF Sentence Generator
# https://github.com/synesthesiam/jsgf-gen/
# -----------------------------------------------------------------------------

class JsgfGeneratorActor(Actor):
    def receiveMessage(self, message, sender):
        try:
            if isinstance(message, TrainLanguageModel):
                lm = self.train_language_model(message.sentences)
                self.send(sender, LanguageModelTrained(lm))
        except Exception as e:
            logging.exception('receiveMessage')

    # -------------------------------------------------------------------------

    def sanitize_sentence(self, sentence: str) -> Tuple[str, List[str]]:
        assert self.profile is not None, 'No profile'
        training_config = self.profile.training

        # Check if sentences should be upper or lower cased
        sentence_casing = training_config.get('sentence_casing', None)
        if sentence_casing == 'lower':
            sentence = sentence.lower()
        elif sentence_casing == 'upper':
            sentence = sentence.upper()

        # Get profile tokenizer
        tokenizer = training_config.get('tokenizer', 'regex')

        if tokenizer == 'regex':
            # Tokenize sentences using regular expressions
            regex_config = training_config[tokenizer]

            # Process replacement patterns
            for repl_dict in regex_config.get('replace', []):
                for pattern, repl in repl_dict.items():
                    sentence = re.sub(pattern, repl, sentence)

            # Tokenize with split pattern
            split_pattern = regex_config.get('split', r'\s+')
            tokens = [t for t in re.split(split_pattern, sentence)
                      if len(t.strip()) > 0]
        else:
            assert False, 'Unknown tokenizer: %s' % tokenizer

        return sentence, tokens
