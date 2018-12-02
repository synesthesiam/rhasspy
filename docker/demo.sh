#!/usr/bin/env bash
# Start Home Assistant
cd /usr/src/app
python -m homeassistant --config /config &

# Start Rhasspy
RHASSPY_APP=/usr/share/rhasspy
RHASSPY_RUN=/rhasspy
RHASSPY_PROFILES="$RHASSPY_APP/profiles:$RHASSPY_RUN/profiles"

if [[ ! -d "$RHASSPY_RUN" ]]; then
    mkdir -p "$RHASSPY_RUN"
fi

cd "$RHASSPY_APP"
export FLASK_APP=app.py
flask run --host=0.0.0.0 --port=12101
