#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title   = "hwut.run: a cap that cannot be enforced fails the test, not run."
#     features = ["run-cap-refused"]
#     choices {
#         acknowledged { }
#         doors        { features = ["run-cap-refused-every-door"] }
#         elsewhere    { }
#         help         { features = ["help-explains-cap-refusal"] }
#         misspelt     { }
#         plan         { features = ["run-cap-refused-every-door", "plan-agrees-with-run"] }
#         refused      { }
#         utility      { features = ["run-cap-refused", "help-explains-cap-refusal"] }
#     }
# }
#
# ---------------------------------------------------------------------------
#
# A page stating 'caps { network = false }' FAILS, not run, where the
# procsitter cannot deny the network (exploration R-48, R-80; services
# E-159): 'uncapped [FAIL]' in the flow, counted, the cap and the
# 'hwut-root.conf' entry that acknowledges it beside it in HINTS. The
# other tests run.
#
# THE PLATFORM'S WORD IS THE MACHINE'S FACT: it is shown as '<platform>'.
#
# refused       no acknowledgement: two choices fail 'uncapped', one test
#               runs; the run exits 1.
# acknowledged  'procsitter { <platform> { network = false } }': all run.
# elsewhere     the acknowledgement names another platform: uncapped still.
# misspelt      an unknown cap, and a word where a boolean belongs:
#               faults by name, and nothing is acknowledged; the root
#               file does not read, so every case fails by name (E-190).
# doors         the face that runs WITHOUT a plan, 'hwut.play', refuses
#               the same case by the same reason, and 'hwut.report.details'
#               says it; 'hwut.accept' and 'hwut.merge' run nothing
#               (E-165), so no cap concerns them. MEASURED 2026-10-22
#               before: accept and merge refused too -- they ran.
# plan          'hwut.plan' names the same cases 'UNCAPPED [FAIL]', by the
#               same reason.
# help          'hwut.help' explains the failure: the cap, the entry
#               that acknowledges, the cases concerned.
# utility       'psutil' taken away: EVERY case fails uncapped -- the default
#               memory cap is a cap -- and run and 'hwut.help' both name
#               'psutil' as missing, and how it is installed.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
RUN="python3 -m hwut.services.run --jobs=1 --deterministic --no-colour"
PLAN="python3 -m hwut.services.plan"
HELP="python3 -m hwut.services.help"
accepted() {            # play every case the words select, then bless (E-165)
    python3 -m hwut.services.lib.run.play --all "$@" --plain > /dev/null 2>&1
    python3 -m hwut.services.accept --whole "$@"
}
ACCEPT=accepted
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "hwut.run: a cap that cannot be enforced fails the test, not run.;"
        echo "CHOICES: refused, acknowledged, elsewhere, misspelt, plan, help, utility, doors;"
        exit 0 ;;
esac

PLATFORM=$(python3 -c \
   'from hwut.engine.procsitter.api import platform_name; print(platform_name())')

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
        touch test-net.sh           # the source is younger than its recording
        echo "== hwut.play test-net.sh a"
        python3 -m hwut.services.lib.run.play test-net.sh a --plain 2>&1 | shown
        echo "STATUS: ${PIPESTATUS[0]}"
        echo "== hwut.accept test-net.sh a: it runs nothing, no cap concerns it"
        python3 -m hwut.services.accept test-net.sh a 2>&1 \
            | grep -c "^REFUSED" | sed 's/^/REFUSED lines: /'
        echo "== hwut.merge test-net.sh a --console --all: the same"
        python3 -m hwut.services.lib.accept.interactive test-net.sh a \
                --console --all --plain < /dev/null 2>&1 \
            | grep -c "^REFUSED" | sed 's/^/REFUSED lines: /'
        echo "== hwut.report.details test-net.sh a"
        python3 -m hwut.services.lib.report.details test-net.sh a 2>&1 \
            | grep -i "not run\|REFUSED\|provision" | shown
        echo "== nothing ran: the candidates are the fixture's own"
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
