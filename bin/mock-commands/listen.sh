#!/usr/bin/env bash

# Available environment variables
# -------------------------------
# Base directory of Rhasspy: ${RHASSPY_BASE_DIR}
# Name of current profile: ${RHASSPY_PROFILE}
# Profile directory: ${RHASSPY_PROFILE_DIR}
wav_file="${RHASSPY_BASE_DIR}/etc/test/turn_on_living_room_lamp.wav"

# Output should be WAV data
cat "$wav_file"
