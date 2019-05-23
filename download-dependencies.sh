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
if [[ -z "$1" ]]; then
    CPU_ARCHS=("x86_64" "armv7l" "arm64v8")
    FRIENDLY_ARCHS=("amd64" "armhf" "aarch64")
else
    CPU_ARCHS=("$1")
    FRIENDLY_ARCHS=("${CPU_TO_FRIENDLY[$1]}")
fi

# -----------------------------------------------------------------------------
# Rhasspy
# -----------------------------------------------------------------------------

for FRIENDLY_ARCH in "${FRIENDLY_ARCHS[@]}";
do
    rhasspy_files=("rhasspy-tools_${FRIENDLY_ARCH}.tar.gz" "rhasspy-web-dist.tar.gz")
    for rhasspy_file_name in "${rhasspy_files}"; do
        rhasspy_file="${download_dir}/${rhasspy_file_name}"
        if [[ ! -f "${rhasspy_file}" ]]; then
            rhasspy_file_url="https://github.com/synesthesiam/rhasspy/releases/download/v2.0/${rhasspy_file_name}"
            echo "Downloading ${rhasspy_file} (${rhasspy_file_url})"
            curl -sSfL -o "${rhasspy_file}" "${rhasspy_file_url}"
        fi
    done
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

for CPU_ARCH in "${CPU_ARCHS}";
do
    case $CPU_ARCH in
        x86_64|armv7l)
            precise_file="${download_dir}/precise-engine_0.3.0_${CPU_ARCH}.tar.gz"
            if [[ ! -f "${precise_file}" ]]; then
                precise_url="https://github.com/MycroftAI/mycroft-precise/releases/download/v0.3.0/precise-engine_0.3.0_${CPU_ARCH}.tar.gz"
                echo "Downloading Mycroft Precise (${precise_url})"
                curl -sSfL -o "${precise_file}" "${precise_url}"
            fi
    esac
done

# -----------------------------------------------------------------------------
# Kaldi
# -----------------------------------------------------------------------------

for FRIENDLY_ARCH in "${FRIENDLY_ARCHS}"
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
# Web Interface
# -----------------------------------------------------------------------------

rhasspy_web_file="${download_dir}/rhasspy-web-dist.tar.gz"
rhasspy_web_url="https://github.com/synesthesiam/rhasspy/releases/download/v2.0/rhasspy-web-dist.tar.gz"
echo "Downloading web interface (${rhasspy_web_url})"
curl -sSfL -o "${rhasspy_web_file}" "${rhasspy_web_url}"


# -----------------------------------------------------------------------------

echo "Done"
