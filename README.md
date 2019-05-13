![Rhasspy logo](docs/img/rhasspy.svg)

Rhasspy (pronounced RAH-SPEE) is an offline, [multilingual](#supported-languages) voice assistant toolkit inspired by [Jasper](https://jasperproject.github.io/) that works well with [Home Assistant](https://www.home-assistant.io/), [Hass.io](https://www.home-assistant.io/hassio/), and [Node-RED](https://nodered.org).

* [Documentation](https://rhasspy.readthedocs.io/)
* [Video Introduction](https://www.youtube.com/watch?v=ijKTR_GqWwA)
* [Hass.IO Add-On Repository](https://github.com/synesthesiam/hassio-addons)
* [Discussion](https://community.home-assistant.io/t/rhasspy-offline-voice-assistant-toolkit/60862)

Rhasspy transforms voice commands into [JSON](https://json.org) events that can trigger actions in home automation software, like [Home Assistant automations](https://www.home-assistant.io/docs/automation/trigger/#event-trigger) or [Node-RED flows](https://rhasspy.readthedocs.io/en/latest/usage/#node-red). You define custom voice commands in a [profile](profiles.md) using a [specialized template syntax](https://rhasspy.readthedocs.io/en/latest/training/#sentencesini), and Rhasspy takes care of the rest.

To run Rhasspy with the English (en) profile using Docker:

    docker run -d -p 12101:12101 \
          --restart unless-stopped \
          -v "$HOME/.config/rhasspy/profiles:/profiles" \
          -e RHASSPY_TTS_DIR=/tts \
          -v "$HOME/.config/rhasspy/tts:/tts" \
          --device /dev/snd:/dev/snd \
          synesthesiam/rhasspy-server:latest \
          --profile en \
          --user-profiles /profiles
          
Then visit the web interface at [http://localhost:12101](http://localhost:12101)
See the [web interface documentation](https://rhasspy.readthedocs.io/en/latest/usage/#web-interface) for a brief tour of what you can do.

## Supported Languages

Rhasspy currently supports the following languages:

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

For more information, please see the [documentation](https://rhasspy.readthedocs.io/).
 
## Intended Audience

Rhasspy is intended for advanced users that want to have a voice interface to Home Assistant, but value **privacy** and **freedom** above all else. There are many other voice assistants, but none (to my knowledge) that:

1. Can function **completely disconnected from the Internet**
2. Are entirely free/open source
3. Work well with Home Assistant, Hass.io, and Node-RED

If you feel comfortable sending your voice commands through the Internet for someone else to process, or are not comfortable with rolling your own Home Assistant automations to handle intents, I recommend taking a look at [Mycroft](https://mycroft.ai).
