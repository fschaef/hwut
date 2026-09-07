#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "A test named by path ENTERS its directory (E-47)."
#     choices    = ["enter", "refused"]
#     tolerance { eq_pattern = ["STATUS: [0-9]"] }
# }
#
# ---------------------------------------------------------------------------
#
# 'a/TEST/test-a.sh' AS A BARE WORD means: enter 'a/TEST', perform
# 'test-a.sh' there -- on every face ('services/_target.py', E-45,
# E-47). The wish faces used to read it as a glob over the tree BELOW
# the current directory, so a path above or beside it matched nothing
# and said nothing; the bare-name faces did not read it at all.
#
# enter      the same test asked for by a path below, by a path with
#            '..', by an absolute path, and relative to '--directory'
#            -- four spellings, one selection,
#            on 'hwut.wishlist' and 'hwut.run'; 'hwut.show' by path.
#            A glob in the DIRECTORY part is not a path: it stays a
#            wish over the tree below.
# refused    two words naming two directories; an absolute path
#            outside '--directory'. A RELATIVE path beside
#            '--directory' is read against it -- shown under 'enter'.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../../.." && pwd)
export PYTHONPATH="$ROOT"
WISHLIST="python3 -m vut.services.wishlist"
RUN="python3 -m vut.services.run"
SHOW="python3 -m vut.services.show"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "A test named by path ENTERS its directory (E-47).;"
        echo "CHOICES: enter, refused;"
        echo "HAPPY: STATUS: [0-9];"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"
printf 'hwut {\n}\n' > hwut-root.conf

face() {                # <face> <args...> -- status and stdout
    local f="$1"; shift
    $f "$@" > out.txt 2> err.txt
    echo "STATUS: $?"
    echo "STDOUT {"; sed "s|$WORK|\$WORK|g; s/^/    /" < out.txt; echo "}"
    if [ -s err.txt ]; then
        echo "STDERR {"; sed "s|$WORK|\$WORK|g; s/^/    /" < err.txt; echo "}"
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

enter)
    fixture
    echo "--- a path BELOW: enter it, one directory selected"
    face "$WISHLIST" tree/messaging/queue/TEST/test-a.sh one
    echo "--- a path with '..': the same"
    ( cd tree/storage && face "$WISHLIST" ../messaging/queue/TEST/test-a.sh one )
    echo "--- an ABSOLUTE path: the same"
    face "$WISHLIST" "$WORK/tree/messaging/queue/TEST/test-a.sh" one
    echo "--- a path RELATIVE TO '--directory': the same"
    face "$WISHLIST" --directory=tree messaging/queue/TEST/test-a.sh one
    echo "--- 'hwut.run' by a path with '..': only that directory is walked"
    ( cd tree/storage \
      && $RUN ../messaging/queue/TEST/test-a.sh one > out.txt 2> err.txt;
      echo "STATUS: $?"; grep -E '\[OK\]|\[FAIL\]|RESULTS' out.txt \
        | sed 's/, [0-9.]* \[sec\]//; s/^/    /' )
    echo "--- 'hwut.show' by a path: the test, from its own directory"
    ( cd tree && $SHOW messaging/net/TEST/test-b.sh > out.txt 2> err.txt;
      echo "STATUS: $?"; head -2 out.txt | sed 's/^/    /' )
    echo "--- a glob in the DIRECTORY part is not a path: a wish over the tree below"
    face "$WISHLIST" --directory=tree 'messaging/*/TEST/test-a.sh' two
    ;;

refused)
    fixture
    echo "--- two words naming two directories"
    face "$WISHLIST" tree/storage/TEST/test-a.sh tree/messaging/net/TEST/test-b.sh
    echo "--- an absolute path outside '--directory'"
    face "$WISHLIST" --directory=tree/storage "$WORK/tree/messaging/net/TEST/test-a.sh"
    echo "--- the same, on 'hwut.run'"
    face "$RUN" --directory=tree/storage "$WORK/tree/messaging/net/TEST/test-a.sh"
    ;;

*)
    echo "no such choice: $1"
    exit 1 ;;
esac
echo "<hwut-end>"
