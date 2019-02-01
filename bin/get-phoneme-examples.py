#!/usr/bin/env python3
import sys
import re
from collections import defaultdict

from bs4 import BeautifulSoup
import requests

# This script downloads frequently used words in a language, looks up their
# pronunciations in a CMU dictionary, then prints an example word +
# pronunciation for each phoneme.

# Languages: eng, deu, fra, spa, ita, nld, rus

def main():
    # fra, deu, etc.
    language = sys.argv[1]

    # path to CMU dictionary
    dict_path = sys.argv[2]

    url = 'https://www.ezglot.com/most-frequently-used-words.php?l={0}&submit=Select'.format(language)

    # Download frequently used words in the given language
    page = requests.get(url).text
    soup = BeautifulSoup(page, 'html.parser')
    words = set()
    for word_li in soup.find(attrs={'class': 'topwords'}).findAll('li'):
        word = word_li.text.strip().upper()
        if len(word) == 0:
            continue

        words.add(word)

    # phoneme -> [(word, pronunciation), ...]
    examples = defaultdict(list)

    # Find pronunciations for each frequently used word
    with open(dict_path, 'r') as dict_file:
        for line in dict_file:
            line = line.strip()
            if len(line) == 0:
                continue

            parts = re.split(r'\s+', line)
            word = parts[0]

            if '(' in word:
                word = word[:word.index('(')]

            # Record example words for each phoneme
            upper_word = word.upper()
            if upper_word in words:
                pronunciation = parts[1:]
                for phoneme in pronunciation:
                    examples[phoneme].append((word, pronunciation))

    # Pick unique example words for every phoneme
    used_words = set()
    for phoneme in sorted(examples.keys()):
        # Choose the shortest, unused example word for this phoneme
        for word, pron in sorted(examples[phoneme], key=lambda kv: len(kv[0])):
            if len(word) > 2 and (not word in used_words):
                # Output format is:
                # phoneme word pronunciation
                print(phoneme, word, ' '.join(pron))
                used_words.add(word)
                break

# -----------------------------------------------------------------------------

if __name__ == '__main__':
    main()
