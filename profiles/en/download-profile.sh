#!/usr/bin/env bash
DIR="$( cd "$( dirname "$0" )" && pwd )"
download_dir="${DIR}/download"
mkdir -p "${download_dir}"

echo "Downloading English (en) profile (sphinx)"

#------------------------------------------------------------------------------
# Acoustic Model
#------------------------------------------------------------------------------

acoustic_url='https://github.com/synesthesiam/rhasspy-profiles/releases/download/v1.0-en/cmusphinx-en-us-5.2.tar.gz'

acoustic_file="${download_dir}/cmusphinx-en-us-5.2.tar.gz"
acoustic_output="${DIR}/acoustic_model"

if [[ ! -f "${acoustic_file}" ]]; then
    echo "Downloading acoustic model"
    wget -q -O "${acoustic_file}" "${acoustic_url}"
fi

echo "Extracting acoustic model (${acoustic_file})"
rm -rf "${acoustic_output}"
tar -xzf "${acoustic_file}" -C "${DIR}" && mv "${DIR}/cmusphinx-en-us-5.2" "${acoustic_output}" || exit 1

#------------------------------------------------------------------------------
# G2P
#------------------------------------------------------------------------------

g2p_url='https://github.com/synesthesiam/rhasspy-profiles/releases/download/v1.0-en/en-g2p.tar.gz'
g2p_file="${download_dir}/en-g2p.tar.gz"
g2p_output="${DIR}/g2p.fst"

if [[ ! -f "${g2p_file}" ]]; then
    echo "Downloading g2p model"
    wget -q -O "${g2p_file}" "${g2p_url}"
fi

echo "Extracting g2p model (${g2p_file})"
tar --to-stdout -xzf "${g2p_file}" 'g2p.fst' > "${g2p_output}" || exit 1

#------------------------------------------------------------------------------
# Dictionary
#------------------------------------------------------------------------------

dict_output="${DIR}/base_dictionary.txt"

echo "Extracting dictionary (${g2p_file})"
tar --to-stdout -xzf "${g2p_file}" 'base_dictionary.txt' > "${dict_output}" || exit 1

#------------------------------------------------------------------------------
# Language Model
#------------------------------------------------------------------------------

lm_url='https://github.com/synesthesiam/rhasspy-profiles/releases/download/v1.0-en/en-70k-0.2-pruned.lm.gz'
lm_file="${download_dir}/en-70k-0.2-pruned.lm.gz"
lm_output="${DIR}/base_language_model.txt"

if [[ ! -f "${lm_file}" ]]; then
    echo "Downloading language model"
    wget -q -O "${lm_file}" "${lm_url}"
fi

echo "Extracting language model (${lm_file})"
zcat "${lm_file}" > "${lm_output}" || exit 1
