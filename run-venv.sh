#!/usr/bin/env bash

export LC_ALL=C.UTF-8
export LANG=C.UTF-8

# Directory of *this* script
DIR="$( cd "$( dirname "$0" )" && pwd )"

export PATH=$DIR/etc/jsgf-gen/bin:$PATH

if [[ -z "$(which docker)" ]] || [[ ! -z "$RHASSPY_NODOCKER" ]]; then
    echo "Using pre-compiled binaries."

    # Usually x86_64 or armhf
    CPU_ARCH="$(lscpu | awk '/^Architecture/{print $2}')"

    # Use amd64 instead of x86_64 for consistency with home assistant's BUILD_ARCH
    case $CPU_ARCH in
        x86_64)
            CPU_ARCH=amd64
    esac

    # Needed for pre-compiled binaries
    export PATH=$DIR/bin/$CPU_ARCH:$PATH
    export LD_LIBRARY_PATH=$DIR/lib/$CPU_ARCH:$LD_LIBRARY_PATH

    echo "PATH=$PATH"
    echo "LD_LIBRARY_PATH=$LD_LIBRARY_PATH"
else
    echo "Using Docker scripts."

    # Use docker shell scripts
    export PATH=$DIR/bin/docker:$PATH
fi

cd "$DIR"
source .venv/bin/activate
export FLASK_APP=app.py
flask run --host=0.0.0.0 --port=12101
