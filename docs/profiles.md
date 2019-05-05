# Profiles

A Rhasspy profile contains all of the necessary files for wake word detection, speech transcription, intent recognition, and training.

Each profile is a directory contained in the top-level `profiles` directory. The `profiles/defaults.json` file contains the default configuration for all profiles. The `profile.json` file *inside* each individual profile directory (e.g., `profiles/en/profile.json`) **overrides** settings in `defaults.json`.

When starting Rhasspy, you must specify a profile name with `--profile <NAME>` where `<NAME>` is the name of the profile directory (`en`, `nl`, etc.).

## Profile Directories

Rhasspy looks for profile-related files in two directories:

1. The **system profile directory** (read only)
    * Override with `--system-profiles <DIR>`
2. The **user profile directory** (read/write)
    * Override with `--user-profiles <DIR>`

Files in the user profile directory override system files, and Rhasspy will *only* ever write to the user profile directory.
The default location for each of these directories is:

* Virtual Environment
    * System profile location is `$PWD/profiles` where `$PWD` is Rhasspy's root directory (where `run-venv.sh` is located)
    * User profile location is `$HOME/.config/rhasspy/profiles`
* Docker
    * System profile location is either `/usr/share/rhasspy/profiles` (ALSA) or `/home/rhasspy/profiles` (PulseAudio)
    * User profile location **must** be explicity set and mapped to a volume:
        * `docker run ... -v /path/to/profiles:/profiles synesthesiam/rhasspy-server --user-profiles /profiles`

### Example

Assume you are running Rhasspy in a virtual environment, and you add some new sentences to the `en` (English) profile in the web interface. When saving the `sentences.ini` file, Rhasspy will create `$HOME/.config/rhasspy/profiles/en` (if it doesn't exist), and write `sentences.ini` in that directory. If you adjust and save your settings, you will find them in `$HOME/.config/rhasspy/profiles/en/profile.json`.

## Downloading Profiles

The first time Rhasspy loads a profile, it needs to download the required binary artifacts (acoustic model, base dictionary, etc.) from [the internet](https://github.com/synesthesiam/rhasspy-profiles/releases). After the initial download, Rhasspy can function completely offline.

If you need to install Rhasspy onto a machine that is not connected to the internet, you can simply download the artifacts yourself and place them in a `download` directory *inside* the appropriate profile directory. For example, the `fr` (French) profile has [three artifacts](https://github.com/synesthesiam/rhasspy-profiles/releases/tag/v1.0-fr):

1. `cmusphinx-fr-5.2.tar.gz`
2. `fr-g2p.tar.gz`
3. `fr-small.lm.gz`

If your user profile directory is `$HOME/.config/rhasspy/profiles`, then you should download/copy all three artifacts to `$HOME/.config/rhasspy/profiles/fr/download` on the offline machine. Now, when Rhasspy loads the `fr` profile and you click "Download", it will extract the files in the `download` directory without going out to the internet. 

If you want to know precisely which files Rhasspy is looking for for a given profile, visit the `profiles` directory in [the source code](https://github.com/synesthesiam/rhasspy/tree/master/profiles) and examine these scripts in that profile's directory:

* `download-profile.sh`
    * Downloads and extracts all required binary artifacts. Uses cache in `download` directory unless `--delete` option is given.
* `check-profile.sh`
    * Verifies that required binary artifacts are present. Returns non-zero exit code if download is required.

## Available Settings

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
        * `mllr_matrix` - MLLR matrix from [acoustic model tuning](https://cmusphinx.github.io/wiki/tutorialtuning/) 
    * `kaldi` - configuration for [Kaldi](speech-to-text.md#kaldi)
        * `compatible` - true if profile can use Kaldi for speech recognition
        * `kaldi_dir` - absolute path to Kaldi root directory
        * `model_dir` - directory where Kaldi model is stored (relative to profile directory)
        * `graph` - directory where HCLG.fst is located (relative to `model_dir`)
        * `base_dictionary` - large text file with word pronunciations (read only)
        * `custom_words` - small text file with words/pronunciations added by user
        * `dictionary` - text file with all words/pronunciations needed for example sentences
        * `unknown_words` - small text file with guessed word pronunciations (from phonetisaurus)
    * `remote` - configuration for [remote Rhasspy server](speech-to-text.md#remote-http-server)
        * `url` - URL to POST WAV data for transcription (e.g., `http://your-rhasspy-server:12101/api/speech-to-text`)
    * `command` - configuration for [external speech-to-text program](speech-to-text.md#command)
        * `program` - path to executable
        * `arguments` - list of arguments to pass to program
    * `sentences_ini` - Ini file with example [sentences/JSGF templates](training.md#sentencesini) grouped by intent
    * `g2p_model` - finite-state transducer for phonetisaurus to guess word pronunciations
    * `g2p_casing` - casing to force for g2p model (`upper`, `lower`, or blank)
    * `dictionary_casing` - casing to force for dictionary words (`upper`, `lower`, or blank)
    * `grammars_dir` - directory to write generated JSGF grammars from sentences ini file
    * `fsts_dir` - directory to write generated finite state transducers from JSGF grammars
* `intent` - transforming text commands to intents
    * `system` - intent recognition system (`fsticuffs`, `fuzzywuzzy`, `rasa`, `remote`, `adapt`, `command`, or `dummy`)
    * `fsticuffs` - configuration for [OpenFST-based](https://www.openfst.org) intent recognizer
        * `intent_fst` - path to generated finite state transducer with all intents combined
    * `fuzzywuzzy` - configuration for simplistic [Levenshtein distance](https://en.wikipedia.org/wiki/Levenshtein_distance) based intent recognizer
        * `examples_json` - JSON file with intents/example sentences
        * `min_confidence` - minimum confidence required for intent to be converted to a JSON event (0-1)
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
