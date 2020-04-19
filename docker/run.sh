#!/usr/bin/env bash
this_dir="$( cd "$( dirname "$0" )" && pwd )"

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

if [[ -f "${CONFIG_PATH}" ]]; then
    # Hass.IO configuration
    profile_name="$(jq --raw-output '.profile_name' "${CONFIG_PATH}")"
    profile_dir="$(jq --raw-output '.profile_dir' "${CONFIG_PATH}")"
    RHASSPY_ARGS="--profile ${profile_name} --user-profiles ${profile_dir}"
fi

RHASSPY_VENV="${RHASSPY_APP}/.venv"
if [[ -d "${RHASSPY_VENV}" ]]; then
    source "${RHASSPY_VENV}/bin/activate"

    # Force .venv/lib to be used
    export LD_LIBRARY_PATH="${RHASSPY_VENV}/lib:${LD_LIBRARY_PATH}"
fi

cd "${RHASSPY_APP}"

if [[ -z "${RHASSPY_ARGS}" ]]; then
    python3 app.py "$@"
else
    python3 app.py ${RHASSPY_ARGS} "$@"
fi
