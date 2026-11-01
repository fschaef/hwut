#! /bin/bash
#
# @hwut {
#     title   = "Parallel word count: the law of map and reduce, any order"
#     choices {
#         four-at-once { features = ["counts", "order-law", "parallel-cap"]
#                        tolerance { constraints = ["in_flight_max >= 1 and in_flight_max <= 4"] } }
#         v1           { features = ["violation-shown"]
#                        tolerance { constraints = ["in_flight_max > 4"] } }
#     }
# }
#
# ______________________________________________________________________________
# SUBJECT  the event stream of the parallel word count (../wc-par.sh or ../wc-
#          par-v1.sh): start, count, done, total -- as wc.pype judges it
# REQUIREMENT. ../wc-par.sh counts the words of ../corpus/*.txt (12 files)
# with 'xargs -P 4' workers (../count.sh) and an awk reducer:
#     R1  every file is counted once, and the total is the sum of the counts;
#     R2  each file's lines come as start, count, done; 'total' comes after
#         every worker has finished, and is the last line;
#     R3  at most 4 files are in flight at any moment (the box has 4 cores
#         and a build server beside it).
#
# CHOICES
#     four-at-once  ../wc-par.sh: the law holds.
#     v1            ../wc-par-v1.sh, release 1.0 with 'xargs -P 0' ("as many
#                   as possible"): all 12 files run at once. R1 and R2 hold,
#                   R3 breaks.
#
# HWUT CONCEPTS. The workers' lines arrive in the scheduler's order, a new
# one every run. The test application only REPORTS (it runs the tool); the
# pype script ./wc.pype holds the LAW as modes (RUNNING, REDUCED) and prints
# only what does not depend on the order: counts sorted by file, the total,
# the breaches sorted, and '<hwut-end>' at <eof>. The one order-dependent
# measure, the largest number of files in flight, is a constraint binding
# '((in_flight_max: n))' -- 3 or 4 on a given run, judged by '<= 4'.
#
# READING THE GOOD. Words per file; R1 the total against the sum of the
# counts; R2 the order breaches (each as a BREACH line); the in-flight chart
# of this run (one row per file, '=' from its start to its done, columns
# the events in arrival order -- in an 'ignore' region, a picture of this
# run's schedule); R3 the in-flight maximum with its law. Each R line ends
# in 'kept' or 'BROKEN'.
# ______________________________________________________________________________
HERE=$(cd "$(dirname "$0")" && pwd)
case "$1" in
    four-at-once) TOOL=wc-par.sh ;;
    v1)           TOOL=wc-par-v1.sh ;;
    *)            echo "choices: four-at-once, v1"; exit 1 ;;
esac
echo "tool: $TOOL ../corpus"
"$HERE/../$TOOL" "$HERE/../corpus" | hwut.pype "$HERE/wc.pype"
