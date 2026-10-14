#!/usr/bin/env bash

# PURPOSE: Unused code detection with vulture
# 
# DESCRIPTION:
#
#   This HWUT script runs vulture on a Python subtree,
#   excluding ON-HOLD-* files and honoring a whitelist.py file.
#   It prints a standard header and footer. No output in the middle
#   means success: "no output is good output".
#
# AUTHOR: Frank-Rene Schaefer
#_______________________________________________________________________

if [[ "$1" == "--hwut-info" || "$1" == "-h" ]]; then
    echo "Detect unused python code with 'vulture'."
    exit 0
fi

set -u

# Default subtree and whitelist location
SUBTREE="${1:-.}"
WHITELIST="detect-unused-code-whitelist.py"

# Print standard HWUT header
# Build file list deterministically, excluding ON-HOLD-*.py
PY_FILES=$(find "$SUBTREE" -type f -name "*.py" ! -name "ON-HOLD-*.py" | sort)

# Run vulture, capture output
pushd >& /dev/null
OUTPUT=$(vulture $PY_FILES "$WHITELIST" 2>&1 || true)
popd >& /dev/null

echo "no output is good output"
# Normalize output
echo "unused code: {"
echo "$OUTPUT" | awk '{print "   "$0}'
echo "}"
echo "<terminated>"
