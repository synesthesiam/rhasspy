# Training

Rhasspy is designed to recognize only the specific set of voice commands that [you provide](#sentencesini). These commands are categorized by **intent**, and may contain variable **slots** or **entities**, such as the color and name of a light.

During the training process, Rhasspy simulataneously trains *both* a speech and intent recognizer. The speech recognizer converts voice commands to text, and the intent recognizer converts text to JSON events. Combined, they enable a low power, offline system like a Raspberry Pi to understand and respond to your voice commands.

## How It Works

Recognizing voice commands typically involves two main steps:

1. Speech to text (transcription)
2. Text to intent (recognition)

For step (1), Rhasspy uses [pocketsphinx](https://github.com/cmusphinx/pocketsphinx) or [Kaldi](https://kaldi-asr.org), and generates a custom [ARPA language model](https://cmusphinx.github.io/wiki/arpaformat/) during the training process. Specifically, the steps are:

1. Convert the grammar from your [sentences.ini](#sentencesini) file to a [finite state transducer](https://www.openfst.org)
2. (Optionally) generate all possible sentences that can be spoken with entities tagged (e.g., `name` is `bedroom light`, `color` is `red`)
3. Use the [opengrm](http://www.opengrm.org/twiki/bin/view/GRM/NGramLibrary) toolkit to create a custom language model
4. Train an intent recognizer with the tagged sentences

Additionally, a custom [CMU phonetic dictionary](https://cmusphinx.github.io/wiki/tutorialdict/) is generated with *only* the words in your voice commands (and wake word, if you're using a [pocketsphinx keyphrase](wake-word.md#pocketsphinx)). If the pronunciation of a word is not known, Rhasspy calls out to [phonetisaurus](https://github.com/AdolfVonKleist/Phonetisaurus) to get a guess, and then halts training. Once you've confirmed the pronunciations by adding them to your [custom words](#custom-words), training can continue.

For step (4), Rhasspy can use a [variety of intent recognition systems](intent-recognition.md). However, most are all trained from the **tagged sentences** generated from [sentences.ini](#sentencesini), e.g., `turn [on](state) the [living room lamp](name)`. These sentences are transformed into JSON, like:

    {
      "ChangeLightState": [
        {
          "text": "turn on the living room lamp",
          "entities": [
            { "entity": "state", "value": "on" },
            { "entity": "name", "value": "living room lamp" }
          ]
        },
        ...
      ],
      ...
    }

and provided as training material to the intent recognition system. The [fuzzywuzzy](intent-recognition.md#fuzzywuzzy) system, for example, simply saves the JSON file and, during recognition, finds the closest matching sentence according to the [Levenshtein distance](https://en.wikipedia.org/wiki/Levenshtein_distance). The [default intent recognizer](intent-recognition.md#fsticuffs) interacts directly with the finite state transducer(s) generated in step (1) and, while less tolerant of errors than `fuzzywuzzy`, is significantly faster for large sets of voice commands (i.e., millions).

More sophisticated systems like [rasaNLU](intent-recognition.md#rasanlu) use machine learning techniques to classify sentences by intent and assign slota (entity) values. These systems are much better at recognizing sentences not seen during training, but can take minutes to hours to train.

## sentences.ini

Voice commands are recognized by Rhasspy from a set of sentences that you define in your [profile](profiles.md). These are stored in an [ini file](https://docs.python.org/3/library/configparser.html) whose "values" are simplified [JSGF grammars](https://www.w3.org/TR/jsgf/). The set of all sentences *generated* from these grammars is used to train an [ARPA language model](https://cmusphinx.github.io/wiki/arpaformat/) and an intent recognizer.

### Motivation

The combination of an ini file and JSGF is arguably an abuse of two file formats, so why do this? At a minimum, Rhasspy needs a set of sentences grouped by intent in order to train the speech and intent recognizers. A fairly pleasant way to express this in text is as follows:

    [Intent 1]
    sentence 1
    sentence 2
    ...

    [Intent 2]
    sentence 3
    sentence 4
    ...

Compared to JSON, YAML, etc., there is minimal syntactic overhead for the purposes of just writing down sentences. However, its shortcomings become painfully obvious once you have more than a handful of sentences and intents:

1. If two sentences are nearly identical, save for an *optional word* like "the" or "a", you have to maintain two nearly identical copies of a sentence.
2. When speaking about collections of things, like colors or states (on/off), you need a sentence for every *alternative choice*.
3. You cannot share commonly *repeated phrases* across sentences or intents.
4. There is no way to *tag phrases* so the intent recognizer knows the values for an intent's slots (e.g., color).

Each of these shortcomings are addressed by considering the space between intent headings (`[Intent 1]`, etc.) as a **grammar** that will *generate* tagged sentences in [rasaNLU's training data format](https://rasa.com/docs/nlu/dataformat/#markdown-format). The generated sentences, stripped of their tags, are used as input to [opengrm](https://www.opengrm.org) to produce a language model for [pocketsphinx](https://github.com/cmusphinx/pocketsphinx) or [Kaldi](https://kaldi-asr.org). The tagged sentences are then used to train an intent recognizer.

### Optional Words

Within a sentence, you can specify optional word(s) by surrounding them `[with brackets]`. These will generate at least two sentences: one with the optional word(s), and one without. So the following sentence template:

    [an] example sentence [with] some optional words

will generate 4 concrete sentences:

1. `an example sentence with some optional words`
2. `example sentence with some optional words`
3. `an example sentence some optional words`
4. `example sentence some optional words`

### Alternatives

A set of items, where only one is present at a time, is `(specified | like | this)`. For N items, there will be N sentences generated (unless you nest optional words, etc.). The template:

    set the light to (red | green | blue)

will generate:

1. `set the light to red`
2. `set the light to green`
3. `set the light to blue`

### Rules

Rules allow you to reuse common phrases, alternatives, etc. Rules are defined by `rule_name = ...` alongside your sentences and referenced by `<rule_name>`. The template above with colors could be rewritten as:

    colors = (red | green | blue)
    set the light to <colors>

which will generate the same 4 sentences as above. Importantly, you can **share rules** across intents by prefixing the rule's name with the intent name followed by a dot:

    [SetLightColor]
    colors = (red | green | blue)
    set the light to <colors>

    [GetLightColor]
    is the light <SetLightColor.colors>

The second intent (`GetLightColor`) references the `colors` rule from `SetLightColor`.

### Tags

The example templates above will generate sentences for training the speech recognizer, but using them to train the intent recognizer will not be satisfactory. The `SetLightColor` intent, when recognized, will result in a Home Assistant event called `rhasspy_SetLightColor`. But the actual *color* will not be provided because the intent recognizer is not aware that a `color` slot should exist (and has the values `red`, `green`, and `blue`).

Luckily, JSGF has a [tag feature](https://www.w3.org/TR/jsgf/#15057) that lets you annotate portions of sentences/rules. Rhasspy assumes that the tags themselves are *slot/entity names* and the tagged portions of the sentence are *slot/entity values*. The `SetLightColor` example can be extended with tags like this:

    [SetLightColor]
    colors = (red | green | blue){color}
    set the light to <colors>

With the `{color}` tag attached to the `(red | green | blue)` alternative set, each color name will carry the tag. This is the same as typing `((red){color} | (green){color} | (blue){color})`, but less verbose. Rhasspy will now generate the following **tagged sentences**:

1. `set the light to [red](color)`
2. `set the light to [green](color)`
3. `set the light to [blue](color)`

When the `SetLightColor` intent is recognized now, the corresponding JSON event (`rhasspy_SetLightColor` in Home Assistant) will have the following properties:

    {
      "color": "red"
    }


A Home Assistant [automation](https://www.home-assistant.io/docs/automation) can use the slot values to take an appropriate action, such as [setting an RGB light's color](https://www.home-assistant.io/docs/automation/action/) to `[255,0,0]` (red).

#### Tag Synonyms

There are times where you want to match a particular part of your sentence with a tag, but want the actual *value* of the tag to be something different than the matched text. This is needed if you want to talk about entities in Home Assistant, for example, with phrases like "the living room lamp", but want to pass the appropriate entity id (say `lamp_1`) to Home Assistant instead.

Normally, you would tag part of a sentence like this:

    [ChangeLightState]
    turn on the (living room lamp){name}

When this intent is activated, Rhasspy will send a JSON event (named `rhasspy_ChangeLightState` in Home Assistant) with:

    {
      "name": "living room lamp"
    }

You can catch this event in a Home Assistant automation, match the `name` "living room name", and do something with the `lamp_1` entity. That's fine for one instance, but would require a separate rule for every `name`! Instead, let's add a tag **synonym**:

    [ChangeLightState]
    turn on the (living room lamp){name:lamp_1}

The tag label and synonym are separated by a ":". When this sentence is spoken and the intent is activated, the same `rhasspy_ChangeLightState` event will be sent to Home Assistant, but with the following data:

    {
      "name": "lamp_1"
    }

Now in your Home Assistant automation, you could use [templating](https://www.home-assistant.io/docs/automation/templating/) to plug the `name` directly into the `entity_id` field of an action. One rule to rule them all.

This same technique could be used to replace number words with digits, like:

    [SetTimer]
    set a timer for (ten){number:10} seconds

which would generate an event like this when recognized:

    {
      "number": "10"
    }

### Slots Lists

In the `SetLightColor` example above, the color names are stored in `sentences.ini` as a rule:

    colors = (red | green | blue)

Ths is convenient when the list of colors is small, changes infrequently, and does not depend on an external service.
But what if this was a list of movie names that were stored on your [Kodi Home Theater](https://kodi.tv)?

    movies = ("Primer" | "Moon" | "Chronicle" | "Timecrimes" | "Mulholland Drive" | ... )

It would be much easier if this list was stored externally, but could be *referenced* in the appropriate places in the grammar.
This is possible in Rhasspy by placing text files in the `speech_to_text.slots_dir` directory specified in your [profile](profiles.md) ("slots" by default).

If you're using the English (`en`) profile, for example, create the file `profiles/en/slots/movies` and add the following content:

    Primer
    Moon
    Chronicle
    Timecrimes
    Mullholand Drive

This list of movie can now be referenced as `$movies` in your your `sentences.ini` file! Something like:

    [PlayMovie]
    play ($movies){movie_name}

will generate `rhasspy_PlayMovie` events like:

    {
      "movie_name": "Primer"
    }

If you update the `movies` file, make sure to re-train Rhasspy in order to pick up the new movie names.

### Special Cases

If one of your sentences happens to start with an optional word (e.g., `[the]`), this can lead to a problem:

    [SomeIntent]
    [the] problem sentence

Python's [configparser](https://docs.python.org/3/library/configparser.html) will interpret `[the]` as a new section header, which will produce a new intent, grammar, etc. Rhasspy handles this special case by using a backslash escape sequence (`\[`):

    [SomeIntent]
    \[the] problem sentence

Now `[the]` will be properly interpreted as a sentence under `[SomeIntent]`. You only need to escape a `[` if it's the **very first** character in your sentence.

## Custom Words

Rhasspy looks for words you've defined outside of your profile's base dictionary (typically `base_dictionary.txt`) in a custom words file (typically `custom_words.txt`). This is just a [CMU phonetic dictionary](https://cmusphinx.github.io/wiki/tutorialdict/) with words/pronunciations separated by newlines:

    hello H EH L OW
    world W ER L D

You can use the [Words tab](usage.md#words-tab) in Rhasspy's web interface to generate this dictionary. During training, Rhasspy will merge `custom_words.txt` into your `dictionary.txt` file so the [speech to text](speech-to-text.md) system knows the words in your voice commands are pronounced.

## Speech to Text

By default, Rhasspy generates training sentences from your [sentences.ini](#sentencesini) file, and then trains a custom language model using [opengrm](https://www.opengrm.org). You can call a **custom program** instead if you want to use a different language modeling toolkit or your custom speech to text system needs special training.

Add to your [profile](profiles.md):

```json
"training": {
  "speech_to_text": {
    "system": "command",
    "command": {
      "program": "/path/to/program",
      "arguments": []
    }
  }
}
```

When training, your program will be called with all of the training sentences grouped by intent in JSON to standard in. No output is expected from your program besides a successful exit code. **NOTE**: Rhasspy will not generate `dictionary.txt` or `language_model.txt` if you use a custom program.

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
              "value": "bedroom light"
            },
            {
              "entity": "color",
              "value": "red"
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

See [train-stt.sh](https://github.com/synesthesiam/rhasspy/blob/master/bin/mock-commands/train-stt.sh) for an example program.

## Intent Recognition

During training, Rhasspy uses the sentences generated from [sentences.ini](#sentencesini) as training material for the selected intent recognition system. If your intent recognition system requires some special training, you can call a **custom program** here.

Add to your [profile](profiles.md):

```json
"training": {
  "intent": {
    "system": "command",
    "command": {
      "program": "/path/to/program",
      "arguments": []
    }
  }
}
```

During training, Rhasspy will call your program with the training sentences grouped by intent in JSON printed to standard in. No output is expected, besides a successful exit code.

The input JSON is an object where each key is the name of an intent and the values are lists of training sentence objects. Each sentence object has the text of the sentence, all tagged entities, and the tokens of the sentence.

Example input:

```json
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
          "value": "bedroom light"
        },
        {
          "entity": "color",
          "value": "red"
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

}
```

The following environment variables are available to your program:

* `$RHASSPY_BASE_DIR` - path to the directory where Rhasspy is running from
* `$RHASSPY_PROFILE` - name of the current profile (e.g., "en")
* `$RHASSPY_PROFILE_DIR` - directory of the current profile (where `profile.json` is)

See [train-intent.sh](https://github.com/synesthesiam/rhasspy/blob/master/bin/mock-commands/train-intent.sh) for an example program.


## Language Model Mixing

Rhasspy is designed to only respond to the voice commands you specify in [sentences.ini](training.md#sentencesini), but both the Pocketsphinx and Kaldi speech to text systems are capable of transcribing open ended speech. While this will never be as good as a cloud-based system, Rhasspy offers it as an option.

Open ended speech is achieved in Rhasspy by the inclusion of `base_dictionary.txt` and `base_language_model.txt` files in every profile. The former is a dictionary containing the pronunciations all possible words. The latter is a large language model trained on very large corpus of text in the profile's language (usually books and web pages).

During training, Rhasspy can **mix** this large, open ended language model with the one generated specifically for your voice commands. You specify a **mixture weight**, which controls how much of an influence the large language model has; a mixture weight of 0 makes Rhasspy sensitive *only* to your voice commands, which is the default.

![Diagram of Rhasspy's training process](img/training.svg)

To see the effect of language model mixing, consder a simple `sentences.ini` file:

```
[ChangeLightState]
turn (on){state} the living room lamp
```

This will only allow Rhasspy to understand the voice command "turn on the living room lamp". If we train Rhasspy and perform speech to text on a WAV file with this command, the output is no surprise:

```
$ rhasspy-cli --profile en train
OK

$ rhasspy-cli --profile en wav2text < turn_on_living_room_lamp.wav
turn on the living room lamp
```

Now let's do speech to text on a variation of the command, a WAV file with the speech "would you please turn on the living room lamp":

```
$ rhasspy-cli --profile en wav2text < would_you_please_turn_on_living_room_lamp.wav
on the the the turn on the living room lamp
```

The word salad here is because we're trying to recognize a voice command that was not present in `sentences.ini`. We could always add it, of course, and that is the preferred method for Rhasspy. There may be cases, however, where we cannot anticipate all of the variations of a voice command. For these cases, you should increase the `mix_weight` in your [profile](profiles.md) to something above 0:

```
$ rhasspy-cli --profile en \
    --set 'speech_to_text.pocketsphinx.mix_weight' '0.05' \
    train

OK
```

Note that training will take **significantly** longer because of the size of the base langauge model. Now, let's test our two WAV files:

```
$ rhasspy-cli --profile en wav2text < turn_on_living_room_lamp.wav
turn on the living room lamp

$ rhasspy-cli --profile en wav2text < would_you_please_turn_on_living_room_lamp.wav
would you please turn on the living room lamp
```

Great! Rhasspy was able to transcribe a sentence that it wasn't explicitly trained on. If you're trying this at home, you surely noticed that it takes a lot longer to process the WAV files too. In practice, it's not recommended to do mixed language modeling on lower-end hardware like a Raspberry Pi. If you need open ended speech recognition, try running Rhasspy in a [client/server set up](speech-to-text.md#remote-http-server).

### The Elephant in the Room

This isn't the end of the story for open ended speech recognition in Rhasspy, however, because Rhasspy also does *intent recognition* using the transcribed text as input. When the set of possible voice commands is known ahead of time, it's relatively easy to know what to do with each and every sentence. The flexibility gained from mixing in a base language model unfortunately places a large burden on the intent recognizer.

In our `ChangeLightState` example above, we're fortunate that everything works as expected:

```
$ echo 'would you please turn on the living room lamp' | \
    rhasspy-cli --profile en text2intent

{
    "would you please turn on the living room lamp": {
        "text": "turn on the living room lamp",
        "intent": {
            "name": "ChangeLightState",
            "confidence": 1.0
        },
        "entities": [
            {
                "entity": "state",
                "value": "on"
            }
        ],
        "tokens": [
            "turn",
            "on",
            "the",
            "living",
            "room",
            "lamp"
        ],
        "speech_confidence": 1,
        "slots": {
            "state": "on"
        }
    }
}
```

But this works only because the default intent recognizer ([fsticuffs](intent-recognition.md#fsticuffs)) ignores unknown words by default, so "would you please" is not interpreted. Changing "lamp" to "light" in the input sentence will reveal the problem:


```
$ echo 'would you please turn on the living room light | \
    rhasspy-cli --profile en text2intent

{
    "would you please turn on the living room light": {
        "text": "",
        "intent": {
            "name": "",
            "confidence": 0
        },
        "entities": [],
        "speech_confidence": 1,
        "slots": {}
    }
}
```

This sentence would be impossible for the speech to text system to recognize without language model mixing, but it's quite possible now. We can band-aid over the problem a bit by switching to the [fuzzywuzzy](intent-recognition.md#fuzzywuzzy) intent recognizer:

```
$ rhasspy-cli --profile en \
    --set 'speech_to_text.pocketsphinx.mix_weight' '0.05' \
    --set 'intent.system' 'fuzzywuzzy' \
    train

OK
```

Now when we interpret the sentence with "light" instead of "lamp", we still get the expected output:

```
$ echo 'would you please turn on the living room light' | \
    rhasspy-cli --profile en --set 'intent.system' 'fuzzywuzzy' text2intent

{
    "would you please turn on the living room light": {
        "text": "turn on the living room lamp",
        "intent": {
            "name": "ChangeLightState",
            "confidence": 0.86
        },
        "entities": [
            {
                "entity": "state",
                "value": "on"
            }
        ],
        "speech_confidence": 1,
        "slots": {
            "state": "on"
        }
    }
}
```

This works well for our toy example, but will not scale well when there are thousands of voice commands represented in `sentences.ini` or if the words used are significantly different than in the training set ("light" and "lamp" are close enough for `fuzzywuzzy`).

A machine learning-based intent recognizer, like [flar](intent-recognition.md#flair), would be a better choice for open ended speech.
