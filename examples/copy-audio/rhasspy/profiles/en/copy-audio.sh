#!/usr/bin/env bash

# Directory of *this* script
DIR="$( cd "$( dirname "$0" )" && pwd )"

# Create output directory if it doesn't exist
output_dir="$DIR/output"
mkdir -p "$output_dir"

# Write WAV data to file (overwrite)
cat > "$output_dir/audio.wav"
