#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title    = "The book writers' D-63 onwards and the defect list on a52f2a3 (R1, ND-, Q2, S8)"
#     features = ["book-defects-round-2"]
#     choices  = ["header-once", "pipe-quiet", "units-written", "exponent-law",
#                 "zero-law", "play-neighbour", "play-cut-short",
#                 "play-no-launch", "propose-ignore", "runner-words",
#                 "demo-documents", "play-menu", "accept-first",
#                 "laws-all", "conf-unread", "unit-algebra", "law-names",
#                 "genomics", "link-bits"]
# }
#
# ---------------------------------------------------------------------------
#
# The book writers' D-63 to D-65 (2026-10-24, note b) and the open-defect
# list measured on a52f2a3, one choice per fixed item (services E-180 to
# E-191; compare C-22):
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
#                 'delta_degC' line; '--units M' (molar) is refused by
#                 name ('cM' was, until it became a centimorgan, E-194).
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
# laws-all        M3, U-4, compare C-22 (ruled 2026-10-25): two laws broken
#                 and a line differing besides. The run's verdict stops
#                 where the equivalence check bails out ('[FAIL]', nothing
#                 more); 'hwut.diff' marks BROKEN under both laws;
#                 'hwut.accept' names both. MEASURED before: the diff drew
#                 '~((n: 9))~' as tolerated, no BROKEN; accept named "n < 5"
#                 alone.
# conf-unread     ND7, E-190 (ruled 2026-10-25, (a)): a configuration file
#                 that does not read fails every case it governs -- the
#                 directory at and below it -- 'spec [FAIL]', not run; a
#                 sibling directory runs. Root file, a parent's 'hwut.conf'
#                 and a TEST directory's own. 'hwut.play' and 'hwut.accept'
#                 refuse, exit 1. MEASURED before: 'caps' at the root of
#                 'hwut-root.conf' -- play recorded under the default cap
#                 and said nothing, accept blessed, the run said '1 ok'.
# unit-algebra    ND12, E-191 (ruled 2026-10-25, (a)): a unit-less number in
#                 a law fails where it meets a quantity ('t > 0' over
#                 -5 degC: "write its unit"); an absolute temperature in
#                 arithmetic fails by name; pint's algebra otherwise --
#                 a difference of readings is a delta_degC, speed x time a
#                 length, force = mass x acceleration. pype keeps readings
#                 and differences apart; information is a dimension of its
#                 own (ND10, E-192): '10 GHz' is no data rate, '90 degree'
#                 no size. MEASURED before: the frost check
#                 't > 0' over -5 degC blessed (268.15 K > 0); 't * 2' over
#                 20 degC computed in kelvin; '5 delta_degC' bound as 5 K.
# law-names       E-193 (ruled 2026-10-26, (a)): what a law's words mean.
#                 A binding named like a constant of the namespace ('e',
#                 'pi') is refused by name -- a law read it as Euler's
#                 number. An exponent is a number of magnitude at most 64
#                 ('10 ** 10 ** 10' held the run for good). A glued product
#                 '10 m*force' takes the longest unit pint knows; where the
#                 swallowed word is a binding ('2 kg*a', 'a' = annum) the
#                 refusal says so. Two units that do not compare are said
#                 with their dimensions. MEASURED before: ((e: 30 J)) under
#                 'e < 3' compared 2.718; '10 m*force' was no unit.
# genomics        ND14, E-194 (ruled 2026-10-26, (a)): 'bp' is a base pair,
#                 a sequence length ('kbp', 'Mbp', 'Gbp'); 'cM' a
#                 centimorgan, a genetic distance. MEASURED before:
#                 '1200 bp' bound pint's big point, 0.423 m, under
#                 'quantity(length)' -- and held 'n < 1 m'; '5 cM' bound
#                 centimolar.
# link-bits       E-195 (ruled 2026-10-26, (i)): 'kb', 'Mb', 'Gb' are kilo-,
#                 mega-, gigabits, as a link speed writes them. MEASURED
#                 before: '100 Mb/s' bound megabarn per second, '1 Gb/s'
#                 gilbert per second -- no data rate.
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
        echo "CHOICES: header-once, pipe-quiet, units-written, exponent-law, zero-law, play-neighbour, play-cut-short, play-no-launch, propose-ignore, runner-words, demo-documents, play-menu, accept-first, laws-all, conf-unread, unit-algebra, law-names, genomics, link-bits;"
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
            s/\(digest: [A-Za-z0-9_-]+\)/(digest: <tag>)/; s/wall [0-9.]+s/wall <t>s/;
            s/ +\|\|[0-9]+$//"
    #  ' ||N' ends a run line: how many runs stood at that instant -- the
    #  recording machine's cores, not the subject (determinism law).
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
        #  A DIFFERENCE IS ITS OWN TYPE (E-191).
        echo "== --units temperature_difference"
        "$BIN/hwut.pype" --units temperature_difference | grep -E "^(delta_degC|Δ°C) " | sort
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
        echo "== --units M"
        "$BIN/hwut.pype" --units M; echo "exit $?" ;;
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
    laws-all)
        page test-two.sh 'choices = ["x"] tolerance { constraints = ["n < 5", "m < 5"] }' \
             'echo "head ${H:-a}"' 'echo "n = ((n: ${N:-3}))"' 'echo "m = ((m: ${M:-3}))"'
        record
        "$BIN/hwut.accept" test-two.sh x > /dev/null 2>&1
        echo "== hwut.run: line 1 differs, n and m break their laws"
        N=9 M=9 H=b "$BIN/hwut.run" --plain 2>&1 | grep -E "^END|constraint \"" | shown
        echo "== hwut.diff"
        "$BIN/hwut.diff" test-two.sh x 2>&1 | grep -E "^S |BROKEN"
        echo "== hwut.accept of that recording, no nominal standing"
        rm -rf GOOD/test-two.sh--x.txt
        "$BIN/hwut.accept" test-two.sh x 2>&1 | grep -E "^REFUSED|constraint \""
        echo "exit ${PIPESTATUS[0]}" ;;
    conf-unread)
        mkdir -p "$WORK/a/TEST" "$WORK/z/TEST"
        cd "$WORK/a/TEST"; page test-c.sh 'choices = ["x", "y"]' 'echo "c $1"'
        record; "$BIN/hwut.accept" > /dev/null 2>&1
        cd "$WORK/z/TEST"; page test-c.sh 'choices = ["x", "y"]' 'echo "c $1"'
        record; "$BIN/hwut.accept" > /dev/null 2>&1
        cd "$WORK"
        probe() {
            echo "== hwut.run"
            "$BIN/hwut.run" --plain > o.txt 2>&1; echo "exit $?"
            grep -E "^ERROR|FAIL\]|^END|configuration does not read|^RESULTS" o.txt \
                | grep -v "^ *[|+']" | shown
            echo "== hwut.report.list --fail"; "$BIN/hwut.report.list" --fail
            echo "== hwut.play a/TEST"
            ( cd a/TEST && "$BIN/hwut.play" test-c.sh x --plain 2>&1 \
                  | grep -E "^FAULT|^nothing|^RECORDED" | shown
              echo "exit ${PIPESTATUS[0]}" )
            echo "== hwut.accept --directory=a/TEST"
            "$BIN/hwut.accept" --directory=a/TEST 2>&1 | grep -E "^FAULT|^REFUSED" | shown
            echo "exit ${PIPESTATUS[0]}"
        }
        unknown='hwut {\n    no_such_key = 1\n}\n'
        echo "######## a/hwut.conf: unknown key"
        printf "$unknown" > a/hwut.conf; probe; rm a/hwut.conf
        echo "######## a/TEST/hwut.conf: unknown key"
        printf "$unknown" > a/TEST/hwut.conf; probe; rm a/TEST/hwut.conf
        echo "######## hwut-root.conf: 'caps' at the root"
        sed -i 's/^}$/    caps { timeout_sec = 1 }\n}/' hwut-root.conf; probe ;;
    unit-algebra)
        judged() {      # <law> <line printed>: blessed, or the refusal's reason
            page test-u.sh "tolerance { constraints = [\"$1\"] }" "echo \"$2\""
            rm -rf GOOD OUT
            "$BIN/hwut.play" test-u.sh --plain > /dev/null 2>&1
            printf '%-24s over %-34s : ' "$1" "$2"
            #  THE REFUSAL'S CONSTRAINT LINE: its reason after ' -- ', or 'broken'.
            "$BIN/hwut.accept" test-u.sh > o.txt 2>&1 && echo "blessed" \
                || grep -m1 '^    constraint ' o.txt \
                   | sed -E 's/.*, line [0-9]+ -- (.*)$/refused: \1/; t; s/.*/refused: broken/'
        }
        judged "t > 0"                  "frost ((t: -5 degC))"
        judged "t > 0 degC"             "frost ((t: -5 degC))"
        judged "t * 2 < 100 degC"       "warm ((t: 20 degC))"
        judged "t2 - t1 < 5 delta_degC" "rise ((t1: 20 degC)) to ((t2: 23 degC))"
        judged "t2 - t1 < 2 delta_degC" "rise ((t1: 20 degC)) to ((t2: 23 degC))"
        judged "v * t < 10 m"           "run ((v: 2 m/s)) for ((t: 4 s))"
        judged "f == m * a"             "((f: 6 N)) = ((m: 2 kg)) x ((a: 3 m/s**2))"
        judged "x < 2 * y"              "((x: 9 ms)) against ((y: 5 ms))"
        judged "x / y > 2"              "((x: 10 ms)) over ((y: 2 s))"
        judged "x < 5"                  "plain ((x: 3))"
        #  INFORMATION IS A DIMENSION OF ITS OWN (ND10, E-192).
        judged "r >= 100 MB/s"          "rate ((r: 1 Gbit/s))"
        judged "r >= 100 MB/s"          "rate ((r: 10 GHz))"
        judged "n < 1 MB"               "size ((n: 7))"
        echo "== pype: readings and differences apart"
        printf '%s\n' 'on: <t = quantity(temperature)> => { print("reading", t) }' \
               'on: <d = quantity(temperature_difference)> => { print("difference", d) }' \
               'on: <b = quantity(data)> => { print("bytes", b) }' \
               'on: <else> => { print("other:", pype.line()) }' 'on: <eof> => ignore;' > q.pype
        printf '20 degC\n5 delta_degC\n300 K\n3 MB\n90 degree\n' | "$BIN/hwut.pype" q.pype ;;
    law-names)
        judged() {      # <law> <line printed>: blessed, or the refusal's reason
            page test-u.sh "tolerance { constraints = [\"$1\"] }" "echo \"$2\""
            rm -rf GOOD OUT
            "$BIN/hwut.play" test-u.sh --plain > p.txt 2>&1
            printf '%-22s over %-34s : ' "$1" "$2"
            if grep -q '^FAULT' p.txt; then
                grep -m1 '^FAULT' p.txt | sed -E "s/.*: '[^']*': //; s/^/play: /"
                return
            fi
            "$BIN/hwut.accept" test-u.sh > o.txt 2>&1 && echo "blessed" \
                || grep -m1 -E '^    (constraint|binding) ' o.txt \
                   | sed -E 's/.*, line [0-9]+ -- (.*)$/refused: \1/; t; s/.*/refused: broken/'
        }
        judged "x < 3"                  "((e: 30 J)) and ((x: 1))"
        judged "e < 3"                  "((e: 30 J))"
        judged "x < 10 ** 10 ** 10"     "((x: 1))"
        judged "x ** 2 < 10 m**2"       "((x: 3 m))"
        judged "s < 3 m*s"              "((s: 2 kg))"
        judged "v * t == 10 m*force"    "((v: 2 m/s)) ((t: 5 s)) ((force: 1))"
        judged "f == 2 kg*a"            "((f: 6 N)) with ((a: 3 m/s**2))"
        judged "f == 2 kg*a"            "((a: 3 m/s**2)) with ((f: 6 N))"
        judged "f == 2 kg * a"          "((f: 6 N)) with ((a: 3 m/s**2))"
        judged "x < 10 m"               "((x: 3 kg))" ;;
    genomics)
        judged() {      # <law> <line printed>: blessed, or the refusal's reason
            page test-g.sh "tolerance { constraints = [\"$1\"] }" "echo \"$2\""
            rm -rf GOOD OUT
            "$BIN/hwut.play" test-g.sh --plain > /dev/null 2>&1
            printf '%-12s over %-28s : ' "$1" "$2"
            "$BIN/hwut.accept" test-g.sh > o.txt 2>&1 && echo "blessed" \
                || grep -m1 '^    constraint ' o.txt \
                   | sed -E 's/.*, line [0-9]+ -- (.*)$/refused: \1/; t; s/.*/refused: broken/'
        }
        judged "n < 2 kbp"   "insert ((n: 1200 bp))"
        judged "n < 1 kbp"   "insert ((n: 1200 bp))"
        judged "n < 1 m"     "insert ((n: 1200 bp))"
        judged "g > 3 Gbp"   "genome ((g: 3100 Mbp))"
        judged "d <= 50 cM"  "map ((d: 12.5 cM))"
        judged "d < 1 cm"    "map ((d: 12.5 cM))"
        judged "x < 1 m"     "((x: 1200 big_point))"
        echo "== pype: what a line binds"
        printf '%s\n' 'on: <n = quantity(sequence_length)> => { print("sequence", n) }' \
               'on: <d = quantity(genetic_distance)> => { print("distance", d) }' \
               'on: <x = quantity(length)> => { print("length", x) }' \
               'on: <else> => { print("other:", pype.line()) }' 'on: <eof> => ignore;' > g.pype
        printf '1200 bp\n2 kbp\n5 cM\n5 cm\n12 pp\n' | "$BIN/hwut.pype" g.pype
        echo "== --units sequence_length";  "$BIN/hwut.pype" --units sequence_length
        echo "== --units genetic_distance"; "$BIN/hwut.pype" --units genetic_distance ;;
    link-bits)
        judged() {      # <law> <line printed>: blessed, or the refusal's reason
            page test-b.sh "tolerance { constraints = [\"$1\"] }" "echo \"$2\""
            rm -rf GOOD OUT
            "$BIN/hwut.play" test-b.sh --plain > /dev/null 2>&1
            printf '%-14s over %-28s : ' "$1" "$2"
            "$BIN/hwut.accept" test-b.sh > o.txt 2>&1 && echo "blessed" \
                || grep -m1 '^    constraint ' o.txt \
                   | sed -E 's/.*, line [0-9]+ -- (.*)$/refused: \1/; t; s/.*/refused: broken/'
        }
        judged "r >= 10 MB/s"  "throughput ((r: 100 Mb/s))"
        judged "r >= 20 MB/s"  "throughput ((r: 100 Mb/s))"
        judged "r == 1000 Mb/s" "link ((r: 1 Gb/s))"
        judged "n < 1 kB"      "frame ((n: 6 kb))"
        judged "n < 1 kB"      "frame ((n: 9 kb))"
        echo "== pype: what a line binds"
        printf '%s\n' 'on: <r = quantity(MB/s)> => { print("rate", r) }' \
               'on: <n = quantity(data)> => { print("data", n) }' \
               'on: <else> => { print("other:", pype.line()) }' 'on: <eof> => ignore;' > b.pype
        printf '100 Mb/s\n1 Gb/s\n64 kb/s\n3 kb\n2 Mbit\n' | "$BIN/hwut.pype" b.pype ;;
    *)
        echo "unknown choice '$1'"; exit 1 ;;
esac
echo "<hwut-end>"
