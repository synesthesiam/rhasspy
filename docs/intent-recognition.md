# Intent Recognition

After you voice command has been transcribed by the [speech to text](speech-to-text.md) system, the next step is to recognize your intent. 

## Fsticuffs

Uses [OpenFST](https://www.openfst.org) to recognize **only** those sentences that were [trained](training.md#sentencesini). While less flexible than the other intent recognizers, `fsticuffs` can be trained and perform recognition over *millions* of sentences in milliseconds. If you only plan to recognize voice commands from your training set (and not unseen ones via text chat), `fsticuffs` is the best choice.

Add to your [profile](profiles.md):

```json
"intent": {
  "system": "fsticuffs",
  "fsticuffs": {
    "intent_fst": "intent.fst"
  }
}
```

See `rhasspy.intent.FsticuffsRecognizer` for details.

## Fuzzywuzzy

Finds the closest matching intent by using the [Levenshtein distance](https://en.wikipedia.org/wiki/Levenshtein_distance) between the text and the all of the [training sentences](training.md#sentencesini) you provided. Works best when you have a small number of sentences (dozens to hundreds) and need some resiliency to spelling errors (i.e., from text chat).

Add to your [profile](profiles.md):

```json
"intent": {
  "system": "fuzzywuzzy",
  "fuzzywuzzy": {
    "examples_json": "intent_examples.json"
  }
}
```

See `rhasspy.intent.FuzzyWuzzyRecognizer` for details.

## Mycroft Adapt

Recognizes intents using [Mycroft Adapt](https://github.com/MycroftAI/adapt). Works best when you have a medium number of sentences (hundreds to thousands) and need to be able to recognize sentences not seen during training (no new words, though).

Add to your [profile](profiles.md):

```json
"intent": {
  "system": "adapt", 
  "adapt": {
      "stop_words": "stop_words.txt"
  }
}
```

The `intent.adapt.stop_words` text file contains words that should be ignored (i.e., cannot be "required" or "optional").

See `rhasspy.intent.AdaptIntentRecognizer` for details.

## RasaNLU

Recognizes intents using a remote [rasaNLU](https://rasa.com/) server. Works well when you have a large number of sentences (thousands to hundreds of thousands) and need to handle sentences *and* words not seen during training.

Add to your [profile](profiles.md):

```json
"intent": {
  "system": "rasa",
  "rasa": {
    "examples_markdown": "intent_examples.md",
    "project_name": "rhasspy",
    "url": "http://localhost:5000/"
  }
}
```

See `rhasspy.intent.RasaIntentRecognizer` for details.

## Remote HTTP Server

Uses a remote Rhasppy server to do intent recognition. POSTs the text to an HTTP endpoint and receives the intent as JSON.

Add to your [profile](profiles.md):

```json
"intent": {
  "system": "remote",
  "remote": {
    "url": "http://my-server:12101/api/text-to-intent"
  }
}
```

See `rhasspy.intent.RemoteRecognizer` for details.

## Command

Recognizes intents from text using a custom external program.

Add to your [profile](profiles.md):

```json
"intent": {
  "system": "command",
  "command": {
    "program": "/path/to/program",
    "arguments": []
  }
}
```

Rhasspy recognizes intents from text using one of several systems, such as [fuzzywuzzy](https://github.com/seatgeek/fuzzywuzzy) or [rasaNLU](https://rasa.com/). You can call a custom program that does intent recognition from a text command.

When a voice command is successfully transcribed, your program will be called with the text transcription printed to standard in. Your program should return JSON on standard out, something like:

```json
{
  "intent": {
    "name": "ChangeLightColor",
    "confidence": 1.0
  },
  "entities": [
    { "entity": "name",
      "value": "bedroom light" },
    { "entity": "color",
      "value": "red" }
  ],
  "text": "set the bedroom light to red"
}
```
    
The following environment variables are available to your program:

* `$RHASSPY_BASE_DIR` - path to the directory where Rhasspy is running from
* `$RHASSPY_PROFILE` - name of the current profile (e.g., "en")
* `$RHASSPY_PROFILE_DIR` - directory of the current profile (where `profile.json` is)

See [text2intent.sh](https://github.com/synesthesiam/rhasspy/blob/master/bin/mock-commands/text2intent.sh) for an example program.

If you intent recognition system requires some special training, you should also override Rhasspy's [intent training system](training.md#intent-recognition).

See `rhasspy.intent.CommandRecognizer` for details.

## Dummy

Disables intent recognition.

Add to your [profile](profiles.md):

```json
"intent": {
  "system": "dummy"
}
```

See `rhasspy.intent.DummyRecognizer` for details.
