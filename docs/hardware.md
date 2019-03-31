# Hardware

Rhasspy is designed to be run on different kinds of hardware, such as:

* Raspberry Pi 2-3 B/B+ (`armhf`/`aarch64`)
* Desktop/laptop/server (`amd64`)

## Raspberry Pi

To run Rhasspy on a Raspberry Pi, you'll need at least a 4 GB SD card and a good power supply. I highly recommend the [CanaKit Starter Kit](https://www.amazon.com/CanaKit-Raspberry-Starter-Premium-Black/dp/B07BCC8PK7), which includes a 32 GB SD card, a 2.5 A power supply, and a case.

## Microphone

Rhasspy can listen to audio input from a local microphone or from a [remote audio stream](audio-input.md#mqtthermes). Most of the local audio testing has been done with a USB [PlayStation Eye camera](https://en.wikipedia.org/wiki/PlayStation_Eye) and a [ReSpeaker 4 Mic Array](https://respeaker.io/4_mic_array/).

You may also be interested in reading [this microphone benchmarking post](https://medium.com/snips-ai/benchmarking-microphone-arrays-respeaker-conexant-microsemi-acuedge-matrix-creator-minidsp-950de8876fda) that the [Snips.AI](http://snips.ai/) folks did back in 2017.
