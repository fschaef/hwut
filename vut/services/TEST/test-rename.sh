#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "The rename faces: the boundary records follow the name."
#     choices    = ["labels"]
#     eq-pattern = ["STATUS: [0-9]"]
# }
#
# ---------------------------------------------------------------------------
#
# 'hwut.rename' AND 'hwut.rename-choice', ON THE BOUNDARY RECORDS
# ('services/_follow.py', disc-8 section 5). The directory-local
# mechanics -- nominals, candidates, the book, the register -- are
# exercised under the bookkeeper's own suites; THIS suite watches the
# records at the tree's boundary follow the new name: a label keyed by
# a name that has changed loses a member SILENTLY, and the member is
# not missing, it is UNLABELLED, which looks exactly like never having
# been labelled.
#
# labels     a whole test renamed: every entry re-keys; a choice
#            renamed: its one entry follows; the file stays sorted
#            and elided. A fresh name standing in the STORE is the
#            face's own refusal; one standing only in the FILE -- a
#            stale entry -- is a FAULT, not a merge, and the file is
#            left as it stood.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
RUN="python3 -m vut.services.run"
RENAME="python3 -m vut.services.rename"
RENAME_CHOICE="python3 -m vut.services.rename_choice"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "The rename faces: the boundary records follow the name.;"
        echo "CHOICES: labels;"
        echo "HAPPY: STATUS: [0-9];"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

printf 'hwut {\n}\n' > hwut-root.conf

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
    ( cd tree/suite/TEST && python3 -m vut.services.accept --yes \
        > /dev/null 2>&1 )
}

# ---------------------------------------------------------------------------
case "$1" in

labels)
    fixture
    python3 -m vut.services.labels.create concern \
        --glob "test-app.sh" --directory=tree > /dev/null
    python3 -m vut.services.labels.add meta \
        --glob "test-app.sh one" --directory=tree > /dev/null
    the_file
    echo "--- the whole test renamed: every entry follows"
    ( cd tree/suite/TEST \
      && printf 'y\n' | $RENAME test-app.sh test-fresh.sh ) \
        > out.txt 2> err.txt
    echo "STATUS: $?"
    grep -E "labels|book entry" out.txt | sed 's/^/    /'
    the_file
    echo "--- one choice renamed: its one entry follows"
    ( cd tree/suite/TEST \
      && printf 'y\n' | $RENAME_CHOICE test-fresh.sh one first ) \
        > out.txt 2> err.txt
    echo "STATUS: $?"
    grep -E "labels" out.txt | sed 's/^/    /'
    the_file
    echo "--- a fresh name that stands in the STORE: the face's own door"
    ( cd tree/suite/TEST \
      && printf 'y\n' | $RENAME_CHOICE test-fresh.sh first two ) \
        > out.txt 2> err.txt
    echo "STATUS: $?"
    grep -E "labels|REFUSED" out.txt | sed 's/^/    /'
    echo "--- a fresh name that stands only in the FILE: a fault, not a merge"
    echo "./tree/suite/TEST/test-fresh.sh stale : concern" \
        >> hwut-root.labels
    ( cd tree/suite/TEST \
      && printf 'y\n' | $RENAME_CHOICE test-fresh.sh first stale ) \
        > out.txt 2> err.txt
    echo "STATUS: $?"
    grep -E "labels" out.txt | sed 's/^/    /'
    the_file
    ;;

*)
    echo "no such choice: $1"
    exit 1 ;;
esac
