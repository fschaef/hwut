#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "The pype service called as a shell citizen -- its natural habitat."
#     choices    = ["absent_script", "exit_code", "filter"]
#     eq-pattern = ["SUCCESS.*"]
# }
#
# ---------------------------------------------------------------------------
#
# THE SERVICE IN ITS NATURAL HABITAT: pype is a PIPE FILTER, and this test
# calls it as one -- a producer, a pipe, the filter, the terminal. No
# Python test frame stands between the service and its caller; the caller
# IS the shell, as it will be in the field.
#
#     producer ──► │ pipe │ ──► hwut_pype script.pype ──► stdout
#
# The display: STIMULUS first (the command line and what flows in), then
# REACTION (what comes out, verbatim). A reader compares the two by eye;
# the GOOD file is the blessed description of the behaviour.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
PYPE="python3 $HERE/../hwut_pype.py"

case "$1" in
    --hwut-info)
        echo "The pype service called as a shell citizen -- its natural habitat.;"
        echo "CHOICES: filter, exit_code, absent_script;"
        echo "HAPPY: SUCCESS.*;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

case "$1" in

filter)
    #  Canonicalisation as one stage of a pipe: arbitrary order in,
    #  canonical order out.
    cat > "$WORK/sort.pype" << 'EOF'
on: <bof> => {
    collected = []
}
on: <else> => {
    collected.append(pype.line())
}
on: <eof> => {
    for line in sorted(collected):
        print(line)
}
EOF
    echo "STIMULUS  printf 'zebra\\napple\\nmango\\n' | hwut_pype sort.pype"
    echo "REACTION"
    printf 'zebra\napple\nmango\n' | $PYPE "$WORK/sort.pype" | sed 's/^/    /'
    echo "SUCCESS: the filter is one stage of a pipe, like any other."
    ;;

exit_code)
    #  A shell composes on EXIT CODES; the service must be a citizen.
    cat > "$WORK/pass.pype" << 'EOF'
on: <else> => {
    print(pype.line())
}
EOF
    printf 'a line\n' | $PYPE "$WORK/pass.pype" > /dev/null
    echo "STIMULUS  a clean run          -> exit code: $?"
    printf 'on: <else =>\n' > "$WORK/broken.pype"
    $PYPE "$WORK/broken.pype" < /dev/null > /dev/null 2>"$WORK/err"
    echo "          a broken script      -> exit code: $?"
    echo "REACTION  stderr says: $(head -1 "$WORK/err" | sed "s|$WORK|<work>|")"
    echo "SUCCESS: zero on success, non-zero with a spoken reason."
    ;;

absent_script)
    #  The habitat's classic accident: the script path is wrong.
    printf 'a line\n' | $PYPE "$WORK/no-such.pype" > "$WORK/out" 2>"$WORK/err"
    code=$?
    echo "STIMULUS  hwut_pype no-such.pype   (the file does not exist)"
    echo "REACTION  exit code: $code"
    echo "          stdout   : $(wc -c < "$WORK/out") bytes"
    echo "          stderr   : $(head -1 "$WORK/err" | sed "s|$WORK|<work>|")"
    echo "SUCCESS: the fault is spoken on stderr; stdout stays clean."
    ;;

*)
    echo "unknown choice: '$1'" >&2
    exit 1 ;;
esac
