#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "hwut.labels.query: the runs a label expression names."
#     choices    = ["doors", "forms", "silence", "wishlist"]
#     tolerance { eq_pattern = ["STATUS: [0-9]"] }
# }
#
# ---------------------------------------------------------------------------
#
# 'hwut.labels.query [<expr>]' -- the runs an expression names
# (disc-8).
#
# wishlist    THE DEFAULT OUTPUT IS A WISHLIST: target lines, sorted,
#             ELIDED, nothing else -- and it PIPES BACK into
#             '--wishlist', so the round trip closes.
# forms       '--expand' one full target per line; '--labels' each
#             run with what it carries -- for looking, not for
#             wishlist-making.
# silence     bare is 'all AND NOT meta' -- what a bare run would
#             take; naming 'meta' lifts the silence; 'all' is the
#             universe; the grammar composes ('AND', 'NOT', ',').
# doors       refused by name: a label that does not stand, an
#             expression that cannot be read, two expressions, an
#             option the face does not take.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../../../.." && pwd)
export PYTHONPATH="$ROOT"
CREATE="python3 -m vut.services.lib.labels.create"
ADD="python3 -m vut.services.lib.labels.add"
QUERY="python3 -m vut.services.lib.labels.query"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "hwut.labels.query: the runs a label expression names.;"
        echo "CHOICES: wishlist, forms, silence, doors;"
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
    $CREATE concern --glob "test-b.sh"                   > /dev/null
    $ADD    meta    --glob "tree/messaging/*/TEST/test-a.sh one" \
                                                         > /dev/null
}

# ---------------------------------------------------------------------------
case "$1" in

wishlist)
    fixture
    echo "--- sorted, elided, ready to be read back"
    face "$QUERY" concern
    echo "--- and it PIPES BACK: the round trip closes"
    $QUERY "concern OR meta" > list.txt
    face "$CREATE" mixed --wishlist list.txt
    ;;

forms)
    fixture
    echo "--- '--expand': for eyes and for grep"
    face "$QUERY" "concern OR meta" --expand
    echo "--- '--labels': what each run carries; not a wishlist"
    face "$QUERY" "concern OR meta" --labels
    ;;

silence)
    fixture
    echo "--- bare is 'all AND NOT meta': what a bare run would take"
    face "$QUERY" --expand
    echo "--- naming 'meta' lifts the silence"
    face "$QUERY" meta --expand
    echo "--- 'all' is the universe"
    face "$QUERY" all --expand
    echo "--- the grammar composes"
    face "$QUERY" "all AND NOT (concern, meta)" --expand
    ;;

doors)
    fixture
    echo "--- a label that does not stand"
    face "$QUERY" "concren AND meta"
    echo "--- an expression that cannot be read"
    face "$QUERY" "concern AND"
    echo "--- two expressions"
    face "$QUERY" concern meta
    echo "--- an option the face does not take"
    face "$QUERY" --sideways
    ;;

*)
    echo "no such choice: $1"
    exit 1 ;;
esac
