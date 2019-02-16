# Intent Handling

After a voice command has been transcribed and your intent has been successfully recognized, Rhasspy is ready to send an event to Home Assistant with all of the information it needs.

## Home Assistant

Add to your [profile](profiles.md):

```json
"handle": {
  "system": "hass"
},

"home_assistant": {
  "access_token": "",
  "api_password": "",
  "event_type_format": "rhasspy_{0}",
  "url": "http://hassio/homeassistant/"
}
```

If you're running Rhasspy as an add-on inside [Hass.io](https://www.home-assistant.io/hassio/), the access token is [automatically provided](https://developers.home-assistant.io/docs/en/hassio_addon_communication.html#hassio-api). Otherwise, you'll need to create a [long-lived access token](https://www.home-assistant.io/docs/authentication/) and set `home_assistant.access_token` manually.

See `rhasspy.intent_handler.HomeAssistantIntentHandler` for details.

## Command

Once an intent is successfully recognized, Rhasspy will send an event to Home Assistant with the details (as well as [publish it over MQTT](https://docs.snips.ai/reference/dialogue#intent)). You can call a custom program instead *or in addition* to this behavior.
    
Add to your [profile](profiles.md):

```json
"handle": {
  "system": "command",
  "command": {
      "program": "/path/to/program",
      "arguments": []
  },
  "forward_to_hass": true
}
```

When an intent is recognized, Rhasspy will call your custom program with the intent JSON printed to standard in. You should return JSON to standard out, optionally with additional information. If `handle.forward_to_hass` is `true`, Rhasspy will look for a `hass_event` property of the returned JSON with the following structure:

```json
{
  // rest of input JSON
  // ...
  "hass_event": {
    "event_type": "...",
    "event_data": {
      "key": "value",
      // ...
    }
  }
}
```
    
Rhasspy will create the Home Assistant event based on this information. If it is **not** present, the remaining intent information will be used to construct the event as normal (i.e., `intent` and `entities`). If `handle.forward_to_hass` is `false`, the output of your program is not used.

The following environment variables are available to your program:

* `$RHASSPY_BASE_DIR` - path to the directory where Rhasspy is running from
* `$RHASSPY_PROFILE` - name of the current profile (e.g., "en")
* `$RHASSPY_PROFILE_DIR` - directory of the current profile (where `profile.json` is)

See [handle.sh](https://github.com/synesthesiam/rhasspy-hassio-addon/blob/master/bin/mock-commands/handle.sh) for an example program.

See `rhasspy.intent_handler.CommandIntentHandler` for details.

## Dummy

Disables intent handling.

Add to your [profile](profiles.md):

```json
"handle": {
  "system": "dummy"
}
```

See `rhasspy.intent_handler.DummyIntentHandler` for details.
