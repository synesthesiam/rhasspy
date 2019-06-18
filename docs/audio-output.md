# Audio Output

Rhasspy provides audio feedback when waking up, processing commands, and when pronouncing custom words.
It can also do [text to speech](text-to-speech.md).

## ALSA

Plays WAV files on the local device by calling the `aplay` command. Should work with ALSA and PulseAudio.

Add to your [profile](profiles.md):

    "sounds": {
       "system": "aplay",
       "aplay": {
         "device": ""
       }
    }
    
If provided, `sounds.aplay.device` is passed to `aplay` with the `-D` argument.
Leave it blank to use the default device.

See `rhasspy.audio_player.APlayAudioPlayer` for details.


## MQTT/Hermes

Publishes WAV data to the `hermes/audioServer/<SITE_ID>/playBytes/<REQUEST_ID>` topic ([Hermes protocol](https://docs.snips.ai/ressources/hermes-protocol)).
This allows Rhasspy to send audio to [Snips.AI](https://snips.ai/).

Rhasspy will always try to send 16 kHz, 16-bit mono audio.
The request id is generated each time a sound is played using `uuid.uuid4`.

Add to your [profile](profiles.md):

    "sounds": {
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

Adjust the `mqtt` configuration to connect to your MQTT broker.
Set `mqtt.site_id` to match your Snips.AI siteId.

See `rhasspy.audio_player.HermesAudioPlayer` for more details.

## Dummy

Disables audio output.

Add to your [profile](profiles.md):

```json
"sounds": {
  "system": "dummy"
}
```

See `rhasspy.audio_player.DummyAudioPlayer` for details.
