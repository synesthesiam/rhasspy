<style>
  h1::before {
    content:url('/img/smiley-face.png');
    padding-right: 5px;
  }
</style>

# Command Listener

## WebRTCVAD

Listens for a voice commands using [webrtcvad](https://github.com/wiseman/py-webrtcvad) to detect speech and silence.

Add to your [profile](profiles.md):

```json
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
```
    
This system listens for up to `timeout_sec` for a voice command. The first few frames of audio data are discarded (`throwaway_buffers`) to avoid clicks from the microphone being engaged. When speech is detected for some number of successive frames (`speech_buffers`), the voice command is considered to have *started*. After `min_sec`, Rhasspy will start listening for silence. If at least `silence_sec` goes by without any speech detected, the command is considered *finished*, and the recorded WAV data is sent to the [speech recognition system](speech-to-text.md).

You may want to adjust `min_sec`, `silence_sec`, and `vad_mode` for your environment.
These control how short a voice command can be (`min_sec`), how much silence is required before Rhasspy stops listening (`silence_sec`), and how sensitive the voice activity detector is (`vad_mode`, higher is more sensitive).

**NOTE**: you must set `chunk_size` such that (relative to sample rate) it produces 10, 20, or 30 millisecond buffers. This is required by `webrtcvad`.

See `rhasspy.command_listener.Webrtcvadcommandlistener` for details.

## OneShot

Takes the first chunk of audio input received to be the **entire** voice command.
Useful when paired with the [MQTT audio input](audio-input.md#mqtthermes) system if an entire WAV file is being sent in a single MQTT message.

Add to your [profile](profiles.md):

```json
"command": {
  "system": "oneshot",
  "oneshot": {
    "timeout_sec": 30
  }
}
```
    
See `rhasspy.command_listener.OneShotCommandListener` for details.

## Command

Calls a custom external program to record a voice command.

Add to your [profile](profiles.md):

```json
"command": {
  "system": "command",
  "command": {
    "program": "/path/to/program",
    "arguments": []
  }
}
```

When awake, Rhasspy normally listens for voice commands from the microphone and waits for silence by using [webrtcvad](https://github.com/wiseman/py-webrtcvad). You can call a custom program that will listen for a voice command and simply return the recorded WAV audio data to Rhasspy.

When Rhasspy wakes up, your program will be called with the given arguments. The program's output should be WAV data with the recorded voice command (Rhasspy will automatically convert this to 16-bit 16Khz mono if necessary).

See [listen.sh](https://github.com/synesthesiam/rhasspy-hassio-addon/blob/master/bin/mock-commands/listen.sh) for an example program.

See `rhasspy.command_listener.CommandCommandListener` for details.

## Dummy

Disables voice command listening.

Add to your [profile](profiles.md):

```json
"command": {
  "system": "dummy"
}
```

See `rhasspy.command.DummyCommandListener` for details.
