#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# hwut {
#     title      = "The launcher roof: every shim answers with its face's voice."
#     choices    = ["answer", "path"]
# }
#
# ---------------------------------------------------------------------------
#
# THE LAUNCHER ROOF, DRIVEN AS A TABLE: every shim in bin/ is called and
# must answer with its face's own voice. A launcher that resolves its
# location wrongly, or loses PYTHONPATH, shows as a divergent cell.
#
# answer   every launcher called by path: the exit code and the first
#          non-empty line of what it said. The faces answer '--help'
#          with 0; 'hwut.pype' answers a bare call with its usage, 1.
#
# path     the PATH form and the by-path form must agree byte-for-byte;
#          a '#! /usr/bin/env hwut.pype' she-bang script must run when
#          bin/ is on PATH -- the display suite's reliance, pinned.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
BIN=$(cd "$HERE/.." && pwd)
unset COLUMNS NO_COLOR

case "$1" in
    --hwut-info)
        echo "The launcher roof: every shim answers with its face's voice.;"
        echo "CHOICES: answer, path;"
        exit 0 ;;
esac

FACE_LIST="show plan run accept target cov compare merge tell
           stability wishlist report remove remove-choice
           rename rename-choice"

first_line() { grep -m1 -v '^[[:space:]]*$'; }

# ---------------------------------------------------------------------------
if [ "$1" == "answer" ]; then
    for name in $FACE_LIST; do
        out=$("$BIN/hwut.$name" --help 2>&1); code=$?
        printf 'hwut.%-13s exit %d: %s\n' "$name" "$code" \
               "$(echo "$out" | first_line)"
    done
    out=$("$BIN/hwut" --help 2>&1); code=$?
    printf 'hwut%-13s exit %d: %s\n' "" "$code" \
           "$(echo "$out" | first_line)"
    err=$("$BIN/hwut.pype" 2>&1 >/dev/null); code=$?
    printf 'hwut.%-13s exit %d: %s\n' "pype" "$code" \
           "$(echo "$err" | first_line)"
fi

# ---------------------------------------------------------------------------
if [ "$1" == "path" ]; then
    WORK=$(mktemp -d)
    trap 'rm -rf "$WORK"' EXIT
    cd "$WORK"
    export PATH="$BIN:$PATH"

    by_path=$("$BIN/hwut.show" --help 2>&1)
    by_PATH=$(hwut.show --help 2>&1)
    [ "$by_path" == "$by_PATH" ] \
        && echo "hwut.show: PATH form == by-path form: True" \
        || echo "hwut.show: PATH form == by-path form: FALSE"

    printf '#! /usr/bin/env hwut.pype\non: "x" => flush;\non: <else> => ignore;\n' \
        > filter.pype
    chmod +x filter.pype
    printf 'l1 x\nl2\nl3 x\n' | ./filter.pype
    echo "she-bang through PATH: exit $?"
fi
