Rhasspy Voice Assistant
=============================

Rhasspy is an offline, multilingual voice assistant toolkit inspired by [Jasper](https://jasperproject.github.io/) that works with [Home Assistant](https://www.home-assistant.io/) and [Hass.io](https://www.home-assistant.io/hassio/).

Purpose
---------

A typical voice assistant (Alexa, Google Home, etc.) solves a number of important problems:

1. Deciding when to listen (wake word)
2. Listening for commands/questions (wait for silence)
3. Transcribing command/question (speech to text)
4. Interpreting the speaker's *intent* from the text (intent recognition)
5. Fulfilling the speaker's intent (e.g., playing a song, answering a question)

Rhasspy provides offline, private solutions to problems 1-4 using off-the-shelf tools. These tools are:

1. [Pocketsphinx Keyphrase](https://cmusphinx.github.io/wiki/tutoriallm/#using-keyword-lists-with-pocketsphinx) (wake word)
2. [PyAudio](https://people.csail.mit.edu/hubert/pyaudio/) (wait for silence)
3. [Pocketsphinx](https://github.com/cmusphinx/pocketsphinx) (speech to text)
4. [RasaNLU](https://rasa.com/) (intent recognition)

For problem 5 (fulfilling the speaker's intent), Rhasspy works with Home Assistant's built-in [automation capability](https://www.home-assistant.io/docs/automation/). For each intent you define, Rhasspy sends an event to Home Assistant that can be used to do anything Home Assistant can do (toggle switches, call REST services, etc.). This means that Rhasspy will do very little out of the box compared to other voice assistants, but there will also be no limits to what can be done.
 
Intended Audience
---------------------

Rhasspy is intended for advanced users that want to have a voice interface to Home Assistant, but value **privacy** and **freedom** above all else. There are many other voice assistants, but none (to my knowledge) that:

1. Can function **completely disconnected from the Internet**
2. Are entirely free/open source
3. Work well with Home Assistant and Hass.io

If you feel comfortable sending your voice commands through the Internet for someone else to process, or are not comfortable with rolling your own Home Assistant automations to handle intents, I recommend taking a look at [Mycroft](https://mycroft.ai).

Customization
----------------

Rhasspy allows you to customize every stage of intent recognition, including:

1. Defining custom wake words
2. Providing example sentences that you want to be recognized, annotated with intent information
3. Specifying how you pronounce specific words, including words that Rhasspy doesn't know

Profiles
----------

All of the files Rhasspy needs for wake word detection, speech transcription, and intent recognition are contained in a *profile* directory. Out of the box, Rhasspy contains profiles for English (en), Spanish (es), French (fr), German (de), Italian (it), and Dutch (nl).

The important files in a profile are:

* `acoustic_model/`
  * Directory with CMU acoustic model (16 Khz)
* `base_dictionary.txt`
  * Large CMU dictionary file with general word pronunciations
* `custom_words.txt`
  * Small CMU dictionary file with custom word pronunciations for you
* `unknown_words.txt`
  * Small CMU dictionary file with guessed word pronunciations by phonetisaurus
* `g2p.fst`
  * Finite state tranducer used by phonetisaurus to guess unknown word pronunciations
* `language_model.txt`
  * ARPA trigram model created from user sentences
* `phoneme_examples.txt`
  * Text file with example words/pronunciations for each phoneme
* `phonemes.txt`
  * Text file mapping from CMU to eSpeak phonemes 
* `profile.json`
  * Overrides profile settings from `defaults.json`
  * See [profile documentation](doc/profiles.md) for details
* `rasa_config.yml`
  * YAML configuration for RasaNLU
* `classes.yml`
  * Class expansions for user-defined word classes
* `sentences.yml`
  * Intents and sentences used to generate language model and train intent recognizer
  
Running
---------

Rhasspy is intended to run in three possible ways:

1. In a Python virtual environment
  * Use the `create-venv.sh` and `run-venv.sh` scripts (expects a Debian distribution)
  * Local `profiles` directory is used
2. In a standalone Docker container
  * Use `make docker` target and `run-docker.sh` script
  * Local `profiles` directory is used
3. As a Hass.io add-on
  * Clone the repo into your `/addons` directory and install/build
  * See the add-on's `/data` directory for `profiles`

Supporting Tools
--------------------

The following tools/libraries help to support Rhasspy:

* [Flask](http://flask.pocoo.org) (web server)
* [Opengrm](http://www.opengrm.org/twiki/bin/view/GRM/NGramLibrary) (language modeling)
* [Phonetisaurus](https://github.com/AdolfVonKleist/Phonetisaurus) (word pronunciations)
* [Python 3](https://www.python.org)
* [Sox](http://sox.sourceforge.net) (WAV conversion)
* [Vue.js](https://vuejs.org/) (web UI)
