#!/usr/bin/env bash
set -e

# Directory of *this* script
DIR="$( cd "$( dirname "$0" )" && pwd )"

# Place where downloaded artifacts are stored
download_dir="${DIR}/download"
mkdir -p "${download_dir}"

# CPU architecture
CPU_ARCH="$(lscpu | awk '/^Architecture/{print $2}')"
case $CPU_ARCH in
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
     gfortran libfst-dev \
     sphinxbase-utils sphinxtrain pocketsphinx \
     jq checkinstall unzip xz-utils \
     libfst-dev curl

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

# shellcheck source=/dev/null
source "${VENV_PATH}/bin/activate"
"${PYTHON}" -m pip install wheel
"${PYTHON}" -m pip install -r requirements.txt

# Download dependencies
echo "Downloading dependencies"
bash download-dependencies.sh

# -----------------------------------------------------------------------------
# Pocketsphinx for Python
# -----------------------------------------------------------------------------

pocketsphinx_file="${download_dir}/pocketsphinx-python.tar.gz"
"${PYTHON}" -m pip install "${pocketsphinx_file}"

# -----------------------------------------------------------------------------
# Snowboy
# -----------------------------------------------------------------------------

case $CPU_ARCH in
    x86_64|armv7l)
        snowboy_file="${download_dir}/snowboy-1.3.0.tar.gz"
        if [[ ! -f "${snowboy_file}" ]]; then
            snowboy_url='https://github.com/Kitt-AI/snowboy/archive/v1.3.0.tar.gz'
            echo "Downloading snowboy (${snowboy_url})"
            curl -sSfL-o "${snowboy_file}" "${snowboy_url}"
        fi

        "${PYTHON}" -m pip install "${snowboy_file}"
        ;;

    *)
        echo "Not installing snowboy (${CPU_ARCH} not supported)"
esac

# -----------------------------------------------------------------------------
# Mycroft Precise
# -----------------------------------------------------------------------------

if [[ -z "$(which precise-engine)" ]]; then
    case $CPU_ARCH in
        x86_64|armv7l)
            precise_file="${download_dir}/precise-engine_0.3.0_${CPU_ARCH}.tar.gz"
            precise_install='/usr/lib'
            sudo tar -C "${precise_install}" -xf "${precise_file}"
            sudo ln -s "${precise_install}/precise-engine/precise-engine" '/usr/bin/precise-engine'
            ;;

        *)
            echo "Not installing Mycroft Precise (${CPU_ARCH} not supported)"
    esac
fi

# -----------------------------------------------------------------------------
# Opengrm
# -----------------------------------------------------------------------------

if [[ -z "$(which ngramcount)" ]]; then
    opengrm_file="${download_dir}/opengrm-ngram-1.3.3.tar.gz"
    echo "Building Opengrm ${opengrm_file}"
    tar -C "${temp_dir}" -xf "${opengrm_file}" && \
        cd "${temp_dir}/opengrm-ngram-1.3.3" && \
        ./configure && \
        make -j 4 && \
        sudo make install && \
        sudo ldconfig
fi

# -----------------------------------------------------------------------------
# Phonetisaurus
# -----------------------------------------------------------------------------

if [[ -z "$(which phonetisaurus-apply)" ]]; then
    case $CPU_ARCH in
        x86_64|armv7l|arm64v8)
            # Install pre-built package
            phonetisaurus_file="${download_dir}/phonetisaurus-2019_${FRIENDLY_ARCH}.deb"
            echo "Installing phonetisaurus (${phonetisaurus_file})"
            sudo dpkg -i "${phonetisaurus_file}"
        ;;

        *)
            # Build from source
            phonetisaurus_file="${download_dir}/phonetisaurus-2019.zip"
            echo "Building phonetisaurus (${phonetisaurus_file})"
            unzip -d "${temp_dir}" "${phonetisaurus_file}" && \
                cd "${temp_dir}/phonetisaurus" && \
                ./configure && \
                make -j 4 && \
                sudo make install
    esac
fi

# Add /usr/local/lib to LD_LIBRARY_PATH
sudo ldconfig

# -----------------------------------------------------------------------------
# NodeJS / Yarn
# -----------------------------------------------------------------------------

if [[ -z "$(which node)" ]]; then
    echo "Installing nodejs"
    sudo apt-get install -y nodejs
fi

if [[ -z "$(which yarn)" ]]; then
    echo "Installing yarn"
    curl -o- -L https://yarnpkg.com/install.sh | bash

    # Need to re-source .bashrc so yarn is in the path
    source "${HOME}/.bashrc"
fi

# -----------------------------------------------------------------------------
# Web Interface
# -----------------------------------------------------------------------------

echo "Building web interface"
cd "${DIR}" && yarn && yarn build

# -----------------------------------------------------------------------------

echo "Done"
