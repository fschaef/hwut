#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "The rename face: the boundary records follow the name."
#     choices    = ["labels", "across", "notes"]
#     tolerance { eq_pattern = ["STATUS: [0-9]", "-- [0-9]+ file\\(s\\)"] }
# }
#
# ---------------------------------------------------------------------------
#
# 'hwut.rename' AND 'hwut.move', ON THE BOUNDARY RECORDS
# ('services/_follow.py', disc-8 section 5) AND ACROSS A DIRECTORY
# (E-46). The directory-local mechanics -- nominals, candidates, the
# book, the register -- are exercised under the bookkeeper's own
# suites; THIS suite watches the records at the tree's boundary follow
# the new name: a label keyed by a name that has changed loses a
# member SILENTLY, and the member is not missing, it is UNLABELLED,
# which looks exactly like never having been labelled.
#
# labels     a whole test renamed: every entry re-keys; a choice
#            renamed ('<app> <choice> -to <choice'>'): its one entry
#            follows; the file stays sorted and elided. A fresh name
#            standing in the STORE is the face's own refusal; one
#            standing only in the FILE -- a stale entry -- is a FAULT,
#            not a merge, and the file is left as it stood.
# notes      READ AND SAY, NEVER EDIT (E-48): the application under
#            the old name, the '@hwut' block still declaring the old
#            choice, a 'hwut.conf' apps section naming the old name --
#            each a telegraphic NOTE before 'Proceed?'; '--no-warning'
#            drops them, '--silent' everything but a refusal; a file
#            under BOTH names is refused.
# across     a test carried into another directory: the entries
#            re-key to the new path under the same boundary; the
#            target register issues fresh ids, the source retires;
#            'hwut.move' says the same in two words.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
RUN="python3 -m vut.services.run"
RENAME="python3 -m vut.services.rename"
MOVE="python3 -m vut.services.move"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "The rename face: the boundary records follow the name.;"
        echo "CHOICES: labels, across, notes;"
        echo "HAPPY: STATUS: [0-9];"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

printf 'hwut {\n}\n' > hwut-root.conf

register_of() {         # <TEST dir> -- the register, through the
                        # bookkeeper's door: the book IS the register
                        # (B-13), and nothing here reads a file of its own
    python3 -c "from vut.engine.bookkeeper.api import Bookkeeper
print(Bookkeeper('$1').register_text(), end='')"
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

the_file() {
    if [ -f hwut-root.labels ]; then
        echo "THE FILE {"; grep -v "^#" hwut-root.labels \
            | sed 's/^/    /'; echo "}"
    else
        echo "THE FILE: absent -- no label exists"
    fi
}

fixture() {             # one app with two choices, run and accepted
    mkdir -p tree/suite/TEST/GOOD
    printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n}\n' \
        > tree/suite/TEST/hwut.conf
    { echo '#!/bin/bash'
      echo '# @hwut { title = "Two"  choices = ["one", "two"] }'
      echo 'echo "line for $1"'
      echo 'echo "<hwut-end>"'
    } > tree/suite/TEST/test-app.sh
    chmod +x tree/suite/TEST/test-app.sh
    $RUN --directory=tree --silent > /dev/null 2>&1
    ( cd tree/suite/TEST && python3 -m vut.services.accept --force \
        > /dev/null 2>&1 )
}

# ---------------------------------------------------------------------------
case "$1" in

labels)
    fixture
    python3 -m vut.services.lib.labels.create concern \
        --glob "test-app.sh" --directory=tree > /dev/null
    python3 -m vut.services.lib.labels.add meta \
        --glob "test-app.sh one" --directory=tree > /dev/null
    the_file
    echo "--- the whole test renamed: every entry follows"
    ( cd tree/suite/TEST \
      && printf 'y\n' | $RENAME test-app.sh -to test-fresh.sh ) \
        > out.txt 2> err.txt
    echo "STATUS: $?"
    grep -E "labels|book entry" out.txt | sed 's/^/    /'
    the_file
    echo "--- one choice renamed: its one entry follows"
    ( cd tree/suite/TEST \
      && printf 'y\n' | $RENAME test-fresh.sh one -to first ) \
        > out.txt 2> err.txt
    echo "STATUS: $?"
    grep -E "labels" out.txt | sed 's/^/    /'
    the_file
    echo "--- a fresh name that stands in the STORE: the face's own door"
    ( cd tree/suite/TEST \
      && printf 'y\n' | $RENAME test-fresh.sh first -to two ) \
        > out.txt 2> err.txt
    echo "STATUS: $?"
    grep -E "labels|REFUSED" out.txt | sed 's/^/    /'
    echo "--- a fresh name that stands only in the FILE: a fault, not a merge"
    echo "./tree/suite/TEST/test-fresh.sh stale : concern" \
        >> hwut-root.labels
    ( cd tree/suite/TEST \
      && printf 'y\n' | $RENAME test-fresh.sh first -to stale ) \
        > out.txt 2> err.txt
    echo "STATUS: $?"
    grep -E "labels" out.txt | sed 's/^/    /'
    the_file
    ;;

across)
    fixture
    mkdir -p tree/other/TEST
    cp tree/suite/TEST/hwut.conf tree/other/TEST/
    python3 -m vut.services.lib.labels.create concern \
        --glob "test-app.sh" --directory=tree > /dev/null
    the_file
    echo "--- carried into another directory: the entries follow the path"
    ( cd tree && printf 'y\n' \
      | $RENAME suite/TEST/test-app.sh -to other/TEST/test-moved.sh ) \
        > out.txt 2> err.txt
    echo "STATUS: $?"
    grep -E "labels|book entry|register|coverage" out.txt | sed 's/^/    /'
    the_file
    echo "--- the source register retired the id; the target issued afresh"
    register_of tree/suite/TEST | sed -n '/^A:/p;/^C:/p' | sed 's/^/    suite: /'
    register_of tree/other/TEST | sed -n '/^A:/p;/^C:/p' | sed 's/^/    other: /'
    echo "--- 'hwut.move' INTO a directory, two words"
    ( cd tree && printf 'y\n' | $MOVE other/TEST/test-moved.sh suite/TEST/ ) \
        > out.txt 2> err.txt
    echo "STATUS: $?"
    grep -E "labels|register" out.txt | sed 's/^/    /'
    the_file
    echo "--- a choice never crosses"
    ( cd tree && $RENAME suite/TEST/test-moved.sh one -to other/TEST/x ) \
        > out.txt 2> err.txt
    echo "STATUS: $?"
    grep -E "REFUSED" out.txt | sed 's/^/    /'
    ;;

notes)
    fixture
    printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n    apps {\n        "test-app.sh" { title = "T"  choices = ["one", "two"] }\n    }\n}\n' \
        > tree/suite/TEST/hwut.conf
    echo "--- the application under the OLD name, a conf section naming it"
    ( cd tree/suite/TEST && $RENAME test-app.sh -to test-fresh.sh --dont-ask ) \
        > out.txt 2> err.txt
    echo "STATUS: $?"
    grep -E "^NOTE" out.txt | sed 's/^/    /'
    echo "--- the author moved the file; a choice renamed: the block still declares 'one'"
    ( cd tree/suite/TEST && mv test-app.sh test-fresh.sh \
      && $RENAME test-fresh.sh one -to first --dont-ask ) > out.txt 2> err.txt
    echo "STATUS: $?"
    grep -E "^NOTE" out.txt | sed 's/^/    /'
    echo "--- --no-warning: the same disagreement, unsaid"
    ( cd tree/suite/TEST && $RENAME test-fresh.sh -to test-final.sh --dont-ask --no-warning ) \
        > out.txt 2> err.txt
    echo "STATUS: $?  NOTE lines: $(grep -c '^NOTE' out.txt)"
    echo "--- --silent: nothing but a refusal"
    ( cd tree/suite/TEST && $RENAME test-final.sh -to test-quiet.sh --dont-ask --silent ) \
        > out.txt 2> err.txt
    echo "STATUS: $?  lines: $(wc -l < out.txt)"
    echo "--- under BOTH names: refused before anything moves"
    ( cd tree/suite/TEST && cp test-fresh.sh test-quiet.sh \
      && $RENAME test-fresh.sh -to test-quiet.sh --dont-ask ) > out.txt 2> err.txt
    echo "STATUS: $?"
    grep -E "REFUSED" out.txt | sed 's/^/    /'
    ;;

*)
    echo "no such choice: $1"
    exit 1 ;;
esac
echo "<hwut-end>"
