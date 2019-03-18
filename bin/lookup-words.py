#!/usr/bin/env python3
import sys
import os
import re
import subprocess
from collections import defaultdict

# This script downloads frequently used words in the supported languages.

def main():
    words = set()
    for line in sys.stdin:
        line = line.strip().upper()
        words.add(line)

    # path to CMU dictionary
    dict_path = sys.argv[1]

    with open(dict_path, 'r') as dict_file:
        for line in dict_file:
            line = line.strip()
            if len(line) == 0:
                continue

            parts = re.split(r'\s+', line)
            word = parts[0].upper()
            if word in words:
                espeak_phones = subprocess.check_output(['espeak', '-x', '-q', word]).decode().strip()
                print(word, espeak_phones, ' '.join(parts[1:]))
                words.remove(word)

# -----------------------------------------------------------------------------

if __name__ == '__main__':
    main()
