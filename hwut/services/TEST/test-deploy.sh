#! /bin/bash
#
# @hwut {
#     title   = "Deploy: a plan node between the build and the tests"
#     choices = ["flashed", "failed", "absent", "unbuilt"]
# }
#
# ---------------------------------------------------------------------------
# intend/26 o-40, o-41, o-47 (ruled 2026-11-06/07): 'deploy = "<command>"'
# is 'deploy { flash = "<command>" }'; the command runs directly, once per
# run, where the build ran; it is a plan node supported by the build and
# supporting the application's tests. A fake command stands for the flash;
# 'mode' says how it ends.
#
# flashed  exit 0: the deploy runs ONCE for two choices, before them; both
#          pass.
# failed   exit 1: 'deploy[test-b.sh]' fails, 'deploy failed' with its last
#          stderr line; both choices are 'unsupported', never run.
# absent   exit 77: the device the image goes to is not reachable --
#          'no-device' on the deploy, the choices unsupported.
# unbuilt  the build fails: the deploy and the choices are unsupported; the
#          deploy command never runs.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
BIN="$ROOT/hwut/bin"
export PATH="$BIN:$PATH"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "Deploy: a plan node between the build and the tests;"
        echo "CHOICES: flashed, failed, absent, unbuilt;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/TEST"
cd "$WORK"
printf 'hwut {\n    language-setup { bash { extensions = [".sh"] interpreter = "bash" } }\n}\n' \
       > hwut-root.conf
cd TEST
printf 'hwut { ignore = ["mode", "flash.sh", "flashed.log", "Makefile", "app", "broken"] }\n' > hwut.conf
shown() {
    sed -E "s|$WORK|\$WORK|g; s/[0-9]+\.[0-9]+ \[sec\]/<t> [sec]/g; s/ +\|\|[0-9]+$//"
}

#  THE FAKE FLASH: says what it was asked, ends as 'mode' says.
cat > flash.sh <<'EOF'
#! /bin/bash
echo "flash $*" >> flashed.log
case "$(cat mode)" in
    0)  exit 0 ;;
    1)  echo "flash: verify failed at 0x0400" >&2; exit 1 ;;
    77) echo "serial: no device /dev/serial/by-id/usb-Altera_USB-Blaster" >&2
        exit 77 ;;
esac
EOF

#  THE TEST: built by make (its target 'app'), deployed, then run.
cat > Makefile <<'EOF'
app:
	@test ! -f broken
	@printf '#! /bin/bash\necho "row of $$1"\necho "<hwut-end>"\n' > app
	@chmod +x app
EOF
cat > test-b.sh <<'EOF'
#! /bin/bash
# @hwut { build = "make"  deploy = "bash flash.sh uut.img"
#         choices = ["x", "y"] }
EOF

run() {
    rm -f flashed.log
    "$BIN/hwut.run" --plain > out.txt 2>&1; status=$?
    grep -vE "^(=|-|DIR |DIRECTORIES|   TEST|\||$)" out.txt | shown
    echo "exit: $status"
    echo "flash calls: $(cat flashed.log 2>/dev/null | wc -l)"
}

#  THE NOMINAL, recorded with the device present.
echo 0 > mode
"$BIN/hwut.play" test-b.sh x --plain > /dev/null 2>&1
"$BIN/hwut.play" test-b.sh y --plain > /dev/null 2>&1
"$BIN/hwut.accept" test-b.sh > /dev/null 2>&1

case "$1" in
    flashed) echo 0  > mode; run ;;
    failed)  echo 1  > mode; run ;;
    absent)  echo 77 > mode; run ;;
    unbuilt) echo 0  > mode; rm -f app; touch broken; run ;;
    *)
        echo "unknown choice '$1'"; exit 1 ;;
esac
echo "<hwut-end>"
