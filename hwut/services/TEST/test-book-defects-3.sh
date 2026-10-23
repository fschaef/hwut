#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title    = "Defects of the book writers' round 2 and the agent swarm (D-34 onwards)"
#     features = ["book-defects-round-2"]
#     choices  = ["plus-sign", "entry-goto", "refusal-exit",
#                 "propose-too-large", "not-executable",
#                 "stability-names", "record-bless"]
# }
#
# ---------------------------------------------------------------------------
#
# DEFECTS-hwut-78e11f7, round 2 (2026-10-22), one choice each:
#
# plus-sign          D-35: '((w: +4.2))' binds w = 4.2 (C-12: the sign is
#                    the number's, either sign). Against "w > 0": '4.2'
#                    and '+4.2' blessed, '-4.2' refused. MEASURED
#                    2026-10-22 before: '+4.2' refused, "'w' never bound".
# entry-goto         D-38: a mode whose '<entry>' says 'pype.goto("A")'
#                    hands the NEXT line to A: four lines, four 'A ...'.
#                    Gotos in a circle are an error naming the chain.
#                    MEASURED 2026-10-22 before: 'T swallowed 2 open' --
#                    the switch waited for the next line's handler; the
#                    circle went unnoticed, exit 0.
# refusal-exit       D-44: 'hwut.accept' that refuses a case exits 1 --
#                    a constraint the candidate breaks, a stain. A case
#                    blessed exits 0. MEASURED 2026-10-22 before: the
#                    constraint refusal exit 0, the stained one exit 3.
# propose-too-large  D-42: a case whose difference exceeds the proposal's
#                    bound is named on stdout, and the file does not say
#                    'every selected case agrees'; exit 1. MEASURED
#                    2026-10-22 before: 'DIFF(...) > 4 lines' on stdout,
#                    the file 'nothing to propose: every selected case
#                    agrees with its nominal', exit 3.
# not-executable     D-43: a test application without its x bit, whose
#                    extension no 'language-setup' entry claims, is named
#                    so: in the run's HINTS beside 'application launch
#                    failed', and in play's RESOLVED line. MEASURED
#                    2026-10-22 before: HINTS 'application launch failed'
#                    alone, play 'NOT FOUND on PATH' for a file standing.
# stability-names    D-52: 'hwut.run.stability' called inside the TEST
#                    directory names it from the root ('TEST'), in the
#                    finding, STAINED and CLEARED. MEASURED 2026-10-22
#                    before: '.: test-f.sh x', 'STAINED: .: ...'.
# record-bless       D-34, E-165 (ruled 2026-10-22): only 'hwut.run' and
#                    'hwut.play' run. A new case: 'hwut.run' does not run
#                    it, 'hwut.accept' refuses it -- no recording. 'hwut.
#                    play' records; accept blesses it and says so. The
#                    DATA changes, no play: accept blesses the recording
#                    ('one'), as recorded. The SOURCE changes: a HINT;
#                    'hwut.report.details' says 'stale' and runs nothing.
#                    'hwut.play' then accept: 'two'. MEASURED 2026-10-22
#                    before: accept ran the case itself where the source
#                    was newer, and blessed 'one' unseen where only the
#                    data changed; details ran a stale case.
#
# D-53 (a coverage run that did not complete, worded 'did not end with
# <hwut-end>') is pinned by 'test-cov_run.py run' and 'trace'.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
BIN="$ROOT/hwut/bin"
export PATH="$BIN:$PATH"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "Defects of the book writers' round 2 and the agent swarm (D-34 onwards);"
        echo "CHOICES: plus-sign, entry-goto, refusal-exit, propose-too-large, not-executable, stability-names, record-bless;"
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
    sed -E "s|$WORK|\$WORK|g; s/[0-9]+\.[0-9]+ \[sec\]/<t> [sec]/g; s/, [0-9:]+$/, <t>/"
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

case "$1" in
    plus-sign)
        page test-s.sh 'choices = ["pos", "plus", "neg"]
#   tolerance { constraints = ["w > 0"] }' \
             'case "$1" in pos) V=4.2;; plus) V=+4.2;; neg) V=-4.2;; esac' \
             'echo "w = ((w: $V))"'
        record
        for c in pos plus neg; do
            echo "== $c"
            "$BIN/hwut.accept" --whole test-s.sh $c 2>&1 \
                | grep -E "REFUSED|constraint|blessed|left alone"
        done ;;
    entry-goto)
        cat > transit.pype <<'PYPE'
A/on: "open" => {
    print("A open", pype.line_n())
}
and: goto T;
A/on: <else> => {
    print("A else", pype.line_n())
}
T/on: <entry> => {
    pype.goto("A")
}
T/on: <else> => {
    print("T swallowed", pype.line_n(), pype.line())
}
PYPE
        cat > circle.pype <<'PYPE'
on: "go" => goto A;
on: <else> => ignore;
A/on: <entry> => {
    pype.goto("B")
}
A/on: <else> => ignore;
B/on: <entry> => {
    pype.goto("A")
}
B/on: <else> => ignore;
PYPE
        echo "== transit"
        printf 'open\nopen\nopen\nx\n' | "$BIN/hwut.pype" transit.pype
        echo "exit $?"
        echo "== circle"
        printf 'go\n' | timeout 10 "$BIN/hwut.pype" circle.pype 2>&1
        echo "exit $?" ;;
    refusal-exit)
        page test-r.sh 'choices = ["x"]  tolerance { constraints = ["w > 0"] }' \
             'echo "w = ((w: -1))"'
        page test-o.sh 'choices = ["x"]' 'echo "plain"'
        page test-f.sh 'choices = ["x"]' \
             'N=$(cat "$(dirname "$0")/n" 2>/dev/null || echo 0)' \
             'echo $((N + 1)) > "$(dirname "$0")/n"' \
             'echo "v $((N % 2))"'
        record
        "$BIN/hwut.accept" --whole test-r.sh > /dev/null 2>&1
        echo "constraint refused: exit $?"
        "$BIN/hwut.accept" --whole test-o.sh > /dev/null 2>&1
        echo "blessed: exit $?"
        "$BIN/hwut.accept" --whole test-f.sh > /dev/null 2>&1
        "$BIN/hwut.run.stability" test-f.sh --repeat=6 > /dev/null 2>&1
        "$BIN/hwut.accept" --whole test-f.sh 2>&1 | grep "^REFUSED"
        "$BIN/hwut.accept" --whole test-f.sh > /dev/null 2>&1
        echo "stained refused: exit $?" ;;
    propose-too-large)
        page test-p.sh 'choices = ["x"]' \
             '[ -n "$ALT" ] && echo "inserted"' \
             'for i in 0 1 2 3 4 5; do echo "line $i"; done'
        record
        "$BIN/hwut.accept" --whole test-p.sh > /dev/null 2>&1
        ALT=1 "$BIN/hwut.run" > /dev/null 2>&1
        "$BIN/hwut.accept.propose" -o p.txt
        echo "exit $?"
        echo "== the file"
        cat p.txt ;;
    not-executable)
        printf '#! /usr/bin/env python3\n# @hwut { choices = ["x"] }\nprint("hi")\nprint("<hwut-end>")\n' \
            > test-n.py
        chmod +x test-n.py
        record
        "$BIN/hwut.accept" --whole test-n.py > /dev/null 2>&1
        chmod -x test-n.py
        echo "== hwut.run"
        "$BIN/hwut.run" --no-colour 2>&1 | grep "launch failed"
        echo "== hwut.play"
        "$BIN/hwut.play" test-n.py x --plain 2>&1 | grep "RESOLVED" | shown ;;
    stability-names)
        page test-f.sh 'choices = ["x"]' \
             'N=$(cat "$(dirname "$0")/n" 2>/dev/null || echo 0)' \
             '[ -f "$(dirname "$0")/steady" ] || echo $((N + 1)) > "$(dirname "$0")/n"' \
             'echo "v $((N % 2))"'
        record
        "$BIN/hwut.accept" --whole test-f.sh > /dev/null 2>&1
        "$BIN/hwut.run.stability" test-f.sh --repeat=4 2>&1 \
            | grep -E "test-f.sh x|STAINED"
        touch steady
        "$BIN/hwut.run.stability" test-f.sh --repeat=4 2>&1 | grep "CLEARED" ;;
    record-bless)
        printf '#! /bin/bash\n# @hwut { choices = ["a"] }\ncat "$(dirname "$0")/data.txt"\necho "<hwut-end>"\n' > test-d.sh
        chmod +x test-d.sh
        printf 'hwut { ignore = ["data.txt"] }\n' > hwut.conf
        echo one > data.txt
        when() { sed -E 's/[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}/<when>/'; }
        echo "== a new case: hwut.run, then hwut.accept"
        "$BIN/hwut.run" --no-colour 2>&1 | grep "test-d.sh  a"
        "$BIN/hwut.accept" test-d.sh a --force > out.txt 2>&1
        echo "accept exit $?"
        grep "REFUSED" out.txt
        echo "== hwut.play records it; hwut.accept blesses it"
        "$BIN/hwut.play" test-d.sh a --plain 2>&1 | grep "RECORDED"
        "$BIN/hwut.accept" test-d.sh a --force 2>&1 | grep -E "RECORDING|blessed" | when
        echo "== the data changes, no play: the recording is blessed"
        echo two > data.txt
        "$BIN/hwut.accept" test-d.sh a --force 2>&1 | grep -E "RECORDING|HINT" | when
        echo "GOOD: $(head -1 GOOD/test-d.sh--a.txt)"
        echo "== the source changes: a HINT; details runs nothing"
        echo '# edited' >> test-d.sh
        "$BIN/hwut.accept" test-d.sh a --force 2>&1 | grep -E "HINT"
        "$BIN/hwut.report.details" test-d.sh a 2>&1 | grep "^provision" \
            | sed -E "s/\(A\.[0-9]\) '[^']*'/(A.n) 'test-d.sh'/"
        echo "OUT:  $(head -1 OUT/test-d.sh--a.txt)"
        echo "== hwut.play, then hwut.accept"
        "$BIN/hwut.play" test-d.sh a --plain > /dev/null 2>&1
        "$BIN/hwut.accept" test-d.sh a --force > /dev/null 2>&1
        echo "GOOD: $(head -1 GOOD/test-d.sh--a.txt)" ;;
    *)
        echo "unknown choice '$1'"; exit 1 ;;
esac
echo "<hwut-end>"
