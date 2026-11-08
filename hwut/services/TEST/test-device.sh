#! /bin/bash
#
# @hwut {
#     title   = "Exit 77: the device a test talks to is not reachable"
#     choices = ["unreachable", "other-status"]
# }
#
# ---------------------------------------------------------------------------
# intend/26 o-49 (ruled 2026-11-07): a test whose device -- a board, a
# simulator -- is missing or does not come up FAILS, like a test that cannot
# be built; exit status 77 is its reason, the output is NOT compared, the
# last stderr line is the NOTE. Every other status stays behaviour.
#
# unreachable   a test recorded with its device present, then run with the
#               device gone: it exits 77 -- '[FAIL]', 'no-device', the
#               stderr line beside it, counted in RESULTS, the run's exit 1.
#               MEASURED 2026-11-07 before: 'stderr [FAIL]' -- the half
#               picture compared, the device named nowhere.
# other-status  a test that exits 3 with its rows: compared as ever (the
#               status is behaviour) -- it passes.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
BIN="$ROOT/hwut/bin"
export PATH="$BIN:$PATH"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "Exit 77: the device a test talks to is not reachable;"
        echo "CHOICES: unreachable, other-status;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/TEST"
cd "$WORK"
printf 'hwut {\n    language-setup { bash { extensions = [".sh"] interpreter = "bash" } }\n}\n' \
       > hwut-root.conf
cd TEST
printf 'hwut { ignore = ["board"] }\n' > hwut.conf
shown() {
    sed -E "s|$WORK|\$WORK|g; s/[0-9]+\.[0-9]+ \[sec\]/<t> [sec]/g; s/ +\|\|[0-9]+$//"
}

case "$1" in
    unreachable)
        cat > test-b.sh <<'EOF'
#! /bin/bash
# @hwut { choices = ["x"] }
echo "## agent: proto 1"
if [ ! -f "$(dirname "$0")/board" ]; then
    echo "serial: no device /dev/serial/by-id/usb-Altera_USB-Blaster" >&2
    exit 77
fi
echo "0304 007"
echo "<hwut-end>"
EOF
        chmod +x test-b.sh
        touch board
        "$BIN/hwut.play" test-b.sh x --plain > /dev/null 2>&1
        "$BIN/hwut.accept" test-b.sh x > /dev/null 2>&1
        echo "== the device present"
        "$BIN/hwut.run" --plain 2>&1 | grep -E "^END|RESULTS" | shown
        rm board
        echo "== the device gone"
        "$BIN/hwut.run" --plain > out.txt 2>&1; status=$?
        grep -E "^END|RESULTS|no device|no-device|not reachable" out.txt | shown
        echo "exit: $status" ;;
    other-status)
        printf '#! /bin/bash\n# @hwut { choices = ["x"] }\necho "rows"\necho "<hwut-end>"\nexit 3\n' > test-s.sh
        chmod +x test-s.sh
        "$BIN/hwut.play" test-s.sh x --plain > /dev/null 2>&1
        "$BIN/hwut.accept" test-s.sh x > /dev/null 2>&1
        "$BIN/hwut.run" --plain > out.txt 2>&1; status=$?
        grep -E "^END|RESULTS" out.txt | shown
        echo "exit: $status" ;;
    *)
        echo "unknown choice '$1'"; exit 1 ;;
esac
echo "<hwut-end>"
