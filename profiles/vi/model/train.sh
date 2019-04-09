#!/usr/bin/env bash
set -e

if [[ -z "$4" ]]; then
    echo "Usage: train.sh <kaldi-dir> <model-dir> <dict-file> <lm-file>"
    exit 1
fi

kaldi_dir="$(realpath "$1")"
model_dir="$(realpath "$2")"
dict_file="$(realpath "$3")"
lm_file="$(realpath "$4")"

steps_dir="${kaldi_dir}/egs/wsj/s5/steps"
utils_dir="${kaldi_dir}/egs/wsj/s5/utils"
bin_dir="${kaldi_dir}/src/bin"
fstbin_dir="${kaldi_dir}/src/fstbin"
lmbin_dir="${kaldi_dir}/src/lmbin"

# Link utils, if missing
if [[ ! -d "${model_dir}/utils" ]]; then
    ln -s "${utils_dir}" "${model_dir}/utils"
fi

export PATH="${utils_dir}:${fstbin_dir}:${lmbin_dir}:${bin_dir}:$PATH"

log_file="${model_dir}/train.log"
truncate --size 0 "${log_file}"

echo "${model_dir}/train.sh \"${kaldi_dir}\" \"${model_dir}\" \"${dict_file}\" \"${lm_file}\"" >> "${log_file}"
echo "PATH=${PATH}" >> "${log_file}"

# Clean up
echo "Cleaning up" | tee -a "${log_file}"
"${model_dir}/clean.sh" \
    "${model_dir}" \
    2>&1 | tee -a "${log_file}"

# Lexicon
echo "Generating lexicon" | tee -a "${log_file}"
mkdir -p "${model_dir}/data/local/dict"
cp "${model_dir}"/phones/*.txt "${model_dir}/data/local/dict/"
cp "${dict_file}" "${model_dir}/data/local/dict/lexicon.txt"
cd "${model_dir}" && \
    utils/prepare_lang.sh \
        "${model_dir}/data/local/dict" '' \
        "${model_dir}/data/local/lang" "${model_dir}/data/lang" \
        2>&1 | tee -a "${log_file}"

# Language model
echo "Formatting language model" | tee -a "${log_file}"
cat "${lm_file}" | gzip --to-stdout > "${model_dir}/data/local/lang/lm.arpa.gz"
cd "${model_dir}" && \
    utils/format_lm.sh \
        "${model_dir}/data/lang" "${model_dir}/data/local/lang/lm.arpa.gz" \
        "${model_dir}/data/local/dict/lexicon.txt" "${model_dir}/data/lang" \
        2>&1 | tee -a "${log_file}"

# Graph
echo "Creating graph" | tee -a "${log_file}"
cd "${model_dir}" && \
    utils/mkgraph.sh \
        "${model_dir}/data/lang" \
        "${model_dir}/model" \
        "${model_dir}/graph" \
        2>&1 | tee -a "${log_file}"
