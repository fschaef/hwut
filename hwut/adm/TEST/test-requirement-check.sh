#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title    = "adm/requirement-check.sh: ok, MISSING, OLD; exit 1 for the census"
#     features = ["requirement-check"]
#     choices  = ["census", "road"]
# }
#
# ---------------------------------------------------------------------------
#
# THE CHECK OVER A LIST OF ITS OWN: the script is copied beside a list
# whose rows every machine answers alike -- 'sh' stands, a program
# 'no-such-program-x' does not; 'json' stands (no '>='), 'pip' stands
# above 0.1 and below 999, a module 'no_such_module_x' does not.
#
#   census   a python row whose version is below '>=' reads OLD, an
#            absent one MISSING; both count, exit 1. MEASURED 2026-10-16:
#            every python row read MISSING -- the probe ran
#            'import bidict>=0.22.1', a syntax error.
#   road     the same rows needed by a road only: said, exit 0.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)

case "$1" in
    --hwut-info)
        echo "adm/requirement-check.sh: ok, MISSING, OLD; exit 1 for the census;"
        echo "CHOICES: census, road;"
        exit 0 ;;
esac

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
cp "$HERE/../requirement-check.sh" "$WORK/"

#  A MODULE WITH METADATA AND A KNOWN VERSION: 'pip' stands wherever
#  the suite runs (the census installs through it); its version is far
#  below 999 and far above 0.1.
need=$1
cat > "$WORK/requirement-list.txt" <<EOF
prose line: neither of the list's own vocabulary, read past
program  sh                    $need  -   a program that stands
program  no-such-program-x     $need  -   a program that does not
python   json                  $need  -   a module without '>=' that stands
python   pip>=0.1              $need  -   new enough
python   pip>=999              $need  -   below the oldest measured
python   no_such_module_x>=1.0 $need  -   absent
EOF

bash "$WORK/requirement-check.sh" | sed 's/  *$//'
echo "exit: ${PIPESTATUS[0]}"
echo "<hwut-end>"
