#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

python3 "$SCRIPT_DIR/find_files.py"
python3 "$SCRIPT_DIR/find_functions.py"
python3 "$SCRIPT_DIR/find_classes.py"
python3 "$SCRIPT_DIR/find_consts.py"
python3 "$SCRIPT_DIR/find_dependencies.py"
python3 "$SCRIPT_DIR/find_imports.py"
python3 "$SCRIPT_DIR/find_fix_roadmap.py"
