#!/usr/bin/env bash

# Usually x86_64 or armhf
CPU_ARCH="$(lscpu | awk '/^Architecture/{print $2}')"

# Use amd64 instead of x86_64 for consistency with home assistant's BUILD_ARCH
case $CPU_ARCH in
    x86_64)
        CPU_ARCH=amd64
esac

docker run -d -p 12101:12101 \
       -v "$(pwd):/rhasspy" \
       -v /dev/snd:/dev/snd \
       --privileged \
       synesthesiam/rhasspy-hassio-addon:${CPU_ARCH}
