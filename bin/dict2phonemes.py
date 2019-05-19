#!/usr/bin/env python3
import os
import argparse
import logging
import re
import random
import subprocess
import json
from collections import defaultdict, Counter
from concurrent.futures import ProcessPoolExecutor, as_completed

# -----------------------------------------------------------------------------

EXCLUDED = ["'", ",", "@", " "]
SINGLE_EXCLUDED = [":", "2", "#", ";"]
FIRST_EXCLUDED = [":"]

# -----------------------------------------------------------------------------


def main():
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser("dic2phonemes")
    parser.add_argument("dictionary", type=str, help="Path to CMU dictionary")
    parser.add_argument(
        "--espeak", type=str, default="espeak", help="Path to eSpeak binary"
    )
    parser.add_argument(
        "--samples", type=int, default=10000, help="Number of samples per phoneme set"
    )
    parser.add_argument("--hypin", type=str, help="Path to load hypotheses")
    parser.add_argument("--hypout", type=str, help="Path to save hypotheses")
    parser.add_argument("--voice", type=str, default="en", help="Voice for eSpeak")

    args = parser.parse_args()

    # Load dictionary
    word_dict = {}
    logging.info("Loading dictionary from %s" % args.dictionary)
    with open(args.dictionary, "r") as dict_file:
        read_dict(dict_file, word_dict)

    # Extract phonemes and associated words
    phonemes = set()
    phoneme_words = defaultdict(list)
    all_words = []
    for word, pronounces in word_dict.items():
        for phoneme_str in pronounces:
            for phoneme in re.split(r"[ ]+", phoneme_str):
                phonemes.add(phoneme)
                if len(word) > 1:
                    phoneme_words[phoneme].append(word)
                    all_words.append(word)

    assert len(phonemes) == len(phoneme_words), "Not enough words to cover phonemes"
    logging.debug("Phonemes: %s" % ", ".join(phoneme_words.keys()))

    phoneme_hyps = defaultdict(lambda: defaultdict(float))

    # Load previous hypotheses
    if args.hypin and os.path.exists(args.hypin):
        with open(args.hypin, "r") as hyp_file:
            hyp_dict = json.load(hyp_file)
            for phoneme, counts in hyp_dict.items():
                for hyp, count in counts.items():
                    phoneme_hyps[phoneme][hyp] = count

    # Sample words from the dictionary
    logging.info("Starting %s sample(s)" % args.samples)
    phoneme_futures = {}
    with ProcessPoolExecutor() as executor:
        # Schedule eSpeak word samples
        for i in range(args.samples):
            for phoneme in phonemes:
                word = random.choice(phoneme_words[phoneme])
                future = executor.submit(pronounce, word, voice=args.voice)
                phoneme_futures[future] = phoneme

        # Process pronounced words
        for i, future in enumerate(as_completed(phoneme_futures)):
            if i % len(phonemes) == 0:
                logging.info(
                    "Sample %s of %s" % ((i // len(phonemes) + 1), args.samples)
                )

            phoneme = phoneme_futures[future]
            word, espeak_str = future.result()
            if espeak_str is None:
                continue  # eSpeak failed

            last_char = None
            for char in espeak_str:
                # Ignore stress chars
                if char not in EXCLUDED:
                    hyps = []
                    if char not in SINGLE_EXCLUDED:
                        # Single
                        hyps.append(char)

                    if (last_char is not None) and (char not in FIRST_EXCLUDED):
                        # Double
                        hyps.append(last_char + char)

                    for hyp in hyps:
                        # Add to current phoneme
                        phoneme_hyps[phoneme][hyp] += 1 / len(word)

                    last_char = char

    # -------------------------------------------------------------------------

    # Find the "best" eSpeak phoneme for a given Sphinx phoneme
    best = {}
    todo = set(phonemes)
    used = set()
    while len(todo) > 0:
        for phoneme in list(todo):
            best_to_worst = sorted(
                phoneme_hyps[phoneme].items(), key=lambda kv: kv[1], reverse=True
            )

            for hyp, count in best_to_worst:
                if not hyp in used:
                    best[phoneme] = hyp
                    used.add(hyp)
                    todo.remove(phoneme)
                    break

    # Save all hypotheses
    if args.hypout:
        with open(args.hypout, "w") as hyp_file:
            json.dump(phoneme_hyps, hyp_file, indent=4)

    # Print results
    for phoneme, hyp in sorted(best.items()):
        print(phoneme, hyp)


# -----------------------------------------------------------------------------


def pronounce(word, voice="en", espeak="espeak"):
    espeak_str = None

    try:
        espeak_command = [espeak, "-x", "-q", "-v", voice, clean_word(word)]
        espeak_str = subprocess.check_output(espeak_command).decode().strip()
    except Exception as ex:
        logging.error(espeak_command)
        logging.exception(ex)

    return (word, espeak_str)


def clean_word(word):
    if word.startswith("-"):
        return word[1:]

    return word


def read_dict(dict_file, word_dict):
    """
    Loads a CMU word dictionary into an existing Python dictionary.
    """
    for line in dict_file:
        line = line.strip()
        if len(line) == 0:
            continue

        word, pronounce = re.split("[ ]+", line, maxsplit=1)
        idx = word.find("(")
        if idx > 0:
            word = word[:idx]

        pronounce = pronounce.strip()
        if word in word_dict:
            word_dict[word].append(pronounce)
        else:
            word_dict[word] = [pronounce]


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
