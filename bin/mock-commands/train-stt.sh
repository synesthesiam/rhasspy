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
# {
#     "GetTime": [
#         [
#             "what time is it",
#             [],
#             [
#                 "what",
#                 "time",
#                 "is",
#                 "it"
#             ]
#         ],
#         [
#             "tell me the time",
#             [],
#             [
#                 "tell",
#                 "me",
#                 "the",
#                 "time"
#             ]
#         ]
#     ],
#     "ChangeLightColor": [
#         [
#             "set the living room lamp to red",
#             [
#                 [
#                     "name",
#                     "living room lamp"
#                 ],
#                 [
#                     "color",
#                     "red"
#                 ]
#             ],
#             [
#                 "set",
#                 "the",
#                 "living",
#                 "room",
#                 "lamp",
#                 "to",
#                 "red"
#             ]
#         ]
#     ]
# }

# No output is expected.
# Here, we just show the training sentences we received.
cat | jq -r '.[] | .[] | .[0]'
