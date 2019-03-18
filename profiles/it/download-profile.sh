#!/usr/bin/env bash
DIR="$( cd "$( dirname "$0" )" && pwd )"
download_dir="${DIR}/download"
mkdir -p "${download_dir}"

echo "Downloading Italian (it) profile (sphinx)"

#------------------------------------------------------------------------------
# Acoustic Model
#------------------------------------------------------------------------------

acoustic_url='https://github.com/synesthesiam/rhasspy-profiles/releases/download/v1.0-it/cmusphinx-it-5.2.tar.gz'
acoustic_file="${download_dir}/cmusphinx-it-5.2.tar.gz"
acoustic_output="${DIR}/acoustic_model"

if [[ ! -f "${acoustic_file}" ]]; then
    echo "Downloading acoustic model"
    wget -q -O "${acoustic_file}" "${acoustic_url}"
fi

echo "Extracting acoustic model (${acoustic_file})"
rm -rf "${acoustic_output}"
tar -xf "${acoustic_file}" "cmusphinx-it-5.2/model_parameters/voxforge_it_sphinx.cd_cont_2000/" && mv "${DIR}/cmusphinx-it-5.2/model_parameters/voxforge_it_sphinx.cd_cont_2000/" "${acoustic_output}" && rm -rf "${DIR}/cmusphinx-it-5.2" || exit 1

#------------------------------------------------------------------------------
# G2P
#------------------------------------------------------------------------------

g2p_url='https://github.com/synesthesiam/rhasspy-profiles/releases/download/v1.0-it/it-g2p.tar.gz'
g2p_file="${download_dir}/it-g2p.tar.gz"
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
tar --to-stdout -xzf "${acoustic_file}" 'cmusphinx-it-5.2/etc/voxforge_it_sphinx.dic' > "${dict_output}" || exit 1


#------------------------------------------------------------------------------
# Language Model
#------------------------------------------------------------------------------

lm_output="${DIR}/base_language_model.txt"
echo "Extracting language model (${acoustic_file})"
tar --to-stdout -xzf "${acoustic_file}" 'cmusphinx-it-5.2/etc/voxforge_it_sphinx.lm' > "${lm_output}" || exit 1
