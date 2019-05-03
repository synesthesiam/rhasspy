#!/usr/bin/env bash
DIR="$( cd "$( dirname "$0" )" && pwd )"

# Try to detemine where Rhasspy is located
if [[ -z "${RHASSPY_APP}" ]]; then
    if [[ -d "/home/rhasspy" ]]; then
        # With pulseaudio
        RHASSPY_APP="/home/rhasspy"
    else
        # With ALSA
        RHASSPY_APP="/usr/share/rhasspy"
    fi
fi

if [[ -f "$CONFIG_PATH" ]]; then
    # Hass.IO configuration
    RHASSPY_PROFILE="$(jq --raw-output '.default_profile' "${CONFIG_PATH}")"
    RHASSPY_ARGS="--profile \"${RHASSPY_PROFILE}\""
fi

cd "${RHASSPY_APP}"
python3 app.py "${RHASSPY_ARGS}" "$@"
