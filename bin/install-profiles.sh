#!/usr/bin/env bash
for lang in "$@"; do
    wget -qO - https://github.com/synesthesiam/rhasspy-profiles/releases/download/v1.0-$lang/$lang.tar.gz | tar xzf -
done
