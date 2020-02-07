"""Rhasspy utility functions."""
import collections
import gzip
import io
import itertools
import json
import logging
import math
import os
import random
import re
import subprocess
import threading
import wave
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Set, Tuple

import networkx as nx
import rhasspynlu

from num2words import num2words

WHITESPACE_PATTERN = re.compile(r"\s+")
_LOGGER = logging.getLogger(__name__)

# -----------------------------------------------------------------------------


class FunctionLoggingHandler(logging.Handler):
    """Calls a function for each logging message."""

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
    dict_file: Iterable[str],
    word_dict: Optional[Dict[str, List[str]]] = None,
    transform: Optional[Callable[[str], str]] = None,
    silence_words: Optional[Set[str]] = None,
) -> Dict[str, List[str]]:
    """
    Loads a CMU/Julius word dictionary, optionally into an existing Python dictionary.
    """
    if word_dict is None:
        word_dict = {}

    for i, line in enumerate(dict_file):
        line = line.strip()
        if not line:
            continue

        try:
            # Use explicit whitespace (avoid 0xA0)
            parts = re.split(r"[ \t]+", line)
            word = parts[0]

            # Skip Julius extras
            parts = [p for p in parts[1:] if p[0] not in ["[", "@"]]

            idx = word.find("(")
            if idx > 0:
                word = word[:idx]

            if "+" in word:
                # Julius format word1+word2
                words = word.split("+")
            else:
                words = [word]

            for word in words:
                # Don't transform silence words
                if transform and (
                    (silence_words is None) or (word not in silence_words)
                ):
                    word = transform(word)

                pronounce = " ".join(parts)

                if word in word_dict:
                    word_dict[word].append(pronounce)
                else:
                    word_dict[word] = [pronounce]
        except Exception as e:
            _LOGGER.warning("read_dict: %s (line %s)", e, i + 1)

    return word_dict


# -----------------------------------------------------------------------------


def lcm(*nums: int) -> int:
    """Returns the least common multiple of the given integers"""
    if not nums:
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
                if not v:
                    del new_dict[k]
            elif v == base_dict[k]:
                del new_dict[k]


# -----------------------------------------------------------------------------


def buffer_to_wav(buffer: bytes) -> bytes:
    """Wraps a buffer of raw audio data (16-bit, 16Khz mono) in a WAV"""
    with io.BytesIO() as wav_buffer:
        wav_file: wave.Wave_write = wave.open(wav_buffer, mode="wb")
        with wav_file:
            wav_file.setframerate(16000)
            wav_file.setsampwidth(2)
            wav_file.setnchannels(1)
            wav_file.writeframes(buffer)

        return wav_buffer.getvalue()


def convert_wav(wav_data: bytes, rate=16000, width=16, channels=1) -> bytes:
    """Converts WAV data to 16-bit, 16Khz mono with sox."""
    return subprocess.run(
        [
            "sox",
            "-t",
            "wav",
            "-",
            "-r",
            str(rate),
            "-e",
            "signed-integer",
            "-b",
            str(width),
            "-c",
            str(channels),
            "-t",
            "wav",
            "-",
        ],
        check=True,
        stdout=subprocess.PIPE,
        input=wav_data,
    ).stdout


def maybe_convert_wav(wav_data: bytes, rate=16000, width=16, channels=1) -> bytes:
    """Converts WAV data to 16-bit, 16Khz mono if necessary."""
    with io.BytesIO(wav_data) as wav_io:
        wav_file: wave.Wave_read = wave.open(wav_io, "rb")
        with wav_file:
            if (
                (wav_file.getframerate() != rate)
                or (wav_file.getsampwidth() != width)
                or (wav_file.getnchannels() != channels)
            ):
                return convert_wav(wav_data, rate=rate, width=width, channels=channels)

            return wav_file.readframes(wav_file.getnframes())


# -----------------------------------------------------------------------------


def load_phoneme_examples(path: str) -> Dict[str, Dict[str, str]]:
    """Loads example words and pronunciations for each phoneme."""
    examples = {}
    with open(path, "r") as example_file:
        for line in example_file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue  # skip blanks and comments

            parts = split_whitespace(line)
            examples[parts[0]] = {"word": parts[1], "phonemes": " ".join(parts[2:])}

    return examples


def load_phoneme_map(path: str) -> Dict[str, str]:
    """Load phoneme map from CMU (Sphinx) phonemes to eSpeak phonemes."""
    phonemes = {}
    with open(path, "r") as phoneme_file:
        for line in phoneme_file:
            line = line.strip()
            if not line or line.startswith("#"):
                continue  # skip blanks and comments

            parts = split_whitespace(line, maxsplit=1)
            phonemes[parts[0]] = parts[1]

    return phonemes


# -----------------------------------------------------------------------------


def empty_intent() -> Dict[str, Any]:
    """Get intent structure."""
    return {"text": "", "intent": {"name": "", "confidence": 0}, "entities": []}


# -----------------------------------------------------------------------------


class ByteStream:
    """Read/write file-like interface to a buffer."""

    def __init__(self) -> None:
        self.buffer = bytes()
        self.read_event = threading.Event()
        self.closed = False

    def read(self, n=-1) -> bytes:
        """Read some number of bytes."""
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
        """Write buffer."""
        if self.closed:
            return

        self.buffer += data
        self.read_event.set()

    def close(self) -> None:
        """Close stream."""
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
    tokens = [t for t in re.split(split_pattern, sentence) if t.strip()]

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
    """Group items from an interable."""
    args = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)


# -----------------------------------------------------------------------------


def make_sentences_by_intent(
    intent_graph: nx.DiGraph, num_samples: Optional[int] = None, extra_converters=None
) -> Dict[str, List[Dict[str, Any]]]:
    """Get all sentences from a graph."""

    # { intent: [ { 'text': ..., 'entities': { ... } }, ... ] }
    sentences_by_intent: Dict[str, Any] = defaultdict(list)

    start_node = None
    end_node = None
    for node, node_data in intent_graph.nodes(data=True):
        if node_data.get("start", False):
            start_node = node
        elif node_data.get("final", False):
            end_node = node

        if start_node and end_node:
            break

    assert (start_node is not None) and (
        end_node is not None
    ), "Missing start/end node(s)"

    if num_samples is not None:
        # Randomly sample
        paths = random.sample(
            list(nx.all_simple_paths(intent_graph, start_node, end_node)), num_samples
        )
    else:
        # Use generator
        paths = nx.all_simple_paths(intent_graph, start_node, end_node)

    # TODO: Add converters
    for path in paths:
        _, recognition = rhasspynlu.fsticuffs.path_to_recognition(
            path, intent_graph, extra_converters=extra_converters
        )
        assert recognition, "Path failed"
        sentences_by_intent[recognition.intent.name].append(recognition.asdict())

    return sentences_by_intent


# -----------------------------------------------------------------------------


def ppath(
    profile,
    profile_dir: Path,
    query: str,
    default: Optional[str] = None,
    write: bool = False,
) -> Optional[Path]:
    """Returns a Path from a profile or a default Path relative to the profile directory."""
    result = profile.get(query, default)
    if write:
        return Path(profile.write_path(result))

    return Path(profile.read_path(result))


# -----------------------------------------------------------------------------


def numbers_to_words(sentence: str, language: Optional[str] = None) -> str:
    """Replaces numbers with words in a sentence. Optionally substitues number back in."""
    if not language:
        # Default language
        language = None

    words = split_whitespace(sentence)
    changed = False
    for i, word in enumerate(words):
        try:
            number = float(word)

            # 75 -> seventy-five -> seventy five
            words[i] = re.sub(r"[-,]\s*", " ", num2words(number, lang=language))
            changed = True
        except ValueError:
            pass  # not a number
        except NotImplementedError:
            break  # unsupported language

    if not changed:
        return sentence

    return " ".join(words)


def split_whitespace(s: str, **kwargs):
    """Split a string by whitespace of any type/length."""
    return WHITESPACE_PATTERN.split(s, **kwargs)


# -----------------------------------------------------------------------------


def get_wav_duration(wav_bytes: bytes) -> float:
    """Return the real-time duration of a WAV file"""
    with io.BytesIO(wav_bytes) as wav_buffer:
        wav_file: wave.Wave_read = wave.open(wav_buffer, "rb")
        with wav_file:
            frames = wav_file.getnframes()
            rate = wav_file.getframerate()
            return frames / float(rate)


# -----------------------------------------------------------------------------


def hass_request_kwargs(
    hass_config: Dict[str, Any], pem_file: Optional[str] = None
) -> Dict[str, Any]:
    """Get arguments for HTTP interaction with Home Assistant."""
    headers = {}

    # Security stuff
    if ("access_token" in hass_config) and hass_config["access_token"]:
        # Use token from config
        headers["Authorization"] = f'Bearer {hass_config["access_token"]}'
    elif ("api_password" in hass_config) and hass_config["api_password"]:
        # Use API password (deprecated)
        headers["X-HA-Access"] = hass_config["api_password"]
    elif "HASSIO_TOKEN" in os.environ:
        # Use token from hass.io
        headers["Authorization"] = f'Bearer {os.environ["HASSIO_TOKEN"]}'

    kwargs: Dict[str, Any] = {"headers": headers}

    if pem_file is not None:
        kwargs["verify"] = pem_file

    return kwargs


# -----------------------------------------------------------------------------


def get_ini_paths(
    sentences_ini: Path, sentences_dir: Optional[Path] = None
) -> List[Path]:
    """Get paths to all .ini files in profile."""
    ini_paths: List[Path] = []
    if sentences_ini.is_file():
        ini_paths = [sentences_ini]

    # Add .ini files from intents directory
    if sentences_dir and sentences_dir.is_dir():
        for ini_path in sentences_dir.rglob("*.ini"):
            ini_paths.append(ini_path)

    return ini_paths


def get_all_intents(ini_paths: List[Path]) -> Dict[str, Any]:
    """Get intents from all .ini files in profile."""
    try:
        with io.StringIO() as combined_ini_file:
            for ini_path in ini_paths:
                combined_ini_file.write(ini_path.read_text())
                print("", file=combined_ini_file)

            return rhasspynlu.parse_ini(combined_ini_file.getvalue())
    except Exception:
        _LOGGER.exception("Failed to parse %s", ini_paths)

    return {}


# -----------------------------------------------------------------------------


class CliConverter:
    """Command-line converter for intent recognition"""

    def __init__(self, name: str, command_path: Path):
        self.name = name
        self.command_path = command_path

    def __call__(self, *args, converter_args=None):
        """Runs external program to convert JSON values"""
        converter_args = converter_args or []
        proc = subprocess.Popen(
            [str(self.command_path)] + converter_args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            universal_newlines=True,
        )

        with io.StringIO() as input_file:
            for arg in args:
                json.dump(arg, input_file)

            stdout, _ = proc.communicate(input=input_file.getvalue())

            return [json.loads(line) for line in stdout.splitlines() if line.strip()]


def load_converters(profile) -> Dict[str, Any]:
    # Load user-defined converters
    converters = {}

    converters_dir = Path(
        profile.read_path(profile.get("intent.fsticuffs.converters_dir", "converters"))
    )

    if converters_dir.is_dir():
        _LOGGER.debug("Loading converters from %s", converters_dir)
        for converter_path in converters_dir.glob("**/*"):
            if not converter_path.is_file():
                continue

            # Retain directory structure in name
            converter_name = str(
                converter_path.relative_to(converters_dir).with_suffix("")
            )

            # Run converter as external program.
            # Input arguments are encoded as JSON on individual lines.
            # Output values should be encoded as JSON on individual lines.
            converter = CliConverter(converter_name, converter_path)

            # Key off name without file extension
            converters[converter_name] = converter

            _LOGGER.debug("Loaded converter %s from %s", converter_name, converter_path)

    return converters
