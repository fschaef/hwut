#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "The exit status law: one enum, every face relates."
#     features   = ["face-exit-status-law", "face-signal-ends-quietly",
#                   "face-teardown-noise-to-file"]
#     choices    = ["law", "signal", "unraisable"]
# }
#
# NO TOLERANCE ON NUMBERS: the numbers are the subject. (Measured
# 2026-10-10: 'eq_pattern = ["[0-9]+"]' stood here, any status equalled
# any other, and the page's GOOD recorded 'hwut.run 1 1 2 1' under a
# law that says 0 1 2 3 -- three stale stimuli, hidden for weeks.)
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
        echo "CHOICES: law, signal, unraisable;"
        exit 0 ;;
esac

#  EVERY CHOICE IN A SCRATCH DIRECTORY. 'signal' once built its tree in
#  the page's own directory: 'tree/', 'out.txt' and 'err.txt' were left
#  in 'services/TEST' and committed (2026-09-10), and each run wrote a
#  book into 'tree/suite/TEST/GOOD/'.
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

case "${1:-law}" in

law)

#  THE TREE'S BOUNDARY. Every face ASCENDS collecting 'hwut.conf'
#  until it meets this file; a tree without one is refused, so a
#  fixture states its own. Empty says only 'the tree ends here'.
printf 'hwut {\n}\n' > hwut-root.conf

echo "THE ENUM (services/_exit.py):"
python3 - <<'PYEOF'
from hwut.services._exit import E_ExitCode
for member in E_ExitCode:
    print("    %-8s = %d" % (member.name, member.value))
PYEOF

#  The stimuli, one directory each. ---------------------------------------
mkdir -p ok_dir/GOOD
printf '#!/bin/bash\n# @hwut { title = "Ok" }\necho "steady line"\necho "<hwut-end>"\n' \
    > ok_dir/test-ok.sh
chmod +x ok_dir/test-ok.sh
printf 'steady line\n<hwut-end>\n' > ok_dir/GOOD/test-ok.sh.txt

#  A REAL FAULT: a dependency CYCLE, which the plan cannot satisfy.
#  (It was a test with an unterminated header, which the reader passes
#  over in silence -- the file simply is not a test application. The
#  '1' that column showed came from an ImportError in the interview,
#  not from a fault: a GOOD recorded over a crash.)
mkdir -p fault_dir
printf 'hwut {\n    on_entry = "true"\n    on_exit = "true"\n    dependency { "test-a.sh" = ["test-b.sh"]  "test-b.sh" = ["test-a.sh"] }\n}\n' \
    > fault_dir/hwut.conf
for name in a b; do
    printf '#!/bin/bash\n# @hwut { title = "T" }\necho x\n' \
        > "fault_dir/test-$name.sh"
    chmod +x "fault_dir/test-$name.sh"
done

mkdir -p run_ok/suite/TEST run_fault/suite/TEST
cp -r ok_dir/.    run_ok/suite/TEST/
cp -r fault_dir/. run_fault/suite/TEST/
printf 'hwut {\n    on_entry = "true"\n    on_exit = "true"\n}\n' \
    > run_ok/suite/TEST/hwut.conf

status() { "$@" > /dev/null 2>&1; echo -n "$?"; }

echo
echo "FACE                OK  FAULT  REFUSED  EMPTY"
printf 'hwut.config.show    %s      %s        %s      -\n' \
    "$(status python3 -m hwut.services.lib.config.show \
              --directory=ok_dir)" \
    "$(status python3 -m hwut.services.lib.config.show \
              --directory=fault_dir)" \
    "$(status python3 -m hwut.services.lib.config.show \
              --directory=ok_dir --bogus)"
printf 'hwut.plan           %s      %s        %s      %s\n' \
    "$(status python3 -m hwut.services.plan \
              --directory=ok_dir)" \
    "$(status python3 -m hwut.services.plan \
              --directory=fault_dir)" \
    "$(status python3 -m hwut.services.plan \
              --directory=ok_dir --bogus)" \
    "$(status python3 -m hwut.services.plan \
              --directory=ok_dir --glob 'nothing-*')"
printf 'hwut.run            %s      %s        %s      %s\n' \
    "$(status python3 -m hwut.services.run \
              --directory=run_ok)" \
    "$(status python3 -m hwut.services.run \
              --directory=run_fault)" \
    "$(status python3 -m hwut.services.run \
              --directory=run_ok --bogus)" \
    "$(status python3 -m hwut.services.run \
              --directory=run_ok --glob 'nothing-*')"
printf 'steady\n'      > a.txt
printf 'different\n'   > b.txt
printf 'on: <else> => flush;\non: <eof> => ignore;\n' > ok.pype
printf 'on: bad\n'              > broken.pype
printf 'hwut.pype           %s      %s        %s      -\n' \
    "$(status python3 -m hwut.services.pype ok.pype a.txt)" \
    "$(status python3 -m hwut.services.pype broken.pype a.txt)" \
    "$(status python3 -m hwut.services.pype)"
printf 'hwut.diff           %s      %s        %s      -\n' \
    "$(status python3 -m hwut.services.lib.run.diff \
              a.txt a.txt)" \
    "$(status python3 -m hwut.services.lib.run.diff \
              a.txt b.txt)" \
    "$(status python3 -m hwut.services.lib.run.diff --bogus)"

    ;;

signal)
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55): one line on
    #  stderr, the shell's own code, and NO TRACEBACK -- what the
    #  interpreter would print is the face's innards, and the person
    #  asked it to stop, not to read them.
    mkdir -p tree/suite/TEST/GOOD
    printf 'hwut {\n}\n' > tree/hwut-root.conf
    printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n}\n' \
        > tree/suite/TEST/hwut.conf
    printf '#!/bin/bash\n# @hwut { title = "Slow" }\nsleep 30\necho "<hwut-end>"\n' \
        > tree/suite/TEST/test-slow.sh
    chmod +x tree/suite/TEST/test-slow.sh
    printf 'x\n' > tree/suite/TEST/GOOD/test-slow.sh.txt

    echo "STIMULUS  a run under way, then SIGTERM"
    python3 -m hwut.services.run --directory=tree --plain > out.txt 2> err.txt &
    victim=$!
    sleep 3
    kill -TERM $victim
    wait $victim
    echo "REACTION  exit code : $?    (the shell's 128 + 15)"
    echo "          stderr {"; sed 's/^/              /' err.txt; echo "          }"
    echo "          tracebacks in stderr : $(grep -c Traceback err.txt)"
    echo
    echo "STIMULUS  the guard itself, on Ctrl-C's own exception"
    python3 -c "
from hwut.services._exit import guarded
def boom(): raise KeyboardInterrupt
print('exit code : %d' % int(guarded('hwut.run', boom)))" > out.txt 2> err.txt
    sed 's/^/          /' out.txt
    echo "          stderr {"; sed 's/^/              /' err.txt; echo "          }"
    echo
    echo "One line names the face and the ending; the shell reads the"
    echo "signal's own code; nothing of the innards is shown."
    echo "SUCCESS: a signal ends a face, it does not crash it."
    ;;

unraisable)
    #  THE TEARDOWN'S UNRAISABLES GO TO A FILE (E-225, 2026-11-14).
    #  MEASURED before: a 'hwut.run' that ended well printed, under
    #  'RESULTS', 'Exception ignored in: <function BaseSubprocessTransport
    #  .__del__>' and 'RuntimeError: Event loop is closed' (Python 3.12).
    #  The stimulus is a '__del__' that raises: Python's own leak of a
    #  transport does not arise on every version, a raising '__del__'
    #  does. The file's name holds the person: TMPDIR points it here.
    export TMPDIR="$WORK"
    cat > leaky.py <<'PYEOF'
import sys
from hwut.services._exit import guarded

class Leaky:
    def __del__(self):
        raise RuntimeError("Event loop is closed")

def main():
    first, second = Leaky(), Leaky()
    print("RESULTS: 1 ok, 0 fail")
    del first, second            # two unraisables, one NOTE line
    return 0

sys.exit(int(guarded("hwut.run", main)))
PYEOF
    show() {
        echo "          exit code : $1"
        echo "          stdout {"; sed 's/^/              /' out.txt; echo "          }"
        echo "          stderr {"
        sed -e "s#$WORK#<tmp>#g" -e 's#hwut-unraisable-[^/"]*\.txt#hwut-unraisable-<user>.txt#' \
            -e 's/at 0x[0-9a-f]*/at <address>/' err.txt | grep -v '^  ' | sed 's/^/              /'
        echo "          }"
        echo "          tracebacks in stderr : $(grep -c Traceback err.txt)"
    }

    echo "STIMULUS  a face ends well; two objects fail in '__del__'"
    python3 leaky.py > out.txt 2> err.txt; show $?
    file=$(ls "$WORK"/hwut-unraisable-*.txt)
    echo "          the file {"
    echo "              entries    : $(grep -c '^=== hwut.run (pid' "$file")"
    echo "              tracebacks : $(grep -c '^Traceback' "$file")"
    echo "              last line  : $(tail -1 "$file")"
    echo "          }"
    echo
    echo "STIMULUS  the same, the guard stood aside (VUT_DEBUG_EXCEPTION=1)"
    #  Python's own words differ between versions: counted, not shown.
    VUT_DEBUG_EXCEPTION=1 python3 leaky.py > out.txt 2> err.txt
    echo "          exit code : $?"
    echo "          NOTE lines in stderr : $(grep -c '^NOTE' err.txt)"
    echo "          tracebacks in stderr : $(grep -c Traceback err.txt)"
    echo
    echo "No traceback reaches the command line where the face ends; the"
    echo "evidence is kept in a file the one NOTE line names."
    echo "SUCCESS: the teardown's noise goes to a file, said once."
    ;;

*)
    echo "no such choice: $1" >&2
    exit 1 ;;
esac
echo "<hwut-end>"
