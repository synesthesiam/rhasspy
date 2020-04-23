#!/usr/bin/env bash

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
    RHASSPY_ARGS=('--profile' "${profile_name}" '--user-profiles' "${profile_dir}")

    # Copy user-defined asoundrc to root
    asoundrc="$(jq --raw-output '.asoundrc' "${CONFIG_PATH}")"
    if [[ ! -z "${asoundrc}" ]]; then
	    echo "${asoundrc}" > /root/.asoundrc
    fi

    # Add SSL settings
    ssl="$(jq --raw-output '.ssl' "${CONFIG_PATH}")"
    if [[ "${ssl}" == 'true' ]]; then
        certfile="$(jq --raw-output '.certfile' "${CONFIG_PATH}")"
        keyfile="$(jq --raw-output '.keyfile' "${CONFIG_PATH}")"
        RHASSPY_ARGS+=('--ssl' "/ssl/${certfile}" "/ssl/${keyfile}")
    fi
fi

RHASSPY_VENV="${RHASSPY_APP}/.venv"
if [[ -d "${RHASSPY_VENV}" ]]; then
    source "${RHASSPY_VENV}/bin/activate"

    # Force .venv/lib to be used
    export LD_LIBRARY_PATH="${RHASSPY_VENV}/lib:${LD_LIBRARY_PATH}"
fi

cd "${RHASSPY_APP}" || exit 1

if [[ -z "${RHASSPY_ARGS[*]}" ]]; then
    python3 app.py "$@"
else
    python3 app.py "${RHASSPY_ARGS[@]}" "$@"
fi
