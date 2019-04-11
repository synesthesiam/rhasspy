#!/usr/bin/env bash
set -e

export LC_ALL=C.UTF-8
export LANG=C.UTF-8

# Directory of *this* script
DIR="$( cd "$( dirname "$0" )" && pwd )"

if [[ -z "${RHASSPY_PORT}" ]]; then
    export RHASSPY_PORT=12101
fi

cd "$DIR"
source .venv/bin/activate
export FLASK_APP=app.py
export RHASSPY_ARGS="$@"
flask run --host=0.0.0.0 --port=$RHASSPY_PORT
