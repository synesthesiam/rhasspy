#!/usr/bin/env bash

# Directory of *this* script
DIR="$( cd "$( dirname "$0" )" && pwd )"

# Debian dependencies
echo "Installing system dependencies"
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv python3-dev \
     sox espeak swig portaudio19-dev

if [[ -z "$(which java)" ]]; then
    echo "Installing Java"
    sudo apt-get install -y ca-certificates-java
    sudo apt-get install -y openjdk-8-jre-headless
fi

VENV_PATH=$DIR/.venv
echo $VENV_PATH

echo "Removing existing virtual environment"
rm -rf "$VENV_PATH"

echo "Creating new virtual environment"
mkdir -p "$VENV_PATH"
python3 -m venv "$VENV_PATH"
source "$VENV_PATH"/bin/activate
python3 -m pip install wheel
python3 -m pip install -r requirements.txt
python3 -m pip install https://github.com/synesthesiam/pocketsphinx-python/releases/download/v1.0/pocketsphinx-python.tar.gz

if [[ -z "$(which docker)" ]] || [[ ! -z "$RHASSPY_NODOCKER" ]]; then
    echo "Installing pre-compiled binaries"

    # Usually x86_64 or armhf
    CPU_ARCH="$(lscpu | awk '/^Architecture/{print $2}')"

    # Use amd64 instead of x86_64 for consistency with home assistant's BUILD_ARCH
    case $CPU_ARCH in
        x86_64)
            CPU_ARCH=amd64
    esac

    PKG_DIR=$(mktemp -d)

    function cleanup {
        rm -rf "$PKG_DIR"
    }

    trap cleanup EXIT

    wget -O "$PKG_DIR/jsgf-gen.deb" https://github.com/synesthesiam/jsgf-gen/releases/download/v1.0/jsgf-gen-1.0_all.deb

    wget -O "$PKG_DIR/openfst.deb" https://github.com/synesthesiam/docker-opengrm/releases/download/v1.3.4-${CPU_ARCH}/openfst_1.6.9-1_${CPU_ARCH}.deb

    wget -O "$PKG_DIR/opengrm.deb" https://github.com/synesthesiam/docker-opengrm/releases/download/v1.3.4-${CPU_ARCH}/opengrm_1.3.4-1_${CPU_ARCH}.deb

    wget -O "$PKG_DIR/phonetisaurus.deb" https://github.com/synesthesiam/phonetisaurus-2013/releases/download/v1.0-${CPU_ARCH}/phonetisaurus_2013-1_${CPU_ARCH}.deb

    sudo dpkg -i ${PKG_DIR}/*.deb
fi

echo "Done"
