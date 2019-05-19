#!/usr/bin/env bash
set -e

if [[ -z "$(which phonetisaurus-train)" ]]; then
    echo "Phonetisaurus not installed!"
    exit 1
fi

if [[ -z "$2" ]]; then
    echo "Usage: make-g2p.sh DICTIONARY MODEL"
    exit 1
fi

dict_path="$(realpath "$1")"
model_path="$(realpath "$2")"

temp_dir="$(mktemp -d)"
function finish {
    rm -rf "${temp_dir}"
}

trap finish EXIT

cd "${temp_dir}"
perl -pe 's/\([0-9]+\)//;
            s/[ ]+/ /g; s/^[ ]+//;
            s/[ ]+$//; @_ = split (/[ ]+/);
            $w = shift (@_);
            $_ = $w."\t".join (" ", @_)."\n";' < "${dict_path}" | sed -e '/[_|\xA0]/d' > formatted.dict

phonetisaurus-train --lexicon formatted.dict --seq2_del --verbose
cp train/model.fst "${model_path}"
