#!/usr/bin/env bash

# sentence is avaiable via STDIN
read -r text

# Available environment variables
# -------------------------------
# Base directory of Rhasspy: ${RHASSPY_BASE_DIR}
# Name of current profile: ${RHASSPY_PROFILE}
# Profile directory: ${RHASSPY_PROFILE_DIR}

# Output should be WAV data (stdout)
espeak --stdout "$text"
