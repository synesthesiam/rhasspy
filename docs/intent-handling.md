# Intent Handling

After a voice command has been transcribed and your intent has been successfully recognized, Rhasspy is ready to send a JSON event to Home Assistant or Node-RED.

Regardless of which intent handling system you choose, Rhasspy emits JSON events [over a websocket connection](usage.md#websocket-events).

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

### Events

Rhasspy will send Home Assistant an event every time an intent is recognized through its [REST API](https://developers.home-assistant.io/docs/en/external_api_rest.html#post-api-events-lt-event-type). The type of the event is determined by the name of the intent, and the event data comes from the tagged words in your [sentences](training.md#sentencesini).

For example, if you have an intent like:

```
[ChangeLightColor]
set the (bedroom light){name} to (red | green | blue){color}
```

and you say something like *"set the bedroom light to blue"*, Rhasspy will POST to the `/api/events/rhasspy_ChangeLightColor` endpoint of your Home Assistant server with the following data:

```json
{
  "name": "bedroom light",
  "color": "blue"
}
```

In order to do something with the `rhasspy_ChangeLightColor` event, create an automation with an [event trigger](https://www.home-assistant.io/docs/automation/trigger/#event-trigger). For example, add the following to your `automation.yaml` file:

```yaml
- alias: "Set bedroom light color (blue)"
  trigger:
    platform: event
    event_type: rhasspy_ChangeLightColor
    event_data:
      name: 'bedroom light'
      color: 'blue'
  action:
    ...
```

See the documentation on [actions](https://www.home-assistant.io/docs/automation/action/) for the different things you can do with Home Assistant.

### MQTT

In addition to events, Rhasspy can also publish intents through MQTT ([Hermes protocol](https://docs.snips.ai/reference/dialogue#intent)).
This allows Rhasspy to send intents to [Snips.AI](https://snips.ai/).

Add to your [profile](profiles.md):

```json
"mqtt": {
    "enabled": true,
    "host": "localhost",
    "username": "",
    "password": "",
    "port": 1883,
    "reconnect_sec": 5,
    "site_id": "default",
    "publish_intents": true
}
```

Adjust the `mqtt` configuration to connect to your MQTT broker.
Set `mqtt.site_id` to match your Snips.AI siteId.

Add to your Home Assistant's `configuration.yaml` file:

```yaml
snips:

intent_script:
  ...
```

See the [intent script](https://www.home-assistant.io/components/intent_script/) documentation for details on how to handle the intents.

### Self-Signed Certificate

If your Home Assistant uses a self-signed certificate, you'll need to give Rhasspy some extra information.

Add to your [profile](profiles.md):

```json
"home_assistant": {
  ...
  "pem_file": "/path/to/certfile"
}
```

Set `home_assistant.pem_file` to the full path to your <a href="http://docs.python-requests.org/en/latest/user/advanced/#ssl-cert-verification">CA_BUNDLE file or a directory with certificates of trusted CAs</a>.

Use the environment variable `RHASSPY_PROFILE_DIR` to reference your current profile's directory. For example, `$RHASSPY_PROFILE_DIR/my.pem` will tell Rhasspy to use a file named `my.pem` in your profile directory when verifying your self-signed certificate.

## Command

Once an intent is successfully recognized, Rhasspy will send an event to Home Assistant with the details. You can call a custom program instead *or in addition* to this behavior.
    
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

See [handle.sh](https://github.com/synesthesiam/rhasspy/blob/master/bin/mock-commands/handle.sh) for an example program.

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
