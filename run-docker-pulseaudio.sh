#!/usr/bin/env bash

export LC_ALL=C.UTF-8
export LANG=C.UTF-8

# Directory of *this* script
DIR="$( cd "$( dirname "$0" )" && pwd )"

if [[ -z "$XDG_CONFIG_HOME" ]]; then
    profile_dir="$HOME/.config/rhasspy/profiles"
    tts_dir="$HOME/.config/rhasspy/profiles"
else
    profile_dir="$XDG_CONFIG_HOME/rhasspy/profiles"
    tts_dir="$XDG_CONFIG_HOME/rhasspy/profiles"
fi

user_id=$(id -u)
docker run -d -p 12101:12101 \
       --device /dev/snd:/dev/snd \
       -e RHASSPY_PROFILES="/home/rhasspy/profiles:$profile_dir$RHASSPY_PROFILES" \
       -e RHASSPY_TTS_DIR="/home/rhasspy/tts" \
       -v "$profile_dir":"$profile_dir" \
       -v "$tts_dir":"/home/rhasspy/tts" \
       -v /run/user/${user_id}/pulse:/run/user/1000/pulse \
       -v ${HOME}/.config/pulse/cookie:/home/pacat/.config/pulse/cookie \
       -v /etc/localtime:/etc/localtime \
       synesthesiam/rhasspy-server:latest
