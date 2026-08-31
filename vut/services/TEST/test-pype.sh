#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "The pype service face: the filter behind one door."
#     choices    = ["help", "filter", "shebang", "refused", "fault", "exit"]
# }
#
# ---------------------------------------------------------------------------
#
# THE PYPE FACE IS A DOOR, NOT A LANGUAGE. The language is tested where
# it lives ('test_writing_support/hwut_pype/TEST'); this suite drives
# the face and shows what the shell reads: stdout, stderr folded in,
# exit status.
#
# help      '--help' answers on stdout with the usage, exit 0 -- the
#           interpreter alone answers usage on stderr with 1, and that
#           is the one thing the face changes.
# filter    a script over stdin, and over named input files; the
#           interpreter's stdout passes through untouched; exit 0.
# shebang   '#! /usr/bin/env hwut.pype' reaches the face by PATH.
#           The launcher's execute bit is named first: a she-bang the
#           kernel cannot exec is an INSTALLATION fault, and 126 and
#           127 say which, rather than looking like a filter defect.
# refused   nothing names a script; a dangling '--pype-dir'. Refused
#           at the door, with the usage, exit 2.
# fault     a script that does not parse. The interpreter's own line,
#           exit 1.
# exit      'sys.exit(n)' inside a python block leaves untouched: the
#           script's own number, not the law's.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
BIN="$ROOT/vut/bin"
PYPE="python3 -m vut.services.pype"

case "$1" in
    --hwut-info)
        echo "The pype service face: the filter behind one door.;"
        echo "CHOICES: help, filter, shebang, refused, fault, exit;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

printf 'on: "x" => flush;\non: <else> => ignore;\n' > keep-x.pype
printf 'l1 x\nl2\nl3 x\n'                              > in-1.txt
printf 'l4\nl5 x\n'                                    > in-2.txt

show() {
    #  Stimulus shown, reaction shown, exit shown. The REPORTING is
    #  under test here, so stderr is folded into the shown reaction.
    echo "STIMULUS: $*"
    "$@" 2>&1
    echo "EXIT:     $?"
}

case "$1" in
help)
    echo "--- stdout, exit 0"
    show $PYPE --help
    echo "--- and nothing on stderr"
    $PYPE --help 2>&1 >/dev/null | sed 's/^/stderr: /'
    ;;
filter)
    echo "--- over stdin"
    printf 'l1 x\nl2\nl3 x\n' | $PYPE keep-x.pype
    echo "EXIT:     $?"
    echo "--- over named input files, in order"
    show $PYPE keep-x.pype in-1.txt in-2.txt
    echo "--- dry run reads no input"
    show $PYPE --dry-run keep-x.pype
    ;;
shebang)
    #  THE SHE-BANG PATH IS THE KERNEL'S, not the framework's: it execs
    #  'bin/hwut.pype' by PATH, so the launcher's EXECUTE BIT decides
    #  whether this works at all. A diff of filtered lines is the wrong
    #  way to learn that; the state is named first, and an exec that
    #  never started is named by its number.
    if [ -x "$BIN/hwut.pype" ]; then
        echo "LAUNCHER: bin/hwut.pype is executable"
    else
        echo "LAUNCHER: bin/hwut.pype IS NOT EXECUTABLE -- a she-bang"
        echo "          cannot reach it. Run the extraction's chmod"
        echo "          script: sh <bundle>.txt.chmod.sh"
    fi
    printf '#! /usr/bin/env hwut.pype\non: "x" => flush;\non: <else> => ignore;\n' \
        > filter.pype
    chmod +x filter.pype
    export PATH="$BIN:$PATH"
    printf 'l1 x\nl2\nl3 x\n' | ./filter.pype
    status=$?
    case $status in
        126) echo "EXIT:     126 -- found, NOT EXECUTABLE" ;;
        127) echo "EXIT:     127 -- not found on PATH" ;;
        *)   echo "EXIT:     $status" ;;
    esac
    ;;
refused)
    echo "--- nothing names a script"
    show $PYPE
    echo "--- a name that is not a file"
    show $PYPE no-such.pype
    echo "--- '--pype-dir' with nothing after it"
    show $PYPE keep-x.pype --pype-dir
    ;;
fault)
    printf 'on: bad\n' > broken.pype
    show $PYPE broken.pype < /dev/null
    ;;
exit)
    printf 'on: <bof> => {\n    import sys\n    sys.exit(7)\n}\non: <else> => ignore;\n' \
        > leave.pype
    echo | show $PYPE leave.pype
    ;;
*)
    echo "unknown choice '$1'" >&2
    exit 2 ;;
esac
echo "<hwut-end>"
