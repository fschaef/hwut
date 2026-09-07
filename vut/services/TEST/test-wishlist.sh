#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "The hwut.wishlist face: the list, printed and spent."
#     choices    = ["elided", "empty", "labels", "print", "refused",
#                   "roundtrip", "select", "short-form", "spent",
#                   "travels"]
#     tolerance { eq_pattern = ["STATUS: [0-9]"] }
# }
#
# ---------------------------------------------------------------------------
#
# THE 'hwut.wishlist' FACE AND THE '--wishlist' KEYWORD -- the list,
# printed and spent.
#
# print       every case the wish selects, one wishlist line each, in
#             walk order; a choice-less test prints its file alone.
# short-form  the short form of HWUT 1.0: bare words are targets,
#             the first naming files, each further one a choice --
#             sugar for '--glob', so the two spell one selection.
# labels      the silence is THE WISH'S (disc-8): a bare
#             'hwut.wishlist' does not print what the standard label
#             silences, so its output and 'hwut.run --wishlist' of it
#             select ONE set and the disc-5 round trip closes over
#             labels too; '--label' lifts and composes.
# elided      a SORTED list may elide (disc-8): ':/' dittos the
#             previous line's directory, ':/:' its file, a choice
#             following; the reader takes both forms, and a ditto
#             with no predecessor is refused by name.
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
        echo "CHOICES: print, select, roundtrip, travels, spent, empty, elided, labels, short-form, refused;"
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
        printf '#!/bin/bash\n# @hwut { title = "A"  choices = ["one", "two"] }\necho "line $1"\necho "<hwut-end>"\n' \
            > "tree/$where/TEST/test-a.sh"
        printf '#!/bin/bash\n# @hwut { title = "B" }\necho "b"\necho "<hwut-end>"\n' \
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

short-form)
    #  Sugar and long form must select the same runs.
    fixture
    echo "--- 'test-a.sh one': app and choice"
    face --directory=tree test-a.sh one
    echo "--- the same as '--glob'"
    face --directory=tree --glob "test-a.sh one"
    echo "--- one app, every choice of it"
    face --directory=tree test-a.sh
    echo "--- two choices of one app"
    face --directory=tree test-a.sh one two
    ;;

labels)
    #  One set, both directions: what a bare wishlist prints is what
    #  a bare run takes -- the silence lives in the wish they share.
    fixture
    python3 -m vut.services.lib.labels.add meta \
        --glob "tree/messaging/*/TEST/test-a.sh one" > /dev/null
    echo "--- bare: the silenced runs are not printed"
    face --directory=tree
    echo "--- '--label meta': the silence lifted, the two alone"
    face --directory=tree --label meta
    echo "--- '--label all AND NOT meta' spells the bare wish"
    face --directory=tree --label "all AND NOT meta"
    echo "--- a LITERAL target overrides the silence"
    face --directory=tree messaging/net/TEST/test-a.sh one
    echo "--- a GLOB does not; wholly swallowed, it warns"
    face --directory=tree "messaging/net/TEST/test-a.s?" one
    echo "--- a label that does not stand, refused by name"
    face --directory=tree --label cocnern
    ;;

elided)
    #  The reader takes the elided forms; only a SORTED writer emits
    #  them, which 'hwut.wishlist' is not: its walk order would make
    #  the ditto fire almost never and suggest an adjacency the file
    #  does not have.
    fixture
    cat > tree/short.txt <<'LIST'
./messaging/net/TEST/test-a.sh one
:/: two
:/test-b.sh
./storage/TEST/test-a.sh one
LIST
    echo "THE FILE {"; sed 's/^/    /' < tree/short.txt; echo "}"
    echo "READ BACK, expanded:"
    face --directory=tree --wishlist tree/short.txt

    echo "--- a ditto with no predecessor, refused by name"
    printf ':/test-b.sh\n' > tree/first.txt
    face --directory=tree --wishlist tree/first.txt

    echo "--- ':/:' without a choice, refused by name"
    printf './storage/TEST/test-a.sh one\n:/:\n' > tree/bare.txt
    face --directory=tree --wishlist tree/bare.txt

    echo "--- a lone ':' is no elision mark"
    printf './storage/TEST/test-a.sh one\n:sideways\n' > tree/lone.txt
    face --directory=tree --wishlist tree/lone.txt
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

echo "<hwut-end>"
