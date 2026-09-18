#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "hwut.labels.create: a NEW label, a snapshot of a wish."
#     choices    = ["doors", "empty", "snapshot", "union"]
#     tolerance { eq_pattern = ["STATUS: [0-9]"] }
# }
#
# ---------------------------------------------------------------------------
#
# 'hwut.labels.create <label> <wish>' -- a NEW label (disc-8).
#
# snapshot    a glob is SPENT at write time: the report names run by
#             run what the pattern caught, the file holds literal
#             targets, sorted, elided; creating the same label again
#             is refused, naming 'add'.
# union       '--label' inside the wish: a union among its labels,
#             narrowing against the rest of the wish.
# empty       a glob that met nothing WARNS by name; an empty
#             selection makes NO label -- an empty set is not a set
#             anybody wanted.
# doors       refused by name: a reserved name, a standard name, a
#             wish that states nothing, two labels, a label that
#             already stands.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../../../.." && pwd)
export PYTHONPATH="$ROOT"
CREATE="python3 -m vut.services.lib.labels.create"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "hwut.labels.create: a NEW label, a snapshot of a wish.;"
        echo "CHOICES: snapshot, union, empty, doors;"
        echo "HAPPY: STATUS: [0-9];"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

printf 'hwut {\n}\n' > hwut-root.conf

face() {                # <cmd> <args...> -- status, stdout, stderr
    local cmd="$1"; shift
    $cmd "$@" > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "STDOUT {"; sed 's/^/    /' < out.txt; echo "}"
    if [ -s err.txt ]; then
        echo "STDERR {"; sed 's/^/    /' < err.txt; echo "}"
    fi
}

the_file() {
    if [ -f hwut-root.labels ]; then
        echo "THE FILE {"; sed 's/^/    /' < hwut-root.labels; echo "}"
    else
        echo "THE FILE: absent -- no label exists"
    fi
}

fixture() {             # three directories, two apps each
    for where in messaging/queue messaging/net storage; do
        mkdir -p "tree/$where/TEST/GOOD"
        printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n}\n' \
            > "tree/$where/TEST/hwut.conf"
        printf '#!/bin/bash\n# @hwut { title = "A"  choices = ["one", "two"] }\necho "line $1"\necho "<hwut-end>"\n' \
            > "tree/$where/TEST/test-a.sh"
        printf '#!/bin/bash\n# @hwut { title = "B" }\necho "b"\necho "<hwut-end>"\n' \
            > "tree/$where/TEST/test-b.sh"
        chmod +x "tree/$where/TEST/"*.sh
    done
}

# ---------------------------------------------------------------------------
case "$1" in

snapshot)
    fixture
    echo "--- the glob is spent here, run by run"
    face "$CREATE" concern --glob "test-b.sh"
    the_file
    echo "--- the same label again, refused, 'add' named"
    face "$CREATE" concern --glob "test-a.sh"
    ;;

union)
    fixture
    face "$CREATE" east --glob "tree/messaging/*/TEST/test-b.sh" > /dev/null 2>&1
    face "$CREATE" west --glob "tree/storage/TEST/test-b.sh"     > /dev/null 2>&1
    echo "--- a union of two labels, narrowed by a glob"
    face "$CREATE" coast --label "east,west" --glob "tree/messaging/*"
    the_file
    ;;

empty)
    fixture
    echo "--- a glob that met nothing warns by name; no label is made"
    face "$CREATE" ghost --glob "test-queue.sh"
    the_file
    ;;

doors)
    fixture
    echo "--- a keyword"
    face "$CREATE" AND --glob "test-b.sh"
    echo "--- the universe"
    face "$CREATE" all --glob "test-b.sh"
    echo "--- the standard label"
    face "$CREATE" meta --glob "test-b.sh"
    echo "--- a wish that states nothing"
    face "$CREATE" concern
    echo "--- two labels"
    face "$CREATE" one two --glob "test-b.sh"
    ;;

*)
    echo "no such choice: $1"
    exit 1 ;;
esac

#  THE STREAM COMPLETED (R-70).
echo "<hwut-end>"
