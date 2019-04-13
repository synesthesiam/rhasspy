#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "$0" )" && pwd )"
download_dir="${DIR}/download"

echo "Checking Vietnamese (vi) profile (kaldi)"

#------------------------------------------------------------------------------
# Acoustic Model
#------------------------------------------------------------------------------

acoustic_output="${DIR}/model/model"

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

echo "OK"
