#! /bin/bash
#
# @hwut {
#     title    = "C headers: module prefix on every macro, include guard named after the file"
#     features = ["prefix", "guard"]
#     choices {
#         good   { tolerance { constraints = ["violations == 0"] } }
#         broken { tolerance { constraints = ["violations > 0"] } }
#     }
# }
#
# ____________________________________________________________________________
# SUBJECT  the include guards and macro prefixes of one set of C headers
#          (good/broken)
# REQUIREMENT (house rules for the headers of an embedded code base)
#
#   P  every macro #defined in <module>.h starts with the module prefix,
#      MODULE_ (uart.h -> UART_). A bare 'BIT' or 'MAX_XFER' collides with
#      the next vendor header that has the same idea.
#   G  the include guard is '#ifndef <MODULE>_H' + '#define <MODULE>_H' as
#      the first two directives, and '#endif' is the last one. A guard named
#      '__X_H__' is a reserved identifier; a guard that defines another name
#      than it tests ('ADC_H' / 'ADC_HH') guards nothing.
#
# HOW: bash and awk read the headers; nothing is compiled. A directive may
# be indented after its '#' ('#  define SPI_TRACE 0' inside an #ifndef) --
# the reader joins '#' and keyword before it splits. The output is
#   1. the GUARD table: one row per header, what it tests, defines, ends;
#   2. the PREFIX RULER: every macro split into the prefix it must carry and
#      the rest -- a missing prefix is a gap in the left column, '------';
#   3. the violations and two counts.
#
# CHOICES
#   good     four headers, every rule kept; spi.h has an overridable
#            '#  define SPI_TRACE' (indented directive).
#   broken   spi.h defines MAX_XFER, gpio.h adds BIT(n) and guards with
#            __GPIO_H__, adc.h tests ADC_H and defines ADC_HH.
#
# HWUT CONCEPTS
#   constraints  'violations == 0' is the requirement of the good choice,
#                stated in the header, so a re-accept cannot bless a
#                violation (hwut.accept refuses it); 'violations > 0' for
#                broken -- the violation is reported, ruler and table say
#                where. The header and macro counts are exact text: a
#                scanner that finds nothing changes them (no vacuous green).
#   exact lines  the ruler and the table; their columns are aligned for the
#                eye only (whitespace runs are tolerated).
#
# READING THE GOOD: look down the left column of the ruler for '------',
# and along the guard table for anything that is not 'ok'.
# ____________________________________________________________________________
HERE=$(cd "$(dirname "$0")" && pwd)

case "$1" in
    good|broken) ;;
    *) echo "choices: good, broken"; exit 1 ;;
esac
cd "$HERE/../$1/include" || exit 1
header_list=$(ls *.h | sort)

echo "headers of '$1/include': $(echo $header_list)"
echo "rules: P  every macro starts with MODULE_   G  the guard is <MODULE>_H, '#endif' last"
echo
echo "GUARD (G)  tests            defines          last directive   verdict"
violations=0
for h in $header_list; do
    want=$(basename "$h" .h | tr a-z A-Z)_H
    row=$(awk -v want="$want" '
        /^[ \t]*#/ { sub(/^[ \t]*#[ \t]*/, "#"); n++; d[n] = $0 }
        END {
            split(d[1], a); split(d[2], b); split(d[n], c)
            v = "ok"
            if (a[1] != "#ifndef" || b[1] != "#define") v = "G NO GUARD"
            else if (a[2] != b[2])   v = "G DEFINES ANOTHER NAME"
            else if (a[2] != want)   v = "G NOT " want
            else if (c[1] != "#endif") v = "G #endif NOT LAST"
            printf "%-16s %-16s %-16s %s", a[2], b[2], c[1], v
        }' "$h")
    printf "%-10s %s\n" "$h" "$row"
    case "$row" in *" ok") ;; *) violations=$((violations + 1)) ;; esac
done

ruler=$(mktemp)
echo
echo "PREFIX RULER (P)   prefix | rest of the macro name     ('------': prefix missing)"
for h in $header_list; do
    prefix=$(basename "$h" .h | tr a-z A-Z)_
    # every #define except the guard's (the second directive)
    awk '/^[ \t]*#/ { sub(/^[ \t]*#[ \t]*/, "#"); n++ } /^#define/ && n != 2 { sub(/\(.*/, "(..)", $2); print $2 }' "$h" |
    while read -r macro; do
        case "$macro" in
            "$prefix"*) printf "  %-9s %8s | %s\n" "$h" "$prefix" "${macro#$prefix}" ;;
            *)          printf "  %-9s %8s | %-24s <- P: not %s\n" "$h" "------" "$macro" "$prefix" ;;
        esac
    done
done > "$ruler"
cat "$ruler"
missing=$(grep -c -- '------ |' "$ruler")
macros=$(wc -l < "$ruler")
rm -f "$ruler"
guard=$violations
violations=$((violations + missing))

echo
echo "macros: $macros   headers: $(echo $header_list | wc -w)"
echo "G guard: $guard   P prefix: $missing   ((violations: $violations))   law == 0   $([ $violations = 0 ] && echo kept || echo BROKEN)"
echo "<hwut-end>"
