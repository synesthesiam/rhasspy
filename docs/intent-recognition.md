# Intent Recognition

After you voice command has been transcribed by the [speech to text](speech-to-text.md) system, the next step is to recognize your intent. 

## Fuzzywuzzy

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

Add to your [profile](profiles.md):

```json
"intent": {
  "system": "adapt", 
  "adapt": {
      "stop_words": "stop_words.txt"
  }
}
```

See `rhasspy.intent.AdaptIntentRecognizer` for details.

## RasaNLU

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
