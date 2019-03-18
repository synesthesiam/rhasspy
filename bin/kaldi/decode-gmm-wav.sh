#!/usr/bin/env bash
if [[ -z "$3" ]]; then
    echo "Usage: decode-gmm-wav.sh <kaldi-dir> <model-dir> <wav-file>"
    exit 1
fi

kaldi_dir="$(realpath "$1")"
model_dir="$(realpath "$2")"
wav_file="$(realpath "$3")"

steps_dir="${kaldi_dir}/egs/wsj/s5/steps"
utils_dir="${kaldi_dir}/egs/wsj/s5/utils"

if [[ ! -d "${model_dir}/utils" ]]; then
    ln -s "${utils_dir}" "${model_dir}/utils"
fi

if [[ -d "${model_dir}/train" ]]; then
    # Use trained graph
    decode_dir="${model_dir}/train"
    graph_dir="${decode_dir}/graph"
    lang_dir="${decode_dir}/lang"
else
    # Use model graph
    decode_dir="${model_dir}/decode"
    graph_dir="${model_dir}/model/graph"
    lang_dir="${model_dir}/data/lang"
    if [[ ! -d "$decode_dir" ]]; then
        export PATH="${utils_dir}:$PATH"
        cd "${model_dir}" && \
            "${steps_dir}/online/nnet3/prepare_online_decoding.sh" \
                --mfcc-config "${model_dir}/conf/mfcc_hires.conf" \
                "${model_dir}/data/lang" \
                "${model_dir}/extractor" \
                "${model_dir}/model" \
                "${decode_dir}" || exit 1
    fi
fi

bin_dir="${kaldi_dir}/src/online2bin"

"${bin_dir}/online2-wav-gmm-latgen-faster" \
    "--config=${decode_dir}/conf/online.conf" \
    "--word-symbol-table=${lang_dir}/words.txt" \
    "--model=${decode_dir}/final.mdl" \
    "${graph_dir}/HCLG.fst" \
    'ark:echo utt1 utt1|' \
    "scp:echo utt1 ${wav_file}|" \
    'ark:/dev/null' #2>&1 | grep ^utt1 | cut -d' ' -f2-
