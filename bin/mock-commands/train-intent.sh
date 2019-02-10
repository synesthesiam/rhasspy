#!/usr/bin/env bash

# Available environment variables
# -------------------------------
# Base directory of Rhasspy: ${RHASSPY_BASE_DIR}
# Name of current profile: ${RHASSPY_PROFILE}
# Profile directory: ${RHASSPY_PROFILE_DIR}

# Input is JSON where sentences are grouped by intent.
# Each sentence contains the original text, a list of key/value slots, and a
# list of sentence tokens (words).
#
# Something like:
#
#  {
#      "GetTime": [
#          {
#              "sentence": "what time is it",
#              "entities": [],
#              "tokens": [
#                  "what",
#                  "time",
#                  "is",
#                  "it"
#              ]
#          },
#          {
#              "sentence": "tell me the time",
#              "entities": [],
#              "tokens": [
#                  "tell",
#                  "me",
#                  "the",
#                  "time"
#              ]
#          }
#      ],
#      "ChangeLightColor": [
#          {
#              "sentence": "set the bedroom light to red",
#              "entities": [
#                  {
#                      "entity": "name",
#                      "value": "bedroom light",
#                      "text": "bedroom light",
#                      "start": 8,
#                      "end": 21
#                  },
#                  {
#                      "entity": "color",
#                      "value": "red",
#                      "text": "red",
#                      "start": 25,
#                      "end": 28
#                  }
#              ],
#              "tokens": [
#                  "set",
#                  "the",
#                  "bedroom",
#                  "light",
#                  "to",
#                  "red"
#              ]
#          }
#      ]
#  }

# No output is expected.
# Here, we just show the training data we received.
cat | jq
