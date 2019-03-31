#!/usr/bin/env bash
if [[ -z "$3" ]]; then
    echo "Usage: train-lm.sh <kaldi-dir> <model-dir> <lm-file>"
    exit 1
fi

kaldi_dir="$(realpath "$1")"
model_dir="$(realpath "$2")"
lm_in_file="$(realpath "$3")"

steps_dir="${kaldi_dir}/egs/wsj/s5/steps"
utils_dir="${kaldi_dir}/egs/wsj/s5/utils"
bin_dir="${kaldi_dir}/src/bin"
fstbin_dir="${kaldi_dir}/src/fstbin"
lmbin_dir="${kaldi_dir}/src/lmbin"

if [[ ! -d "${model_dir}/utils" ]]; then
    ln -s "${utils_dir}" "${model_dir}/utils"
fi

export PATH="${utils_dir}:${fstbin_dir}:${lmbin_dir}:${bin_dir}:$PATH"

# Prepare a training configuration
train_dir="${model_dir}/train"
if [[ -d "$train_dir" ]]; then
    rm -rf "${train_dir}"
    mkdir -p "${train_dir}"
fi

# Prepare the dictionary
cd "${model_dir}" && \
    "${utils_dir}/prepare_lang.sh" \
        --phone-symbol-table "${model_dir}/data/lang/phones.txt" \
        "${model_dir}/data/local/dict" \
        "" \
        "${train_dir}/dict_tmp" \
        "${train_dir}/dict" || exit 1

# Copy language model and gzip it
lm_out_file="${model_dir}/data/local/lang/language_model.lm.gz"
mkdir -p "$(dirname "${lm_out_file}")"
cat "${lm_in_file}" | gzip > "${lm_out_file}" || exit 1

# Format language model
cd "${model_dir}" && \
    "${utils_dir}/format_lm.sh" \
        "${train_dir}/dict" \
        "${lm_out_file}" \
        "${model_dir}/data/local/dict/lexicon.txt" \
        "${train_dir}/lang" || exit 1

# Generate FST graph
cd "${model_dir}" && \
    "${utils_dir}/mkgraph.sh" \
        "${train_dir}/lang" \
        "${model_dir}/model" \
        "${train_dir}/graph" || exit 1
