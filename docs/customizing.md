# Custom Commands

Most of Rhasspy's internal components can be replaced by calls to external
programs. This is usually done by setting the component's `system` to `command`,
and then supplying a `program` (path to executable) and optionally some
`arguments`.

The inputs and outputs of each program depend on the component, but in general
input will come in via standard in and output is expected on standard out.
Additionally, the following environment variables are available:

* `$RHASSPY_BASE_DIR` - path to the directory where Rhasspy is running from
* `$RHASSPY_PROFILE` - name of the current profile (e.g., "en")
* `$RHASSPY_PROFILE_DIR` - directory of the current profile (where `profile.json` is)

## Available Components

The components that can be customized via the `command` system are listed below.
You can find mocked up external programs for every component in the [mock
commands](https://github.com/synesthesiam/rhasspy-hassio-addon/tree/master/bin/mock-commands)
directory.

### Intent Recognition


Add to your `profile.json`:

    {
      "intent": {
        "system": "command",
        "command": {
          "program": "/path/to/program",
          "arguments": ["argument1", "argument2"]
        }
      }
    }

### Intent Handling

Once an intent is successfully recognized, Rhasspy will send an event to Home
Assistant with the details (as well as [publish it over
MQTT](https://docs.snips.ai/reference/dialogue#intent)). You can call a custom
program instead *or in addition* to this behavior.

Add to your `profile.json`:

    {
      "handle": {
        "system": "command",
        "command": {
          "program": "/path/to/program",
          "arguments": ["argument1", "argument2"]
        },
        "forward_to_hass": true
      }
    }
    
When an intent is recognized, Rhasspy will call your custom program with the
intent JSON printed to standard in. You should return JSON to standard out,
optionally with additional information. If `handle.forward_to_hass` is `true`,
Rhasspy will look for a `hass_event` property of the returned JSON with the
following structure:

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
    
Rhasspy will create the Home Assistant event based on this information. If it is
**not** present, the remaining intent information will be used to construct the
event as normal (i.e., `intent` and `entities`). If `handle.forward_to_hass` is
`false`, the output of your program is not used.

See
[handle.sh](https://github.com/synesthesiam/rhasspy-hassio-addon/blob/master/bin/mock-commands/handle.sh)
for an example.
