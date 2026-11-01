#! /bin/bash
#
# @hwut {
#     title   = "CLI contract of crc32: argument case x exit code x stream"
#     choices {
#         current { features = ["check-value", "exit-codes", "streams", "keeps-going"]
#                   tolerance { constraints = ["breaches == 0"] } }
#         v1      { features = ["violation-shown"]
#                   tolerance { constraints = ["breaches > 0"] } }
#     }
# }
#
# ______________________________________________________________________________
# SUBJECT  the exit code, stdout and stderr of the crc32 command (../crc32.c
#          or ../crc32_v1.c) for each argument case
# REQUIREMENT. The command-line contract of ../crc32.c, the one scripts rely on:
#     R1  'crc32 check' over "123456789" prints CBF43926 (the CRC-32 check
#         value) -- results on stdout, nothing else there;
#     R2  exit 0 when every file was read, 1 when a file could not be read,
#         2 for a bad command line; --help is not an error (exit 0);
#     R3  every complaint goes to stderr, prefixed 'crc32: ';
#     R4  a bad file does not stop the others.
#
# CHOICES -- the same matrix of argument cases, two builds:
#     current  ../crc32.c: every row 'ok' (law: breaches == 0).
#     v1       ../crc32_v1.c, release 1.0: errors on stdout, exit 0 on a
#              missing file (a script's 'crc32 f || alarm' never fires), a
#              directory gets a CRC of 00000000, --help exits 1
#              (law: breaches > 0).
#
# HWUT CONCEPT. The test application, not hwut, captures stdout, stderr and
# the exit status of each case and prints them as one row of a matrix -- the
# process boundary of the tool under test becomes text. Nothing varies: the
# matrix and every line on both streams are compared exactly, in full; the
# two builds land in a fresh scratch directory per run, which is never
# printed. The number of rows that break a rule is a constraint binding
# '((breaches: n))', judged by the choice's law.
#
# READING THE GOOD. The rule key R1..R4 heads the matrix. One row per
# argument case: the exit status wanted and got, and the verdict naming the
# rule the row breaks ('R2:exit'); under it every line the case wrote, as
# 'out|' (stdout) or 'err|' (stderr). The last line states the law and its
# verdict, 'kept' or 'BROKEN'.
# ______________________________________________________________________________
HERE=$(cd "$(dirname "$0")" && pwd)
TOP=$HERE/..
case "$1" in
    current) SOURCE=crc32.c ;;
    v1)      SOURCE=crc32_v1.c ;;
    *)       echo "choices: current, v1"; exit 1 ;;
esac
SCRATCH=$(mktemp -d)
trap 'rm -rf "$SCRATCH"' EXIT
gcc -O2 -o "$SCRATCH/crc32" "$TOP/$SOURCE" || exit 1
export LC_ALL=C
cd "$TOP"

# row  <case name> <wanted exit> <stdout wanted: data|usage|none> <stderr wanted: yes|no> -- <argv...>
row() {
    local name=$1 want=$2 want_out=$3 want_err=$4; shift 5
    "$SCRATCH/crc32" "$@" < check > "$SCRATCH/out" 2> "$SCRATCH/err"
    local got=$?
    local out err verdict=""
    out=$(head -n 1 "$SCRATCH/out"); err=$(head -n 1 "$SCRATCH/err")
    [ "$got" = "$want" ]                       || verdict="$verdict R2:exit"
    case "$want_out" in
        data)  grep -qvE '^[0-9A-F]{8}  ' "$SCRATCH/out" && verdict="$verdict R1:stdout" ;;
        usage) grep -q '^Usage:' "$SCRATCH/out" || verdict="$verdict R2:help" ;;
        none)  [ -s "$SCRATCH/out" ] && verdict="$verdict R3:stdout" ;;
    esac
    if [ "$want_err" = yes ]; then
        grep -q '^crc32: \|^Usage:' "$SCRATCH/err" || verdict="$verdict R3:stderr"
    else
        [ -s "$SCRATCH/err" ] && verdict="$verdict R3:stderr"
    fi
    if [ "$name" = "missing among good" ]; then
        [ "$(grep -cE '^[0-9A-F]{8}  ' "$SCRATCH/out")" = 2 ] || verdict="$verdict R4:stopped"
    fi
    local argv="$*"
    printf "%-19s %-19s %9s %8s  %s\n" "$name" "${argv:-(none)}" "$want" "$got" "${verdict:- ok}"
    sed 's/^/    out| /' "$SCRATCH/out"
    sed 's/^/    err| /' "$SCRATCH/err"
    [ -n "$verdict" ] && breaches=$((breaches + 1))
}

breaches=0
echo "crc32 built from $SOURCE"
echo "rules: R1 results on stdout, nothing else there   R2 exit 0 all read, 1 a file unreadable,"
echo "       2 bad command line (--help: 0, usage on stdout)   R3 complaints on stderr, 'crc32: ...'"
echo "       R4 a bad file does not stop the others"
printf "%-19s %-19s %9s %8s  %s\n" "case" "argv" "exit want" "exit got" "verdict"
row "check value"        0 data  no  -- check
row "empty file"         0 data  no  -- empty
row "standard input"     0 data  no  -- -
row "help"               0 usage no  -- --help
row "missing file"       1 none  yes -- nofile
row "missing among good" 1 data  yes -- check nofile empty
row "directory"          1 none  yes -- TEST
row "no argument"        2 none  yes --
row "unknown option"     2 none  yes -- -x check
echo "rows breaking a rule ((breaches: $breaches))   law == 0   $([ $breaches = 0 ] && echo kept || echo BROKEN)"
echo "<hwut-end>"
