#!/usr/bin/env python3
import sys
import os
from collections import defaultdict

from bs4 import BeautifulSoup
import requests

# This script downloads frequently used words in the supported languages.

def main():
    profiles_dir = sys.argv[1]

    # Languages: eng, deu, fra, spa, ita, nld, rus
    languages = {
        'eng': 'en',
        'deu': 'de',
        'fra': 'fr',
        'spa': 'es',
        'ita': 'it',
        'nld': 'nl',
        'rus': 'ru' }

    for language in languages:
        url = 'https://www.ezglot.com/most-frequently-used-words.php?l={0}&submit=Select'.format(language)

        # Download frequently used words in the given language
        page = requests.get(url).text
        soup = BeautifulSoup(page, 'html.parser')

        file_path = os.path.join(profiles_dir, languages[language], 'frequent_words.txt')
        with open(file_path, 'w') as freq_file:
            for word_li in soup.find(attrs={'class': 'topwords'}).findAll('li'):
                word = word_li.text.strip().upper()
                if len(word) < 3:
                    continue

                print(word, file=freq_file)

        print(language)

# -----------------------------------------------------------------------------

if __name__ == '__main__':
    main()
