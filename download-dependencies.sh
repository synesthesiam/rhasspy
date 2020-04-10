#!/usr/bin/env bash
this_dir="$( cd "$( dirname "$0" )" && pwd )"
cpu_arch=$(uname --m)

# -----------------------------------------------------------------------------
# Command-line Arguments
# -----------------------------------------------------------------------------

. "${this_dir}/etc/shflags"

DEFINE_string 'download-dir' "${this_dir}/download" 'Directory to cache downloaded files'
DEFINE_boolean 'precise' true 'Install Mycroft Precise'
DEFINE_boolean 'kaldi' true 'Install Kaldi'
DEFINE_boolean 'web' true "Install web UI"
DEFINE_boolean 'offline' false "Don't download anything"
DEFINE_boolean 'all-cpu' false 'Download dependencies for all CPU architectures'
DEFINE_string 'cpu-arch' "${cpu_arch}" 'CPU architecture (x86_64, armv7l, arm64v8, armv6l)'

FLAGS "$@" || exit $?
eval set -- "${FLAGS_ARGV}"

# -----------------------------------------------------------------------------
# Default Settings
# -----------------------------------------------------------------------------

set -e

cpu_arch="${FLAGS_cpu_arch}"
download_dir="${FLAGS_download_dir}"
mkdir -p "${download_dir}"

if [[ "${FLAGS_offline}" -eq "${FLAGS_TRUE}" ]]; then
    offline='true'
fi

if [[ "${FLAGS_all_cpu}" -eq "${FLAGS_TRUE}" ]]; then
    all_cpu='true'
fi

if [[ "${FLAGS_precise}" -eq "${FLAGS_FALSE}" ]]; then
    no_precise='true'
fi

if [[ "${FLAGS_kaldi}" -eq "${FLAGS_FALSE}" ]]; then
    no_kaldi='true'
fi

if [[ "${FLAGS_web}" -eq "${FLAGS_FALSE}" ]]; then
    no_web='true'
fi

# -----------------------------------------------------------------------------

function maybe_download {
    if [[ ! -s "$2" ]]; then
        if [[ -n "${offline}" ]]; then
            echo "Need to download $1 but offline."
            exit 1
        fi

        mkdir -p "$(dirname "$2")"
        curl -sSfL -o "$2" "$1" || { echo "Can't download $1"; exit 1; }
        echo "$1 => $2"
    fi
}

# -----------------------------------------------------------------------------

declare -A CPU_TO_FRIENDLY
CPU_TO_FRIENDLY["x86_64"]="amd64"
CPU_TO_FRIENDLY["armv7l"]="armhf"
CPU_TO_FRIENDLY["arm64v8"]="aarch64"
CPU_TO_FRIENDLY["aarch64"]="aarch64"
CPU_TO_FRIENDLY["armv6l"]="armv6l"

declare -A FRIENDLY_TO_DOCKER
FRIENDLY_TO_DOCKER["amd64"]="amd64"
FRIENDLY_TO_DOCKER["armhf"]="armv7"
FRIENDLY_TO_DOCKER["aarch64"]="arm64"
FRIENDLY_TO_DOCKER["armv6l"]="armv6"

# CPU architecture
if [[ -n "${all_cpu}" ]]; then
    CPU_ARCHS=("x86_64" "armv7l" "arm64v8")
    FRIENDLY_ARCHS=("amd64" "armhf" "aarch64")
else
    CPU_ARCHS=("${cpu_arch}")
    FRIENDLY_ARCHS=("${CPU_TO_FRIENDLY[${cpu_arch}]}")
fi

# -----------------------------------------------------------------------------
# Rhasspy
# -----------------------------------------------------------------------------

for FRIENDLY_ARCH in "${FRIENDLY_ARCHS[@]}"; do
    rhasspy_files=()

    if [[ -z "${no_tools}" ]]; then
        # Install Rhasspy tools
        rhasspy_files+=("rhasspy-tools_${FRIENDLY_ARCH}.tar.gz")
    fi

    if [[ -z "${no_web}" ]]; then
        # Install web UI
        rhasspy_files+=('rhasspy-web-dist.tar.gz')
    fi

    for rhasspy_file_name in "${rhasspy_files[@]}"; do
        rhasspy_file="${download_dir}/${rhasspy_file_name}"
        rhasspy_file_url="https://github.com/synesthesiam/rhasspy/releases/download/v2.0/${rhasspy_file_name}"
        maybe_download "${rhasspy_file_url}" "${rhasspy_file}"
    done

    if [[ -z "${no_tools}" ]]; then
        # Create link for docker buildx
        DOCKER_ARCH="${FRIENDLY_TO_DOCKER[${FRIENDLY_ARCH}]}"
        if [[ "${FRIENDLY_ARCH}" != "${DOCKER_ARCH}" ]]; then
            ln -f "${download_dir}/rhasspy-tools_${FRIENDLY_ARCH}.tar.gz" \
               "${download_dir}/rhasspy-tools_${DOCKER_ARCH}.tar.gz"
        fi
    fi
done

# -----------------------------------------------------------------------------
# Pocketsphinx for Python
# -----------------------------------------------------------------------------

pocketsphinx_file="${download_dir}/pocketsphinx-python.tar.gz"
pocketsphinx_url='https://github.com/synesthesiam/pocketsphinx-python/releases/download/v1.0/pocketsphinx-python.tar.gz'
maybe_download "${pocketsphinx_url}" "${pocketsphinx_file}"

# -----------------------------------------------------------------------------
# Snowboy
# -----------------------------------------------------------------------------

snowboy_file="${download_dir}/snowboy-1.3.0.tar.gz"
snowboy_url='https://github.com/Kitt-AI/snowboy/archive/v1.3.0.tar.gz'
maybe_download "${snowboy_url}" "${snowboy_file}"

# -----------------------------------------------------------------------------
# Mycroft Precise
# -----------------------------------------------------------------------------

if [[ -z "${no_precise}" ]]; then
    for CPU_ARCH in "${CPU_ARCHS[@]}"; do
        case $CPU_ARCH in
            x86_64|armv7l|aarch64)
                precise_file="${download_dir}/precise-engine_0.3.0_${CPU_ARCH}.tar.gz"
                precise_url="https://github.com/MycroftAI/mycroft-precise/releases/download/v0.3.0/precise-engine_0.3.0_${CPU_ARCH}.tar.gz"
                maybe_download "${precise_url}" "${precise_file}"

                # Create link for docker buildx
                FRIENDLY_ARCH="${CPU_TO_FRIENDLY[${CPU_ARCH}]}"
                DOCKER_ARCH="${FRIENDLY_TO_DOCKER[${FRIENDLY_ARCH}]}"
                if [[ "${CPU_ARCH}" != "${DOCKER_ARCH}" ]]; then
                    ln -f "${download_dir}/precise-engine_0.3.0_${CPU_ARCH}.tar.gz" \
                       "${download_dir}/precise-engine_0.3.0_${DOCKER_ARCH}.tar.gz"
                fi
        esac
    done
fi

# -----------------------------------------------------------------------------
# Kaldi
# -----------------------------------------------------------------------------

if [[ -z "${no_kaldi}" ]]; then
    for FRIENDLY_ARCH in "${FRIENDLY_ARCHS[@]}"; do
        if [[ "${FRIENDLY_ARCH}" != "armv6l" ]]; then
            # Install pre-built package
            kaldi_file="${download_dir}/kaldi_${FRIENDLY_ARCH}.tar.gz"
            kaldi_url="https://github.com/synesthesiam/kaldi-docker/releases/download/v1.0/kaldi_${FRIENDLY_ARCH}.tar.gz"
            maybe_download "${kaldi_url}" "${kaldi_file}"

            # Create link for docker buildx
            DOCKER_ARCH="${FRIENDLY_TO_DOCKER[${FRIENDLY_ARCH}]}"
            if [[ "${FRIENDLY_ARCH}" != "${DOCKER_ARCH}" ]]; then
                ln -f "${download_dir}/kaldi_${FRIENDLY_ARCH}.tar.gz" \
                   "${download_dir}/kaldi_${DOCKER_ARCH}.tar.gz"
            fi
        fi
    done
fi

# -----------------------------------------------------------------------------

echo "Done"
