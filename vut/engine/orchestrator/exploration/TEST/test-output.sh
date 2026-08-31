#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "The 'output' parameter: declared subjects, files included."
#     choices    = ["cycle", "declare", "forgotten", "refuse"]
#     eq-pattern = ["STATUS: [0-9]"]
# }
#
# ---------------------------------------------------------------------------
#
# THE 'output' PARAMETER (todo-1): a test STATES what it produces.
# Absent, the subject is '<stdout>' alone; stated, the list names the
# subjects -- '<stdout>' the one channel name, every other entry a
# FILE read AFTER the run has ended.
#
# THE THREE LAWS on display here:
#   (1) STDERR IS NEVER SUBJECT TO TESTING -- '<stderr>' is refused
#       at validation, by name, with the reason.
#   (2) A FILE IS READ ONLY AFTER TERMINATION -- and then REMOVED:
#       the transport leaves no residue, so a stale file can never
#       green a run that stopped producing it.
#   (3) PYPE-ING IS ONLY EVER APPLIED TO STDOUT.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../../../.." && pwd)
RUN="python3 -m vut.services.run"
ACCEPT="python3 -m vut.services.accept"
export PYTHONPATH="$ROOT"

case "$1" in
    --hwut-info)
        echo "The 'output' parameter: declared subjects, files included.;"
        echo "CHOICES: declare, refuse, cycle, forgotten;"
        echo "HAPPY: STATUS: [0-9];"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

#  THE TREE'S BOUNDARY. Every face ASCENDS collecting 'hwut.conf'
#  until it meets this file; a tree without one is refused, so a
#  fixture states its own. Empty says only 'the tree ends here'.
printf 'hwut {\n}\n' > hwut-root.conf

mask() { sed -E 's/[0-9]{2}:[0-9]{2}:[0-9]{2}/hh:mm:ss/g'; }

fixture() {             # the app writes stdout AND result.csv
    rm -rf tree
    mkdir -p tree/suite/TEST
    printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n}\n' \
        > tree/suite/TEST/hwut.conf
    printf '#!/bin/bash\n# @hwut { title = "File subject"\n#        output = ["<stdout>", "result.csv"] }\necho "on the channel"\nprintf "a,b\\\\n1,2\\\\n" > result.csv\necho "<hwut-end>"\n' \
        > tree/suite/TEST/test-file.sh
    chmod +x tree/suite/TEST/test-file.sh
}

case "$1" in

declare)
    #  The parsed declaration, read back from exploration.
    fixture
    python3 - <<'PYEOF'
from vut.engine.orchestrator.exploration.explorer import explore
result = explore("tree/suite/TEST")
for fault in result.fault_list: print("FAULT: %s" % fault)
for app in sorted(result.app_set, key=lambda a: a.source_file):
    print("%-14s output = %s"
          % (app.source_file, app.choice_db[None].output))
PYEOF
    echo "STATUS: $?"
    ;;

refuse)
    #  '<stderr>' and every other malformation, refused by name.
    mkdir -p bad
    printf '#!/bin/bash\n# @hwut { title = "A"\n#        output = ["<stdout>", "<stderr>"] }\necho x\n' > bad/test-a.sh
    printf '#!/bin/bash\n# @hwut { title = "B"\n#        output = ["<stdin>"] }\necho x\n'  > bad/test-b.sh
    printf '#!/bin/bash\n# @hwut { title = "C"\n#        output = ["a.log", "a.log"] }\necho x\n' > bad/test-c.sh
    printf '#!/bin/bash\n# @hwut { title = "D"\n#        output = ["-dash.log"] }\necho x\n'      > bad/test-d.sh
    chmod +x bad/*.sh
    python3 - <<'PYEOF'
from vut.engine.orchestrator.exploration.explorer import explore
for fault in explore("bad").fault_list:
    print("FAULT: %s" % fault)
PYEOF
    echo "STATUS: $?"
    ;;

cycle)
    #  Declare -> run records the file as a CANDIDATE, no residue ->
    #  accept blesses it beside stdout -> the re-run is green.
    fixture
    $RUN --directory=tree --silent 2> /dev/null
    echo "first run (no nominal yet): status $?"
    echo "residue in the test directory: $(ls tree/suite/TEST | grep -c result.csv)"
    echo "candidates:"
    ls tree/suite/TEST/TMP/store/ | grep -v when | sed 's/^/    /'
    $ACCEPT --directory=tree/suite/TEST --yes > /dev/null 2>&1
    echo "accepted: status $?"
    echo "nominals:"
    ls tree/suite/TEST/GOOD/ | grep -v result_db | sed 's/^/    /'
    $RUN --directory=tree --silent 2> /dev/null
    echo "STATUS: $?"
    ;;

forgotten)
    #  The application stops producing the declared file: the verdict
    #  'output-file-not-found', phrased, status 1 -- a stale file from
    #  the earlier run CANNOT green this one (it was removed).
    fixture
    $RUN --directory=tree --silent 2> /dev/null
    $ACCEPT --directory=tree/suite/TEST --yes > /dev/null 2>&1
    printf '#!/bin/bash\n# @hwut { title = "File subject"\n#        output = ["<stdout>", "result.csv"] }\necho "on the channel"\necho "<hwut-end>"\n' \
        > tree/suite/TEST/test-file.sh
    chmod +x tree/suite/TEST/test-file.sh
    $RUN --directory=tree --quiet > run.txt 2> /dev/null
    echo "STATUS: $?"
    mask < run.txt | sed 's/^/    /'
    ;;

*)
    echo "unknown choice '$1'"
    exit 1 ;;
esac
