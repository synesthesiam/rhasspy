#!/usr/bin/env bash
if [[ -z "$1" ]]; then
    echo "Usage: get-ipa-examples.sh phoneme_examples.txt"
    exit 1
fi

paste -d' ' \
      <(cut -d' ' -f1-2 "$1") \
      <(cut -d' ' -f2 "$1" | \
            xargs -n1 rhasspy/lexconvert.py --phones unicode-ipa {})
