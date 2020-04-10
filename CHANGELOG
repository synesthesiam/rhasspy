## [2.4.20] - 2020 Apr 10

### Added

- libasound2-plugins to Docker image (for Hass.IO)
- MQTT TLS support (thanks https://github.com/ofekd)
- Mycroft Precise 0.3.0 added to Docker image

### Changed

- Properly accept websocket connections
- Don't error out on missing porcupine files
- Fix rawValue in MQTT messages

## [2.4.19] - 2020 Mar 04

### Added

- Support for Google Cloud speech to text
- Rasa NLU minimum confidence parameter

### Changed

- Using tagged version of porcupine wake models to avoid incompatibilities
- Fix Rasa NLU first entity only bug
- Fix siteId null bug

## [2.4.18] - 2020 Feb 07

### Added

- /api/listen-for-wake accepts "on" and "off" as POST data to enable/disable wake word
- /api/events/wake websocket endpoint reports wake up events
- /api/events/text websocket endpoint reports transcription events
- Rhasspy logo changes in web UI when wake word is detected
- espeak arguments list for text to speech

### Changed

- STT output casing is fixed outside of HTTP API calls
- All voice commands show up in web UI test page
- Play last voice command button in web UI works for any command
- Fixed commas in numbers with thousand separators
- Words from Pocketsphinx wake keyphrase are added to dictionary
- Pocketsphinx wake word keyphrase casing is fixed

## [2.4.17] - 2020 Jan 21

### Added

- Button to web UI to play last recorded voice command
- RHASSPY_LOG_LEVEL environment variable
- Web UI feedback during download
- Add "asoundrc" config option to Hass.IO add-on

### Changed

- Moved $profile/kaldi/custom_words.txt to $profile/kaldi_custom_words.txt
- Slot substitution casing is kept during training/recognition
- Fixed fuzzywuzzy and other intent recognizer training after addition of converters
- Fix thread max count issue
- Hide web UI alerts after 10 seconds
- Delete partially downloaded profile files
- Force slot programs to run each training cycle
- Fix _raw_text in Hass event being same as _text

### Removed

- Flair intent recognizer

## [2.4.16] - 2020 Jan 5

### Added

- Number ranges (0..100)
- Converters for transforming JSON values in intents (!int)
- Slot programs for generating slot values
- $rhasspy/days and $rhasspy/months built-in slots

## [2.4.15] - 2019 Dec 27

### Added

- Preliminary support for Raspberry Pi Zero (no Kaldi)
- Play error sound when intent not recognized
- _text and _raw_text to Home Assistant events

### Changed

- Disable wake word when TTS is speaking
- Use json5 library to parse profile
- Remove picotts pop sound
- Don't open/close microphone after wake-up

## [2.4.14] - 2019 Dec 19

### Added

- Ability to split sentences across multiple .ini file in intents directory
- Support (future) /api/intent for Home Assistant
- Support for Home Assistant TTS system
- Emulate MaryTTS /process API in web API
- Include wakeId/siteId in JSON intent (MQTT/Websocket)
- ?voice and ?language query parameters to /api/text-to-speech
