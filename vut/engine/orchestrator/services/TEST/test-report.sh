#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
# ---------------------------------------------------------------------------
#
# THE REPORT SERVICE, IN ITS NATURAL HABITAT: one shell command packs
# one test WHOLE -- metadata, source, GOOD, OUT -- for handing to
# another pair of eyes, human or AI, without them asking for file
# after file:
#
#     hwut.report APPLICATION [CHOICE] [-r|--raw] [-c|--coverage]
#
#     default    the pack, cadence written INTO the stream as
#                '<delta-t>:<line>' prefixes; raw sidecars stay out
#     --raw      the files VERBATIM, sidecars as their own sections
#     --coverage RESERVED (todo-22): accepted, and honest about it
#
# The pack is the product: stdout, exit 0, stderr silent.
#
# THE FIXTURE, built here: a packed corpus in miniature --
#
#     <work>/demo.py                        the source
#     <work>/GOOD/demo.py--basic.stdout     alpha, beta
#     <work>/OUT/demo.py--basic.stdout      alpha, BETA      (differs!)
#     <work>/OUT/...stdout.raw              raw sidecar
#     <work>/OUT/...stdout.times            cadence sidecar
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../../../.." && pwd)
REPORT="python3 $ROOT/vut/engine/orchestrator/services/report.py"

case "$1" in
    --hwut-info)
        echo "The report service face: one command packs one test whole."
        echo "CHOICES: pack, raw, bare, flags;"
        echo "HAPPY: SUCCESS.*;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

build_fixture() {       # [bare]  -- 'bare' omits the sidecars
    mkdir -p GOOD OUT
    printf 'print("alpha")\nprint("beta")\n' > demo.py
    printf 'alpha\nbeta\n'                   > GOOD/demo.py--basic.stdout
    printf 'alpha\nBETA\n'                   > OUT/demo.py--basic.stdout
    if [ "$1" != "bare" ]; then
        printf 'raw alpha\nraw BETA\n'       > OUT/demo.py--basic.stdout.raw
        printf '{"unit": "second", "delta_list": [0.0121, 1.5034]}\n' \
                                             > OUT/demo.py--basic.stdout.times
    fi
}

run_report() {          # <args...>  -- run, show pack verbatim + channels
    $REPORT "$@" > pack.txt 2> err.txt
    echo "REACTION  exit code : $?   stderr : $(wc -c < err.txt) bytes"
    echo "          the pack {"
    sed -e "s|$WORK|<work>|g" -e 's/^/              /' pack.txt
    echo "          }"
}

case "$1" in

pack)
    build_fixture
    echo "STIMULUS  hwut.report demo.py basic          (the default pack)"
    run_report demo.py basic
    echo
    echo "The cadence rides INSIDE the stream, per line; the raw"
    echo "sidecars stay out of the default pack; the hint says at once"
    echo "whether OUT meets GOOD."
    echo "SUCCESS: one dump answers every 'can you send me...' at once."
    ;;

raw)
    build_fixture
    echo "STIMULUS  hwut.report demo.py basic --raw    (the files verbatim)"
    run_report demo.py basic --raw
    echo
    echo "No prefixes woven in: the raw sidecar is its own section and"
    echo "the cadence sidecar rides verbatim, as it was written."
    echo "SUCCESS: --raw shows what is on disk, not an interpretation."
    ;;

bare)
    build_fixture bare
    echo "STIMULUS  hwut.report demo.py basic          (fixture WITHOUT sidecars)"
    run_report demo.py basic
    echo
    echo "Absence is reported, never guessed: no cadence recorded is"
    echo "SAID, and no section pretends otherwise."
    echo "SUCCESS: what is not there is spoken, not invented."
    ;;

flags)
    build_fixture
    echo "STIMULUS  the flag spellings, one flag at a time:"
    echo
    $REPORT demo.py basic -r         > short_r.txt 2> /dev/null
    $REPORT demo.py basic --raw      > long_r.txt  2> /dev/null
    $REPORT demo.py basic -c         > short_c.txt 2> /dev/null
    $REPORT demo.py basic --coverage > long_c.txt  2> /dev/null
    $REPORT demo.py basic            > neither.txt 2> /dev/null
    if cmp -s short_r.txt long_r.txt; then r_same="identical"; else r_same="DIFFER"; fi
    if cmp -s short_c.txt long_c.txt; then c_same="identical"; else c_same="DIFFER"; fi
    echo "REACTION  -r vs --raw      : $r_same"
    echo "          -c vs --coverage : $c_same"
    echo "          coverage line, asked  : $(grep '^coverage:' short_c.txt)"
    echo "          coverage line, silent : $(grep '^coverage:' neither.txt)"
    echo "          COVERAGE section, asked {"
    sed -n '/^==\[ COVERAGE \]/,/^$/p' short_c.txt | sed 's/^/              /'
    echo "          }"
    echo "          COVERAGE sections, silent : \
$(grep -c '^==\[ COVERAGE \]' neither.txt)"
    echo
    echo "One flag, two spellings -- and a RESERVED flag is honest:"
    echo "asked, it says the gathering is owed (todo-22); unasked, no"
    echo "section pretends there was anything to show."
    echo "SUCCESS: a reserved flag is honest about being reserved."
    ;;

*)
    echo "unknown choice: '$1'" >&2
    exit 1 ;;
esac
