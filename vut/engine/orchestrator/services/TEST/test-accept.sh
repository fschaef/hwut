#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
# ---------------------------------------------------------------------------
#
# THE 'hwut.accept' FACE, IN ITS NATURAL HABITAT: real runs record real
# candidates, then acceptance promotes them. What is under test:
#
#     bless      a candidate without a nominal becomes the FIRST pole
#     merge      a standing nominal is DETECTED and left alone;
#                '--force' overwrites it, said out loud
#     stderr     STDERR IS NEVER SUBJECT TO TESTING: it is never
#                promoted; where it SPOKE there is NO DEFAULT -- the
#                choice is refused until '--stderr-tol' notes IGNORED
#     sugar      the short form desugars into the wish's own '--glob'
#     ask        the interactive question shows the CANDIDATE and
#                anything but 'y' leaves the pole alone
#
# The wall clock is masked; fixture paths are relative.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../../../.." && pwd)
RUN="python3 -m vut.engine.orchestrator.services.run"
ACCEPT="python3 -m vut.engine.orchestrator.services.accept"
export PYTHONPATH="$ROOT"

case "$1" in
    --hwut-info)
        echo "The hwut.accept face: promotion, and what it refuses."
        echo "CHOICES: bless, merge, stderr, sugar, ask;"
        echo "HAPPY: STATUS: [0-9];"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

mask() { sed -E 's/[0-9]{2}:[0-9]{2}:[0-9]{2}/hh:mm:ss/g'; }

face() {                # <args...>  -- status, stdout
    $ACCEPT "$@" > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "STDOUT {"
    mask < out.txt | sed 's/^/    /'
    echo "}"
    if [ -s err.txt ]; then
        echo "STDERR {"; mask < err.txt | sed 's/^/    /'; echo "}"
    fi
}

fixture() {             # one directory, one plain test, one two-choice
    rm -rf tree
    mkdir -p tree/suite/TEST
    printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n}\n' \
        > tree/suite/TEST/hwut.conf
    printf '#!/bin/bash\n# hwut { title = "Ok" }\necho "steady line"\n' \
        > tree/suite/TEST/test-ok.sh
    printf '#!/bin/bash\n# hwut { title = "Two"\n#        choices = ["a", "b"] }\necho "choice $1"\n' \
        > tree/suite/TEST/test-two.sh
    chmod +x tree/suite/TEST/*.sh
    $RUN --directory=tree --silent 2> /dev/null
}

good() { ls tree/suite/TEST/GOOD/ 2>/dev/null | grep -v result_db; }

case "$1" in

bless)
    #  No nominal stands: every stdout candidate becomes the first
    #  pole; stderr is NEVER among them.
    fixture
    face --directory=tree/suite/TEST --yes
    echo "GOOD holds:"
    good | sed 's/^/    /'
    ;;

merge)
    #  A nominal stands: DETECTED, named, left alone -- status 1.
    #  '--force' overwrites the pole, said out loud -- status 0.
    fixture
    $ACCEPT --directory=tree/suite/TEST --yes > /dev/null
    echo "== a second accept: the nominals stand =="
    face --directory=tree/suite/TEST --yes
    echo "== --force =="
    face --directory=tree/suite/TEST --yes --force
    ;;

stderr)
    #  STDERR IS NEVER SUBJECT TO TESTING. Where it SPOKE there is no
    #  default: refused by name with both remedies; '--stderr-tol'
    #  notes IGNORED, and the note GOVERNS -- the re-run is green.
    fixture
    printf '#!/bin/bash\n# hwut { title = "Ok" }\necho "steady line"\necho "a warning" >&2\n' \
        > tree/suite/TEST/test-ok.sh
    chmod +x tree/suite/TEST/test-ok.sh
    $RUN --directory=tree --silent 2> /dev/null
    echo "== stderr spoke, no flag =="
    face --directory=tree/suite/TEST --yes
    echo "== --stderr-tol =="
    face --directory=tree/suite/TEST --yes --stderr-tol
    echo "== the note governs: the suite re-runs green =="
    $RUN --directory=tree --silent 2> /dev/null
    echo "run status: $?"
    echo "GOOD holds (no stderr nominal):"
    good | sed 's/^/    /'
    ;;

sugar)
    #  The short form is SUGAR over '--glob': the first word names
    #  files, every further word a choice. One selection language.
    fixture
    echo "== hwut.accept 'test-two.sh' a =="
    face --directory=tree/suite/TEST --yes "test-two.sh" a
    echo "GOOD holds:"
    good | sed 's/^/    /'
    echo "== the same thing, spelled as the wish =="
    fixture
    face --directory=tree/suite/TEST --yes --glob "test-two.sh a"
    echo "GOOD holds:"
    good | sed 's/^/    /'
    ;;

ask)
    #  Interactive: the CANDIDATE is shown -- what the framework
    #  compares -- and anything but 'y' leaves the pole alone.
    fixture
    printf 'y\nn\n' | $ACCEPT --directory=tree/suite/TEST \
        > out.txt 2> /dev/null
    echo "STATUS: $?"
    mask < out.txt | sed 's/^/    /'
    echo "GOOD holds (first blessed, second left alone):"
    good | sed 's/^/    /'
    ;;

*)
    echo "unknown choice '$1'"
    exit 1 ;;
esac
