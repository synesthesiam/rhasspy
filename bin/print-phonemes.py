#!/usr/bin/env python3
import sys
import re

def main():
    if len(sys.argv) < 2:
        print('Usage: print-phonemes.py dictionary.txt')
        sys.exit(1)

    phonemes = set()
    with open(sys.argv[1], 'r') as dict_file:
        for line in dict_file:
            line = line.strip()
            if len(line) == 0:
                continue

            parts = re.split(r'\s+', line)
            phonemes.update(parts[1:])

        for phoneme in sorted(phonemes):
            print(phoneme)

if __name__ == '__main__':
    main()
