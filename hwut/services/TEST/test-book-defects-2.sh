#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title    = "Defects found re-measuring the book's chapters 1-5 (D-27 to D-31)"
#     features = ["book-defects-ch1-5"]
#     choices  = ["play-no-colour", "apply-names", "region-analogy",
#                 "output-constraint", "diff-head", "conflict-named",
#                 "details-judgement"]
# }
#
# ---------------------------------------------------------------------------
#
# DEFECTS-hwut-78e11f7, found on 5acc421 (2026-10-19), one choice each:
#
# play-no-colour     D-27: 'hwut.run.play' on a terminal with NO_COLOR:
#                    the reading marks '{1.0}' as its legend says, and no
#                    escape is written. MEASURED before: the numbers
#                    painted cyan, NO_COLOR not asked.
# apply-names        D-28: 'hwut.accept.apply' called inside the TEST
#                    directory names it from the root ('TEST'), not '.'.
# region-analogy     D-29: a potpourri binds '((0x1a))' to '((0x9a))'; a
#                    line OUTSIDE binds it afresh to '((0x7c))' -- the run
#                    passes it, and the diff cites the line itself, not
#                    the region. MEASURED before: 'established at S:2/N:2',
#                    a line inside the potpourri.
# output-constraint  D-30: a constraint broken in the OUTPUT is the
#                    behaviour's failure -- EXECUTION, 'constraint violated
#                    by the output' -- not 'NOMINAL -- error in GOOD file'.
# diff-head          D-31: 'hwut.run.diff | head -1' ends quietly.
#                    MEASURED before: a ValueError traceback, a ContextVar
#                    token 'created in a different Context'.
# conflict-named     D-32: a broken binding outside a region names the
#                    binding that forbids it, on the subject's side too:
#                    '((0x7c))' bound at S:5 meets '((0x2b))' on line 6.
#                    MEASURED before (727d141): line 6 red, no CONFLICT
#                    line -- the subject's lookup asked a value that is
#                    None whenever no origin is known.
# details-judgement  D-33: 'hwut.report.details' says the run's JUDGEMENT,
#                    equivalent or not -- never byte identity (ruled
#                    2026-10-21). Other handles: 'equivalent'; a line
#                    changed: 'not equivalent'. MEASURED before: 'OUT
#                    differs from GOOD' for the run judged OK.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
BIN="$ROOT/hwut/bin"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "Defects found re-measuring the book's chapters 1-5 (D-27 to D-31);"
        echo "CHOICES: play-no-colour, apply-names, region-analogy, output-constraint, diff-head, conflict-named, details-judgement;"
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
page() {                # <file> <header> <body lines...>
    local file=$1 header=$2; shift 2
    { echo '#! /bin/bash'; echo "# @hwut { $header }"; printf '%s\n' "$@"
      echo 'echo "<hwut-end>"'; } > $file
    chmod +x $file
}

case "$1" in
    play-no-colour)
        page test-n.sh 'title = "n"' 'echo "ball: 1.0 kg, friction 0.5"'
        python3 - "$BIN/hwut.run.play" <<'PYEOF'
import os, pty, re, sys
pid, fd = pty.fork()
if pid == 0:
    env = dict(os.environ, NO_COLOR="1", TERM="xterm", COLUMNS="72")
    os.execvpe(sys.argv[1], [sys.argv[1], "test-n.sh"], env)
out = b""
while True:
    try:    chunk = os.read(fd, 4096)
    except OSError: break
    if not chunk: break
    out += chunk
os.waitpid(pid, 0)
text = out.decode(errors="replace").replace("\r", "")
print("escapes written: %d" % len(re.findall(r"\x1b\[", text)))
for line in text.split("\n"):
    if "ball" in line or line.startswith("reading"): print(line)
PYEOF
        ;;
    apply-names)
        page test-a.sh 'title = "a"' 'echo "value ${V:-1}"'
        "$BIN/hwut.accept" --whole --dont-ask > /dev/null 2>&1
        V=2 "$BIN/hwut.run" > /dev/null 2>&1
        "$BIN/hwut.accept.propose" -o acc.txt test-a.sh > /dev/null 2>&1
        "$BIN/hwut.accept.apply" acc.txt 2>&1 | shown ;;
    region-analogy)
        page test-t.sh 'title = "t"' "echo '##! potpourri'" \
             'echo "ball ((0x${A:-1a}))"' 'echo "cube ((0x${B:-2b}))"' \
             "echo '####'" 'echo "ball meets ((0x${C:-1a}))"' \
             'echo "tail ${D:-x}"'
        "$BIN/hwut.accept" --whole --dont-ask > /dev/null 2>&1
        echo "== D=x: only the analogies differ"
        A=9a B=8b C=7c D=x "$BIN/hwut.run" 2>&1 | grep "^END"
        echo "== D=y: the tail differs, the diff shows the analogies"
        A=9a B=8b C=7c D=y "$BIN/hwut.run" > /dev/null 2>&1
        A=9a B=8b C=7c D=y "$BIN/hwut.run.diff" test-t.sh 2>&1 \
            | grep -A1 "ball\|cube" ;;
    output-constraint)
        page test-c.sh 'title = "c"  tolerance { constraints = ["ms < 50"] }' \
             'echo "took ((ms: ${MS:-10}))"'
        "$BIN/hwut.accept" --whole --dont-ask > /dev/null 2>&1
        MS=100 "$BIN/hwut.run" --no-colour 2>&1 | sed -n '/^HINTS/,/^HINT:/p' | shown ;;
    diff-head)
        page test-d.sh 'title = "d"' \
             'for i in $(seq 1 400); do echo "row $i ${X:-a}"; done'
        "$BIN/hwut.accept" --whole --dont-ask > /dev/null 2>&1
        X=b "$BIN/hwut.run" > /dev/null 2>&1
        X=b "$BIN/hwut.run.diff" test-d.sh 2> err.txt | head -1 > /dev/null
        echo "stderr lines beyond the NOTE: $(grep -vc '^NOTE' err.txt)"
        grep -c "Traceback" err.txt | sed 's/^/tracebacks: /' ;;
    conflict-named)
        page test-k.sh 'title = "k"' "echo '##! potpourri'" \
             'echo "ball ((0x${A:-1a}))"' 'echo "cube ((0x${B:-2b}))"' \
             "echo '####'" 'echo "ball meets ((0x${C:-1a}))"' \
             'echo "cube meets ((0x${D:-2b}))"'
        "$BIN/hwut.accept" --whole --dont-ask > /dev/null 2>&1
        A=9a B=8b C=7c D=7c "$BIN/hwut.run" > /dev/null 2>&1
        A=9a B=8b C=7c D=7c "$BIN/hwut.run.diff" test-k.sh 2>&1 \
            | sed -n '/LINE_SEQUENCE/,/CLOSING/p' ;;
    details-judgement)
        page test-j.sh 'title = "j"' 'echo "thing ((0x${H:-1a}))"' \
             'echo "tail ${T:-x}"'
        "$BIN/hwut.accept" --whole --dont-ask > /dev/null 2>&1
        for env in "H=9z T=x" "H=9z T=y"; do
            echo "== $env"
            env $env "$BIN/hwut.run" > /dev/null 2>&1
            env $env "$BIN/hwut.report.details" test-j.sh 2>&1 | grep "^verdict:"
        done ;;
esac
echo "<hwut-end>"
