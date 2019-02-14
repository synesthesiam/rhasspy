# Speech to Text

## Pocketsphinx

Does speech recognition with [CMU's pocketsphinx](https://github.com/cmusphinx/pocketsphinx).

Add to your [profile](profiles.md):

```json
"speech_to_text": {
  "system": "pocketsphinx",
  "pocketsphinx": {
    "acoustic_model": "acoustic_model",
    "base_dictionary": "base_dictionary.txt",
    "custom_words": "custom_words.txt",
    "dictionary": "dictionary.txt",
    "language_model": "language_model.txt",
    "unknown_words": "unknown_words.txt",
    "mllr_matrix": "acoustic_model_mllr"
  }
}
```

The `dictionary`, `language_model`, and `unknown_words` files are written during training by the default [speech to text training system](training.md#how-it-works). The `acoustic_model` and `base_dictionary` components for each profile were taken from [a set of pre-trained models](https://sourceforge.net/projects/cmusphinx/files/Acoustic%20and%20Language%20Models/). Anyone can extend Rhasspy to new languages by training a [new acoustic model](https://cmusphinx.github.io/wiki/tutorialam).

When Rhasspy starts, it creates a pocketsphinx decoder with the following attributes:

* `hmm` - `speech_to_text.pocketsphinx.acoustic_model` (directory)
* `dict` - `speech_to_text.pocketsphinx.dictionary` (file)
* `lm` - `speech_to_text.pocketsphinx.language_model` (file)
* `mllr` - `speech_to_text.pocketsphinx.mllr_matrix` (file, optional)

The `mllr_matrix` file is intended for advanced users who want to [tune/adapt their acoustic models](https://cmusphinx.github.io/wiki/tutorialadapt). This can increase the performance of Rhasspy's speech recognition for a specific user/microphone/acoustic environment.

See `rhasspy.stt.PocketsphinxDecoder` for details.

## Remote HTTP Server

Uses a remote HTTP server to transform speech (WAV) to text.
The `/api/speech-to-text` endpoint from [Rhasspy's HTTP API](usage.md#http-api) does just this, allowing you to use a remote instance of Rhasspy for speech recognition.

Add to your [profile](profiles.md):

```json
"speech_to_text": {
  "system": "remote",
  "remote": {
    "url": "http://my-server:12101/api/speech-to-text"
  }
}
```

During speech recognition, 16-bit 16Khz mono WAV data will be POST-ed to the endpoint with the `Content-Type` set to `audio/wav`. A `text/plain` response with the transcription is expected back. An additional `profile` query argument is sent with the current profile name, so the POST URL is effectively something like `http://remote-server:12101/api/speech-to-text?profile=en`.

See `rhasspy.stt.RemoteDecoder` for details.

## Command

Calls a custom external program to do speech recognition.

Voice commands are normally transcribed by Rhasspy using [pocketsphinx](https://github.com/cmusphinx/pocketsphinx). The acoustic model, dictionary, and language model are available in your profile directory (after training) as `acoustic_model/`, `dictionary.txt`, and `language_model.txt` respectively. You can call a custom program to do speech to text that uses these artifacts or does something totally different!

Add to your [profile](profiles.md):

```json
"speech_to_text": {
  "system": "command",
  "command": {
    "program": "/path/to/program",
    "arguments": ["argument1", "argument2"]
  }
}
```

When a voice command is received, Rhasspy will call your program and push the recorded WAV data (16-bit 16 Khz mono) to standard in. Your program should print the text transcription to standard out.

See
[speech2text.sh](https://github.com/synesthesiam/rhasspy-hassio-addon/blob/master/bin/mock-commands/speech2text.sh)
for an example program.

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
