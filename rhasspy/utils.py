import os
import re
import io
import wave
import logging
import math
import itertools
import json
import gzip
import collections
from collections import defaultdict
import concurrent.futures
import threading
import tempfile
import subprocess
from typing import Dict, List, Iterable, Optional, Any, Mapping, Tuple

from jsgf2fst import fstprintall, symbols2intent
import pywrapfst as fst

# -----------------------------------------------------------------------------


class FunctionLoggingHandler(logging.Handler):
    def __init__(self, func):
        logging.Handler.__init__(self)
        self.func = func
        self.formatter = logging.Formatter(
            "[%(levelname)s:%(relativeCreated)d] %(name)s: %(message)s"
        )

    def handle(self, record):
        self.func(self.formatter.format(record))


# -----------------------------------------------------------------------------


def read_dict(
    dict_file: Iterable[str], word_dict: Optional[Dict[str, List[str]]] = None
) -> Dict[str, List[str]]:
    """
    Loads a CMU word dictionary, optionally into an existing Python dictionary.
    """
    if word_dict is None:
        word_dict = {}

    for line in dict_file:
        line = line.strip()
        if len(line) == 0:
            continue

        word, pronounce = re.split(r"\s+", line, maxsplit=1)
        idx = word.find("(")
        if idx > 0:
            word = word[:idx]

        pronounce = pronounce.strip()
        if word in word_dict:
            word_dict[word].append(pronounce)
        else:
            word_dict[word] = [pronounce]

    return word_dict


# -----------------------------------------------------------------------------


def lcm(*nums: int) -> int:
    """Returns the least common multiple of the given integers"""
    if len(nums) == 0:
        return 1

    nums_lcm = nums[0]
    for n in nums[1:]:
        nums_lcm = (nums_lcm * n) // math.gcd(nums_lcm, n)

    return nums_lcm


# -----------------------------------------------------------------------------


def recursive_update(base_dict: Dict[Any, Any], new_dict: Mapping[Any, Any]) -> None:
    """Recursively overwrites values in base dictionary with values from new dictionary"""
    for k, v in new_dict.items():
        if isinstance(v, collections.Mapping) and (k in base_dict):
            recursive_update(base_dict[k], v)
        else:
            base_dict[k] = v


def recursive_remove(base_dict: Dict[Any, Any], new_dict: Dict[Any, Any]) -> None:
    """Recursively removes values from new dictionary that are already in base dictionary"""
    for k, v in list(new_dict.items()):
        if k in base_dict:
            if isinstance(v, dict):
                recursive_remove(base_dict[k], v)
                if len(v) == 0:
                    del new_dict[k]
            elif v == base_dict[k]:
                del new_dict[k]


# -----------------------------------------------------------------------------


def buffer_to_wav(buffer: bytes) -> bytes:
    """Wraps a buffer of raw audio data (16-bit, 16Khz mono) in a WAV"""
    with io.BytesIO() as wav_buffer:
        with wave.open(wav_buffer, mode="wb") as wav_file:
            wav_file.setframerate(16000)
            wav_file.setsampwidth(2)
            wav_file.setnchannels(1)
            wav_file.writeframesraw(buffer)

        return wav_buffer.getvalue()


def convert_wav(wav_data: bytes) -> bytes:
    """Converts WAV data to 16-bit, 16Khz mono with sox."""
    return subprocess.run(
        [
            "sox",
            "-t",
            "wav",
            "-",
            "-r",
            "16000",
            "-e",
            "signed-integer",
            "-b",
            "16",
            "-c",
            "1",
            "-t",
            "wav",
            "-",
        ],
        check=True,
        stdout=subprocess.PIPE,
        input=wav_data,
    ).stdout


def maybe_convert_wav(wav_data: bytes) -> bytes:
    """Converts WAV data to 16-bit, 16Khz mono if necessary."""
    with io.BytesIO(wav_data) as wav_io:
        with wave.open(wav_io, "rb") as wav_file:
            rate, width, channels = (
                wav_file.getframerate(),
                wav_file.getsampwidth(),
                wav_file.getnchannels(),
            )
            if (rate != 16000) or (width != 2) or (channels != 1):
                return convert_wav(wav_data)
            else:
                return wav_file.readframes(wav_file.getnframes())


# -----------------------------------------------------------------------------


def load_phoneme_examples(path: str) -> Dict[str, Dict[str, str]]:
    """Loads example words and pronunciations for each phoneme."""
    examples = {}
    with open(path, "r") as example_file:
        for line in example_file:
            line = line.strip()
            if (len(line) == 0) or line.startswith("#"):
                continue  # skip blanks and comments

            parts = re.split("\s+", line)
            examples[parts[0]] = {"word": parts[1], "phonemes": " ".join(parts[2:])}

    return examples


def load_phoneme_map(path: str) -> Dict[str, str]:
    """Load phoneme map from CMU (Sphinx) phonemes to eSpeak phonemes."""
    phonemes = {}
    with open(path, "r") as phoneme_file:
        for line in phoneme_file:
            line = line.strip()
            if (len(line) == 0) or line.startswith("#"):
                continue  # skip blanks and comments

            parts = re.split("\s+", line, maxsplit=1)
            phonemes[parts[0]] = parts[1]

    return phonemes


# -----------------------------------------------------------------------------


def empty_intent() -> Dict[str, Any]:
    return {"text": "", "intent": {"name": "", "confidence": 0}, "entities": []}


# -----------------------------------------------------------------------------


class ByteStream:
    """Read/write file-like interface to a buffer."""

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

    def write(self, data: bytes) -> None:
        if self.closed:
            return

        self.buffer += data
        self.read_event.set()

    def close(self) -> None:
        self.closed = True
        self.read_event.set()


# -----------------------------------------------------------------------------


def sanitize_sentence(
    sentence: str, sentence_casing: str, replace_patterns: List[Any], split_pattern: Any
) -> Tuple[str, List[str]]:
    """Applies profile-specific casing and tokenization to a sentence.
    Returns the sanitized sentence and tokens."""

    if sentence_casing == "lower":
        sentence = sentence.lower()
    elif sentence_casing == "upper":
        sentence = sentence.upper()

    # Process replacement patterns
    for pattern_set in replace_patterns:
        for pattern, repl in pattern_set.items():
            sentence = re.sub(pattern, repl, sentence)

    # Tokenize
    tokens = [t for t in re.split(split_pattern, sentence) if len(t.strip()) > 0]

    return sentence, tokens


# -----------------------------------------------------------------------------


def open_maybe_gzip(path, mode_normal="r", mode_gzip=None):
    """Opens a file with gzip.open if it ends in .gz, otherwise normally with open"""
    if path.endswith(".gz"):
        if mode_gzip is None:
            if mode_normal == "r":
                mode_gzip = "rt"
            elif mode_normal == "w":
                mode_gzip = "wt"
            elif mode_normal == "a":
                mode_gzip = "at"

        return gzip.open(path, mode_gzip)

    return open(path, mode_normal)


# -----------------------------------------------------------------------------


def grouper(iterable, n, fillvalue=None):
    args = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)


# -----------------------------------------------------------------------------


def make_sentences_by_intent(intent_fst: fst.Fst) -> Dict[str, Any]:
    # { intent: [ { 'text': ..., 'entities': { ... } }, ... ] }
    sentences_by_intent: Dict[str, Any] = defaultdict(list)

    for symbols in fstprintall(intent_fst, exclude_meta=False):
        intent = symbols2intent(symbols)
        intent_name = intent["intent"]["name"]
        sentences_by_intent[intent_name].append(intent)

    return sentences_by_intent


# -----------------------------------------------------------------------------


def sample_sentences_by_intent(
    intent_fst_paths: Dict[str, str], num_samples: int
) -> Dict[str, Any]:
    def sample_sentences(intent_name: str, intent_fst_path: str):
        rand_fst = fst.Fst.read_from_string(
            subprocess.check_output(
                ["fstrandgen", f"--npath={num_samples}", intent_fst_path]
            )
        )

        sentences: List[Dict[str, Any]] = []
        for symbols in fstprintall(rand_fst, exclude_meta=False):
            intent = symbols2intent(symbols)
            intent_name = intent["intent"]["name"]
            sentences.append(intent)

        return sentences

    # Generate samples in parallel
    future_to_intent = {}
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for intent_name, intent_fst_path in intent_fst_paths.items():
            future = executor.submit(sample_sentences, intent_name, intent_fst_path)
            future_to_intent[future] = intent_name

    # { intent: [ { 'text': ..., 'entities': { ... } }, ... ] }
    sentences_by_intent: Dict[str, Any] = {}
    for future, intent_name in future_to_intent.items():
        sentences_by_intent[intent_name] = future.result()

    return sentences_by_intent
