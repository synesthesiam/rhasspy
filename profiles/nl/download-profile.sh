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

echo "Downloading Dutch (nl) profile (sphinx)"

#------------------------------------------------------------------------------
# Acoustic Model
#------------------------------------------------------------------------------

acoustic_url='https://github.com/synesthesiam/rhasspy-profiles/releases/download/v1.0-nl/cmusphinx-nl-5.2.tar.gz'
acoustic_file="${download_dir}/cmusphinx-nl-5.2.tar.gz"
acoustic_output="${DIR}/acoustic_model"

if [[ ! -s "${acoustic_file}" ]]; then
    echo "Downloading acoustic model (${acoustic_url})"
    curl -sSfL -o "${acoustic_file}" "${acoustic_url}"
fi

echo "Extracting acoustic model (${acoustic_file})"
rm -rf "${acoustic_output}"
tar -C "${DIR}" -xf "${acoustic_file}" "cmusphinx-nl-5.2/model_parameters/voxforge_nl_sphinx.cd_cont_2000/" && mv "${DIR}/cmusphinx-nl-5.2/model_parameters/voxforge_nl_sphinx.cd_cont_2000/" "${acoustic_output}" && rm -rf "${DIR}/cmusphinx-nl-5.2" || exit 1

#------------------------------------------------------------------------------
# G2P
#------------------------------------------------------------------------------

g2p_url='https://github.com/synesthesiam/rhasspy-profiles/releases/download/v1.0-nl/nl-g2p.tar.gz'
g2p_file="${download_dir}/nl-g2p.tar.gz"
g2p_output="${DIR}/g2p.fst"

if [[ ! -s "${g2p_file}" ]]; then
    echo "Downloading g2p model (${g2p_url})"
    curl -sSfL -o "${g2p_file}" "${g2p_url}"
fi

echo "Extracting g2p model (${g2p_file})"
tar --to-stdout -xzf "${g2p_file}" 'g2p.fst' > "${g2p_output}" || exit 1

#------------------------------------------------------------------------------
# Dictionary
#------------------------------------------------------------------------------

dict_output="${DIR}/base_dictionary.txt"
echo "Extracting dictionary (${acoustic_file})"
tar --to-stdout -xzf "${acoustic_file}" 'cmusphinx-nl-5.2/etc/voxforge_nl_sphinx.dic' > "${dict_output}" || exit 1

#------------------------------------------------------------------------------
# Language Model
#------------------------------------------------------------------------------

lm_output="${DIR}/base_language_model.txt"
echo "Extracting language model (${acoustic_file})"
tar --to-stdout -xzf "${acoustic_file}" 'cmusphinx-nl-5.2/etc/voxforge_nl_sphinx.lm' > "${lm_output}" || exit 1

#------------------------------------------------------------------------------
# Snowboy
#------------------------------------------------------------------------------

snowboy_models=("snowboy.umdl" "computer.umdl")
for model_name in "${snowboy_models[@]}"; do
    model_output="${DIR}/${model_name}"
    if [[ ! -s "${model_output}" ]]; then
        model_url="https://github.com/Kitt-AI/snowboy/raw/master/resources/models/${model_name}"
        echo "Downloading ${model_output} (${model_url})"
        curl -sSfL -o "${model_output}" "${model_url}"
    fi
done

#------------------------------------------------------------------------------
# Mycroft Precise
#------------------------------------------------------------------------------

precise_files=("hey-mycroft-2.pb" "hey-mycroft-2.pb.params")
for file_name in "${precise_files[@]}"; do
    file_output="${DIR}/${file_name}"
    if [[ ! -s "${file_output}" ]]; then
        file_url="https://github.com/MycroftAI/precise-data/raw/models/${file_name}"
        echo "Downloading ${file_output} (${file_url})"
        curl -sSfL -o "${file_output}" "${file_url}"
    fi
done
