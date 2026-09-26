#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "hwut.execute: a target over the tree, or shell commands in every test directory."
#     choices    = ["run", "absence", "default", "reasons", "lock",
#                   "passthrough", "quiet", "vocabulary", "refused", "help",
#                   "command", "command-refused"]
# }
#
# ---------------------------------------------------------------------------
#
# 'hwut.execute <target>' runs the script each directory's 'hwut.conf'
# binds to <target> (E-7); '-c "<commands>"' runs shell commands in every
# TEST DIRECTORY instead. Both run each directory under its lock, from the
# directory itself, and report exit codes without letting them decide.
#
# run            the target over the tree: 'alpha' binds 'clean' to a
#                script exiting 3, 'beta/TEST' to one writing stderr.
# absence        a target nobody binds refuses everything, zero runs;
#                under '-i' each directory is skipped instead.
# default        '--default=' runs where the target is absent.
# reasons        the three reasons, each refusing: not executable (with
#                '+x' setting it), a shebang's interpreter missing, no
#                file.
# lock           a directory another live run holds: its script does not
#                run, and the face says so and fails.
# passthrough    everything after the target reaches the script as is.
# quiet          '-q': the summary alone.
# vocabulary     a standard target ('on_entry') inside 'target { }' is
#                refused by name, where it stands.
# refused        no target; an unknown option; no directory binds any.
# help           the face's text.
# command        '-c': every test directory, in walk order; '--dir'
#                narrows; an exit 7 decides nothing; no tests is EMPTY.
# command-refused '-c' without commands; a word after them; '+x' and
#                '--default' beside it; neither a target nor '-c'.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
FACE="python3 -m vut.services.execute"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "hwut.execute: a target over the tree, or shell commands in every test directory.;"
        echo "CHOICES: run, absence, default, reasons, lock, passthrough, quiet, vocabulary, refused, help, command, command-refused;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

section() { echo; echo "--- $1 ---"; }
face()    { $FACE "$@" 2>&1; echo "[status $?]"; }
script()  {             # <path> <body...> -- an executable bash script
    local path=$1; shift
    printf '#!/bin/bash\n%s\n' "$*" > "$path"; chmod +x "$path"
}
conf()    {             # <dir> <binding lines> -- a hwut.conf binding targets
    mkdir -p "$1"
    printf 'hwut {\n    target {\n%b    }\n}\n' "$2" > "$1/hwut.conf"
}
target_tree() {         # tree/alpha and tree/beta/TEST, both binding 'clean'
    conf tree/alpha      '        clean = "./clean.sh"\n'
    conf tree/beta/TEST  '        clean = "./tidy.sh"\n        fix   = "./fix.sh"\n'
    script tree/alpha/clean.sh     'echo "alpha cleaned: $*"; exit 3'
    script tree/beta/TEST/tidy.sh  'echo "beta tidied"; echo "beta grumbles" >&2'
    script tree/alpha/spare.sh     'echo "spare ran in alpha"'
    script tree/beta/TEST/spare.sh 'echo "spare ran in beta"'
    printf '#!/bin/bash\necho "beta fixed"\n' > tree/beta/TEST/fix.sh
}
test_tree() {           # a root, two test directories, one without tests
    printf 'hwut {\n}\n' > hwut-root.conf
    for where in a b/c; do
        mkdir -p "tree/$where/TEST"
        printf '#!/bin/bash\n# @hwut { title = "T" }\necho x\necho "<hwut-end>"\n' \
            > "tree/$where/TEST/test-x.sh"
        chmod +x "tree/$where/TEST/test-x.sh"
    done
    mkdir -p tree/no-tests-here
}
cface() { $FACE "$@"; echo "STATUS: $?"; }

# ---------------------------------------------------------------------------
case "$1" in
run)
    target_tree; cd tree
    section "the target over the tree: exit codes reported, never deciding"
    face clean
    ;;
absence)
    target_tree; cd tree
    section "'fix' is bound in beta alone: absence refuses, zero executions"
    face missing
    section "the same under '-i': skipped, and the run succeeds"
    face -i missing
    ;;
default)
    target_tree; cd tree
    section "'--default=' fills absence: 'polish' is bound nowhere"
    face --default=./spare.sh polish
    ;;
reasons)
    target_tree
    section "reason 2, file not executable: refused, '+x' hinted"
    face --directory=tree/beta fix
    section "'+x' sets the bit; the run stands"
    face --directory=tree/beta +x fix
    conf odd '        bad  = "./bad.sh"\n        gone = "./gone.sh"\n'
    printf '#!/no/such/interpreter\n' > odd/bad.sh; chmod +x odd/bad.sh
    cd odd
    section "reason 3, shebang interpreter not executable: refused"
    face bad
    section "reason 1, file not present"
    face gone
    ;;
lock)
    target_tree; cd tree
    python3 -c "
import sys, time
from vut.engine.bookkeeper.api import DirectoryLock
lock = DirectoryLock('alpha'); lock.acquire()
open('held', 'w').close(); time.sleep(60)" &
    holder=$!
    while [ ! -f held ]; do sleep 0.05; done
    section "a held directory lock: the script does not run; FAULT, named"
    face clean
    kill $holder 2>/dev/null; wait $holder 2>/dev/null; rm -f held
    ;;
passthrough)
    conf pass '        show = "./args.sh"\n'
    script pass/args.sh 'IFS="|"; echo "argv: $*"'
    cd pass
    section "everything after the target name reaches the script, untouched"
    face show --fast -q "two words"
    ;;
quiet)
    target_tree; cd tree
    section "'-q': no per-directory recording, the summary alone"
    face -q clean
    ;;
vocabulary)
    mkdir -p vocab
    printf 'hwut {\n    target {\n        on_entry = "./x.sh"\n    }\n}\n' > vocab/hwut.conf
    cd vocab
    section "a standard target inside 'target { }': refused by name"
    face on_entry
    ;;
refused)
    mkdir -p none; cd none
    section "no target named"
    face
    section "an unknown option before the target name"
    face --bogus clean
    section "no directory binds any target: EMPTY"
    face clean
    ;;
help)
    face --help
    ;;
command)
    test_tree
    echo "--- every test directory, from its own cwd"
    cface --directory=tree -c 'basename $(dirname $PWD); ls'
    echo "--- '--dir' narrows"
    cface --directory=tree --dir c -c 'echo in $(basename $(dirname $PWD))'
    echo "--- an exit code informs, it does not decide"
    cface --directory=tree -c 'exit 7'
    echo "--- a tree without tests"
    cface --directory=tree/no-tests-here -c 'echo never'
    ;;
command-refused)
    test_tree
    cface -c
    cface -c ls extra
    cface +x -c ls
    cface --default=x.sh -c ls
    cface
    ;;
esac
echo "<hwut-end>"
