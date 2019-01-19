#!/usr/bin/env bash

export LC_ALL=C.UTF-8
export LANG=C.UTF-8

# Directory of *this* script
DIR="$( cd "$( dirname "$0" )" && pwd )"

docker run -d -p 12101:12101 \
       --device /dev/snd:/dev/snd \
       -v "$DIR/profiles":/profiles \
       -e RHASSPY_PROFILES=/profiles \
       synesthesiam/rhasspy-server:latest
