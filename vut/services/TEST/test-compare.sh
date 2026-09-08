#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "The compare service face: the diff convention, on stdout."
#     choices    = ["differing", "reading", "tolerated", "side-by-side"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
# }
#
# ---------------------------------------------------------------------------
#
# THE COMPARE SERVICE, IN ITS NATURAL HABITAT. The shell asks, the
# service answers by the DIFF CONVENTION -- so it composes where diff
# composes ('if hwut.compare A B; then ...'):
#
#     hwut.compare SUBJECT NOMINAL      the VERDICT view
#     hwut.compare FILE                 the READING view
#
#     EXIT 0    equivalent (or: a reading was displayed)
#     EXIT 1    at least one differing pair
#     EXIT 2    the request itself was unusable
#
# THE RENDERING IS THE PRODUCT: it goes to stdout; stderr stays silent.
# What the rows and marks look like is the renderer's own affair,
# tested at interaction/TEST -- here they are shown as the shell
# receives them.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
COMPARE="python3 -m vut.services.compare"
export PYTHONPATH="$ROOT"

case "$1" in
    --hwut-info)
        echo "The compare service face: the diff convention, on stdout.;"
        echo "CHOICES: differing, tolerated, reading, side-by-side;"
        echo "HAPPY: SUCCESS.*;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

#  THE TREE'S BOUNDARY. Every face ASCENDS collecting 'hwut.conf'
#  until it meets this file; a tree without one is refused, so a
#  fixture states its own. Empty says only 'the tree ends here'.
printf 'hwut {\n}\n' > hwut-root.conf

printf 'alpha\nvalue 3.140\n' > subject.txt
printf 'alpha\nvalue 3.141\n' > nominal.txt

show() {                # <file>  -- stdout as the shell received it
    echo "REACTION  stdout {"
    sed 's/^/              /' "$1"
    echo "          }"
}

case "$1" in

differing)
    #  3.140 against 3.141, no tolerance granted: a differing pair.
    echo "STIMULUS  subject.txt: alpha, value 3.140"
    echo "          nominal.txt: alpha, value 3.141"
    echo "          hwut.compare subject.txt nominal.txt --plain"
    $COMPARE subject.txt nominal.txt --plain > out.txt 2> err.txt
    code=$?
    show out.txt
    echo "          exit code : $code"
    echo "          stderr    : $(wc -c < err.txt) bytes"
    echo
    echo "Exit 1 says 'they differ' the way diff says it, and the"
    echo "rendering says WHERE -- on stdout, because it is the product."
    echo "SUCCESS: a difference answers 1, spoken on the product channel."
    ;;

tolerated)
    #  The SAME streams, one flag wider: '--numeric 0.01'. The verdict
    #  flips; the machinery does not.
    echo "STIMULUS  the same streams,"
    echo "          hwut.compare subject.txt nominal.txt --plain --numeric 0.01"
    $COMPARE subject.txt nominal.txt --plain --numeric 0.01 \
             > out.txt 2> err.txt
    code=$?
    show out.txt
    echo "          exit code : $code"
    echo
    echo "What was a difference is now a tolerance, and the marks say"
    echo "so; the SETUP changed the verdict, never the machinery."
    echo "SUCCESS: under the widened setup the same streams answer 0."
    ;;

reading)
    #  ONE argument asks the other question: how does compare READ this
    #  stream? Fed against itself, so only interpretation shows.
    echo "STIMULUS  hwut.compare subject.txt --plain      (one argument)"
    $COMPARE subject.txt --plain > out.txt 2> err.txt
    code=$?
    show out.txt
    echo "          exit code : $code"
    echo
    echo "No second door: the one association serves both questions,"
    echo "and a displayed reading is a success by the convention."
    echo "SUCCESS: one argument asks the reading; the answer is 0."
    ;;

side-by-side)
    #  TWO COLUMNS, subject LEFT, nominal RIGHT -- the direction a
    #  merge goes. The gutter says the relation; a wide line wraps.
    printf 'alpha\nvalue 3.140\nonly in subject\nsame ((token)) here\na line wide enough to wrap around the column it is given, so the continuation rows show\n' > s.txt
    printf 'alpha\nvalue 3.141\nsame ((other)) here\ninserted in nominal\na line wide enough to wrap around the column it is given, so the continuation rows show\n' > n.txt
    echo "STIMULUS  hwut.compare s.txt n.txt --plain --side-by-side --width 80"
    $COMPARE s.txt n.txt --plain --side-by-side --width 80 > out.txt 2> err.txt
    code=$?
    show out.txt
    echo "          exit code : $code"
    echo
    echo "STIMULUS  the same, --numeric 0.01: the pair is tolerated, gutter '~'"
    $COMPARE s.txt n.txt --plain -y --width 80 --numeric 0.01 > out.txt 2> err.txt
    sed -n '/^--\[/,/^====/p' out.txt | sed 's/^/              /'
    echo
    echo "Subject left, nominal right: what the author reads is what he"
    echo "will merge, left into right. ' ' equal, '~' tolerated, '|'"
    echo "differing, '>' subject only, '<' nominal only."
    echo "SUCCESS: one row per aligned pair, two columns, the gutter speaks."
    ;;

*)
    echo "unknown choice: '$1'" >&2
    exit 1 ;;
esac

echo "<hwut-end>"
