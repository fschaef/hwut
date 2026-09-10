#! /bin/bash
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#
# @hwut {
#     title      = "Static analysis: what this tree tolerates"
#     tolerance { eq_pattern = ["ruff [0-9]+\\.[0-9]+\\.[0-9]+"] }
# }
#
# ---------------------------------------------------------------------------
#
# STATIC ANALYSIS: the source read WITHOUT BEING RUN.
#
# NOT A 'HYGIENE' SUITE, and the word is deliberately avoided: hygiene
# in this tree means A COMPONENT'S OWN source and GOOD files, checked
# against the defects that recurred while THAT component was built
# ('engine/operations/TEST/test-hygiene.py'). It belongs to its
# component and knows what that component keeps getting wrong. This
# suite belongs to no component and knows only what a tool reports
# about every file alike. This suite and
# 'test-import_graph.sh' beside it are the two in this tree that ask
# about the code base's SHAPE rather than its BEHAVIOUR -- every other
# suite runs the product and reads what came out.
#
# IT IS A RATCHET. 'ruff' is run over the tree with the tree's own
# configuration ('adm/ruff.toml'), and every kind of finding that
# still stands is printed, SORTED -- what this tree TOLERATES today.
#
# IT IS NOT A TEST THAT THE TREE IS CLEAN. It is a test that the tree
# is NO LESS CLEAN THAN IT WAS. A finding of a new kind, or one more
# instance of a kind already tolerated, moves the GOOD and the suite
# says so. A finding REMOVED moves it too, and that re-blessing is the
# record of an improvement.
#
# WHAT IS NOT LISTED HERE IS IN 'adm/ruff.toml', ignored BY NAME with
# its reason: house style ('%' formatting, hand-aligned imports,
# asserts as door guards) is not a finding, and 878 of one kind drown
# every finding that matters.
#
# THE RUFF VERSION IS PRINTED, and it is a HAPPY PATTERN: two runs
# under different ruffs are EQUIVALENT on that line. The version is
# not the fact this suite is about -- THE FINDINGS ARE. A ruff that
# knows new rules will move the list below, and that is where the
# suite speaks; a ruff that merely counts higher and finds the same
# things has said nothing, and the suite says nothing back.
#
# WITHOUT THE PATTERN this test would go red on every upgrade for a
# reason nobody could act on, and a suite that cries at noise is a
# suite that gets re-blessed unread.
#
# NO RUFF, NO REPORT. A missing tool is a MISSING PRECONDITION, and a
# missing precondition is a RESULT stated as one -- never a silent
# pass that would let hygiene rot unwatched.
# ---------------------------------------------------------------------------
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)      # the tree root: adm/TEST is two below
CONFIG="$ROOT/adm/ruff.toml"
unset NO_COLOR CI COLUMNS

case "$1" in
    --hwut-info)
        echo "Static analysis: what this tree tolerates;"
        echo "HAPPY: ruff [0-9]+\\.[0-9]+\\.[0-9]+;"
        exit 0 ;;
esac

if ! command -v ruff > /dev/null 2>&1; then
    echo "PRECONDITION MISSING: 'ruff' is not installed"
    echo "    the static analysis of this tree cannot be asked"
    echo "    without it;"
    echo "    'pip install ruff' and run again"
    exit 1
fi

cd "$ROOT"

echo "==[ STATIC ANALYSIS ]========================================"
echo "ground:  $(ruff --version)"
echo "config:  adm/ruff.toml"
echo "ignored: $(python3 - <<'PYEOF'
import re, io
text = io.open("adm/ruff.toml", encoding="utf-8").read()
match = re.search(r"lint\.ignore\s*=\s*\[(.*?)\]", text, re.S)
print(", ".join(sorted(re.findall(r'"([^"]+)"', match.group(1))))
      if match else "(none)")
PYEOF
)"
echo

#  SORTED BY RULE, never by count: a count that ties would order two
#  lines by whichever the tool named first, and a GOOD file may hold
#  no such coin-toss.
echo "TOLERATED {"
ruff check --config "$CONFIG" . --statistics 2>/dev/null \
    | grep -E '^ *[0-9]+\s+[A-Z]+[0-9]+' \
    | sed -E 's/^ *([0-9]+)[[:space:]]+([A-Z]+[0-9]+)[[:space:]]*(\[.\])?[[:space:]]*/\2|\1|/' \
    | sort \
    | awk -F'|' '{ printf "    %-10s %5d  %s\n", $1, $2, $3 }'
echo "}"
echo

TOTAL=$(ruff check --config "$CONFIG" . --statistics 2>/dev/null \
        | grep -E '^ *[0-9]+\s+[A-Z]+[0-9]+' \
        | awk '{ s += $1 } END { print s + 0 }')
echo "total tolerated: $TOTAL"

#  THE CORRECTNESS SET STANDS AT ZERO, and this is the line that must
#  never move upward. Four rules, chosen because each can HIDE A
#  FAILURE rather than merely offend:
#
#      F      a name that is not there
#      B011   a dispatch that vanishes under 'python -O' and then
#             returns None to a caller who blames their own code
#      B020   a loop variable rebinding what the loop reads from
#      S110   a swallow with no reason given
#
#  'S102' (exec) is NOT here: the pype language executes its own
#  effect blocks, so exec is the feature. A set that can never be
#  empty is a set people learn to ignore.
echo
echo "MUST STAND AT ZERO {"
ZERO=$(ruff check --config "$CONFIG" --select F,B011,B020,S110 \
       --exclude "*/TEST/*" . --statistics 2>/dev/null \
       | grep -E '^ *[0-9]+\s+[A-Z]+[0-9]+' \
       | sed -E 's/^ *([0-9]+)[[:space:]]+([A-Z]+[0-9]+).*/    \2 \1/')
if [ -z "$ZERO" ]; then
    echo "    empty -- no name that is not there, no dispatch that"
    echo "    vanishes under '-O', no swallow without a reason"
else
    echo "$ZERO"
fi
echo "}"

echo "<hwut-end>"
