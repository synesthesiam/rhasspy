#!/usr/bin/env bash

# Input text is avaiable via STDIN
read -r text

intent_name="ChangeLightState"
slot_name="living room lamp"
slot_state="on"

# Available environment variables
# -------------------------------
# Base directory of Rhasspy: ${RHASSPY_BASE_DIR}
# Name of current profile: ${RHASSPY_PROFILE}
# Profile directory: ${RHASSPY_PROFILE_DIR}

# Output should be JSON
echo "{
  \"intent\": { \"name\": \"$intent_name\", \"confidence\": 1.0 },
  \"entities\": [
    { \"entity\": \"name\", \"value\": \"$slot_name\" },
    { \"entity\": \"state\", \"value\": \"$slot_state\" }
  ],
  \"text\": \"$text\"
}"
