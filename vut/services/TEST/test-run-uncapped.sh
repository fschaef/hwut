#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title   = "hwut.run: a cap that cannot be enforced refuses the test."
#     choices = ["acknowledged", "doors", "elsewhere", "help", "misspelt",
#                "plan", "refused", "utility"]
# }
#
# ---------------------------------------------------------------------------
#
# A page stating 'caps { network = false }' is REFUSED where the
# procsitter cannot deny the network (exploration R-48, R-80): not run,
# named in the flow and in the closing REFUSED block under its reason,
# with the 'hwut-root.conf' entry that acknowledges it. The other tests
# run and the summary stands.
#
# THE PLATFORM'S WORD IS THE MACHINE'S FACT: it is shown as '<platform>'.
#
# refused       no acknowledgement: two choices refused, one test runs;
#               the run exits REFUSED (2) though the rest passed.
# acknowledged  'procsitter { <platform> { network = false } }': all run.
# elsewhere     the acknowledgement names another platform: refused still.
# misspelt      an unknown cap, and a word where a boolean belongs:
#               faults by name, and nothing is acknowledged.
# doors         the faces that run WITHOUT a plan refuse the same case
#               by the same reason: 'hwut.accept', 'hwut.run.play',
#               'hwut.accept.interactive', 'hwut.report.details'.
# plan          'hwut.plan' refuses the same cases, by the same reason.
# help          'hwut.help' explains the refusal: the cap, the entry
#               that acknowledges, the cases concerned.
# utility       'psutil' taken away: EVERY case is refused -- the default
#               memory cap is a cap -- and run and 'hwut.help' both name
#               'psutil' as missing, and how it is installed.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
RUN="python3 -m vut.services.run --jobs=1 --deterministic --no-colour"
PLAN="python3 -m vut.services.plan"
HELP="python3 -m vut.services.help"
ACCEPT="python3 -m vut.services.accept --whole --dont-ask"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "hwut.run: a cap that cannot be enforced refuses the test.;"
        echo "CHOICES: refused, acknowledged, elsewhere, misspelt, plan, help, utility, doors;"
        exit 0 ;;
esac

PLATFORM=$(python3 -c \
   'from vut.engine.procsitter.api import platform_name; print(platform_name())')

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir "$WORK/TEST"
cd "$WORK/TEST"

conf() {                # <line of the root conf's own>
    printf 'hwut {\n    language-setup { bash { extensions = [".sh"] interpreter = "bash" } }\n%s}\n' \
           "$1" > ../hwut-root.conf
}
shown() {               # stdin -> stdout: no machine-chosen word
    sed "s|$WORK|\$WORK|g; s/$PLATFORM/<platform>/g; \
         s/[0-9]*\.[0-9]* \[sec\]/<t> [sec]/g; s/, [0-9:]*$/, <t>/"
}

cat > test-net.sh <<'PAGE'
#! /bin/bash
# @hwut {
#     title   = "network denied"
#     choices = ["a", "b"]
#     caps { network = false }
# }
echo "choice $1"
echo "<hwut-end>"
PAGE
cat > test-free.sh <<'PAGE'
#! /bin/bash
# @hwut { title = "no cap stated" }
echo "free"
echo "<hwut-end>"
PAGE
chmod +x test-net.sh test-free.sh

#  THE NOMINALS ARE RECORDED UNDER AN ACKNOWLEDGEMENT: a refused case is
#  never run, and so never accepted either.
conf "    procsitter { $PLATFORM { network = false } }
"
$ACCEPT test-net.sh a > /dev/null 2>&1
$ACCEPT test-net.sh b > /dev/null 2>&1
$ACCEPT test-free.sh  > /dev/null 2>&1

case "$1" in
    refused)
        conf ""
        $RUN 2>&1 | shown; echo "STATUS: ${PIPESTATUS[0]}" ;;
    acknowledged)
        $RUN 2>&1 | shown; echo "STATUS: ${PIPESTATUS[0]}" ;;
    elsewhere)
        conf "    procsitter { no-such-platform { network = false } }
"
        $RUN 2>&1 | shown; echo "STATUS: ${PIPESTATUS[0]}" ;;
    misspelt)
        #  ONE ENTRY PER LINE: a fault names its column, and the
        #  platform's word must not move it.
        conf "    procsitter { $PLATFORM {
        netwerk = false
        network = \"ignore\"
    } }
"
        $RUN 2>&1 | shown; echo "STATUS: ${PIPESTATUS[0]}" ;;
    doors)
        conf ""
        touch test-net.sh           # the recording is older: a run is owed
        echo "== hwut.accept test-net.sh a"
        python3 -m vut.services.accept test-net.sh a --dont-ask 2>&1 | shown
        echo "STATUS: ${PIPESTATUS[0]}"
        echo "== hwut.run.play test-net.sh a"
        python3 -m vut.services.lib.run.play test-net.sh a --plain 2>&1 | shown
        echo "STATUS: ${PIPESTATUS[0]}"
        echo "== hwut.accept.interactive test-net.sh a --console --all"
        python3 -m vut.services.lib.accept.interactive test-net.sh a \
                --console --all --plain < /dev/null 2>&1 | shown
        echo "STATUS: ${PIPESTATUS[0]}"
        echo "== hwut.report.details test-net.sh a"
        python3 -m vut.services.lib.report.details test-net.sh a 2>&1 \
            | grep -i "not run\|REFUSED\|provision" | shown
        echo "== nothing ran: the candidates are the acceptance's own"
        ls OUT | grep -c "test-net" | sed 's/^/candidate files: /'
        ;;
    plan)
        conf ""
        $PLAN 2>&1 | shown; echo "STATUS: ${PIPESTATUS[0]}" ;;
    help)
        conf ""
        $HELP 2>&1 | shown; echo "STATUS: ${PIPESTATUS[0]}" ;;
    utility)
        conf ""
        #  'psutil' TAKEN AWAY for hwut alone: a module of that name
        #  that refuses to import, ahead of the real one.
        mkdir "$WORK/shim"
        echo 'raise ImportError("psutil taken away by the test")' \
             > "$WORK/shim/psutil.py"
        export PYTHONPATH="$WORK/shim:$ROOT"
        $RUN 2>&1 | shown; echo "STATUS: ${PIPESTATUS[0]}"
        echo "--- hwut.help"
        $HELP 2>&1 | shown; echo "STATUS: ${PIPESTATUS[0]}" ;;
esac
echo "<hwut-end>"
