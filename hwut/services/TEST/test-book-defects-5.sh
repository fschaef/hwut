#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title    = "The book writers' D-63 onwards and the defect list on a52f2a3 (R1, ND-, Q2, S8)"
#     features = ["book-defects-round-2"]
#     choices  = ["header-once", "pipe-quiet", "units-written", "exponent-law",
#                 "zero-law", "play-neighbour", "play-cut-short",
#                 "play-no-launch", "propose-ignore", "runner-words",
#                 "demo-documents", "play-menu", "accept-first"]
# }
#
# ---------------------------------------------------------------------------
#
# The book writers' D-63 to D-65 (2026-10-24, note b) and the open-defect
# list measured on a52f2a3, one choice per fixed item (services E-180 to
# E-189):
#
# header-once     D-63: a test the book records whose header is then
#                 refused fails ONCE, 'spec [FAIL]'; run, 'hwut.report'
#                 and 'hwut.report.list' agree, the run's HINTS name the
#                 header; mended, it is green against its old GOOD.
#                 MEASURED before: 'spec [FAIL]' and 'no-app [FAIL]' ("in
#                 book, no such test"), RESULTS '1 fail' beside two lines.
# pipe-quiet      D-64: 'hwut.pype ... | head -1' ends quietly, exit 141,
#                 for a script, a system, and '--draw --svg'. MEASURED
#                 before: 'pype: [Errno 32] Broken pipe', exit 1.
# units-written   D-65, ND9, ND11: '--units' lists only spellings a line
#                 can write and the reader binds back ('um', 'angstrom',
#                 'delta_degC', '°C'); 'quantity(degC)' does not match a
#                 'delta_degC' line; '--units cM' is refused by name.
#                 MEASURED before: 38 of 470 listed spellings unwritable
#                 ('μm', 'Å', 'Δ°C', '%', 'mcd' = microday); a
#                 DimensionalityError; a traceback over an empty max().
# exponent-law    R1: 'x <= 1e-9' and 'x <= 1E-9' are numbers: 2e-16
#                 holds, 2e-6 breaks. MEASURED before: read as
#                 'quantity("1 e")-9' (the elementary charge), every
#                 value broke it; '1E-9' refused the directory.
# zero-law        ND13: a bare 0 against a law with a unit is refused as
#                 every bare number is ('x == 0 s'); '0 s' holds it, and
#                 a law over plain numbers takes plain 0. MEASURED
#                 before: a bare 0 blessed under 'x == 0 s' (pint's own
#                 exception for zero).
# play-neighbour  Q2: 'hwut.play' plays a test beside one whose header
#                 does not parse, names the other NOT PLAYED; '--all'
#                 plays the readable ones and exits 1; the unreadable
#                 one named alone is refused. MEASURED before: 'nothing
#                 played' for the whole directory.
# play-cut-short  ND6, ND3: a stream without '<hwut-end>' is shown and
#                 NOT recorded, exit 1; one killed by its cap names the
#                 cap. MEASURED before: 'RECORDED', exit 0, no cause.
# play-no-launch  ND2: an application that does not launch is a FAULT,
#                 exit 1, as the help says. MEASURED before: 'EMPTY',
#                 exit 3.
# propose-ignore  ND5: 'hwut.accept.propose' proposes no line inside a
#                 '##! ignore' region. MEASURED before: the ignored line
#                 proposed beside the real difference.
# runner-words    ND4, S8, E-189: a choice-less 'hwut_runner' application
#                 runs on '-' and refuses any other word by saying it has
#                 no choices; an application with choices called bare
#                 refuses, naming them and 'hwut.play', exit 1 -- the
#                 menu is play's. MEASURED before: "choice '-' not
#                 available. available: -."; a menu read from stdin
#                 that exited 0 or 255 on a bad answer.
# demo-documents  ND1: the feature file 'hwut.demo.python' writes points
#                 at documents that stand -- every relative path made
#                 absolute from where it was written -- and the copy
#                 runs green. MEASURED before: 18 paths pointed nowhere.
# play-menu       E-189 (ruled 2026-10-24): 'hwut.play' of an application
#                 with several choices, none named, asks on the terminal
#                 -- index or name; a word that selects nothing, or the
#                 end of input, plays nothing; without a terminal the
#                 refusal stands. Driven through a pseudo-terminal.
# accept-first    N10, E-188 (ruled 2026-10-24, (a)): play, look, a bare
#                 'hwut.accept' blesses the recording whole; the run is
#                 green. MEASURED before: 'ACCEPTED 1 of 1 / undecided',
#                 the GOOD a '--?--' mirror, the run red.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
BIN="$ROOT/hwut/bin"
export PATH="$BIN:$PATH"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "The book writers' D-63 onwards and the defect list on a52f2a3;"
        echo "CHOICES: header-once, pipe-quiet, units-written, exponent-law, zero-law, play-neighbour, play-cut-short, play-no-launch, propose-ignore, runner-words, demo-documents, play-menu, accept-first;"
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
            s/\(digest: [A-Za-z0-9_-]+\)/(digest: <tag>)/; s/wall [0-9.]+s/wall <t>s/"
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
law() {                 # <law> <value printed>: accept says blessed or refused
    page test-law.sh "tolerance { constraints = [\"$1\"] }" "echo \"v = ((x: $2))\""
    rm -rf GOOD OUT
    "$BIN/hwut.play" test-law.sh --plain > /dev/null 2>&1
    printf '%-14s over %-8s : ' "$1" "$2"
    if "$BIN/hwut.accept" --whole test-law.sh > /dev/null 2>&1; then echo "blessed"
    else                                                          echo "refused"; fi
}

case "$1" in
    header-once)
        page test-h.sh 'choices = ["x"]' 'echo "hello"'
        record
        "$BIN/hwut.accept" --whole > /dev/null 2>&1
        sed -i 's/choices = \["x"\]/choices = ["x"/' test-h.sh
        echo "== the header no longer parses"
        "$BIN/hwut.run" --plain 2>&1 | grep -E "FAIL\]|header|BOOK|no such|^RESULTS" | shown
        echo "== hwut.report --fail"
        "$BIN/hwut.report" --fail 2>&1 | grep -E "FAIL\]|no such|^RESULTS"
        echo "== hwut.report.list --fail"
        "$BIN/hwut.report.list" --fail
        echo "== mended"
        sed -i 's/\["x" }/["x"] }/' test-h.sh
        "$BIN/hwut.run" --plain 2>&1 | grep -E "^END|^RESULTS" | shown ;;
    pipe-quiet)
        printf 'on: <else> => { print(pype.line()) }\non: <eof> => ignore;\n' > a.pype
        printf -- '--> a.pype\na.pype --> b.pype\n' > s.pypes
        cp a.pype b.pype
        { echo "--> a.pype"; for i in $(seq 0 299); do echo "a.pype --> n$i.pype"; done; } > big.pypes
        for i in $(seq 0 299); do cp a.pype n$i.pype; done
        seq 1 200000 > in.txt
        for words in "a.pype in.txt" "s.pypes in.txt" "--draw --svg big.pypes"; do
            "$BIN/hwut.pype" $words 2> err.txt | head -1 | cut -c1-12 > /dev/null
            echo "$words: exit ${PIPESTATUS[0]}, stderr $(wc -c < err.txt) byte(s)"
        done ;;
    units-written)
        echo "== --units length: the spellings a line writes"
        "$BIN/hwut.pype" --units length | grep -E "^(um|angstrom|μm|Å) " | sort
        echo "== --units temperature"
        "$BIN/hwut.pype" --units temperature | grep -E "^(°C|delta_degC|degC|Δ°C) " | sort
        echo "== every listed spelling, bound back through the reader"
        python3 - <<'EOF'
import re
from hwut.auxiliary import units as U
row_list = U.unit_tuple()
bad_list = []
for unit, type_name in row_list:
    try:
        assert re.fullmatch(U.UNIT_WORD_SRC, unit)
        U.bound_value("1 " + unit, type_name)
    except Exception:
        bad_list.append(unit)
print("unwritable:", bad_list or "none")
EOF
        echo "== quantity(degC) over a difference"
        printf 'on: <t = quantity(degC)> => { print("abs", t) }\non: <else> => { print("other:", pype.line()) }\non: <eof> => ignore;\n' > d.pype
        printf '20 degC\n5 delta_degC\n' | "$BIN/hwut.pype" d.pype 2>&1
        echo "exit ${PIPESTATUS[1]}"
        echo "== --units cM"
        "$BIN/hwut.pype" --units cM; echo "exit $?" ;;
    exponent-law)
        law "x <= 1e-9" "2e-16"
        law "x <= 1e-9" "2e-6"
        law "x <= 1E-9" "2e-16"
        law "x < 1e-9 s" "2e-16 s" ;;
    zero-law)
        law "x == 0 s" "0"
        law "x == 0 s" "0 s"
        law "x > 5 ms" "0"
        law "x >= 0"   "0"
        law "x < 5"    "3" ;;
    play-neighbour)
        page test-bad.sh 'choices = ["x" }'
        page test-ok.sh  'choices = ["x"]' 'echo "hi"'
        echo "== hwut.play test-ok.sh x"
        "$BIN/hwut.play" test-ok.sh x --plain > o.txt 2>&1; echo "exit $?"
        grep -E "^FAULT|^NOT PLAYED|^RECORDED|^nothing" o.txt | shown
        rm -rf OUT
        echo "== hwut.play --all"
        "$BIN/hwut.play" --all --plain > o.txt 2>&1; echo "exit $?"
        grep -E "^FAULT|^NOT PLAYED|^RECORDED|^nothing" o.txt | shown
        echo "== hwut.play test-bad.sh x"
        "$BIN/hwut.play" test-bad.sh x --plain > o.txt 2>&1; echo "exit $?"
        grep -E "^FAULT|^NOT PLAYED|^RECORDED|^nothing" o.txt | shown ;;
    play-cut-short)
        { echo '#! /bin/bash'; echo '# @hwut { choices = ["x"] }'; echo 'echo "half"'; } > test-cut.sh
        page test-slow.sh 'choices = ["x"] caps { timeout_sec = 1 }' 'echo "before"' 'sleep 5'
        chmod +x test-cut.sh
        for t in test-cut.sh test-slow.sh; do
            echo "== hwut.play $t x"
            "$BIN/hwut.play" $t x --plain > o.txt 2>&1; echo "exit $?"
            grep -E "containment|REPORT|RECORDED" o.txt | shown
        done
        ls OUT 2>/dev/null || echo "OUT: nothing recorded" ;;
    play-no-launch)
        page test-n.sh 'choices = ["x"] execute = "/no/such/program"'
        "$BIN/hwut.play" test-n.sh x --plain > o.txt 2>&1; echo "exit $?"
        grep -E "^FAULT|^EMPTY|REPORT|RECORDED" o.txt | shown ;;
    propose-ignore)
        page test-i.sh 'choices = ["x"]' 'echo "a"' 'echo "##! ignore"' \
             'echo "noise ${N:-1}"' 'echo "####"' 'echo "b ${B:-1}"'
        record
        "$BIN/hwut.accept" --whole > /dev/null 2>&1
        N=2 B=2 "$BIN/hwut.run" --plain > /dev/null 2>&1
        "$BIN/hwut.accept.propose" -o p.txt > /dev/null 2>&1; echo "exit $?"
        grep -v "^#  " p.txt ;;
    runner-words)
        cat > one.py <<'EOF'
import sys
from hwut.test_writing_support.python.hwut_runner import HwutRunner
HwutRunner(sys.argv, "one;", {None: lambda: print("the one")}).run()
EOF
        cat > two.py <<'EOF'
import sys
from hwut.test_writing_support.python.hwut_runner import HwutRunner
HwutRunner(sys.argv, "two;", {"a": lambda: print("A"), "b": lambda: print("B")}).run()
EOF
        #  THE APPLICATION'S OWN CLOSING TOKEN is shown as '<end>': this
        #  page's stream has one closing line, its last (R-70).
        for words in "one.py -" "one.py x" "two.py c" "two.py"; do
            echo "== $words"
            python3 $words < /dev/null | sed 's/^<hwut-end>$/<end>/'
            echo "exit ${PIPESTATUS[0]}"
        done ;;
    play-menu)
        page test-two.sh 'choices = ["a", "b"]' 'echo "I am $1"'
        #  A TERMINAL IS WHAT THE MENU NEEDS: a pseudo-terminal runs the
        #  face, and the answer is typed once the prompt stands.
        cat > "$WORK/console.py" <<'PY'
import os, pty, sys
answer, argv = sys.argv[1], sys.argv[2:]
pid, fd = pty.fork()
if pid == 0:
    os.execvp(argv[0], argv)
out, sent = b"", False
while True:
    try:    data = os.read(fd, 4096)
    except OSError: break
    if not data: break
    out += data
    if not sent and b"> " in out:
        os.write(fd, b"\x04" if answer == "EOF" else (answer + "\n").encode())
        sent = True
_, status = os.waitpid(pid, 0)
sys.stdout.write(out.decode(errors="replace").replace("\r", ""))
print("exit %d" % os.waitstatus_to_exitcode(status))
PY
        for answer in 1 a x EOF; do
            echo "== answer '$answer'"
            python3 -I "$WORK/console.py" "$answer" "$BIN/hwut.play" test-two.sh --plain \
                | grep -E "^Select|^\([0-9]\)|^> |REFUSED|I am|^RECORDED|^exit" | shown
        done
        echo "== no terminal"
        "$BIN/hwut.play" test-two.sh --plain < /dev/null 2>&1 | grep REFUSED
        echo "exit ${PIPESTATUS[0]}" ;;
    accept-first)
        page test-f.sh 'choices = ["c"]' 'echo "hello"'
        "$BIN/hwut.play" test-f.sh c --plain 2>&1 | grep "^RECORDED" | shown
        "$BIN/hwut.accept" test-f.sh c 2>&1 | grep -E "ACCEPTED|blessed|undecided"
        echo "exit ${PIPESTATUS[0]}"
        echo "== GOOD"; sed "s/^<hwut-end>$/<end>/" GOOD/test-f.sh--c.txt
        "$BIN/hwut.run" --plain 2>&1 | grep -E "^END|^RESULTS" | shown ;;
    demo-documents)
        "$BIN/hwut.demo.python" "$WORK/demo" > /dev/null 2>&1; echo "exit $?"
        python3 - "$WORK/demo/TEST/hwut-features.conf" <<'EOF2'
import os, re, sys
path_list = re.findall(r'documents *= *\[([^]]*)\]', open(sys.argv[1]).read())
path_list = [p for group in path_list for p in re.findall(r'"([^"]+)"', group)]
print("%d document path(s), %d relative, %d point nowhere"
      % (len(path_list), sum(not os.path.isabs(p) for p in path_list),
         sum(not os.path.exists(p) for p in path_list)))
EOF2
        ( cd "$WORK/demo/TEST" && "$BIN/hwut" --plain 2>&1 | grep "^RESULTS" | shown ) ;;
    *)
        echo "unknown choice '$1'"; exit 1 ;;
esac
echo "<hwut-end>"
