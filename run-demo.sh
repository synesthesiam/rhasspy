#!/usr/bin/env bash

# Usually x86_64 or armhf
CPU_ARCH="$(lscpu | awk '/^Architecture/{print $2}')"

# Use amd64 instead of x86_64 for consistency with home assistant's BUILD_ARCH
case $CPU_ARCH in
    x86_64)
        CPU_ARCH=amd64
esac

docker run --rm -d --name rhasspy-demo \
       -p 8123:8123 -p 12101:12101 -p 4713:4713 \
       -v /etc/localtime:/etc/localtime:ro \
       -v /etc/machine-id:/etc/machine-id \
       -v /var/run/dbus:/var/run/dbus \
       -v $(pwd)/etc/homeassistant/config:/config \
       --device /dev/snd:/dev/snd \
       --privileged \
       synesthesiam/rhasspy-demo:${CPU_ARCH}
