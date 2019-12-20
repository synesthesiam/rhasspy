<img src="img/rhasspy.svg" style="max-height: 200px;" title="Rhasspy logo">

Rhasspy (pronounced RAH-SPEE) is an [open source](https://github.com/synesthesiam/rhasspy), fully offline voice assistant toolkit for [many languages](#supported-languages) that works well with [Home Assistant](https://www.home-assistant.io/), [Hass.io](https://www.home-assistant.io/hassio/), and [Node-RED](https://nodered.org).

You specify voice commands in a [template language](training.md):

```
[LightState]
states = (on | off)
turn (<states>){state} [the] light
```

and Rhasspy will produce [JSON](https://json.org) events that can trigger actions in [home automation software](https://www.home-assistant.io/docs/automation/trigger/#event-trigger) or [Node-RED flows](usage.md#node-red):

```json
{
    "text": "turn on the light",
    "intent": {
        "name": "LightState"
    },
    "slots": {
        "state": "on"
    }
}
```

Rhasspy is <strong>optimized for</strong>:

* Working with external services via [MQTT](usage.md#mqtt), [HTTP](usage.md#http-api), and [Websockets](usage.md#websocket-events)
  * Home Assistant and Hass.IO have [built-in support](usage.md#home-assistant)
* Pre-specified voice commands that are described well [by a grammar](training.md#sentencesini)
  * You can also do [open-ended speech recognition](speech-to-text.md#open-transcription)
* Voice commands with [uncommon words or pronunciations](usage.md#words-tab)
  * New words are added phonetically with [automated assistance](https://github.com/AdolfVonKleist/Phonetisaurus)

## Getting Started

Ready to try Rhasspy? Follow the steps below and check out the [tutorials](tutorials.md).

1. Make sure you have the [necessary hardware](hardware.md)
2. Choose an [installation method](install.md)
3. Access the [web interface](usage.md#web-interface) to download a profile
4. Author your [custom voice commands](training.md) and train Rhasspy
5. Connect Rhasspy to [Home Assistant](usage.md#home-assistant) or a [Node-RED](usage.md#noe-red) flow

## Supported Languages

Rhasspy supports the following languages:

* English (`en`)
* German (`de`)
* Spanish (`es`)
* French (`fr`)
* Italian (`it`)
* Dutch (`nl`)
* Russian (`ru`)
* Greek (`el`)
* Hindi (`hi`)
* Mandarin (`zh`)
* Vietnamese (`vi`)
* Portuguese (`pt`)
* Swedish (`sv`)
* Catalan (`ca`)

## Intended Audience

Rhasspy is intended for advanced users that want to have a voice interface to Home Assistant, but value **privacy** and **freedom** above all else. There are many other voice assistants, but none (to my knowledge) that:

1. Can function **completely disconnected from the Internet**
2. Are entirely free/open source
3. Work well with Home Assistant, Hass.io, and Node-RED

If you feel comfortable sending your voice commands through the Internet for someone else to process, or are not comfortable with rolling your own Home Assistant automations to handle intents, I recommend taking a look at [Mycroft](https://mycroft.ai).
