#!/usr/bin/env bash

# Available environment variables
# -------------------------------
# Base directory of Rhasspy: ${RHASSPY_BASE_DIR}
# Name of current profile: ${RHASSPY_PROFILE}
# Profile directory: ${RHASSPY_PROFILE_DIR}

# Pretend to wait for wake word, but just sleep for 5 seconds
sleep 5

# Output should be text
echo 'okay rhasspy'
