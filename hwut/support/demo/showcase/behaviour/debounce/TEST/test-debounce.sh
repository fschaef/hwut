#! /bin/bash
# @hwut {
#     title    = "Button debouncer: no output pulse shorter than the threshold"
#     features = ["min-pulse", "one-press-one-pulse"]
#     choices {
#         counter-press   { tolerance { constraints = ["shortest >= 5 ms", "high_pulses == 1"] } }
#         counter-chatter { tolerance { constraints = ["shortest >= 5 ms", "high_pulses == 1"] } }
#         naive-chatter   { features = ["glitch-named"]
#                           tolerance { constraints = ["short_pulses > 0", "high_pulses > 1"] } }
#     }
# }
# ____________________________________________________________________________
# SUBJECT  the debounced level of one button press, drawn under the raw contact
#          signal, and the length of every output pulse it makes
# REQUIREMENT  The debounced button level never changes twice within 5 ms
#              (the threshold): no output pulse is shorter than 5 ms, and one
#              press gives exactly one high pulse.
#
# The unit is C ('../debounce.c', an integrating counter), compiled with the
# driver '../drive.c' into a scratch directory. A raw waveform from
# '../signals/' -- '_' low, '-' high, one character per 1 ms tick, recorded
# from a real tactile switch and drawn as text -- is fed through it.
#
# The output draws RAW and DEBOUNCED one above the other on a millisecond
# ruler (in '##! verbatim': the column of an edge IS the time; a '^' row marks
# the start of every pulse shorter than the threshold), then lists
# every pulse of the output with its start and length, and binds what the law
# is about: the shortest pulse as a QUANTITY, '((shortest: 5 ms))', and the
# counts '((high_pulses: N))' and '((short_pulses: N))' -- each printed beside
# its law and a verdict word, kept / BROKEN.
#
# counter-press    a clean press with bounce at both edges: one pulse.
# counter-chatter  a worn switch: 3 ms bursts and a 1 ms dropout in the
#                  middle of the press. Still exactly one pulse.
# naive-chatter    the BROKEN FIXTURE '../debounce_naive.c' ('two samples
#                  agree') on the same signal: the GOOD file is the accepted
#                  violation report -- every pulse below 5 ms marked '!!'.
#
# HWUT CONCEPTS  '##! verbatim' for the picture: it pins every edge, so any
# change of the output turns the run red, lawful or not. The constraint
# bindings carry the LAW into hwut's own judgment: "shortest >= 5 ms" (the
# requirement in its own unit -- '((shortest: 5 ms))' binds a quantity, the
# comparison converts, so a run printing '0.003 s' or a bare '3' breaks it
# as well) and "high_pulses == 1" for the two choices that must keep it;
# "short_pulses > 0" and "high_pulses > 1" for the broken one (there the
# shortest pulse is a free value: the '!!' lines pin it). At run time the
# picture fails first; the law guards the RE-RECORDING -- 'hwut.accept' refuses a
# new picture with a short pulse or a second pulse per press on a counter
# choice, and a 'fixed' naive one that no longer shows the violation. A
# reviewer looks at the picture and the '!!' lines.
# ____________________________________________________________________________
HERE=$(cd "$(dirname "$0")" && pwd)
UNIT_DIR="$HERE/.."
THRESHOLD=5

case "$1" in
    counter-press)   unit=debounce.c;       signal=press.txt ;;
    counter-chatter) unit=debounce.c;       signal=chatter.txt ;;
    naive-chatter)   unit=debounce_naive.c; signal=chatter.txt ;;
    *) echo "choices: counter-press, counter-chatter, naive-chatter"; exit 1 ;;
esac

BUILD=$(mktemp -d)
trap 'rm -rf "$BUILD"' EXIT
gcc -Wall -Werror -O2 -I"$UNIT_DIR" -o "$BUILD/drive" "$UNIT_DIR/drive.c" "$UNIT_DIR/$unit" || exit 1

raw=$(tr -d '\n' < "$UNIT_DIR/signals/$signal")
out=$("$BUILD/drive" $THRESHOLD <<< "$raw")

echo "unit:   $unit, threshold $THRESHOLD ms"
echo "signal: signals/$signal, one character per 1 ms"
echo
awk -v raw="$raw" -v out="$out" -v thr=$THRESHOLD '
function edges(s,    i, n) { n = 0; for (i = 2; i <= length(s); ++i) if (substr(s, i, 1) != substr(s, i-1, 1)) ++n; return n }
BEGIN {
    n = length(raw)
    ruler = ""; ticks = ""
    for (i = 0; i < n; ++i) {
        if (i % 10 == 0) { label = sprintf("%d", i); ruler = ruler label; skip = length(label) - 1 }
        else if (skip > 0) { --skip }
        else ruler = ruler " "
        ticks = ticks (i % 10 == 0 ? "|" : ".")
    }
    start = 0; first = 1; bad = 0; high_n = 0; np = 0; marks = ""
    for (i = 0; i < n; ++i) marks = marks " "
    for (i = 2; i <= n + 1; ++i) {
        if (i <= n && substr(out, i, 1) == substr(out, i-1, 1)) continue
        if (!first && i <= n) {
            len = i - 1 - start
            level = substr(out, start + 1, 1) == "-" ? "high" : "low"
            high_n += level == "high"
            bad += len < thr
            if (len < thr) marks = substr(marks, 1, start) "^" substr(marks, start + 2)
            if (shortest == "" || len < shortest) shortest = len
            line[++np] = sprintf("    %-4s  from %3d ms  for %3d ms   %s", level, start, len,
                                 len < thr ? "!! shorter than " thr " ms" : "ok")
        }
        first = 0; start = i - 1
    }
    print "##! verbatim"
    printf "%-11s%s\n", "ms",        ruler
    printf "%-11s%s\n", "",          ticks
    printf "%-11s%s\n", "raw",       raw
    printf "%-11s%s\n", "debounced", out
    sub(/ +$/, "", marks)
    if (bad) printf "%-11s%s\n", "", marks
    print "####"
    printf "(one character per 1 ms; raw and debounced: \047-\047 high, \047_\047 low%s)\n", bad ? "; \047^\047 a pulse shorter than " thr " ms" : ""
    print ""
    printf "edges: raw %d, debounced %d\n", edges(raw), edges(out)
    print "debounced pulses (between two edges):"
    for (k = 1; k <= np; ++k) print line[k]
    printf "shortest pulse:             ((shortest: %d ms))   law >= %d ms   %s\n", shortest, thr, (shortest >= thr ? "kept" : "BROKEN")
    printf "pulses shorter than %d ms:   ((short_pulses: %d))   law == 0      %s\n", thr, bad, bad ? "BROKEN" : "kept"
    printf "high pulses for one press:  ((high_pulses: %d))   law == 1      %s\n", high_n, high_n == 1 ? "kept" : "BROKEN"
}'
echo "<hwut-end>"
