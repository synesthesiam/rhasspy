#!/usr/bin/env bash
docker run --rm -it --name rhasspy-server \
       -p 12101:12101 \
       --device /dev/snd:/dev/snd \
       --privileged \
       synesthesiam/rhasspy-server:latest
