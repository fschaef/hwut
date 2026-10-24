#! /bin/bash
# @hwut {
#     title    = "Crossing controller (C): the lamps walk the reference state chart"
#     choices {
#         one-car     { features = ["chart-walk", "min-green", "car-served"]
#                       tolerance { constraints = ["breaches == 0", "wait <= 20 s"] } }
#         traffic     { features = ["chart-walk", "min-green", "all-red", "car-served"]
#                       tolerance { constraints = ["breaches == 0", "wait <= 20 s"] } }
#         quick-patch { features = ["breach-named"]
#                       tolerance { constraints = ["breaches > 0"] } }
#         bus-patch   { features = ["breach-named", "two-greens-shown"]
#                       tolerance { constraints = ["breaches > 0"] } }
#     }
# }
# ____________________________________________________________________________
# SUBJECT  the lamp timeline of the crossing controller for one car schedule,
#          as the reference chart reads it: breaches and every car's wait
# REQUIREMENT  The lamps of the crossing change only along the reference state
#              chart: NS green (>= 10 s) -> yellow (>= 3 s) -> all red
#              (>= 2 s) -> EW green (>= 8 s) -> yellow -> all red -> NS green.
#              In particular, never two roads green, never green without an
#              all-red clearance before it. A car on EW is served, after NS
#              has had its minimum green: it waits at most 20 s for EW green.
#
# The unit is C ('../lights.c'), on a simulated clock of one tick per second
# ('../sim.c'): it logs every lamp change and every car the sensor sees, with
# the time and its unit ('4 s NS GREEN'). That stream goes into
# 'crossing.pype', the reference chart: one mode per state, each admitting
# the ONE lamp change that may come next, and checking how long the state
# lasted. It binds the log's time as a quantity, '<t = quantity(s)>'. The
# pype draws the lamp timeline -- NS and EW rows of G/Y/R, one column per
# second, cars as 'c' -- names each breach of the chart and binds their
# number, '((breaches: N))'. It MEASURES liveness: every car's wait for EW
# green, the longest bound as a quantity, '((wait: 11 s))' (a controller
# that ignores the sensor walks the chart perfectly; only the wait shows
# it). The laws: 'breaches == 0' and 'wait <= 20 s' for the lawful choices,
# 'breaches > 0' for the broken ones (their wait is a free value: the
# per-car lines pin it). A re-accept cannot bless a new breach or a starved
# car, nor a fix that hides a known breach. The 20 s bound stands in the
# constraint, in seconds -- the comparison converts, so a wait printed as
# '25000 ms' breaks it as surely as '25 s'.
#
# one-car      a car at 4 s waits until NS has had 10 s, then gets its phase.
# traffic      cars at 4, 30, 31 and 45 s: two full cycles; the car at 45 s
#              comes while EW is green and passes at once.
# quick-patch  BROKEN FIXTURE '../lights_quick.c': yellow hands over straight
#              to the other green. Every lamp shows a legal colour; the
#              timeline has no RR column between the roads; a 'short' row
#              marks '^' where each all-red began, and one BREACH line says
#              what was too short and how often.
# bus-patch    BROKEN FIXTURE '../lights_bus.c': two detections in a row are
#              'a bus' and get EW green at once -- NS stays green. The
#              timeline shows G over G at 31..38 s; the law names the first
#              illegal change and stops judging there (the cars after it are
#              listed as not judged).
#
# HWUT CONCEPTS  pype as a runtime monitor: modes ARE the reference states,
# a lamp change that the base mode catches is one no state admits, the
# mandatory '<else>' names a line that is no lamp change at all, 'pype.goto'
# leaves the chart after the first breach; quantities in the pype: the log
# may count in s or ms -- a log rewritten to '4000 ms NS GREEN' keeps all
# four choices green, unchanged; a constraint binding carries the
# verdict into hwut's own judgment. Deterministic input (a simulated
# clock), so the timeline the pype draws is exact; it stands in
# '##! verbatim'. The application prints no <hwut-end>: the pype's <eof> does.
# ____________________________________________________________________________
HERE=$(cd "$(dirname "$0")" && pwd)
UNIT="$HERE/.."
case "$1" in
    one-car)     unit=lights.c;       cars="4" ;;
    traffic)     unit=lights.c;       cars="4 30 31 45" ;;
    quick-patch) unit=lights_quick.c; cars="4 30 31 45" ;;
    bus-patch)   unit=lights_bus.c;   cars="4 30 31 45" ;;
    *) echo "choices: one-car, traffic, quick-patch, bus-patch"; exit 1 ;;
esac
BUILD=$(mktemp -d)
trap 'rm -rf "$BUILD"' EXIT
gcc -Wall -Werror -I"$UNIT" -o "$BUILD/sim" "$UNIT/sim.c" "$UNIT/$unit" || exit 1

echo "unit: $unit; cars on EW at: $cars s"
echo "$cars" | "$BUILD/sim" 60 | hwut.pype "$HERE/crossing.pype"
