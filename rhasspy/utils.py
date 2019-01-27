import os
import re
import io
import wave
import logging
import math
import itertools
import collections
import threading
import tempfile
import subprocess
from typing import Dict, List, Iterable, Optional, Any, Mapping, Tuple

# -----------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------

def read_dict(dict_file: Iterable[str],
              word_dict: Optional[Dict[str, List[str]]] = None):
    '''
    Loads a CMU word dictionary, optionally into an existing Python dictionary.
    '''
    if word_dict is None:
        word_dict = {}

    for line in dict_file:
        line = line.strip()
        if len(line) == 0:
            continue

        word, pronounce = re.split('\s+', line, maxsplit=1)
        idx = word.find('(')
        if idx > 0:
            word = word[:idx]

        pronounce = pronounce.strip()
        if word in word_dict:
            word_dict[word].append(pronounce)
        else:
            word_dict[word] = [pronounce]

    return word_dict

# -----------------------------------------------------------------------------

def lcm(*nums):
    '''Returns the least common multiple of the given integers'''
    if len(nums) == 0:
        return 1

    nums_lcm = nums[0]
    for n in nums[1:]:
        nums_lcm = (nums_lcm*n) // math.gcd(nums_lcm, n)

    return nums_lcm

# -----------------------------------------------------------------------------

def recursive_update(base_dict: Dict[Any, Any], new_dict: Mapping[Any, Any]):
    '''Recursively overwrites values in base dictionary with values from new dictionary'''
    for k, v in new_dict.items():
        if isinstance(v, collections.Mapping) and (k in base_dict):
            recursive_update(base_dict[k], v)
        else:
            base_dict[k] = v

# -----------------------------------------------------------------------------

def extract_entities(phrase: str) -> Tuple[str, List[Tuple[str, str]]]:
    '''Extracts embedded entity markings from a phrase.
    Returns the phrase with entities removed and a list of entities.

    The format [some text](entity name) is used to mark entities in a training phrase.

    If the synonym format [some text](entity name:something else) is used, then
    "something else" will be substituted for "some text".
    '''
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

# -----------------------------------------------------------------------------

def buffer_to_wav(buffer: bytes) -> bytes:
    '''Wraps a buffer of raw audio data (16-bit, 16Khz mono) in a WAV'''
    with io.BytesIO() as wav_buffer:
        with wave.open(wav_buffer, mode='wb') as wav_file:
            wav_file.setframerate(16000)
            wav_file.setsampwidth(2)
            wav_file.setnchannels(1)
            wav_file.writeframesraw(buffer)

        return wav_buffer.getvalue()

def convert_wav(cls, wav_data: bytes) -> bytes:
    '''Converts WAV data to 16-bit, 16Khz mono with sox.'''
    with tempfile.NamedTemporaryFile(suffix='.wav', mode='wb+') as out_wav_file:
        with tempfile.NamedTemporaryFile(suffix='.wav', mode='wb') as in_wav_file:
            in_wav_file.write(wav_data)
            in_wav_file.seek(0)
            subprocess.check_call(['sox',
                                    in_wav_file.name,
                                    '-r', '16000',
                                    '-e', 'signed-integer',
                                    '-b', '16',
                                    '-c', '1',
                                    out_wav_file.name])

            out_wav_file.seek(0)

            # Return converted data
            with wave.open(out_wav_file.name, 'rb') as wav_file:
                return wav_file.readframes(wav_file.getnframes())

# -----------------------------------------------------------------------------

def load_phoneme_examples(path: str) -> Dict[str, Dict[str, str]]:
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

def load_phoneme_map(path: str) -> Dict[str, str]:
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

# -----------------------------------------------------------------------------

def empty_intent() -> Dict[str, Any]:
    return {
        'text': '',
        'intent': { 'name': '' },
        'entities': {}
    }

class ByteStream:
    '''Read/write file-like interface to a buffer.'''
    def __init__(self):
        self.buffer = bytes()
        self.event = threading.Event()
        self.closed = False

    def read(self, n=-1):
        # Block until enough data is available
        while len(self.buffer) < n:
            if not self.closed:
                self.event.wait()
            else:
                self.buffer += bytearray(n - len(self.buffer))

        chunk = self.buffer[:n]
        self.buffer = self.buffer[n:]
        return chunk

    def write(self, data):
        if self.closed:
            return

        self.buffer += data
        self.event.set()

    def close(self):
        self.closed = True
        self.event.set()
