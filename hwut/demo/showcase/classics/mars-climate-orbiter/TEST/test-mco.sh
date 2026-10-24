#! /bin/bash
# @hwut {
#     title    = "Mars Climate Orbiter (1999): impulse in lbf*s where N*s was expected -- the AMD file, read with its units"
#     choices {
#         newton-seconds { features = ["amd-table", "impulse-as-fired", "periapsis-safe"]
#                          tolerance { constraints = ["abs(total - 10.0 lbf*s) <= 0.01 lbf*s", "periapsis >= 80 km"] } }
#         tagged-lbf     { features = ["amd-table", "impulse-as-fired", "unit-converted", "periapsis-safe"]
#                          tolerance { constraints = ["abs(total - 10.0 lbf*s) <= 0.01 lbf*s", "periapsis >= 80 km"] } }
#         mco-1999       { features = ["amd-table", "underread-named", "periapsis-lost"]
#                          tolerance { constraints = ["total < 10.0 lbf*s", "periapsis < 80 km"] } }
#     }
# }
# ____________________________________________________________________________
# SUBJECT  the AMD file that the ground program SM_FORCES delivers for a
#          model cruise, as navigation reads it, and the periapsis it leads to
# HISTORY  NASA's Mars Climate Orbiter was lost on 23 September 1999 during
# Mars orbit insertion: it passed far lower than planned and was destroyed
# or skipped off into space. The Mishap Investigation Board (Phase I report,
# 10 November 1999) named the root cause: the ground software 'SM_FORCES'
# wrote the impulse of the angular momentum desaturation (AMD) thruster
# firings to the AMD file in pound-force seconds, while the Software
# Interface Specification -- and the navigation software that read the
# file -- expected newton-seconds. Every desaturation was modelled 4.45
# times too small; over the cruise the error grew, and the reconstructed
# periapsis was about 57 km against a planned 226 km. The MIB took 80 km
# as the lowest survivable periapsis.
#
# REQUIREMENT  The AMD file gives each event's impulse as fired, in the
#              unit it names: over the model cruise (50 s of firing at a
#              rated 0.2 lbf) navigation takes 10.0 lbf*s in all, and the
#              periapsis stays at or above 80 km.
#
# THE UNIT  '../sm_forces.c' (C), the model of SM_FORCES, built per choice
# (-DUNITS=...), over the thruster log '../thruster-log.txt' (a dozen
# model events, not MCO's telemetry). 'navigation.pype' is the reading
# side: it binds every impulse as '<imp = quantity(N*s)>' -- the number in
# N*s, whatever unit the line names -- flies each event at the rated
# thrust (on-time x 0.2 lbf) beside it, and carries the shortfall into a
# periapsis (a MODEL, fitted: the 1999 under-read gives the MIB's 57 km).
#
# CHOICES
#     newton-seconds  what the interface asked for: N*s, tagged 'N*s'.
#     tagged-lbf      the file keeps lbf*s but SAYS so ('0.8000 lbf*s'):
#                     the pype converts on reading, every row reads as
#                     flown -- the units do the work, not the producer.
#     mco-1999        lbf*s numbers under the tag 'N*s': each row reads
#                     4.45 times too small ('!!'), 34.5 N*s go unmodelled,
#                     and the spacecraft flies at 57 km.
#
# THE LAWS, IN THE SOURCES' UNITS  The total is printed in N*s (what
# navigation takes) and judged in lbf*s, the unit of the thruster's rating:
# 'abs(total - 10.0 lbf*s) <= 0.01 lbf*s' -- 44.4822 N*s holds it, the
# comparison converts; 10.0000 N*s (the mislabelled file) breaks it, by
# its VALUE: it has the right dimension. The periapsis is judged in km
# against the MIB's 80 km: 'periapsis >= 80 km' for the holding choices,
# 'periapsis < 80 km' and 'total < 10.0 lbf*s' for mco-1999, whose GOOD is
# the accepted report of the loss.
#
# HOW TO READ THE GOOD  The column 'AMD file says' is the producer's text;
# 'navigation reads' is what the pype bound, in N*s; 'flown' is physics.
# Where the last two differ the row ends in '!!' with their ratio -- 4.45
# in every row of mco-1999. Everything is deterministic and exact.
# ____________________________________________________________________________
HERE=$(cd "$(dirname "$0")" && pwd)
UNIT="$HERE/.."
case "$1" in
    newton-seconds) units=UNITS_SI ;;
    tagged-lbf)     units=UNITS_TAGGED ;;
    mco-1999)       units=UNITS_MCO_1999 ;;
    *) echo "choices: newton-seconds, tagged-lbf, mco-1999"; exit 1 ;;
esac
BUILD=$(mktemp -d)
trap 'rm -rf "$BUILD"' EXIT
gcc -Wall -Werror -DUNITS=$units -o "$BUILD/sm_forces" "$UNIT/sm_forces.c" || exit 1

case "$units" in
    UNITS_SI)       how="computes N*s, tags it 'N*s'" ;;
    UNITS_TAGGED)   how="computes lbf*s, tags it 'lbf*s'" ;;
    UNITS_MCO_1999) how="computes lbf*s, tags it 'N*s' as the interface demands" ;;
esac
echo "ground program: sm_forces.c -DUNITS=$units -- $how; thruster log: thruster-log.txt"
echo "the AMD file, as navigation reads it:"
"$BUILD/sm_forces" < "$UNIT/thruster-log.txt" | hwut.pype "$HERE/navigation.pype"
