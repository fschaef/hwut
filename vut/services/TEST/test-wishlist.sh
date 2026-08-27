#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# hwut {
#     title      = "The hwut.wishlist face: the list, printed and spent."
#     choices    = ["empty", "print", "refused", "roundtrip", "select",
#                   "spent", "travels"]
#     eq-pattern = ["STATUS: [0-9]"]
# }
#
# ---------------------------------------------------------------------------
#
# THE 'hwut.wishlist' FACE AND THE '--wishlist' KEYWORD -- the list,
# printed and spent.
#
# print       every case the wish selects, one wishlist line each, in
#             walk order; a choice-less test prints its file alone.
# select      the wish narrows it: a bare name across every directory,
#             a PATH-BEARING glob across the tree, a path and a choice.
# roundtrip   THE POINT: print to a file, comment a line out, read it
#             back -- what returns is what was left standing.
# travels     a list living INSIDE the subtree it describes: its './'
#             is its OWN directory, so it reads back the same wherever
#             the run is rooted.
# spent       'hwut.run --wishlist' runs exactly the listed cases and
#             nothing else.
# refused     a wishlist that is not there; '--wishlist' with no file;
#             an unknown option; a directory that is not there.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
FACE="python3 -m vut.services.wishlist"
RUN="python3 -m vut.services.run"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "The hwut.wishlist face: the list, printed and spent.;"
        echo "CHOICES: print, select, roundtrip, travels, spent, empty, refused;"
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

face() {                # <args...> -- status and stdout
    $FACE "$@" > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "STDOUT {"; sed 's/^/    /' < out.txt; echo "}"
    if [ -s err.txt ]; then
        echo "STDERR {"; sed 's/^/    /' < err.txt; echo "}"
    fi
}

fixture() {             # three directories, two apps each
    for where in messaging/queue messaging/net storage; do
        mkdir -p "tree/$where/TEST/GOOD"
        printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n}\n' \
            > "tree/$where/TEST/hwut.conf"
        printf '#!/bin/bash\n# hwut { title = "A"  choices = ["one", "two"] }\necho "line $1"\necho "<hwut-end>"\n' \
            > "tree/$where/TEST/test-a.sh"
        printf '#!/bin/bash\n# hwut { title = "B" }\necho "b"\necho "<hwut-end>"\n' \
            > "tree/$where/TEST/test-b.sh"
        chmod +x "tree/$where/TEST/"*.sh
    done
}

# ---------------------------------------------------------------------------
case "$1" in

print)
    #  Everything, in walk order; the choice-less test prints bare.
    fixture
    face --directory=tree
    ;;

select)
    #  The wish narrows it, three ways.
    fixture
    echo "--- a bare name, matched in every directory"
    face --directory=tree --glob "test-b.sh"
    echo "--- a PATH-BEARING glob, across the tree"
    face --directory=tree --glob "messaging/*/test-a.sh"
    echo "--- a path AND a choice"
    face --directory=tree --glob "messaging/queue/TEST/test-a.sh one"
    ;;

roundtrip)
    #  Print, comment a line out, read it back.
    fixture
    $FACE --directory=tree --glob "messaging/*/test-a.sh" \
        > tree/messaging.txt
    sed -i '1i # the messaging quick check -- kept by hand' \
        tree/messaging.txt
    sed -i 's|^\./messaging/net/TEST/test-a.sh two|# ./messaging/net/TEST/test-a.sh two   -- too slow|' \
        tree/messaging.txt
    echo "THE FILE {"; sed 's/^/    /' < tree/messaging.txt; echo "}"
    echo "READ BACK:"
    face --directory=tree --wishlist tree/messaging.txt
    ;;

travels)
    #  A list inside the subtree it describes: './' is its OWN ground.
    fixture
    $FACE --directory=tree --glob "messaging/queue/*" \
        | sed 's|^\./messaging/queue/|./|' > tree/messaging/queue/list.txt
    echo "THE FILE, beside the tests it names {"
    sed 's/^/    /' < tree/messaging/queue/list.txt
    echo "}"
    echo "READ BACK from the root:"
    face --directory=tree --wishlist tree/messaging/queue/list.txt
    ;;

spent)
    #  'hwut.run --wishlist' runs exactly those, and nothing else.
    fixture
    $FACE --directory=tree --glob "messaging/*/test-a.sh one" \
        > tree/quick.txt
    echo "THE LIST {"; sed 's/^/    /' < tree/quick.txt; echo "}"
    echo "WHAT RAN:"
    $RUN --directory=tree --wishlist tree/quick.txt --plain \
        > run.txt 2>&1
    echo "STATUS: $?"
    grep -E "\[START\]" run.txt | sed -E 's/^[0-9:]+ \| [0-9]+ \| /    /'
    ;;

empty)
    #  AN ENUMERATION'S EMPTINESS IS A STATEMENT. A list narrowed by
    #  commenting lines out must not, at the last line, explode into
    #  the whole tree -- which is the opposite of what the file says.
    #  The ABSENCE of any wish is not a statement and still means
    #  everything: the two are different questions.
    fixture

    echo "--- no wish at all: everything"
    $FACE --directory=tree | wc -l | sed 's/^/    cases: /'

    echo "--- a list with one line: that one"
    printf './storage/TEST/test-b.sh\n' > tree/one.txt
    face --directory=tree --wishlist tree/one.txt

    echo "--- the same list, its one line commented out"
    printf '# ./storage/TEST/test-b.sh   -- not today\n' > tree/none.txt
    face --directory=tree --wishlist tree/none.txt

    echo "--- a wholly empty file"
    : > tree/blank.txt
    face --directory=tree --wishlist tree/blank.txt

    echo "--- and a run over an empty list runs nothing"
    $RUN --directory=tree --wishlist tree/blank.txt --plain \
        > run.txt 2>&1
    echo "STATUS: $?"
    grep -cE "\[START\]" run.txt | sed 's/^/    started: /'
    ;;

refused)
    #  Every door, by name.
    fixture
    face --directory=tree --wishlist tree/nowhere.txt
    face --directory=tree --wishlist
    face --directory=tree --sideways
    face --directory=nowhere
    ;;

*)
    echo "no such choice: $1"
    exit 1 ;;
esac
