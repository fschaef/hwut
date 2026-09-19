#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "hwut.renovate: carry hwut 1.0's words into VUT 2.0's (B-7, initial)"
#     choices    = ["apply", "clean", "kept", "report"]
# }
#
# ---------------------------------------------------------------------------
#
#  A fixture tree as hwut 1.0 left it: an 'hwut-info.dat' with a title,
#  a '--not' line and a coverage line VUT does not know; a header
#  stating 'numeric' and 'whitespace_eqv' on one line; a conf stating
#  'slash_eqv' at its root.
#
#    report   what renovate WOULD do, nothing written
#    apply    the same with '--apply': the files after, and the
#             directory then plays, accepts and runs
#    kept     a conf that already states 'title' and 'ignore' keeps
#             them; the relic's are reported kept
#    clean    a tree with nothing to renovate
#
# ---------------------------------------------------------------------------
if [ "$1" = "--hwut-info" ]; then
    echo "hwut.renovate: carry hwut 1.0's words into VUT 2.0's"
    echo "CHOICES: report, apply, kept, clean;"
    exit 0
fi
set -u
FACE="python3 -m vut.services.renovate"
WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
printf 'hwut {\n}\n' > hwut-root.conf

fixture() {
    mkdir -p suite/TEST
    printf 'The Old Suite\n-------------\ncoverage run --omit x\n--not helper*.py\n--not *.bak\n' \
        > suite/TEST/hwut-info.dat
    printf '#!/bin/bash\n# @hwut { title = "A"  numeric = 0.01  whitespace_eqv = yes }\necho a\necho "<hwut-end>"\n' \
        > suite/TEST/test-a.sh
    chmod +x suite/TEST/test-a.sh
    printf 'hwut {\n    on_entry = "true"\n    slash_eqv = false\n}\n' > suite/TEST/hwut.conf
}
show() { echo "--- $1"; sed 's/^/    /' < "$1"; }

case "$1" in
report)
    fixture
    $FACE; echo "STATUS: $?"
    echo "--- hwut.conf untouched:"; grep -c slash_eqv suite/TEST/hwut.conf
    ;;
apply)
    fixture
    $FACE --apply; echo "STATUS: $?"
    show suite/TEST/hwut.conf
    echo "--- test-a.sh, line 2"; sed -n 2p suite/TEST/test-a.sh
    echo "--- the relic stays until the person deletes it:"; ls suite/TEST/hwut-info.dat
    echo "--- a second run:"; $FACE
    echo "--- the directory is now VUT's:"
    ( cd suite/TEST && python3 -m vut.services.play test-a.sh --save >/dev/null 2>&1
      python3 -m vut.services.accept test-a.sh --force >/dev/null 2>&1
      python3 -m vut.services.run 2>&1 | grep RESULTS | sed 's/[0-9.]* \[sec\]/N [sec]/' )
    ;;
kept)
    fixture
    printf 'hwut {\n    title = "Already Titled"\n    ignore = ["own.py"]\n}\n' > suite/TEST/hwut.conf
    $FACE; echo "STATUS: $?"
    ;;
clean)
    mkdir -p suite/TEST
    printf '#!/bin/bash\n# @hwut { title = "A" }\necho a\necho "<hwut-end>"\n' > suite/TEST/test-a.sh
    chmod +x suite/TEST/test-a.sh
    $FACE; echo "STATUS: $?"
    ;;
*)  echo "no such choice: $1"; exit 1 ;;
esac

#  THE STREAM COMPLETED (R-70).
echo "<hwut-end>"
