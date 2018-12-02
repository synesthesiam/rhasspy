#!/usr/bin/env bash

# Directory of *this* script
DIR="$( cd "$( dirname "$0" )" && pwd )"

# Debian dependencies
echo "Installing system dependencies"
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv python3-dev \
     sox espeak swig portaudio19-dev

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

echo "Done"
