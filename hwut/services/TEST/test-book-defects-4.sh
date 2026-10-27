#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title    = "The book writers' requirements and defects of 2026-10-24 (RQ-1 onwards, D-58 onwards)"
#     features = ["book-defects-round-2"]
#     choices  = ["compare-crash", "region-refused", "quoted-rule",
#                 "help-coverage", "numeral", "nested-root", "quantity",
#                 "units-list", "sub-root", "tick", "pype-system",
#                 "system-draw", "quantity-compare", "coverage-arms",
#                 "bubble-labels", "bubble-features", "bubble-fault"]
# }
#
# ---------------------------------------------------------------------------
#
# REQUIREMENTS-for-development (RQ-n) and DEFECTS (D-n), 2026-10-24, one
# choice each (services E-172 to E-178):
#
# compare-crash   D-58: a comparison that raises -- here 'pyrsistent'
#                 made unimportable -- FAILS the case, 'compare [FAIL]',
#                 the exception named in HINTS. MEASURED 2026-10-24
#                 before: two tracebacks, then '[OK]', exit 0.
# region-refused  D-59a: 'hwut.accept' refuses a candidate whose regions
#                 cannot be read ('constraint={speed > 0}' over no column
#                 'speed'), naming 'speed'; the run's HINT names it too.
#                 MEASURED before: blessed; then 'broken region framing'.
# quoted-rule     D-59b: a rule holding '"' is said as written,
#                 'constraint 'm == "run"''. MEASURED before: '"m == "run""'.
# help-coverage   RQ-5: 'hwut.help' names an absent 'coverage' as a road,
#                 exit 0. MEASURED before: libvterm alone, then INSTALLED.
# numeral         RQ-6: a number binding takes the longest numeral; '5.5'
#                 is no 'int'. MEASURED before: 'count 5.5' bound n = 5.
# nested-root     RQ-1, amended by RQ-9 (2026-10-27, E-200): an inner
#                 'hwut-root.conf' closes a bubble: from inside it
#                 governs; from above the walk ENTERS it under the inner
#                 configuration alone ('--no-boundary' says the same).
#                 MEASURED before RQ-1: walked from above under the outer
#                 configuration -- one case, two verdicts; before RQ-9:
#                 not walked from above, a NOTE.
# quantity        RQ-7: '<f = quantity(N)>' binds 30 and 2500 newton,
#                 leaves '3 kg' unmatched; 'quantity(ms)' reads seconds.
# units-list      RQ-7: '--unit-types' names 'time', '--units time' names
#                 's', 'h', 'ms', 'us', 'ns'.
# sub-root        RQ-1, ruled: 'hwut.sanitize root' below a root REFUSES,
#                 naming 'hwut.sanitize sub-root'; 'sub-root' writes the
#                 inner 'hwut-root.conf', and refuses where no tree stands
#                 above. MEASURED before: 'nothing to do: a boundary stands'.
# tick            RQ-3: 'tick: 0.5 => "<tick {time_sec}>"' -- lines of
#                 time, in the active mode, between the input lines; a
#                 bad interval and a bad format refused with the script.
# pype-system     RQ-2: the ruled '.pypes' example over three lines: the
#                 flow depth-first, '<eof>' once every predecessor ended,
#                 one '<hwut-end>'; then each refusal of the file.
# system-draw     RQ-2: '--draw' as ASCII; '--draw --svg' an SVG with a
#                 box per script; '--svg' alone and '--draw' of a script
#                 refused.
# quantity-compare RQ-7: '((t: 2.5 ms))' binds a quantity, 't < 50 ms'
#                 compares through pint: 40000us holds, 60 ms and 3 kg
#                 break it; a rule over an unknown unit is refused.
# coverage-arms   D-37/E-49, ruled (b): two per-case records of one source
#                 as coverage.py 7.6.1 leaves them for a generator
#                 expression -- arms -9|9|10 where the line ran, -9|10
#                 where it did not -- gather into ONE record, the arm 9->9
#                 counted as existing and not taken, and a NOTE says so.
#                 MEASURED before: 'cannot be gathered', the whole record
#                 lost, exit 1.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
BIN="$ROOT/hwut/bin"
export PATH="$BIN:$PATH"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "The book writers' requirements and defects of 2026-10-24 (RQ-1 onwards, D-58 onwards);"
        echo "CHOICES: compare-crash, region-refused, quoted-rule, help-coverage, numeral, nested-root, quantity, units-list, sub-root, tick, pype-system, system-draw, quantity-compare, coverage-arms, bubble-labels, bubble-features, bubble-fault;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/TEST"
cd "$WORK"
printf 'hwut {\n    language-setup { bash { extensions = [".sh"] interpreter = "bash" } }\n}\n' \
       > hwut-root.conf
cd TEST
shown() {
    sed -E "s|$WORK|\$WORK|g; s/[0-9]+\.[0-9]+ \[sec\]/<t> [sec]/g; s/, [0-9:]+$/, <t>/;
            s/\(digest: [A-Za-z0-9_-]+\)/(digest: <tag>)/"
}
record() {              # every case here recorded by play (E-165)
    "$BIN/hwut.play" --all --plain > /dev/null 2>&1
}
page() {                # <file> <header> <body lines...>
    local file=$1 header=$2; shift 2
    { echo '#! /bin/bash'; echo "# @hwut { $header }"; printf '%s\n' "$@"
      echo 'echo "<hwut-end>"'; } > $file
    chmod +x $file
}
pype() {                # <script text> <input text>: run, show output and status
    printf '%b' "$1" > p.pype
    printf '%b' "$2" | "$BIN/hwut.pype" p.pype 2>&1 | shown
    echo "exit ${PIPESTATUS[1]}"
}

case "$1" in
    compare-crash)
        page test-cloud.sh 'title = "cloud"' \
             'echo "##! point-cloud limit=0.05"' 'echo "${P:-0.1} 0.2"' 'echo "####"'
        record
        "$BIN/hwut.accept" --whole > /dev/null 2>&1
        mkdir -p "$WORK/nopyr/pyrsistent"
        echo 'raise ModuleNotFoundError("No module named '"'pyrsistent'"'", name="pyrsistent")' \
             > "$WORK/nopyr/pyrsistent/__init__.py"
        P=9.1 PYTHONPATH="$WORK/nopyr:$PYTHONPATH" "$BIN/hwut.run" --plain > out.txt 2>&1
        echo "exit $?"
        grep -E "^END|compare|comparison failed|^RESULTS" out.txt | grep -v Traceback | shown ;;
    region-refused)
        page test-pc.sh 'title = "pc"' \
             'echo "##! point-cloud constraint={speed > 0}"' 'echo "0.1 0.2"' 'echo "####"'
        record
        echo "== accept"
        "$BIN/hwut.accept" --whole test-pc.sh 2>&1 | grep -E "REFUSED|blessed" \
            | sed 's/ (allowed:.*//'
        echo "exit ${PIPESTATUS[0]}"
        echo "== a GOOD placed by hand: the run says why"
        mkdir -p GOOD
        printf '##! point-cloud constraint={speed > 0}\n0.1 0.2\n####\n<hwut-end>\n' \
            > GOOD/test-pc.sh.txt
        "$BIN/hwut.run" --plain 2>&1 | grep -E "test-pc.sh  " | sed 's/ (allowed:.*//' ;;
    quoted-rule)
        page test-q.sh 'title = "q"  tolerance { constraints = ["m == \"run\""] }' \
             'echo "m = ((m: \"walk\"))"'
        record
        "$BIN/hwut.accept" --whole test-q.sh 2>&1 | grep -E "REFUSED|constraint" ;;
    help-coverage)
        mkdir -p "$WORK/nocov"
        #  AN EXEC WRAPPER, NOT A SYMLINK: a venv's python started through a
        #  link in another directory runs as the bare base interpreter --
        #  without the venv's modules, so 'hwut.help' said 'absent' and
        #  exited 1 on a machine whose python3 is a venv (E-197).
        for p in python3 sh dirname readlink; do
            printf '#!/bin/sh\nexec %s "$@"\n' "$(command -v $p)" > "$WORK/nocov/$p"
            chmod +x "$WORK/nocov/$p"
        done
        OUT=$(mktemp -d)        # no 'hwut-root.conf' in or above it
        ( cd "$OUT" && PATH="$WORK/nocov" COLUMNS=72 "$BIN/hwut.help" 2>&1 \
             | grep -E -A2 "MISSING: the program 'coverage'"; echo "exit ${PIPESTATUS[0]}" )
        rm -rf "$OUT" ;;
    numeral)
        pype 'on: "count" <n = int> => { print("int", n) }\non: "count" <x = number> => { print("number", x) }\non: <else> => { print("no match:", pype.line()) }\non: <eof> => ignore;\n' \
             'count 5\ncount 5.5\ncount 5abc\ncount -3\ncount 1e3\n' ;;
    nested-root)
        #  $WORK: TEST/test-top.sh; world/ a project of its own whose
        #  root caps every case at 1 s; world/TEST/test-slow.sh sleeps 2 s.
        W="$WORK/world"
        mkdir -p "$W/TEST"
        sed 's/^hwut {/hwut {\n    app_defaults { caps { timeout_sec = 1 } }/' \
            "$WORK/hwut-root.conf" > "$W/hwut-root.conf"
        page "$W/TEST/test-slow.sh" 'title = "slow"' \
             '[ -f "$(dirname "$0")/slow" ] && sleep 2' 'echo "done"'
        page test-top.sh 'title = "top"' 'echo "top"'
        record
        "$BIN/hwut.accept" --whole > /dev/null 2>&1
        ( cd "$W/TEST" && record && "$BIN/hwut.accept" --whole > /dev/null 2>&1 )
        touch "$W/TEST/slow"        # from now on it takes 2 s
        cd "$WORK"
        #  RQ-9 (services E-200): from above, the bubble 'world/' is
        #  ENTERED under its own root -- the verdict inside and above agree.
        #  MEASURED before: a NOTE, and test-slow.sh not run from above.
        echo "== from above"
        "$BIN/hwut.run" --plain --jobs=1 --deterministic 2>&1 | grep -E "^NOTE  |^END|^RESULTS" | shown
        echo "== from inside"
        ( cd world && "$BIN/hwut.run" --plain 2>&1 | grep -E "^END|^RESULTS" | shown )
        echo "== from above, --no-boundary"
        "$BIN/hwut.run" --plain --no-boundary --jobs=1 --deterministic 2>&1 | grep -E "^NOTE  |^END|^RESULTS" | shown
        echo "== hwut.report.list from above"
        "$BIN/hwut.report.list" 2>&1 ;;
    quantity)
        pype 'on: "push" <f = quantity(N)> => { print("push", f, "N") }\non: "t =" <t = quantity(ms)> => { print("t", t, "ms") }\non: <else> => { print("no match:", pype.line()) }\non: <eof> => ignore;\n' \
             'push +30.0 N\npush 2.5 kN\npush 3 kg\nt = 2.5s\nt = 7 us\n'
        echo "== a unit nobody knows"
        printf 'on: "x" <a = quantity(cubit)> => ignore;\non: <else> => ignore;\non: <eof> => ignore;\n' > c.pype
        "$BIN/hwut.pype" --dry-run c.pype 2>&1 | shown ;;
    units-list)
        "$BIN/hwut.pype" --unit-types | grep -E "^(time|force|length) "
        "$BIN/hwut.pype" --units time | grep -E "^(s|h|ms|us|ns) " ;;
    sub-root)
        mkdir -p "$WORK/a/b"; cd "$WORK"
        for c in "root a/b" "sub-root a/b" "sub-root a/b" "root a/b"; do
            echo "== hwut.sanitize $c"
            "$BIN/hwut.sanitize" $c < /dev/null 2>&1; echo "exit $?"
        done
        echo "== hwut.sanitize root (in a/)"
        ( cd a && "$BIN/hwut.sanitize" root < /dev/null 2>&1; echo "exit $?" )
        OUT=$(mktemp -d)
        echo "== hwut.sanitize sub-root . (no tree above)"
        ( cd "$OUT" && "$BIN/hwut.sanitize" sub-root . < /dev/null 2>&1; echo "exit $?" )
        rm -rf "$OUT" ;;
    tick)
        printf 'tick: 0.5 => "<tick {time_sec}>"\non: "<tick" <t = number> => { print("tick", t, "after line", pype.line_n()) }\non: <else> => flush;\non: <eof> => { print("<hwut-end>") }\n' > t.pype
        ( echo a; sleep 0.75; echo b; sleep 0.5 ) | "$BIN/hwut.pype" t.pype; echo "exit $?"
        printf 'tick: 0 => "x"\non: <else> => ignore;\non: <eof> => ignore;\n' > t2.pype
        "$BIN/hwut.pype" --dry-run t2.pype 2>&1 | shown
        printf 'tick: 1 => "{x}"\non: <else> => ignore;\non: <eof> => ignore;\n' > t2.pype
        "$BIN/hwut.pype" --dry-run t2.pype 2>&1 | shown ;;
    pype-system|system-draw)
        printf 'on: <bof> => { print("a starts") }\non: "x" <n = int> => { print("A", n) }\nand: flush;\non: <else> => ignore;\non: <eof> => { print("a ends"); print("<hwut-end>") }\n' > a.pype
        printf 'on: "x" <n = int> => { print("Q", n) }\non: <else> => ignore;\non: <eof> => { print("q ends") }\n' > q.pype
        printf 'on: <else> => { print("b got:", pype.line()) }\non: <eof> => { print("b ends") }\n' > b.pype
        printf 'on: <else> => { print("c got:", pype.line()) }\non: <eof> => { print("c ends") }\n' > c.pype
        printf '# the ruled example\n--> a.pype\n--> q.pype\na.pype --> b.pype\n: --> c.pype\nq.pype --> b.pype\n' > s.pypes
        if [ "$1" = "system-draw" ]; then
            "$BIN/hwut.pype" --draw s.pypes; echo "exit $?"
            "$BIN/hwut.pype" --draw --svg s.pypes > s.svg; echo "exit $?"
            echo "boxes: $(grep -c '<rect' s.svg), arrows: $(grep -c '<line' s.svg)"
            grep -o '>[^<]*</text>' s.svg | tr '\n' ' '; echo
            "$BIN/hwut.pype" --svg s.pypes 2>&1; echo "exit $?"
            "$BIN/hwut.pype" --draw a.pype 2>&1; echo "exit $?"
        else
            printf 'x 1\ny\nx 2\n' | "$BIN/hwut.pype" s.pypes; echo "exit $?"
            "$BIN/hwut.pype" --dry-run s.pypes
            for bad in ': --> a.pype' '--> a.pype\nb.pype --> a.pype' \
                       '--> a.pype\na.pype --> b.pype\nb.pype --> a.pype' \
                       '--> a.pype\n--> a.pype' '--> nope.pype' 'a.pype -> b.pype'; do
                printf '%b\n' "$bad" > bad.pypes
                "$BIN/hwut.pype" --dry-run bad.pypes 2>&1 | shown; echo "exit ${PIPESTATUS[0]}"
            done
        fi ;;
    quantity-compare)
        page test-q.sh 'title = "q"  tolerance { constraints = ["t < 50 ms"] }' \
             'echo "took ((t: ${T:-2.5 ms}))"'
        record
        "$BIN/hwut.accept" --whole test-q.sh 2>&1 | grep -E "REFUSED|blessed"
        for t in "40000us" "60 ms" "3 kg"; do
            echo "== T=$t"
            T="$t" "$BIN/hwut.run" --plain 2>&1 | grep -E "^END|broken by" | sed 's/^ *//'
        done
        echo "== a rule over an unknown unit"
        sed -i 's/50 ms/50 apples/' test-q.sh
        "$BIN/hwut.run" --plain 2>&1 | grep -E "apples" | shown ;;
    coverage-arms)
        python3 - "$WORK" <<'PYEOF2'
import os, sys
from hwut.engine.coverage.database.record import CoverageRecord, FileCoverage
from hwut.engine.coverage.database.binary import pack_record
from hwut.engine.coverage.output import gather, coverage_path
from hwut.engine.coverage.database.gathered import (unpack_gathered,
                                                     format_gathered)
work = sys.argv[1]; out = os.path.join(work, "out"); os.makedirs(out)
run_list = []
for choice, covered, branch in (("some", ((6, 9),), ((9, 7, 3, "-9|9|10"),)),
                                ("none", ((6, 8),), ((9, 0, 2, "-9|10"),))):
    record = CoverageRecord(language="python", tool="coverage",
                            source="coverage.py-json", counts_f=False,
                            file_db={"test-gen.py": FileCoverage(
                                "test-gen.py", ((6, 11),), covered, None,
                                {"branch": branch})})
    path = os.path.join(work, choice + ".record")
    with open(path, "wb") as handle: handle.write(pack_record(record))
    run_list.append(("", "test-gen.py", choice, path))
run_n, source_n, outside_list, note_list = gather(out, run_list)
print("gathered: %i run(s), %i source(s)" % (run_n, source_n))
for note in note_list: print("NOTE: %s" % note)
with open(coverage_path(out, "test-gen.py"), "rb") as handle:
    print(format_gathered(unpack_gathered(handle.read())))
PYEOF2
        ;;
    bubble-labels|bubble-features|bubble-fault)
        #  RQ-9 (2026-10-27, services E-200): a 'hwut-root.conf' closes a
        #  bubble -- from inside no way out, from outside every way in;
        #  one case, one verdict wherever hwut is called. $WORK holds
        #  TEST/test-top.sh; world/ is a bubble with world/TEST/test-w.sh.
        #  MEASURED before: from above, world/ was not walked (a NOTE);
        #  '--no-boundary' walked it, but '--label' gave its runs no
        #  label, '-F' refused without the outer feature file, and a
        #  broken 'world/hwut-root.conf' was named 'hwut-root.conf'.
        W="$WORK/world"
        mkdir -p "$W/TEST"
        cp "$WORK/hwut-root.conf" "$W/hwut-root.conf"
        page "$W/TEST/test-w.sh" 'choices = ["x", "y"]' 'echo "world $1"'
        page test-top.sh 'choices = ["x", "y"]' 'echo "top $1"'
        record; "$BIN/hwut.accept" --whole > /dev/null 2>&1
        ( cd "$W/TEST" && record && "$BIN/hwut.accept" --whole > /dev/null 2>&1 )
        cd "$WORK"
        ran() {          # <where> <args...>: the END and RESULTS lines
            local where=$1; shift
            echo "== $where: hwut.run $*"
            ( [ "$where" = inside ] && cd world
              "$BIN/hwut.run" "$@" --plain --jobs=1 --deterministic 2>&1 \
                  | grep -E "^ERROR|^REFUSED|^RESULTS| \. \. \. " | shown )
        }
        case "$1" in
        bubble-labels)
            echo "== inside: hwut.labels.create slow"
            ( cd world && "$BIN/hwut.labels.create" slow --glob 'test-*' 2>&1 )
            echo "== above: hwut.labels.create fast"
            "$BIN/hwut.labels.create" fast --glob 'test-*' 2>&1
            echo "== above: the outer file's entries"
            grep -E "^[.:]" hwut-root.labels
            ran inside --label slow
            ran above  --label slow
            ran above  --label fast ;;
        bubble-features)
            printf 'features {\n    childs {\n        flow { title = "a flow" }\n    }\n}\n' \
                   > "$W/TEST/hwut-features.conf"
            ( cd world && "$BIN/hwut.features.init" > /dev/null 2>&1 \
                && "$BIN/hwut.features.register" > /dev/null 2>&1 \
                && "$BIN/hwut.run" --plain > /dev/null 2>&1 )
            sed -i 's/choices = \["x", "y"\]/features = ["flow"] choices = ["x", "y"]/' "$W/TEST/test-w.sh"
            ( cd world && "$BIN/hwut.features.register" > /dev/null 2>&1 \
                && "$BIN/hwut.run" --plain > /dev/null 2>&1 )
            ran inside -F flow
            ran above  -F flow ;;
        bubble-fault)
            printf 'hwut {\n    no_such_key = 1\n}\n' > "$W/hwut-root.conf"
            ran above
            cp hwut-root.conf "$W/hwut-root.conf"
            sed -i 's/^hwut {/hwut {\n    no_such_key = 1/' hwut-root.conf
            ran inside
            ran above ;;
        esac ;;
    *)
        echo "unknown choice '$1'"; exit 1 ;;
esac
echo "<hwut-end>"
