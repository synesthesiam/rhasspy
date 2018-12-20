Rhasspy Voice Assistant
=============================

Rhasspy is an offline, multilingual voice assistant toolkit inspired by [Jasper](https://jasperproject.github.io/) that works with [Home Assistant](https://www.home-assistant.io/) and [Hass.io](https://www.home-assistant.io/hassio/).

* [Video Introduction](https://www.youtube.com/watch?v=ijKTR_GqWwA)
* [Hass.IO Add-On Repository](https://github.com/synesthesiam/hassio-addons)
* [Running Rhasspy](#running)
* [Discussion](https://community.home-assistant.io/t/rhasspy-offline-voice-assistant-toolkit/60862)

To run Rhasspy using Docker:

    docker run -d -p 12101:12101 \
          --restart unless-stopped \
          -e RHASSPY_PROFILES=/profiles \
          -v "$HOME/.rhasspy:/profiles" \
          --device /dev/snd:/dev/snd \
          synesthesiam/rhasspy-hassio-addon:latest
          
Then visit the web interface at http://localhost:12101

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

How it Works
---------------

Rhasspy transforms speech commands into [Home Assistant events](https://www.home-assistant.io/docs/configuration/events/) that [trigger automations](https://www.home-assistant.io/docs/automation/trigger/#event-trigger). You define these commands in a Rhasspy [profile](doc/profiles.md) using a specialized template syntax that lets you control how Rhasspy creates the events it sends to Home Assistant.

Let's say you have an RGB light of some kind in your bedroom that's hooked up already to Home Assistant. You'd like to be able to say things like "*set the bedroom light to red*" to change its color. To start, you could write a [Home Assistant automation](https://www.home-assistant.io/docs/automation/action/) to help you out:

    automation:
      # Change the light in the bedroom to red.
      trigger:
        ...
      action:
        service: light.turn_on
        data:
          rgb_color: [255, 0, 0]
          entity_id: light.bedroom
          
Now you just need the trigger! Rhasspy will send events that can be caught with the [event trigger platform](https://www.home-assistant.io/docs/automation/trigger/#event-trigger). A different event will be sent for each *intent* that you define, with slot values corresponding to important parts of the command (like light name and color). Let's start by defining an intent in Rhasspy called `ChangeLightColor` that can be said a few different ways:

    [ChangeLightColor]
    colors = (red | green | blue) {color}
    set [the] (bedroom){name} [to] <colors>
    
This is a [simplified JSGF grammar](doc/sentences/md) that will generate the following sentences:

* set the bedroom to red
* set the bedroom to green
* set the bedroom to blue
* set the bedroom red
* set the bedroom green
* set the bedroom blue
* set bedroom to red
* set bedroom to green
* set bedroom to blue
* set bedroom red
* set bedroom green
* set bedroom blue

Rhasspy uses these sentences to create an [ARPA language model](https://cmusphinx.github.io/wiki/arpaformat/) for speech recognition, and also train an intent recognizer that can extract relevant parts of the command. The `{color}` tag in the `colors` rule will make Rhasspy put a `color` property in each event with the name of the recognized color (red, green, or blue). Likewise, the `{name}` tag on `bedroom` will add a `name` property to the event.

If trained on these sentences, Rhasspy will now recognize commands like "*set the bedroom light to red*" and send a `rhasspy_ChangeLightState` to Home Assistant with the following data:

    {
      "name": "bedroom",
      "color": "red"
    }
    
You can now fill in the rest of the Home Assistant automation:
    
    automation:
      # Change the light in the bedroom to red.
      trigger:
        platform: event
        event_type: rhasspy_ChangeLightState
        event_data:
          name: bedroom
          color: red
      action:
        service: light.turn_on
        data:
          rgb_color: [255, 0, 0]
          entity_id: light.bedroom
          
This will handle the specific case of setting the bedroom light to red, but not any other color. You can either add additional automations to handle these, or make use of [automation templating](https://www.home-assistant.io/docs/automation/templating/) to do it all at once.
 
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
3. Specifying how you pronounce specific words, including words that Rhasspy doesn't know yet
4. Splitting speech recording, transcription, and intent recognition across multiple machines

Profiles
----------

All of the files Rhasspy needs for wake word detection, speech transcription, and intent recognition are contained in a *profile* directory. Out of the box, Rhasspy contains profiles for English (en), Spanish (es), French (fr), German (de), Italian (it), Dutch (nl), and Russian (ru).

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
  * Finite state transducer used by phonetisaurus to guess unknown word pronunciations
* `language_model.txt`
  * ARPA trigram model created from user sentences
* `phoneme_examples.txt`
  * Text file with example words/pronunciations for each phoneme
* `phonemes.txt`
  * Text file mapping from CMU to eSpeak phonemes 
* `profile.json`
  * Overrides profile settings from `defaults.json`
  * See [profile documentation](doc/profiles.md) for details
* `sentences.ini`
  * Intents and sentences used to generate language model and train intent recognizer
* `rasa_config.yml`
  * YAML configuration for RasaNLU
  
Running
---------

Rhasspy is designed to run on Raspberry Pi's (`armhf`) and desktops/laptops (`amd64`), as a [Hass.IO add-on](https://www.home-assistant.io/addons/), within [Docker](https://www.docker.com/) and inside a [Python virtual environment](https://docs.python-guide.org/dev/virtualenvs/).

### Docker

Make sure you have Docker installed:

    curl -sSL https://get.docker.com | sh
    
and that your user is part of the `docker` group:

    sudo usermod -a -G docker $USER
    
Be sure to reboot after adding yourself to the `docker` group!

Next, start the Rhasspy Docker image in the background:

    docker run -d -p 12101:12101 \
          --restart unless-stopped \
          -e RHASSPY_PROFILES=/profiles \
          -v "$HOME/.rhasspy:/profiles" \
          --device /dev/snd:/dev/snd \
          synesthesiam/rhasspy-hassio-addon:latest
          
The web interface should now be accessible at http://localhost:12101

If you're using [docker compose](https://docs.docker.com/compose/), try this:

    rhasspy:
        image: "synesthesiam/rhasspy-hassio-addon:latest"
        restart: unless-stopped
        environment:
            RHASSPY_PROFILES: "/profiles"
        volumes:
            - "./rhasspy_config:/profiles"
        ports:
            - "12101:12101"
        devices:
            - "/dev/snd:/dev/snd"

### Hass.IO

Add my [Hass.IO Add-On Repository](https://github.com/synesthesiam/hassio-addons) in the Add-On Store, refresh, then install the "Rhasspy Assistant" under “Synesthesiam Hass.IO Add-Ons” (all the way at the bottom of the Add-On Store screen).

**NOTE:** Beware that on a Raspberry Pi 3, the add-on can take 10-15 minutes to build and around 1-2 minutes to start.

Watch the system log for a message like “Build 8e35c251/armhf-addon-rhasspy:1.1 done”. If the “Open Web UI” link on the add-on page doesn’t work, please check the log for errors, wait a minute, and try again.

### Virtual Environment

This repository is designed to host a Python Virtual environment for running Rhasspy outside of Docker. This may be desirable if you have trouble getting Rhasspy to access your microphone from within a Docker container. To start, clone the repo somewhere:

    git clone https://github.com/synesthesiam/rhasspy-hassio-addon.git
    
Then run the `create-venv.sh` script (assumes a Debian distribution):

    cd rhasspy-hassio-addon/
    ./create-venv.sh
    
Once the installation finishes (5-10 minutes on a Raspberry Pi 3), you can use the `run-venv.sh` script to start Rhasspy:

    ./run-venv.sh
    
If all is well, the web interface will be available at http://localhost:12101

Supporting Tools
--------------------

The following tools/libraries help to support Rhasspy:

* [Flask](http://flask.pocoo.org) (web server)
* [Pocketsphinx](https://github.com/cmusphinx/pocketsphinx) (speech to text)
* [Opengrm](http://www.opengrm.org/twiki/bin/view/GRM/NGramLibrary) (language modeling)
* [Phonetisaurus](https://github.com/AdolfVonKleist/Phonetisaurus) (word pronunciations)
* [fuzzywuzzy](https://github.com/seatgeek/fuzzywuzzy) (fuzzy string matching)
* [RasaNLU](https://rasa.com/) (intent recognition)
* [Python 3](https://www.python.org)
* [Sox](http://sox.sourceforge.net) (WAV conversion)
* [Vue.js](https://vuejs.org/) (web UI)
* [webrtcvad](https://github.com/wiseman/py-webrtcvad) (voice activity detection)
