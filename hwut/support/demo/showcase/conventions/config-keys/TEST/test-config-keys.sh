#! /bin/bash
#
# @hwut {
#     title    = "Configuration: every key the code reads is documented, every documented key is read"
#     features = ["read-is-documented", "documented-is-read"]
#     choices {
#         good   { tolerance { constraints = ["findings == 0"] } }
#         broken { tolerance { constraints = ["findings > 0"] } }
#     }
# }
#
# ____________________________________________________________________________
# SUBJECT  where each configuration key of one service (good/broken) is read,
#          documented and exemplified
# REQUIREMENT: the configuration table of README.md is the contract with the
# operators.
#   K1  every key the code reads -- INI keys read by the Python service,
#       environment variables read by Python or by the shell scripts -- has
#       a row in the table;
#   K2  every row of the table names a key that some code still reads
#       (a documented knob that does nothing costs an operator a night);
#   K3  every INI key the code reads has a line in config.example.ini.
#
# HOW: three extractions:
#   code    keys-read.py: *.py through Python's own parser (ast) --
#           os.getenv("X"), os.environ.get("X"), os.environ["X"],
#           cfg.get*("s", "k"), cfg["s"]["k"], cfg["s"].get*("k") on a
#           ConfigParser; *.sh: every $X and ${X...} the script does not
#           assign itself (outside '...' and comments)
#   README  the first column of the table, `key`
#   example section headers and 'key =' lines of config.example.ini
# The output is
#   1. the CROSS REFERENCE: key x {code, README, example}, where found; the
#      code column names the FORM of the first read, so the GOOD shows which
#      spellings the extractor understood;
#   2. the SETS as a three-column picture: read only | both | documented only
#      -- a Venn diagram laid flat; K1 and K2 hold when the outer columns
#      are empty.
#
# CHOICES
#   good     eight keys, every one in code and README (and the INI keys in
#            the example), read in seven different spellings.
#   broken   db.timeout_s is new in the code (cfg["db"]["timeout_s"]),
#            APP_REGION was renamed to APP_ZONE in run.sh only ("$APP_ZONE"),
#            server.workers left the code but not the README.
#
# HWUT CONCEPTS
#   constraints  'findings' = keys read but undocumented (K1) + documented
#                but not read (K2) + INI keys missing in the example (K3).
#                good: 'findings == 0' -- the requirement; broken:
#                'findings > 0' -- the violation is reported, the sets show
#                which. The key count is exact text: a read the extractor
#                stops seeing changes 'keys: 8'.
#   exact lines  table and picture. In the picture the '|' bars, not the
#                spaces, say which column a key stands in: hwut tolerates
#                runs of blanks and strips line ends, so a picture whose
#                columns were made of spaces alone would compare equal
#                when a key moved from one set into another.
#
# READING THE GOOD: the outer columns of the SETS picture must be empty; in the
# cross reference '- !' marks each finding where it stands; the last line is
# the law over K1..K3 and its verdict.
# ____________________________________________________________________________
HERE=$(cd "$(dirname "$0")" && pwd)
export LC_ALL=C
case "$1" in
    good|broken) ;;
    *) echo "choices: good, broken"; exit 1 ;;
esac
cd "$HERE/../$1" || exit 1

reads=$(python3 "$HERE/keys-read.py" .)    # 'key file:line form', sorted
where_code() {    # key -> 'file:line form' of its first read, or '-  -'
    local hit; hit=$(echo "$reads" | awk -v k="$1" '$1 == k { print $2, $3; exit }')
    echo "${hit:--  -}"
}
where_readme() {
    local n; n=$(grep -nF "| \`$1\`" README.md | head -1 | cut -d: -f1)
    [ -n "$n" ] && echo "README.md:$n" || echo "-"
}
where_example() {
    case "$1" in *.*) ;; *) echo "(env)"; return ;; esac
    local n; n=$(awk -v s="${1%%.*}" -v k="${1#*.}" '
        /^\[/ { sec = substr($0, 2, length($0) - 2) }
        sec == s && $1 == k { print NR; exit }' config.example.ini)
    [ -n "$n" ] && echo "example.ini:$n" || echo "-"
}

code_keys=$(echo "$reads" | cut -d' ' -f1 | sort -u)
doc_keys=$(grep -oE '^\| `[A-Za-z_.]+`' README.md | sed -E 's/^\| `(.*)`/\1/' | sort -u)
all_keys=$(printf "%s\n%s\n" "$code_keys" "$doc_keys" | sed '/^$/d' | sort -u)

echo "configuration of '$1'"
echo
echo "CROSS REFERENCE   where each key is read, documented, exemplified"
echo "                  ('-': nowhere; '- !': nowhere, and that is a finding K1, K2 or K3)"
printf "  %-15s %-18s %-17s %-13s %s\n" "key" "read by the code" "as" "README" "example"
for k in $all_keys; do
    read -r code as <<< "$(where_code "$k")"
    readme=$(where_readme "$k"); example=$(where_example "$k")
    [ "$code" = "-" ] && code="- !"                          # K2: documented, not read
    [ "$code" != "- !" ] && [ "$readme" = "-" ] && readme="- !"   # K1: read, undocumented
    case "$k" in *.*) [ "$code" != "- !" ] && [ "$example" = "-" ] && example="- !" ;; esac   # K3
    printf "  %-15s %-18s %-17s %-13s %s\n" "$k" "$code" "$as" "$readme" "$example"
done

read_only=$(comm -23 <(echo "$code_keys") <(echo "$doc_keys"))
both=$(comm -12 <(echo "$code_keys") <(echo "$doc_keys"))
doc_only=$(comm -13 <(echo "$code_keys") <(echo "$doc_keys"))
count() { echo -n "$1" | grep -c . ; }

echo
echo "SETS   (K1: the left column is empty -- K2: the right column is empty)"
printf "  %-20s|  %-20s|  %s\n" "READ, UNDOCUMENTED" "READ AND DOCUMENTED" "DOCUMENTED, NOT READ"
printf "  %-20s+--%-20s+--%s\n" "--------------------" "--------------------" "--------------------"
paste -d'@' <(echo "$read_only") <(echo "$both") <(echo "$doc_only") |
while IFS='@' read -r a b c; do
    printf "  %-20s|  %-20s|  %s\n" "${a:- }" "${b:- }" "${c:- }" | sed 's/ *$//'
done
missing_example=$(for k in $code_keys; do case "$k" in *.*) [ "$(where_example "$k")" = "-" ] && echo "$k";; esac; done)
echo
[ -n "$missing_example" ] && echo "K3  INI keys read, missing in config.example.ini: $(echo $missing_example)"
findings=$(( $(count "$read_only") + $(count "$doc_only") + $(count "$missing_example") ))
echo "keys: $(count "$all_keys")   K1 + K2 + K3 ((findings: $findings))   law == 0   $([ $findings = 0 ] && echo kept || echo BROKEN)"
echo "<hwut-end>"
