import os
import re
import io
import wave
import logging
import math
import itertools
import collections
from collections import defaultdict
import threading
import tempfile
import subprocess
from typing import Dict, List, Iterable, Optional, Any, Mapping, Tuple

# -----------------------------------------------------------------------------

SBI_TYPE = Dict[str, List[Tuple[str, List[Tuple[str, str]], List[str]]]]

# -----------------------------------------------------------------------------

def read_dict(dict_file: Iterable[str],
              word_dict: Optional[Dict[str, List[str]]] = None) -> Dict[str, List[str]]:
    '''
    Loads a CMU word dictionary, optionally into an existing Python dictionary.
    '''
    if word_dict is None:
        word_dict = {}

    for line in dict_file:
        line = line.strip()
        if len(line) == 0:
            continue

        word, pronounce = re.split(r'\s+', line, maxsplit=1)
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

def lcm(*nums:int) -> int:
    '''Returns the least common multiple of the given integers'''
    if len(nums) == 0:
        return 1

    nums_lcm = nums[0]
    for n in nums[1:]:
        nums_lcm = (nums_lcm*n) // math.gcd(nums_lcm, n)

    return nums_lcm

# -----------------------------------------------------------------------------

def recursive_update(base_dict: Dict[Any, Any],
                     new_dict: Mapping[Any, Any]) -> None:
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

    def match(m) -> str:
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

def convert_wav(wav_data: bytes) -> bytes:
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

def maybe_convert_wav(wav_data: bytes) -> bytes:
    '''Converts WAV data to 16-bit, 16Khz mono if necessary.'''
    with io.BytesIO(wav_data) as wav_io:
        with wave.open(wav_io, 'rb') as wav_file:
            rate, width, channels = wav_file.getframerate(), wav_file.getsampwidth(), wav_file.getnchannels()
            if (rate != 16000) or (width != 2) or (channels != 1):
                return convert_wav(wav_data)
            else:
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
        'intent': { 'name': '', 'confidence': 0 },
        'entities': {}
    }

# -----------------------------------------------------------------------------

class ByteStream:
    '''Read/write file-like interface to a buffer.'''
    def __init__(self) -> None:
        self.buffer = bytes()
        self.read_event = threading.Event()
        self.closed = False

    def read(self, n=-1) -> bytes:
        # Block until enough data is available
        while len(self.buffer) < n:
            if not self.closed:
                self.read_event.wait()
            else:
                self.buffer += bytearray(n - len(self.buffer))

        chunk = self.buffer[:n]
        self.buffer = self.buffer[n:]

        return chunk

    def write(self, data:bytes) -> None:
        if self.closed:
            return

        self.buffer += data
        self.read_event.set()

    def close(self) -> None:
        self.closed = True
        self.read_event.set()

# -----------------------------------------------------------------------------

def sanitize_sentence(sentence:str,
                      sentence_casing:str,
                      replace_patterns:List[Any],
                      split_pattern:Any) -> Tuple[str, List[str]]:
    '''Applies profile-specific casing and tokenization to a sentence.
    Returns the sanitized sentence and tokens.'''

    if sentence_casing == 'lower':
        sentence = sentence.lower()
    elif sentence_casing == 'upper':
        sentence = sentence.upper()

    # Process replacement patterns
    for pattern_set in replace_patterns:
        for pattern, repl in pattern_set.items():
            sentence = re.sub(pattern, repl, sentence)

    # Tokenize
    tokens = [t for t in re.split(split_pattern, sentence)
              if len(t.strip()) > 0]

    return sentence, tokens

def group_sentences_by_intent(tagged_sentences: Dict[str, List[str]],
                              *sanitize_args) -> SBI_TYPE:
    sentences_by_intent: SBI_TYPE = defaultdict(list)

    # Extract entities from tagged sentences
    for intent_name, intent_sents in tagged_sentences.items():
        for intent_sent in intent_sents:
            # Template -> untagged sentence + entities
            sentence, entities = extract_entities(intent_sent)

            # Split sentence into words (tokens)
            sentence, tokens = sanitize_sentence(sentence, *sanitize_args)
            sentences_by_intent[intent_name].append((sentence, entities, tokens))

    return sentences_by_intent
