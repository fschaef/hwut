#! /bin/bash
# mirror.sh SRC DST -- make DST a copy of SRC, touching only what differs.
#
# New and changed files are copied (mode and time kept), files whose
# content already matches are left alone, and whatever DST holds that SRC
# does not is removed. Any file name works: blanks, a leading dash, dots.
# Prints one line per action: '+ path' created, '~ path' updated,
# '- path' removed; the order is the order 'find' meets them.
set -euo pipefail
src=${1%/}; dst=${2%/}
[ -d "$src" ] && [ -d "$dst" ] || { echo "usage: mirror.sh SRC DST" >&2; exit 2; }

( cd "$src" && find . -mindepth 1 -print0 ) | while IFS= read -r -d '' rel; do
    rel=${rel#./}
    if [ -d "$src/$rel" ]; then
        [ -d "$dst/$rel" ] || { mkdir -p -- "$dst/$rel"; echo "+ $rel/"; }
    elif [ ! -e "$dst/$rel" ]; then
        cp -p -- "$src/$rel" "$dst/$rel"; echo "+ $rel"
    elif ! cmp -s -- "$src/$rel" "$dst/$rel"; then
        cp -p -- "$src/$rel" "$dst/$rel"; echo "~ $rel"
    fi
done
( cd "$dst" && find . -mindepth 1 -depth -print0 ) | while IFS= read -r -d '' rel; do
    rel=${rel#./}
    if [ ! -e "$src/$rel" ]; then
        if [ -d "$dst/$rel" ]; then rmdir -- "$dst/$rel"; echo "- $rel/"
        else rm -f -- "$dst/$rel"; echo "- $rel"; fi
    fi
done
