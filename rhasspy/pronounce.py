#!/usr/bin/env python3
import os
import re
import logging
import subprocess
import tempfile
from typing import Dict, Tuple, List, Optional

# from thespian.actors import Actor, ActorSystem

import utils
from profiles import Profile

# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

class WordPronounce:
    '''Base class for word lookup/pronounce-ers.'''

    def __init__(self, profile: Profile) -> None:
        self.profile = profile

    def preload(self):
        '''Cache any important stuff upfront.'''
        pass

    def speak(self,
              espeak_str: str,
              voice: Optional[str] = None) -> Tuple[str, bytes]:
        '''Generate WAV data from a word or eSpeak phoneme string.
        Uses the profile's voice or language if voice isn't given.
        Returns the eSpeak phonemes and WAV data.'''
        pass

    def translate_phonemes(self, phonemes: str) -> str:
        '''Converts CMU phonemes to eSpeak phonemes using profile's table.'''
        pass

    def pronounce(self, word: str, n: int = 5) -> Tuple[bool, List[str], str]:
        '''Looks up or generates up to n pronunciations for an unknown word.
        Returns True if the word is in a dictionary, the pronunciations, and eSpeak
        phonemes for the word.'''
        pass

    # -------------------------------------------------------------------------

    @classmethod
    def load_phoneme_map(cls, path: str) -> Dict[str, str]:
        '''Load phoneme map from CMU (Sphinx) phonemes to eSpeak phonemes.'''
        phonemes = {}
        with open(path, 'r') as phoneme_file:
            for line in phoneme_file:
                line = line.strip()
                if (len(line) == 0) or line.startswith('#'):
                    continue  # skip blanks and comments

                parts = re.split('\s+', line, maxsplit=1)
                phonemes[parts[0]] = parts[1]

        return phonemes

    @classmethod
    def load_phoneme_examples(cls, path: str) -> Dict[str, Dict[str, str]]:
        '''Loads example words and pronunciations for each phoneme.'''
        examples = {}
        with open(path, 'r') as example_file:
            for line in example_file:
                line = line.strip()
                if (len(line) == 0) or line.startswith('#'):
                    continue  # skip blanks and comments

                parts = re.split('\s+', line)
                examples[parts[0]] = {
                    'word': parts[1],
                    'phonemes': ' '.join(parts[2:])
                }

        return examples


# -----------------------------------------------------------------------------
# Phonetisaurus based word pronouncer
# https://github.com/AdolfVonKleist/Phonetisaurus
# -----------------------------------------------------------------------------

class PhonetisaurusPronounce(WordPronounce):

    def __init__(self, profile: Profile) -> None:
        WordPronounce.__init__(self, profile)
        self.speed = 80  # wpm for speaking

    def speak(self,
              espeak_str: str,
              voice: Optional[str] = None) -> Tuple[str, bytes]:

        # Use eSpeak to pronounce word
        espeak_command = ['espeak',
                          '-s', str(self.speed),
                          '-x']

        voice = self._get_voice(voice)

        if voice is not None:
            espeak_command.extend(['-v', str(voice)])

        espeak_command.append(espeak_str)

        # Write WAV to temporary file
        with tempfile.NamedTemporaryFile(suffix='.wav', mode='wb+') as wav_file:
            espeak_command.extend(['-w', wav_file.name])
            logger.debug(espeak_command)

            # Generate WAV data
            espeak_phonemes = subprocess.check_output(espeak_command).decode().strip()
            wav_file.seek(0)
            wav_data = wav_file.read()

        return espeak_phonemes, wav_data

    # -------------------------------------------------------------------------

    def translate_phonemes(self, phonemes: str) -> str:
        # Load map from Sphinx to eSpeak phonemes
        map_path = self.profile.read_path(
            self.profile.get('text_to_speech.espeak.phoneme_map'))

        phoneme_map = WordPronounce.load_phoneme_map(map_path)

        # Convert from Sphinx to espeak phonemes
        espeak_str = "[['%s]]" % ''.join(phoneme_map.get(p, p)
                                         for p in phonemes.split())

        return espeak_str

    # -------------------------------------------------------------------------

    def pronounce(self, word: str, n: int = 5) -> Tuple[bool, List[str], str]:
        assert n > 0, 'No pronunciations requested'
        assert len(word) > 0, 'No word to look up'

        logger.debug('Getting pronunciations for %s' % word)

        # Load base and custom dictionaries
        base_dictionary_path = self.profile.read_path(
            self.profile.get('speech_to_text.pocketsphinx.base_dictionary'))

        custom_path = self.profile.read_path(
            self.profile.get('speech_to_text.pocketsphinx.custom_words'))

        word_dict: Dict[str, List[str]] = {}
        for word_dict_path in [base_dictionary_path, custom_path]:
            if os.path.exists(word_dict_path):
                with open(word_dict_path, 'r') as dictionary_file:
                    utils.read_dict(dictionary_file, word_dict)

        in_dictionary, pronunciations = self._lookup_word(word, word_dict, n)

        # Get phonemes from eSpeak
        espeak_command = ['espeak', '-q', '-x']

        voice = self._get_voice()
        if voice is not None:
            espeak_command.extend(['-v', voice])

        espeak_command.append(word)

        logger.debug(espeak_command)
        espeak_str = subprocess.check_output(espeak_command).decode().strip()

        return in_dictionary, pronunciations, espeak_str

    # -------------------------------------------------------------------------

    def _lookup_word(self, word: str, word_dict, n=5) -> Tuple[bool, List[str]]:
        '''Look up or guess word pronunciations.'''

        # Dictionary uses upper-case letters
        dictionary_upper = self.profile.get(
            'speech_to_text.dictionary_upper', False)

        if dictionary_upper:
            word = word.upper()
        else:
            word = word.lower()

        pronounces = list(word_dict.get(word, []))
        in_dictionary = (len(pronounces) > 0)
        if not in_dictionary:
            # Guess pronunciation
            # Path to phonetisaurus FST
            g2p_path = self.profile.read_path(
                self.profile.get('speech_to_text.g2p_model'))

            g2p_upper = self.profile.get(
                'speech_to_text.g2p_upper', False)

            if g2p_upper:
                # FST was trained with upper-case letters
                word = word.upper()
            else:
                # FST was trained with loser-case letters
                word = word.lower()

            # Output phonetisaurus results to temporary file
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt') as pronounce_file:
                # Use phonetisaurus to guess pronunciations
                g2p_command = ['phonetisaurus-g2p',
                                '--model=' + g2p_path,
                                '--input=' + word,  # case sensitive
                                '--nbest=' + str(n),
                                '--words']

                logger.debug(g2p_command)
                subprocess.check_call(g2p_command, stdout=pronounce_file)

                pronounce_file.seek(0)

                # Read results
                ws_pattern = re.compile(r'\s+')

                for line in pronounce_file:
                    parts = ws_pattern.split(line)
                    phonemes = ' '.join(parts[2:]).strip()
                    pronounces.append(phonemes)

        return in_dictionary, pronounces

    # -------------------------------------------------------------------------

    def _get_voice(self, voice: Optional[str] = None) -> Optional[str]:
        '''Uses either the provided voice, the profile's text to speech voice,
        or the profile's language.'''
        return voice \
            or self.profile.get('text_to_speech.espeak.voice') \
            or self.profile.get('language')
