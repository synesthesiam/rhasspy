#!/usr/bin/env bash
DIR="$( cd "$( dirname "$0" )" && pwd )"
RHASSPY_APP=/usr/share/rhasspy
RHASSPY_RUN=$RHASSPY_APP

if [[ -f "$CONFIG_PATH" ]]; then
    RHASSPY_RUN="$(jq --raw-output '.run_dir' $CONFIG_PATH)"
    export RHASSPY_PROFILE="$(jq --raw-output '.default_profile' $CONFIG_PATH)"
fi

if [[ ! -d "$RHASSPY_RUN" ]]; then
    mkdir -p "$RHASSPY_RUN"
fi

export RHASSPY_PROFILES="$RHASSPY_APP/profiles:$RHASSPY_RUN/profiles:$RHASSPY_PROFILES"
export RHASSPY_ARGS="$@"

export FLASK_APP=app.py
cd "$RHASSPY_APP"
flask run --host=0.0.0.0 --port=12101
