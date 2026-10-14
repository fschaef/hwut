#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "hwut.help: the subtle failures of the last results, explained"
#     features   = ["help-explains-failures"]
#     choices {
#         explain  { features = ["help-explains-failures", "run-points-to-help", "run-stderr-fails"] }
#         empty    { features = ["help-explains-failures", "run-points-to-help"] }
#         nonsense { features = ["help-explains-nonsense", "run-ignores-features", "report-features-nonsense"] }
#         refused  { features = ["face-refusal-by-name"] }
#     }
# }
#
# ---------------------------------------------------------------------------
#
# 'hwut.help' (display D-34) reads the books below the directory and
# explains every failure that is not a plain deviation from GOOD -- once,
# with how many cases it struck and one of them as the example.
#
# explain   a run with a deviation, two cases without '<hwut-end>' and
#           one with unexpected stderr: the run ends HINTS with the
#           pointer to 'hwut.help'; 'hwut.help' explains the two subtle
#           failures, once each, and not the deviation.
# empty     a run whose only failure is a deviation: no pointer in the
#           run; 'hwut.help' has nothing to explain (exit 3).
# nonsense  the TEST directory states features and the one test links to
#           none: no failure, the run says nothing of it; 'hwut.help'
#           explains 'NONSENSE?' and names the test run (exit 0). Once
#           the test links to a feature there is nothing to explain.
# refused   an unknown option; a directory that does not exist.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
HELP="python3 -m hwut.services.help"
RUN="python3 -m hwut.services.run"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "hwut.help: the subtle failures of the last results, explained;"
        echo "CHOICES: explain, empty, nonsense, refused;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
printf 'hwut {\n}\n' > hwut-root.conf

face() {                  #  <face> <argument>...: status and output
    $1 "${@:2}" > out.txt 2>&1
    echo "STATUS: $?"
    sed 's|'"$WORK"'|<work>|g; s/^/    /' < out.txt
}

app() {                   #  <name> <body line>...: a test, booked by a run
    { echo '#! /bin/bash'
      echo "# @hwut { title = \"$1\" }"
      shift
      printf '%s\n' "$@"
    } > "tree/TEST/$name"
    chmod +x "tree/TEST/$name"
}

tree() {
    mkdir -p tree/TEST/GOOD
    printf 'hwut {\n}\n' > tree/hwut-root.conf
    printf 'hwut {\n}\n' > tree/TEST/hwut.conf
    name=test-dev.sh; app "Dev" 'echo "what the run says"' 'echo "<hwut-end>"'
    printf 'what GOOD expects\n<hwut-end>\n' > tree/TEST/GOOD/test-dev.sh.txt
}

case "$1" in

explain)
    tree
    for stem in a b; do
        name=test-noend-$stem.sh; app "No end" 'echo "line"'
        printf 'line\n' > tree/TEST/GOOD/$name.txt
    done
    name=test-err.sh; app "Err" 'echo "line"' 'echo "noise" >&2' 'echo "<hwut-end>"'
    printf 'line\n<hwut-end>\n' > tree/TEST/GOOD/test-err.sh.txt
    ( cd tree/TEST && $RUN --jobs=1 > run.txt 2>&1 )
    echo "--- the run's HINTS end with the pointer:"
    sed -n '/^HINTS/,/^REFUSED\|^=\{20,\}$/p' tree/TEST/run.txt \
        | grep -v '^[=-]*$' | sed 's/^/    /'
    echo "--- hwut.help:"
    face "$HELP" --directory=tree
    ;;

empty)
    tree
    ( cd tree/TEST && $RUN --jobs=1 > run.txt 2>&1 )
    echo "--- the run names no pointer: $(grep -c "hwut.help" tree/TEST/run.txt)"
    echo "--- hwut.help:"
    face "$HELP" --directory=tree
    ;;

nonsense)
    tree
    printf 'what the run says\n<hwut-end>\n' > tree/TEST/GOOD/test-dev.sh.txt
    printf 'features {\n    1 { name = "says" }\n}\n' \
        > tree/TEST/hwut-features.conf
    ( cd tree/TEST && $RUN --jobs=1 > run.txt 2>&1 )
    echo "--- the run: $(grep '^RESULTS' tree/TEST/run.txt | cut -d, -f1-2)"
    echo "--- hwut.help:"
    face "$HELP" --directory=tree
    echo "--- the test links to the feature:"
    sed -i 's|title = "Dev"|title = "Dev" features = ["says"]|' \
        tree/TEST/test-dev.sh
    face "$HELP" --directory=tree
    ;;

refused)
    tree
    face "$HELP" --sideways
    face "$HELP" --directory=nowhere
    ;;

*)
    echo "no such choice: $1"
    exit 1 ;;
esac

echo "<hwut-end>"
