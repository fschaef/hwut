#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "test management: the roster, 'HWUT_ROOT/', and what sanitize says of moves"
#     features   = ["roster-records-directories"]
#     choices {
#         roster       { features = ["roster-records-directories", "record-directory"] }
#         gone         { features = ["roster-gone-fails"] }
#         scope        { features = ["roster-scope"] }
#         directories  { features = ["sanitize-directories"] }
#         empty-dir    { features = ["sanitize-orphans-empty-directory"] }
#         rename-noted { features = ["sanitize-rename-noted"] }
#         rubbish-last { features = ["sanitize-rubbish-last"] }
#         pending-move { features = ["run-pending-move-noted"] }
#         old-place    { features = ["old-place-refused", "renovate-root-files"] }
#     }
# }
#
# ---------------------------------------------------------------------------
#
# THE CHANGE REQUEST OF 2026-11-20 (services RATIONALE E-234, bookkeeper
# B-33), one choice per item. MEASURED BEFORE on e434b21, Schwarm 51 stage 5:
#
# roster       (CR-1, CR-2) a directory's first record enters it in
#              'HWUT_ROOT/directories.txt'; its last record removed takes it out.
# gone         (CR-2) a recorded TEST directory deleted whole: before, the
#              run said '26 ok, 0 fail', exit 0 -- the books went with it.
#              Now one case fails, 'in roster, no such directory'; the
#              report shows it, 'hwut.help' explains it.
# scope        (CR-2) a run below another directory, '--dir' elsewhere, a
#              glob: the gone directory is not judged.
# directories  (CR-3) moved and nothing run: 'move <old> <new>', which
#              carries the labels; moved and run since: 'forget', noted
#              'moved?' where one directory bears the same name.
# empty-dir    (CR-5) the last test moved out: before, 'orphans not judged
#              -- the wish hides cases here', 'remove.propose' silent, and
#              'hwut.sanitize move' said 'nothing is recorded of it'.
# rename-noted (CR-6) renamed by hand: before, a bare 'forget', which drops
#              the GOOD files; now the line is noted 'renamed? hwut.rename'.
# rubbish-last (CR-8) before, 'remove <dir>/OUT' led every proposal.
# pending-move (CR-7) 'hwut.rename' across directories before 'git mv':
#              before, the old place said only 'no GOOD file ... accept'.
# old-place    (CR-4, E-235) a tree of before -- 'hwut-root.conf',
#              'hwut-root.labels' -- refused by name; 'hwut.renovate --apply'
#              moves them into 'HWUT_ROOT/' and begins the roster.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
BIN="$ROOT/hwut/bin"
export PYTHONPATH="$ROOT"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "test management: the roster, 'HWUT_ROOT/', and what sanitize says of moves;"
        echo "CHOICES: roster, gone, scope, directories, empty-dir, rename-noted, rubbish-last, pending-move, old-place;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

app() {                   #  <path> <choice>...: a test printing its choice
    local path=$1; shift
    mkdir -p "$(dirname "$path")"
    {   echo '#! /bin/bash'
        echo '# @hwut {'
        echo "#     title = \"$(basename "$path")\""
        echo '#     choices {'
        for c in "$@"; do echo "#         $c { }"; done
        echo '#     }'
        echo '# }'
        echo 'echo "case $1"'
        echo 'echo "<hwut-end>"'
    } > "$path"
    chmod +x "$path"
}

tree() {                  #  a fresh, accepted tree of three directories
    rm -rf "$WORK/t"; mkdir -p "$WORK/t"; cd "$WORK/t"
    mkdir -p HWUT_ROOT
    printf 'hwut {\n}\n' > HWUT_ROOT/setup.conf
    app game/TEST/test-loop.sh   step
    app input/TEST/test-keys.sh  left right
    app render/TEST/test-screen.sh start win
    for d in game input render; do
        ( cd $d/TEST && "$BIN/hwut.play" --all --plain > /dev/null 2>&1 \
                     && "$BIN/hwut.accept" > /dev/null 2>&1 )
    done
}

roster() {                #  the roster's entries
    echo "ROSTER {"; grep -v '^#' HWUT_ROOT/directories.txt | sed 's/^/    /'; echo "}"
}

ran() {                   #  [<argument>...]: hwut.run's verdict and exit
    "$BIN/hwut.run" --plain "$@" > run.txt 2>&1
    echo "EXIT: $?"
    grep -E "^RESULTS|no such directory|pending move" run.txt \
        | sed -E 's/, [0-9.]+ \[sec\].*$//; s/^/    /'
}

proposed() {              #  [<argument>...]: the proposal's commands
    "$BIN/hwut.sanitize.propose" "$@" 2> err.txt \
        | grep -vE '^#( |$)|^$' | sed 's/^/    /'
    sed 's/^/    stderr: /' err.txt
}

case "$1" in
roster)
    tree
    echo "--- after the first acceptance"; roster
    echo "--- the last test of 'render/TEST' removed"
    ( cd render/TEST && "$BIN/hwut.remove" test-screen.sh --dont-ask > /dev/null )
    roster
    echo "--- accepted again"
    ( cd render/TEST && "$BIN/hwut.play" --all --plain > /dev/null 2>&1 \
                     && "$BIN/hwut.accept" > /dev/null 2>&1 )
    roster
    echo "--- 'HWUT_ROOT/' is walked by nobody: a TEST below it is no test"
    app HWUT_ROOT/TEST/test-no.sh one
    ran
    ;;
gone)
    tree; rm -rf render
    echo "--- run"; ran
    sed -n '/^ROSTER/,/^$/p' run.txt | sed 's/^/    /'
    echo "--- report"
    "$BIN/hwut.report" --plain 2>&1 | grep -E "no such directory|^RESULTS" \
        | sed 's/^/    /'
    echo "--- help"
    "$BIN/hwut.help" 2>&1 | grep -E "no-dir|CONCERNED|render/TEST" \
        | sed 's/^ *//; s/^/    /'
    ;;
scope)
    tree; rm -rf render
    echo "--- below 'game/'";      ( cd game && ran )
    echo "--- --dir input/TEST";   ran --dir input/TEST
    echo "--- a glob";             ran --glob "test-loop.sh"
    echo "--- --exclude-dir render/TEST"; ran --exclude-dir render/TEST
    ;;
directories)
    tree
    "$BIN/hwut.labels.create" screens --glob "test-screen.sh" > /dev/null
    echo "--- moved, nothing run"
    mv render gfx; proposed --directories
    "$BIN/hwut.sanitize" move render/TEST gfx/TEST
    roster; grep -v '^#' HWUT_ROOT/labels.txt | sed 's/^/    /'
    echo "--- moved again, and run since"
    mkdir -p lib; mv gfx lib/gfx; ran; proposed --directories
    echo "--- forget"
    "$BIN/hwut.sanitize" forget gfx/TEST; roster
    echo "--- forget a directory that stands: refused"
    "$BIN/hwut.sanitize" forget input/TEST; echo "STATUS: $?"
    ;;
empty-dir)
    tree; mkdir -p world/TEST
    mv render/TEST/test-screen.sh world/TEST/
    echo "--- moved out"; proposed --orphans
    ( cd render/TEST && "$BIN/hwut.sanitize" move test-screen.sh ../../world/TEST )
    echo "--- deleted"
    tree; rm render/TEST/test-screen.sh; proposed --orphans
    "$BIN/hwut.remove.propose" -o r.txt > /dev/null 2>&1
    grep -v '^#' r.txt | grep -v '^$' | sed 's/^/    remove.propose: /'
    ;;
rename-noted)
    tree
    mv input/TEST/test-keys.sh input/TEST/test-buttons.sh
    sed -i 's/#         start { }/#         begin { }/' render/TEST/test-screen.sh
    echo "--- renamed by hand"; proposed --orphans
    echo "--- deleted, and an unrelated test beside it: no note"
    tree; rm input/TEST/test-keys.sh; app input/TEST/test-other.sh up
    proposed --orphans
    ;;
rubbish-last)
    tree; rm input/TEST/test-keys.sh
    proposed
    ;;
pending-move)
    tree
    ( cd input/TEST && "$BIN/hwut.rename" test-keys.sh \
          -to ../../game/TEST/test-keys.sh --dont-ask > /dev/null 2>&1 )
    echo "--- before 'git mv'"; ran
    mv input/TEST/test-keys.sh game/TEST/
    echo "--- after the move"; ran
    ;;
old-place)
    tree
    "$BIN/hwut.labels.create" screens --glob "test-screen.sh" > /dev/null
    echo "--- the layout of before: flat files beside the root"
    mv HWUT_ROOT/setup.conf hwut-root.conf
    mv HWUT_ROOT/labels.txt hwut-root.labels
    rm -rf HWUT_ROOT
    echo "--- run";   ran; grep -E "REFUSED|FAULT" run.txt | sed 's/^/    /'
    echo "--- renovate"; "$BIN/hwut.renovate" 2>&1 | grep -E "' -> '|written|change" \
        | sed 's/^/    /'
    "$BIN/hwut.renovate" --apply > /dev/null 2>&1
    for f in hwut-root.conf hwut-root.labels HWUT_ROOT/setup.conf \
             HWUT_ROOT/labels.txt HWUT_ROOT/directories.txt; do
        if [ -f $f ]; then echo "    stands: $f"; else echo "    gone:   $f"; fi
    done
    echo "--- run"; ran
    echo "--- labels"; "$BIN/hwut.labels.list" 2>&1 | sed 's/^/    /'
    echo "--- both places: two copies"
    cp HWUT_ROOT/labels.txt hwut-root.labels; ran; grep -E "REFUSED|FAULT" run.txt | sed 's/^/    /'
    ;;
esac
echo "<hwut-end>"
