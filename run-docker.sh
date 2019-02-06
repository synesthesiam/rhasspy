#!/usr/bin/env bash

export LC_ALL=C.UTF-8
export LANG=C.UTF-8

# Directory of *this* script
DIR="$( cd "$( dirname "$0" )" && pwd )"

if [[ -z "$XDG_CONFIG_HOME" ]]; then
    profile_dir="$HOME/.config/rhasspy/profiles"
else
    profile_dir="$XDG_CONFIG_HOME/rhasspy/profiles"
fi

docker run -d -p 12101:12101 \
       --device /dev/snd:/dev/snd \
       -e RHASSPY_PROFILES="/usr/share/rhasspy/profiles:$profile_dir" \
       -v "$profile_dir":"$profile_dir" \
       synesthesiam/rhasspy-server:latest
