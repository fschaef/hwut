#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# migrate-support.sh -- the moves of services E-216, and nothing else.
#
#     test_writing_support/hwut_pype/   -> services/lib/pype/
#        hwut_pype.py                   ->    pype.py
#     test_writing_support/             -> support/test_writing/
#     demo/                             -> support/demo/
#
# Run once at the repository root, BEFORE the bundle that edits the moved
# files (bundle 32) is applied:
#
#     bash migrate-support.sh                   # do it
#     bash migrate-support.sh --check           # say what would move
#
# The hwut directory is the one this script stands in ('hwut/adm/'), else
# './hwut' or '.', whichever holds 'hwut-root.conf'.
#
# Moves are 'git mv' of whole directories, so git keeps every file's history
# and files not yet committed (a bundle applied, not committed) travel along.
# Nothing is edited: references are the bundle's business.
#
# Comment convention: every function comment opens with the RETURN block.
# ---------------------------------------------------------------------------
set -euo pipefail

HWUT=""
for candidate in "$(dirname "${BASH_SOURCE[0]}")/.." ./hwut .; do
    if [[ -f "$candidate/hwut-root.conf" ]]; then
        HWUT=$(cd "$candidate" && pwd); break
    fi
done
CHECK_F=0
case "${1-}" in
    --check) CHECK_F=1 ;;
    "")      ;;
    *)       echo "usage: bash $0 [--check]" >&2; exit 2 ;;
esac

# RETURN: nothing, the process ends with exit status 1 and the message on stderr.
die() { echo "migrate-support: $*" >&2; exit 1; }

# RETURN: nothing, 'from' moved to 'to' by 'git mv' (or printed under --check);
#         the process dies if 'from' is missing or 'to' already stands.
move() {
    local from=$1 to=$2
    if (( CHECK_F )); then echo "would move  $from -> $to"; return; fi
    [[ -e "$HWUT/$from" ]] || die "'$from' is missing -- already migrated?"
    [[ ! -e "$HWUT/$to" ]] || die "'$to' stands already -- refusing to merge"
    mkdir -p "$HWUT/$(dirname "$to")"
    git -C "$HWUT" mv "$from" "$to"
    echo "moved  $from -> $to"
}

[[ -n "$HWUT" ]] || { echo "migrate-support: no 'hwut-root.conf' here or in" \
                          "'./hwut' -- run at the repository root" >&2; exit 1; }
git -C "$HWUT" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
    || die "'$HWUT' is not inside a git work tree"
[[ -e "$HWUT/test_writing_support/erlang" ]] \
    || die "bundle 31 is not applied here (no 'test_writing_support/erlang')"
for target in services/lib/pype support/test_writing support/demo; do
    [[ ! -e "$HWUT/$target" ]] || die "'$target' stands already -- migrated?"
done

move test_writing_support/hwut_pype          services/lib/pype
move services/lib/pype/hwut_pype.py          services/lib/pype/pype.py
move test_writing_support                    support/test_writing
move demo                                    support/demo

(( CHECK_F )) || echo "done -- now apply bundle 32, then commit"
