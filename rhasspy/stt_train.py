import os
import re
import tempfile
import subprocess
import logging
import shutil
from collections import defaultdict
from typing import Dict, List, Any, Tuple

from utils import read_dict, lcm
from profiles import Profile

# -----------------------------------------------------------------------------

class SpeechTrainer:
    def train(self, tagged_sentences: Dict[str, List[str]]):
        pass

# -----------------------------------------------------------------------------

class PocketsphinxSpeechTrainer(SpeechTrainer):
    def __init__(self, core, profile: Profile):
        self.core = core
        self.profile = profile

    # -------------------------------------------------------------------------

    def train(self, tagged_sentences: Dict[str, List[str]]):
        '''Creates raw sentences and ARPA language model for pocketsphinx'''
        sentences_by_intent = defaultdict(list)

        self.write_dictionary(tagged_sentences, sentences_by_intent)

        self.write_sentences(sentences_by_intent)

        self.write_language_model()

        return sentences_by_intent

    # -------------------------------------------------------------------------

    def write_dictionary(self, tagged_sentences, sentences_by_intent):
        words_needed = set()

        # Extract entities from tagged sentences
        for intent_name, intent_sents in tagged_sentences.items():
            for intent_sent in intent_sents:
                # Template -> untagged sentence + entities
                sentence, entities = self._extract_entities(intent_sent)

                # Split sentence into words (tokens)
                sentence, tokens = self._sanitize_sentence(sentence)
                sentences_by_intent[intent_name].append((sentence, entities, tokens))

                # Collect all used words
                words_needed.update(tokens)

        # Load base and custom dictionaries
        base_dictionary_path = self.profile.read_path(
            self.profile.get('speech_to_text.pocketsphinx.base_dictionary'))

        custom_path = self.profile.read_path(
            self.profile.get('speech_to_text.pocketsphinx.custom_words'))

        word_dict = {}
        for word_dict_path in [base_dictionary_path, custom_path]:
            if os.path.exists(word_dict_path):
                with open(word_dict_path, 'r') as dictionary_file:
                    read_dict(dictionary_file, word_dict)

        # Add words from wake word if using pocketsphinx
        if self.profile.get('wake.system') == 'pocketsphinx':
            wake_keyphrase = self.profile.get('wake.pocketsphinx.keyphrase')
            _, wake_tokens = self._sanitize_sentence(wake_keyphrase)
            words_needed.update(wake_tokens)

        # Check for unknown words
        unknown_words = words_needed - word_dict.keys()
        unknown_path = self.profile.read_path(
            self.profile.get('speech_to_text.pocketsphinx.unknown_words'))

        if len(unknown_words) > 0:
            word_pron = core.get_word_pronouncer(self.profile.name)
            dictionary_upper = self.profile.get('speech_to_text.dictionary_upper', False)
            with open(unknown_path, 'w') as unknown_file:
                for word in unknown_words:
                    _, pronounces, _ = word_pron.pronounce(word, n=1)
                    phonemes = ' '.join(pronounces[0])

                    # Dictionary uses upper-case letters
                    if dictionary_upper:
                        word = word.upper()
                    else:
                        word = word.lower()

                    print(word.lower(), phonemes, file=unknown_file)

            raise RuntimeError('Training failed due to %s unknown word(s)' % len(unknown_words))

        elif os.path.exists(unknown_path):
            # Remove unknown dictionary
            os.unlink(unknown_path)

        # Write out dictionary with only the necessary words (speeds up loading)
        dictionary_path = self.profile.write_path(
            self.profile.get('speech_to_text.pocketsphinx.dictionary'))

        with open(dictionary_path, 'w') as dictionary_file:
            for word in sorted(words_needed):
                for i, pronounce in enumerate(word_dict[word]):
                    if i < 1:
                        print(word, pronounce, file=dictionary_file)
                    else:
                        print('%s(%s)' % (word, i+1), pronounce, file=dictionary_file)

        logging.debug('Wrote %s word(s) to %s' % (len(words_needed), dictionary_path))

    # -------------------------------------------------------------------------

    def write_sentences(self, sentences_by_intent):
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

        logging.debug('Wrote %s sentence(s) to %s' % (num_sentences, sentences_text_path))


    # -------------------------------------------------------------------------

    def write_language_model(self):
        '''Generate ARPA language model using opengrm'''
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

        logging.debug('Wrote language model to %s' % lm_dest_path)

    # -------------------------------------------------------------------------

    def _sanitize_sentence(self, sentence: str) -> Tuple[str, List[str]]:
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

    # -------------------------------------------------------------------------

    def _extract_entities(self, phrase: str) -> Tuple[str, List[Tuple[str, str]]]:
        """
        Extracts embedded entity markings from a phrase.
        Returns the phrase with entities removed and a list of entities.

        The format [some text](entity name) is used to mark entities in a training phrase.
        """
        entities = []
        removed_chars = 0

        def match(m):
            nonlocal removed_chars
            value, entity = m.group(1), m.group(2)
            replacement = value
            removed_chars += 1 + len(entity) + 3  # 1 for [, 3 for ], (, and )

            # Replace value with entity synonym, if present.
            entity_parts = entity.split(':', maxsplit=1)
            if len(entity_parts) > 1:
                entity = entity_parts[0]
                value = entity_parts[1]

            entities.append((entity, value))
            return replacement

        # [text](entity label) => text
        phrase = re.sub(r'\[([^]]+)\]\(([^)]+)\)', match, phrase)

        return phrase, entities
