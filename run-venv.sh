#!/usr/bin/env bash

export LC_ALL=C.UTF-8
export LANG=C.UTF-8

# Directory of *this* script
DIR="$( cd "$( dirname "$0" )" && pwd )"

if [[ -z "$(which docker)" ]] || [[ ! -z "$RHASSPY_NODOCKER" ]]; then
    echo "Using pre-compiled binaries."
else
    echo "Using Docker scripts."

    # Use docker shell scripts
    export PATH=$DIR/bin/docker:$PATH
fi

cd "$DIR"
source .venv/bin/activate
export FLASK_APP=app.py
flask run --host=0.0.0.0 --port=12101
