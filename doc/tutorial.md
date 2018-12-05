Tutorial
==========

1. Download the latest release of the [Rhasspy Hass.io add-on](https://github.com/synesthesiam/rhasspy-hassio-addon/releases)
2. Extract/copy the files into a `rhasspy` directory in your Hass.io `/addons` directory (see [this tutorial](https://developers.home-assistant.io/docs/en/hassio_addon_tutorial.html) for details on installing local add-ons)
3. Refresh your add-ons in the `Add-On Store` tab and click on  "Rhasspy Assistant" under "Local add-ons"
4. Click `INSTALL` and watch the system log (under the Hass.io `System` tab) to see when it's finished (it may take 10 minutes or more on a Raspberry Pi)
5. Click `Start` and wait until
6. Click `Open Web UI` to open the web interface. If you get a connection error, Rhasspy may still be starting up. Wait a minute and refresh.

Rhasspy Web Interface
--------------------------

Rhasspy's web-based user interface lets you manage custom words and commands as
well as test Rhasspy using your microphone or by uploading a WAV file.

### Speech

The default tab in Rhasspy is `Speech`, which lets you tests various aspects of
Rhasspy's speech/intent recognition:

<img src="img/web-speech.png">

The image above shows important parts of the web interface:

1. The currently selected *profile*
  * `Re-Train` - trains the speech/intent recognizer with your custom sentences/words
  * `Reload` - clears cached speech/intent objects from memory
2. The microphone that will be used to record
  * `Hold to Record` - start recording from microphone when pressed, stop recording when released
3. Upload a pre-recorded WAV for to run through the speech recognizer
  * Preferred format is 16-bit 16Khz mono
4. Type a sentence to test intent recognizer
  * Holds transcription from speech recognizer when record/upload functionality is used
5. Send any recognized intents directly to Home Assistant (`homeassistant.url` in your profile)

### Sentences

This tab contains the custom commands for Rhasspy to recognize. These are categorized by *intent*, and use a [simplified JSGF grammar](sentences.md). Sentences are listed under the `[IntentName]`, and may contain `[optional words]` or `(one |or |more | alternative | items)`. Rules are defined like `rule_name = ...` and referenced in sentences as `<rule_name>`. Adding a `{tag}` to a word, rule, etc. will set a slot with the tag name in the event Rhasspy sends to Home Assistant (`(value) {name}` will be `name: value`).

<img src="img/web-sentences.png">

### Words

You can define [custom words](https://cmusphinx.github.io/wiki/tutorialdict/) here by looking up pronunciations of other words or by having Rhasspy guess pronunciations using [phonetisaurus](https://github.com/AdolfVonKleist/Phonetisaurus).

<img src="img/web-words.png">

### Settings

Rhasspy gets settings for your current profile by overlaying the JSON define in `profile.json` with the `defaults.json` file in your profiles directory. See the [profiles documentation](profiles.md) for more details.

<img src="img/web-settings.png">
