#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "hwut.remove.propose and hwut.remove.apply: lost ground, forgotten"
#     choices    = ["propose", "apply", "veto", "refused"]
# }
#
# ---------------------------------------------------------------------------
#
# THE PAIR (services E-45, E-126): propose writes the cases that have lost
# their ground, apply forgets what the file still names -- one case per
# call to 'hwut.remove', with '--dont-ask'.
#
# propose   an application gone -- its choice-less record and a choice's
#           side by side --, and one of its name standing ELSEWHERE:
#           'possibly moved to'; a choice not offered; and NEVER proposed:
#           an ASPIRANT -- a book entry of an offered case with no
#           nominal (B-14) --, a choice-less record of a test that stands
#           with choices (said on stdout), a file under 'OUT/'. The
#           judgement is sanitize's own function (E-126).
# apply     the proposal applied: every case forgotten, the report, and
#           what stands afterwards -- the aspirant among it.
# veto      a line under '#' is kept.
# refused   no file, a file that cannot be read, a file of comments only.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
PROPOSE="python3 -m vut.services.lib.remove.propose"
APPLY="python3 -m vut.services.lib.remove.apply"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "hwut.remove.propose and hwut.remove.apply: lost ground, forgotten;"
        echo "CHOICES: propose, apply, veto, refused;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

face() {                  #  <face> <argument>...: status and both streams
    $1 "${@:2}" > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "STDOUT {"; sed 's|'"$WORK"'|<work>|g' < out.txt | sed 's/^/    /'; echo "}"
    if [ -s err.txt ]; then echo "STDERR {"; sed 's/^/    /' < err.txt; echo "}"; fi
}

tree() {                  #  two directories; lost ground of three kinds
    mkdir -p suite/TEST/GOOD other/TEST
    printf 'hwut {\n}\n' > hwut-root.conf
    for d in suite other; do
        printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n}\n' \
            > $d/TEST/hwut.conf
    done
    printf '#!/bin/bash\n# @hwut { title = "A" }\necho a\necho "<hwut-end>"\n' \
        > suite/TEST/test-new.sh
    chmod +x suite/TEST/test-new.sh
    cp suite/TEST/test-new.sh other/TEST/test-moved.sh
    printf 'x\n' > suite/TEST/GOOD/test-moved.sh.txt       # app moved away
    printf 'x\n' > suite/TEST/GOOD/test-gone.sh.txt        # app gone ...
    printf 'x\n' > suite/TEST/GOOD/test-gone.sh--x.txt     # ... two records
    printf 'x\n' > suite/TEST/GOOD/test-new.sh--gone.txt   # choice not offered
    printf '#!/bin/bash\n# @hwut { title = "B" choices = ["one"] }\necho b\necho "<hwut-end>"\n' \
        > suite/TEST/test-two.sh
    chmod +x suite/TEST/test-two.sh
    printf 'b\n<hwut-end>\n' > suite/TEST/GOOD/test-two.sh--one.txt
    printf 'x\n' > suite/TEST/GOOD/test-two.sh.txt        # choice-less, stands
    mkdir -p suite/TEST/OUT                                # scratch, not judged
    printf 'x\n' > suite/TEST/OUT/test-new.sh--old.txt
    #  THE ASPIRANT: registered, no nominal (B-14) -- ground not lost.
    python3 -c "
from vut.engine.bookkeeper.api import Bookkeeper
Bookkeeper('suite/TEST').run_id_of('test-new.sh', allocate_f=True)"
}

listing() {               #  what stands in GOOD/, and the book's cases
    echo "GOOD {"; ls suite/TEST/GOOD | sed 's/^/    /'; echo "}"
    echo "BOOK {"
    python3 -c "
from vut.engine.bookkeeper.api import Bookkeeper
b = Bookkeeper('suite/TEST')
for t in b.tests():
    for c in b.choices(t):
        print('    %s %s %s' % (t, c, b.result(t, c).get('verdict')))"
    echo "}"
}

# ---------------------------------------------------------------------------
case "$1" in

propose)
    tree
    face "$PROPOSE" -o r.txt
    echo "FILE {"; sed 's/^/    /' < r.txt; echo "}"
    ;;

apply)
    tree
    $PROPOSE -o r.txt > /dev/null
    face "$APPLY" r.txt
    listing
    ;;

veto)
    tree
    $PROPOSE -o r.txt > /dev/null
    sed -i 's|^suite/TEST/test-moved.sh$|# suite/TEST/test-moved.sh|' r.txt
    face "$APPLY" r.txt
    listing
    ;;

refused)
    tree
    face "$APPLY"
    face "$APPLY" no-such-file.txt
    printf '# only\n\n' > empty.txt
    face "$APPLY" empty.txt
    ;;

*)
    echo "no such choice: $1"
    exit 1 ;;
esac

echo "<hwut-end>"
