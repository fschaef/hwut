#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# hwut {
#     title      = "The report service face: one command packs one test whole."
#     choices    = ["bare", "coverage", "flags", "pack", "raw"]
#     eq-pattern = ["SUCCESS.*"]
# }
#
# ---------------------------------------------------------------------------
#
# THE REPORT SERVICE, IN ITS NATURAL HABITAT: one shell command packs
# one test WHOLE -- metadata, source, GOOD, OUT -- for handing to
# another pair of eyes, human or AI, without them asking for file
# after file:
#
#     hwut.tell APPLICATION [CHOICE] [-r|--raw] [--no-coverage]
#
#     default       the pack, cadence written INTO the stream as
#                   '<delta-t>:<line>' prefixes; raw sidecars stay out;
#                   the COVERAGE of the run where one was harvested
#     --raw         the files VERBATIM, sidecars as their own sections
#     --no-coverage leave the coverage section out
#
# The pack is the product: stdout, exit 0, stderr silent.
#
# THE FIXTURE, built here: a packed corpus in miniature --
#
#     <work>/demo.py                              the source
#     <work>/GOOD/demo--basic.stdout              alpha, beta
#     <work>/.hwut-store/demo--basic.stdout       alpha, BETA  (differs!)
#     <work>/.hwut-store/...stdout.raw            raw sidecar
#     <work>/.hwut-store/...stdout.times          cadence sidecar
#
# THE KEY IS THE BOOKKEEPER'S: 'demo--basic', the source file's STEM --
# what RECORDING uses. The old fixture spelled 'demo.py--basic', which
# no real run ever writes; it named a corpus that could not exist, and
# the face agreed with it because the face spelled the law twice.
# Candidates live under '.hwut-store/', nominals under 'GOOD/'.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
TELL="python3 $ROOT/vut/services/tell.py"

case "$1" in
    --hwut-info)
        echo "The report service face: one command packs one test whole.;"
        echo "CHOICES: pack, raw, bare, flags, coverage;"
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

build_fixture() {       # [bare]  -- 'bare' omits the sidecars
    mkdir -p GOOD .hwut-store
    printf 'print("alpha")\nprint("beta")\n' > demo.py
    printf 'alpha\nbeta\n'                   > GOOD/demo--basic.stdout
    printf 'alpha\nBETA\n'                   > .hwut-store/demo--basic.stdout
    if [ "$1" != "bare" ]; then
        printf 'raw alpha\nraw BETA\n' \
                                > .hwut-store/demo--basic.stdout.raw
        printf '{"unit": "second", "delta_list": [0.0121, 1.5034]}\n' \
                                > .hwut-store/demo--basic.stdout.times
    fi
}

run_report() {          # <args...>  -- run, show pack verbatim + channels
    $TELL "$@" > pack.txt 2> err.txt
    echo "REACTION  exit code : $?   stderr : $(wc -c < err.txt) bytes"
    echo "          the pack {"
    sed -e "s|$WORK|<work>|g" -e 's/^/              /' pack.txt
    echo "          }"
}

case "$1" in

pack)
    build_fixture
    echo "STIMULUS  hwut.tell demo.py basic          (the default pack)"
    run_report demo.py basic
    echo
    echo "The cadence rides INSIDE the stream, per line; the raw"
    echo "sidecars stay out of the default pack; the hint says at once"
    echo "whether OUT meets GOOD."
    echo "SUCCESS: one dump answers every 'can you send me...' at once."
    ;;

raw)
    build_fixture
    echo "STIMULUS  hwut.tell demo.py basic --raw    (the files verbatim)"
    run_report demo.py basic --raw
    echo
    echo "No prefixes woven in: the raw sidecar is its own section and"
    echo "the cadence sidecar rides verbatim, as it was written."
    echo "SUCCESS: --raw shows what is on disk, not an interpretation."
    ;;

bare)
    build_fixture bare
    echo "STIMULUS  hwut.tell demo.py basic          (fixture WITHOUT sidecars)"
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
    $TELL demo.py basic -r         > short_r.txt 2> /dev/null
    $TELL demo.py basic --raw      > long_r.txt  2> /dev/null
    $TELL demo.py basic --no-coverage > without.txt 2> /dev/null
    $TELL demo.py basic               > with.txt    2> /dev/null
    if cmp -s short_r.txt long_r.txt; then r_same="identical"; else r_same="DIFFER"; fi
    echo "REACTION  -r vs --raw      : $r_same"
    echo "          coverage line, default      : \
$(grep '^coverage:' with.txt)"
    echo "          coverage line, --no-coverage: \
$(grep '^coverage:' without.txt)"
    echo "          COVERAGE sections, default      : \
$(grep -c '^==\[ COVERAGE \]' with.txt)"
    echo "          COVERAGE sections, --no-coverage: \
$(grep -c '^==\[ COVERAGE \]' without.txt)"
    echo
    echo "One flag, two spellings; and where the book knows nothing of"
    echo "coverage, no section pretends there was anything to show."
    echo "SUCCESS: the default is the useful one, and absence is spoken."
    ;;

coverage)
    build_fixture
    #  A HARVESTED RUN: the book's entry and the binary record, written
    #  as a real coverage run would leave them.
    ROOT="$ROOT" python3 - <<'PYEOF_INNER'
import json, os, sys
sys.path.insert(0, os.environ["ROOT"])
from vut.engine.coverage.record import (CoverageRecord, FileCoverage,
                                        ranges_of)
from vut.engine.coverage.binary import pack_record
from vut.engine.bookkeeper.test_run_id import TestRunId
record = CoverageRecord("python", "coverage", "coverage.py-json",
                        run=frozenset([TestRunId(0, 1)]),
                        file_db={"demo.py": FileCoverage(
                            "demo.py", ranges_of([1, 2, 3, 4, 5]),
                            ranges_of([1, 2]))})
open(".hwut-store/demo--basic.cover", "wb").write(pack_record(record))
book = {"demo": {"configuration": {}, "choices": {"basic": {
    "operations": {"Run": {"verdict": False, "report": "ok",
                           "coverage": "ok"}}}}}}
os.makedirs("GOOD", exist_ok=True)
json.dump(book, open("GOOD/result_db.json", "w"))
PYEOF_INNER
    echo "STIMULUS  hwut.tell demo.py basic          (a HARVESTED run)"
    run_report demo.py basic
    echo
    echo "The report says WHAT broke; the coverage says WHICH LINES the"
    echo "run reached -- and, first, which it did NOT."
    echo "SUCCESS: a failure and its coverage travel together."
    ;;

*)
    echo "unknown choice: '$1'" >&2
    exit 1 ;;
esac
