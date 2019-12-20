# Reference

* [Supported Languages](#supported-languages)
* [HTTP API](#http-api)
* [Websocket API](#websocket-api)
* [MQTT API](#mqtt-api)
* [Command Line](#command-line)
* [Profile Settings](#profile-settings)

## Supported Languages

The table below lists which components and compatible with Rhasspy's supported languages.

| Category               | Name                                           | Offline?               | en       | de       | es       | fr       | it       | nl       | ru       | el       | hi       | zh       | vi       | pt       | sv       | ca       |
| --------               | ------                                         | --------               | -------  | -------  | -------  | -------  | -------  | -------  | -------  | -------  | -------  | -------  | -------  | -------  | -------  | -------  |
| **Wake Word**          | [pocketsphinx](wake-word.md#pocketsphinx)      | &#x2713;               | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; |          |          |          |          |
|                        | [porcupine](wake-word.md#porcupine)            | &#x2713;               | &#x2713; |          |          |          |          |          |          |          |          |          |          |          |          |          |
|                        | [snowboy](wake-word.md#snowboy)                | *requires account*     | &#x2713; | &bull;   | &bull;   | &bull;   | &bull;   | &bull;   | &bull;   | &bull;   | &bull;   | &bull;   | &bull;   | &bull;   | &bull;   | &bull;   |
|                        | [precise](wake-word.md#mycroft-precise)        | &#x2713;               | &#x2713; | &bull;   | &bull;   | &bull;   | &bull;   | &bull;   | &bull;   | &bull;   | &bull;   | &bull;   | &bull;   | &bull;   | &bull;   | &bull;   |
| **Speech to Text**     | [pocketsphinx](speech-to-text.md#pocketsphinx) | &#x2713;               | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; |          | &#x2713; |          | &#x2713; |
|                        | [kaldi](speech-to-text.md#kaldi)               | &#x2713;               | &#x2713; | &#x2713; |          | &#x2713; |          | &#x2713; |          |          |          |          | &#x2713; |          | &#x2713; |          |
| **Intent Recognition** | [fsticuffs](intent-recognition.md#fsticuffs)   | &#x2713;               | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; |
|                        | [fuzzywuzzy](intent-recognition.md#fuzzywuzzy) | &#x2713;               | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; |
|                        | [adapt](intent-recognition.md#mycroft-adapt)   | &#x2713;               | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; |
|                        | [flair](intent-recognition.md#flair)           | &#x2713;               | &#x2713; | &#x2713; | &#x2713; | &#x2713; |          | &#x2713; |          |          |          |          |          | &#x2713; |          | &#x2713; |
|                        | [rasaNLU](intent-recognition.md#rasanlu)       | *needs extra software* | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; |
| **Text to Speech**     | [espeak](text-to-speech.md#espeak)             | &#x2713;               | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; |
|                        | [flite](text-to-speech.md#flite)               | &#x2713;               | &#x2713; |          |          |          |          |          |          |          | &#x2713; |          |          |          |          |          |
|                        | [picotts](text-to-speech.md#picotts)           | &#x2713;               | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; |          |          |          |          |          |          |          |          |          |
|                        | [marytts](text-to-speech.md#marytts)           | &#x2713;               | &#x2713; | &#x2713; |          | &#x2713; | &#x2713; |          | &#x2713; |          |          |          |          |          |          |          |
|                        | [wavenet](text-to-speech.md#google-wavenet)    |                        | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; | &#x2713; |          | &#x2713; | &#x2713; |          | &#x2713; | &#x2713; |          |

&bull; - yes, but requires training/customization

## HTTP API

Rhasspy's HTTP endpoints are documented below. You can also visit `/api/` in your Rhasspy server (note the final slash) to try out each endpoint.

Application authors may want to use the [rhasspy-client](https://pypi.org/project/rhasspy-client/), which provides a high-level interface to a remote Rhasspy server.

### Endpoints

* `/api/custom-words`
  * GET custom word dictionary as plain text, or POST to overwrite it
  * See `custom_words.txt` in your profile directory
* `/api/download-profile`
  * Force Rhasspy to re-download profile
  * `?delete=true` - clear download cache
* `/api/listen-for-command`
  * POST to wake Rhasspy up and start listening for a voice command
  * Returns intent JSON when command is finished
  * `?nohass=true` - stop Rhasspy from handling the intent
  * `?timeout=<seconds>` - override default command timeout
  * `?entity=<entity>&value=<value>` - set custom entity/value in recognized intent
* `/api/listen-for-wake-word`
  * POST to wake Rhasspy up and return immediately
* `/api/lookup`
  * POST word as plain text to look up or guess pronunciation
  * `?n=<number>` - return at most `n` guessed pronunciations
* `/api/microphones`
  * GET list of available microphones
* `/api/phonemes`
  * GET example phonemes from speech recognizer for your profile
  * See `phoneme_examples.txt` in your profile directory
* `/api/play-wav`
  * POST to play WAV data
* `/api/profile`
  * GET the JSON for your profile, or POST to overwrite it
  * `?layers=profile` to only see settings different from `defaults.json`
  * See `profile.json` in your profile directory
* `/api/restart`
  * Restart Rhasspy server
* `/api/sentences`
  * GET voice command templates or POST to overwrite
  * Set `Accept: application/json` to GET JSON with all sentence files
  * Set `Content-Type: application/json` to POST JSON with sentences for multiple files
  * See `sentences.ini` and `intents` directory in your profile
* `/api/slots`
  * GET slot values as JSON or POST to add to/overwrite them
  * `?overwrite_all=true` to clear slots in JSON before writing
* `/api/speakers`
  * GET list of available audio output devices
* `/api/speech-to-intent`
  * POST a WAV file and have Rhasspy process it as a voice command
  * Returns intent JSON when command is finished
  * `?nohass=true` - stop Rhasspy from handling the intent
* `/api/start-recording`
  * POST to have Rhasspy start recording a voice command
* `/api/stop-recording`
  * POST to have Rhasspy stop recording and process recorded data as a voice command
  * Returns intent JSON when command has been processed
  * `?nohass=true` - stop Rhasspy from handling the intent
* `/api/test-microphones`
  * GET list of available microphones and if they're working
* `/api/text-to-intent`
  * POST text and have Rhasspy process it as command
  * Returns intent JSON when command has been processed
  * `?nohass=true` - stop Rhasspy from handling the intent
* `/api/text-to-speech`
  * POST text and have Rhasspy speak it
  * `?play=false` - get WAV data instead of having Rhasspy speak
  * `?voice=<voice>` - override default TTS voice
  * `?language=<language>` - override default TTS language or locale
  * `?repeat=true` - have Rhasspy repeat the last sentence it spoke
* `/api/train`
  * POST to re-train your profile
  * `?nocache=true` - re-train profile from scratch
* `/api/unknown-words`
  * GET words that Rhasspy doesn't know in your sentences
  * See `unknown_words.txt` in your profile directory

## Websocket API

* `/api/events/intent`
  * Listen for recognized intents published as JSON
* `/api/events/log`
  * Listen for log messages published as plain text

## MQTT API

Rhasspy implements part of the [Hermes](https://docs.snips.ai/reference/hermes) protocol. Various services of Rhasspy can be configured to pass along MQTT messages or to react to MQTT messages following the Hermes protocol.

* `hermes/audioServer/<SITE_ID>/playBytes/<REQUEST_ID>`
  * Rhasspy publishes audio in WAV format to this topic. By default it is 16 kHz, 16-bit mono for compatibility reaons, but other types are possible too.
  * `SITE_ID` is set in Rhasspy's `mqtt` configuration.
  * `REQUEST_ID` is generated using `uuid.uuid4` each time a sound is played.
* `hermes/audioServer/<SITE_ID>/audioFrame`
  * Rhasspy listens to this topic for WAV data. Audio is automatically converted to 16 kHz, 16-bit mono audio and played.
  * `SITE_ID` is set in Rhasspy's `mqtt` configuration.
* `hermes/asr/startListening`
  * Rhasspy wakes up and starts recording on receiving this topic.
  * The payload is a JSON object with a `siteId` key that holds Rhasspy's site ID.
* `hermes/asr/stopListening`
  * Rhasspy stops recording and processes the voice command on receiving this topic.
  * The payload is a JSON object with a `siteId` key that holds Rhasspy's site ID.
* `hermes/intent/<INTENT_NAME>`
  * Rhasspy publishes a message to this topic on recognition of an intent.
  * The payload is a JSON object with the recognized intent, entities and text.
* `hermes/nlu/intentNotRecognized`
  * Rhasspy publishes a message to this topic when it doesn't recognize an intent.
* `hermes/asr/textCaptured`
  * Rhasspy publishes a transcription to this topic each time a voice command is recognized.
* `hermes/hotword/<WAKEWORD_ID>/detected`
  * Rhasspy wakes up when a message is received on this topic.
* More to follow

## Command Line

Rhasspy provides a powerful [command-line interface](usage.md#command-line) called `rhasspy-cli`.

For `rhasspy-cli --profile <PROFILE_NAME> <COMMAND> <ARGUMENTS>`, `<COMMAND>` can be:

* `info`
  * Print profile JSON to standard out
  * Add `--defaults` to only print settings from `defaults.json`
* `wav2text`
  * Convert WAV file(s) to text
* `wav2intent`
  * Convert WAV file(s) to intent JSON
  * Add `--handle` to have Rhasspy send events to Home Assistant
* `text2intent`
  * Convert text command(s) to intent JSON
  * Add `--handle` to have Rhasspy send events to Home Assistant
* `train`
  * Re-train your profile
* `mic2wav`
  * Listen for a voice command and output WAV data
  * Add `--timeout <SECONDS>` to stop recording after some number of seconds
* `mic2text`
  * Listen for a voice command and convert it to text
  * Add `--timeout <SECONDS>` to stop recording after some number of seconds
* `mic2intent`
  * Listen for a voice command output intent JSON
  * Add `--handle` to have Rhasspy send events to Home Assistant
  * Add `--timeout <SECONDS>` to stop recording after some number of seconds
* `word2phonemes`
  * Print the CMU phonemes for a word (possibly unknown)
  * Add `-n <COUNT>` to control the maximum number of guessed pronunciations
* `word2wav`
  * Pronounce a word (possibly unknown) and output WAV data
* `text2speech`
  * Speaks one or more sentences using Rhasspy's text to speech system
* `text2wav`
  * Converts a single sentence to WAV using Rhasspy's text to speech system
* `sleep`
  * Run Rhasspy and wait until wake word is spoken
* `download`
  * Download necessary profile files from the internet

### Profile Operations

Print the complete JSON for the English profile with:

    rhasspy-cli --profile en info

You can combine this with other commands, such as `jq` to get at specific pieces:

    rhasspy-cli info --profile en | jq .wake.pocketsphinx.keyphrase

Output (JSON):

    "okay rhasspy"

### Training

Retrain your the English profile with:

    rhasspy-cli --profile en train

Add `--debug` before `train` for more information.

### Speech to Text/Intent

Convert a WAV file to text from stdin:

    rhasspy-cli --profile en wav2text < what-time-is-it.wav

Output (text):

    what time is it

Convert multiple WAV files:

    rhasspy-cli --profile en wav2text what-time-is-it.wav turn-on-the-living-room-lamp.wav

Output (JSON)

```json
{
    "what-time-is-it.wav": "what time is it",
    "turn-on-the-living-room-lamp.wav": "turn on the living room lamp"
}
```

Convert multiple WAV file(s) to intents **and** handle them:

    rhasspy-cli --profile en wav2intent --handle what-time-is-it.wav turn-on-the-living-room-lamp.wav

Output (JSON):

```json
{
    "what_time_is_it.wav": {
        "text": "what time is it",
        "intent": {
            "name": "GetTime",
            "confidence": 1.0
        },
        "entities": []
    },
    "turn_on_living_room_lamp.wav": {
        "text": "turn on the living room lamp",
        "intent": {
            "name": "ChangeLightState",
            "confidence": 1.0
        },
        "entities": [
            {
                "entity": "state",
                "value": "on"
            },
            {
                "entity": "name",
                "value": "living room lamp"
            }
        ]
    }
}
```

### Text to Intent

Handle a command as if it was spoken:

    rhasspy-cli --profile en text2intent --handle "turn off the living room lamp"

Output (JSON):

```json
{
    "turn off the living room lamp": {
        "text": "turn off the living room lamp",
        "intent": {
            "name": "ChangeLightState",
            "confidence": 1.0
        },
        "entities": [
            {
                "entity": "state",
                "value": "off"
            },
            {
                "entity": "name",
                "value": "living room lamp"
            }
        ]
    }
}
```

### Record Your Voice

Save a voice command to a WAV:

    rhasspy-cli --profile en mic2wav > my-voice-command.wav

You can listen to it with:

    aplay my-voice-command.wav

### Test Your Wake Word

Start Rhasspy and wait for wake word:

    rhasspy-cli --profile en sleep

Should exit and print the wake word when its spoken.

### Text to Speech

Have Rhasspy speak one or more sentences:

    rhasspy-cli --profile en text2speech "We ride at dawn!"

Use a different text to speech system and voice:

    rhasspy-cli --profile en \
        --set 'text_to_speech.system' 'flite' \
        --set 'text_to_speech.flite.voice' 'slt' \
        text2speech "We ride at dawn!"

### Pronounce Words

Speak words Rhasspy doesn't know!

    rhasspy-cli --profile en word2wav raxacoricofallapatorius | aplay

### Text to Speech to Text to Intent

Use the miracle of Unix pipes to have Rhasspy interpret voice commands from itself:

    rhasspy-cli --profile en \
        --set 'text_to_speech.system' 'picotts' \
        text2wav "turn on the living room lamp" | \
          rhasspy-cli --profile en wav2text | \
            rhasspy-cli --profile en text2intent

Output (JSON):

```json
{
    "turn on the living room lamp": {
        "text": "turn on the living room lamp",
        "intent": {
            "name": "ChangeLightState",
            "confidence": 1.0
        },
        "entities": [
            {
                "entity": "state",
                "value": "on"
            },
            {
                "entity": "name",
                "value": "living room lamp"
            }
        ],
        "speech_confidence": 1,
        "slots": {
            "state": "on",
            "name": "living room lamp"
        }
    }
}
```

## Profile Settings

All available profile sections and settings are listed below:

* `rhasspy` - configuration for Rhasspy assistant
  * `preload_profile` - true if speech/intent recognizers should be loaded immediately for default profile (default: `true`)
  * `listen_on_start` - true if Rhasspy should listen for wake word at startup (default: `true`)
  * `load_timeout_sec` - number of seconds to wait for internal actors before proceeding with start up
* `home_assistant` - how to communicate with Home Assistant/Hass.io
  * `url` - Base URL of Home Assistant server (no `/api`)
  * `access_token` -  long-lived access token for Home Assistant (Hass.io token is used automatically)
  * `api_password` - Password, if you have that enabled (deprecated)
  * `pem_file` - Full path to your <a href="http://docs.python-requests.org/en/latest/user/advanced/#ssl-cert-verification">CA_BUNDLE file or a directory with certificates of trusted CAs</a>
  * `event_type_format` - Python format string used to create event type from intent type (`{0}`)
* `speech_to_text` - transcribing [voice commands to text](speech-to-text.md)
  * `system` - name of speech to text system (`pocketsphinx`, `remote`, `command`, or `dummy`)
  * `pocketsphinx` - configuration for [Pocketsphinx](speech-to-text.md#pocketsphinx)
    * `compatible` - true if profile can use pocketsphinx for speech recognition
    * `acoustic_model` - directory with CMU 16Khz acoustic model
    * `base_dictionary` - large text file with word pronunciations (read only)
    * `custom_words` - small text file with words/pronunciations added by user
    * `dictionary` - text file with all words/pronunciations needed for example sentences
    * `unknown_words` - small text file with guessed word pronunciations (from phonetisaurus)
    * `language_model` - text file with trigram [ARPA language model](https://cmusphinx.github.io/wiki/arpaformat/) built from example sentences
    * `open_transcription` - true if general language model should be used (custom voices commands ignored)
    * `base_language_model` - large general language model (read only)
    * `mllr_matrix` - MLLR matrix from [acoustic model tuning](https://cmusphinx.github.io/wiki/tutorialtuning/)
    * `mix_weight` - how much of the base language model to [mix in during training](training.md#language-model-mixing) (0-1)
    * `mix_fst` - path to save mixed ngram FST model
  * `kaldi` - configuration for [Kaldi](speech-to-text.md#kaldi)
    * `compatible` - true if profile can use Kaldi for speech recognition
    * `kaldi_dir` - absolute path to Kaldi root directory
    * `model_dir` - directory where Kaldi model is stored (relative to profile directory)
    * `graph` - directory where HCLG.fst is located (relative to `model_dir`)
    * `base_graph` - directory where large general HCLG.fst is located (relative to `model_dir`)
    * `base_dictionary` - large text file with word pronunciations (read only)
    * `custom_words` - small text file with words/pronunciations added by user
    * `dictionary` - text file with all words/pronunciations needed for example sentences
    * `open_transcription` - true if general language model should be used (custom voices commands ignored)
    * `unknown_words` - small text file with guessed word pronunciations (from phonetisaurus)
    * `mix_weight` - how much of the base language model to [mix in during training](training.md#language-model-mixing) (0-1)
    * `mix_fst` - path to save mixed ngram FST model
  * `remote` - configuration for [remote Rhasspy server](speech-to-text.md#remote-http-server)
    * `url` - URL to POST WAV data for transcription (e.g., `http://your-rhasspy-server:12101/api/speech-to-text`)
  * `command` - configuration for [external speech-to-text program](speech-to-text.md#command)
    * `program` - path to executable
    * `arguments` - list of arguments to pass to program
  * `sentences_ini` - Ini file with example [sentences/JSGF templates](training.md#sentencesini) grouped by intent
  * `sentences_dir` - Directory with additional sentence templates (default: `intents`)
  * `g2p_model` - finite-state transducer for phonetisaurus to guess word pronunciations
  * `g2p_casing` - casing to force for g2p model (`upper`, `lower`, or blank)
  * `dictionary_casing` - casing to force for dictionary words (`upper`, `lower`, or blank)
  * `grammars_dir` - directory to write generated JSGF grammars from sentences ini file
  * `fsts_dir` - directory to write generated finite state transducers from JSGF grammars
* `intent` - transforming text commands to intents
  * `system` - intent recognition system (`fsticuffs`, `fuzzywuzzy`, `rasa`, `remote`, `adapt`, `command`, or `dummy`)
  * `fsticuffs` - configuration for [OpenFST-based](https://www.openfst.org) intent recognizer
    * `intent_fst` - path to generated finite state transducer with all intents combined
    * `ignore_unknown_words` - true if words not in the FST symbol table should be ignored
    * `fuzzy` - true if text is matching in a fuzzy manner, skipping words in `stop_words.txt`
  * `fuzzywuzzy` - configuration for simplistic [Levenshtein distance](https://en.wikipedia.org/wiki/Levenshtein_distance) based intent recognizer
    * `examples_json` - JSON file with intents/example sentences
    * `min_confidence` - minimum confidence required for intent to be converted to a JSON event (0-1)
  * `remote` - configuration for remote Rhasspy server
    * `url` - URL to POST text to for intent recognition (e.g., `http://your-rhasspy-server:12101/api/text-to-intent`)
  * `rasa` - configuration for [Rasa NLU](https://rasa.com/) based intent recognizer
    * `url` - URL of remote Rasa NLU server (e.g., `http://localhost:5005/`)
    * `examples_markdown` - Markdown file to generate with intents/example sentences
    * `project_name` - name of project to generate during training
  * `adapt` - configuration for [Mycroft Adapt](https://github.com/MycroftAI/adapt) based intent recognizer
    * `stop_words` - text file with words to ignore in training sentences
  * `command` - configuration for external speech-to-text program
    * `program` - path to executable
    * `arguments` - list of arguments to pass to program
* `text_to_speech` - pronouncing words
  * `system` - text to speech system (`espeak`, `flite`, `picotts`, `marytts`, `command`, or `dummy`)
  * `espeak` - configuration for [eSpeak](http://espeak.sourceforge.net)
    * `phoneme_map` - text file mapping CMU phonemes to eSpeak phonemes
  * `flite` - configuration for [flite](http://www.festvox.org/flite)
    * `voice` - name of voice to use (e.g., `kal16`, `rms`, `awb`)
  * `picotts` - configuration for [PicoTTS](https://en.wikipedia.org/wiki/SVOX)
    * `language` - language to use (default if not present)
  * `marytts` - configuration for [MaryTTS](http://mary.dfki.de)
    * `url` - address:port of MaryTTS server (port is usually 59125)
    * `voice` - name of voice to use (e.g., `cmu-slt`). Default if not present.
    * `locale` - name of locale to use (e.g., `en-US`). Default if not present.
  * `wavenet` - configuration for Google's [WaveNet](https://cloud.google.com/text-to-speech/docs/wavenet)
    * `cache_dir` - path to directory in your profile where WAV files are cached
    * `credentials_json` - path to the JSON credentials file (generated online)
    * `gender` - gender of speaker (`MALE` `FEMALE`)
    * `language_code` - language/locale e.g. `en-US`,
    * `sample_rate` - WAV sample rate (default: 22050)
    * `url` - URL of WaveNet endpoint
    * `voice` - voice to use (e.g., `Wavenet-C`)
    * `fallback_tts` - text to speech system to use when offline or error occurs (e.g., `espeak`)
  * `phoneme_examples` - text file with examples for each CMU phoneme
* `training` - training speech/intent recognizers
  * `dictionary_number_duplicates` - true if duplicate words in dictionary should be suffixed by `(2)`, `(3)`, etc.
  * `tokenizer` - system used to break sentences into words (`regex` only for now)
  * `regex` - configuration for regex tokenizer
    * `replace` - list of dictionaries with patterns/replacements used on each example sentence
    * `split` - pattern used to break sentences into words
  * `unknown_words` - configuration for dealing with words not in base/custom dictionaries
    * `fail_when_present` - true if Rhasspy should halt training when unknown words are found
    * `guess_pronunciations` - true if [Phonetisaurus](https://github.com/AdolfVonKleist/Phonetisaurus) should be used to guess how an unknown word is pronounced
  * `speech_to_text` - training for speech decoder
    * `system` - speech to text training system (`auto`, `pocketsphinx`, `kaldi`, `command`, or `dummy`)
    * `command` - configuration for external speech-to-text training program
      * `program` - path to executable
      * `arguments` - list of arguments to pass to program
  * `intent` - training for intent recognizer
    * `system` - intent recognizer training system (`auto`, `fsticuffs`, `fuzzywuzzy`, `rasa`, `adapt`, `command`, or `dummy`)
    * `command` - configuration for external intent recognizer training program
      * `program` - path to executable
      * `arguments` - list of arguments to pass to program
* `wake` - waking Rhasspy up for speech input
  * `system` - wake word recognition system (`pocketsphinx`, `snowboy`, `precise`, `porcupine`, `command`, or `dummy`)
  * `pocketsphinx` - configuration for Pocketsphinx wake word recognizer
    * `keyphrase` - phrase to wake up on (3-4 syllables recommended)
    * `threshold` - sensitivity of detection (recommended range 1e-50 to 1e-5)
    * `chunk_size` - number of bytes per chunk to feed to Pocketsphinx (default 960)
  * `snowboy` - configuration for [snowboy](https://snowboy.kitt.ai)
    * `model` - path to model file(s), separated by commas (in profile directory)
    * `sensitivity` - model sensitivity (0-1, default 0.5)
    * `audio_gain` - audio gain (default 1)
    * `apply_frontend` - true if ApplyFrontend should be set
    * `chunk_size` - number of bytes per chunk to feed to snowboy (default 960)
    * `model_settings` - settings for each snowboy model path (e.g., `snowboy/snowboy.umdl`)
      * <MODEL_PATH>
        * `sensitivity` - model sensitivity
        * `audio_gain` - audio gain
        * `apply_frontend` - true if ApplyFrontend should be set
  * `precise` - configuration for [Mycroft Precise](https://github.com/MycroftAI/mycroft-precise)
    * `engine_path` - path to the precise-engine binary
    * `model` - path to model file (in profile directory)
    * `sensitivity` - model sensitivity (0-1, default 0.5)
    * `trigger_level`  - number of events to trigger activation (default 3)
    * `chunk_size` - number of bytes per chunk to feed to Precise (default 2048)
  * `porcupine` - configuration for [PicoVoice's Porcupine](https://github.com/Picovoice/Porcupine)
    * `library_path` - path to  `libpv_porcupine.so` for your platform/architecture
    * `model_path` - path to the `porcupine_params.pv` (lib/common)
    * `keyword_path` - path to the `.ppn` keyword file
    * `sensitivity` - model sensitivity (0-1, default 0.5)
  * `command` - configuration for external speech-to-text program
    * `program` - path to executable
    * `arguments` - list of arguments to pass to program
* `microphone` - configuration for audio recording
  * `system` - audio recording system (`pyaudio`, `arecord`, `hermes`, `http`, or `dummy`)
  * `pyaudio` - configuration for [PyAudio](https://people.csail.mit.edu/hubert/pyaudio/) microphone
    * `device` - index of device to use or empty for default device
    * `frames_per_buffer` - number of frames to read at a time (default 480)
  * `arecord` - configuration for ALSA microphone
    * `device` - name of ALSA device (see `arecord -L`) to use or empty for default device
    * `chunk_size` - number of bytes to read at a time (default 960)
  * `http` - configuration for HTTP audio stream
    * `host` - hostname or IP address of HTTP audio server (default 127.0.0.1)
    * `port` - port to receive audio stream on (default 12333)
    * `stop_after` - one of "never", "text", or "intent" ([see documentation](audio-input.md#http-stream))
  * `gstreamer` - configuration for GStreamer audio recorder
    * `pipeline` - GStreamer pipeline (e.g., `FILTER ! FILTER ! ...`) without sink
  * `hermes` - configuration for MQTT "microphone" ([Hermes protocol](https://docs.snips.ai/ressources/hermes-protocol))
    * Subscribes to WAV data from `hermes/audioServer/<SITE_ID>/audioFrame`
    * Requires MQTT to be enabled
* `sounds` - configuration for feedback sounds from Rhasspy
  * `system` - which sound output system to use (`aplay`, `hermes`, or `dummy`)
  * `wake` - path to WAV file to play when Rhasspy wakes up
  * `recorded` - path to WAV file to play when a command finishes recording
  * `aplay` - configuration for ALSA speakers
    * `device` - name of ALSA device (see `aplay -L`) to use or empty for default device
  * `hermes` - configuration for MQTT "speakers" ([Hermes protocol](https://docs.snips.ai/ressources/hermes-protocol))
    * WAV data published to `hermes/audioServer/<SITE_ID>/playBytes/<REQUEST_ID>`
    * Requires MQTT to be enabled
* `command`
  * `system` - which voice command listener system to use (`webrtcvad`, `oneshot`, `hermes`, or `dummy`)
  * `webrtcvad` - configuration for [webrtcvad](https://github.com/wiseman/py-webrtcvad) system
    * `sample_rate` - sample rate of input audio
    * `chunk_size` - bytes per buffer (must be 10,20,30 ms)
    * `vad_mode` - sensitivity of `webrtcvad` (0-3)
    * `min_sec` - minimum number of seconds in a command
    * `silence_sec` - number of seconds of silences after voice command before stopping
    * `timeout_sec` - maximum number of seconds before stopping
    * `throwaway_buffers` - number of buffers to drop when recording starts
    * `speech_buffers` - number of buffers with speech before command starts
  * `oneshot` - configuration for voice command system that takes first audio frame as entire command
    * `timeout_sec` - maximum number of seconds before stopping
  * `command` - configuration for external voice command program
    * `program` - path to executable
    * `arguments` - list of arguments to pass to program
  * `hermes` - configuration for MQTT-based voice command system that listens betweens `startListening` and `stopListening` commands ([Hermes protocol](https://docs.snips.ai/ressources/hermes-protocol))
    * `timeout_sec` - maximum number of seconds before stopping
* `handle`
  * `system` - which intent handling system to use (`hass`, `command`, or `dummy`)
  * `forward_to_hass` - true if intents are always forwarded to Home Assistant (even if `system` is `command` or `remote`)
  * `command` - configuration for external speech-to-text program
    * `program` - path to executable
    * `arguments` - list of arguments to pass to program
  * `remote` - configuration for remote HTTP intent handler
    * `url` - URL to POST intent JSON to and receive response JSON from
* `mqtt` - configuration for MQTT ([Hermes protocol](https://docs.snips.ai/ressources/hermes-protocol))
  * `enabled` - true if MQTT client should be started
  * `host` - MQTT host
  * `port` - MQTT port
  * `username` - MQTT username (blank for anonymous)
  * `password` - MQTT password
  * `reconnect_sec` - number of seconds before client will reconnect
  * `site_id` - ID of site ([Hermes protocol](https://docs.snips.ai/ressources/hermes-protocol))
  * `publish_intents` - true if intents are published to MQTT
* `download` - configuration for profile file downloading
  * `cache_dir` - directory in your profile where downloaded files are cached
  * `conditions` - profile settings that will trigger file downloads
    * keys are profile setting paths (e.g., `wake.system`)
    * values are dictionaries whose keys are profile settings values (e.g., `snowboy`)
      * settings may have the form `<=N` or `!X` to mean "less than or equal to N" or "not X"
      * leaf nodes are dictionaries whose keys are destination file paths and whose values reference the `files` dictionary
  * `files` - locations, etc. of files to download
    * keys are names of files
    * values are dictionaries with:
      * `url` - URL of file to download
      * `cache` - `false` if file should be downloaded directly into profile (skipping cache)
