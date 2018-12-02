import os
import re
import subprocess
import tempfile
import logging
import gzip
import math
import wave
import itertools
import collections
from collections import defaultdict
from urllib.parse import urljoin

import requests

# -----------------------------------------------------------------------------

def load_phoneme_map(path):
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

def load_phoneme_examples(path):
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

def read_dict(dict_file, word_dict):
    """
    Loads a CMU word dictionary into an existing Python dictionary.
    """
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

# -----------------------------------------------------------------------------

def lookup_word(word, word_dict, profile, n=5):
    assert len(word) > 0, 'No word'

    # Dictionary uses upper-case letters
    stt_config = profile.speech_to_text
    if stt_config.get('dictionary_upper', False):
        word = word.upper()
    else:
        word = word.lower()

    pronounces = list(word_dict.get(word, []))
    in_dictionary = (len(pronounces) > 0)
    if not in_dictionary:
        # Guess pronunciation
        # Path to phonetisaurus FST
        g2p_path = profile.read_path(stt_config['g2p_model'])

        # FST was trained with upper-case letters
        if stt_config.get('g2p_upper', False):
            word = word.upper()
        else:
            word = word.lower()

        with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as pronounce_file:
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

            # Needed on Windows
            try:
                pronounce_file.close()
                os.unlink(pronounce_file.name)
            except:
                pass

    return {
        'in_dictionary': in_dictionary,
        'pronunciations': pronounces
    }

# -----------------------------------------------------------------------------

def lcm(*nums):
    """Returns the least common multiple of the given integers"""
    if len(nums) == 0:
        return 1

    nums_lcm = nums[0]
    for n in nums[1:]:
        nums_lcm = (nums_lcm*n) // math.gcd(nums_lcm, n)

    return nums_lcm

# -----------------------------------------------------------------------------

def open_maybe_gzip(path, mode_normal='r', mode_gzip='rt'):
    """Opens a file with gzip.open if it ends in .gz, otherwise normally with open"""
    if path.endswith('.gz'):
        return gzip.open(path, mode_gzip)

    return open(path, mode_normal)

# -----------------------------------------------------------------------------

def convert_wav(data):
    # Convert a WAV to 16-bit, 16Khz mono
    with tempfile.NamedTemporaryFile(suffix='.wav', mode='wb+', delete=False) as out_wav_file:
        with tempfile.NamedTemporaryFile(suffix='.wav', mode='wb', delete=False) as in_wav_file:
            in_wav_file.write(data)
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

            # Needed on Windows
            try:
                in_wav_file.close()
                os.unlink(in_wav_file.name)
            except:
                pass

        # Needed on Windows
        try:
            out_wav_file.close()
            os.unlink(out_wav_file.name)
        except:
            pass

# -----------------------------------------------------------------------------

group_matcher = re.compile(r'{(\w+)}')
optional_matcher = re.compile(r'\[([\w ]+)\] *')

def expand_sentences(sentences, classes=None, tags=False, slots=False):
    for sentence in sentences:
        if isinstance(sentence, collections.Mapping):
            fixed_values = sentence
            sentence = fixed_values.pop('_')
        else:
            fixed_values = {}

        parts = re.split(r'({\w+}|\[[\w\s]+\] *)', sentence)
        seqs = []

        for part in parts:
            part = part.strip()
            if len(part) == 0:
                continue

            group_match = group_matcher.match(part)
            optional_match = optional_matcher.match(part)

            # Normal part
            if group_match is None and optional_match is None:
                seqs.append((part,))
            # Group part
            elif group_match is not None:
                group = group_match.groups()[0]
                if classes is None:
                    # Upper-case group name
                    seqs.append([group.upper()])
                else:
                    # Expand out to class values
                    class_values = classes.get(group, [])
                    if tags:
                        # Markdown-style tags
                        seqs.append(['[%s](%s)' % (v, group)
                                     for v in class_values])
                    elif slots:
                        # Pass information about class group along
                        seqs.append(itertools.product(class_values, [group]))
                    else:
                        # Just the words
                        seqs.append(class_values)
            # Optional part
            elif optional_match is not None:
                seqs.append(('', optional_match.groups()[0]))

        for seq in itertools.product(*seqs):
            words = []
            group_values = defaultdict(list)

            for key, value in fixed_values.items():
                group_values[key].append(value)

            for item in seq:
                if isinstance(item, str):
                    words.append(item)
                else:
                    word, group = item
                    words.append(word)
                    group_values[group].append(word)

            seq_sent = ' '.join(word for word in words if len(word) > 0)
            if slots:
                yield seq_sent, group_values
            else:
                yield seq_sent

# -----------------------------------------------------------------------------

def send_intent(hass_config, intent):
    event_type_format = hass_config['event_type_format']
    event_type = event_type_format.format(intent['intent']['name'])
    post_url = urljoin(hass_config['url'], 'api/events/' + event_type)
    headers = {}

    if ('api_password' in hass_config) and \
       len(hass_config['api_password']) > 0:
        # Use API pasword
        headers['X-HA-Access'] = hass_config['api_password']
    elif 'HASSIO_TOKEN' in os.environ:
        # Use token from hass.io
        headers['Authorization'] = 'Bearer %s' % os.environ['HASSIO_TOKEN']

    slots = {}
    for entity in intent['entities']:
        slots[entity['entity']] = entity['value']

    # Add a copy of the event to the intent
    intent['hass_event'] = {
        'event_type': event_type,
        'event_data': slots
    }

    try:
        # Send to Home Assistant
        response = requests.post(post_url, headers=headers, json=slots)
        logging.debug('POSTed intent to %s with headers=%s' % (post_url, headers))

        response.raise_for_status()
    except Exception as e:
        logging.exception('send_intent')
        intent['error'] = str(e)

# -----------------------------------------------------------------------------

def extract_entities(phrase):
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
