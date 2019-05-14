#!/usr/bin/env python3
import os
import sys
import re
import itertools
import argparse
import tempfile
import concurrent.futures
from collections import Counter, defaultdict
import subprocess

import pyparsing as pp


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("frequent_words", help="Path to text file with frequent words")
    parser.add_argument("dictionary", help="Path to CMU dictionary")
    parser.add_argument(
        "--frequent_phones", help="Path to eSpeak pronunciations for frequent words"
    )
    args = parser.parse_args()

    # Load frequent words
    with open(args.frequent_words, "r") as freq_file:
        words = set([line.strip().lower() for line in freq_file])

    # Find pronunciations for each frequently used word
    freq_phonemes = {}
    all_phonemes = set()
    with open(args.dictionary, "r") as dict_file:
        for line in dict_file:
            line = line.strip()
            if len(line) == 0:
                continue

            parts = re.split(r"\s+", line)
            word = parts[0].lower()

            if ("(" in word) or (word in freq_phonemes):
                continue

            # Record example words for each phoneme
            if word in words:
                pronunciation = parts[1:]
                freq_phonemes[word] = " ".join(pronunciation)
                all_phonemes.update(pronunciation)

    # Get eSpeak phones
    freq_espeak = {}
    if (args.frequent_phones is None) or not os.path.exists(args.frequent_phones):
        # Generate
        def get_espeak(word):
            phones = (
                subprocess.check_output(["espeak", "-q", "-x", word]).decode().strip()
            )
            return (word, phones)

        with concurrent.futures.ThreadPoolExecutor() as executor:
            freq_espeak = dict(executor.map(get_espeak, words))

        if args.frequent_phones is None:
            args.frequent_phones = os.path.splitext(args.frequent_words)[0] + ".phones"

        with open(args.frequent_phones, "w") as freq_phones_file:
            for word, phones in freq_espeak.items():
                print(word, phones, file=freq_phones_file)
    else:
        # Load from previous run
        with open(args.frequent_phones, "r") as freq_phones_file:
            for line in freq_phones_file:
                line = line.strip()
                if len(line) == 0:
                    continue

                parts = re.split(r"\s+", line, maxsplit=1)
                word = parts[0].lower()
                freq_espeak[word] = parts[1]

    # Generate possible mappings
    phoneme_counts = Counter()
    mappings = []
    bad_espeak = (":", ";", "-", "#")
    for word, espeak in freq_espeak.items():
        if not word in freq_phonemes:
            # No pronunciation
            continue

        phonemes = freq_phonemes[word].split()

        # Exclude emphasis, etc.
        espeak = [c for c in espeak if c not in ["'", ","]]

        if len(phonemes) == len(espeak):
            # Direct mapping
            context = {}
            for p, e in zip(phonemes, espeak):
                if e[0] in bad_espeak:
                    continue
                pe_ctx = dict(context)
                mappings.append([p, e, pe_ctx])
                context[p] = e
                phoneme_counts[(p, e)] += 1
        else:
            # Multiple possibilities
            possibilities = itertools.product(*[[(p, 1), (p, 2)] for p in phonemes])
            for possibility in possibilities:
                poss_len = sum(pl[1] for pl in possibility)
                if poss_len > len(espeak):
                    continue

                i = 0
                context = {}
                maybe_mappings = []
                maybe_counts = Counter()
                for p, l in possibility:
                    e = "".join(espeak[i : i + l])
                    if e[0] in bad_espeak:
                        continue
                    pe_ctx = dict(context)
                    maybe_mappings.append([p, e, pe_ctx])
                    context[p] = e
                    maybe_counts[(p, e)] += 1
                    i += l

                if i == len(espeak):
                    mappings.extend(maybe_mappings)
                    phoneme_counts += maybe_counts

    # Generate candidates
    sorted_phonemes = sorted(all_phonemes)
    candidates = defaultdict(list)
    n = 0
    m = 4
    for p in all_phonemes:
        candidate_counts = [
            (e, phoneme_counts[(cp, e)]) for (cp, e) in phoneme_counts.keys() if cp == p
        ]
        candidate_counts = [ec for ec in candidate_counts if ec[1] > n]
        candidate_counts = sorted(candidate_counts, key=lambda x: x[1], reverse=True)
        if len(candidate_counts) < m:
            candidates[p] = [ec[0] for ec in candidate_counts]
        else:
            candidates[p] = [ec[0] for ec in candidate_counts[:m]]

    # for p in all_phonemes:
    #     assert p in candidates, p

    # for p in sorted_phonemes:
    #     print(p, ", ".join(candidates[p]))

    # Write clingo file
    with tempfile.NamedTemporaryFile(
        suffix=".lp", mode="w+", delete=False
    ) as clingo_file:
        for p in sorted_phonemes:
            print(f'phoneme("{p}").', file=clingo_file)
        for p, es in candidates.items():
            for e in es:
                print(f'candidate("{p}", "{e}").', file=clingo_file)
                for (cp, ce), count in phoneme_counts.items():
                    if cp == p:
                        print(
                            f'candidate_count("{cp}", "{ce}", {count}).',
                            file=clingo_file,
                        )
                context_counts = Counter()
                for mp, me, pe_ctx in mappings:
                    if (mp == p) and (me == e):
                        for cp, ce in pe_ctx.items():
                            context_counts[(cp, ce)] += 1

                for (cp, ce), count in context_counts.items():
                    print(
                        f'context("{p}", "{e}", "{cp}", "{ce}", {count}).',
                        file=clingo_file,
                    )

        # -----

        print(
            """
0 { maybe_assign(P, E) } 1 :-
    candidate(P, E), phoneme(P).

assign(P, E) :- maybe_assign(P, E).

% All must be assigned
:- not assign(P, _), phoneme(P).

% No duplicate assignments
:- assign(P, E1), assign(P, E2),
   E1 != E2.

:- assign(P1, E), assign(P2, E),
   P1 != P2.

#maximize { S : candidate_count(P1, E1, C), context(P1, E1, P2, E2, N), assign(P1, E1), assign(P2, E2), S = C + N }.

#show assign/2.
#show score/1.
        """,
            file=clingo_file,
        )

        # Find optimal assignment
        parser = get_parser()
        clingo_file.seek(0)
        proc = subprocess.run(
            ["clingo", "-n0", "-t8", "--verbose=0", "--warn=none", clingo_file.name],
            stdout=subprocess.PIPE,
        )
        predicates = []
        for line in proc.stdout.splitlines():
            line = line.decode().strip()
            if len(line) == 0:
                continue
            elif line.startswith("OPTIMUM FOUND"):
                break
            else:
                try:
                    predicates = parser.parseString(line, parseAll=True).asList()
                except:
                    pass

        # Collect best assignment
        assignments = {}
        for assignment in predicates:
            if assignment[0] != "assign":
                continue

            # Phonemes are surrounded by double quotes
            assignments[assignment[1][1:-1]] = assignment[2][1:-1]

        # Print best assignment
        for p in sorted_phonemes:
            if p in assignments:
                print(p, assignments[p])
            else:
                print(f"Missing {p}")


# -----------------------------------------------------------------------------


def get_parser():
    identifier = pp.Combine(
        pp.Word(pp.alphas + "_", exact=1) + pp.Optional(pp.Word(pp.alphanums + "_"))
    )
    string = pp.quotedString
    number = pp.Combine(pp.Optional("-") + pp.Word(pp.nums))

    predicate = pp.Forward()
    atom = pp.Or([predicate, string, number])
    lpar = pp.Literal("(").suppress()
    rpar = pp.Literal(")").suppress()
    predicate <<= pp.Group(
        identifier.setResultsName("head")
        + pp.Optional(lpar + pp.delimitedList(atom).setResultsName("args") + rpar)
    )

    predicates = pp.OneOrMore(predicate)

    return predicates


# -----------------------------------------------------------------------------

if __name__ == "__main__":
    main()
