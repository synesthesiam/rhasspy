#!/usr/bin/env bash

# Directory of *this* script
DIR="$( cd "$( dirname "$0" )" && pwd )"

docker run -it \
       -v "$DIR/home-assistant/config":"/config" \
       --network=host \
       homeassistant/home-assistant \
       "$@"
