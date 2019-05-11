#!/usr/bin/env bash

export LC_ALL=C.UTF-8
export LANG=C.UTF-8

# Directory of *this* script
DIR="$( cd "$( dirname "$0" )" && pwd )"

if [[ -z "$RHASSPY_PORT" ]]; then
    export RHASSPY_PORT=12101
fi

cd "$DIR"
source .venv/bin/activate
export RHASSPY_PROFILES="$DIR/profiles:$HOME/.rhasspy-test/profiles"
export RHASSPY_TTS_DIR="$DIR/tts:$HOME/.rhasspy-test/tts"
python3 test.py "$@"
