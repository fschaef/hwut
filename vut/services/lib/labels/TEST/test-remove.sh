#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "hwut.labels.remove: take a label off what a wish selects."
#     choices    = ["comments", "delete", "doors", "take"]
#     tolerance { eq_pattern = ["STATUS: [0-9]"] }
# }
#
# ---------------------------------------------------------------------------
#
# 'hwut.labels.remove <label> <wish>' -- take a label off (disc-8).
#
# take        '-' removed, '=' untouched: removing what is not there
#             is a no-op, not a fault.
# delete      a label left with no members is DELETED and the report
#             says so; a labels file left with no entries is removed
#             whole -- absent and empty mean the same.
# doors       refused by name: a label that does not stand, a wish
#             that states nothing (the remedy names the label).
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../../../.." && pwd)
export PYTHONPATH="$ROOT"
CREATE="python3 -m vut.services.lib.labels.create"
ADD="python3 -m vut.services.lib.labels.add"
REMOVE="python3 -m vut.services.lib.labels.remove"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "hwut.labels.remove: take a label off what a wish selects.;"
        echo "CHOICES: take, delete, doors;"
        echo "HAPPY: STATUS: [0-9];"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

printf 'hwut {\n}\n' > hwut-root.conf

face() {
    local cmd="$1"; shift
    $cmd "$@" > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "STDOUT {"; sed 's/^/    /' < out.txt; echo "}"
    if [ -s err.txt ]; then
        echo "STDERR {"; sed 's/^/    /' < err.txt; echo "}"
    fi
}

the_file() {
    if [ -f hwut-root.labels ]; then
        echo "THE FILE {"; sed 's/^/    /' < hwut-root.labels; echo "}"
    else
        echo "THE FILE: absent -- no label exists"
    fi
}

fixture() {
    for where in messaging/queue messaging/net storage; do
        mkdir -p "tree/$where/TEST/GOOD"
        printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n}\n' \
            > "tree/$where/TEST/hwut.conf"
        printf '#!/bin/bash\n# @hwut { title = "A"  choices = ["one", "two"] }\necho "line $1"\necho "<hwut-end>"\n' \
            > "tree/$where/TEST/test-a.sh"
        printf '#!/bin/bash\n# @hwut { title = "B" }\necho "b"\necho "<hwut-end>"\n' \
            > "tree/$where/TEST/test-b.sh"
        chmod +x "tree/$where/TEST/"*.sh
    done
}

# ---------------------------------------------------------------------------
case "$1" in

take)
    fixture
    $CREATE concern --glob "tree/messaging/*/TEST/test-b.sh" > /dev/null
    echo "--- one carried it, one never did"
    face "$REMOVE" concern \
         --glob "tree/messaging/net/TEST/test-b.sh" \
         --glob "tree/storage/TEST/test-b.sh"
    the_file
    ;;

delete)
    fixture
    $CREATE concern --glob "test-b.sh" > /dev/null
    $ADD    meta    --glob "tree/storage/TEST/test-a.sh one" > /dev/null
    echo "--- the whole set, asked for in words"
    face "$REMOVE" concern --label concern
    the_file
    echo "--- the last label goes; the file goes with it"
    face "$REMOVE" meta --label meta
    the_file
    ;;

comments)
    #  E-96: a hand comment glued to an entry (the line above or below,
    #  no blank between) travels with it and goes with it; a comment
    #  with a blank on both sides is glued to nothing and may be
    #  dropped. The header is rewritten whole.
    fixture
    $CREATE concern --glob "tree/messaging/*/TEST/test-b.sh" > /dev/null
    $ADD    meta    --glob "tree/storage/TEST/test-a.sh one" > /dev/null
    python3 - <<'PY'
import re
text = open("hwut-root.labels").read().splitlines()
out, seen = [], 0
for line in text:
    if line.startswith("#"): out.append(line); continue
    seen += 1
    if seen == 1:
        out += ["", "# loose: blank on both sides", "", "# above the first entry", line, "# below the first entry"]
    elif seen == 2:
        out += ["# above the second entry", line]
    else:
        out.append(line)
open("hwut-root.labels", "w").write("\n".join(out) + "\n")
PY
    #  E-98: the PREAMBLE -- everything down to the first '#___' rule --
    #  is the person's, kept verbatim; a note added there survives.
    sed -i '1s/^/# my own note, above the rule\n/' hwut-root.labels
    echo "--- as edited by hand"
    the_file
    echo "--- a label taken off an entry that is NOT the commented ones"
    face "$REMOVE" meta --label meta
    the_file
    echo "--- the first commented entry goes; its comments go with it"
    face "$REMOVE" concern --glob "tree/messaging/net/TEST/test-b.sh"
    the_file
    ;;

doors)
    fixture
    $CREATE concern --glob "test-b.sh" > /dev/null
    echo "--- a label that does not stand"
    face "$REMOVE" ghost --glob "test-b.sh"
    echo "--- a wish that states nothing; the remedy names the label"
    face "$REMOVE" concern
    ;;

*)
    echo "no such choice: $1"
    exit 1 ;;
esac

#  THE STREAM COMPLETED (R-70).
echo "<hwut-end>"
