#! /bin/bash
#
# @hwut {
#     title    = "License header: the same SPDX header on top of every source file"
#     features = ["spdx-present", "spdx-identical"]
#     choices {
#         good   { tolerance { constraints = ["failing == 0"] } }
#         broken { tolerance { constraints = ["failing > 0"] } }
#     }
# }
#
# ____________________________________________________________________________
# SUBJECT  the license header of every source file in one project
#          (good/broken), against LICENSE-HEADER.txt
# REQUIREMENT: every source file -- C, header, shell, Python, JavaScript,
# Makefile, YAML -- opens (after a '#!' line, if any) with the two lines of
# LICENSE-HEADER.txt, in the comment syntax of its language:
#
#     H1  'SPDX-License-Identifier:' stands within the first 3 lines
#     H2  the identifier is the project's: the one in LICENSE-HEADER.txt
#     H3  the copyright line is word for word the project's
#     H4  both lines are comments of the file's own language
#         (C: '/*' ' *' '//'; JavaScript: '//'; the rest: '#')
#
# HOW: bash, sed and grep -- no parser. The output is the HEADER MATRIX,
# one row per file and one column per check: 'ok', 'XX' (broken), '--' (not
# judged: no header was found, so there is nothing to compare). Below it,
# for every XX, the line that stands against the line that should.
#
# CHOICES
#   good     seven files in five languages, all with the header.
#   broken   app.js has none; gen_table.py says GPL-2.0-only; board.h has an
#            old copyright line; flash.sh has the header, but only after a
#            usage comment, at line 8; pipeline.yaml took it from a C file
#            ('//' -- in YAML that is no comment).
#
# HWUT CONCEPTS
#   sorted rows  'find' lists files in the order of the file system's
#                directory entries: it differs between ext4, tmpfs and a
#                fresh clone. The test sorts the rows (LC_ALL=C), so the
#                matrix and the list below it read in one order and every
#                cell is exact. (An earlier version matched the rows with
#                '##! table key=0'; log-summary shows that region where
#                the order truly is not the test's to fix.)
#   constraints  'failing' -- the number of files with an XX (or no header
#                in lines 1-3): 'failing == 0' for good is the requirement;
#                'failing > 0' for broken -- the violation is reported, the
#                matrix says where. The file count is exact text
#                ('files: 7'): a scan that loses a file changes it.
#                The law and its verdict close the page.
#
# READING THE GOOD: any XX in the matrix, then the lines under it.
# ____________________________________________________________________________
HERE=$(cd "$(dirname "$0")" && pwd)
export LC_ALL=C
case "$1" in
    good|broken) ;;
    *) echo "choices: good, broken"; exit 1 ;;
esac
cd "$HERE/../$1" || exit 1

spdx=$(sed -n 1p LICENSE-HEADER.txt)
copyright=$(sed -n 2p LICENSE-HEADER.txt)

comment_of() {        # the comment leaders a file's language allows
    case "$1" in
        *.c|*.h) echo '/\*|\*|//' ;;
        *.js)    echo '//' ;;
        *)       echo '#' ;;
    esac
}

echo "project header (LICENSE-HEADER.txt):"
echo "    $spdx"
echo "    $copyright"
echo
echo "HEADER MATRIX of '$1'   ok = holds   XX = broken   -- = no header to judge"
echo "    H1 SPDX in lines 1-3  H2 identifier  H3 copyright  H4 comment syntax"
echo "file                  H1   H2   H3   H4"
files=0; failing=0; detail=""
for f in $(find . -type f ! -name LICENSE-HEADER.txt | sed 's|^\./||' | LC_ALL=C sort); do
    files=$((files + 1))
    lead=$(comment_of "$f")
    head=$(sed -n '1{/^#!/d};1,4p' "$f" | sed -n '1,3p')     # 3 lines after a '#!'
    h1=XX; h2=--; h3=--; h4=--
    line=$(grep -n -m1 'SPDX-License-Identifier:' <<< "$head" | cut -d: -f1)
    if [ -n "$line" ]; then
        h1=ok
        body=$(sed -n "${line},$((line + 1))p" <<< "$head")
        any='/\*|\*|//|#|"""'                          # any comment leader at all
        got_spdx=$(sed -n 1p <<< "$body" | sed -E "s,^[[:space:]]*($any)[[:space:]]*,,")
        got_copy=$(sed -n 2p <<< "$body" | sed -E "s,^[[:space:]]*($any)[[:space:]]*,,")
        [ "$got_spdx" = "$spdx" ] && h2=ok || { h2=XX; detail+="$f: '$got_spdx'  ->  '$spdx'|"; }
        [ "$got_copy" = "$copyright" ] && h3=ok || { h3=XX; detail+="$f: '$got_copy'  ->  '$copyright'|"; }
        if grep -qvE "^[[:space:]]*($lead)" <<< "$body"; then
            h4=XX; detail+="$f: '$(sed -n 1p <<< "$body")'  ->  a comment of this language: ${lead//\\/}|"
        else
            h4=ok
        fi
    else
        at=$(grep -n -m1 'SPDX-License-Identifier:' "$f" | cut -d: -f1)
        if [ -n "$at" ]; then detail+="$f: the header begins only at line $at|"
        else                  detail+="$f: no SPDX header at all|"; fi
    fi
    case "$h1$h2$h3$h4" in *XX*) failing=$((failing + 1)) ;; esac
    printf "%-21s %-4s %-4s %-4s %s\n" "$f" "$h1" "$h2" "$h3" "$h4"
done
echo
if [ -n "$detail" ]; then
    echo "WHAT STANDS  ->  WHAT SHOULD   (sorted by file)"
    tr '|' '\n' <<< "$detail" | sed '/^$/d' | sort | sed 's/^/  /'
    echo
fi
echo "files: $files   files failing ((failing: $failing))   law == 0   $([ $failing = 0 ] && echo kept || echo BROKEN)"
echo "<hwut-end>"
