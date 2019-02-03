import os
import re
import tempfile
import subprocess
import logging
import shutil
from collections import defaultdict
from typing import Dict, List, Any, Tuple, Set, Optional

from thespian.actors import ActorAddress

from .actor import RhasspyActor
from .profiles import Profile
from .pronounce import GetWordPronunciations, WordPronunciation
from .utils import read_dict, lcm, extract_entities

# -----------------------------------------------------------------------------

SBI_TYPE = Dict[str, List[Tuple[str, List[Tuple[str, str]], List[str]]]]

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
                 sentences_by_intent: SBI_TYPE) -> None:
        self.tagged_sentences = tagged_sentences
        self.sentences_by_intent = sentences_by_intent

class SpeechTrainingFailed:
    pass

# -----------------------------------------------------------------------------

class PocketsphinxSpeechTrainer(RhasspyActor):
    '''Trains an ARPA language model using opengrm.'''
    def to_started(self, from_state:str) -> None:
        self.word_pronouncer:ActorAddress = self.config['word_pronouncer']
        self.tagged_sentences:Dict[str, List[str]] = {}
        self.unknown_words:Dict[str, Optional[WordPronunciation]] = {}
        self.waiting_words:List[str] = []
        self.receiver:Optional[ActorAddress] = None
        self.dictionary_upper:bool = \
            self.profile.get('speech_to_text.dictionary_upper', False)

    def in_started(self, message: Any, sender: ActorAddress) -> None:
        if isinstance(message, TrainSpeech):
            self.receiver = message.receiver or sender
            self.tagged_sentences = message.tagged_sentences
            self.transition('writing_dictionary')

    def to_writing_dictionary(self, from_state:str) -> None:
        self.sentences_by_intent: SBI_TYPE = defaultdict(list)
        self.unknown_words = {
            word: None
            for word in self.write_dictionary(self.tagged_sentences,
                                              self.sentences_by_intent)
        }

        if len(self.unknown_words) > 0:
            self._logger.warn('There are %s unknown word(s)' % len(self.unknown_words))
            self.transition('unknown_words')
        else:
            self.transition('writing_sentences')

            # Remove unknown dictionary
            unknown_path = self.profile.read_path(
                self.profile.get('speech_to_text.pocketsphinx.unknown_words'))

            if os.path.exists(unknown_path):
                os.unlink(unknown_path)

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
                self.send(self.receiver, SpeechTrainingFailed())
                self.transition('started')

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
                         sentences_by_intent: SBI_TYPE) -> Set[str]:
        '''Writes all required words to a CMU dictionary.
        Unknown words have their pronunciations guessed and written to a separate dictionary.
        Fails if any unknown words are found.'''

        words_needed: Set[str] = set()

        # Extract entities from tagged sentences
        for intent_name, intent_sents in tagged_sentences.items():
            for intent_sent in intent_sents:
                # Template -> untagged sentence + entities
                sentence, entities = extract_entities(intent_sent)

                # Split sentence into words (tokens)
                sentence, tokens = self._sanitize_sentence(sentence)
                sentences_by_intent[intent_name].append((sentence, entities, tokens))

                # Collect all used words
                for word in tokens:
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
            _, wake_tokens = self._sanitize_sentence(wake_keyphrase)

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

    def write_sentences(self, sentences_by_intent: SBI_TYPE) -> None:
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

        with open(sentences_text_path, 'w') as sentences_text_file:
            num_sentences = 0
            for intent_name, intent_sents in sentences_by_intent.items():
                num_repeats = max(1, lcm_sentences // len(intent_sents))
                for sentence, slots, tokens in intent_sents:
                    for i in range(num_repeats):
                        print(sentence, file=sentences_text_file)
                        num_sentences = num_sentences + 1

        self._logger.debug('Wrote %s sentence(s) to %s' % (num_sentences, sentences_text_path))


    # -------------------------------------------------------------------------

    def write_language_model(self) -> None:
        '''Generates an ARPA language model using opengrm'''
        sentences_text_path = self.profile.read_path(
            self.profile.get('speech_to_text.sentences_text'))

        # Extract file name only (will be made relative to container path)
        sentences_text_path = os.path.split(sentences_text_path)[1]
        working_dir = self.profile.write_dir()

        # Generate symbols
        subprocess.check_call(['ngramsymbols',
                               sentences_text_path,
                               'sentences.syms'],
                              cwd=working_dir)

        # Convert to archive (FAR)
        subprocess.check_call(['farcompilestrings',
                               '-symbols=sentences.syms',
                               '-keep_symbols=1',
                               sentences_text_path,
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

        lm_source_path = os.path.join(working_dir, 'sentences.arpa')

        # Save to profile
        lm_dest_path = self.profile.write_path(
            self.profile.get('speech_to_text.pocketsphinx.language_model'))

        if lm_source_path != lm_dest_path:
            shutil.copy(lm_source_path, lm_dest_path)

        self._logger.debug('Wrote language model to %s' % lm_dest_path)

    # -------------------------------------------------------------------------

    def _sanitize_sentence(self, sentence: str) -> Tuple[str, List[str]]:
        '''Applies profile-specific casing and tokenization to a sentence.
        Returns the sanitized sentence and tokens.'''

        sentence_casing = self.profile.get('training.sentence_casing', None)
        if sentence_casing == 'lower':
            sentence = sentence.lower()
        elif sentence_casing == 'upper':
            sentence = sentence.upper()

        tokenizer = self.profile.get('training.tokenizer', 'regex')
        assert tokenizer in ['regex'], 'Unknown tokenizer: %s' % tokenizer

        if tokenizer == 'regex':
            regex_config = self.profile.get('training.regex', {})

            # Process replacement patterns
            for repl_dict in regex_config.get('replace', []):
                for pattern, repl in repl_dict.items():
                    sentence = re.sub(pattern, repl, sentence)

            # Tokenize
            split_pattern = regex_config.get('split', r'\s+')
            tokens = [t for t in re.split(split_pattern, sentence)
                      if len(t.strip()) > 0]

        return sentence, tokens
