#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
# ---------------------------------------------------------------------------
#
# THE 'hwut.run' FACE, IN ITS NATURAL HABITAT: real bash test
# applications under the real dispatcher, driven from the shell. The
# wall clock is the user's stopwatch and no GOOD's business -- every
# 'hh:mm:ss' is masked by ONE substitution before comparison.
#
# EXIT STATUS under test (E-1): 0 green, 1 a test failed or a fault
# was met, 2 the command line cannot be read, 3 it reads and asks for
# nothing.
#
# THE COLOUR DECISION under test, not the escapes' spelling: piped is
# plain; '--colour' enforces, 'NO_COLOR' notwithstanding;
# '--no-colour' refuses.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../../.." && pwd)
RUN="python3 -m vut.engine.orchestrator.services.run"
export PYTHONPATH="$ROOT"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "The hwut.run face: the tree run, rendered live."
        echo "CHOICES: green, fail, nostore, empty, refused, tiers, colour;"
        echo "HAPPY: STATUS: [0-9];"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

mask() {                # hh:mm:ss -> the one masked token
    sed -E 's/[0-9]{2}:[0-9]{2}:[0-9]{2}/hh:mm:ss/g'
}

face() {                # <args...>  -- status, masked stdout, stderr
    $RUN "$@" > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "STDOUT {"
    mask < out.txt | sed 's/^/    /'
    echo "}"
    if [ -s err.txt ]; then
        echo "STDERR {"
        mask < err.txt | sed 's/^/    /'
        echo "}"
    fi
}

put() {                 # <path> <content...>
    printf '%s\n' "$2" > "$1"
}

fixture_green() {       # one directory, one passing test
    mkdir -p tree/suite/TEST/GOOD
    printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n}\n' \
        > tree/suite/TEST/hwut.conf
    printf '#!/bin/bash\n# hwut { title = "Ok" }\necho "steady line"\n' \
        > tree/suite/TEST/test-ok.sh
    chmod +x tree/suite/TEST/test-ok.sh
    put tree/suite/TEST/GOOD/test-ok.stdout "steady line"
}

fixture_fail() {        # the green one, one differing test beside it
    fixture_green
    printf '#!/bin/bash\n# hwut { title = "Diff" }\necho "what the run says"\n' \
        > tree/suite/TEST/test-diff.sh
    chmod +x tree/suite/TEST/test-diff.sh
    put tree/suite/TEST/GOOD/test-diff.stdout "what the GOOD expects"
}

fixture_fault() {       # a dependency the directory does not offer
    fixture_green
    printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n    dependency { "test-ok.sh" = ["required.dat"] }\n}\n' \
        > tree/suite/TEST/hwut.conf
}

case "$1" in

green)
    #  Everything stands: the flow, the roll-call, status 0.
    fixture_green
    face --directory=tree
    ;;

fail)
    #  One test differs: its phrase inline, the FAILURES block,
    #  status 1.
    fixture_fail
    face --directory=tree
    ;;

nostore)
    #  The store knob: '--no-store' leaves no candidate behind;
    #  the default records the subject beside its freshness sidecar.
    fixture_green
    face --directory=tree --no-store > /dev/null
    n=$(find tree -name "*.stdout" -not -path "*/GOOD/*" | wc -l)
    echo "candidates after --no-store: $n"
    rm -rf tree; fixture_green
    face --directory=tree > /dev/null
    n=$(find tree -name "*.stdout" -not -path "*/GOOD/*" | wc -l)
    s=$(find tree -name "*.when" | wc -l)
    echo "candidates after the default: $n   freshness sidecars: $s"
    ;;

empty)
    #  The command line reads, and asks for nothing: status 3.
    fixture_green
    face --directory=tree --glob 'nothing-*'
    ;;

refused)
    #  Refused at the door, by name, with the usage line: status 2.
    fixture_green
    echo "== a directory that does not exist =="
    face --directory=nowhere-such-dir
    echo "== an option nobody knows =="
    face --directory=tree --frobnicate
    echo "== tiers beside one another =="
    face --directory=tree --silent --verbose
    echo "== colour beside no-colour =="
    face --directory=tree --colour --no-colour
    echo "== jobs without a number =="
    face --directory=tree --jobs=many
    ;;

tiers)
    #  QUIET keeps the closing blocks and the FAULTS met; SILENT
    #  keeps nothing on stdout and the fault on stderr, prefixed.
    fixture_fault
    echo "== --quiet =="
    face --directory=tree --quiet
    echo "== --silent =="
    face --directory=tree --silent
    echo "== --plain, statable redundantly =="
    fixture_green
    face --directory=tree --plain > plain.txt
    head -1 plain.txt
    ;;

colour)
    #  THE DECISION, not the escapes' spelling: presence alone.
    fixture_green
    verdict() {         # <label> <args...>
        label=$1; shift
        $RUN --directory=tree "$@" > c.txt 2> /dev/null
        n=$(tr -cd '\033' < c.txt | wc -c)
        if [ "$n" -gt 0 ]; then echo "$label: escapes present"
        else                    echo "$label: plain"
        fi
    }
    verdict "piped, nothing spoken     "
    verdict "--colour                  " --colour
    NO_COLOR=1 verdict "--colour, NO_COLOR set    " --colour
    verdict "--no-colour               " --no-colour
    ;;

*)
    echo "unknown choice '$1'"
    exit 1 ;;
esac
