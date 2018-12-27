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

class WordPronounce:
    def speak(self,
              espeak_str: str,
              voice: Optional[str] = None,
              speed: int = 80) -> Tuple[str, bytes]:
        pass

    def translate_phonemes(self,
                           phonemes: str) -> str:
        pass

    def pronounce(self,
                  word: str,
                  n: int = 5) -> Tuple[bool, List[str], str]:
        pass

    # -------------------------------------------------------------------------

    @classmethod
    def load_phoneme_map(cls, path: str) -> Dict[str, str]:
        # Load phoneme map from Sphinx to eSpeak (dictionary)
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
    def load_phoneme_examples(cls, path: str) -> Dict[str, Tuple[str, str]]:
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

class PhonetisaurusPronounce(WordPronounce):
    def __init__(self, profile: Profile):
        self.profile = profile

    def speak(self,
              espeak_str: str,
              voice: Optional[str] = None,
              speed: int = 80) -> Tuple[str, bytes]:

        # Use eSpeak to pronounce word
        espeak_command = ['espeak',
                          '-s', str(speed),
                          '-x']

        voice = self._get_voice(voice)

        if voice is not None:
            espeak_command.extend(['-v', str(voice)])

        espeak_command.append(espeak_str)

        # Write WAV to temporary file
        with tempfile.NamedTemporaryFile(suffix='.wav', mode='wb+') as wav_file:
            espeak_command.extend(['-w', wav_file.name])
            logging.debug(espeak_command)

            # Generate WAV data
            espeak_phonemes = subprocess.check_output(espeak_command).decode().strip()
            wav_file.seek(0)
            wav_data = wav_file.read()

        return espeak_phonemes, wav_data

    # -------------------------------------------------------------------------

    def translate_phonemes(self, phonemes: str) -> str:
        # Load map from Sphinx to eSpeak phonemes
        map_path = profile.read_path(
            profile.get('text_to_speech.espeak.phoneme_map'))

        phoneme_map = WordPronounce.load_phoneme_map(map_path)

        # Convert from Sphinx to espeak phonemes
        espeak_str = "[['%s]]" % ''.join(phoneme_map.get(p, p)
                                         for p in phonemes.split())

        return espeak_str

    # -------------------------------------------------------------------------

    def pronounce(self, word: str, n: int = 5) -> Tuple[bool, List[str], str]:
        assert n > 0, 'No pronunciations requested'
        assert len(word) > 0, 'No word to look up'

        logging.debug('Getting pronunciations for %s' % word)

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

        logging.debug(espeak_command)
        espeak_str = subprocess.check_output(espeak_command).decode().strip()

        return in_dictionary, pronunciations, espeak_str

    # -------------------------------------------------------------------------

    def _lookup_word(self, word: str, word_dict, n=5) -> Tuple[bool, List[str]]:
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

                logging.debug(g2p_command)
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
        return voice \
            or self.profile.get('text_to_speech.espeak.voice') \
            or self.profile.get('language')

# -----------------------------------------------------------------------------
# Events
# -----------------------------------------------------------------------------

# class SpeakWord:
#     def __init__(self, word: str, phonemes: str = None, silent=False):
#         self.word = word
#         self.phonemes = phonemes
#         self.silent = silent

# class WordSpoken:
#     def __init__(self, word: str, phonemes: str, wav_data: bytes):
#         self.word = word
#         self.phonemes = phonemes
#         self.wav_data = wav_data

# class GetWordPronunciations:
#     def __init__(self, word: str, n: int = 5):
#         self.word = word
#         self.n = n

# class WordPronunciations:
#     def __init__(self,
#                  word: str,
#                  in_dictionary: bool,
#                  pronunciations: List[str],
#                  espeak_str: str = ''):

#         self.word = word
#         self.in_dictionary = in_dictionary
#         self.pronunciations = pronunciations
#         self.espeak_str = espeak_str

# -----------------------------------------------------------------------------
# eSpeak and phonetisaurus Based Actor
# -----------------------------------------------------------------------------

# class PronounceActor(Actor):
#     def __init__(self):
#         self.profile = None

#     def receiveMessage(self, message, sender):
#         try:
#             if isinstance(message, Profile):
#                 self.profile = message
#             elif isinstance(message, SpeakWord):
#                 if message.phonemes is not None:
#                     espeak_str = self.translate_phonemes(message.phonemes)
#                 else:
#                     espeak_str = message.word

#                 espeak_phonemes, wav_data = self.speak(espeak_str, silent=message.silent)
#                 self.send(sender, WordSpoken(message.word, espeak_phonemes, wav_data))
#             elif isinstance(message, GetWordPronunciations):
#                 in_dictionary, pronunciations, espeak_str = \
#                     self.pronounce(message.word, message.n)

#                 self.send(sender, WordPronunciations(message.word,
#                                                      in_dictionary,
#                                                      pronunciations,
#                                                      espeak_str))
#         except Exception as e:
#             logging.exception('receiveMessage')

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

if __name__ == '__main__':
    profile = Profile('en', ['profiles'])

    p = Pronounce(profile)

    # Test speaking word
    phonemes, wav_data = p.speak('test')
    assert len(phonemes) > 0
    assert len(wav_data) > 0
    print(phonemes)

    # Test speaking phonemes
    phonemes, wav_data = p.speak(p.translate_phonemes('T IY S T'))
    print(phonemes)
    assert len(wav_data) > 0

    # Test known word pronunciations
    in_dictionary, pronunciations, espeak_str = p.pronounce('test')
    assert in_dictionary
    assert len(pronunciations) > 0
    print(pronunciations)
    print(espeak_str)

    # Test unknown word pronunciations
    in_dictionary, pronunciations, espeak_str = \
        p.pronounce('raxacoricofallapatorius')

    assert not in_dictionary
    assert len(pronunciations) > 0
    print(pronunciations)
    print(espeak_str)
