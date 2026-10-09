#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title   = "hwut.about: the version, and where this installation stands."
#     choices = ["page", "refused", "version"]
# }
#
# ---------------------------------------------------------------------------
#
# THE 'hwut.about' FACE (services E-138), called by its launcher from a
# directory that is in NO tree: it is asked before a tree exists.
#
# page      the page. THE VERSION IS MASKED '<version>' and the four
#           machine words -- the package's place, the Python, its
#           interpreter, the platform -- by their names: a release moves
#           no nominal, and no machine's word enters one.
# version   '--version' is ONE bare line, and it is the string of
#           'adm/version.py' -- the one place the version stands.
# refused   a word the face does not take: named, the usage, exit 2;
#           '--version' beside another word is such a word.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
VUT=$(cd "$HERE/../.." && pwd)
FACE="$VUT/bin/hwut.about"
unset PYTHONPATH

case "$1" in
    --hwut-info)
        echo "hwut.about: the version, and where this installation stands.;"
        echo "CHOICES: page, refused, version;"
        exit 0 ;;
esac

STATED=$(sed -n 's/^string *= *"\(.*\)"$/\1/p' "$VUT/adm/version.py")
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

masked() {
    sed -e "s|$VUT|<package>|" \
        -e "s|^\(    python     \).*|\1<python>|" \
        -e "s|^\(    run by     \).*|\1<interpreter>|" \
        -e "s|^\(    platform   \).*|\1<platform>|" \
        -e "s|^\(    sources    \).*|\1<files and checksum>|" \
        -e "s|$STATED|<version>|g"
}

case "$1" in
    page)
        "$FACE" 2>&1 | masked
        echo "STATUS: ${PIPESTATUS[0]}" ;;
    version)
        "$FACE" --version > out.txt 2>&1
        echo "STATUS: $?"
        echo "lines: $(wc -l < out.txt)"
        [ "$(cat out.txt)" = "$STATED" ] \
            && echo "the line is the string of adm/version.py" \
            || echo "DIFFERS from adm/version.py: '$(cat out.txt)'" ;;
    refused)
        for words in "--verson" "--version --all" "now"; do
            echo "== hwut.about $words"
            "$FACE" $words 2>&1 | masked
            echo "STATUS: ${PIPESTATUS[0]}"
        done ;;
    *)
        echo "no such choice: $1"
        exit 1 ;;
esac
echo "<hwut-end>"
