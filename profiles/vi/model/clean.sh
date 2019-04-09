#!/usr/bin/env bash
set -e

if [[ -z "$1" ]]; then
    echo "Usage: clean.sh <model-dir>"
fi

rm -rf "${model_dir}/data"
rm -rf "${model_dir}/graph"
rm -f "${model_dir}"/*.log
