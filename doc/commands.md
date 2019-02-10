# Custom Commands

Most of Rhasspy's internal components can be replaced by calls to external
programs. This is usually done by setting the component's `system` to `command`,
and then supplying a `program` (path to executable) and optionally some
`arguments`.

The inputs and outputs of each program depend on the component, but in general
input will come in via standard in and output is expected on standard out.
Additionally, the following environment variables are available:

* `$RHASSPY_BASE_DIR` - path to the directory where Rhasspy is running from
* `$RHASSPY_PROFILE` - name of the current profile (e.g., "en")
* `$RHASSPY_PROFILE_DIR` - directory of the current profile (where `profile.json` is)

## Available Components

The components that can be customized via the `command` system are listed below.
You can find mocked up external programs for every component in the [mock
commands](https://github.com/synesthesiam/rhasspy-hassio-addon/tree/master/bin/mock-commands)
directory.

### Wake

Rhasspy normally listens for a wake word via
[pocketsphinx](https://github.com/cmusphinx/pocketsphinx),
[snowboy](https://snowboy.kitt.ai), etc. You can call a custom program that will
do this externally, only waking Rhasspy up when it exits.

Add to your `profile.json`:

    {
      "wake": {
        "system": "command",
        "command": {
          "program": "/path/to/program",
          "arguments": ["argument1", "argument2"]
        }
      },
      
      "rhasspy": {
        "listen_on_start": true
      }
    }
    
When Rhasspy starts, your program will be called with the given arguments. Once
your program detects the wake word, it should print it to standard out and exit.
Rhasspy will call your program again when it goes back to sleep. If the empty
string is printed, will not wake up.

See
[sleep.sh](https://github.com/synesthesiam/rhasspy-hassio-addon/blob/master/bin/mock-commands/sleep.sh)
for an example.


### Voice Command

When awake, Rhasspy normally listens for voice commands from the microphone and
waits for silence by using [webrtcvad](https://github.com/wiseman/py-webrtcvad).
You can call a custom program that will listen for a voice command and simply
return the recorded WAV audio data to Rhasspy.

Add to your `profile.json`:

    {
      "command": {
        "system": "command",
        "command": {
          "program": "/path/to/program",
          "arguments": ["argument1", "argument2"]
        }
      }
    }

When Rhasspy wakes up, your program will be called with the given arguments. The
program's output should be WAV data with the recorded voice command (Rhasspy
will automatically convert this to 16-bit 16Khz mono if necessary).

See
[listen.sh](https://github.com/synesthesiam/rhasspy-hassio-addon/blob/master/bin/mock-commands/listen.sh)
for an example.


### Speech to Text

Voice commands are normally transcribed by Rhasspy using
[pocketsphinx](https://github.com/cmusphinx/pocketsphinx). The acoustic model,
dictionary, and language model are available in your profile directory (after
training) as `acoustic_model/`, `dictionary.txt`, and `language_model.txt`
respectively. You can call a custom program to do speech to text that uses these
artifacts or does something totally different!

Add to your `profile.json`:

    {
      "speech_to_text": {
        "system": "command",
        "command": {
          "program": "/path/to/program",
          "arguments": ["argument1", "argument2"]
        }
      }
    }

When a voice command is received, Rhasspy will call your program and push the
recorded WAV data (16-bit 16 Khz mono) to standard in. Your program should print
the text transcription to standard out.

See
[speech2text.sh](https://github.com/synesthesiam/rhasspy-hassio-addon/blob/master/bin/mock-commands/speech2text.sh)
for an example.

If your speech to text system requires some kind of custom training, you should
also override Rhasspy's speech to text training system (see below).


### Speech to Text Training

Rhasspy generates training sentences from your [sentences.ini](sentences.md)
file, and then trains a custom language model using
[opengrm](http://www.opengrm.org/twiki/bin/view/GRM/NGramLibrary). You can call
a custom program instead if you want to use a different language modeling
toolkit or your custom speech to text system needs special training.

Add to your `profile.json`:

    {
      "training": {
        "speech_to_text": {
          "system": "command",
          "command": {
            "program": "/path/to/program",
            "arguments": ["argument1", "argument2"]
          }
        }
      }
    }

When training, your program will be called with all of the training sentences
grouped by intent in JSON to standard in. No output is expected from your
program besides a successful exit code. **NOTE**: Rhasspy will not generate
`dictionary.txt` or `language_model.txt` if you use a custom program.

The input JSON is an object where each key is the name of an intent and the values are lists of training sentence objects. Each sentence object has the text of the sentence, all tagged entities, and the tokens of the sentence.

Example input:

    {
      "GetTime": [
        {
          "sentence": "what time is it",
          "entities": [],
          "tokens": [
            "what",
            "time",
            "is",
            "it"
          ]
        },
        {
          "sentence": "tell me the time",
          "entities": [],
          "tokens": [
            "tell",
            "me",
            "the",
            "time"
          ]
        }
      ],
      "ChangeLightColor": [
        {
          "sentence": "set the bedroom light to red",
          "entities": [
            {
              "entity": "name",
              "value": "bedroom light",
              "text": "bedroom light",
              "start": 8,
              "end": 21
            },
            {
              "entity": "color",
              "value": "red",
              "text": "red",
              "start": 25,
              "end": 28
            }
          ],
          "tokens": [
            "set",
            "the",
            "bedroom",
            "light",
            "to",
            "red"
          ]
        }
      ]
    }

See
[train-stt.sh](https://github.com/synesthesiam/rhasspy-hassio-addon/blob/master/bin/mock-commands/train-stt.sh)
for an example.


### Intent Recognition

Rhasspy recognizes intents from text using one of several systems, such as
[fuzzywuzzy](https://github.com/seatgeek/fuzzywuzzy) or
[rasaNLU](https://rasa.com/). You can call a custom program that does intent
recognition from a text command.

Add to your `profile.json`:

    {
      "intent": {
        "system": "command",
        "command": {
          "program": "/path/to/program",
          "arguments": ["argument1", "argument2"]
        }
      }
    }

When a voice command is successfully transcribed, your program will be called
with the text transcription printed to standard in. Your program should return
JSON on standard out, something like:

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
    
See
[text2intent.sh](https://github.com/synesthesiam/rhasspy-hassio-addon/blob/master/bin/mock-commands/text2intent.sh)
for an example.

If you intent recognition system requires some special training, you should also
override Rhasspy's intent training system (see below).


### Intent Recognizer Training

During training, Rhasspy uses the sentences generated from
[sentences.ini](sentences.md) as training material for the selected intent
recognition system. These sentences are typically available in Markdown format
in your profile directory as `tagged_sentences.md`. If your intent recognition
system requires some special training, you can call a custom program here.

Add to your `profile.json`:

    {
      "training": {
        "intent": {
          "system": "command",
          "command": {
            "program": "/path/to/program",
            "arguments": ["argument1", "argument2"]
          }
        }
      }
    }
    
During training, Rhasspy will call your program with the training sentences
grouped by intent in JSON printed to standard in. No output is expected, besides
a successful exit code.

The input JSON is an object where each key is the name of an intent and the values are lists of training sentence objects. Each sentence object has the text of the sentence, all tagged entities, and the tokens of the sentence.

Example input:

    {
      "GetTime": [
        {
          "sentence": "what time is it",
          "entities": [],
          "tokens": [
            "what",
            "time",
            "is",
            "it"
          ]
        },
        {
          "sentence": "tell me the time",
          "entities": [],
          "tokens": [
            "tell",
            "me",
            "the",
            "time"
          ]
        }
      ],
      "ChangeLightColor": [
        {
          "sentence": "set the bedroom light to red",
          "entities": [
            {
              "entity": "name",
              "value": "bedroom light",
              "text": "bedroom light",
              "start": 8,
              "end": 21
            },
            {
              "entity": "color",
              "value": "red",
              "text": "red",
              "start": 25,
              "end": 28
            }
          ],
          "tokens": [
            "set",
            "the",
            "bedroom",
            "light",
            "to",
            "red"
          ]
        }
      ]
    }
    
See
[train-intent.sh](https://github.com/synesthesiam/rhasspy-hassio-addon/blob/master/bin/mock-commands/train-intent.sh)
for an example.


### Intent Handling

Once an intent is successfully recognized, Rhasspy will send an event to Home
Assistant with the details (as well as [publish it over
MQTT](https://docs.snips.ai/reference/dialogue#intent)). You can call a custom
program instead *or in addition* to this behavior.

Add to your `profile.json`:

    {
      "handle": {
        "system": "command",
        "command": {
          "program": "/path/to/program",
          "arguments": ["argument1", "argument2"]
        },
        "forward_to_hass": true
      }
    }
    
When an intent is recognized, Rhasspy will call your custom program with the
intent JSON printed to standard in. You should return JSON to standard out,
optionally with additional information. If `handle.forward_to_hass` is `true`,
Rhasspy will look for a `hass_event` property of the returned JSON with the
following structure:

    {
      // rest of input JSON
      // ...
      "hass_event": {
        "event_type": "...",
        "event_data": {
          "key": "value",
          // ...
        }
      }
    }
    
Rhasspy will create the Home Assistant event based on this information. If it is
**not** present, the remaining intent information will be used to construct the
event as normal (i.e., `intent` and `entities`). If `handle.forward_to_hass` is
`false`, the output of your program is not used.

See
[handle.sh](https://github.com/synesthesiam/rhasspy-hassio-addon/blob/master/bin/mock-commands/handle.sh)
for an example.
