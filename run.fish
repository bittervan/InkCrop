#!/usr/bin/env fish
# Convenience script to run inkcrop for fish shell

set SCRIPT_DIR (dirname (status --current-filename))
set -x PYTHONPATH "$SCRIPT_DIR/src:$PYTHONPATH"

python -m inkcrop.cli $argv
