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

Each of these shortcomings are addressed by considering the space between intent headings (`[Intent 1]`, etc.) as a **grammar** that will *generate* tagged sentences in [rasaNLU's training data format](https://rasa.com/docs/nlu/dataformat/#markdown-format). The generated sentences, stripped of their tags, are used as input to [mitlm](https://github.com/mitlm/mitlm) to produce a language model for [pocketsphinx](https://github.com/cmusphinx/pocketsphinx). The tagged sentences are then used to train an intent recognizer.

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

Luckily, JSGF has a (tag feature)(https://www.w3.org/TR/jsgf/#15057) that lets you annotate portions of sentences/rules. Rhasspy assumes that the tags themselves are *slot names* and the tagged portions of the sentence are *slot values*. The `SetLightColor` example can be extended with tags like this:

    [SetLightColor]
    colors = (red | green | blue){color}
    set the light to <colors>
    
With the `{color}` tag attached to the `(red | green | blue)` alternative set, each color name will carry the tag. This is the same as typing `((red){color} | (green){color} | (blue){color})`, but less verbose. Rhasspy will now generate the following **tagged sentences**:

1. `set the light to [red](color)`
2. `set the light to [green](color)`
3. `set the light to [blue](color)`

When the `SetLightColor` intent is recognized now, the `rhasspy_SetLightColor` event will have some event data like:

    {
      "color": "red" 
    }
    
    
Your [automation](https://www.home-assistant.io/docs/automation) can use the slot values to take an appropriate action, such as (setting an RGB light's color)(https://www.home-assistant.io/docs/automation/action/) to `[255,0,0]`. 

#### Tag Synonyms

There are times where you want to match a particular part of your sentence with a tag, but want the actual *value* of the tag to be something different than the matched text. This is needed if you, for example, want to talk about entities in Home Assistant with phrases like "the living room lamp", but want to pass the appropriate entity id (say `lamp_1`) to Home Assistant instead.

Normally, you would tag part of a sentence like this:

    [ChangeLightState]
    turn on the (living room lamp){name}
    
When this intent is activated, Rhasspy will send an event named `rhasspy_ChangeLightState` to Home Assistant with

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

### Slots Lists

In the `SetLightColor` example above, the color names are stored in `sentences.ini` as a rule:

    colors = (red | green | blue)
    
Ths is convenient when the list of colors is small, changes infrequently, and does not depend on an external service.
But what if this was a list of movie names that were stored on your [Kodi Home Theater](https://kodi.tv)?

    movies = ("Primer" | "Moon" | "Chronicle" | "Timecrimes" | "Mulholland Drive" | ... )
    
It would be much easier if this list was stored externally, but could be *referenced* in the appropriate places in the grammar.
This is possible in Rhasspy by placing text files in the `speech_to_text.slots_dir` directory specified in your [profile](profiles.md) ("slots" by default).

If you're using the English (`en`) profile, for example, create the file `profiles/en/slots/movies.txt` and add the following content:

    Primer
    Moon
    Chronicle
    Timecrimes
    Mullholand Drive
    
This list of movie can now be referenced as `-movies-` in your your `sentences.ini` file! Something like:

    [PlayMovie]
    play (-movies-){movie_name}
    
will generate `rhasspy_PlayMovie` events like:

    {
      "movie_name": "Primer"
    }
    
If you update `movies.txt**, make sure to re-train Rhasspy in order to pick up the new movies.

**NOTE**: Rhasspy will look for `slots` in *all* of your [profile directories](profiles.md#profile-directories), merging together all of the same named text files it finds.

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

Rhasspy generates training sentences from your [sentences.ini](#sentencesini) file, and then trains a custom language model using [mitlm](https://github.com/mitlm/mitlm). You can call a custom program instead if you want to use a different language modeling toolkit or your custom speech to text system needs special training.

Add to your [profile](profiles.md):

```json
"training": {
  "speech_to_text": {
    "system": "command",
    "command": {
      "program": "/path/to/program",
      "arguments": ["argument1", "argument2"]
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

See [train-stt.sh](https://github.com/synesthesiam/rhasspy/blob/master/bin/mock-commands/train-stt.sh) for an example program.

## Intent Recognition

During training, Rhasspy uses the sentences generated from [sentences.ini](#sentencesini) as training material for the selected intent recognition system. If your intent recognition system requires some special training, you can call a custom program here.

Add to your [profile](profiles.md):

```json
"training": {
  "intent": {
    "system": "command",
    "command": {
      "program": "/path/to/program",
      "arguments": ["argument1", "argument2"]
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

}
```
    
The following environment variables are available to your program:

* `$RHASSPY_BASE_DIR` - path to the directory where Rhasspy is running from
* `$RHASSPY_PROFILE` - name of the current profile (e.g., "en")
* `$RHASSPY_PROFILE_DIR` - directory of the current profile (where `profile.json` is)

See [train-intent.sh](https://github.com/synesthesiam/rhasspy/blob/master/bin/mock-commands/train-intent.sh) for an example program.

