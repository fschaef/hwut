#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "The removal faces: a test, or one choice, forgotten."
#     choices    = ["asking", "choice", "labels", "refused", "stain",
#                   "unknown", "untouched", "whole"]
#     eq-pattern = ["STATUS: [0-9]"]
# }
#
# ---------------------------------------------------------------------------
#
# THE 'hwut.remove' AND 'hwut.remove-choice' FACES -- a test, or one
# choice of it, forgotten.
#
# whole       a test entire: its nominal, its candidate and every
#             sidecar, its book entry, its register id. What stood
#             before and after is listed, so the loss is on the page.
# choice      ONE choice gone, the test's other choice standing --
#             its nominal, its candidate, its book entry, and no more.
# untouched   the test application, the 'hwut.conf' and 'OUT/' are the
#             author's and are never touched.
# unknown     a test the book never knew: nothing to forget is not an
#             error, and the face says so.
# asking      without '--yes' the whole list is shown and confirmed;
#             answering anything but yes removes nothing.
# stain       THE URGENT WAY OUT: a stained test removed, and running
#             again afterwards -- the stain went with the book entry.
# refused     the doors: an unknown option, a directory that is not
#             there, an odd number of words in the choice form, and
#             the empty command line.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
REMOVE="python3 -m vut.services.remove"
REMOVE_CHOICE="python3 -m vut.services.remove_choice"
RUN="python3 -m vut.services.run"
STABILITY="python3 -m vut.services.stability"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "The removal faces: a test, or one choice, forgotten.;"
        echo "CHOICES: whole, choice, untouched, unknown, asking, stain, labels, refused;"
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

mask() {                # THE ELAPSED STAMP IS THE MACHINE'S. A run
                        # line carries 'hh:mm:ss' and a run that
                        # crosses a second prints a different one --
                        # which is how this suite convicted itself.
    sed -E 's/[0-9]{2}:[0-9]{2}:[0-9]{2}/hh:mm:ss/g'
}

face() {                # <command> <args...> -- status and stdout
    local command="$1"; shift
    $command "$@" > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "STDOUT {"
    sed 's/^/    /' < out.txt
    echo "}"
    if [ -s err.txt ]; then
        echo "STDERR {"; sed 's/^/    /' < err.txt; echo "}"
    fi
}

standing() {            # <label> -- what the framework holds, sorted
    echo "$1 {"
    ( cd tree/suite/TEST \
      && find GOOD TMP/store -type f 2>/dev/null | sort \
         | sed 's/^/    /' )
    echo "    book: $(python3 -c "
import json,sys
try:    print(sorted(json.load(open('tree/suite/TEST/GOOD/result_db.json'))))
except Exception: print('unreadable')")"
    echo "}"
}

fixture() {             # <choice-line...> -- one app, run and accepted
    mkdir -p tree/suite/TEST/GOOD
    printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n}\n' \
        > tree/suite/TEST/hwut.conf
    { echo '#!/bin/bash'
      printf '%s\n' "$@"
    } > tree/suite/TEST/test-app.sh
    chmod +x tree/suite/TEST/test-app.sh
    $RUN --directory=tree --silent > /dev/null 2>&1
    ( cd tree/suite/TEST && python3 -m vut.services.accept --yes \
        > /dev/null 2>&1 )
    $RUN --directory=tree --timing --silent > /dev/null 2>&1
}

plain_app() { fixture '# @hwut { title = "Plain" }' \
                      'echo "steady line"' 'echo "<hwut-end>"'; }

choice_app() {
    fixture '# @hwut { title = "Two"  choices = ["one", "two"] }' \
            'echo "line for $1"' 'echo "<hwut-end>"'
}

# ---------------------------------------------------------------------------
case "$1" in

labels)
    #  THE BOUNDARY RECORDS FOLLOW ('services/_follow.py', disc-8
    #  section 5): a dropped test's label entries drop with it,
    #  symmetric with the book and the register (E-12) -- a run named
    #  in 'hwut-root.labels' but no longer offered would look merely
    #  unlabelled, which is the silent failure this forbids.
    choice_app
    python3 -m vut.services.labels.create concern \
        --glob "test-app.sh" --directory=tree > /dev/null
    echo "THE FILE, BEFORE {"; grep -v "^#" hwut-root.labels \
        | sed 's/^/    /'; echo "}"
    echo "--- one choice forgotten: its entry alone drops"
    face $REMOVE_CHOICE --directory=tree/suite/TEST test-app.sh one --yes
    echo "THE FILE {"; grep -v "^#" hwut-root.labels \
        | sed 's/^/    /'; echo "}"
    echo "--- the whole test forgotten: the label empties, the file goes"
    face $REMOVE --directory=tree/suite/TEST test-app.sh --yes
    if [ -f hwut-root.labels ]; then echo "THE FILE: still stands"
    else echo "THE FILE: absent -- no label exists"; fi
    ;;

whole)
    #  Everything the framework recorded, gone.
    plain_app
    standing "BEFORE"
    face $REMOVE --directory=tree/suite/TEST test-app.sh --yes
    standing "AFTER"
    ;;

choice)
    #  One choice gone; the other stands, nominal and all.
    choice_app
    standing "BEFORE"
    face $REMOVE_CHOICE --directory=tree/suite/TEST test-app.sh one --yes
    standing "AFTER"
    ;;

untouched)
    #  The author's own files are the author's.
    plain_app
    $REMOVE --directory=tree/suite/TEST test-app.sh --yes > /dev/null
    echo "the application stands:  $([ -f tree/suite/TEST/test-app.sh ] \
        && echo True || echo False)"
    echo "the hwut.conf stands:    $([ -f tree/suite/TEST/hwut.conf ] \
        && echo True || echo False)"
    echo "it is still executable:  $([ -x tree/suite/TEST/test-app.sh ] \
        && echo True || echo False)"
    ;;

unknown)
    #  Nothing to forget is not an error.
    plain_app
    face $REMOVE --directory=tree/suite/TEST test-nobody.sh --yes
    ;;

asking)
    #  Without '--yes' it asks, and 'n' removes nothing.
    plain_app
    echo "n" | $REMOVE --directory=tree/suite/TEST test-app.sh > out.txt 2>&1
    echo "STATUS: $?"
    echo "STDOUT {"; sed 's/^/    /' < out.txt; echo "}"
    standing "AFTER a refusal"
    ;;

stain)
    #  The urgent way out of a stain.
    fixture '# @hwut { title = "Flip" }' \
            'n=0' \
            '[ -f count.txt ] && n=$(cat count.txt)' \
            'echo $((n + 1)) > count.txt' \
            'if [ $((n % 2)) -eq 0 ]; then echo "steady line";' \
            'else echo "other line"; fi' \
            'echo "<hwut-end>"'
    $STABILITY --directory=tree --repeat=4 > /dev/null 2>&1
    echo "stained, so not run:"
    $RUN --directory=tree --plain > run.txt 2>&1
    echo "STATUS: $?"
    grep -E "UNSTABLE" run.txt | mask | sed 's/^/    /'
    echo "removed:"
    $REMOVE --directory=tree/suite/TEST test-app.sh --yes > /dev/null 2>&1
    echo "    the stain went with the book: $(python3 -c "
import json
print(json.load(open('tree/suite/TEST/GOOD/result_db.json')) == {})")"
    echo "runs again, with no history:"
    $RUN --directory=tree --plain > run.txt 2>&1
    echo "STATUS: $?"
    grep -E "GOOD missing" run.txt | mask | sed 's/^/    /'
    ;;

refused)
    #  Every door, by name.
    plain_app
    face $REMOVE --directory=tree/suite/TEST --sideways test-app.sh
    face $REMOVE --directory=nowhere test-app.sh
    face $REMOVE --directory=tree/suite/TEST
    face $REMOVE_CHOICE --directory=tree/suite/TEST test-app.sh one two
    ;;

*)
    echo "no such choice: $1"
    exit 1 ;;
esac
