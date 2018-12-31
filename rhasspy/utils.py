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
from typing import Mapping, List, Iterable, Optional, Any

import requests

# -----------------------------------------------------------------------------

def read_dict(dict_file: Iterable[str],
              word_dict: Optional[Mapping[str, List[str]]] = None):
    """
    Loads a CMU word dictionary, optionally into an existing Python dictionary.
    """
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

def recursive_update(base_dict: Mapping[Any, Any], new_dict: Mapping[Any, Any]):
    for k, v in new_dict.items():
        if isinstance(v, collections.Mapping) and (k in base_dict):
            recursive_update(base_dict[k], v)
        else:
            base_dict[k] = v

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

    if ('access_token' in hass_config) and \
         len(hass_config['access_token']) > 0:
        # Use token from config
        headers['Authorization'] = 'Bearer %s' % hass_config['access_token']
    elif 'HASSIO_TOKEN' in os.environ:
        # Use token from hass.io
        headers['Authorization'] = 'Bearer %s' % os.environ['HASSIO_TOKEN']
    elif ('api_password' in hass_config) and \
       len(hass_config['api_password']) > 0:
        # Use API pasword
        headers['X-HA-Access'] = hass_config['api_password']

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

