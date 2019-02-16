![Rhasspy logo](docs.img/rhasspy.svg)

Rhasspy (pronounced RAH-SPEE) is an offline, [multilingual](#supported-languages) voice assistant toolkit inspired by [Jasper](https://jasperproject.github.io/) that works with [Home Assistant](https://www.home-assistant.io/) and [Hass.io](https://www.home-assistant.io/hassio/).

* [Documentation](https://rhasspy.readthedocs.io/)
* [Video Introduction](https://www.youtube.com/watch?v=ijKTR_GqWwA)
* [Hass.IO Add-On Repository](https://github.com/synesthesiam/hassio-addons)
* [Discussion](https://community.home-assistant.io/t/rhasspy-offline-voice-assistant-toolkit/60862)

Rhasspy transforms voice commands into [Home Assistant events](https://www.home-assistant.io/docs/configuration/events/) that [trigger automations](https://www.home-assistant.io/docs/automation/trigger/#event-trigger). You define these commands in a Rhasspy [profile](https://rhasspy.readthedocs.io/en/latest/profiles/) using a [specialized template syntax](https://rhasspy.readthedocs.io/en/latest/training/#sentencesini) that lets you control how Rhasspy creates the events it sends to Home Assistant.

To run Rhasspy using Docker:

    docker run -d -p 12101:12101 \
          --restart unless-stopped \
          -e RHASSPY_PROFILES=/profiles \
          -v "$HOME/.config/rhasspy/profiles:/profiles" \
          --device /dev/snd:/dev/snd \
          synesthesiam/rhasspy-server:latest
          
Then visit the web interface at http://localhost:12101

For more information, please see the [documentation](https://rhasspy.readthedocs.io/).
 
## Intended Audience

Rhasspy is intended for advanced users that want to have a voice interface to Home Assistant, but value **privacy** and **freedom** above all else. There are many other voice assistants, but none (to my knowledge) that:

1. Can function **completely disconnected from the Internet**
2. Are entirely free/open source
3. Work well with Home Assistant and Hass.io

If you feel comfortable sending your voice commands through the Internet for someone else to process, or are not comfortable with rolling your own Home Assistant automations to handle intents, I recommend taking a look at [Mycroft](https://mycroft.ai).

## Supported Languages

Rhasspy currently supports English (`en`), German (`de`), Spanish (`es`), Italian (`it`), Dutch (`nl`), and Russian (`ru`). Support for these languages comes directly from existing [CMU Sphinx models](https://sourceforge.net/projects/cmusphinx/files/Acoustic%20and%20Language%20Models/).
