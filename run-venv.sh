#!/usr/bin/env bash
set -e

export LC_ALL=C.UTF-8
export LANG=C.UTF-8

# Directory of *this* script
this_dir="$( cd "$( dirname "$0" )" && pwd )"
venv="${this_dir}/.venv"

if [[ ! -d "${venv}" ]]; then
    echo "Missing virtual environment at ${venv}"
    echo "Did you run create-venv.sh?"
    exit 1
fi

cd "${this_dir}"
source .venv/bin/activate
python3 app.py "$@"
