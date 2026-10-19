#! /bin/bash
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#
# WHAT OF 'adm/requirement-list.txt' STANDS ON THIS MACHINE.
#
#     sh adm/requirement-check.sh
#
# One line per requirement: 'ok', 'MISSING' or 'OLD' (older than the list's
# '>=<version>'), what it is for, and the
# package that brings it. EXIT 1 where a requirement the CENSUS needs is
# missing; a missing ROAD requirement is said and does not fail.
# ---------------------------------------------------------------------------
LIST="$(cd "$(dirname "$0")" && pwd)/requirement-list.txt"

found() {               #  <kind> <name>: 0 stands, 1 missing, 2 older than
                        #  the '>=<version>' a 'python' name carries
    case "$1" in
        program) command -v "$2" > /dev/null 2>&1 ;;
        python)  python3 - "$2" > /dev/null 2>&1 <<'EOF' ;;
import importlib, importlib.metadata, re, sys
module, _, oldest = sys.argv[1].partition(">=")
try:    importlib.import_module(module)
except ImportError: sys.exit(1)
if not oldest: sys.exit(0)
def numbers(v): return [int(n) for n in re.findall(r"\d+", v)]
try:    have = importlib.metadata.version(module)
except importlib.metadata.PackageNotFoundError: sys.exit(0)
sys.exit(0 if numbers(have) >= numbers(oldest) else 2)
EOF
        library) python3 -c "
import ctypes.util, sys
sys.exit(0 if ctypes.util.find_library('$2') else 1)" > /dev/null 2>&1 ;;
    esac
}

missing_n=0
while read -r kind name need package rest; do
    #  AN ENTRY IS A LINE WHOSE FIRST AND THIRD WORDS ARE OF THE LIST'S
    #  OWN VOCABULARY; everything else is the list's prose.
    case "$kind" in program|python|library) ;; *) continue ;; esac
    case "$need" in census|road)            ;; *) continue ;; esac
    found "$kind" "$name"
    case $? in
        0) state="ok     " ;;
        2) state="OLD    " ;;
        *) state="MISSING" ;;
    esac
    [ "$state" != "ok     " ] && [ "$need" = census ] \
        && missing_n=$((missing_n + 1))
    printf '%s  %-7s %-15s %-6s %-22s %s\n' \
           "$state" "$kind" "$name" "$need" "$package" "$rest"
done < "$LIST"

echo
if [ "$missing_n" -gt 0 ]; then
    echo "$missing_n requirement(s) of the census missing or too old: its rows that want them are red."
    exit 1
fi
echo "every requirement of the census stands."
