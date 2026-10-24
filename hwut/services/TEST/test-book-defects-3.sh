#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title    = "Defects of the book writers' round 2 and the agent swarm (D-34 onwards)"
#     features = ["book-defects-round-2"]
#     choices  = ["plus-sign", "entry-goto", "refusal-exit",
#                 "propose-too-large", "not-executable",
#                 "stability-names", "record-bless",
#                 "accept-asks-nothing", "digest", "pype-eof",
#                 "pype-inline", "pype-first-match", "diff-broken",
#                 "propose-aligned", "demo-root", "cov-dir",
#                 "labels-derived", "play-choices"]
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
#
# THE SESSION OF 2026-10-23 (rulings E-167 to E-170):
#
# accept-asks-nothing D-54, E-167: 'hwut.accept' asks nothing and opens
#                    no screen; a standing GOOD is refused '=> hwut.merge';
#                    '--dont-ask' is refused by name. MEASURED 2026-10-23
#                    before: a y/N prompt per key, on a terminal the merge.
# digest             E-168: 'hwut.play' says 'RECORDED: <file> (digest:
#                    <tag>)'; 'hwut.accept --digest=<tag>' blesses that
#                    recording and refuses another, exit 1; on several
#                    cases it is refused, exit 2; a wishlist line may carry
#                    one, after a glob it is refused, and 'hwut.run' refuses
#                    it by name.
# pype-eof           D-39: a mode without '<eof>' is refused where the
#                    script is read, on a run and on '--dry-run', exit 1.
#                    MEASURED before: exit 0 on both, the token missing.
# pype-inline        D-46: '=> { print("x") }' on one line is a block.
#                    MEASURED before: "cannot read EFFECT".
# pype-first-match   D-47: where two patterns match a line, the first
#                    defined fires; '--dry-run' NOTEs a handler that can
#                    never fire. MEASURED before: both orders accepted as
#                    'disjoint', the order decided silently.
# diff-broken        D-41: 'hwut.diff' draws the broken binding as BAD with
#                    'BROKEN:' under its line, and aligns the rest. MEASURED
#                    before: the value drawn tolerated, every later line
#                    shifted by the run's violation region.
# propose-aligned    D-42b: one inserted line is one entry of the proposal.
#                    MEASURED before: every later line a replacement.
# demo-root          D-43, D-45: 'hwut.demo.python' writes the template
#                    root. MEASURED before: 'hwut { }'.
# cov-dir            D-50: 'hwut.cov.run' takes '--cov-dir' beside '-o'.
# labels-derived     D-56: '[derived]' in 'hwut-root.labels' -- recursive,
#                    'missing in expression evaluation', a circle refused,
#                    kept verbatim by a rewrite, '--label' reaches it.
# play-choices       a test with several choices and none named is refused
#                    by its choices and '--all'; a test with none plays.
#                    MEASURED before: "no choice specified".
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
        echo "CHOICES: plus-sign, entry-goto, refusal-exit, propose-too-large, not-executable, stability-names, record-bless, accept-asks-nothing, digest, pype-eof, pype-inline, pype-first-match, diff-broken, propose-aligned, demo-root, cov-dir, labels-derived, play-choices;"
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
A/on: <eof> => ignore;
T/on: <eof> => ignore;
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
on: <eof> => ignore;
A/on: <eof> => ignore;
B/on: <eof> => ignore;
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
        #  EVERY LINE CHANGED: an alignment (D-42b) still finds six
        #  replacements, beyond the bound of four.
        page test-p.sh 'choices = ["x"]' \
             'for i in 0 1 2 3 4 5; do echo "${ALT:+row}${ALT:-line} $i"; done'
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
        "$BIN/hwut.play" test-d.sh a --plain 2>&1 | grep "RECORDED" \
            | sed 's/(digest: [^)]*)/(digest: <tag>)/'
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
    accept-asks-nothing)
        page test-a.sh 'choices = ["x", "y"]' 'echo "$1 ${ALT:-one}"'
        record
        echo "== the answers on stdin are never read"
        printf 'n\nn\n' | "$BIN/hwut.accept" --whole test-a.sh 2>&1 \
            | grep -E "blessed|left alone|ACCEPTED|\?"
        echo "exit ${PIPESTATUS[1]}"
        echo "== a standing GOOD"
        ALT=two "$BIN/hwut.play" test-a.sh x --plain > /dev/null 2>&1
        "$BIN/hwut.accept" test-a.sh x 2>&1 | grep -E "merge"
        echo "== --dont-ask"
        "$BIN/hwut.accept" --dont-ask 2>&1; echo "exit $?" ;;
    digest)
        page test-d.sh 'choices = ["x", "y"]' 'echo "$1"'
        tag() { "$BIN/hwut.play" test-d.sh $1 --plain 2>&1 \
                | sed -n 's/^RECORDED: .* (digest: \(.*\))$/\1/p'; }
        X=$(tag x); Y=$(tag y)
        echo "tag length: ${#X}"
        "$BIN/hwut.play" test-d.sh x --plain 2>&1 | grep RECORDED \
            | sed 's/(digest: [^)]*)/(digest: <tag>)/'
        echo "== two cases, one digest"
        "$BIN/hwut.accept" --whole test-d.sh --digest=$X 2>&1; echo "exit $?"
        echo "== the recording edited"
        sed -i '1s/^/edited /' OUT/test-d.sh--x.txt
        "$BIN/hwut.accept" --whole test-d.sh x --digest=$X 2>&1 \
            | grep REFUSED | sed 's/(digest [^)]*)/(digest <now>, asked <tag>)/'
        echo "exit ${PIPESTATUS[0]}"
        X=$(tag x)
        echo "== played again: blessed"
        "$BIN/hwut.accept" --whole test-d.sh x --digest=$X > /dev/null 2>&1
        echo "exit $?"
        echo "== a wishlist"
        printf './test-d.sh x --digest=%s\n./test-d.sh y --digest=%s\n' $X $Y > list.txt
        rm -f GOOD/test-d.sh--*.txt
        "$BIN/hwut.accept" --whole --wishlist list.txt 2>&1 | grep ACCEPTED
        echo './test-*.sh x --digest=abc' > glob.txt
        "$BIN/hwut.accept" --wishlist glob.txt 2>&1 | grep REFUSED
        "$BIN/hwut.run" --wishlist list.txt 2>&1 | grep REFUSED ;;
    pype-eof)
        printf 'on: "go" => goto BODY;\non: <else> => ignore;\non: <eof> => {\n    print("end")\n}\nBODY/on: <else> => ignore;\n' > e.pype
        echo "== run"
        printf 'go\n' | "$BIN/hwut.pype" e.pype 2>&1 | shown; echo "exit ${PIPESTATUS[1]}"
        echo "== dry run"
        "$BIN/hwut.pype" --dry-run e.pype 2>&1 | shown; echo "exit ${PIPESTATUS[0]}"
        echo "BODY/on: <eof> => ignore;" >> e.pype
        "$BIN/hwut.pype" --dry-run e.pype ;;
    pype-inline)
        printf 'on: "x" => { print("inline", pype.line_n()) }\non: <else> => ignore;\non: <eof> => { print("end") }\n' > i.pype
        printf 'a\nx\n' | "$BIN/hwut.pype" i.pype; echo "exit $?" ;;
    pype-first-match)
        for order in short-first long-first; do
            S='on: "abc" => {\n    print("short")\n}\n'
            L='on: "abc" "def" => {\n    print("long")\n}\n'
            [ $order = short-first ] && H="$S$L" || H="$L$S"
            printf "${H}on: <else> => ignore;\non: <eof> => ignore;\n" > $order.pype
            echo "== $order"
            printf 'abc\nabc def\nabcdef\n' | "$BIN/hwut.pype" $order.pype | tr '\n' ' '; echo
            "$BIN/hwut.pype" --dry-run $order.pype 2>&1 | sed 's/([^)]*:\([0-9]*\))/(line \1)/g'
        done ;;
    diff-broken)
        page test-c.sh 'choices = ["only", "other"]
#   tolerance { constraints = ["ms < 50"] }' \
             'echo "ms = ((ms: ${MS:-10}))"' \
             '[ "$1" = other ] && [ -n "$MS" ] && echo "line b" || echo "line a"'
        record
        "$BIN/hwut.accept" --whole test-c.sh > /dev/null 2>&1
        MS=100 "$BIN/hwut.run" > /dev/null 2>&1
        for c in only other; do
            echo "== $c"
            "$BIN/hwut.diff" test-c.sh $c --plain 2>&1 | grep -E '^(S|N| ) |\| '
        done ;;
    propose-aligned)
        page test-q.sh 'choices = ["x"]' \
             '[ -n "$ALT" ] && echo "inserted"' \
             'for i in 0 1 2 3 4 5; do echo "line $i"; done' \
             '[ -n "$ALT" ] && echo "line X" || echo "line 6"'
        record
        "$BIN/hwut.accept" --whole test-q.sh > /dev/null 2>&1
        ALT=1 "$BIN/hwut.run" > /dev/null 2>&1
        "$BIN/hwut.accept.propose" -o p.txt
        echo "exit $?"
        grep -v '^#  \|^$' p.txt ;;
    demo-root)
        "$BIN/hwut.demo.python" demo > /dev/null 2>&1
        "$BIN/hwut.config.show" --root-conf-template > template.txt 2>/dev/null
        cmp -s demo/hwut-root.conf template.txt && echo "root: the template" \
            || echo "root: NOT the template"
        grep -c "language-setup" demo/hwut-root.conf | sed 's/^/language-setup blocks: /' ;;
    cov-dir)
        "$BIN/hwut.cov.run" --help 2>&1 | grep -o -- "--cov-dir[^]]*" | head -1
        "$BIN/hwut.cov.run" --cov-dir 2>&1 | head -1 ;;
    labels-derived)
        cd "$WORK"
        page TEST/test-l.sh 'choices = ["x", "y"]' 'echo "$1"'
        page TEST/test-m.sh 'choices = ["x"]' 'echo "$1"'
        cd TEST
        "$BIN/hwut.labels.create" needs-pwsh --glob "test-l.sh x" > /dev/null
        "$BIN/hwut.labels.create" slow --glob "test-m.sh" > /dev/null
        { echo; echo "[derived]"; echo "# what this machine cannot do"
          echo "needs-outside = needs-container OR needs-pwsh"
          echo "quick = NOT needs-outside AND NOT slow"; } >> ../hwut-root.labels
        echo "== list"; "$BIN/hwut.labels.list"
        echo "== query quick"; "$BIN/hwut.labels.query" quick
        echo "== a rewrite keeps the section"
        "$BIN/hwut.labels.add" slow --glob "test-l.sh y" > /dev/null
        sed -n '/^\[derived\]/,$p' ../hwut-root.labels
        echo "== remove a derived label"
        "$BIN/hwut.labels.remove" quick --glob "test-l.sh y"; echo "exit $?"
        echo "== a circle"
        echo "a = b" >> ../hwut-root.labels; echo "b = a" >> ../hwut-root.labels
        "$BIN/hwut.labels.list" 2>&1 | shown; echo "exit ${PIPESTATUS[0]}" ;;
    play-choices)
        page test-two.sh 'choices = ["a", "b"]' 'echo "$1"'
        printf '#! /bin/bash\n# @hwut { title = "one run" }\necho "single"\necho "<hwut-end>"\n' > test-one.sh
        chmod +x test-one.sh
        "$BIN/hwut.play" test-two.sh --plain 2>&1 | grep REFUSED
        "$BIN/hwut.play" test-one.sh --plain 2>&1 | grep RECORDED \
            | sed 's/(digest: [^)]*)/(digest: <tag>)/' ;;
    *)
        echo "unknown choice '$1'"; exit 1 ;;
esac
echo "<hwut-end>"
