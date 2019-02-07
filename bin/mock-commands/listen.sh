#!/usr/bin/env bash

# Available environment variables
# -------------------------------
# Base directory of Rhasspy: ${RHASSPY_BASE_DIR}
# Name of current profile: ${RHASSPY_PROFILE}
# Profile directory: ${RHASSPY_PROFILE_DIR}
wav_file="${RHASSPY_BASE_DIR}/etc/test/what_time_is_it.wav"

# Output should be 16-bit, 16 Khz, mono raw audio data
cat "$wav_file" | sox -t wav - -r 16000 -e signed-integer -b 16 -c 1 -t raw -
