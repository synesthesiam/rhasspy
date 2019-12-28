const profileDefaults = {
    "command": {
        "system": "webrtcvad",
        "webrtcvad": {
            "chunk_size": 960,
            "min_sec": 2,
            "sample_rate": 16000,
            "silence_sec": 0.5,
            "speech_buffers": 5,
            "throwaway_buffers": 10,
            "timeout_sec": 30,
            "vad_mode": 0
        },
        "command": {
            "program": "$RHASSPY_BASE_DIR/bin/mock-commands/listen.sh",
            "arguments": []
        },
        "oneshot": {
            "timeout_sec": 30
        },
        "hermes": {
            "timeout_sec": 30
        }
    },
    "home_assistant": {
        "access_token": "",
        "api_password": "",
        "event_type_format": "rhasspy_{0}",
        "url": "http://hassio/homeassistant/",
        "pem_file": "",
        "handle_type": "event"
    },
    "handle": {
        "system": "hass",
        "command": {
            "program": "$RHASSPY_BASE_DIR/bin/mock-commands/handle.sh",
            "arguments": []
        },
        "remote": {
            "url": "http://my-server:port/endpoint"
        },
        "forward_to_hass": true
    },
    "intent": {
        "conversation": {
            "handle_speech": true
        },
        "error_sound": true,
        "fsticuffs": {
            "intent_fst": "intent.fst",
            "ignore_unknown_words": true,
            "fuzzy": true
        },
        "adapt": {
            "stop_words": "stop_words.txt"
        },
        "fuzzywuzzy": {
            "examples_json": "intent_examples.json",
            "min_confidence": 0.0
        },
        "rasa": {
            "examples_markdown": "intent_examples.md",
            "project_name": "rhasspy",
            "url": "http://localhost:5005/"
        },
        "remote": {
            "url": "http://my-server:12101/api/text-to-intent"
        },
        "flair": {
            "data_dir": "flair_data",
            "max_epochs": 25,
            "do_sampling": true,
            "num_samples": 10000
        },
        "command": {
            "program": "$RHASSPY_BASE_DIR/bin/mock-commands/text2intent.sh",
            "arguments": []
        },
        "system": "fuzzywuzzy"
    },
    "language": "en",
    "microphone": {
        "system": "pyaudio",
        "pyaudio": {
            "device": "",
            "frames_per_buffer": 480
        },
        "arecord": {
            "device": "",
            "chunk_size": 960
        },
        "stdin": {
            "auto_start": true,
            "chunk_size": 960
        },
        "http": {
            "host": "127.0.0.1",
            "port": 12333
        },
        "gstreamer": {
            "pipeline": "udpsrc port=12333 ! rawaudioparse use-sink-caps=false format=pcm pcm-format=s16le sample-rate=16000 num-channels=1 ! queue ! audioconvert ! audioresample"
        },
    },
    "mqtt": {
        "enabled": false,
        "host": "localhost",
        "password": "",
        "port": 1883,
        "reconnect_sec": 5,
        "site_id": "default",
        "username": "",
        "publish_intents": true
    },
    "rhasspy": {
        "default_profile": "en",
        "listen_on_start": true,
        "load_timeout_sec": 15,
        "preload_profile": true
    },
    "sounds": {
        "recorded": "${RHASSPY_BASE_DIR}/etc/wav/beep_lo.wav",
        "system": "aplay",
        "wake": "${RHASSPY_BASE_DIR}/etc/wav/beep_hi.wav",
        "error": "${RHASSPY_BASE_DIR}/etc/wav/beep_error.wav"
    },
    "speech_to_text": {
        "g2p_model": "g2p.fst",
        "g2p_casing": "",
        "grammars_dir": "grammars",
        "slots_dir": "slots",
        "pocketsphinx": {
            "acoustic_model": "acoustic_model",
            "base_dictionary": "base_dictionary.txt",
            "custom_words": "custom_words.txt",
            "dictionary": "dictionary.txt",
            "language_model": "language_model.txt",
            "mllr_matrix": "acoustic_model_mllr",
            "unknown_words": "unknown_words.txt",
            "min_confidence": 0.0,
            "compatible": true,
            "phoneme_examples": "phoneme_examples.txt",
            "phoneme_map": "espeak_phonemes.txt",
            "open_transcription": false
        },
        "kaldi": {
            "base_dictionary": "base_dictionary.txt",
            "custom_words": "custom_words.txt",
            "dictionary": "dictionary.txt",
            "graph": "graph",
            "kaldi_dir": "/opt/kaldi",
            "language_model": "language_model.txt",
            "model_dir": "model",
            "unknown_words": "unknown_words.txt",
            "compatible": false,
            "phoneme_examples": "phoneme_examples.txt",
            "phoneme_map": "espeak_phonemes.txt",
            "open_transcription": false
        },
        "remote": {
            "url": "http://my-server:12101/api/speech-to-text"
        },
        "command": {
            "program": "$RHASSPY_BASE_DIR/bin/mock-commands/speech2text.sh",
            "arguments": []
        },
        "hass_stt": {
            "platform": "",
            "sample_rate": 16000,
            "bit_size": 16,
            "channels": 1,
            "language": "en-US"
        },
        "sentences_ini": "sentences.ini",
        "sentences_text": "sentences.txt",
        "dictionary_casing": "",
        "system": "pocketsphinx"
    },
    "text_to_speech": {
        "espeak": {
        },
        "system": "espeak",
        "command": {
            "program": "",
            "arguments": []
        },
        "disable_wake": true,
        "marytts": {
            "url": "http://localhost:59125"
        },
        "wavenet": {
            "url": "https://texttospeech.googleapis.com/v1/text:synthesize",
            "cache_dir": "tts/googlewavenet/cache",
            "credentials_json": "tts/googlewavenet/credentials.json",
            "voice": "Wavenet-C",
            "gender": "FEMALE",
            "samplerate": 22050,
            "language_code": "en-US",
            "fallback_tts": "espeak"
        },
        "flite": {
            "voice": "kal16"
        },
        "picotts": {
        }
    },
    "training": {
        "grammars": {
            "delete_before_training": true
        },
        "regex": {
            "split": "\\s+"
        },
        "sentences_by_intent": "sentences_by_intent.json.gz",
        "fsts_dir": "fsts",
        "tokenizer": "regex",
        "unknown_words": {
            "guess_pronunciations": true,
            "fail_when_present": true
        },
        "speech_to_text": {
            "system": "auto",
            "command": {
                "program": "$RHASSPY_BASE_DIR/bin/mock-commands/train-stt.sh",
                "arguments": []
            }
        },
        "intent": {
            "system": "auto",
            "command": {
                "program": "$RHASSPY_BASE_DIR/bin/mock-commands/train-intent.sh",
                "arguments": []
            }
        }
    },
    "tuning": {
        "sphinxtrain": {
            "mllr_matrix": "acoustic_model_mllr"
        },
        "system": "sphinxtrain"
    },
    "wake": {
        "hermes": {
            "wakeword_id": "default"
        },
        "pocketsphinx": {
            "keyphrase": "okay rhasspy",
            "mllr_matrix": "wake_mllr",
            "threshold": 1e-30,
            "chunk_size": 960,
            "compatible": true
        },
        "precise": {
            "model": "okay-rhasspy.pb",
            "sensitivity": 0.5,
            "trigger_level": 3,
            "chunk_size": 2048,
            "engine_path": "precise-engine",
            "chunk_delay": 0.005
        },
        "snowboy": {
            "audio_gain": 1,
            "model": "snowboy.umdl",
            "sensitivity": 0.5,
            "chunk_size": 960,
            "apply_frontend": false
        },
        "porcupine": {
            "library_path": "porcupine/libpv_porcupine.so",
            "model_path": "porcupine/porcupine_params.pv",
            "keyword_path": "porcupine/porcupine.ppn",
            "sensitivity": 0.5
        },
        "command": {
            "program": "$RHASSPY_BASE_DIR/bin/mock-commands/sleep.sh",
            "arguments": []
        },
        "system": "pocketsphinx"
    }
}

export default {
    profileDefaults
}
