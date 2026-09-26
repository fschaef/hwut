#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "adm/bundle.sh --self: a bundle that lands in a standing tree"
#     choices    = ["self", "refused"]
# }
#
# ---------------------------------------------------------------------------
#
# 'adm/bundle.sh --self' writes a SHELL SCRIPT: the applier, then the
# bundle unchanged -- 'git apply' still reads it. Run at the receiving
# root, the applier rebuilds every member from its '+' lines, proves
# each against the '# sha256' manifest BEFORE the tree is touched, and
# classifies: NEW created, IDENTICAL skipped, CHANGED refused unless
# '--force', '# delete' lines removed, '# mode' lines restored.
#
# self        a sender's tree bundled into a receiver's that already
#             holds one identical file, one edited file and one file
#             the sender deleted: '--check' reports, the plain run
#             refuses the edited file, '--force' lands everything, the
#             rerun says 'already applied', and 'git apply' reads the
#             same file into an empty directory. An empty member and a
#             member without a final newline travel intact.
# refused     a directory where nothing listed stands and no root marker
#             is; a bundle whose content was tampered with after
#             signing; '--self' beside '--binary' and '--max-bytes'.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
TOOL="$ROOT/adm/bundle.sh"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "adm/bundle.sh --self: a bundle that lands in a standing tree;"
        echo "CHOICES: self, refused;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

apply() {               # <bundle> [args...] -- status and stdout
    local b="$1"; shift
    sh "$b" "$@" > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "STDOUT {"; sed "s|$WORK|<work>|g; s/^/    /" < out.txt; echo "}"
    if [ -s err.txt ]; then
        echo "STDERR {"; sed "s|$WORK|<work>|g; s/^/    /" < err.txt; echo "}"
    fi
}

fixture() {
    mkdir -p send/a/b recv/a/b
    touch send/hwut-root.conf recv/hwut-root.conf
    printf 'one\ntwo\n'         > send/a/b/same.txt
    printf 'sender line\n'      > send/a/b/edited.txt
    printf 'no final newline'   > send/a/b/short.txt
    : > send/a/empty.txt
    printf '#!/bin/sh\necho hi\n' > send/a/run.sh; chmod +x send/a/run.sh
    printf 'one\ntwo\n'         > recv/a/b/same.txt
    printf 'receiver line\n'    > recv/a/b/edited.txt
    printf 'to go\n'            > recv/a/gone.txt
    ( cd send && bash "$TOOL" --self --use-find -d a --delete a/gone.txt \
                     -o "$WORK/b.sh" > /dev/null 2>&1 )
}

# ---------------------------------------------------------------------------
case "$1" in

self)
    fixture
    echo "--- the header carries the mode and the deletion"
    grep -E '^# (mode|delete) ' b.sh | sed 's/^/    /'
    cd recv
    echo "--- --check: reported, nothing touched"
    apply ../b.sh --check
    echo "--- the plain run refuses the edited file"
    apply ../b.sh
    echo "--- --force lands everything"
    apply ../b.sh --force
    echo "--- what stands now"
    ( find a -type f | sort; [ -x a/run.sh ] && echo "a/run.sh is executable";
      cat a/b/edited.txt; printf '[%s]\n' "$(cat a/b/short.txt)" ) | sed 's/^/    /'
    echo "--- rerun"
    apply ../b.sh
    echo "--- 'git apply' reads the same file into an empty directory"
    #  A scratch directory may lie INSIDE a git repository (hwut sets
    #  TMPDIR under the suite): git is told the prefix, or it drops
    #  every path outside the cwd without a word.
    mkdir ../plain && cd ../plain \
      && git apply --directory="$(git rev-parse --show-prefix 2>/dev/null)" ../b.sh \
      && find . -type f | sort | sed 's/^/    /'
    ;;

refused)
    fixture
    echo "--- a directory where nothing listed stands, no root marker"
    mkdir elsewhere && cd elsewhere
    apply ../b.sh
    cd ..
    echo "--- tampered after signing: a member no longer rebuilds to its sha256"
    sed 's/^+sender line$/+tampered line/' b.sh > tampered.sh
    ( cd recv && apply ../tampered.sh --force )
    echo "--- --self beside --binary, --max-bytes"
    ( cd send && bash "$TOOL" --self --use-find -d a --binary -o x.sh 2>&1 | sed 's/^/    /' )
    ( cd send && bash "$TOOL" --self --use-find -d a --max-bytes 100 -o x.sh 2>&1 | sed 's/^/    /' )
    ;;

*)
    echo "no such choice: $1"
    exit 1 ;;
esac
echo "<hwut-end>"
