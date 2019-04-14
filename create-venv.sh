#!/usr/bin/env bash

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
temp_dir=$(mktemp -d)

function cleanup {
    rm -rf "${temp_dir}"
}

trap cleanup EXIT

# -----------------------------------------------------------------------------
# Debian dependencies
# -----------------------------------------------------------------------------

echo "Installing system dependencies"
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv python3-dev \
     python \
     build-essential autoconf autoconf-archive libtool automake bison \
     sox espeak flite swig portaudio19-dev \
     libatlas-base-dev \
     gfortran libfst-dev \
     sphinxbase-utils sphinxtrain pocketsphinx \
     jq checkinstall unzip xz-utils

# -----------------------------------------------------------------------------
# Virtual environment
# -----------------------------------------------------------------------------

VENV_PATH="$DIR/.venv"
echo "${VENV_PATH}"

echo "Removing existing virtual environment"
rm -rf "${VENV_PATH}"

echo "Creating new virtual environment"
mkdir -p "${VENV_PATH}"
python3 -m venv "${VENV_PATH}"

# shellcheck source=/dev/null
source "${VENV_PATH}/bin/activate"
python3 -m pip install wheel
python3 -m pip install -r requirements.txt

# -----------------------------------------------------------------------------
# Pocketsphinx for Python
# -----------------------------------------------------------------------------

pocketsphinx_file="${download_dir}/pocketsphinx-python.tar.gz"
if [[ ! -f "${pocketsphinx_file}" ]]; then
    pocketsphinx_url='https://github.com/synesthesiam/pocketsphinx-python/releases/download/v1.0/pocketsphinx-python.tar.gz'
    echo "Downloading pocketsphinx (${pocketsphinx_url})"
    wget -q -O "${pocketsphinx_file}" "${pocketsphinx_url}"
fi

python3 -m pip install "${pocketsphinx_file}"

# -----------------------------------------------------------------------------
# Snowboy
# -----------------------------------------------------------------------------

case $CPU_ARCH in
    x86_64|armv7l)
        snowboy_file="${download_dir}/snowboy-1.3.0.tar.gz"
        if [[ ! -f "${snowboy_file}" ]]; then
            snowboy_url='https://github.com/Kitt-AI/snowboy/archive/v1.3.0.tar.gz'
            echo "Downloading snowboy (${snowboy_url})"
            wget -q -O "${snowboy_file}" "${snowboy_url}"
        fi

        python3 -m pip install "${snowboy_file}"
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
            precise_file="${download_dir}/precise-engine_0.2.0_${CPU_ARCH}.tar.gz"
            if [[ ! -f "${precise_file}" ]]; then
                precise_url="https://github.com/MycroftAI/mycroft-precise/releases/download/v0.2.0/precise-engine_0.2.0_${CPU_ARCH}.tar.gz"
                echo "Downloading Mycroft Precise (${precise_url})"
                wget -q -O "${precise_file}" "${precise_url}"
            fi

            precise_install='/usr/lib'
            sudo tar -C "${precise_install}" -xf "${precise_file}"
            sudo ln -s "${precise_install}/precise-engine/precise-engine" '/usr/bin/precise-engine'
            ;;

        *)
            echo "Not installing Mycroft Precise (${CPU_ARCH} not supported)"
    esac
fi

# -----------------------------------------------------------------------------
# MITLM
# -----------------------------------------------------------------------------

if [[ -z "$(which estimate-ngram)" ]]; then
    mitlm_file="${download_dir}/mitlm-0.4.2.tar.gz"
    if [[ ! -f "${mitlm_file}" ]]; then
        mitlm_url='https://github.com/mitlm/mitlm/releases/download/v0.4.2/mitlm-0.4.2.tar.xz'
        echo "Download MITLM (${mitlm_url})"
        wget -q -O "${mitlm_file}" "${mitlm_url}"
    fi

    echo "Building MITLM ${mitlm_file}"
    tar -C "${temp_dir}" -xf "${mitlm_file}" && \
        cd "${temp_dir}/mitlm-0.4.2" && \
        ./configure && \
        make -j 4 && \
        sudo make install
fi

# -----------------------------------------------------------------------------
# Phonetisaurus
# -----------------------------------------------------------------------------

if [[ -z "$(which phonetisaurus-apply)" ]]; then
    case $CPU_ARCH in
        x86_64|armv7l|arm64v8)
            # Install pre-built package
            phonetisaurus_file="${download_dir}/phonetisaurus-2019_${FRIENDLY_ARCH}.deb"
            if [[ ! -f "${phonetisaurus_file}" ]]; then
                phonetisaurus_url="https://github.com/synesthesiam/phonetisaurus-2019/releases/download/v1.0/phonetisaurus-2019_${FRIENDLY_ARCH}.deb"
                echo "Downloading phonetisaurus (${phonetisaurus_url})"
                wget -q -O "${phonetisaurus_file}" "${phonetisaurus_url}"
            fi

            echo "Installing phonetisaurus (${phonetisaurus_file})"
            sudo dpkg -i "${phonetisaurus_file}"
        ;;

        *)
            # Build from source
            openfst_file="${download_dir}/openfst-1.6.2.tar.gz"
            if [[ ! -f "${openfst_file}" ]]; then
                openfst_url='http://www.openfst.org/twiki/pub/FST/FstDownload/openfst-1.6.2.tar.gz'
                echo "Downloading OpenFST source (${openfst_url})"
                wget -q -O "${openfst_file}" "${openfst_url}"
            fi

            echo "Building OpenFST (${openfst_file})"
            tar -C "${temp_dir}" -xzf "${openfst_file}" && \
                cd "${temp_dir}/openfst-1.6.2" && \
                ./configure --enable-static --enable-shared --enable-far --enable-ngram-fsts && \
                make -j 4 && \
                sudo make install

            phonetisaurus_file="${download_dir}/phonetisaurus-2019.zip"
            if [[ ! -f "${phonetisaurus_file}" ]]; then
                phonetisaurus_url="https://github.com/synesthesiam/phonetisaurus-2019/releases/download/v1.0/phonetisaurus-2019_${FRIENDLY_ARCH}.deb"
                echo "Downloading phonetisaurus source (${phonetisaurus_url})"
                wget -q -O "${phonetisaurus_file}" "${phonetisaurus_url}"
            fi

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
yarn && yarn build

# -----------------------------------------------------------------------------

echo "Done"
