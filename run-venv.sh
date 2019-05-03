#!/usr/bin/env bash
set -e

export LC_ALL=C.UTF-8
export LANG=C.UTF-8

# Directory of *this* script
DIR="$( cd "$( dirname "$0" )" && pwd )"

cd "$DIR"
source .venv/bin/activate
python3 app.py "$@"
