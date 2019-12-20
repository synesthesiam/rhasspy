# Audio Input

Rhasspy can listen to audio input from a local microphone or from a remote audio
stream. Most of the local audio testing has been done with a USB [PlayStation
Eye camera](https://en.wikipedia.org/wiki/PlayStation_Eye).

## PyAudio

Streams microphone data from a [PyAudio](https://people.csail.mit.edu/hubert/pyaudio/) device.
This is the default audio input system, and should work with both [ALSA](https://www.alsa-project.org/main/index.php/Main_Page) and [PulseAudio](https://www.freedesktop.org/wiki/Software/PulseAudio/).

Add to your [profile](profiles.md):

```json
"microphone": {
  "system": "pyaudio",
  "pyaudio": {
    "device": "",
    "frames_per_buffer": 480
  }
}
```

Set `microphone.pyaudio.device` to a PyAudio device number or leave blank for the default device.
Streams 30ms chunks of 16-bit, 16 Khz mono audio by default (480 frames).

See `rhasspy.audio_recorder.PyAudioRecorder` for details.

## ALSA

Starts an `arecord` process locally and reads audio data from its standard out.
Works best with [ALSA](https://www.alsa-project.org/main/index.php/Main_Page).

Add to your [profile](profiles.md):

```json
"microphone": {
  "system": "arecord",
  "arecord": {
    "device": "",
    "chunk_size": 960
  }
}
```

Set `microphone.arecord.device` to the name of the ALSA device to use (`-D` flag
to `arecord`) or leave blank for the default device.
By default, calls `arecord -t raw -r 16000 -f S16_LE -c 1` and reads 30ms (960
bytes) of audio data at a time.

See `rhasspy.audio_recorder.ARecordAudioRecorder` for details.

## MQTT/Hermes

Listens to the `hermes/audioServer/<SITE_ID>/audioFrame` topic for WAV data ([Hermes protocol](https://docs.snips.ai/ressources/hermes-protocol)).
This allows Rhasspy to receive audio from [Snips.AI](https://snips.ai/).
Audio data is automatically converted to 16-bit, 16 kHz mono with [sox](http://sox.sourceforge.net).

Add to your [profile](profiles.md):

```json
"microphone": {
  "system": "hermes"
},

"mqtt": {
  "enabled": true,
  "host": "localhost",
  "username": "",
  "port": 1883,
  "password": "",
  "site_id": "default"
}
```

Adjust the `mqtt` configuration to connect to your MQTT broker.
Set `mqtt.site_id` to match your Snips.AI siteId.

See `rhasspy.audio_recorder.HermesAudioRecorder` for details.

## HTTP Stream

Accepts chunks of 16-bit 16Khz mono audio via an HTTP POST stream (assumes [chunked transfer encoding](https://en.wikipedia.org/wiki/Chunked_transfer_encoding)).

Add to your [profile](profiles.md):

```json
"microphone": {
  "system": "http",
  "http": {
    "host": "127.0.0.1",
    "port": 12333,
    "stop_after": "never"
  }
}
```

Set `microphone.http.stop_after` to one of "never", "text", or "intent". When set to "never", you can continously stream (chunked) audio into Rhasspy across multiple voice commands. When set to "text" or "intent", the stream will be closed when the first voice command has been transcribed ("text") or recognized ("intent"). Once closed, you can perform an HTTP GET request to the stream URL to retrieve the result (text for transcriptions or JSON for intent).

Note that `microphone.http.port` must be different than Rhasspy's webserver port (usually 12101).

See `rhasspy.audio_recorder.HTTPAudioRecorder` for details.

## GStreamer

Receives audio chunks via stdout from a [GStreamer](https://gstreamer.freedesktop.org/) pipeline.

Add to your [profile](profiles.md):

```json
"microphone": {
  "system": "gstreamer",
  "gstreamer": {
    "pipeline": "...",
  }
}
```

Set `microphone.gstreamer.pipeline` to your GStreamer pipeline **without a sink** (this will be added by Rhasspy). By default, the pipeline is:

```
udpsrc port=12333 ! rawaudioparse use-sink-caps=false format=pcm pcm-format=s16le sample-rate=16000 num-channels=1 ! queue ! audioconvert ! audioresample
```

which "simply" receives raw 16-bit 16khz audio chunks via UDP port 12333. You could stream microphone audio to Rhasspy from another machine by running the following terminal command:

```bash
gst-launch-1.0 \
    autoaudiosrc ! \
    audioconvert ! \
    audioresample ! \
    audio/x-raw, rate=16000, channels=1, format=S16LE ! \
    udpsink host=RHASSPY_SERVER port=12333
```

where `RHASSPY_SERVER` is the hostname of your Rhasspy server (e.g., `localhost`).

The Rhasspy Docker images contains the ["good" plugin](https://gstreamer.freedesktop.org/data/doc/gstreamer/head/gst-plugins-good-plugins/html/) set for GStreamer, which includes a wide variety of ways to stream/transform audio.

See `rhasspy.audio_recorder.GStreamerAudioRecorder` for details.

## Dummy

Disables microphone recording.

Add to your [profile](profiles.md):

```json
"microphone": {
  "system": "dummy"
}
```

See `rhasspy.audio_recorder.DummyAudioRecorder` for details.
