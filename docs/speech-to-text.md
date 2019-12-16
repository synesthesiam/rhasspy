# Speech to Text

Rhasspy's primary function is convert voice commands to JSON events. The first step of this process is converting speech to text (transcription).

The following table summarizes language support for the various speech to text systems:

| System                                         | en       | de       | es       | fr       | it       | nl       | ru       | el       | hi       | zh       | vi       | pt       | ca       |
| ------                                         | -------  | -------  | -------  | -------  | -------  | -------  | -------  | -------  | -------  | -------  | -------  | -------  | -------  |
| [pocketsphinx](speech-to-text.md#pocketsphinx) | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; |          | &#x2713; | &#x2713; |
| [kaldi](speech-to-text.md#kaldi)               | &#x2713; | &#x2713; |          | &#x2713; |          | &#x2713; |          |          |          |          | &#x2713; |          |          |

## Pocketsphinx

Does speech recognition with [CMU's pocketsphinx](https://github.com/cmusphinx/pocketsphinx).
This is done completely offline, on your device. If you experience performance problems (usually on a Raspberry Pi), consider running on a home server as well and have your client Rhasspy use a [remote HTTP connection](speech-to-text.md#remote-http-server).

Add to your [profile](profiles.md):

```json
"speech_to_text": {
  "system": "pocketsphinx",
  "pocketsphinx": {
    "acoustic_model": "acoustic_model",
    "base_dictionary": "base_dictionary.txt",
    "custom_words": "custom_words.txt",
    "dictionary": "dictionary.txt",
    "language_model": "language_model.txt"
  }
}
```

The `dictionary`, `language_model`, and `unknown_words` files are written during training by the default [speech to text training system](training.md#how-it-works). The `acoustic_model` and `base_dictionary` components for each profile were taken from [a set of pre-trained models](https://sourceforge.net/projects/cmusphinx/files/Acoustic%20and%20Language%20Models/). Anyone can extend Rhasspy to new languages by training a [new acoustic model](https://cmusphinx.github.io/wiki/tutorialam).

When Rhasspy starts, it creates a pocketsphinx decoder with the following attributes:

* `hmm` - `speech_to_text.pocketsphinx.acoustic_model` (directory)
* `dict` - `speech_to_text.pocketsphinx.dictionary` (file)
* `lm` - `speech_to_text.pocketsphinx.language_model` (file)

### Open Transcription

If you just want to use Rhasspy for general speech to text, you can set `speech_to_text.pocketsphinx.open_transcription` to `true` in your profile. This will use the included general language model (much slower) and ignore any custom voice commands you've specified. For English, German, and Dutch, you may want to use [Kaldi](#kaldi) instead for better results.

See `rhasspy.stt.PocketsphinxDecoder` for details.

## Kaldi

Does speech recognition with [Kaldi](https://kaldi-asr.org).
This is done completely offline, on your device. If you experience performance problems (usually on a Raspberry Pi), consider running on a home server as well and have your client Rhasspy use a [remote HTTP connection](speech-to-text.md#remote-http-server).

```json
{
  "speech_to_text": {
    "system": "kaldi",
    "kaldi": {
        "base_dictionary": "base_dictionary.txt",
        "compatible": true,
        "custom_words": "custom_words.txt",
        "dictionary": "dictionary.txt",
        "graph": "graph",
        "kaldi_dir": "/opt/kaldi",
        "language_model": "language_model.txt",
        "model_dir": "model",
        "unknown_words": "unknown_words.txt"
    }
  }
}
```

Kaldi allows Rhasspy to support Vietnamese (vi) and Portuguese (pt) thanks to [pre-trained models](https://montreal-forced-aligner.readthedocs.io/en/latest/pretrained_models.html) from the folks from the [Montreal Forced Aligner](https://github.com/MontrealCorpusTools/Montreal-Forced-Aligner).

This requires Kaldi to be installed, which is...challenging. The [Docker image of Rhasspy](https://cloud.docker.com/u/synesthesiam/repository/docker/synesthesiam/rhasspy-server) contains a [pre-built copy](https://github.com/synesthesiam/kaldi-docker/releases) of Kaldi, which might work for you outside of Docker. Make sure to set `kaldi_dir` to wherever you installed Kaldi.

Rhasspy expects a Kaldi-compatible profile to contain a `model` directory with a `train.sh` and `decode.sh` script. See the Vietnamese (vi) or Portuguese (pt) [profile](https://github.com/synesthesiam/rhasspy-profiles/releases) for an example.

### Open Transcription

If you just want to use Rhasspy for general speech to text, you can set `speech_to_text.kaldi.open_transcription` to `true` in your profile. This will use the included general language model (much slower) and ignore any custom voice commands you've specified.

## Remote HTTP Server

Uses a remote HTTP server to transform speech (WAV) to text.
The `/api/speech-to-text` endpoint from [Rhasspy's HTTP API](usage.md#http-api) does just this, allowing you to use a remote instance of Rhasspy for speech recognition.
This is typically used in a client/server set up, where Rhasspy does speech/intent recognition on a home server with decent CPU/RAM available.

Add to your [profile](profiles.md):

```json
"speech_to_text": {
  "system": "remote",
  "remote": {
    "url": "http://my-server:12101/api/speech-to-text"
  }
}
```

During speech recognition, 16-bit 16 kHz mono WAV data will be POST-ed to the endpoint with the `Content-Type` set to `audio/wav`. A `text/plain` response with the transcription is expected back. An additional `profile` query argument is sent with the current profile name, so the POST URL is effectively something like `http://remote-server:12101/api/speech-to-text?profile=en`.

See `rhasspy.stt.RemoteDecoder` for details.

## MQTT/Hermes

Publishes transcriptions to `hermes/asr/textCaptured` ([Hermes protocol](https://docs.snips.ai/ressources/hermes-protocol)) each time a voice command is spoken.

This is enabled by default.

## Command

Calls a custom external program to do speech recognition.

Voice commands are normally transcribed by Rhasspy using [pocketsphinx](https://github.com/cmusphinx/pocketsphinx). The acoustic model, dictionary, and language model are available in your profile directory (after training) as `acoustic_model/`, `dictionary.txt`, and `language_model.txt` respectively. You can call a custom program to do speech to text that uses these artifacts or does something totally different!

Add to your [profile](profiles.md):

```json
"speech_to_text": {
  "system": "command",
  "command": {
    "program": "/path/to/program",
    "arguments": []
  }
}
```

When a voice command is received, Rhasspy will call your program and push the recorded WAV data (16-bit 16 kHz mono) to standard in. Your program should print the text transcription to standard out.

The following environment variables are available to your program:

* `$RHASSPY_BASE_DIR` - path to the directory where Rhasspy is running from
* `$RHASSPY_PROFILE` - name of the current profile (e.g., "en")
* `$RHASSPY_PROFILE_DIR` - directory of the current profile (where `profile.json` is)

See [speech2text.sh](https://github.com/synesthesiam/rhasspy/blob/master/bin/mock-commands/speech2text.sh) for an example program.

If your speech to text system requires some kind of custom training, you should also override Rhasspy's [speech to text training system](training.md#speech-to-text).

See `rhasspy.stt.CommandDecoder` for details.

## Dummy

Disables speech to text decoding.

Add to your [profile](profiles.md):

```json
"speech_to_text": {
  "system": "dummy"
}
```

See `rhasspy.stt.DummyDecoder` for details.
