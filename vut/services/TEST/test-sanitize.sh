#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "hwut.sanitize: propose, edit, apply -- what a tree accumulates"
#     choices    = ["propose", "session", "lock", "nameless", "out",
#                   "orphans", "unreachable", "apply", "target",
#                   "refused", "transient", "command", "veto", "rejudge"]
# }
#
# ---------------------------------------------------------------------------
#
# THE THREE FACES OF SANITIZE (services E-125): 'hwut.sanitize.propose'
# writes commands, 'hwut.sanitize.apply' does what a file still holds,
# 'hwut.sanitize <command> <entity>' does one.
#
# propose      PROPOSE ACTS ON NOTHING -- what it found still stands --
#              and '-o <file>' writes what stdout carries, byte for byte.
# session      'TMP/session/' is wreckage: 'remove'.
# lock         a lock whose holder is GONE is proposed; A LIVE LOCK IS
#              NEVER PROPOSED, and 'remove' refuses it by name.
# nameless     a claim that cannot name its claimant -- no start time,
#              a record of the wrong shape, no record at all -- is
#              proposed in every case, and for one reason.
# out          'OUT/' is the application's scratch: 'remove'.
# orphans      a case the configuration no longer offers: 'forget' --
#              the test where the application is gone, the choice where
#              it stands; a file that names no case is somebody's.
# unreachable  A RECORD WHOSE APPLICATION STILL STANDS IS NOT AN ORPHAN.
#              Never proposed, and 'forget' refuses it by name.
# apply        the proposal, applied: the report, and what went.
# target       '--target' proposes one 'run' line; a target NO
#              DIRECTORY BINDS is refused BY NAME.
# refused      unknown options, a bare '--target', a missing directory;
#              apply without a file.
# transient    the two roots whole (E-24); never in a bare proposal; a
#              directory a live run holds is not proposed, said on stderr.
# command      the one-command face: done, nothing to do, refused by the
#              tree, and a line that spells no command.
# veto         a line under '#' is not done; a line that spells no
#              command refuses the WHOLE file, and nothing is done.
# rejudge      THE FILE SAYS WHAT, THE TREE SAYS WHETHER: a lock that
#              came alive between propose and apply is refused.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
PROPOSE="python3 -m vut.services.lib.sanitize.propose"
APPLY="python3 -m vut.services.lib.sanitize.apply"
COMMAND="python3 -m vut.services.sanitize"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "hwut.sanitize: propose, edit, apply -- what a tree accumulates;"
        echo "CHOICES: propose, session, lock, nameless, out, orphans, unreachable, apply, target, refused, transient, command, veto, rejudge;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

printf 'hwut {\n}\n' > hwut-root.conf

face() {                  #  <face> <argument>...: status and both streams
    $1 "${@:2}" > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "STDOUT {"; sed 's|'"$WORK"'|<work>|g; s/pid [0-9]\+/pid <n>/' \
                    < out.txt | sed 's/^/    /'; echo "}"
    if [ -s err.txt ]; then echo "STDERR {"; sed 's|'"$WORK"'|<work>|g; s/pid [0-9]\+/pid <n>/; s/^/    /' < err.txt; echo "}"; fi
}

commands() {              #  a proposal's commands alone, and its status
    $PROPOSE "$@" > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "COMMANDS {"; grep -v '^#' out.txt | grep -v '^$' | sed 's/^/    /'; echo "}"
    if [ -s err.txt ]; then echo "STDERR {"; sed 's|'"$WORK"'|<work>|g; s/pid [0-9]\+/pid <n>/; s/^/    /' < err.txt; echo "}"; fi
}

live_lock() {             #  <dir>: a lock held by THIS very shell
    python3 -c "
import json, os, sys
sys.path.insert(0, '$ROOT')
from vut.auxiliary.directory_mutex import _process_start_time
json.dump({'pid': os.getppid(),
           'started': _process_start_time(os.getppid()),
           'acquired': 1.0},
          open('$1/TMP/lock/holder.json', 'w'))"
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

propose)
    #  PROPOSE ACTS ON NOTHING, and '-o' writes what stdout carries.
    tree
    mkdir -p tree/suite/TEST/TMP/session tree/suite/TEST/OUT
    touch tree/suite/TEST/TMP/session/a.out tree/suite/TEST/OUT/product.txt
    face "$PROPOSE" --directory=tree
    cp out.txt piped.txt
    $PROPOSE --directory=tree -o written.txt 2> /dev/null
    echo "'-o' writes what stdout carries: $(cmp -s piped.txt written.txt && echo yes || echo NO)"
    listing
    ;;

session)
    tree
    mkdir -p tree/suite/TEST/TMP/session
    touch tree/suite/TEST/TMP/session/a.out tree/suite/TEST/TMP/session/a.err
    commands --directory=tree --session
    ;;

lock)
    #  A LIVE LOCK IS NEVER PROPOSED. The dead one is.
    tree
    mkdir -p tree/suite/TEST/TMP/lock
    printf '{"pid": 999999, "started": 1.0, "acquired": 1.0}\n' \
        > tree/suite/TEST/TMP/lock/holder.json
    echo "--- a holder that is gone:"
    commands --directory=tree --lock
    echo "--- a holder that LIVES (this very shell):"
    live_lock tree/suite/TEST
    commands --directory=tree --lock
    face "$COMMAND" remove tree/suite/TEST/TMP/lock
    echo "the lock still stands: $([ -d tree/suite/TEST/TMP/lock ] && echo yes || echo NO)"
    ;;

transient)
    #  THE TWO ROOTS WHOLE (E-24). Proposed with the pieces silenced;
    #  a directory with a LIVE lock not proposed, said on stderr.
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
    live_lock tree/other/TEST
    echo "--- the roots, not their pieces; 'other' is held by a live run"
    commands --directory=tree --transient
    echo "--- a bare proposal never takes them"
    commands --directory=tree
    echo "--- applied"
    $PROPOSE --directory=tree --transient -o p.txt 2> /dev/null
    face "$APPLY" p.txt
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
    commands --directory=tree --lock
    echo "--- a record of the wrong shape:"
    printf '{"pid": 1, "started": "yesterday"}\n' \
        > tree/suite/TEST/TMP/lock/holder.json
    commands --directory=tree --lock
    echo "--- no record at all:"
    rm -f tree/suite/TEST/TMP/lock/holder.json
    commands --directory=tree --lock
    ;;

out)
    tree
    mkdir -p tree/suite/TEST/OUT
    touch tree/suite/TEST/OUT/a.txt tree/suite/TEST/OUT/b.txt
    commands --directory=tree --out
    ;;

orphans)
    #  A case that is not offered: the test gone, the choice not named.
    tree
    printf 'stale\n' > tree/suite/TEST/GOOD/test-gone.sh.txt
    printf 'stale\n' > tree/suite/TEST/GOOD/test-app.sh--nochoice.txt
    printf 'not ours\n' > tree/suite/TEST/GOOD/notes.md
    commands --directory=tree --orphans
    $PROPOSE --directory=tree --orphans -o p.txt 2> /dev/null
    face "$APPLY" p.txt
    listing
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
    commands --directory=tree --orphans
    face "$COMMAND" forget tree/suite/TEST/test-hidden.sh
    echo "the nominal still stands: $([ -f tree/suite/TEST/GOOD/test-hidden.sh.txt ] \
          && echo yes || echo NO)"
    ;;

apply)
    tree
    mkdir -p tree/suite/TEST/TMP/session tree/suite/TEST/OUT
    touch tree/suite/TEST/TMP/session/a.out tree/suite/TEST/OUT/a.txt
    $PROPOSE --directory=tree --session --out -o p.txt 2> /dev/null
    face "$APPLY" p.txt
    listing
    ;;

target)
    tree
    echo "--- a target NO directory binds:"
    commands --directory=tree --target clean
    echo "--- a target one directory binds:"
    printf 'hwut {\n    on_entry = "true"\n    on_exit  = "true"\n    target { clean = "./clean.sh" }\n}\n' \
        > tree/suite/TEST/hwut.conf
    printf '#! /bin/bash\necho "the project cleaned itself"\n' \
        > tree/suite/TEST/clean.sh
    chmod +x tree/suite/TEST/clean.sh
    commands --directory=tree --target clean
    $PROPOSE --directory=tree --target clean -o p.txt 2> /dev/null
    grep -v '^book ' p.txt > q.txt
    face "$APPLY" q.txt
    ;;

refused)
    tree
    face "$PROPOSE" --directory=tree --sideways
    face "$PROPOSE" --directory=tree --target
    face "$PROPOSE" --directory=nowhere
    face "$APPLY"
    face "$APPLY" no-such-file.txt
    face "$COMMAND" --sideways remove x/OUT
    ;;

command)
    #  ONE LINE OF A PROPOSAL, AS A COMMAND LINE OF ITS OWN.
    tree
    mkdir -p tree/suite/TEST/OUT
    touch tree/suite/TEST/OUT/a.txt
    echo "--- done:"
    face "$COMMAND" remove tree/suite/TEST/OUT
    echo "--- nothing to do, it is gone:"
    face "$COMMAND" remove tree/suite/TEST/OUT
    echo "--- the path is none that 'remove' takes:"
    face "$COMMAND" remove tree/suite/TEST/GOOD
    echo "--- the book, from '--directory':"
    face "$COMMAND" book suite/TEST/test-app.sh --directory=tree
    face "$COMMAND" book suite/TEST/test-app.sh --directory=tree
    echo "--- no nominal, nothing to book:"
    face "$COMMAND" book tree/suite/TEST/test-none.sh
    echo "--- an offered case is no orphan:"
    face "$COMMAND" forget tree/suite/TEST/test-app.sh
    echo "--- words that spell no command:"
    face "$COMMAND" frget tree/suite/TEST/test-app.sh
    face "$COMMAND" run tree
    face "$COMMAND"
    ;;

veto)
    tree
    mkdir -p tree/suite/TEST/TMP/session tree/suite/TEST/OUT
    touch tree/suite/TEST/TMP/session/a.out tree/suite/TEST/OUT/a.txt
    printf '# a comment\n\n#remove tree/suite/TEST/OUT\nremove tree/suite/TEST/TMP/session\n' > vetoed.txt
    echo "--- the line under '#' is not done:"
    face "$APPLY" vetoed.txt
    listing
    echo "--- a line that spells no command refuses the file:"
    touch tree/suite/TEST/OUT/a.txt
    printf 'remove tree/suite/TEST/OUT\nerase tree/suite/TEST/OUT\nbook\n' > broken.txt
    face "$APPLY" broken.txt
    listing
    echo "--- nothing but comments:"
    printf '# only\n\n' > empty.txt
    face "$APPLY" empty.txt
    ;;

rejudge)
    #  THE FILE SAYS WHAT, THE TREE SAYS WHETHER.
    tree
    mkdir -p tree/suite/TEST/TMP/lock
    printf '{"pid": 999999, "started": 1.0, "acquired": 1.0}\n' \
        > tree/suite/TEST/TMP/lock/holder.json
    $PROPOSE --directory=tree --lock -o p.txt 2> /dev/null
    echo "--- proposed while the holder was gone:"
    grep -v '^#' p.txt | grep -v '^$' | sed 's/^/    /'
    live_lock tree/suite/TEST
    echo "--- applied after a live run took the directory:"
    face "$APPLY" p.txt
    echo "the lock still stands: $([ -d tree/suite/TEST/TMP/lock ] && echo yes || echo NO)"
    ;;

*)
    echo "no such choice: $1"
    exit 1 ;;
esac

echo "<hwut-end>"
