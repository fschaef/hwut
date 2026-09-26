#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "hwut.config.ignore: the answer to the wallflower NOTE."
#     choices    = ["paths", "wishlist", "wallflowers", "reported", "refused"]
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
# refused      a path that stands nowhere; an unknown option;
#              '--wishlist' without a file; a list that is not there.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../../../.." && pwd)
export PYTHONPATH="$ROOT"
IGNORE="python3 -m vut.services.lib.config.ignore"
REPORT="python3 -m vut.services.lib.report.wallflowers"
RUN="python3 -m vut.services.run"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "hwut.config.ignore: the answer to the wallflower NOTE.;"
        echo "CHOICES: paths, wishlist, wallflowers, reported, refused;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
printf 'hwut {\n}\n' > hwut-root.conf

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
