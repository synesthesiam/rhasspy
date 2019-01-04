import os
import re
import logging
import math
import itertools
import collections
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
