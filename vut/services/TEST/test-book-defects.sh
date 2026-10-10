#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title   = "Defects found by a reader: each one, on the road the reader took."
#     choices = ["affected", "constraint-name", "coverage-ground",
#                "frame-side", "refused-band", "table-sep", "test-directory"]
# }
#
# ---------------------------------------------------------------------------
#
# THE DEFECT REPORT OF 2026-10-10 (measured on fc3c1b6), ONE CHOICE PER
# DEFECT, each driven the way the reader drove it: a small tree, the
# faces called by their launchers.
#
# frame-side       a broken region frame names THE SIDE AT FAULT: in the
#                  output it is 'EXECUTION ... in output', in GOOD it is
#                  'NOMINAL'. 'hwut.run.diff' says it in one FAULT line
#                  with file and line, exit 1 -- no traceback.
# constraint-name  a constraint over a variable named like a function
#                  of the namespace ('min > 5') is REFUSED where the
#                  header is read; it used to be filed under no
#                  variable and never checked.
# table-sep        'sep=' of a table is the GOOD file's: an output that
#                  opens '##! table' with no 'sep', or another one, is
#                  split by the nominal's.
# test-directory   'test_directory = "checks"': the same result standing
#                  above the directory and standing in it.
# refused-band     a refused backup-shaped file stands under the band
#                  of ITS directory.
# affected         'hwut.affected' after a real 'hwut.cov.run': the runs
#                  that executed a changed line, as wishlist lines that
#                  'hwut.run --wishlist' takes; an empty directory is
#                  refused by name, never answered 'NONE'.
# coverage-ground  the output of 'hwut.cov.run' MIRRORS the tree, its
#                  'TEST' directories with it: no walk enters it --
#                  under the default name, under a name '-o' gave, and
#                  when called inside it (exploration R-85). What keeps
#                  a walk out is the EMPTY 'hwut.no-entry-here.marker';
#                  a person's own directory carrying it is passed over
#                  alike, and so are a test directory's 'TMP' and 'OUT'.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
BIN=$(cd "$HERE/../../bin" && pwd)
export PATH="$BIN:$PATH"
unset NO_COLOR CI COLUMNS
RUN="hwut.run --jobs=1 --deterministic --no-colour --plain"

case "$1" in
    --hwut-info)
        echo "Defects found by a reader: each one, on the road the reader took.;"
        echo "CHOICES: frame-side, constraint-name, table-sep, test-directory, refused-band, affected, coverage-ground;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
printf 'hwut {\n}\n' > hwut-root.conf

page() {            # <path> <choices block> ; body on stdin
    mkdir -p "$(dirname "$1")"
    { printf '#! /usr/bin/env python3\n#\n# @hwut {\n#     title   = "t"\n'
      printf '#     choices { %s }\n# }\n#\n' "$2"
      cat; printf 'print("<hwut-end>")\n'; } > "$1"
    chmod +x "$1"
}
#  The flow without what the machine chose: timings.
flow() { grep -v '^RESULTS:' | sed 's/, [0-9:]*$//'; }
said() { "$@" 2>&1; echo "exit $?"; }

case "$1" in

frame-side)
    page a/TEST/test-t.py 'table { }' <<'EOF'
import os
print("##! %s" % os.environ.get("H", "table"))
print("a  1")
print("####")
EOF
    cd a/TEST
    hwut.accept --force test-t.py table > /dev/null 2>&1
    echo "--- the OUTPUT opens '##! tabel'; GOOD is intact"
    H=tabel $RUN | flow
    echo "--- hwut.run.diff"
    H=tabel said hwut.run.diff test-t.py table < /dev/null
    echo "--- GOOD opens '##! tabel'; the output is intact"
    $RUN > /dev/null 2>&1
    chmod u+w GOOD/*.txt
    sed -i 's/##! table/##! tabel/' GOOD/test-t.py--table.txt
    $RUN | flow
    echo "--- hwut.run.diff"
    said hwut.run.diff test-t.py table < /dev/null
    ;;

constraint-name)
    page a/TEST/test-c.py \
         'fn { tolerance { constraints = ["min > 5"] } }  var { tolerance { constraints = ["k > 5"] } }' <<'EOF'
import sys
print("v ((%s: 1))" % ("min" if sys.argv[1] == "fn" else "k"))
EOF
    cd a/TEST
    $RUN | flow
    ;;

table-sep)
    page a/TEST/test-s.py 'run { }' <<'EOF'
import os
print("##! table%s" % os.environ.get("SEP", " sep={;}"))
print("a;1")
print("b;2")
print("####")
EOF
    cd a/TEST
    hwut.accept --force test-s.py run > /dev/null 2>&1
    echo "--- the output opens '##! table', no 'sep'"
    SEP= $RUN | grep -E '^(END|SKIP)'
    echo "--- the output opens '##! table sep={,}'"
    SEP=" sep={,}" $RUN | grep -E '^(END|SKIP)'
    echo "--- a row differs: still a failure"
    sed -i 's/b;2/b;3/' test-s.py
    SEP= $RUN | grep -E '^(END|SKIP)'
    ;;

test-directory)
    mkdir -p lib
    printf 'hwut {\n    test_directory = "checks"\n}\n' > lib/hwut.conf
    page lib/alpha/checks/test-x.py 'one { }' <<'EOF'
print("hello")
EOF
    echo "--- standing in 'lib/alpha/checks'"
    ( cd lib/alpha/checks
      hwut.accept --force test-x.py one 2>&1 | grep -E 'ACCEPTED|blessed|NOTE'
      $RUN | grep -E '^(DIR |END|SKIP|NOTE)|no directory' )
    echo "--- standing at the root"
    $RUN | grep -E '^(DIR |END|SKIP|NOTE)|no directory'
    ;;

coverage-ground)
    cp "$BIN/../hwut-root.conf" hwut-root.conf
    page a/TEST/test-m.py 'one { }' <<'EOF'
print("hello")
EOF
    ( cd a/TEST; hwut.accept --force test-m.py one > /dev/null 2>&1 )
    hwut.cov.run --dont-ask --plain --jobs=1 > /dev/null 2>&1
    hwut.cov.run -o measured --dont-ask --plain --jobs=1 > /dev/null 2>&1
    echo "--- the outputs mirror the tree"
    find hwut.coverage measured -type d -name TEST | sort
    echo "--- hwut.run at the root"
    $RUN | grep -E '^(DIR |END|SKIP|NOTE)|no directory|TEST \\.'
    echo "--- hwut.report.list at the root"
    hwut.report.list
    echo "--- hwut.run inside the mirror"
    ( cd hwut.coverage/a/TEST; $RUN | grep -E '^(DIR |END|SKIP|NOTE)|no directory' )
    echo "--- nothing was made there"
    find hwut.coverage measured -name TMP -o -name OUT -o -name GOOD | sort
    echo "--- the marker that keeps a walk out: empty"
    for d in hwut.coverage measured; do
        echo "$d/hwut.no-entry-here.marker: $(wc -c < $d/hwut.no-entry-here.marker) byte(s)"
    done
    echo "--- a person's own directory, entered; then marked"
    page vendor/lib/TEST/test-v.py 'one { }' <<'EOF'
print("vendor")
EOF
    hwut.report.list
    : > vendor/hwut.no-entry-here.marker
    echo "marked:"
    hwut.report.list
    echo "--- 'TMP' and 'OUT' of a test directory: a tree left there is not entered"
    mkdir -p a/TEST/TMP/left/TEST a/TEST/OUT/left/TEST
    cp a/TEST/test-m.py a/TEST/TMP/left/TEST/
    cp a/TEST/test-m.py a/TEST/OUT/left/TEST/
    printf 'hwut {\n    target { say = "./say.sh" }\n}\n' > a/TEST/hwut.conf
    printf '#! /bin/sh\necho "said here"\n' > a/TEST/say.sh; chmod +x a/TEST/say.sh
    for d in a/TEST/TMP/left/TEST a/TEST/OUT/left/TEST; do
        cp a/TEST/hwut.conf a/TEST/say.sh $d/
    done
    echo "hwut.execute say: said $(hwut.execute say 2>&1 | grep -c 'said here') time(s)"
    ;;

refused-band)
    for d in most router; do
        page $d/TEST/test-r.py 'one { }' <<'EOF'
print("hello")
EOF
        ( cd $d/TEST; hwut.accept --force test-r.py one > /dev/null 2>&1 )
    done
    cp router/TEST/test-r.py router/TEST/test-r.py.orig
    $RUN | grep -E '^(DIR |START|END|DONE)'
    ;;

affected)
    cat > a_TEST_body <<'EOF'
import sys
def one():
    print("one")
def two():
    print("two")
def both():
    print("both")
both()
if sys.argv[1] == "first": one()
else:                      two()
EOF
    #  THE TREE'S OWN ROOT CONF: it names the coverage tool of python.
    cp "$BIN/../hwut-root.conf" hwut-root.conf
    page a/TEST/test-m.py 'first { }  second { }' < a_TEST_body
    rm a_TEST_body
    cd a/TEST
    hwut.accept --force test-m.py first  > /dev/null 2>&1
    hwut.accept --force test-m.py second > /dev/null 2>&1
    echo "--- hwut.cov.run"
    hwut.cov.run --dont-ask --plain --jobs=1 2>&1 | grep -E 'rec\]|^COVERAGE DATA' \
        | sed 's|: .*hwut.coverage|: <dir>/hwut.coverage|'
    #  The lines of 'one', 'two' and 'both' in the page, by content.
    line_of() { grep -n "print(\"$1\")" test-m.py | cut -d: -f1; }
    change() { printf -- '--- a/test-m.py\n+++ b/test-m.py\n@@ -%s,1 +%s,1 @@\n-x\n+y\n' "$1" "$1"; }
    echo "--- a change in 'one': the first run alone"
    change "$(line_of one)"  | said hwut.affected --bare 2> /dev/null
    echo "--- a change in 'both': both runs, framed"
    change "$(line_of both)" | said hwut.affected
    echo "--- a change in a line nobody executes"
    change 2 | said hwut.affected --bare 2> /dev/null
    echo "--- the answer is a wishlist"
    change "$(line_of two)" | hwut.affected --bare > w.txt 2> /dev/null
    $RUN --wishlist w.txt | grep -E '^(START|END|      :)'
    rm w.txt
    echo "--- a directory that holds no coverage: refused by name"
    mkdir empty
    change 2 | said hwut.affected --cov-dir empty
    ;;

*)
    echo "no such choice: $1" >&2
    exit 1 ;;
esac
echo "<hwut-end>"
