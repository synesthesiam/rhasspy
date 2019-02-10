#!/usr/bin/env bash
mosquitto_pub -h pumpkin.lan -t hermes/hotword/default/detected -m '{ "siteId": "default" }'
sleep 1
mosquitto_pub -h pumpkin.lan -t hermes/audioServer/default/audioFrame -s < what_time_is_it.wav
echo "Sent WAV"
