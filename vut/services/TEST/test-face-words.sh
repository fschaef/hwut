#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title   = "A word typed at a face: what the ruling says, every face does."
#     choices = ["book", "boundary", "coverage_serial", "glob_silenced",
#                "label_unknown", "language_unknown", "propose",
#                "pype_call", "query_here", "shape", "strategy", "tiers",
#                "yes_gone"]
# }
#
# ---------------------------------------------------------------------------
#
# ONE PAGE THROUGH THE FACES (audit r10, TODO D-9) for words a person
# types on a command line. Each ruling below stood by name and by no
# page; the word is typed here, at EVERY face that takes it, and what
# the face answers is printed. Three of them were measured otherwise
# first (G-13, G-14) -- the parser held and a face did not.
#
# boundary          a tree without 'hwut-root.conf' (E-25, amended
#                   2026-10-08): every face refuses in one line and
#                   HINTS at 'hwut.sanitize root [dir]'. With no
#                   directory that command ASKS -- a menu of the
#                   repository's root, the current directory and 'q' --
#                   and where nobody can answer it refuses and says so.
#                   THE MENU IS SHOWN WITH THE TERMINAL STOOD IN FOR:
#                   the face's 'main' is handed the answers a person
#                   would type (a pipe cannot answer, and a pty is not
#                   a page's ground). 'hwut.sanitize.propose' writes
#                   the same candidates as commands, 'apply' writes the
#                   file, a face runs, and a second 'root' finds
#                   nothing to do. MEASURED BEFORE (G-12): one line, no
#                   way out named, and an offer no face called.
# book              'GOOD/book.csv' as a person finds it (bookkeeper):
#                   an empty 'test' cell is the row above's and ':' is
#                   an ordinary character in a name (B-8); a book under
#                   an old name is read and, at the first write, IS
#                   'book.csv' (B-10), written without the 'coverage'
#                   column it still carried (B-27); an acceptance that
#                   is refused takes no id -- the next test gets the
#                   number (B-4).
# tiers             '--plain' is the default and may be said (display
#                   D-4); VERBOSE, PLAIN, QUIET, SILENT each a subset of
#                   the one above, two together refused; SILENT is
#                   silent on stdout and says a fault on stderr (D-5).
# strategy          '--strategy=linear,<order>': 'longest-first' starts
#                   the directory whose LONGEST measured case is
#                   longest (run O-33), 'shortest-first' the other end,
#                   'name-sorted' the tree's own order; 'bundled' is a
#                   word of the option and the default is not it (O-31).
# coverage_serial   under 'hwut.cov.run' one test runs at a time in a
#                   directory, whatever '--jobs' says (coverage D-22):
#                   three choices that each note when they began and
#                   ended overlap under 'hwut.run --jobs=3' and never
#                   under the coverage run. WANTS the 'coverage' tool.
# label_unknown     '--label nosuch' (E-19): REFUSED BY NAME, exit 2, at
#                   every face that takes a wish. 'hwut.plan' died in a
#                   traceback, 'hwut.run.stability' said EMPTY, and
#                   'hwut.sanitize.propose' went on and proposed (G-13).
# language_unknown  '--language=cobol' (E-26, exploration R-75): the
#                   same law, the same three faces (G-13).
# glob_silenced     a glob whose every match the standard label 'meta'
#                   silences (E-21): a WARNING naming the remedy in
#                   every face. 'hwut.report', 'hwut.plan' and
#                   'hwut.run.stability' said nothing (G-14). A LITERAL
#                   target overrides the silence; a machine format on
#                   stdout carries no warning line.
# query_here        'hwut.labels.query' prints its targets FROM WHERE THE
#                   CALLER STANDS (ruled 2026-10-09, f-7), so the pipe
#                   its help names -- into '--wishlist' -- selects the
#                   same runs from the root and from a test directory
#                   (a run covers the tree BELOW where it stands: the
#                   lines leading out of it select nothing there).
#                   MEASURED before: root-relative lines; from a test
#                   directory the pipe selected nothing.
# yes_gone          '--yes' is REFUSED BY NAME wherever it once stood
#                   (E-66, E-68), with the word that replaced it.
# pype_call         a '.pype' runs under this Python whatever its
#                   she-bang or mode (E-28): the she-bang names an
#                   interpreter that does not exist, the file carries no
#                   execute bit, and the filter filters.
# shape             GREW, SHRANK, DIVERGED (E-29): the run books
#                   'differs' and no more; 'hwut.report' takes the shape
#                   from the files afterwards (E-31) and the machine
#                   formats carry it as the reason.
# propose           'hwut.accept.propose <n> -o <file>' (E-44): a
#                   replacement as a block with its own line numbers,
#                   the target under it; over the bound, one line on
#                   stdout and no target; 'hwut.accept.apply' blesses
#                   what the file still names, and nothing else.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "A word typed at a face.;"
        echo "CHOICES: book, boundary, coverage_serial, glob_silenced, label_unknown, language_unknown, propose, pype_call, query_here, shape, strategy, tiers, yes_gone;"
        exit 0 ;;
esac

#  THE FACES, AS 'bin/' NAMES THEM: a launcher is two lines over the
#  module, and the module is what a page may call from any directory.
face() {                # <launcher name> <argument>...
    local name=$1; shift
    case "$name" in
        hwut.run)              python3 -m vut.services.run "$@" ;;
        hwut.accept)           python3 -m vut.services.accept "$@" ;;
        hwut.accept.propose)   python3 -m vut.services.lib.accept.propose "$@" ;;
        hwut.accept.apply)     python3 -m vut.services.lib.accept.apply "$@" ;;
        hwut.plan)             python3 -m vut.services.plan "$@" ;;
        hwut.report)           python3 -m vut.services.report "$@" ;;
        hwut.report.list)      python3 -m vut.services.lib.report.list "$@" ;;
        hwut.report.details)   python3 -m vut.services.lib.report.details "$@" ;;
        hwut.run.stability)    python3 -m vut.services.lib.run.stability "$@" ;;
        hwut.run.play)         python3 -m vut.services.lib.run.play "$@" ;;
        hwut.run.diff)         python3 -m vut.services.lib.run.diff "$@" ;;
        hwut.cov.run)          python3 -m vut.services.lib.cov.run "$@" ;;
        hwut.sanitize.propose) python3 -m vut.services.lib.sanitize.propose "$@" ;;
        hwut.sanitize.apply)   python3 -m vut.services.lib.sanitize.apply "$@" ;;
        hwut.sanitize)         python3 -m vut.services.sanitize "$@" ;;
        hwut.config.show)      python3 -m vut.services.lib.config.show "$@" ;;
        hwut.labels.list)      python3 -m vut.services.lib.labels.list "$@" ;;
        hwut.labels.add)       python3 -m vut.services.lib.labels.add "$@" ;;
        hwut.labels.create)    python3 -m vut.services.lib.labels.create "$@" ;;
        hwut.labels.query)     python3 -m vut.services.lib.labels.query "$@" ;;
        hwut.rename)           python3 -m vut.services.rename "$@" ;;
        hwut.move)             python3 -m vut.services.move "$@" ;;
        hwut.remove)           python3 -m vut.services.remove "$@" ;;
    esac
}

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir "$WORK/TEST"
cd "$WORK/TEST"
printf 'hwut {\n    language-setup { bash { extensions = [".sh"] interpreter = "bash" } }\n}\n' \
       > ../hwut-root.conf

page() {                # <file> <header lines> <body line>
    printf '#! /bin/bash\n# @hwut {\n%b# }\n%s\necho "<hwut-end>"\n' "$2" "$3" > "$1"
    chmod +x "$1"
}
shown() { sed "s|$WORK|\$WORK|g"; }

#  ONE LINE PER FACE: what it said first, and how it left.
answered() {            # <launcher name> <argument>...
    local name=$1
    face "$@" < /dev/null > out.txt 2>&1
    local status=$?
    printf '%-22s exit %s  %s\n' "$name" "$status" \
           "$(grep -m1 "$PATTERN" out.txt | shown | cut -c1-76)"
}

labelled() {            # two tests accepted; 'test-m.sh' labelled 'meta'
    page test-a.sh '#     title   = "a"\n#     choices = ["one", "two"]\n' 'echo "a $1"'
    page test-m.sh '#     title   = "m"\n' 'echo "m"'
    face hwut.labels.add meta --glob "test-m.sh" > /dev/null
    face hwut.accept --whole --label all --dont-ask < /dev/null > /dev/null 2>&1
    face hwut.run --label all --silent < /dev/null > /dev/null 2>&1
}

WISH_FACES="hwut.run hwut.accept hwut.plan hwut.report hwut.report.list
            hwut.report.details hwut.run.stability hwut.run.diff
            hwut.sanitize.propose"

case "$1" in
    book)
        page 'a:b.sh' '#     title   = "colon"\n#     choices = ["one", "two"]\n' 'echo "c $1"'
        page t.sh '#     title = "t"\n' 'echo "t"'
        face hwut.accept --whole --dont-ask < /dev/null > /dev/null 2>&1
        echo "== the book"
        cat GOOD/book.csv
        echo "== under an old name, as that time wrote it: no ids, a 'coverage' column"
        grep -v "^#" GOOD/book.csv | cut -d';' -f1-4 \
            | sed '1s/$/;coverage/; 2,$s/$/;tok/' > GOOD/result_db.csv
        rm GOOD/book.csv
        cat GOOD/result_db.csv
        echo "== hwut.report reads it"
        face hwut.report --plain --width=60 2>&1 | grep "\[OK\]\|\[FAIL\]" | grep -v "^  *[0-9]"
        echo "== hwut.run writes: the name and the column"
        #  ONE JOB, THE TREE'S ORDER: the run REGISTERS what the old book
        #  never numbered, in the order the cases end -- two at a time,
        #  'two' may end first and take id 0.
        face hwut.run --silent --jobs=1 --deterministic < /dev/null > /dev/null 2>&1
        ls GOOD | grep "csv"
        sed -n '/^test;/,$p' GOOD/book.csv
        echo "== an acceptance refused takes no id"
        printf '#! /bin/bash\n# @hwut {\n#     title = "no token"\n# }\necho x\n' > u.sh
        chmod +x u.sh
        face hwut.accept u.sh --whole --dont-ask < /dev/null 2>&1 | grep -c "REFUSED" \
            | sed 's/^/    refused: /'
        page v.sh '#     title = "v"\n' 'echo "v"'
        face hwut.accept v.sh --whole --dont-ask < /dev/null > /dev/null 2>&1
        grep "^[tuv]\.sh" GOOD/book.csv ;;
    tiers)
        page test-a.sh '#     title   = "a"\n#     choices = ["one", "two"]\n' 'echo "a $1"'
        page test-b.sh '#     title = "b"\n' 'echo "b"'
        face hwut.accept --whole --dont-ask < /dev/null > /dev/null 2>&1
        printf 'DIFFERENT\n<hwut-end>\n' > GOOD/test-b.sh.txt
        R="--jobs=1 --deterministic --no-colour"
        for tier in "" "--plain" "--verbose" "--quiet" "--silent" \
                    "--plain --quiet" "--quiet --silent"; do
            face hwut.run $R $tier < /dev/null > out.txt 2> err.txt
            status=$?
            printf '%-18s exit %s  stdout %2s line(s)  flow %s  roll-call %s  stderr %s\n' \
                   "[$tier]" $status "$(grep -c . out.txt)" \
                   "$(grep -c '^START\|^END' out.txt)" \
                   "$(grep -c '^DIRECTORIES' out.txt)" "$(grep -c . err.txt)"
        done
        face hwut.run $R < /dev/null 2>&1 | sed 's/[0-9.]* \[sec\]/T/g' > bare.txt
        face hwut.run $R --plain < /dev/null 2>&1 | sed 's/[0-9.]* \[sec\]/T/g' > plain.txt
        diff bare.txt plain.txt > /dev/null && echo "bare is '--plain'"
        face hwut.run $R --plain --quiet < /dev/null 2>&1 | grep "REFUSED"
        echo "== a fault under '--silent'"
        printf 'hwut {\n    oops = 1\n}\n' > hwut.conf
        face hwut.run $R --silent < /dev/null > out.txt 2> err.txt
        echo "stdout $(grep -c . out.txt) line(s); stderr: $(cut -c1-60 err.txt)" ;;
    strategy)
        cd ..
        rm -rf TEST
        for name in quick slow mid; do
            mkdir -p $name/TEST
            case $name in quick) nap=0.05 ;; slow) nap=0.9 ;; mid) nap=0.4 ;; esac
            ( cd $name/TEST
              page test-$name.sh "#     title = \"$name\"\n" "sleep $nap; echo $name" )
        done
        face hwut.accept --whole --dont-ask < /dev/null > /dev/null 2>&1
        face hwut.run --silent < /dev/null > /dev/null 2>&1
        for words in "linear,longest-first" "linear,shortest-first" \
                     "linear,name-sorted" "bundled,longest-first" \
                     "linear,parallel" "nosuch"; do
            printf '%-24s ' "$words"
            face hwut.run --strategy=$words --jobs=1 --plain --no-colour < /dev/null 2>&1 \
                | grep "^DIR\|REFUSED" | sed 's/^DIR  *//; s/ *$//' | cut -c1-48 \
                | tr '\n' ' '
            echo
        done ;;
    coverage_serial)
        printf 'hwut {\n    language-setup { python { extensions = [".py"] interpreter = "python3" coverage = ["coverage"] } }\n}\n' \
               > ../hwut-root.conf
        printf 'def f(x):\n    if x > 0:\n        return "pos"\n    return "neg"\n' > unit.py
        cat > test-a.py <<'PAGE'
# @hwut {
#     title   = "a"
#     choices = ["neg", "pos", "third"]
# }
import sys, time, unit
began = time.time()
time.sleep(0.4)
open("log.txt", "a").write("%.3f %.3f\n" % (began, time.time()))
print(unit.f(1 if sys.argv[1] == "pos" else -1))
print("<hwut-end>")
PAGE
        face hwut.accept --whole --dont-ask < /dev/null > /dev/null 2>&1
        overlaps() {
            python3 -c "
span = sorted(tuple(map(float, line.split())) for line in open('log.txt'))
print(sum(1 for a, b in zip(span, span[1:]) if b[0] < a[1]) and 'overlap' or 'one at a time')"
        }
        rm -f log.txt
        face hwut.run --jobs=3 --silent < /dev/null > /dev/null 2>&1
        echo "hwut.run --jobs=3:      $(wc -l < log.txt) runs, $(overlaps)"
        rm -f log.txt
        face hwut.cov.run --dont-ask --jobs=3 --quiet --no-colour < /dev/null 2>&1 \
            | grep "^RESULTS" | sed 's/, [0-9.]* \[sec\].*//'
        echo "hwut.cov.run --jobs=3:  $(wc -l < log.txt) runs, $(overlaps)" ;;
    boundary)
        #  A PROJECT WITH ITS TOP MARKED, AND NO BOUNDARY: the one the
        #  other choices stand under is taken away.
        rm ../hwut-root.conf
        mkdir -p ../proj/sub/TEST ../proj/.git
        cd ../proj/sub/TEST
        page test-a.sh '#     title = "a"\n' 'echo "a"'
        for name in hwut.run hwut.accept hwut.plan hwut.report \
                    hwut.report.list hwut.run.stability hwut.labels.list; do
            echo "== $name"
            face $name < /dev/null 2>&1 | shown | cut -c1-100
            echo "STATUS: ${PIPESTATUS[0]}"
        done
        echo "== hwut.sanitize root -- nobody to answer"
        face hwut.sanitize root < /dev/null 2>&1 | shown
        echo "STATUS: ${PIPESTATUS[0]}"
        asked() {       # <answer>... -- 'main' with the answers scripted
            python3 - "$@" <<'PYTHON' 2>&1 | shown
import sys
from vut.services import sanitize
answer_list = sys.argv[1:]
def ask(prompt):
    """RETURN: str, the next scripted answer, echoed as a terminal echoes it."""
    if not answer_list: raise EOFError
    print("%s%s" % (prompt, answer_list[0]))
    return answer_list.pop(0)
print("STATUS: %d" % sanitize.main(["root"], ask=ask))
PYTHON
        }
        echo "== hwut.sanitize root -- a wrong answer, then 'q'"
        asked x q
        ls ../.. | sed 's/^/    stands: /'
        echo "== hwut.sanitize.propose -o proposal.txt"
        face hwut.sanitize.propose -o proposal.txt 2>&1 | shown
        echo "STATUS: ${PIPESTATUS[0]}"
        sed -n '/NO BOUNDARY/,$p' proposal.txt | sed 's/^/    /'
        echo "== hwut.sanitize.apply proposal.txt"
        face hwut.sanitize.apply proposal.txt 2>&1 | shown | grep "root\|Done"
        echo "    written: $(cd ../.. && ls hwut-root.conf), $(grep -c extensions ../../hwut-root.conf) 'extensions' lines"
        echo "== a face, now"
        face hwut.report.list < /dev/null 2>&1 | shown
        echo "STATUS: ${PIPESTATUS[0]}"
        echo "== hwut.sanitize root . -- a boundary stands above"
        face hwut.sanitize root . 2>&1 | shown
        echo "STATUS: ${PIPESTATUS[0]}"
        echo "== hwut.sanitize root -- asks nothing where one stands"
        face hwut.sanitize root < /dev/null 2>&1 | shown
        echo "STATUS: ${PIPESTATUS[0]}"
        echo "== hwut.sanitize root -- no repository above: [1] the current directory"
        mkdir -p "$WORK/plain/TEST"
        cd "$WORK/plain/TEST"
        asked 1
        ls | sed 's/^/    stands: /'
        echo "== hwut.sanitize root nosuch"
        face hwut.sanitize root nosuch 2>&1 | shown
        echo "STATUS: ${PIPESTATUS[0]}" ;;
    query_here)
        page test-a.sh '#     title   = "a"\n#     choices = ["one", "two"]\n' 'echo "a $1"'
        mkdir -p ../other/TEST
        cp test-a.sh ../other/TEST/test-b.sh
        ( cd .. && face hwut.accept --whole < /dev/null > /dev/null 2>&1 )
        face hwut.labels.create nightly --glob 'test-*' --directory=.. > /dev/null
        for where in "$WORK/TEST" "$WORK" "$WORK/other/TEST"; do
            cd "$where"
            echo "== in ${where#$WORK/}" | sed "s|$WORK|the root|"
            face hwut.labels.query nightly --expand --directory="$WORK" | sed 's/^/   /'
            face hwut.labels.query nightly --directory="$WORK" > "$WORK/wish.txt"
            face hwut.run --wishlist "$WORK/wish.txt" --brief --plain < /dev/null 2>&1 \
                | grep "^RESULTS" | sed 's/,[^,]*sec.*//; s/^/   /'
        done ;;
    label_unknown)
        labelled
        PATTERN="REFUSED\|Traceback\|EMPTY"
        for name in $WISH_FACES; do answered $name --label nosuch; done
        answered hwut.cov.run --dont-ask --label nosuch ;;
    language_unknown)
        labelled
        PATTERN="REFUSED\|Traceback\|EMPTY"
        for name in $WISH_FACES; do answered $name --language=cobol; done
        answered hwut.cov.run --dont-ask --language=cobol ;;
    glob_silenced)
        labelled
        PATTERN="^WARNING"
        for name in hwut.run hwut.accept hwut.plan hwut.report \
                    hwut.report.list hwut.run.stability; do
            answered $name --glob "test-m*"
        done
        echo "== a literal target overrides the silence"
        face hwut.report.list test-m.sh 2>&1 | shown
        echo "== the page that holds a case says it after its tail"
        face hwut.report --glob "test-m*" --glob "test-a.sh one" --plain --width=60 2>&1 \
            | grep "\[OK\]\|^WARNING\|^RESULTS" | cut -c1-76
        echo "== a machine format on stdout carries no warning line"
        face hwut.report --glob "test-m*" --glob "test-a.sh one" --format=tap 2>&1 ;;
    yes_gone)
        page test-a.sh '#     title = "a"\n' 'echo "a"'
        PATTERN="REFUSED"
        answered hwut.accept --yes
        answered hwut.run.diff --yes
        answered hwut.rename test-a.sh -to test-b.sh --yes
        answered hwut.move test-a.sh test-b.sh --yes
        answered hwut.remove test-a.sh --yes ;;
    pype_call)
        page test-p.sh '#     title = "pype"\n#     pype  = "keep.pype"\n' \
             'echo "l1 x"; echo "l2"; echo "l3 x"'
        printf '#! /usr/bin/env no-such-interpreter\non: "x" => flush;\non: <else> => ignore;\n' \
               > keep.pype
        chmod -x keep.pype
        echo "she-bang: $(head -1 keep.pype)"
        echo "execute bit: $([ -x keep.pype ] && echo set || echo none)"
        echo "== hwut.run.play test-p.sh --pyped"
        face hwut.run.play test-p.sh --pyped --plain 2>&1 | shown \
            | grep "l[0-9]\|FAULT\|EMPTY\|Traceback"
        echo "STATUS: ${PIPESTATUS[0]}" ;;
    shape)
        page test-g.sh \
             '#     title   = "shapes"\n#     choices = ["diverged", "grew", "same", "shrank"]\n' \
             'case $1 in grew) echo a; echo NEW; echo b;; shrank) echo a;; diverged) echo a; echo X;; same) echo a; echo b;; esac'
        mkdir GOOD
        for choice in diverged grew same shrank; do
            printf 'a\nb\n<hwut-end>\n' > GOOD/test-g.sh--$choice.txt
        done
        face hwut.run --silent < /dev/null > /dev/null 2>&1
        echo "== the book: the run says 'differs', and no more"
        cut -d';' -f1-4 GOOD/book.csv | tail -n +2
        echo "== hwut.report --format=tap: the shape is the reason"
        face hwut.report --format=tap 2>&1 | grep "^not ok\|^ok\|reason:"
        echo "== hwut.report: no word beside a plain difference (display D-31)"
        face hwut.report --plain --width=60 2>&1 | grep "\[OK\]\|\[FAIL\]" | grep -v "^  *[0-9]" ;;
    propose)
        page test-a.sh '#     title   = "a"\n#     choices = ["one", "two"]\n' \
             'echo "first  line"; echo "second $1"; echo "third"'
        face hwut.accept --whole --dont-ask < /dev/null > /dev/null 2>&1
        page test-a.sh '#     title   = "a"\n#     choices = ["one", "two"]\n' \
             'echo "first  line"; echo "SECOND  $1"; echo "third"'
        face hwut.run --silent < /dev/null > /dev/null 2>&1
        echo "== hwut.accept.propose 5 -o proposal.txt"
        face hwut.accept.propose 5 -o proposal.txt 2>&1 | shown
        echo "STATUS: ${PIPESTATUS[0]}"
        sed 's/^/    /' proposal.txt
        echo "== the nominals stand untouched"
        grep -h "second" GOOD/test-a.sh--*.txt | sed 's/^/    /'
        echo "== one target vetoed, the file handed back"
        sed -i 's|^\./test-a.sh two$|# ./test-a.sh two|' proposal.txt
        face hwut.accept.apply proposal.txt 2>&1 | shown | grep "DONE\|ERROR\|Accepted"
        grep -h "second\|SECOND" GOOD/test-a.sh--*.txt | sed 's/^/    /'
        echo "== hwut.accept.propose 0 -o over.txt: over the bound"
        face hwut.accept.propose 0 -o over.txt 2>&1 | shown
        echo "STATUS: ${PIPESTATUS[0]}"
        grep -c "^\./" over.txt | sed 's/^/    targets in the file: /' ;;
    *)
        echo "no such choice: $1"
        exit 1 ;;
esac
echo "<hwut-end>"
