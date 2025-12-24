#!/bin/bash

# --- HWUT Info Section ---
if [ "$1" == "--hwut-info" ]; then
    echo "Cross-checks Protocol signatures across ui.py execution, source files, and global protocol definitions."
    exit 0
fi

# File paths
UI_FILE="../ui.py"
FEEDER_FILE="test-ui_feeder.py"
GLOBAL_SIG_FILE="../../../../SIGNATURE_UI_PROTOCOL.txt"

# 1. Extraction: currently produced signature (from running ui.py)
# Runs the script, finds the line, takes the 3rd word after the label
UI_OUTPUT=$(python3 "$UI_FILE" 2>/dev/null)
echo $UI_OUTPUT
CURRENT_PROD_HASH=$(echo "$UI_OUTPUT" | awk '/Protocol/ {print $3}')

# 2. Extraction: signature announced in ui.py (the file content)
# Takes the 2nd word of the line containing "SIGNATURE:"
UI_FILE_SIG=$(awk '/SIGNATURE/ {print $2;exit}' $UI_FILE)

# 3. Extraction: signature used in test-ui_feeder.py
# Looks for line starting with "SIGNATURE =" and takes the word after the "="
FEEDER_SIG=$(awk '/SIGNATURE *=/ {print $3;exit}' "$FEEDER_FILE" | tr -d "'\"")

# 4. Extraction: signature announced in SIGNATURE_UI_PROTOCOL.txt
# Takes the first word/content of that file
if [ -f "$GLOBAL_SIG_FILE" ]; then
    GLOBAL_SIG=$(cat "$GLOBAL_SIG_FILE" | xargs)
else
    GLOBAL_SIG="FILE_NOT_FOUND"
fi

# --- Final Output ---
echo "currently produced signature:                     (($CURRENT_PROD_HASH))"
echo "signature announced in ui.py:                     (($UI_FILE_SIG))"
echo "signature used in test-ui_feeder.py:              (($FEEDER_SIG))"
echo "signature announced in SIGNATURE_UI_PROTOCOL.txt: (($GLOBAL_SIG))"
