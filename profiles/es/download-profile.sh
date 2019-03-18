#!/usr/bin/env bash
DIR="$( cd "$( dirname "$0" )" && pwd )"
download_dir="${DIR}/download"
mkdir -p "${download_dir}"

echo "Downloading Spanish (es) profile (sphinx)"

#------------------------------------------------------------------------------
# Acoustic Model
#------------------------------------------------------------------------------

acoustic_url='https://github.com/synesthesiam/rhasspy-profiles/releases/download/v1.0-es/cmusphinx-es-5.2.tar.gz'
acoustic_file="${download_dir}/cmusphinx-es-5.2.tar.gz"
acoustic_output="${DIR}/acoustic_model"

if [[ ! -f "${acoustic_file}" ]]; then
    echo "Downloading acoustic model"
    wget -q -O "${acoustic_file}" "${acoustic_url}"
fi

echo "Extracting acoustic model (${acoustic_file})"
rm -rf "${acoustic_output}"
tar -xf "${acoustic_file}" "cmusphinx-es-5.2/model_parameters/voxforge_es_sphinx.cd_ptm_4000/" && mv "${DIR}/cmusphinx-es-5.2/model_parameters/voxforge_es_sphinx.cd_ptm_4000/" "${acoustic_output}" && rm -rf "${DIR}/cmusphinx-es-5.2" || exit 1

#------------------------------------------------------------------------------
# G2P
#------------------------------------------------------------------------------

g2p_url='https://github.com/synesthesiam/rhasspy-profiles/releases/download/v1.0-es/es-g2p.tar.gz'
g2p_file="${download_dir}/es-g2p.tar.gz"
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
echo "Extracting dictionary (${acoustic_file})"
tar --to-stdout -xf "${acoustic_file}" "cmusphinx-es-5.2/etc/voxforge_es_sphinx.dic" > "${dict_output}" || exit 1

#------------------------------------------------------------------------------
# Language Model
#------------------------------------------------------------------------------

lm_output="${DIR}/base_language_model.txt"
echo "Extracting language model (${acoustic_file})"
tar --to-stdout -xf "${acoustic_file}" "cmusphinx-es-5.2/etc/es-20k.lm.gz" | zcat > "${lm_output}" || exit 1
