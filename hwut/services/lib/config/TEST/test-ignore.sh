#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "hwut.config.ignore: the answer to the wallflower NOTE."
#     choices {
#         paths       { features = ["ignore-named-paths"] }
#         wishlist    { features = ["ignore-from-wishlist"] }
#         wallflowers { features = ["settle-wallflowers"] }
#         reported    { features = ["report-feeds-ignore"] }
#         refused     { features = ["ignore-refusals"] }
#         refused_too { features = ["refused-file-is-wallflower"] }
#         no_default  { features = ["settle-wallflowers"] }
#         anchored    { features = ["settle-wallflowers"] }
#         selection   { features = ["settle-wallflowers"] }
#         pype_named  { features = ["settle-wallflowers"] }
#     }
# }
#
# ---------------------------------------------------------------------------
#
# 'hwut.config.ignore' writes a helper's name into its directory's
# 'hwut.conf' under 'ignore', and touches nothing else (E-48). A run
# leaves a WALLFLOWER LIST in every explored directory holding files no
# carrier speaks for ('TMP/wallflowers.txt', X-SILENT); this face reads
# such a list, or every one below it.
#
# paths        paths as typed, grouped by directory; a name already
#              ignored is not written twice.
# wishlist     '--wishlist <list>': the list's '#' header dropped, its
#              './' read as the list's own directory -- from wherever
#              the face is called.
# wallflowers  a run writes the lists; '--wallflowers' ignores them all,
#              removes each list, and the next run finds nothing.
# reported     'hwut.report.wallflowers' prints them, one path per line,
#              and its output IS this face's input; then it finds none.
# refused_too  (exploration R-103, 2026-11-22) a backup-shaped file is a
#              WALLFLOWER, its header unread -- the '.bak' copy of a test
#              is no second test. MEASURED BEFORE: it was ignored, silent
#              (services E-159); without the unread header it ran as a
#              test, 'no GOOD file'.
# no_default   (exploration R-102, 2026-11-22) nothing is ignored by
#              default: a '.txt', a '.json', a '.pype', a README are
#              wallflowers like any helper. MEASURED BEFORE: the four were
#              silent, the list named only 'helper.py' and 'bench.log'.
# anchored     (R-103) 'ignore' is local like '.gitignore' and inherited:
#              a name in the root conf holds in every directory below; a
#              glob with '/' is anchored at its conf's directory.
#              MEASURED BEFORE: 'b/TEST/data.csv' in the root conf matched
#              nothing -- names were matched bare.
# selection    (R-103) the NOTE's two lines: 'hwut.sanitize.propose
#              --wallflowers -o <file>' lists them, one line each; a line
#              deleted stays a wallflower; 'hwut.sanitize.apply <file>'
#              ignores the rest in each directory's own 'hwut.conf'.
# pype_named   (R-104, ruled 2026-11-22) a file the 'pype' value reads is
#              no wallflower: the scripts its words name -- a system, the
#              command form --, a system's scripts, every 'import:'
#              transitively, also through '--pype-dir'. A '.pype' no value
#              names stays one. Then pype's own parse, held equal to the
#              exploration's reading ('pype_reference.file_set').
#              MEASURED BEFORE: all five '.pype'/'.pypes' were wallflowers.
# refused      a path that stands nowhere; an unknown option;
#              '--wishlist' without a file; a list that is not there.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../../../.." && pwd)
export PYTHONPATH="$ROOT"
IGNORE="python3 -m hwut.services.lib.config.ignore"
REPORT="python3 -m hwut.services.lib.report.wallflowers"
RUN="python3 -m hwut.services.run"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "hwut.config.ignore: the answer to the wallflower NOTE.;"
        echo "CHOICES: paths, wishlist, wallflowers, reported, refused, refused_too, no_default, anchored, selection, pype_named;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
mkdir -p HWUT_ROOT
printf 'hwut {\n}\n' > HWUT_ROOT/setup.conf

face() {                # <args...> -- status, stdout, stderr
    $IGNORE "$@" > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "STDOUT {"; sed "s|$WORK|\$WORK|g; s/^/    /" < out.txt; echo "}"
    if [ -s err.txt ]; then
        echo "STDERR {"; sed "s|$WORK|\$WORK|g; s/^/    /" < err.txt; echo "}"
    fi
}
fixture() {             # two test directories, one test and two helpers each
    for where in a b; do
        mkdir -p "$where/TEST/GOOD"
        printf '#!/bin/bash\n# @hwut { title = "T" }\necho x\necho "<hwut-end>"\n' \
            > "$where/TEST/test-x.sh"
        chmod +x "$where/TEST/test-x.sh"
        printf 'x\n<hwut-end>\n' > "$where/TEST/GOOD/test-x.sh.txt"
        echo helper > "$where/TEST/helper.py"
        echo log    > "$where/TEST/bench.log"
    done
}
conf() {                # <dir> -- the directory's hwut.conf, or its absence
    echo "$1/hwut.conf {"
    if [ -f "$1/hwut.conf" ]; then sed 's/^/    /' < "$1/hwut.conf"
    else echo "    (none)"; fi
    echo "}"
}
# ---------------------------------------------------------------------------
case "$1" in
paths)
    fixture
    echo "--- two paths, two directories"
    face a/TEST/helper.py b/TEST/bench.log --dont-ask
    conf a/TEST; conf b/TEST
    echo "--- again, with one name already ignored"
    face a/TEST/helper.py a/TEST/bench.log --dont-ask
    conf a/TEST
    ;;
wishlist)
    fixture
    $RUN --plain > run.txt 2>&1
    echo "--- the list a run wrote"
    sed 's/^/    /' < a/TEST/TMP/wallflowers.txt
    echo "--- read from its own test directory"
    ( cd a/TEST && face --wishlist TMP/wallflowers.txt --dont-ask )
    conf a/TEST
    echo "--- read from the root: './' is the list's own directory"
    face --wishlist b/TEST/TMP/wallflowers.txt --dont-ask
    conf b/TEST
    ;;
refused_too)
    fixture
    #  A REFUSED FILE IS A WALLFLOWER TOO (X-SILENT, amended): a
    #  backup-shaped name stands in the REFUSED block by name AND in
    #  the wallflower list, where this face settles it with the rest.
    cp a/TEST/test-x.sh a/TEST/test-x.sh.bak
    $RUN --plain > run.txt 2>&1
    echo "--- the REFUSED block names it, under its reason"
    sed -n '/^REFUSED -- not run/,/^====/p' run.txt \
        | grep "bak\|backup-shaped" | sed 's/^/    /'
    echo "--- and the NOTE counts it"
    grep "wallflower" run.txt | sed 's/^/    /'
    echo "--- the list holds it"
    grep -v '^#' a/TEST/TMP/wallflowers.txt | sed 's/^/    /'
    echo "--- settled with the rest"
    face --wallflowers --dont-ask
    conf a/TEST
    echo "--- run again: $($RUN --plain 2>&1 | grep -c 'REFUSED\|wallflower') REFUSED or NOTE line(s)"
    ;;
wallflowers)
    fixture
    $RUN --plain > run.txt 2>&1
    echo "--- the run's NOTE"
    grep "wallflower" run.txt | sed 's/^/    /'
    echo "--- every list below here"
    face --wallflowers --dont-ask
    conf a/TEST; conf b/TEST
    echo "--- the lists are gone: $(find . -name wallflowers.txt | wc -l)"
    echo "--- run again: $(  $RUN --plain 2>&1 | grep -c wallflower) NOTE line(s)"
    echo "--- and nothing left to settle"
    face --wallflowers --dont-ask
    ;;
reported)
    fixture
    echo "--- the wallflowers, as the report finds them"
    $REPORT > found.txt; echo "STATUS: $?"; sed 's/^/    /' < found.txt
    echo "--- piped into the face that settles them"
    face $(cat found.txt) --dont-ask
    conf a/TEST
    echo "--- none left"
    $REPORT > found.txt; echo "STATUS: $?"; sed 's/^/    /' < found.txt
    echo "--- a wish word is not its business"
    $REPORT --fail; echo "STATUS: $?"
    ;;
no_default)
    fixture
    for name in samples.txt notes.json strip.pype README.txt; do
        echo data > "a/TEST/$name"
    done
    $RUN --plain > run.txt 2>&1
    echo "--- the run's NOTE"
    grep "wallflower" run.txt | sed 's/^/    /'
    echo "--- a/TEST's list"
    grep -v '^#' a/TEST/TMP/wallflowers.txt | sed 's/^/    /'
    ;;
anchored)
    fixture
    for where in a b; do echo d > "$where/TEST/data.csv"; done
    printf 'hwut {\n    ignore = ["*.log", "b/TEST/data.csv"]\n}\n' \
        > HWUT_ROOT/setup.conf
    $RUN --plain > run.txt 2>&1
    echo "--- a/TEST's list: 'bench.log' ignored by name, 'data.csv' not"
    grep -v '^#' a/TEST/TMP/wallflowers.txt | sed 's/^/    /'
    echo "--- b/TEST's list: both ignored"
    grep -v '^#' b/TEST/TMP/wallflowers.txt | sed 's/^/    /'
    ;;
selection)
    fixture
    PROPOSE="python3 -m hwut.services.lib.sanitize.propose"
    APPLY="python3 -m hwut.services.lib.sanitize.apply"
    $RUN --plain > run.txt 2>&1
    echo "--- the run's NOTE"
    grep -A2 "wallflower" run.txt | sed 's/^/    /'
    echo "--- listed, one line each"
    $PROPOSE --wallflowers -o w.txt; echo "STATUS: $?"
    grep '^ignore' w.txt | sed 's/^/    /'
    echo "--- the a/TEST lines deleted, the rest applied"
    sed -i '/ignore a\/TEST/d' w.txt
    $APPLY w.txt > out.txt 2>&1; echo "STATUS: $?"
    grep "ignore" out.txt | sed 's/ *\.\.\.*/ .../; s/^/    /'
    conf a/TEST
    conf b/TEST
    echo "--- what is left"
    $PROPOSE --wallflowers | grep '^ignore' | sed 's/^/    /'
    ;;
pype_named)
    mkdir -p a/TEST/GOOD lib
    printf '#!/bin/bash\n# @hwut {\n#     title = "T"\n#     choices { one { pype = "sys.pypes" }\n#               two { pype = "python3 -I pype.py --pype-dir ../../lib solo.pype" } }\n# }\necho x\n' \
        > a/TEST/test-x.sh
    chmod +x a/TEST/test-x.sh
    printf -- '--> one.pype\none.pype --> two.pype   # a system of two\n' > a/TEST/sys.pypes
    printf 'import: "lib.pype"\non: <else> => flush;\non: <eof> => ignore;\n' > a/TEST/one.pype
    printf 'on: <else> => flush;\non: <eof> => ignore;\n' > a/TEST/two.pype
    printf 'LIB/on: <eof> => ignore;\n' > a/TEST/lib.pype
    printf 'import: "far.pype"\non: <else> => flush;\non: <eof> => ignore;\n' > a/TEST/solo.pype
    printf 'FAR/on: <eof> => ignore;\n' > lib/far.pype
    echo stray > a/TEST/stray.pype
    $RUN --plain > run.txt 2>&1
    echo "--- the wallflowers: the one no value names"
    grep -v '^#' a/TEST/TMP/wallflowers.txt | sed 's/^/    /'
    echo "--- the exploration's reading equals pype's own parse"
    python3 - "$WORK" <<'PY'
import os, sys
from hwut.engine.orchestrator.exploration.pype_reference import file_set
from hwut.services.lib.pype import pype, pype_system
work = sys.argv[1]; d = os.path.join(work, "a", "TEST")
def own(script, search=()):
    source_db = {}
    pype.parse(open(script).read(), script, search_dir_list=list(search),
               source_db=source_db)
    return {os.path.abspath(f) for f in source_db}
system = pype_system.read(os.path.join(d, "sys.pypes"))
by_pype = {os.path.abspath(system.file_name)}
for path in system.path_db.values(): by_pype |= own(path)
for v, expected in (("sys.pypes", by_pype),
                    ("python3 -I pype.py --pype-dir ../../lib solo.pype",
                     own(os.path.join(d, "solo.pype"),
                         [os.path.join(work, "lib")]))):
    got = file_set(v, d)
    print("    %-50s %s  %s" % (v, "equal" if got == expected else "DIFFER",
          " ".join(sorted(os.path.relpath(p, work) for p in got))))
PY
    ;;
refused)
    fixture
    echo "--- a path that stands nowhere"
    face a/TEST/nothing.py --dont-ask
    echo "--- an unknown option"
    face --from a.txt
    echo "--- '--wishlist' without a file"
    face --wishlist
    echo "--- a list that is not there"
    face --wishlist gone.txt --dont-ask
    conf a/TEST
    ;;
esac
echo "<hwut-end>"
