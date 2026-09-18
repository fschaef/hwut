#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "hwut.labels.list: every label, with a count beside it."
#     choices    = ["counts", "empty", "refused"]
#     tolerance { eq_pattern = ["STATUS: [0-9]"] }
# }
#
# ---------------------------------------------------------------------------
#
# 'hwut.labels.list' -- every label that stands, with THE NUMBER OF
# MEMBERS beside it (disc-8). The number is a COUNT, never a handle:
# numbering for reference invites '--label 3', and a number that
# shifts when a label is added is a target that moves under the
# author.
#
# counts      labels with their member counts, sorted by name.
# empty       a tree that labels nothing prints NOTHING AT ALL; the
#             status carries the news.
# refused     an argument the face does not take, by name.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../../../.." && pwd)
export PYTHONPATH="$ROOT"
CREATE="python3 -m vut.services.lib.labels.create"
ADD="python3 -m vut.services.lib.labels.add"
LIST="python3 -m vut.services.lib.labels.list"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "hwut.labels.list: every label, with a count beside it.;"
        echo "CHOICES: counts, empty, refused;"
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

counts)
    fixture
    $CREATE concern --glob "test-b.sh"                        > /dev/null
    $ADD    meta    --glob "tree/storage/TEST/test-a.sh"      > /dev/null
    $CREATE slow    --glob "tree/messaging/*/TEST/test-a.sh one" \
                                                              > /dev/null
    face "$LIST"
    ;;

empty)
    fixture
    face "$LIST"
    ;;

refused)
    fixture
    face "$LIST" --sideways
    ;;

*)
    echo "no such choice: $1"
    exit 1 ;;
esac

#  THE STREAM COMPLETED (R-70).
echo "<hwut-end>"
