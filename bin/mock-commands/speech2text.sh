#!/usr/bin/env bash

# WAV data is avaiable via STDIN
wav_file=$(mktemp)
trap "rm -f $wav_file" EXIT
cat | sox -t wav - -r 16000 -e signed-integer -b 16 -c 1 -t wav - > "$wav_file"

# Available environment variables
# -------------------------------
# Base directory of Rhasspy: ${RHASSPY_BASE_DIR}
# Name of current profile: ${RHASSPY_PROFILE}
# Profile directory: ${RHASSPY_PROFILE_DIR}
base_dir="${RHASSPY_BASE_DIR}"
profile_name="${RHASSPY_PROFILE}"
profile_dir="${RHASSPY_PROFILE_DIR}"

# Assume acoustic model is in the base profile directory.
# Use dictionary and language model from user profile directory.
pocketsphinx_continuous \
    -infile "$wav_file" \
    -hmm "${base_dir}/profiles/${profile_name}/acoustic_model" \
    -dict "${profile_dir}/dictionary.txt" \
    -lm "${profile_dir}/language_model.txt" \
    -logfn /dev/null \
    "$@" # Arguments here are passed in from intent.command.arguments

# Output should be text (stdout)
