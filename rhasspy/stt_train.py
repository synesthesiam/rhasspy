import os
import re
import tempfile
import subprocess
import logging
import shutil
import json
from collections import defaultdict
from typing import Dict, List, Any, Tuple, Set, Optional

from thespian.actors import ActorAddress

from .actor import RhasspyActor
from .profiles import Profile
from .pronounce import GetWordPronunciations, WordPronunciation
from .utils import (read_dict, lcm, group_sentences_by_intent,
                    sanitize_sentence, TrainingSentence)

# -----------------------------------------------------------------------------

class TrainSpeech:
    def __init__(self,
                 tagged_sentences: Dict[str, List[str]],
                 receiver:Optional[ActorAddress]=None) -> None:
        self.tagged_sentences = tagged_sentences
        self.receiver = receiver

class SpeechTrainingComplete:
    def __init__(self,
                 tagged_sentences: Dict[str, List[str]],
                 sentences_by_intent: Dict[str, List[TrainingSentence]]) -> None:
        self.tagged_sentences = tagged_sentences
        self.sentences_by_intent = sentences_by_intent

class SpeechTrainingFailed:
    pass

# -----------------------------------------------------------------------------

class DummySpeechTrainer(RhasspyActor):
    '''Passes sentences along'''
    def to_started(self, from_state:str) -> None:
        self.sentence_casing = self.profile.get('training.sentence_casing', None)
        tokenizer = self.profile.get('training.tokenizer', 'regex')
        regex_config = self.profile.get(f'training.{tokenizer}', {})
        self.replace_patterns = regex_config.get('replace', [])
        self.split_pattern = regex_config.get('split', r'\s+')

    def in_started(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, TrainSpeech):
            self.send(message.receiver or sender,
                      SpeechTrainingComplete(message.tagged_sentences,
                                             self.train(message.tagged_sentences)))

    # -------------------------------------------------------------------------

    def train(self, tagged_sentences: Dict[str, List[str]]) -> Dict[str, List[TrainingSentence]]:
        return group_sentences_by_intent(tagged_sentences,
                                         self.sentence_casing,
                                         self.replace_patterns,
                                         self.split_pattern)

# -----------------------------------------------------------------------------
# Speech system trainer for Pocketsphinx.
# Uses mitlm (ARPA model) and phonetisaurus (pronunciations).
# -----------------------------------------------------------------------------

class PocketsphinxSpeechTrainer(RhasspyActor):
    '''Trains an ARPA language model using opengrm.'''
    def to_started(self, from_state:str) -> None:
        self.word_pronouncer:ActorAddress = self.config['word_pronouncer']
        self.tagged_sentences:Dict[str, List[str]] = {}
        self.unknown_words:Dict[str, Optional[WordPronunciation]] = {}
        self.waiting_words:List[str] = []
        self.receiver:Optional[ActorAddress] = None
        self.sentence_casing = self.profile.get('training.sentence_casing', None)
        self.dictionary_upper:bool = \
            self.profile.get('speech_to_text.dictionary_upper', False)

        tokenizer = self.profile.get('training.tokenizer', 'regex')
        regex_config = self.profile.get(f'training.{tokenizer}', {})
        self.replace_patterns = regex_config.get('replace', [])
        self.split_pattern = regex_config.get('split', r'\s+')

        # Unknown words
        self.guess_unknown = self.profile.get(
            'training.unknown_words.guess_pronunciations', True)
        self.fail_on_unknown = self.profile.get(
            'training.unknown_words.fail_when_present', True)

    def in_started(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, TrainSpeech):
            self.receiver = message.receiver or sender
            self.tagged_sentences = message.tagged_sentences
            self.transition('writing_dictionary')

    def to_writing_dictionary(self, from_state:str) -> None:
        self.sentences_by_intent = group_sentences_by_intent(
            self.tagged_sentences,
            self.sentence_casing,
            self.replace_patterns,
            self.split_pattern)

        self.unknown_words = {
            word: None
            for word in self.write_dictionary(self.tagged_sentences,
                                              self.sentences_by_intent)
        }

        has_unknown_words = len(self.unknown_words) > 0

        if has_unknown_words:
            self._logger.warn('There are %s unknown word(s)' % len(self.unknown_words))
        else:
            # Remove unknown dictionary
            unknown_path = self.profile.read_path(
                self.profile.get('speech_to_text.pocketsphinx.unknown_words'))

            if os.path.exists(unknown_path):
                os.unlink(unknown_path)

        # Proceed or guess pronunciations
        if self.guess_unknown and has_unknown_words:
            self.transition('unknown_words')
        else:
            self.transition('writing_sentences')

    def to_unknown_words(self, from_state:str) -> None:
        self.waiting_words = list(self.unknown_words.keys())
        for word in self.unknown_words:
            self.send(self.word_pronouncer,
                      GetWordPronunciations(word, n=1))

    def in_unknown_words(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, WordPronunciation):
            self.waiting_words.remove(message.word)
            self.unknown_words[message.word] = message
            if len(self.waiting_words) == 0:
                self.write_unknown_words(self.unknown_words)

                if self.fail_on_unknown:
                    # Fail when unknown words are present
                    self.send(self.receiver, SpeechTrainingFailed())
                    self.transition('started')
                else:
                    # Proceed with training
                    self.transition('writing_sentences')

    def to_writing_sentences(self, from_state:str) -> None:
        self.write_sentences(self.sentences_by_intent)
        self.transition('writing_language_model')

    def to_writing_language_model(self, from_state:str) -> None:
        self.write_language_model()
        self.send(self.receiver,
                  SpeechTrainingComplete(self.tagged_sentences,
                                         self.sentences_by_intent))
        self.transition('started')

    # -------------------------------------------------------------------------

    def write_dictionary(self, tagged_sentences: Dict[str, List[str]],
                         sentences_by_intent: Dict[str, List[TrainingSentence]]) -> Set[str]:
        '''Writes all required words to a CMU dictionary.
        Unknown words have their pronunciations guessed and written to a separate dictionary.
        Fails if any unknown words are found.'''

        words_needed: Set[str] = set()

        # Extract entities from tagged sentences
        for intent_name, intent_sents in sentences_by_intent.items():
            for intent_sent in intent_sents:
                # Collect all used words
                for word in intent_sent.tokens:
                    # Dictionary uses upper-case letters
                    if self.dictionary_upper:
                        word = word.upper()
                    else:
                        word = word.lower()

                    words_needed.add(word)

        # Load base and custom dictionaries
        base_dictionary_path = self.profile.read_path(
            self.profile.get('speech_to_text.pocketsphinx.base_dictionary'))

        custom_path = self.profile.read_path(
            self.profile.get('speech_to_text.pocketsphinx.custom_words'))

        word_dict: Dict[str, List[str]] = {}
        for word_dict_path in [base_dictionary_path, custom_path]:
            if os.path.exists(word_dict_path):
                with open(word_dict_path, 'r') as dictionary_file:
                    read_dict(dictionary_file, word_dict)

        # Add words from wake word if using pocketsphinx
        if self.profile.get('wake.system') == 'pocketsphinx':
            wake_keyphrase = self.profile.get('wake.pocketsphinx.keyphrase')
            _, wake_tokens = sanitize_sentence(wake_keyphrase,
                                               self.sentence_casing,
                                               self.replace_patterns,
                                               self.split_pattern)

            for word in wake_tokens:
                # Dictionary uses upper-case letters
                if self.dictionary_upper:
                    word = word.upper()
                else:
                    word = word.lower()

                words_needed.add(word)

        # Write out dictionary with only the necessary words (speeds up loading)
        dictionary_path = self.profile.write_path(
            self.profile.get('speech_to_text.pocketsphinx.dictionary'))

        words_written = 0
        with open(dictionary_path, 'w') as dictionary_file:
            for word in sorted(words_needed):
                if not word in word_dict:
                    continue

                for i, pronounce in enumerate(word_dict[word]):
                    if i < 1:
                        print(word, pronounce, file=dictionary_file)
                    else:
                        print('%s(%s)' % (word, i+1), pronounce, file=dictionary_file)

                words_written += 1

        self._logger.debug('Wrote %s word(s) to %s' % (words_written, dictionary_path))

        # Check for unknown words
        return words_needed - word_dict.keys()

    # -------------------------------------------------------------------------

    def write_unknown_words(self, unknown_words: Dict[str, Optional[WordPronunciation]]) -> None:
        unknown_path = self.profile.read_path(
            self.profile.get('speech_to_text.pocketsphinx.unknown_words'))

        with open(unknown_path, 'w') as unknown_file:
            for word, word_pron in unknown_words.items():
                assert word_pron is not None
                pronunciations = word_pron.pronunciations
                phonemes = pronunciations[0]

                # Dictionary uses upper-case letters
                if self.dictionary_upper:
                    word = word.upper()
                else:
                    word = word.lower()

                print(word, phonemes, file=unknown_file)

    # -------------------------------------------------------------------------

    def write_sentences(self, sentences_by_intent: Dict[str, List[TrainingSentence]]) -> None:
        '''Writes all raw sentences to a text file.
        Optionally balances (repeats) sentences so all intents have the same number.'''

        # Repeat sentences so that all intents will contain the same number
        balance_sentences = self.profile.get('training.balance_sentences', True)
        if balance_sentences:
            # Use least common multiple
            lcm_sentences = lcm(*(len(sents) for sents
                                  in sentences_by_intent.values()))
        else:
            lcm_sentences = 0  # no repeats

        # Write sentences to text file
        sentences_text_path = self.profile.write_path(
            self.profile.get('speech_to_text.sentences_text'))

        num_sentences = 0
        with open(sentences_text_path, 'w') as sentences_text_file:
            for intent_name, intent_sents in sentences_by_intent.items():
                num_repeats = max(1, lcm_sentences // len(intent_sents))
                for intent_sent in intent_sents:
                    for i in range(num_repeats):
                        print(intent_sent.sentence, file=sentences_text_file)
                    num_sentences = num_sentences + 1

        self._logger.debug('Wrote %s sentence(s) to %s' % (num_sentences, sentences_text_path))

    # -------------------------------------------------------------------------

    def write_language_model(self) -> None:
        '''Generates an ARPA language model using mitlm'''
        sentences_text_path = self.profile.read_path(
            self.profile.get('speech_to_text.sentences_text'))

        # Extract file name only (will be made relative to container path)
        sentences_text_path = sentences_text_path
        working_dir = self.profile.write_dir()
        lm_dest_path = self.profile.write_path(
            self.profile.get('speech_to_text.pocketsphinx.language_model'))

        # Use mitlm
        subprocess.check_call(['estimate-ngram',
                               '-o', '3',
                               '-text', sentences_text_path,
                               '-wl', lm_dest_path])

        self._logger.debug('Wrote language model to %s' % lm_dest_path)

# -----------------------------------------------------------------------------
# Command-line based speed trainer.
# -----------------------------------------------------------------------------

class CommandSpeechTrainer(RhasspyActor):
    '''Trains a speech to text system via command line.'''

    def to_started(self, from_state:str) -> None:
        program = os.path.expandvars(self.profile.get('training.speech_to_text.command.program'))
        arguments = [os.path.expandvars(str(a))
                     for a in self.profile.get('training.speech_to_text.command.arguments', [])]

        self.command = [program] + arguments

        self.sentence_casing = self.profile.get('training.sentence_casing', None)
        tokenizer = self.profile.get('training.tokenizer', 'regex')
        regex_config = self.profile.get(f'training.{tokenizer}', {})
        self.replace_patterns = regex_config.get('replace', [])
        self.split_pattern = regex_config.get('split', r'\s+')

    def in_started(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, TrainSpeech):
            try:
                sentences_by_intent = self.train(message.tagged_sentences)
                self.send(message.receiver or sender,
                          SpeechTrainingComplete(message.tagged_sentences,
                                                 sentences_by_intent))
            except:
                self._logger.exception('train')
                self.send(message.receiver or sender,
                          SpeechTrainingFailed())

    # -------------------------------------------------------------------------

    def train(self, tagged_sentences: Dict[str, List[str]]) -> Dict[str, List[TrainingSentence]]:
        sentences_by_intent = group_sentences_by_intent(tagged_sentences,
                                                        self.sentence_casing,
                                                        self.replace_patterns,
                                                        self.split_pattern)

        self._logger.debug(self.command)

        # JSON -> STDIN
        input = json.dumps({
            intent_name: [s.json() for s in sentences]
            for intent_name, sentences in sentences_by_intent.items()
        }).encode()

        subprocess.run(self.command, input=input, check=True)

        return sentences_by_intent
