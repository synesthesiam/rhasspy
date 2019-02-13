# Wake Word

The typical workflow for interacting with a voice assistant is to first activate it with a "wake" or "hot" word, then provide your voice command. Rhasspy supports listening for a wake word with one of several systems, using [pocketsphinx](#pocketsphinx).

## Pocketsphinx

Listens for a [keyphrase](https://cmusphinx.github.io/wiki/tutoriallm/#using-keyword-lists-with-pocketsphinx) using [pocketsphinx](https://github.com/cmusphinx/pocketsphinx).

    "wake": {
        "system": "pocketsphinx",
        "pocketsphinx": {
            "keyphrase": "okay rhasspy",
            "threshold": 1e-30,
            "chunk_size": 960
        }
    },
    
    "rhasspy": {
        "listen_on_start": true
    }
    
Set `wake.pocketsphinx.keyphrase` to whatever you like, though 3-4 syllables is recommended. Make sure to [train](training.md) and restart Rhasspy whenever you change the keyphrase.

The `wake.pocketsphinx.threshold` should be in the range 1e-50 to 1e-5. The smaller the number, the less like the keyphrase is to be observed. At least one person has written a script to [automatically tune the threshold](https://medium.com/@PankajB96/automatic-tuning-of-keyword-spotting-thresholds-a27256869d31).

See `rhasspy.wake.PocketsphinxWakeListener` for details.

## Mycroft Precise

Listens for a wake word with [Mycroft Precise](https://github.com/MycroftAI/mycroft-precise).

    "wake": {
        "system": "precise",
        "precise": {
            "model": "model-name-in-profile.pb",
            "sensitivity": 0.5,
            "trigger_level": 3,
            "chunk_size": 2048
        }
    },
    
    "rhasspy": {
        "listen_on_start": true
    }
    
See `rhasspy.wake.PreciseWakeListener` for details.

## Snowboy

Listens for a wake word with [snowboy](https://snowboy.kitt.ai).

    "wake": {
        "system": "snowboy",
        "hermes": {
            "wakeword_id": "default"
        },
        "snowboy": {
            "model": "model-name-in-profile.(u|p)mdl",
            "audio_gain": 1,
            "sensitivity": 0.5,
            "chunk_size": 960
        }
    },

    "rhasspy": {
        "listen_on_start": true
    }

See `rhasspy.wake.SnowboyWakeListener` for details.

## MQTT/Hermes

Subscribes to the `hermes/hotword/<WAKEWORD_ID>/detected` topic, and wakes Rhasspy up when a message is received ([Hermes protocol](https://docs.snips.ai/ressources/hermes-protocol)).

    "wake": {
        "system": "hermes",
        "hermes": {
            "wakeword_id": "default"
        }
    },
    
    
    "rhasspy": {
        "listen_on_start": true
    },
    
    "mqtt": {
      "enabled": true,
        "host": "localhost",
        "username": "",
        "port": 1883,
        "password": "",
        "site_id": "default"
    }
    
Adjust the `mqtt` configuration to connect to your MQTT broker.
Set `mqtt.site_id` to match your Snips.AI siteId and `wake.hermes.wakeword_id` to match your Snips.AI wakewordId.

See `rhasspy.wake.HermesWakeListener` for details.

## Command

Calls a custom external program to listen for a wake word, only waking up Rhasspy when it exits.

    "wake": {
        "system": "command",
        "command": {
            "program": "/path/to/program",
            "arguments": []
        }
    },
    
    "rhasspy": {
        "listen_on_start": true
    }
    
When Rhasspy starts, your program will be called with the given arguments. Once your program detects the wake word, it should print it to standard out and exit. Rhasspy will call your program again when it goes back to sleep. If the empty string is printed, Rhasspy will **not** wake up and your program will be called again.

See [sleep.sh](https://github.com/synesthesiam/rhasspy-hassio-addon/blob/master/bin/mock-commands/sleep.sh) for an example program.

See `rhasspy.wake.CommandWakeListener` for details.
