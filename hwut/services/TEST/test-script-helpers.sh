#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title    = "the directory's scripts: helpers around each test run, all supervised"
#     features = ["script-helpers-supervised"]
#     choices  = ["around", "caps", "execute", "misplaced"]
# }
#
# ---------------------------------------------------------------------------
#
# TODO B-17, ruled 2026-10-19: 'on_before_test' and 'on_after_test' run a
# script before and after EACH test run, as 'on_entry' and 'on_exit' do
# around the directory -- helpers, NO VERDICT; an end other than exit 0
# is said, a FRAME line and a NOTE. EVERY script of a directory runs under
# the procsitter -- the frame, the helpers, the targets of 'hwut.execute'
# -- with the caps 'script_caps { }' of 'hwut.conf' states, in the words
# of 'caps { }'.
#
# around     the order the four scripts run in, the run told by
#            'HWUT_TEST' and 'HWUT_CHOICE'; one 'on_after_test' exiting 1:
#            said, the verdicts untouched.
# caps       'script_caps { timeout_sec = 1 }': an 'on_entry' sleeping 5
#            is ended by the supervisor, said 'ended: wall clock
#            exceeded'; the tests run.
# execute    'hwut.execute': a target within its caps runs and speaks; one
#            past them is ended by the supervisor, FAILED by name.
#            MEASURED 2026-10-19 before: targets ran unsupervised.
# misplaced  a helper named at a tree level, above the test directory: a
#            fault, a local matter.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
BIN="$ROOT/hwut/bin"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "the directory's scripts: helpers around each test run, all supervised;"
        echo "CHOICES: around, caps, execute, misplaced;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/sub/TEST"
cd "$WORK"
printf 'hwut {\n    language-setup { bash { extensions = [".sh"] interpreter = "bash" } }\n}\n' \
       > hwut-root.conf
printf '#! /bin/bash\n# @hwut { title = "a" choices = ["x", "y"] }\necho "$1"; echo "<hwut-end>"\n' \
       > sub/TEST/test-a.sh
printf '#!/bin/bash\necho hello from the target\n' > sub/TEST/hello.sh
printf '#!/bin/bash\nsleep 5\n'                     > sub/TEST/slow.sh
chmod +x sub/TEST/*.sh
(cd sub/TEST && "$BIN/hwut.play" --all --plain > /dev/null 2>&1; "$BIN/hwut.accept" --whole --dont-ask > /dev/null 2>&1)
rm -f sub/TEST/log.txt

shown() {
    sed -E "s/[0-9]+\.[0-9]+ \[sec\]/<t> [sec]/g; s/, [0-9:]+$/, <t>/"
}
RUN="$BIN/hwut.run --jobs=1 --deterministic --no-colour"
case "$1" in
    around)
        cat > sub/TEST/hwut.conf <<'E'
hwut {
    on_entry       = "echo entry >> log.txt"
    on_before_test = "echo before $HWUT_TEST $HWUT_CHOICE >> log.txt"
    on_after_test  = "echo after $HWUT_TEST $HWUT_CHOICE >> log.txt; test $HWUT_CHOICE != y"
    on_exit        = "echo exit >> log.txt"
}
E
        $RUN 2>&1 | shown
        echo "== log.txt"; cat sub/TEST/log.txt ;;
    caps)
        cat > sub/TEST/hwut.conf <<'E'
hwut {
    on_entry    = "sleep 5"
    script_caps { timeout_sec = 1 }
}
E
        $RUN 2>&1 | shown ;;
    execute)
        cat > sub/TEST/hwut.conf <<'E'
hwut {
    script_caps { timeout_sec = 1 }
    target { hello = "./hello.sh"  slow = "./slow.sh" }
}
E
        "$BIN/hwut.execute" hello 2>&1; echo "STATUS: $?"
        "$BIN/hwut.execute" slow 2>&1;  echo "STATUS: $?" ;;
    misplaced)
        printf 'hwut {\n    on_before_test = "true"\n}\n' > sub/hwut.conf
        $RUN 2>&1 | grep -E "ERROR|VOCABULARY" | shown ;;
esac
echo "<hwut-end>"
