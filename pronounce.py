#!/usr/bin/env python3
import os
import re
import logging
import subprocess
import tempfile
from typing import Dict, Tuple, List, Optional

from thespian.actors import Actor, ActorSystem

import utils
from profiles import Profile

# -----------------------------------------------------------------------------
# Events
# -----------------------------------------------------------------------------

class SpeakWord:
    def __init__(self, word: str, phonemes: str = None, silent=False):
        self.word = word
        self.phonemes = phonemes
        self.silent = silent

class WordSpoken:
    def __init__(self, word: str, phonemes: str, wav_data: bytes):
        self.word = word
        self.phonemes = phonemes
        self.wav_data = wav_data

class GetWordPronunciations:
    def __init__(self, word: str, n: int = 5):
        self.word = word
        self.n = n

class WordPronunciations:
    def __init__(self,
                 word: str,
                 in_dictionary: bool,
                 pronunciations: List[str],
                 espeak_str: str = ''):

        self.word = word
        self.in_dictionary = in_dictionary
        self.pronunciations = pronunciations
        self.espeak_str = espeak_str

# -----------------------------------------------------------------------------
# eSpeak and phonetisaurus Based Actor
# -----------------------------------------------------------------------------

class PronounceActor(Actor):
    def __init__(self):
        self.profile = None

    def receiveMessage(self, message, sender):
        try:
            if isinstance(message, Profile):
                self.profile = message
            elif isinstance(message, SpeakWord):
                if message.phonemes is not None:
                    espeak_str = self.translate_phonemes(message.phonemes)
                else:
                    espeak_str = message.word

                espeak_phonemes, wav_data = self.speak(espeak_str, silent=message.silent)
                self.send(sender, WordSpoken(message.word, espeak_phonemes, wav_data))
            elif isinstance(message, GetWordPronunciations):
                in_dictionary, pronunciations, espeak_str = \
                    self.pronounce(message.word, message.n)

                self.send(sender, WordPronunciations(message.word,
                                                     in_dictionary,
                                                     pronunciations,
                                                     espeak_str))
        except Exception as e:
            logging.exception('receiveMessage')

    # -------------------------------------------------------------------------

    def speak(self,
              espeak_str: str,
              voice: str = None,
              speed: int = 80,
              silent: bool = False) -> Tuple[str, bytes]:

        assert self.profile is not None, 'No profile'
        espeak_config = self.profile.text_to_speech['espeak']

        # Use eSpeak to pronounce word
        espeak_command = ['espeak',
                          '-s', str(speed),
                          '-x']

        voice = self.get_voice(voice)

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

            if not silent:
                # TODO: Use APlayActor
                subprocess.check_call(['aplay', '-t', 'wav', wav_file.name])

        return espeak_phonemes, wav_data

    # -------------------------------------------------------------------------

    def get_voice(self, voice: str = None) -> Optional[str]:
        espeak_config = self.profile.text_to_speech['espeak']
        if 'voice' in espeak_config:
            # Use profile voice
            voice = espeak_config['voice']
        elif 'language' in profile.json:
            # Use language default voice
            voice = self.profile.json['language']

        return voice

    # -------------------------------------------------------------------------

    def translate_phonemes(self, phonemes: str) -> str:
        assert self.profile is not None, 'No profile'
        espeak_config = profile.text_to_speech['espeak']

        # Load map from Sphinx to eSpeak phonemes
        map_path = profile.read_path(espeak_config['phoneme_map'])
        phoneme_map = self.load_phoneme_map(map_path)

        # Convert from Sphinx to espeak phonemes
        espeak_str = "[['%s]]" % ''.join(phoneme_map.get(p, p)
                                         for p in phonemes.split())

        return espeak_str

    # -------------------------------------------------------------------------

    def load_phoneme_map(self, path: str) -> Dict[str, str]:
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

    # -------------------------------------------------------------------------

    def pronounce(self, word: str, n: int = 5) -> Tuple[bool, List[str], str]:
        assert self.profile is not None, 'No profile'
        assert n > 0, 'No pronunciations requested'
        assert len(word) > 0, 'No word to look up'

        ps_config = self.profile.speech_to_text['pocketsphinx']
        espeak_config = self.profile.text_to_speech['espeak']

        logging.debug('Getting pronunciations for %s' % word)

        # Load base and custom dictionaries
        base_dictionary_path = self.profile.read_path(ps_config['base_dictionary'])
        custom_path = self.profile.read_path(ps_config['custom_words'])

        word_dict: Dict[str, List[str]] = {}
        for word_dict_path in [base_dictionary_path, custom_path]:
            if os.path.exists(word_dict_path):
                with open(word_dict_path, 'r') as dictionary_file:
                    utils.read_dict(dictionary_file, word_dict)

        in_dictionary, pronunciations = self.lookup_word(word, word_dict, n)

        # Get phonemes from eSpeak
        espeak_command = ['espeak', '-q', '-x']

        voice = self.get_voice()
        if voice is not None:
            espeak_command.extend(['-v', voice])

        espeak_command.append(word)

        logging.debug(espeak_command)
        espeak_str = subprocess.check_output(espeak_command).decode().strip()

        return in_dictionary, pronunciations, espeak_str

    # -------------------------------------------------------------------------

    def lookup_word(self, word: str, word_dict, n=5) -> Tuple[bool, List[str]]:
        # Dictionary uses upper-case letters
        stt_config = self.profile.speech_to_text
        if stt_config.get('dictionary_upper', False):
            word = word.upper()
        else:
            word = word.lower()

        pronounces = list(word_dict.get(word, []))
        in_dictionary = (len(pronounces) > 0)
        if not in_dictionary:
            # Guess pronunciation
            # Path to phonetisaurus FST
            g2p_path = self.profile.read_path(stt_config['g2p_model'])

            if stt_config.get('g2p_upper', False):
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

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

if __name__ == '__main__':
    profile = Profile('en', ['profiles'])

    # Start actor system
    system = ActorSystem('multiprocQueueBase')

    try:
        actor = system.createActor(PronounceActor)
        system.tell(actor, profile)

        # Test speaking word
        result = system.ask(actor, SpeakWord('test'))
        print(result.phonemes)
        assert len(result.wav_data) > 0

        # Test speaking phonemes
        result = system.ask(actor, SpeakWord('test', 'T IY S T', silent=True))
        print(result.phonemes)
        assert len(result.wav_data) > 0

        # Test known word pronunciations
        result = system.ask(actor, GetWordPronunciations('test'))
        assert result.in_dictionary
        assert len(result.pronunciations) > 0
        print(result.pronunciations)
        print(result.espeak_str)

        # Test unknown word pronunciations
        result = system.ask(actor, GetWordPronunciations('raxacoricofallapatorius'))
        assert not result.in_dictionary
        assert len(result.pronunciations) > 0
        print(result.pronunciations)
        print(result.espeak_str)
    finally:
        # Shut down actor system
        system.shutdown()
