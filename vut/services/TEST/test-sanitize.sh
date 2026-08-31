#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "The hwut.sanitize face: what a tree accumulates"
#     choices    = ["report", "session", "lock", "nameless", "out",
#                   "orphans", "unreachable", "apply", "target",
#                   "refused", "transient"]
#     eq-pattern = ["STATUS: [0-9]"]
# }
#
# ---------------------------------------------------------------------------
#
# THE 'hwut.sanitize' FACE.
#
# report       a bare command line REPORTS AND DOES NOT ACT -- what it
#              found still stands afterwards.
# session      'TMP/session/' is wreckage; always safe.
# lock         a lock whose holder is GONE is offered; A LIVE LOCK IS
#              NEVER OFFERED, not even under '--apply'. And a claim
#              that CANNOT NAME ITS CLAIMANT is gone: honoured, it
#              would block the directory for ever.
# nameless     a claim that cannot name its claimant -- no start time,
#              a record of the wrong shape, no record at all -- is
#              GONE in every case, and for one reason.
# out          'OUT/' is the application's scratch.
# orphans      a record naming a case the configuration no longer
#              offers -- file, and book entry.
# unreachable  A RECORD WHOSE APPLICATION STILL STANDS IS NOT AN
#              ORPHAN. The guard that stops '--apply' destroying a
#              blessed nominal to tidy a directory.
# apply        '--apply' removes, and says what went.
# target       '--target' calls the project's own verb; a target NO
#              DIRECTORY BINDS is refused BY NAME.
# refused      unknown options, a bare '--target', a missing directory.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
FACE="python3 -m vut.services.sanitize"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "The hwut.sanitize face: what a tree accumulates;"
        echo "CHOICES: report, session, lock, nameless, out, orphans, unreachable, apply, target, refused;"
        echo "HAPPY: STATUS: [0-9];"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

printf 'hwut {\n}\n' > hwut-root.conf

face() {
    $FACE "$@" > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "STDOUT {"; sed 's|'"$WORK"'|<work>|g; s/[0-9]\+\.[0-9] kB/<size> kB/;
                        s/pid [0-9]\+/pid <n>/; s/[0-9]\+ s ago/<n> s ago/' \
                    < out.txt | sed 's/^/    /'; echo "}"
    if [ -s err.txt ]; then echo "STDERR {"; sed 's/pid [0-9]\+/pid <n>/; s/^/    /' < err.txt; echo "}"; fi
}

tree() {                  #  one directory, one application, one choice
    mkdir -p tree/suite/TEST/GOOD
    printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n}\n' \
        > tree/suite/TEST/hwut.conf
    printf '#! /bin/bash\n# @hwut { title = "A" }\necho "line"\necho "<hwut-end>"\n' \
        > tree/suite/TEST/test-app.sh
    chmod +x tree/suite/TEST/test-app.sh
    printf 'line\n<hwut-end>\n' > tree/suite/TEST/GOOD/test-app.sh.txt
    printf 'hwut {\n}\n' > tree/hwut-root.conf
}

listing() {               #  what still stands, so 'report' can be proved
    echo "STANDING {"
    ( cd tree && find . -not -name "." | sed 's|^\./||' | sort | sed 's/^/    /' )
    echo "}"
}

# ---------------------------------------------------------------------------
case "$1" in

report)
    #  A BARE COMMAND LINE ACTS ON NOTHING.
    tree
    mkdir -p tree/suite/TEST/TMP/session tree/suite/TEST/OUT
    touch tree/suite/TEST/TMP/session/a.out tree/suite/TEST/OUT/product.txt
    face --directory=tree
    listing
    ;;

session)
    tree
    mkdir -p tree/suite/TEST/TMP/session
    touch tree/suite/TEST/TMP/session/a.out tree/suite/TEST/TMP/session/a.err
    face --directory=tree --session
    ;;

lock)
    #  A LIVE LOCK IS NEVER OFFERED. The dead one is.
    tree
    mkdir -p tree/suite/TEST/TMP/lock
    printf '{"pid": 999999, "started": 1.0, "acquired": 1.0}\n' \
        > tree/suite/TEST/TMP/lock/holder.json
    echo "--- a holder that is gone:"
    face --directory=tree --lock
    #  A LIVE HOLDER RECORDS ITS OWN START TIME. A record WITHOUT one
    #  is not a live holder -- it is a claim that cannot name its
    #  claimant, and such a claim is GONE (directory_mutex).
    python3 -c "
import json, os, sys
sys.path.insert(0, '$ROOT')
from vut.auxiliary.directory_mutex import _process_start_time
json.dump({'pid': os.getppid(),
           'started': _process_start_time(os.getppid()),
           'acquired': 1.0},
          open('tree/suite/TEST/TMP/lock/holder.json', 'w'))"
    echo "--- a holder that LIVES (this very shell):"
    face --directory=tree --lock --apply
    echo "the lock still stands: $([ -d tree/suite/TEST/TMP/lock ] && echo yes || echo NO)"
    ;;

transient)
    #  THE TWO ROOTS WHOLE (E-24). Reported with the rest silenced;
    #  removed under --apply; a directory with a LIVE lock refused on
    #  stderr and the walk goes on.
    tree
    mkdir -p tree/suite/TEST/OUT tree/suite/TEST/TMP/store \
             tree/suite/TEST/TMP/session tree/other/TEST/GOOD \
             tree/other/TEST/TMP/lock tree/other/TEST/OUT
    echo x > tree/suite/TEST/OUT/product.txt
    echo x > tree/suite/TEST/TMP/store/test-app.sh.stdout
    echo x > tree/suite/TEST/TMP/session/a.out
    echo x > tree/other/TEST/OUT/product.txt
    cp tree/suite/TEST/test-app.sh tree/other/TEST/
    printf 'line\n<hwut-end>\n' > tree/other/TEST/GOOD/test-app.sh.txt
    echo "--- report: the roots, not their pieces"
    face --directory=tree --transient
    echo "--- a bare call never takes them"
    face --directory=tree
    python3 -c "
import json, os, sys
sys.path.insert(0, '$ROOT')
from vut.auxiliary.directory_mutex import _process_start_time
json.dump({'pid': os.getppid(),
           'started': _process_start_time(os.getppid()),
           'acquired': 1.0},
          open('tree/other/TEST/TMP/lock/holder.json', 'w'))"
    echo "--- apply: 'other' holds a live lock and is refused whole"
    face --directory=tree --transient --apply
    listing
    ;;

nameless)
    #  A CLAIM THAT CANNOT NAME ITS CLAIMANT IS GONE. Honoured, it
    #  would block the directory for ever: no future run could break
    #  it and no cleaning could remove it.
    tree
    mkdir -p tree/suite/TEST/TMP/lock
    echo "--- a record with no start time:"
    printf '{"pid": 1, "acquired": 1.0}\n' \
        > tree/suite/TEST/TMP/lock/holder.json
    face --directory=tree --lock
    echo "--- a record of the wrong shape:"
    printf '{"pid": 1, "started": "yesterday"}\n' \
        > tree/suite/TEST/TMP/lock/holder.json
    face --directory=tree --lock
    echo "--- no record at all:"
    rm -f tree/suite/TEST/TMP/lock/holder.json
    face --directory=tree --lock
    ;;

out)
    tree
    mkdir -p tree/suite/TEST/OUT
    touch tree/suite/TEST/OUT/a.txt tree/suite/TEST/OUT/b.txt
    face --directory=tree --out
    ;;

orphans)
    #  A record naming a case that is not offered.
    tree
    printf 'stale\n' > tree/suite/TEST/GOOD/test-gone.sh.txt
    printf 'stale\n' > tree/suite/TEST/GOOD/test-app.sh--nochoice.txt
    printf 'not ours\n' > tree/suite/TEST/GOOD/notes.md
    face --directory=tree --orphans
    ;;

unreachable)
    #  THE GUARD. The application STANDS but the configuration hides
    #  it: its nominal is UNREACHABLE, never an orphan.
    tree
    printf '#! /bin/bash\necho "hi"\n' > tree/suite/TEST/test-hidden.sh
    chmod +x tree/suite/TEST/test-hidden.sh
    printf 'hi\n' > tree/suite/TEST/GOOD/test-hidden.sh.txt
    printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n    ignore = ["test-hidden.sh"]\n}\n' \
        > tree/suite/TEST/hwut.conf
    face --directory=tree --orphans --apply
    echo "the nominal still stands: $([ -f tree/suite/TEST/GOOD/test-hidden.sh.txt ] \
          && echo yes || echo NO)"
    ;;

apply)
    tree
    mkdir -p tree/suite/TEST/TMP/session tree/suite/TEST/OUT
    touch tree/suite/TEST/TMP/session/a.out tree/suite/TEST/OUT/a.txt
    face --directory=tree --session --out --apply
    listing
    ;;

target)
    tree
    echo "--- a target NO directory binds:"
    face --directory=tree --target clean --apply
    echo "--- a target one directory binds:"
    printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n    target { clean = "./clean.sh" }\n}\n' \
        > tree/suite/TEST/hwut.conf
    printf '#! /bin/bash\necho "the project cleaned itself"\n' \
        > tree/suite/TEST/clean.sh
    chmod +x tree/suite/TEST/clean.sh
    face --directory=tree --target clean --apply
    echo "--- and without '--apply' it only says so:"
    face --directory=tree --target clean
    ;;

refused)
    tree
    face --directory=tree --sideways
    face --directory=tree --target
    face --directory=nowhere
    ;;

*)
    echo "no such choice: $1"
    exit 1 ;;
esac
