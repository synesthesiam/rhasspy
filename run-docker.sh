#!/usr/bin/env bash
docker run --rm -it -p 12101:12101 \
       -v $(pwd):/rhasspy \
       -v /dev/snd:/dev/snd \
       --privileged \
       rhasspy-hassio:0.1-alpha
