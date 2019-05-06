# Text to Speech

After you voice command has been [handled](intent-handling.md), it's common to produce speech as a response back to the user. Rhasspy has support for several text to speech systems which, importantly, can be played through any of the [audio output](audio-output.md) systems.

## eSpeak

Uses [eSpeak](http://espeak.sourceforge.net) to speak sentences. This is the default text to speech system and, while it sounds robotic, has the widest support for different languages.

Add to your [profile](profiles.md):

```json
"text_to_speech": {
  "system": "espeak",
  "espeak": {
    "voice": "en"
  }
}
```

Remove the `voice` option to have `espeak` use your profile's language automatically.

See `rhasspy.tts.EspeakSentenceSpeaker` for more details.

## Flite

Uses FestVox's [flite](http://www.festvox.org/flite) for speech. Sounds better than `espeak` in most cases, but only supports English out of the box.

Add to your [profile](profiles.md):

```json
"text_to_speech": {
  "system": "flite",
  "flite": {
    "voice": "kal16"
  }
}
```

Some other included voices are `rms`, `slt`, and `awb`.

See `rhasspy.tts.FliteSentenceSpeaker` for details.

## PicoTTS

Uses SVOX's [picotts](https://en.wikipedia.org/wiki/SVOX) for text to speech. Sounds a bit better (to me) than `flite` or `espeak`, but only has a single English voice.

Add to your [profile](profiles.md):

```json
"text_to_speech": {
  "system": "picotts",
  "picotts": {
    "language": "en-US"
  }
}
```

See `rhasspy.tts.PicoTTSSentenceSpeaker` for details.

## MaryTTS

Uses a remote [MaryTTS](http://mary.dfki.de/) web server. Supported languages include German, British and American English, French, Italian, Luxembourgish, Russian, Swedish, Telugu, and Turkish. An [MaryTTS Docker image](https://hub.docker.com/r/synesthesiam/marytts) is available, though only the default voice is included.

```json
"text_to_speech": {
  "system": "marytts",
  "marytts": {
    "url": "http://localhost:59125",
    "voice": "cmu-slt",
    "locale": "en-US"
  }
}
```

To run the Docker image, simply execute:

```bash
docker run -it -p 59125:59125 synesthesiam/marytts:5.2
```
    
and visit [http://localhost:59125](http://localhost:59125) after it starts. For more English voices, run the following commands in a Bash shell:

```bash
mkdir -p marytts-5.2/download
for voice in dfki-prudence dfki-poppy dfki-obadiah dfki-spike cmu-bdl cmu-rms;
  do wget -O marytts-5.2/download/voice-${voice}-hsmm-5.2.zip https://github.com/marytts/voice-${voice}-hsmm/releases/download/v5.2/voice-${voice}-hsmm-5.2.zip;
  unzip -d marytts-5.2 marytts-5.2/download/voice-${voice}-hsmm-5.2.zip;
done
```

Now run the Docker image again with the following command (in the same directory):

```bash
voice=dfki-prudence
docker run -it -p 59125:59125 -v "$(pwd)/marytts-5.2/lib/voice-${voice}-hsmm-5.2.jar:/marytts/lib/voice-${voice}-hsmm-5.2.jar" synesthesiam/marytts:5.2
```

Change the first line to select the voice you'd like to add. It's not recommended to link in all of the voices at once, since MaryTTS seems to load them all into memory and overwhelm the RAM of a Raspberry Pi.

See `rhasspy.tts.MaryTTSSentenceSpeaker` for details.

## Command

You can extend Rhasspy easily with your own external text to speech system. When a sentence needs to be spoken, Rhasspy will call your custom program with the text given on standard in. Your program should return the corresponding WAV data on standard out.

Add to your [profile](profiles.md):

```json
"text_to_speech": {
  "system": "command",
  "command": {
      "program": "/path/to/program",
      "arguments": []
  }
}
```

For compatibility with other services and Rhasspy components, it's best to return 16 Khz, 16-bit mono WAV data.

See `rhasspy.tts.CommandSentenceSpeaker` for details.

## Dummy

Disables text to speech.

Add to your [profile](profiles.md):

```json
"text_to_speech": {
  "system": "dummy"
}
```

See `rhasspy.tts.DummySentenceSpeaker` for details.
