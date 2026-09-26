#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "hwut.config.show: what a conf states, where it states it."
#     choices    = ["app_defaults", "provenance", "stray"]
# }
#
# ---------------------------------------------------------------------------
#
# A root conf and a directory's own 'hwut.conf' each carry a 'app_defaults'
# scope of test parameters; the directory's word wins, leaf by leaf, and
# what neither states is compare's default.
#
# app_defaults  the directory's own 'app_defaults' is SHOWN, merged over the
#              root's: 'b' shows the root's numeric_ratio and its own
#              slash; 'a', with no conf of its own, the root's alone.
# provenance   every value names the file it stands in: the root's as
#              'hwut-root.conf:<n>', the directory's as 'hwut.conf:<n>'.
# stray        a test parameter written directly under 'hwut { }' in a
#              conf -- outside 'app_defaults' -- is REFUSED by name, not
#              silently dropped.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../../../.." && pwd)
export PYTHONPATH="$ROOT"
SHOW="python3 -m vut.services.lib.config.show"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "hwut.config.show: what a conf states, where it states it.;"
        echo "CHOICES: app_defaults, provenance, stray;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
printf 'hwut {\n    app_defaults {\n        tolerance { numeric_ratio = 0.2 }\n    }\n}\n' > hwut-root.conf
for where in a b; do
    mkdir -p "$where/TEST"
    printf '#!/bin/bash\n# @hwut { title = "T" }\necho x\necho "<hwut-end>"\n' \
        > "$where/TEST/test-x.sh"
    chmod +x "$where/TEST/test-x.sh"
done
printf 'hwut {\n    app_defaults {\n        tolerance { slash = false }\n    }\n}\n' > b/TEST/hwut.conf

leaves() {              # <file> <option...> -- the two tolerances, and status
    $SHOW "$@" > out.txt 2>&1; status=$?
    grep -E "numeric_ratio|slash" out.txt | sed 's/^ */    /'
    echo "    STATUS: $status"
}
case "$1" in
app_defaults)
    echo "--- a: the root's app_defaults alone"
    leaves a/TEST/test-x.sh
    echo "--- b: its own app_defaults over the root's"
    leaves b/TEST/test-x.sh
    ;;
provenance)
    echo "--- b, each value naming its file"
    leaves b/TEST/test-x.sh --provenance
    ;;
stray)
    printf 'hwut {\n    tolerance { slash = false }\n}\n' > a/TEST/hwut.conf
    echo "--- a test parameter directly under 'hwut { }' in a conf"
    $SHOW a/TEST/test-x.sh > out.txt 2>&1; echo "STATUS: $?"
    grep -vE "^ " out.txt | sed "s|$WORK|\$WORK|g"
    printf 'hwut {\n    tolerance { slash = false }\n}\n' > hwut-root.conf
    rm a/TEST/hwut.conf
    echo "--- the same in the root conf"
    $SHOW a/TEST/test-x.sh > out.txt 2>&1; echo "STATUS: $?"
    grep -vE "^ " out.txt | sed "s|$WORK|\$WORK|g"
    ;;
esac
echo "<hwut-end>"
