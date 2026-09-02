#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "hwut.labels.add: grow a STANDING label."
#     choices    = ["doors", "grow", "standard"]
#     eq-pattern = ["STATUS: [0-9]"]
# }
#
# ---------------------------------------------------------------------------
#
# 'hwut.labels.add <label> <wish>' -- grow a STANDING label (disc-8).
#
# grow        '+' enrolled, '=' already carrying: the report states
#             which half of the selection was news; nothing rewritten
#             where nothing was news.
# standard    'meta' always stands and needs no create; labels
#             ACCUMULATE -- an application's entry and a choice's own
#             entry unite.
# doors       refused by name: a label that does not stand (naming
#             'create'), the universe, a wish that states nothing.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../../../.." && pwd)
export PYTHONPATH="$ROOT"
CREATE="python3 -m vut.services.lib.labels.create"
ADD="python3 -m vut.services.lib.labels.add"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "hwut.labels.add: grow a STANDING label.;"
        echo "CHOICES: grow, standard, doors;"
        echo "HAPPY: STATUS: [0-9];"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

printf 'hwut {\n}\n' > hwut-root.conf

face() {
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

fixture() {
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

grow)
    fixture
    $CREATE concern --glob "tree/messaging/*/TEST/test-b.sh" > /dev/null
    echo "--- half news, half already carrying"
    face "$ADD" concern --glob "test-b.sh"
    the_file
    ;;

standard)
    fixture
    echo "--- 'meta' needs no create"
    face "$ADD" meta --glob "tree/storage/TEST/test-a.sh"
    echo "--- labels accumulate: the choice's own entry adds to it"
    $CREATE concern --glob "tree/storage/TEST/test-a.sh one" > /dev/null
    the_file
    ;;

doors)
    fixture
    $CREATE concern --glob "test-b.sh" > /dev/null
    echo "--- a label that does not stand, 'create' named"
    face "$ADD" cocnern --glob "test-b.sh"
    echo "--- the universe"
    face "$ADD" all --glob "test-b.sh"
    echo "--- a wish that states nothing"
    face "$ADD" concern
    ;;

*)
    echo "no such choice: $1"
    exit 1 ;;
esac
