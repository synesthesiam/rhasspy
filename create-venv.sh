#!/usr/bin/env bash

# Directory of *this* script
DIR="$( cd "$( dirname "$0" )" && pwd )"

# Debian dependencies
echo "Installing system dependencies"
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv python3-dev \
     build-essential autoconf libtool automake bison \
     sox espeak swig portaudio19-dev \
     libatlas-base-dev \
     sphinxbase-utils sphinxtrain pocketsphinx \
     jq checkinstall

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
python3 -m pip install etc/pocketsphinx-python.tar.gz
python3 -m pip install etc/snowboy-1.3.0.tar.gz

if [[ -z "$RHASSPY_DOCKER" ]]; then
    echo "Installing pre-compiled binaries"

    # Usually x86_64 or armhf
    CPU_ARCH="$(lscpu | awk '/^Architecture/{print $2}')"

    # Use amd64 instead of x86_64 for consistency with home assistant's BUILD_ARCH
    case $CPU_ARCH in
	    x86_64)
		    CPU_ARCH=amd64
		    ;;

	    armv7l)
		    CPU_ARCH=armhf
		    ;;

	    arm64v8)
		    CPU_ARCH=aarch64
		    ;;
    esac

    PKG_DIR=$(mktemp -d)

    function cleanup {
        rm -rf "$PKG_DIR"
    }

    trap cleanup EXIT

    wget -O "$PKG_DIR/phonetisaurus.deb" https://github.com/synesthesiam/phonetisaurus-2013/releases/download/v1.0-${CPU_ARCH}/phonetisaurus_2013-1_${CPU_ARCH}.deb

    sudo dpkg -i ${PKG_DIR}/*.deb

    # Install mitlm
    pushd "$DIR/etc"
    tar -xf mitlm-0.4.2.tar.xz && \
        cd mitlm-0.4.2 && \
        ./configure && \
        make -j 4 && \
        sudo checkinstall --pkgname=mitlm --default
    popd

    precise_path="$DIR/etc/precise-engine_0.2.0_${CPU_ARCH}.tar.gz"
    echo "$precise_path"
    if [[ -f "$precise_path" ]]; then
        pushd "$DIR/etc"
        tar -xf "$precise_path"
        sudo ln -s "$DIR/etc/precise-engine/precise-engine" /usr/local/bin/precise-engine
        popd
    fi
fi

# Add /usr/local/lib to LD_LIBRARY_PATH
sudo ldconfig

echo "Done"
