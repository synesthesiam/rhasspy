# Node-RED Examples

This directory contains two example Node-RED flows for Rhasspy. They assume Rhasspy is running on the localhost at port 12101. See the `run-nodered.sh` script for the Docker command to start Node-RED.

Both example flows use the websocket connection available at `/api/events/intent` to receive intents as Rhasspy recognizes them. The `/api/text-to-speech` endpoint in Rhasspy is also used to provide basic feedback.
