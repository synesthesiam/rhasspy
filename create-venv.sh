#!/usr/bin/env bash
set -e

# Process command-line arguments
no_flair="no"
for arg in "$@"; do
    shift
    case "${arg}" in
        "--no-flair") no_flair="yes" ;;
    esac
done

# Directory of *this* script
DIR="$( cd "$( dirname "$0" )" && pwd )"

# Place where downloaded artifacts are stored
download_dir="${DIR}/download"
mkdir -p "${download_dir}"

# CPU architecture
CPU_ARCH="$(lscpu | awk '/^Architecture/{print $2}')"
case "${CPU_ARCH}" in
    x86_64)
        FRIENDLY_ARCH=amd64
        ;;

    armv7l)
        FRIENDLY_ARCH=armhf
        ;;

    arm64v8)
        FRIENDLY_ARCH=aarch64
        ;;
esac

# Create a temporary directory for building stuff
temp_dir="$(mktemp -d)"

function cleanup {
    rm -rf "${temp_dir}"
}

trap cleanup EXIT

# -----------------------------------------------------------------------------
# Debian dependencies
# -----------------------------------------------------------------------------

echo "Installing system dependencies (${FRIENDLY_ARCH})"
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv python3-dev \
     python \
     build-essential autoconf autoconf-archive libtool automake bison \
     sox espeak flite swig portaudio19-dev \
     libatlas-base-dev \
     gfortran \
     sphinxbase-utils sphinxtrain pocketsphinx \
     jq checkinstall unzip xz-utils \
     curl

# -----------------------------------------------------------------------------
# Python 3.6
# -----------------------------------------------------------------------------

if [[ -z "$(which python3.6)" ]]; then
    echo "Installing Python 3.6 from source. This is going to take a LONG time."
    sudo apt-get install -y tk-dev libncurses5-dev libncursesw5-dev \
         libreadline6-dev libdb5.3-dev libgdbm-dev \
         libsqlite3-dev libssl-dev libbz2-dev \
         libexpat1-dev liblzma-dev zlib1g-dev

    python_file="${download_dir}/Python-3.6.8.tar.xz"
    if [[ ! -f "${python_file}" ]]; then
        python_url='https://www.python.org/ftp/python/3.6.8/Python-3.6.8.tar.xz'
        curl -sSfL-o "${python_file}" "${python_url}"
    fi

    tar -C "${temp_dir}" -xf "${python_file}"
    cd "${temp_dir}/Python-3.6.8" && \
        ./configure && \
        make -j 4 && \
        sudo make altinstall
fi

# -----------------------------------------------------------------------------
# Download dependencies
# -----------------------------------------------------------------------------

echo "Downloading dependencies"
bash download-dependencies.sh "${CPU_ARCH}"

# -----------------------------------------------------------------------------
# Virtual environment
# -----------------------------------------------------------------------------

cd "${DIR}"

PYTHON="python3.6"
VENV_PATH="${DIR}/.venv"
echo "${VENV_PATH}"

echo "Removing existing virtual environment"
rm -rf "${VENV_PATH}"

echo "Creating new virtual environment"
mkdir -p "${VENV_PATH}"
"${PYTHON}" -m venv "${VENV_PATH}"

# Extract Rhasspy tools
rhasspy_tools_file="${download_dir}/rhasspy-tools_${FRIENDLY_ARCH}.tar.gz"
echo "Extracting tools (${rhasspy_tools_file})"
tar -C "${VENV_PATH}" -xf "${rhasspy_tools_file}"

# Force .venv/lib to be used
export LD_LIBRARY_PATH="${VENV_PATH}/lib:${LD_LIBRARY_PATH}"

# shellcheck source=/dev/null
source "${VENV_PATH}/bin/activate"

echo "Installing Python requirements"
"${PYTHON}" -m pip install wheel

requirements_file="${DIR}/requirements.txt"
if [[ ! -z "${no_flair}" ]]; then
    echo "Excluding flair from virtual environment"
    grep -v flair "${requirements_file}" > "${temp_dir}/requirements.txt"
    requirements_file="${temp_dir}/requirements.txt"
fi

"${PYTHON}" -m pip install -r "${requirements_file}"

# -----------------------------------------------------------------------------
# Pocketsphinx for Python
# -----------------------------------------------------------------------------

pocketsphinx_file="${download_dir}/pocketsphinx-python.tar.gz"
"${PYTHON}" -m pip install "${pocketsphinx_file}"

# -----------------------------------------------------------------------------
# Snowboy
# -----------------------------------------------------------------------------

case "${CPU_ARCH}" in
    x86_64|armv7l)
        snowboy_file="${download_dir}/snowboy-1.3.0.tar.gz"
        echo "Installing snowboy"
        "${PYTHON}" -m pip install "${snowboy_file}"
        ;;

    *)
        echo "Not installing snowboy (${CPU_ARCH} not supported)"
esac

# -----------------------------------------------------------------------------
# Mycroft Precise
# -----------------------------------------------------------------------------

if [[ -z "$(which precise-engine)" ]]; then
    case "${CPU_ARCH}" in
        x86_64|armv7l)
            echo "Installing Mycroft Precise"
            precise_file="${download_dir}/precise-engine_0.3.0_${CPU_ARCH}.tar.gz"
            precise_install="${VENV_PATH}/lib"
            tar -C "${precise_install}" -xf "${precise_file}"
            ln -s "${precise_install}/precise-engine/precise-engine" "${VENV_PATH}/bin/precise-engine"
            ;;

        *)
            echo "Not installing Mycroft Precise (${CPU_ARCH} not supported)"
    esac
fi

# -----------------------------------------------------------------------------
# Kaldi
# -----------------------------------------------------------------------------

kaldi_file="${download_dir}/kaldi_${FRIENDLY_ARCH}.tar.gz"
echo "Installing Kaldi (${kaldi_file})"
mkdir -p "${DIR}/opt"
tar -C "${DIR}/opt" -xf "${kaldi_file}"

# -----------------------------------------------------------------------------
# Web Interface
# -----------------------------------------------------------------------------

rhasspy_web_file="${download_dir}/rhasspy-web-dist.tar.gz"
echo "Extracting web interface (${rhasspy_web_file})"
tar -C "${DIR}" -xf "${rhasspy_web_file}"

# -----------------------------------------------------------------------------

echo "Done"
