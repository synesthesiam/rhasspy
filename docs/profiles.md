# Profiles

A Rhasspy profile contains all of the necessary files for wake word detection,
speech transcription, intent recognition, and training.

Each profile is a directory contained in the top-level `profiles` directory, The
`profiles/defaults.json` file contains the default configuration for all
profiles. The `profile.json` file *inside* each individual profile directory
(e.g., `profiles/en/profile.json`) **overrides** settings in `defaults.json`.

## Profile Directories

Rhasspy uses an environment variable named `RHASSPY_PROFILES` to decide where to read/write profile files. By default, this is set to a directory named `profiles` wherever Rhasspy is running.

Similar to the Unix `PATH` environment variable, you can add more directories to `RHASSPY_PROFILES` (separated by ":"). Rhasspy will go through the list of directories from **right to left** (like `PATH`) when reading or writing a profile file (like `profile.json`). When *reading* a profile file, Rhasspy tries each of the directories until the file is found. When *writing* a profile file, Rhasspy will try to write to each directory, stopping when it succeeds.

### Example

Assume you have `RHASSPY_PROFILES="/usr/share/rhasspy/profiles:/profiles"` and you add some new sentences to the `en` (English) profile in the web interface. When saving the `sentences.ini` file, Rhasspy will search for a **writable** directory in the following order:

1. `/profiles/en/`
2. `/usr/share/rhasspy/profiles/en/`

If `/profiles/en` is writable, then `/profiles/en/sentences.ini` will be written with all of your sentences. When Rhasspy attempts to locate the profile file `sentences.ini` in the future, `/profiles/en/sentences.ini` will be found **first** and loaded *instead of* `/usr/share/rhasspy/profiles/en/sentences.ini`.

## Default Profile

Rhasspy desides which profile to load by looking at the value of `rhasspy.default_profile` in the **first** `defaults.json` file in can find in the `RHASSPY_PROFILES` environment variable (right to left). You can override this behavior by setting `RHASSPY_PROFILE` to the name of a different profile. This is easy to see with the [command-line interface](usage.md#command-line):

    rhasspy-cli info --debugs | jq .rhasspy.default_profile
    "en"

    rhasspy-cli info | jq .language
    "en"
    
    RHASSPY_PROFILE=fr rhasspy-cli info | jq .language
    "fr"

## Available Settings

All available profile sections and settings are listed below:

* `rhasspy` - configuration for Rhasspy assistant
    * `default_profile` - name of the default profile
    * `preload_profile` - true if speech/intent recognizers should be loaded immediately for default profile
    * `listen_on_start` - true if Rhasspy should listen for wake word at startup
* `home_assistant` - how to communicate with Home Assistant/Hass.io
    * `url` - Base URL of Home Assistant server (no `/api`)
    * `access_token` -  long-lived access token for Home Assistant (Hass.io token is used automatically)
    * `api_password` - Password, if you have that enabled (deprecated)
    * `pem_file` - Full path to your <a href="http://docs.python-requests.org/en/latest/user/advanced/#ssl-cert-verification">CA_BUNDLE file or a directory with certificates of trusted CAs</a>
    * `event_type_format` - Python format string used to create event type from intent type (`{0}`)
* `speech_to_text` - transcribing [voice commands to text](speech-to-text.md)
    * `system` - name of speech to text system (`pocketsphinx`, `remote`, `command`, or `dummy`)
    * `pocketsphinx` - configuration for [Pocketsphinx](speech-to-text.md#pocketsphinx)
        * `acoustic_model` - directory with CMU 16Khz acoustic model
        * `base_dictionary` - large text file with word pronunciations (read only)
        * `custom_words` - small text file with words/pronunciations added by user
        * `dictionary` - text file with all words/pronunciations needed for example sentences
        * `unknown_words` - small text file with guessed word pronunciations (from phonetisaurus)
        * `language_model` - text file with trigram [ARPA language model](https://cmusphinx.github.io/wiki/arpaformat/) built from example sentences
        * `mllr_matrix` - MLLR matrix from [acoustic model tuning](https://cmusphinx.github.io/wiki/tutorialtuning/) 
    * `remote` - configuration for [remote Rhasspy server](speech-to-text.md#remote-http-server)
        * `url` - URL to POST WAV data for transcription (e.g., `http://your-rhasspy-server:12101/api/speech-to-text`)
    * `command` - configuration for [external speech-to-text program](speech-to-text.md#command)
        * `program` - path to executable
        * `arguments` - list of arguments to pass to program
    * `sentences_ini` - Ini file with example [sentences/JSGF templates](training.md#sentencesini) grouped by intent
    * `sentences_text` - text file with all example sentences expanded and repeated
    * `g2p_model` - finite-state transducer for phonetisaurus to guess word pronunciations
    * `g2p_casing` - casing to force for g2p model (`upper`, `lower`, or blank)
    * `grammars_dir` - directory to write generated JSGF grammars from sentences ini file
* `intent` - transforming text commands to intents
    * `system` - intent recognition system (`fuzzywuzzy`, `rasa`, `remote`, `adapt`, `command`, or `dummy`)
    * `fuzzywuzzy` - configuration for simplistic [Levenshtein distance](https://en.wikipedia.org/wiki/Levenshtein_distance) based intent recognizer
        * `examples_json` - JSON file with intents/example sentences
    * `remote` - configuration for remote Rhasspy server
        * `url` - URL to POST text to for intent recognition (e.g., `http://your-rhasspy-server:12101/api/text-to-intent`)
    * `rasa` - configuration for [rasaNLU](https://rasa.com/) based intent recognizer
        * `url` - URL of remote rasaNLU server (e.g., `http://localhost:5000/`)
        * `examples_markdown` - Markdown file to generate with intents/example sentences
        * `project_name` - name of project to generate during training
    * `adapt` - configuration for [Mycroft Adapt](https://github.com/MycroftAI/adapt) based intent recognizer
        * `stop_words` - text file with words to ignore in training sentences
    * `command` - configuration for external speech-to-text program
        * `program` - path to executable
        * `arguments` - list of arguments to pass to program
* `text_to_speech` - pronouncing words
    * `system` - text to speech system (only `espeak` for now)
    * `espeak`
        * `phoneme_map` - text file mapping CMU phonemes to eSpeak phonemes
    * `phoneme_examples` - text file with examples for each CMU phoneme
* `training` - training speech/intent recognizers
    * `sentences`
        * `balance_by_intent` - true if example sentences should be repeated to make all intents equally likely
        * `casing` - make all sentences `lower` or `upper` case (do nothing if not present)
        * `write_weights` - `true` if sentence weights should be written in the first column instead of repeating them (default: `false`)
        * `write_sorted` - `true` if sentences should be sorted before writing out (default: `false`)
    * `tokenizer` - system used to break sentences into words (`regex` only for now)
    * `regex` - configuration for regex tokenizer
        * `replace` - list of dictionaries with patterns/replacements used on each example sentence
        * `split` - pattern used to break sentences into words
    * `speech_to_text` - training for speech decoder
        * `system` - speech to text training system (`auto`, `pocketsphinx`, `command`, or `dummy`)
        * `command` - configuration for external speech-to-text training program
            * `program` - path to executable
            * `arguments` - list of arguments to pass to program
    * `intent` - training for intent recognizer
        * `system` - intent recognizer training system (`auto`, `fuzzywuzzy`, `rasa`, `adapt`, `command`, or `dummy`)
        * `command` - configuration for external intent recognizer training program
            * `program` - path to executable
            * `arguments` - list of arguments to pass to program
* `wake` - waking Rhasspy up for speech input
    * `system` - wake word recognition system (`pocketsphinx`, `snowboy`, `precise`, `command`, or `dummy`)
    * `pocketsphinx` - configuration for Pocketsphinx wake word recognizer
        * `keyphrase` - phrase to wake up on (3-4 syllables recommended)
        * `threshold` - sensitivity of detection (recommended range 1e-50 to 1e-5)
        * `chunk_size` - number of bytes per chunk to feed to Pocketsphinx (default 960)
    * `snowboy` - configuration for [snowboy](https://snowboy.kitt.ai)
        * `model` - path to model file (in profile directory)
        * `sensitivity` - model sensitivity (0-1, default 0.5)
        * `audio_gain` - audio gain (default 1)
        * `chunk_size` - number of bytes per chunk to feed to snowboy (default 960)
    * `precise` - configuration for [Mycroft Precise](https://github.com/MycroftAI/mycroft-precise)
        * `engine_path` - path to the precise-engine binary
        * `model` - path to model file (in profile directory)
        * `sensitivity` - model sensitivity (0-1, default 0.5)
        * `trigger_level`  - number of events to trigger activation (default 3)
        * `chunk_size` - number of bytes per chunk to feed to Precise (default 2048)
  * `command` - configuration for external speech-to-text program
      * `program` - path to executable
      * `arguments` - list of arguments to pass to program
* `microphone` - configuration for audio recording
    * `system` - audio recording system (`pyaudio`, `arecord`, `hermes`, or `dummy`)
    * `pyaudio` - configuration for [PyAudio](https://people.csail.mit.edu/hubert/pyaudio/) microphone
        * `device` - index of device to use or empty for default device
        * `frames_per_buffer` - number of frames to read at a time (default 480)
    * `arecord` - configuration for ALSA microphone
        * `device` - name of ALSA device (see `arecord -L`) to use or empty for default device
        * `chunk_size` - number of bytes to read at a time (default 960)
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
    * `forward_to_hass` - true if intents are always forwarded to Home Assistant (even if `system` is `command`)
    * `command` - configuration for external speech-to-text program
        * `program` - path to executable
        * `arguments` - list of arguments to pass to program
* `mqtt` - configuration for MQTT ([Hermes protocol](https://docs.snips.ai/ressources/hermes-protocol))
    * `enabled` - true if MQTT client should be started
    * `host` - MQTT host
    * `port` - MQTT port
    * `username` - MQTT username (blank for anonymous)
    * `password` - MQTT password
    * `reconnect_sec` - number of seconds before client will reconnect
    * `site_id` - ID of site ([Hermes protocol](https://docs.snips.ai/ressources/hermes-protocol))
    * `publish_intents` - true if intents are published to MQTT
* `tuning` - configuration for acoustic model tuning
    * `system` - system for tuning (currently only `sphinxtrain`)
    * `sphinxtrain` - configuration for [sphinxtrain](https://github.com/cmusphinx/sphinxtrain) based acoustic model tuning
        * `mllr_matrix` - name of generated MLLR matrix (should match `speech_to_text.pocketsphinx.mllr_matrix`)
