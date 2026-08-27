#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# hwut {
#     title      = "The exit status law: one enum, every face relates."
#     choices    = ["law"]
#     eq-pattern = ["[0-9]+"]
# }
#
# ---------------------------------------------------------------------------
#
# THE EXIT STATUS LAW (E-1), TESTED AS A TABLE: one enum,
# 'E_ExitCode', and every face driven over the same four stimuli --
# a good line, a fault, an unreadable line, an empty selection. A
# face that disagrees with the law shows as a divergent cell, not as
# a comment nobody read. '-' marks a stimulus a face cannot express.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"

case "$1" in
    --hwut-info)
        echo "The exit status law: one enum, every face relates.;"
        echo "CHOICES: law;"
        echo "HAPPY: [0-9]+;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

#  THE TREE'S BOUNDARY. Every face ASCENDS collecting 'hwut.conf'
#  until it meets this file; a tree without one is refused, so a
#  fixture states its own. Empty says only 'the tree ends here'.
printf 'hwut {\n}\n' > hwut-root.conf

echo "THE ENUM (services/_exit.py):"
python3 - <<'PYEOF'
from vut.services._exit import E_ExitCode
for member in E_ExitCode:
    print("    %-8s = %d" % (member.name, member.value))
PYEOF

#  The stimuli, one directory each. ---------------------------------------
mkdir -p ok_dir/GOOD
printf '#!/bin/bash\n# hwut { title = "Ok" }\necho "steady line"\n' \
    > ok_dir/test-ok.sh
chmod +x ok_dir/test-ok.sh
printf 'steady line\n' > ok_dir/GOOD/test-ok.sh.txt

#  A REAL FAULT: a dependency CYCLE, which the plan cannot satisfy.
#  (It was a test with an unterminated header, which the reader passes
#  over in silence -- the file simply is not a test application. The
#  '1' that column showed came from an ImportError in the interview,
#  not from a fault: a GOOD recorded over a crash.)
mkdir -p fault_dir
printf 'hwut {\n    on_entry = "true"\n    on_exit = "true"\n    dependency { "test-a.sh" = ["test-b.sh"]  "test-b.sh" = ["test-a.sh"] }\n}\n' \
    > fault_dir/hwut.conf
for name in a b; do
    printf '#!/bin/bash\n# hwut { title = "T" }\necho x\n' \
        > "fault_dir/test-$name.sh"
    chmod +x "fault_dir/test-$name.sh"
done

mkdir -p run_ok/suite/TEST run_fault/suite/TEST
cp -r ok_dir/.    run_ok/suite/TEST/
cp -r fault_dir/. run_fault/suite/TEST/
printf 'hwut {\n    on_entry = "true"\n    on_exit = "true"\n}\n' \
    | tee run_ok/suite/TEST/hwut.conf > run_fault/suite/TEST/hwut.conf

status() { "$@" > /dev/null 2>&1; echo -n "$?"; }

echo
echo "FACE         OK  FAULT  REFUSED  EMPTY"
printf 'hwut.show     %s      %s        %s      -\n' \
    "$(status python3 -m vut.services.show \
              --directory=ok_dir)" \
    "$(status python3 -m vut.services.show \
              --directory=fault_dir)" \
    "$(status python3 -m vut.services.show \
              --directory=ok_dir --bogus)"
printf 'hwut.plan     %s      %s        %s      %s\n' \
    "$(status python3 -m vut.services.plan \
              --directory=ok_dir)" \
    "$(status python3 -m vut.services.plan \
              --directory=fault_dir)" \
    "$(status python3 -m vut.services.plan \
              --directory=ok_dir --bogus)" \
    "$(status python3 -m vut.services.plan \
              --directory=ok_dir --glob 'nothing-*')"
printf 'hwut.run      %s      %s        %s      %s\n' \
    "$(status python3 -m vut.services.run \
              --directory=run_ok)" \
    "$(status python3 -m vut.services.run \
              --directory=run_fault)" \
    "$(status python3 -m vut.services.run \
              --directory=run_ok --bogus)" \
    "$(status python3 -m vut.services.run \
              --directory=run_ok --glob 'nothing-*')"
printf 'steady\n'      > a.txt
printf 'different\n'   > b.txt
printf 'hwut.compare  %s      %s        %s      -\n' \
    "$(status python3 -m vut.services.compare \
              a.txt a.txt)" \
    "$(status python3 -m vut.services.compare \
              a.txt b.txt)" \
    "$(status python3 -m vut.services.compare)"
