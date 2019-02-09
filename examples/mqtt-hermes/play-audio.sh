#!/usr/bin/env bash
while true; do
    mosquitto_sub -C 1 -t 'hermes/audioServer/default/playBytes/#' | aplay || exit 0
done
