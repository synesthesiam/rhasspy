#!/usr/bin/env bash
set -e

if [[ -z "$1" ]]; then
    echo "Directory required as first argument"
    exit 1
fi

DIR="$1"
download_dir="${DIR}/download"

if [[ "$2" = "--delete" ]]; then
    rm -rf "${download_dir}"
fi

mkdir -p "${download_dir}"

echo "Downloading Vietnamese (vi) profile (kaldi)"

#------------------------------------------------------------------------------
# Acoustic Model
#------------------------------------------------------------------------------

acoustic_url='https://github.com/synesthesiam/rhasspy-profiles/releases/download/v1.0-vi/vietnamese.zip'

acoustic_file="${download_dir}/vietnamese.zip"
acoustic_output="${DIR}/model"

if [[ ! -s "${acoustic_file}" ]]; then
    echo "Downloading acoustic model"
    wget -q -O "${acoustic_file}" "${acoustic_url}"
fi

echo "Extracting acoustic model (${acoustic_file})"
rm -rf "${acoustic_output}"
mkdir -p "${acoustic_output}"
unzip -d "${DIR}" "${acoustic_file}" && mv "${DIR}/vietnamese" "${acoustic_output}" || exit 1

#------------------------------------------------------------------------------
# G2P
#------------------------------------------------------------------------------

g2p_url='https://github.com/synesthesiam/rhasspy-profiles/releases/download/v1.0-vi/vietnamese_g2p.zip'
g2p_file="${download_dir}/vietnamese_g2p.zip"
g2p_output="${DIR}/g2p.fst"

if [[ ! -s "${g2p_file}" ]]; then
    echo "Downloading g2p model"
    wget -q -O "${g2p_file}" "${g2p_url}"
fi

echo "Extracting g2p model (${g2p_file})"
unzip -p "${g2p_file}" 'VN/model.fst' > "${g2p_output}" || exit 1

#------------------------------------------------------------------------------
# Dictionary
#------------------------------------------------------------------------------

dict_output="${DIR}/base_dictionary.txt"

echo "Extracting dictionary (${g2p_file})"
unzip -p "${g2p_file}" 'VN/base.dict' > "${dict_output}" || exit 1

#------------------------------------------------------------------------------
# Language Model
#------------------------------------------------------------------------------

lm_url='https://github.com/synesthesiam/rhasspy-profiles/releases/download/v1.0-vi/VN.3gram.lm.gz'
lm_file="${download_dir}/VN.3gram.lm.gz"
lm_output="${DIR}/base_language_model.txt"

if [[ ! -s "${lm_file}" ]]; then
    echo "Downloading language model"
    wget -q -O "${lm_file}" "${lm_url}"
fi

echo "Extracting language model (${lm_file})"
zcat "${lm_file}" > "${lm_output}" || exit 1

#------------------------------------------------------------------------------
# Snowboy
#------------------------------------------------------------------------------

snowboy_models=("snowboy.umdl" "computer.umdl")
for model_name in "${snowboy_models[@]}"; do
    model_output="${DIR}/${model_name}"
    if [[ ! -s "${model_output}" ]]; then
        model_url="https://github.com/Kitt-AI/snowboy/raw/master/resources/models/${model_name}"
        echo "Downloading ${model_output} (${model_url})"
        wget -q -O "${model_output}" "${model_url}"
    fi
done
