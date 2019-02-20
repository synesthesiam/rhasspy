#!/usr/bin/env bash
mosquitto_pub -h localhost -t hermes/asr/startListening -m '{ "siteId": "default" }'
sleep 0.5
for f in output*.wav; do
	mosquitto_pub -h localhost -t hermes/audioServer/default/audioFrame -s < $f;
done
sleep 0.5
mosquitto_pub -h localhost -t hermes/asr/stopListening -m '{ "siteId": "default" }'
echo "Sent WAV"
