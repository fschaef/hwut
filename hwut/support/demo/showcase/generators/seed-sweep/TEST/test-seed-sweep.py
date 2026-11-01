#! /usr/bin/env python3
# @hwut {
#     title    = "Seed sweep: do N seeds of DeterministicStream give N different streams?"
#     features = ["alive"]
#     choices {
#         splitmix       { features = ["alive", "first-draws-spread"]
#                          tolerance { constraints = ["dead == 0", "lockstep <= 249"] } }
#         consecutive    { features = ["alive", "dead-and-striped"]
#                          tolerance { constraints = ["dead > 0", "lockstep > 249"] } }
#         multiplicative { features = ["alive", "linear-named"]
#                          tolerance { constraints = ["dead == 0", "lockstep > 249"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the first draws of 1000 runs seeded by one campaign scheme
         (../campaign.py), and their correlation
REQUIREMENT  A fuzz campaign of 1000 runs explores 1000 different streams:
             no run's stream is constant, and the first draw of run i+1
             does not follow from that of run i (the first draws decide the
             shape of the input, so correlated first draws mean a campaign
             that tries one shape after the other in lock-step).

The unit is the seeding scheme in '../campaign.py': 'seed_consecutive'
(run i gets seed i, as one writes it first -- and as a "sweep many seeds"
advice reads), 'seed_multiplicative' (Knuth's multiplicative hash into
1..2^31-2) and 'seed_splitmix' (the splitmix64 finaliser into 1..2^31-2).

WHAT THIS SHOWS ABOUT THE GENERATOR (hwut's DeterministicStream, MINSTD):
  - seed 0 is DEAD: state 0 * 48271 stays 0, every draw is the lower bound.
    So are -1, 2^31-1 and every multiple of 2^31 ('seed & 0x7FFFFFFF' maps
    them to 0 or to the modulus). The module neither refuses nor documents
    it.
  - the first state is 48271 * seed; 48271 = 1 (mod 10) and (mod 2), so as
    long as 48271 * seed < 2^31 - 1 (seed < 44488) the first next_int(0, 9)
    IS seed mod 10 and the first coin is seed mod 2.

THE GENERATOR INSTRUCTION under test: 'run i -> seed_of(i) ->
DeterministicStream(seed).next_int(0, 9), 16 draws'. The picture shows runs
0..23 as rows of draws; the statistics cover all 1000 runs.

splitmix        no dead run; the step from run i's first draw to run
                i+1's is spread over all ten values.
consecutive     run 0 is a row of zeros; column 1 counts 0 1 2 ... 9 0 1
                down the rows; the step histogram is ONE bar: +1, 999
                times. The plain histogram of first draws is perfectly flat
                (100 each) -- a uniformity check would pass it.
multiplicative  the scrambled-looking seeds are still a linear function of
                i, and MINSTD's first state is linear in the seed: the
                first draws follow a lattice, the step histogram has four
                bars and one of them holds more than half the pairs. A
                linear hash does not decorrelate a linear generator.

HOW TO READ THE GOOD   Rows of digits: look down the first column. Then the
first-draw histogram (not the evidence: flat for consecutive, 100 each; for
multiplicative odd digits about 140, even ones about 60 -- skewed, yet a
skew says nothing about lock-step), and the step histogram (the evidence);
each states its scale, '-' an empty bar. Then the two laws as bindings with
their bounds -- dead runs '== 0', the largest step bucket '<= 249' (a
quarter of the 999 steps; uniform steps give about 100) -- and a verdict in
words: uncorrelated, live but correlated, or dead. All exact: integer
arithmetic, nothing varies.
______________________________________________________________________________
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
from hwut.test_writing_support.python.deterministic_random import DeterministicStream

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import campaign

RUNS, SHOWN, DRAWS = 1000, 24, 16
CHOICE_DB = {"splitmix": campaign.seed_splitmix, "consecutive": campaign.seed_consecutive,
             "multiplicative": campaign.seed_multiplicative}


def bar(n, total, width=40):
    return "#" * (n * width // total) if n * width // total else "-"


def main(choice):
    seed_of = CHOICE_DB[choice]
    streams = []
    for i in range(RUNS):
        s = DeterministicStream(seed_of(i))
        streams.append([s.next_int(0, 9) for _ in range(DRAWS)])

    print("scheme: campaign.seed_%s, %d runs, stream = next_int(0, 9)" % (choice, RUNS))
    print()
    print("##! verbatim")
    print("   run        seed   draws 1..%d" % DRAWS)
    for i in range(SHOWN):
        print("  %4d  %10d   %s" % (i, seed_of(i), " ".join(str(d) for d in streams[i])))
    print("####")
    print()
    dead = [i for i in range(RUNS) if len(set(streams[i])) == 1]
    first = [row[0] for row in streams]
    print("first draw, histogram over %d runs, one '#' per 5 runs (flat is NOT enough):" % RUNS)
    for d in range(10):
        n = first.count(d)
        print("  %d  %4d  %s" % (d, n, bar(n, RUNS, 200)))
    print()
    steps = [(first[i + 1] - first[i]) % 10 for i in range(RUNS - 1)]
    print("step first(i+1) - first(i) mod 10, histogram over %d pairs, one '#' per 25 pairs:" % (RUNS - 1))
    for d in range(10):
        n = steps.count(d)
        print("  +%d %4d  %s" % (d, n, bar(n, RUNS - 1)))
    lockstep = max(steps.count(d) for d in range(10))
    bound = (RUNS - 1) // 4
    print()
    print("dead runs, all %d draws equal ((dead: %d))%s   law == 0   %s"
          % (DRAWS, len(dead), " %s" % dead[:5] if dead else "", "kept" if not dead else "BROKEN"))
    print("largest step bucket ((lockstep: %d)) of %d   law <= %d (a quarter)   %s"
          % (lockstep, RUNS - 1, bound, "kept" if lockstep <= bound else "BROKEN"))
    print("verdict: %s" % ("%d live, uncorrelated runs" % RUNS if not dead and lockstep <= bound
                           else "live but correlated: the first draws move in lock-step" if not dead
                           else "dead runs, and the live ones move in lock-step"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
