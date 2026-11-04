#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "The platform words '-p' and '--exclude-local': who takes them"
#     choices {
#         takes   { features = ["platform-words-taken"] }
#         refused { features = ["platform-words-refused"] }
#     }
# }
#
# ---------------------------------------------------------------------------
#
# THE PLATFORM WORDS OF THE WISH (adm/WORK/spec/42-platforms.txt section 2;
# plan/42 P-3): '-p <platform>' adds a platform to those specified,
# '--exclude-local' takes this machine out. Which bubble then runs where
# is P-4's decision (engine/orchestrator/run/TEST test-bubble.py); this
# page is about who takes the words.
#
# takes     the faces that run a test, and 'hwut.sanitize.propose', which
#           names every platform and runs nothing (intend/42 ruling 12):
#           'hwut.run -p linux' on a tree whose bubble requires none --
#           a NOTE, and the same RESULTS as without '-p'; '-p local' says
#           what no '-p' says, no NOTE; '--exclude-local -p linux' -- the
#           NOTE, and nothing runs: the one bubble requires 'local' (exit
#           3, EMPTY); 'hwut.play -p linux' -- the NOTE, the case
#           recorded; '--exclude-local' alone -- refused, it leaves no
#           platform.
# refused   every other face that reads the whole wish, by name and with
#           the faces that take them; a face that takes only some wish
#           words ('hwut.execute') does not know '-p' at all.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "The platform words '-p' and '--exclude-local': who takes them;"
        echo "CHOICES: takes, refused;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

#  A TREE WHOSE BUBBLE REQUIRES NO PLATFORM: 'local' alone (ruling 10).
printf 'hwut {\n}\n' > hwut-root.conf
mkdir -p TEST/GOOD
printf '#! /bin/sh\n# @hwut { title = "A" }\necho hello\necho "<hwut-end>"\n' \
       > TEST/test-a.sh
chmod +x TEST/test-a.sh
printf 'hello\n<hwut-end>\n' > TEST/GOOD/test-a.sh.txt

face() {                # <module> <args...> -- status, the lines that matter
    module=$1; shift
    echo "\$ $module $*"
    python3 -m "hwut.services.$module" "$@" > out.txt 2>&1
    echo "    STATUS: $?"
    #  THE MACHINE'S WORDS LEAVE THE PAGE: the seconds of RESULTS.
    grep -E "^(NOTE  -p|REFUSED|RESULTS|RECORDED|NOT RECORDED)" out.txt \
        | sed -e 's/, [0-9.]* \[sec\].*//' -e 's/(digest: [^)]*)/(digest)/' \
        | sed 's/^/    /'
}

case "$1" in
    takes)
        face run --plain
        face run -p linux --plain
        face run -p local --plain
        face run --exclude-local -p linux --plain
        face run --exclude-local --plain
        (cd TEST && face lib.run.play -p linux test-a.sh)
        face lib.sanitize.propose -p linux -p local -o proposal.txt
        echo "SUCCESS: the faces that run take them."
        ;;
    refused)
        for module in report lib.report.list accept lib.run.diff \
                      lib.accept.interactive plan lib.run.stability \
                      lib.cov.run lib.labels.create; do
            face "$module" -p linux
        done
        face lib.report.list --exclude-local -p linux
        #  'hwut.help' says first what this machine lacks -- a machine
        #  fact; its own reading is asked directly.
        echo "\$ help -p linux"
        python3 -c "from hwut.services import help as h; h.main(['-p', 'linux'])" \
            2>&1 | grep "^REFUSED" | sed 's/^/    /'
        face execute -p linux build
        echo "SUCCESS: refused by name where the face does not run."
        ;;
esac
echo "<hwut-end>"
