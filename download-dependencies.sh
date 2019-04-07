#!/usr/bin/env bash

# Directory of *this* script
DIR="$( cd "$( dirname "$0" )" && pwd )"

# Place where downloaded artifacts are stored
download_dir="${DIR}/download"
mkdir -p "${download_dir}"

# CPU architecture
CPU_ARCHS="x86_64 armv7l arm64v8"
FRIENDLY_ARCHS="amd64 armhf aarch64"

# -----------------------------------------------------------------------------
# Pocketsphinx for Python
# -----------------------------------------------------------------------------

pocketsphinx_file="${download_dir}/pocketsphinx-python.tar.gz"
if [[ ! -f "${pocketsphinx_file}" ]]; then
    pocketsphinx_url='https://github.com/synesthesiam/pocketsphinx-python/releases/download/v1.0/pocketsphinx-python.tar.gz'
    echo "Downloading pocketsphinx (${pocketsphinx_url})"
    wget -q -O "${pocketsphinx_file}" "${pocketsphinx_url}"
fi

# -----------------------------------------------------------------------------
# PyJSGF
# -----------------------------------------------------------------------------

pyjsgf_file="${download_dir}/pyjsgf-1.6.0.tar.gz"
if [[ ! -f "${pyjsgf_file}" ]]; then
    pyjsgf_url='https://github.com/Danesprite/pyjsgf/archive/v1.6.0.tar.gz'
    echo "Downloading pyjsgf (${pyjsgf_url})"
    wget -q -O "${pyjsgf_file}" "${pyjsgf_url}"
fi

# -----------------------------------------------------------------------------
# Snowboy
# -----------------------------------------------------------------------------

snowboy_file="${download_dir}/snowboy-1.3.0.tar.gz"
if [[ ! -f "${snowboy_file}" ]]; then
    snowboy_url='https://github.com/Kitt-AI/snowboy/archive/v1.3.0.tar.gz'
    echo "Downloading snowboy (${snowboy_url})"
    wget -q -O "${snowboy_file}" "${snowboy_url}"
fi

# -----------------------------------------------------------------------------
# Mycroft Precise
# -----------------------------------------------------------------------------

for CPU_ARCH in CPU_ARCHES;
do
    precise_file="${download_dir}/precise-engine_0.2.0_${CPU_ARCH}.tar.gz"
    if [[ ! -f "${precise_file}" ]]; then
        precise_url="https://github.com/MycroftAI/mycroft-precise/releases/download/v0.2.0/precise-engine_0.2.0_${CPU_ARCH}.tar.gz"
        echo "Downloading Mycroft Precise (${precise_url})"
        wget -q -O "${precise_file}" "${precise_url}"
    fi
done

# -----------------------------------------------------------------------------
# MITLM
# -----------------------------------------------------------------------------

mitlm_file="${download_dir}/mitlm-0.4.2.tar.gz"
if [[ ! -f "${mitlm_file}" ]]; then
    mitlm_url='https://github.com/mitlm/mitlm/releases/download/v0.4.2/mitlm-0.4.2.tar.xz'
    echo "Download MITLM (${mitlm_url})"
    wget -q -O "${mitlm_file}" "${mitlm_url}"
fi

# -----------------------------------------------------------------------------
# Phonetisaurus
# -----------------------------------------------------------------------------

for CPU_ARCH in CPU_ARCHES;
do
    # Install pre-built package
    phonetisaurus_file="${download_dir}/phonetisaurus-2019_${FRIENDLY_ARCH}.deb"
    if [[ ! -f "${phonetisaurus_file}" ]]; then
        phonetisaurus_url="https://github.com/synesthesiam/phonetisaurus-2019/releases/download/v1.0/phonetisaurus-2019_${FRIENDLY_ARCH}.deb"
        echo "Downloading phonetisaurus (${phonetisaurus_url})"
        wget -q -O "${phonetisaurus_file}" "${phonetisaurus_url}"
    fi
done

# Build from source
openfst_file="${download_dir}/openfst-1.6.2.tar.gz"
if [[ ! -f "${openfst_file}" ]]; then
    openfst_url='http://www.openfst.org/twiki/pub/FST/FstDownload/openfst-1.6.2.tar.gz'
    echo "Downloading OpenFST source (${openfst_url})"
    wget -q -O "${openfst_file}" "${openfst_url}"
fi

phonetisaurus_file="${download_dir}/phonetisaurus-2019.zip"
if [[ ! -f "${phonetisaurus_file}" ]]; then
    phonetisaurus_url="https://github.com/synesthesiam/phonetisaurus-2019/releases/download/v1.0/phonetisaurus-2019_${FRIENDLY_ARCH}.deb"
    echo "Downloading phonetisaurus source (${phonetisaurus_url})"
    wget -q -O "${phonetisaurus_file}" "${phonetisaurus_url}"
fi

echo "Done"
