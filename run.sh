#!/bin/bash
# Convenience script to run inkcrop

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export PYTHONPATH="$SCRIPT_DIR/src:$PYTHONPATH"

python -m inkcrop.cli "$@"
