#!/usr/bin/env python3
import sys
import os
from collections import defaultdict

from bs4 import BeautifulSoup
import requests

# This script downloads frequently used words in the supported languages.

def main():
    profiles_dir = sys.argv[1]
    languages = {
        'eng': 'en',
        'deu': 'de',
        'fra': 'fr',
        'spa': 'es',
        'ita': 'it',
        'nld': 'nl',
        'rus': 'ru',
        'vie': 'vi',
        'cmn': 'zh',
        'hin': 'hi',
        'ell': 'el'
    }

    for language in languages:
        profile_language = languages[language]
        html_path = os.path.join(profiles_dir, profile_language, 'frequent_words.html')

        if not os.path.exists(html_path):
            # Download
            url = 'https://www.ezglot.com/most-frequently-used-words.php?l={0}&submit=Select'.format(language)
            print(f'Downloading from {url}')

            with open(html_path, 'w') as html_file:
                # Download frequently used words in the given language
                page = requests.get(url).text
                html_file.write(page)
        else:
            # Load cached file
            with open(html_path, 'r') as html_file:
                page = html_file.read()

        # Process
        soup = BeautifulSoup(page, 'html5lib')
        file_path = os.path.join(profiles_dir, profile_language, 'frequent_words.txt')
        with open(file_path, 'w') as freq_file:
            for word_ul in soup.find_all(attrs={'class': 'topwords'}):
                for word_li in word_ul.findAll('li'):
                    word = word_li.text.strip().upper()
                    if len(word) < 3:
                        continue

                    print(word, file=freq_file)

        print(language)

# -----------------------------------------------------------------------------

if __name__ == '__main__':
    main()
