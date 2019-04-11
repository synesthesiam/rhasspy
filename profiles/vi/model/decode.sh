#!/usr/bin/env bash
set -e

if [[ -z "$4" ]]; then
    echo "Usage: decode.sh <kaldi-dir> <model-dir> <graph-dir> <wav-file> [<wav-file> ...]"
    exit 1
fi

kaldi_dir="$(realpath "$1")"
model_dir="$(realpath "$2")"
graph_dir="$(realpath "$3")"
export PATH="${kaldi_dir}/src/featbin:${kaldi_dir}/src/gmmbin:$PATH"

# Rest of arguments should be WAV files
shift 3

log_file="${model_dir}/decode.log"
truncate --size 0 "${log_file}"

echo "${model_dir}/decode.sh \"${kaldi_dir}\" \"${model_dir}\" \"${graph_dir}\" $@" >> "${log_file}"
echo "PATH=${PATH}" >> "${log_file}"

temp_dir="$(mktemp -d)"
function finish {
    rm -rf "$temp_dir"
}

trap finish EXIT

# wav.scp
i=1
while [[ ! -z "$1" ]]; do
    echo "utt_${i} $(realpath "$1")" >> "${temp_dir}/wav.scp"
    shift
    ((i++))
done

# make_mfcc
compute-mfcc-feats \
    --config="${model_dir}/conf/mfcc.conf" \
    "scp:${temp_dir}/wav.scp" \
    "ark,scp:${temp_dir}/feats.ark,${temp_dir}/feats.scp" \
    >> "${log_file}" \
    2>&1

# cmvn
compute-cmvn-stats \
    "scp:${temp_dir}/feats.scp" \
    "ark,scp:${temp_dir}/cmvn.ark,${temp_dir}/cmvn.scp" \
    >> "${log_file}" \
    2>&1

# norm
apply-cmvn \
    "scp:${temp_dir}/cmvn.scp" \
    "scp:${temp_dir}/feats.scp" \
    "ark,scp:${temp_dir}/feats_cmvn.ark,${temp_dir}/feats_cmvn.scp" \
    >> "${log_file}" \
    2>&1

# add_deltas
add-deltas \
    "scp:${temp_dir}/feats_cmvn.scp" \
    "ark,scp:${temp_dir}/deltas.ark,${temp_dir}/deltas.scp" \
    >> "${log_file}" \
    2>&1

# decode
gmm-latgen-faster \
    --print-args=false \
    --word-symbol-table="${model_dir}/graph/words.txt" \
    "${model_dir}/model/final.mdl" \
    "${graph_dir}/HCLG.fst" \
    "scp:${temp_dir}/deltas.scp" \
    "ark,scp:${temp_dir}/lattices.ark,${temp_dir}/lattices.scp" \
    2>&1 | \
    tee -a "${log_file}" | \
    grep '^utt_' | \
    cut -d' ' -f2-

