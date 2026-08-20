#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
# ---------------------------------------------------------------------------
#
# THE EXIT STATUS LAW (E-1), TESTED AS A TABLE: one enum,
# 'E_ExitCode', and every face driven over the same four stimuli --
# a good line, a fault, an unreadable line, an empty selection. A
# face that disagrees with the law shows as a divergent cell, not as
# a comment nobody read. '-' marks a stimulus a face cannot express.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../../../.." && pwd)
export PYTHONPATH="$ROOT"

case "$1" in
    --hwut-info)
        echo "The exit status law: one enum, every face relates."
        echo "CHOICES: law;"
        echo "HAPPY: [0-9]+;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

echo "THE ENUM (services/_exit.py):"
python3 - <<'PYEOF'
from vut.engine.orchestrator.services._exit import E_ExitCode
for member in E_ExitCode:
    print("    %-8s = %d" % (member.name, member.value))
PYEOF

#  The stimuli, one directory each. ---------------------------------------
mkdir -p ok_dir/GOOD
printf '#!/bin/bash\n# hwut { title = "Ok" }\necho "steady line"\n' \
    > ok_dir/test-ok.sh
chmod +x ok_dir/test-ok.sh
printf 'steady line\n' > ok_dir/GOOD/test-ok.stdout

mkdir -p fault_dir
printf '#!/bin/bash\n# hwut { title = %s\necho x\n' '"broken' \
    > fault_dir/test-broken.sh
chmod +x fault_dir/test-broken.sh

mkdir -p run_ok/suite/TEST run_fault/suite/TEST
cp -r ok_dir/.    run_ok/suite/TEST/
cp -r fault_dir/. run_fault/suite/TEST/
printf 'hwut {\n    on_entry = "true"\n    on_exit = "true"\n}\n' \
    | tee run_ok/suite/TEST/hwut.conf > run_fault/suite/TEST/hwut.conf

status() { "$@" > /dev/null 2>&1; echo -n "$?"; }

echo
echo "FACE         OK  FAULT  REFUSED  EMPTY"
printf 'hwut.show     %s      %s        %s      -\n' \
    "$(status python3 -m vut.engine.orchestrator.services.show \
              --directory=ok_dir)" \
    "$(status python3 -m vut.engine.orchestrator.services.show \
              --directory=fault_dir)" \
    "$(status python3 -m vut.engine.orchestrator.services.show \
              --directory=ok_dir --bogus)"
printf 'hwut.plan     %s      %s        %s      %s\n' \
    "$(status python3 -m vut.engine.orchestrator.services.plan \
              --directory=ok_dir)" \
    "$(status python3 -m vut.engine.orchestrator.services.plan \
              --directory=fault_dir)" \
    "$(status python3 -m vut.engine.orchestrator.services.plan \
              --directory=ok_dir --bogus)" \
    "$(status python3 -m vut.engine.orchestrator.services.plan \
              --directory=ok_dir --glob 'nothing-*')"
printf 'hwut.run      %s      %s        %s      %s\n' \
    "$(status python3 -m vut.engine.orchestrator.services.run \
              --directory=run_ok)" \
    "$(status python3 -m vut.engine.orchestrator.services.run \
              --directory=run_fault)" \
    "$(status python3 -m vut.engine.orchestrator.services.run \
              --directory=run_ok --bogus)" \
    "$(status python3 -m vut.engine.orchestrator.services.run \
              --directory=run_ok --glob 'nothing-*')"
printf 'steady\n'      > a.txt
printf 'different\n'   > b.txt
printf 'hwut.compare  %s      %s        %s      -\n' \
    "$(status python3 -m vut.engine.orchestrator.services.compare \
              a.txt a.txt)" \
    "$(status python3 -m vut.engine.orchestrator.services.compare \
              a.txt b.txt)" \
    "$(status python3 -m vut.engine.orchestrator.services.compare)"
