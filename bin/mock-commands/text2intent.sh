#!/usr/bin/env bash

# Input text is avaiable via STDIN
read -r text

# Arguments here are passed in from intent.command.arguments
intent_name="$1"
slot_name="$2"
slot_state="$3"

# Available environment variables
# -------------------------------
# Base directory of Rhasspy: ${RHASSPY_BASE_DIR}
# Name of current profile: ${RHASSPY_PROFILE}
# Profile directory: ${RHASSPY_PROFILE_DIR}

# Output should be JSON
echo "{
  \"intent\": { \"name\": \"$intent_name\" },
  \"entities\": [
    { \"entity\": \"name\", \"value\": \"$slot_name\" },
    { \"entity\": \"state\", \"value\": \"$slot_state\" }
  ],
  \"text\": \"$text\"
}"
