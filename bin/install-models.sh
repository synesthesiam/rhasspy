#!/usr/bin/env bash
for lang in "$@"; do
    python3 -m spacy install $lang
done
