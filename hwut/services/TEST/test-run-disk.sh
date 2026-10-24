#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title    = "hwut.run: a case starts where its disk has room for it"
#     features = ["run-disk-room"]
#     choices  = ["short", "wait", "local"]
# }
#
# ---------------------------------------------------------------------------
#
# THE DISK GUARD SEEN FROM THE RUN (scheduler S-5, exploration R-99,
# DEFECTS-hwut-78e11f7 D-24). 'hwut { free_disk_min_mb = <n> }' in
# 'hwut-root.conf' is every disk's floor; a case needs twice its
# 'caps { disk_mb }' free above it.
#
# short   a floor above anything a disk holds: every case 'no-disk
#         [FAIL]', not run, its numbers in HINTS.
# wait    two cases of 'disk_mb = 1000' with room for one: run with two
#         workers, the second starts after the first ended. The floor is
#         set 3000 MB below what stands free now (the page needs that
#         much), so the margin outlasts what else writes meanwhile.
#         MEASURED 2026-10-19 before the guard: 'a had ended: no'.
# local   the floor in a test directory's own 'hwut.conf': a fault, it
#         is the root's alone.
#
# THE FREE SPACE IS THE MACHINE'S FACT: shown as '<n>'.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
RUN="python3 -m hwut.services.run --no-colour"
accepted() {            # play every case the words select, then bless (E-165)
    python3 -m hwut.services.lib.run.play --all "$@" --plain > /dev/null 2>&1
    python3 -m hwut.services.accept --whole "$@"
}
ACCEPT=accepted
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "hwut.run: a case starts where its disk has room for it;"
        echo "CHOICES: short, wait, local;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir "$WORK/TEST"
cd "$WORK/TEST"

conf() {                # <line of the root conf's own>
    printf 'hwut {\n    language-setup { bash { extensions = [".sh"] interpreter = "bash" } }\n%s}\n' \
           "$1" > ../hwut-root.conf
}
shown() {               # stdin -> stdout: no machine-chosen word
    sed "s|$WORK|\$WORK|g; s/free [0-9]* MB/free <n> MB/g; \
         s/floor of [0-9]* MB/floor of <n> MB/g; \
         s/[0-9]*\.[0-9]* \[sec\]/<t> [sec]/g; s/, [0-9:]*$/, <t>/"
}

cat > test-a.sh <<'PAGE'
#! /bin/bash
# @hwut { title = "first"  caps { disk_mb = 1000 } }
sleep 1
touch a.done
echo "a"
echo "<hwut-end>"
PAGE
cat > test-b.sh <<'PAGE'
#! /bin/bash
# @hwut { title = "second"  caps { disk_mb = 1000 } }
if [ -f a.done ]; then echo "a had ended: yes"; else echo "a had ended: no"; fi
echo "<hwut-end>"
PAGE
chmod +x test-a.sh test-b.sh

conf ""
touch a.done
$ACCEPT test-a.sh > /dev/null 2>&1
$ACCEPT test-b.sh > /dev/null 2>&1
rm -f a.done

case "$1" in
    short)
        conf "    free_disk_min_mb = 1000000000
"
        $RUN --deterministic --jobs=1 2>&1 | shown; echo "STATUS: ${PIPESTATUS[0]}" ;;
    wait)
        FREE=$(python3 -c "import shutil; print(int(shutil.disk_usage('.').free / 1048576))")
        conf "    free_disk_min_mb = $((FREE - 3000))
"
        $RUN --jobs=2 --strategy=linear,name-sorted 2>&1 | shown; echo "STATUS: ${PIPESTATUS[0]}" ;;
    local)
        conf ""
        printf 'hwut {\n    free_disk_min_mb = 512\n}\n' > hwut.conf
        $RUN --deterministic --jobs=1 2>&1 | shown; echo "STATUS: ${PIPESTATUS[0]}" ;;
esac
echo "<hwut-end>"
