#!/usr/bin/env bash
set -e

# Directory of *this* script
DIR="$( cd "$( dirname "$0" )" && pwd )"

# Place where downloaded artifacts are stored
download_dir="${DIR}/download"
mkdir -p "${download_dir}"

declare -A CPU_TO_FRIENDLY
CPU_TO_FRIENDLY["x86_64"]="amd64"
CPU_TO_FRIENDLY["armv7l"]="armhf"
CPU_TO_FRIENDLY["arm64v8"]="aarch64"

# CPU architecture
CPU_ARCHS=("x86_64" "armv7l" "arm64v8")
FRIENDLY_ARCHS=("amd64" "armhf" "aarch64")

if [[ ! -z "$1" ]]; then
    CPU_ARCHS=("$1")
    FRIENDLY_ARCHS=(${CPU_TO_FRIENDLY["$1"]})
fi

# -----------------------------------------------------------------------------
# OpenFST
# -----------------------------------------------------------------------------

for FRIENDLY_ARCH in "${FRIENDLY_ARCHS[@]}"; do
    openfst_file="${download_dir}/openfst_1.6.9-1_${FRIENDLY_ARCH}.deb"
    if [[ ! -f "${openfst_file}" ]]; then
        openfst_url="https://github.com/synesthesiam/docker-opengrm/releases/download/v1.3.4-${FRIENDLY_ARCH}/openfst_1.6.9-1_${FRIENDLY_ARCH}.deb"
        echo "Downloading OpenFST pre-built binary (${openfst_url})"
        curl -sSfL -o "${openfst_file}" "${openfst_url}"
    fi
done

# -----------------------------------------------------------------------------
# Pocketsphinx for Python
# -----------------------------------------------------------------------------

pocketsphinx_file="${download_dir}/pocketsphinx-python.tar.gz"
if [[ ! -f "${pocketsphinx_file}" ]]; then
    pocketsphinx_url='https://github.com/synesthesiam/pocketsphinx-python/releases/download/v1.0/pocketsphinx-python.tar.gz'
    echo "Downloading pocketsphinx (${pocketsphinx_url})"
    curl -sSfL -o "${pocketsphinx_file}" "${pocketsphinx_url}"
fi

# -----------------------------------------------------------------------------
# jsgf2fst
# -----------------------------------------------------------------------------

jsgf2fst_file="${download_dir}/jsgf2fst-0.1.0.tar.gz"
if [[ ! -f "${jsgf2fst_file}" ]]; then
    jsgf2fst_url='https://github.com/synesthesiam/jsgf2fst/releases/download/v0.1.0/jsgf2fst-0.1.0.tar.gz'
    echo "Downloading jsgf2fst (${jsgf2fst_url})"
    curl -sSfL -o "${jsgf2fst_file}" "${jsgf2fst_url}"
fi

# -----------------------------------------------------------------------------
# Snowboy
# -----------------------------------------------------------------------------

snowboy_file="${download_dir}/snowboy-1.3.0.tar.gz"
if [[ ! -f "${snowboy_file}" ]]; then
    snowboy_url='https://github.com/Kitt-AI/snowboy/archive/v1.3.0.tar.gz'
    echo "Downloading snowboy (${snowboy_url})"
    curl -sSfL -o "${snowboy_file}" "${snowboy_url}"
fi

# -----------------------------------------------------------------------------
# Mycroft Precise
# -----------------------------------------------------------------------------

for CPU_ARCH in "x86_64" "armv7l"
do
    precise_file="${download_dir}/precise-engine_0.3.0_${CPU_ARCH}.tar.gz"
    if [[ ! -f "${precise_file}" ]]; then
        precise_url="https://github.com/MycroftAI/mycroft-precise/releases/download/v0.3.0/precise-engine_0.3.0_${CPU_ARCH}.tar.gz"
        echo "Downloading Mycroft Precise (${precise_url})"
        curl -sSfL -o "${precise_file}" "${precise_url}"
    fi
done

# -----------------------------------------------------------------------------
# Opengrm
# -----------------------------------------------------------------------------

if [[ -z "$(which ngramcount)" ]]; then
    # Download source
    opengrm_file="${download_dir}/opengrm-ngram-1.3.3.tar.gz"
    if [[ ! -f "${opengrm_file}" ]]; then
        opengrm_url='https://www.opengrm.org/twiki/pub/GRM/NGramDownload/opengrm-ngram-1.3.3.tar.gz'
        echo "Download Opengrm (${opengrm_url})"
        curl -sSfLk -o "${opengrm_file}" "${opengrm_url}"
    fi

    # Download pre-built packages
    for FRIENDLY_ARCH in "${FRIENDLY_ARCHS[@]}"; do
        opengrm_file="${download_dir}/opengrm_1.3.4-1_${FRIENDLY_ARCH}.deb"
        if [[ ! -f "${opengrm_file}" ]]; then
            opengrm_url="https://github.com/synesthesiam/docker-opengrm/releases/download/v1.3.4-${FRIENDLY_ARCH}/opengrm_1.3.4-1_${FRIENDLY_ARCH}.deb"
            echo "Downloading opengrm pre-built binary (${opengrm_url})"
            curl -sSfL -o "${opengrm_file}" "${opengrm_url}"
        fi
    done
fi

# -----------------------------------------------------------------------------
# Phonetisaurus
# -----------------------------------------------------------------------------

for FRIENDLY_ARCH in "${FRIENDLY_ARCHS[@]}"
do
    # Install pre-built package
    phonetisaurus_file="${download_dir}/phonetisaurus-2019_${FRIENDLY_ARCH}.deb"
    if [[ ! -f "${phonetisaurus_file}" ]]; then
        phonetisaurus_url="https://github.com/synesthesiam/phonetisaurus-2019/releases/download/v1.0/phonetisaurus-2019_${FRIENDLY_ARCH}.deb"
        echo "Downloading phonetisaurus (${phonetisaurus_url})"
        curl -sSfL -o "${phonetisaurus_file}" "${phonetisaurus_url}"
    fi
done

# Build from source
phonetisaurus_file="${download_dir}/phonetisaurus-2019.zip"
if [[ ! -f "${phonetisaurus_file}" ]]; then
    phonetisaurus_url="https://github.com/synesthesiam/phonetisaurus-2019/releases/download/v1.0/phonetisaurus-2019_${FRIENDLY_ARCH}.deb"
    echo "Downloading phonetisaurus source (${phonetisaurus_url})"
    curl -sSfL -o "${phonetisaurus_file}" "${phonetisaurus_url}"
fi

# -----------------------------------------------------------------------------
# Kaldi
# -----------------------------------------------------------------------------

for FRIENDLY_ARCH in "${FRIENDLY_ARCHS[@]}"
do
    # Install pre-built package
    kaldi_file="${download_dir}/kaldi_${FRIENDLY_ARCH}.tar.gz"
    if [[ ! -f "${kaldi_file}" ]]; then
        kaldi_url="https://github.com/synesthesiam/kaldi-docker/releases/download/v1.0/kaldi_${FRIENDLY_ARCH}.tar.gz"
        echo "Downloading kaldi (${kaldi_url})"
        curl -sSfL -o "${kaldi_file}" "${kaldi_url}"
    fi
done

# -----------------------------------------------------------------------------

echo "Done"
