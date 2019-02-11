# Rhasspy 

Rhasspy is an offline, multilingual voice assistant toolkit inspired by [Jasper](https://jasperproject.github.io/) that works with [Home Assistant](https://www.home-assistant.io/) and [Hass.io](https://www.home-assistant.io/hassio/).

## Purpose

A typical voice assistant (Alexa, Google Home, etc.) solves a number of important problems:

1. Deciding when to record audio (wake word)
2. Listening for commands/questions (wait for silence)
3. Transcribing command/question (speech to text)
4. Interpreting the speaker's *intent* from the text (intent recognition)
5. Fulfilling the speaker's intent (e.g., playing a song, answering a question)

Rhasspy provides **offline, private solutions** to problems 1-4 using off-the-shelf tools. These tools are:

* **Wake word**
    * [Pocketsphinx Keyphrase](https://cmusphinx.github.io/wiki/tutoriallm/#using-keyword-lists-with-pocketsphinx)
    * [snowboy](https://snowboy.kitt.ai)
    * [Mycroft Precise](https://github.com/MycroftAI/mycroft-precise)
* **Command listener**
    * [webrtcvad](https://github.com/wiseman/py-webrtcvad)
* **Speech to text**
    * [Pocketsphinx](https://github.com/cmusphinx/pocketsphinx)
    * Remote HTTP server (WAV -> text)
* **Intent recognition**
    * [fuzzywuzzy](https://github.com/seatgeek/fuzzywuzzy)
    * [RasaNLU](https://rasa.com/)
    * [Mycroft Adapt](https://github.com/MycroftAI/adapt)
    * Remote HTTP server (text -> JSON)

For problem 5 (fulfilling the speaker's intent), Rhasspy works with Home Assistant's built-in [automation capability](https://www.home-assistant.io/docs/automation/). For each intent you define, Rhasspy sends an event to Home Assistant that can be used to do anything Home Assistant can do (toggle switches, call REST services, etc.). This means that Rhasspy will do very little out of the box compared to other voice assistants, but there will also be *no limits* to what can be done.

## How it Works

Rhasspy transforms speech commands into [Home Assistant events](https://www.home-assistant.io/docs/configuration/events/) that [trigger automations](https://www.home-assistant.io/docs/automation/trigger/#event-trigger). You define these commands in a Rhasspy [profile](profiles/) using a [specialized template syntax](training/) that lets you control how Rhasspy creates the events it sends to Home Assistant.

Importantly, Rhasspy **only recognizes commands that you provide**. This is a double-edged sword: Rhasspy cannot recognize words or commands outside of your training set, but you have precise control over that training set. Additionally, the [training sentence format](training/) allows you compactly express a large set of commands using relatively little text.

### RGB Light Example

Let's say you have an RGB light of some kind in your bedroom that's hooked up already to Home Assistant. You'd like to be able to say things like "*set the bedroom light to red*" to change its color. To start, let's write a [Home Assistant automation](https://www.home-assistant.io/docs/automation/action/) to help you out:

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

Audio Input
-------------

Rhasspy can listen to audio input from one of several sources:

* [PyAudio](https://people.csail.mit.edu/hubert/pyaudio/) (local)
* ALSA (via direct use of `arecord`)
* MQTT ([Hermes protocol](https://docs.snips.ai/ressources/hermes-protocol))

Profiles
----------

All of the files Rhasspy needs for wake word detection, speech transcription, and intent recognition are contained in a *profile* directory. Out of the box, Rhasspy contains profiles for English (en), Spanish (es), French (fr), German (de), Italian (it), Dutch (nl), and Russian (ru).

Each profile contains a `profile.json` file with settings specific to the profile, such as configuration details for speech/intent recognition and your Home Assistant server. The settings in `profile.json` override settings in the `defaults.json` file in the main profiles directory. See [profile documentation](doc/profiles.md) for more details.

Supporting Tools
--------------------

The following tools/libraries help to support Rhasspy:

* [Flask](http://flask.pocoo.org) (web server)
* [fuzzywuzzy](https://github.com/seatgeek/fuzzywuzzy) (fuzzy string matching)
* [Mycroft Adapt](https://github.com/MycroftAI/adapt) (intent recognition)
* [Mycroft Precise](https://github.com/MycroftAI/mycroft-precise) (wake word)
* [Phonetisaurus](https://github.com/AdolfVonKleist/Phonetisaurus) (word pronunciations)
* [Pocketsphinx](https://github.com/cmusphinx/pocketsphinx) (speech to text, wake word)
* [PyAudio](https://people.csail.mit.edu/hubert/pyaudio/) (microphone)
* [Python 3](https://www.python.org)
* [Opengrm](http://www.opengrm.org/twiki/bin/view/GRM/NGramLibrary) (language modeling)
* [RasaNLU](https://rasa.com/) (intent recognition)
* [sphinxtrain](https://github.com/cmusphinx/sphinxtrain) (acoustic model tuning)
* [snowboy](https://snowboy.kitt.ai) (wake word)
* [Sox](http://sox.sourceforge.net) (WAV conversion)
* [Vue.js](https://vuejs.org/) (web UI)
* [webrtcvad](https://github.com/wiseman/py-webrtcvad) (voice activity detection)
