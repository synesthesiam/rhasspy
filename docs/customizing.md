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

