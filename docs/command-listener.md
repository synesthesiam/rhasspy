# Command Listener

## WebRTCVAD

Listens for a voice commands using [webrtcvad](https://github.com/wiseman/py-webrtcvad) to detect speech.

Add to your profile:

    "command": {
      "system": "webrtcvad",
      "webrtcvad": {
        "chunk_size": 960,
        "min_sec": 2,
        "sample_rate": 16000,
        "silence_sec": 0.5,
        "speech_buffers": 5,
        "throwaway_buffers": 10,
        "timeout_sec": 30,
        "vad_mode": 0
      }
    }

See `rhasspy.command_listener.Webrtcvadcommandlistener` for details.

## OneShot

Takes the first chunk of audio input received to be the **entire** voice command.
Useful when paired with the [MQTT audio input](audio-input.md#mqtthermes) system if an entire WAV file is being sent in a single MQTT message.

See `rhasspy.command_listener.OneShotCommandListener` for details.

## Command

Calls a custom external program to record a voice command.

See `rhasspy.command_listener.CommandCommandListener` for details.

## Dummy

Disables voice command listening.

Add to your profile:

    "command": {
      "system": "dummy"
    }
