#!/usr/bin/env bash

# Usually x86_64 or armhf
CPU_ARCH="$(lscpu | awk '/^Architecture/{print $2}')"

# Use amd64 instead of x86_64 for consistency with home assistant's BUILD_ARCH
case $CPU_ARCH in
    x86_64)
        CPU_ARCH=amd64
esac

docker run --rm -it --name rhasspy-server \
       -p 12101:12101 \
       --device /dev/snd:/dev/snd \
       --privileged \
       synesthesiam/rhasspy-server:${CPU_ARCH}
