#!/usr/bin/env python3
import sys
import re
import argparse
from collections import defaultdict

# This script loads frequently used words in a language, looks up their
# pronunciations in a CMU dictionary, then prints an example word +
# pronunciation for each phoneme.


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("frequent_words", help="Path to text file with frequent words")
    parser.add_argument("dictionary", help="Path to CMU dictionary")
    args = parser.parse_args()

    # Download frequently used words in the given language
    with open(args.frequent_words, "r") as word_file:
        words = set([w.strip().upper() for w in word_file.read().splitlines()])

    # phoneme -> [(word, pronunciation), ...]
    examples = defaultdict(list)

    # Find pronunciations for each frequently used word
    with open(args.dictionary, "r") as dict_file:
        for line in dict_file:
            line = line.strip()
            if len(line) == 0:
                continue

            parts = re.split(r"[\t ]+", line)
            word = parts[0]

            if "(" in word:
                word = word[: word.index("(")]

            # Record example words for each phoneme
            upper_word = word.upper()
            if upper_word in words:
                pronunciation = parts[1:]
                for phoneme in pronunciation:
                    examples[phoneme].append((word, pronunciation))

    # Pick unique example words for every phoneme
    used_words = set()
    for phoneme in sorted(examples.keys()):
        # Choose the shortest, unused example word for this phoneme.
        # Exclude words with 3 or fewer letters.
        for word, pron in sorted(examples[phoneme], key=lambda kv: len(kv[0])):
            if len(word) > 3 and (not word in used_words):
                # Output format is:
                # phoneme word pronunciation
                print(phoneme, word, " ".join(pron))
                used_words.add(word)
                break


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
