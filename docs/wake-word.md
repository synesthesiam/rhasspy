# Wake Word

## Pocketsphinx

    "wake": {
        "system": "pocketsphinx",
        "pocketsphinx": {
            "keyphrase": "okay rhasspy",
            "threshold": 1e-30,
            "chunk_size": 960,
            "mllr_matrix": "wake_mlr"
        }
    },
    
    "rhasspy": {
        "listen_on_start": true
    }

See `rhasspy.wake.PocketsphinxWakeListener` for details.

## Snowboy

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

## Mycroft Precise

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

## MQTT/Hermes

    "wake": {
        "system": "hermes",
        "hermes": {
            "wakeword_id": "default"
        }
    },
    
    
    "rhasspy": {
        "listen_on_start": true
    }

See `rhasspy.wake.HermesWakeListener` for details.

## Command

    "wake": {
        "system": "pocketsphinx",
        "command": {
            "program": "/path/to/program",
            "arguments": []
        }
    },
    
    "rhasspy": {
        "listen_on_start": true
    }
    
See `rhasspy.wake.CommandWakeListener` for details.
