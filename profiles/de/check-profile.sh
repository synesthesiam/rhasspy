#!/usr/bin/env bash
set -e

if [[ -z "$1" ]]; then
    echo "Directory required as first argument"
    exit 1
fi

DIR="$1"

#------------------------------------------------------------------------------
# Acoustic Model
#------------------------------------------------------------------------------

acoustic_output="${DIR}/acoustic_model"

if [[ ! -d "${acoustic_output}" ]]; then
    echo "Missing acoustic model"
    exit 1
fi

#------------------------------------------------------------------------------
# G2P
#------------------------------------------------------------------------------

g2p_output="${DIR}/g2p.fst"

if [[ ! -s "${g2p_output}" ]]; then
    echo "Missing g2p model"
    exit 1
fi

#------------------------------------------------------------------------------
# Dictionary
#------------------------------------------------------------------------------

dict_output="${DIR}/base_dictionary.txt"

if [[ ! -s "${dict_output}" ]]; then
    echo "Missing base dictionary"
    exit 1
fi

#------------------------------------------------------------------------------
# Language Model
#------------------------------------------------------------------------------

lm_output="${DIR}/base_language_model.txt"

if [[ ! -s "${lm_output}" ]]; then
    echo "Missing base language model"
    exit 1
fi

#------------------------------------------------------------------------------
# Flair Embeddings
#------------------------------------------------------------------------------

flair_dir="${DIR}/flair/cache/embeddings"
flair_files=("lm-mix-german-forward-v0.2rc.pt" "lm-mix-german-backward-v0.2rc.pt")
for file_name in "${flair_files[@]}"; do
    file_output="${flair_dir}/${file_name}"
    if [[ ! -s "${file_output}" ]]; then
        echo "Missing flair embedding (${file_name})"
        exit 1
    fi
done
