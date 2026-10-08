#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title   = "A word in a test's header, through the face: what the validator admits, the run does."
#     choices = ["constraint", "constraint_refused", "execute", "same"]
# }
#
# ---------------------------------------------------------------------------
#
# ONE PAGE THROUGH THE FACE (audit r10, G-10) for words a header may
# state: the word written in a fixture's '@hwut { }', the launcher
# called, the outcome printed. Each was green by a page that exercised
# a function while the face took another road.
#
# constraint          'constraints = ["glob(name, \"build-*.log\")"]'
#                     (exploration R-66, G-3): 'hwut.run.play' reads the
#                     stream under it and 'hwut.accept' judges it --
#                     once holding, once broken.
# constraint_refused  a name the namespace does not hold: a FAULT with
#                     file, line and column, from 'hwut.run' and from
#                     'hwut.run.play' -- no traceback.
# execute             'execute' with '$file', '$filestem', '$choice'
#                     (exploration R-68, G-4): expanded in the call; a
#                     placed '$choice' is not appended again; an
#                     unplaced one is the last argument; the choice-less
#                     call drops the empty word.
# same                'same = true' (exploration R-45, bookkeeper B-30,
#                     G-2): 'hwut.accept' writes ONE nominal for the
#                     test, 'hwut.run' judges every choice by it,
#                     'hwut.report.details' finds it, a choice's removal
#                     leaves it, the test's rename takes it along and
#                     the test's removal takes it away.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
RUN="python3 -m vut.services.run --jobs=1 --deterministic --no-colour --quiet"
PLAY="python3 -m vut.services.lib.run.play --plain"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "A word in a test's header, through the face.;"
        echo "CHOICES: constraint, constraint_refused, execute, same;"
        exit 0 ;;
esac

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

case "$1" in
    constraint)
        HEAD='#     title = "glob"\n#     tolerance { constraints = ["glob(name, \\"build-*.log\\")"] }\n'
        #  A STRING BINDING IS QUOTED: '((name: "text"))'. Unquoted it
        #  reads as an analogy and binds nothing.
        page test-holds.sh  "$HEAD" "echo 'file ((name: \"build-7.log\"))'"
        page test-breaks.sh "$HEAD" "echo 'file ((name: \"debug-7.log\"))'"
        for t in test-holds.sh test-breaks.sh; do
            echo "== hwut.run.play $t"
            $PLAY $t 2>&1 | shown | sed -n '/^===== OUTPUT/,$p' | grep -v "^=*$"
            echo "STATUS: ${PIPESTATUS[0]}"
            echo "== hwut.accept --whole $t"
            python3 -m vut.services.accept --whole $t --dont-ask 2>&1 | shown \
                | grep "blessed\|REFUSED\|constraint\|Traceback"
        done ;;
    constraint_refused)
        page test-typo.sh \
             '#     title = "typo"\n#     tolerance { constraints = ["globb(name, \\"x\\")"] }\n' \
             'echo "file ((name: x))"'
        echo "== hwut.run"
        $RUN 2>&1 | shown | grep "ERROR\|Traceback" | cut -c1-74
        echo "STATUS: ${PIPESTATUS[0]}"
        echo "== hwut.run.play test-typo.sh"
        $PLAY test-typo.sh 2>&1 | shown | grep "FAULT\|Traceback\|nothing played" | cut -c1-74
        echo "STATUS: ${PIPESTATUS[0]}" ;;
    execute)
        page test-placed.sh \
             '#     title   = "placed"\n#     choices = ["one", "two"]\n#     execute = "bash $file --stem=$filestem --pick $choice tail"\n' \
             'echo "args: $*"'
        page test-unplaced.sh \
             '#     title   = "unplaced"\n#     choices = ["one"]\n#     execute = "bash $file head"\n' \
             'echo "args: $*"'
        page test-none.sh \
             '#     title   = "no choice"\n#     execute = "bash $file $choice end"\n' \
             'echo "args: $*"'
        for t in "test-placed.sh one" "test-placed.sh two" \
                 "test-unplaced.sh one" "test-none.sh"; do
            echo "== hwut.run.play $t --raw"
            $PLAY $t --raw 2>&1 | shown | grep "args:\|EMPTY\|FAULT" | head -1
        done ;;
    same)
        page test-same.sh \
             '#     title   = "same"\n#     choices = ["a", "b"]\n#     same    = true\n' \
             'echo "one behaviour"'
        good() { ls GOOD | grep -v book.csv | sed 's/^/    GOOD: /'; }
        echo "== hwut.accept --whole"
        python3 -m vut.services.accept --whole --dont-ask 2>&1 | grep "blessed\|REFUSED"
        good
        echo "== hwut.run"
        $RUN 2>&1 | grep "RESULTS" | sed 's/, [0-9.]* \[sec\].*//'
        echo "== hwut.report.details test-same.sh a"
        python3 -m vut.services.lib.report.details test-same.sh a 2>&1 \
            | grep "status report"
        echo "== hwut.remove test-same.sh b"
        python3 -m vut.services.remove test-same.sh b --dont-ask > /dev/null 2>&1
        good
        echo "== hwut.rename test-same.sh -to test-other.sh"
        python3 -m vut.services.rename test-same.sh -to test-other.sh \
                --dont-ask > /dev/null 2>&1
        good
        echo "== hwut.remove test-other.sh"
        python3 -m vut.services.remove test-other.sh --dont-ask > /dev/null 2>&1
        good
        echo "    (GOOD holds no nominal)" ;;
esac
echo "<hwut-end>"
