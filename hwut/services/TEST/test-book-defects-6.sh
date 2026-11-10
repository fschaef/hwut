#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title    = "The author's run of 2026-11-04: what '--dir' did, and what a silent run wrote"
#     features = ["book-defects-round-3"]
#     choices  = ["dir-slash", "dir-walked", "silent-events"]
# }
#
# ---------------------------------------------------------------------------
#
# MEASURED BY THE AUTHOR on his own machine, 2026-11-04, running
# 'hwut -p linux --dir <one port>/TEST/' -- a test directory of the test
# writing support, named with the slash the shell's completion writes
# (the path itself is not spelled here: a file of hwut outside the
# support may not name a departing port, adm/support_layout.py). The run
# did nothing, said 'the selection is empty' of 128 directories it was
# never asked about, and reported two errors of the platform's. Three of
# the four
# findings are here; the fourth -- a far run whose wish selects nothing is
# no fault -- is 'engine/orchestrator/run/TEST test-bubble.py far-empty'.
#
# dir-slash       A TRAILING '/' IS PUNCTUATION, NOT A LEVEL: the shell's
#                 completion writes '--dir a/TEST/', and '--dir a/TEST'
#                 and '--dir a/TEST/' select the same; so do
#                 '--exclude-dir b/' and the bare name 'TEST/'. MEASURED
#                 before: the empty level behind the slash matched no
#                 directory -- 0 ok, everything skipped.
# dir-walked      WHAT THE WISH NEVER ASKED ABOUT IS NOT EXPLORED: with
#                 '--dir a/TEST' nothing of 'b/' is interviewed, no case
#                 of it is named and no directory says 'the selection is
#                 empty'. MEASURED before: every directory explored, its
#                 applications interviewed, and one NOTE each.
#                 A CONF THAT CANNOT BE READ IS THE TREE'S FAULT, NOT THE
#                 SELECTION'S: the descent folds every level it passes,
#                 so 'b/hwut.conf' is named and the run ends 1 whatever
#                 the wish -- where the wish asks for 'b/TEST' the conf
#                 fails its cases besides (E-190).
# silent-events   A SILENT RUN'S STDOUT CARRIES EVENTS AND NOTHING ELSE
#                 (display D-5): the feature hint is written under
#                 '--plain' and not under '--silent'. MEASURED before:
#                 the hint reached the far run's event channel
#                 ('--events /dev/stdout'), and the near run read it as a
#                 fault of the platform's.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
BIN="$ROOT/hwut/bin"
export PATH="$BIN:$PATH"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "The author's run of 2026-11-04: '--dir' and a silent run's stdout;"
        echo "CHOICES: dir-slash, dir-walked, silent-events;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
printf 'hwut {\n    language-setup { bash { extensions = [".sh"] interpreter = "bash" } }\n}\n' \
       > hwut-root.conf
shown() {
    sed -E "s|$WORK|\$WORK|g; s/[0-9]+\.[0-9]+ \[sec\]/<t> [sec]/g;
            s/, [0-9:]+$/, <t>/; s/ +\|\|[0-9]+$//"
}
page() {                # <file> <header> <body lines...>
    local file=$1 header=$2; shift 2
    { echo '#! /bin/bash'; echo "# @hwut { $header }"; printf '%s\n' "$@"
      echo 'echo "<hwut-end>"'; } > $file
    chmod +x $file
}
tree() {                # 'a/TEST' and 'b/TEST', each one green case
    local d
    for d in a b; do
        mkdir -p "$WORK/$d/TEST"
        page "$WORK/$d/TEST/test-t.sh" 'choices = ["x"]' 'echo "$1"'
    done
    ( cd "$WORK/a/TEST" && "$BIN/hwut.play" --all --plain > /dev/null 2>&1 \
                        && "$BIN/hwut.accept" > /dev/null 2>&1 )
    ( cd "$WORK/b/TEST" && "$BIN/hwut.play" --all --plain > /dev/null 2>&1 \
                        && "$BIN/hwut.accept" > /dev/null 2>&1 )
}
ran() {                 # <title> <args...>: the RESULTS of a run, and its status
    local title=$1; shift
    echo "== $title"
    "$BIN/hwut.run" --plain "$@" 2>&1 | grep -E "^RESULTS" | shown \
        | sed -E 's/, <t> \[sec\].*//; s/^/    /'
    "$BIN/hwut.run" --silent "$@" > /dev/null 2>&1
    echo "    exit $?"
}

case "$1" in
    dir-slash)
        tree
        cd "$WORK"
        ran "--dir a/TEST"                  --dir a/TEST
        ran "--dir a/TEST/  (the shell's completion)" --dir a/TEST/
        ran "--dir TEST/    (a bare name)"  --dir TEST/
        ran "--exclude-dir b"               --exclude-dir b
        ran "--exclude-dir b/"              --exclude-dir b/
        ran "--dir a/TEST/ --exclude-dir a/" --dir a/TEST/ --exclude-dir a/ ;;
    dir-walked)
        tree
        #  'b/hwut.conf' CANNOT BE READ (E-190): it fails 'b/TEST' where
        #  the walk reads it, and is never read where the wish does not ask.
        printf 'hwut {\n    caps { timeout_sec = }\n}\n' > "$WORK/b/hwut.conf"
        cd "$WORK"
        said() {        # <title> <args...>: what the run says of either
            local title=$1; shift
            echo "== hwut.run $title"
            "$BIN/hwut.run" --plain "$@" 2>&1 \
                | grep -E "^ERROR|FAIL\]|^NOTE|^RESULTS|no directory ran" \
                | shown | sed -E 's/, <t> \[sec\].*//; s/^/    /'
            "$BIN/hwut.run" --silent "$@" > /dev/null 2>&1
            echo "    exit $?"
        }
        said "(the whole tree): 'b/' is read, and fails its case"
        said "--dir a/TEST: nothing of 'b/' is explored" --dir a/TEST
        said "--dir nowhere/TEST: nothing is explored" --dir nowhere/TEST
        rm "$WORK/b/hwut.conf"
        said "--dir nowhere/TEST, the conf mended: EMPTY" --dir nowhere/TEST ;;
    silent-events)
        mkdir -p "$WORK/a/TEST"
        page "$WORK/a/TEST/test-t.sh" 'choices = ["x"] features = ["one"]' 'echo "$1"'
        ( cd "$WORK/a/TEST" && "$BIN/hwut.play" --all --plain > /dev/null 2>&1 \
                            && "$BIN/hwut.accept" > /dev/null 2>&1 )
        cd "$WORK"
        #  THE FOREST STANDS AND KNOWS NOTHING OF 'one': the hint is due.
        : > hwut-feature-forest.csv
        echo "== hwut.run --plain: the hint stands on stdout"
        "$BIN/hwut.run" --plain 2>&1 | grep -E "link\(s\) to no feature" | shown \
            | sed 's/^/    /'
        echo "== hwut.run --silent: stdout, line by line"
        "$BIN/hwut.run" --silent 2>/dev/null | sed -E 's/^/    |/'
        echo "    (that is all of it)"
        echo "== hwut.run --silent --events: stdout, line by line"
        "$BIN/hwut.run" --silent --events "$WORK/ev.txt" 2>/dev/null | sed -E 's/^/    |/'
        echo "    (that is all of it)"
        echo "== the events were written: $(grep -c . "$WORK/ev.txt") line(s)" ;;
    *)
        echo "unknown choice '$1'"; exit 1 ;;
esac
echo "<hwut-end>"
