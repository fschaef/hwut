#!/bin/bash
#
# @hwut {
#     title = "UI protocol signature: produced, announced, used, recorded"
# }
#
# The four places the UI protocol's signature stands must agree: what
# 'python ui.py' produces, the 'SIGNATURE:' of ui.py's header, the
# 'SIGNATURE =' of test-html_feeder.py, adm/SIGNATURE_UI_PROTOCOL.txt.
# A changed protocol changes the first; 'python ui.py -w' writes the
# last, the other two are edited by hand. Revived 2026-11-26: an hwut 1.x
# page without a header, a wallflower since R-102 -- found the four
# disagreeing (7qRU... produced, mmiF... announced everywhere else).

# File paths
UI_FILE="../ui.py"
FEEDER_FILE="test-html_feeder.py"
GLOBAL_SIG_FILE="../../../../adm/SIGNATURE_UI_PROTOCOL.txt"

# 1. Extraction: currently produced signature (from running ui.py)
# Runs the script, finds the line, takes the 3rd word after the label
UI_OUTPUT=$(python3 "$UI_FILE" 2>/dev/null)
CURRENT_PROD_HASH=$(echo "$UI_OUTPUT" | awk '/Protocol/ {print $3}')

# 2. Extraction: signature announced in ui.py (the file content)
# Takes the 2nd word of the line containing "SIGNATURE:"
UI_FILE_SIG=$(awk '/SIGNATURE/ {print $2;exit}' $UI_FILE)

# 3. Extraction: signature used in test-ui_feeder.py
# Looks for line starting with "SIGNATURE =" and takes the word after the "="
FEEDER_SIG=$(awk '/SIGNATURE *=/ {print $3;exit}' "$FEEDER_FILE" | tr -d "'\"")

# 4. Extraction: signature announced in adm/SIGNATURE_UI_PROTOCOL.txt
# Takes the first word/content of that file
if [ -f "$GLOBAL_SIG_FILE" ]; then
    GLOBAL_SIG=$(cat "$GLOBAL_SIG_FILE" | xargs)
else
    GLOBAL_SIG="FILE_NOT_FOUND"
fi

# --- Final Output ---
echo "currently produced signature:                     (($CURRENT_PROD_HASH))"
echo "## --> produced by 'python ui.py'" 
echo "signature announced in ui.py:                     (($UI_FILE_SIG))"
echo "## --> see file header 'SIGNATURE: ..." 
echo "signature used in test-html_feeder.py:            (($FEEDER_SIG))"
echo "## --> see SIGNATURE = ..." 
echo "signature announced in adm/SIGNATURE_UI_PROTOCOL.txt: (($GLOBAL_SIG))"
echo "## --> call 'python ui.py -w'" 
echo "<hwut-end>"
