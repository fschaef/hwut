#! /usr/bin/env python3
# @hwut {
#     title    = "Peterson's mutual exclusion, proved over every reachable state -- and two broken locks"
#     choices {
#         peterson         { features = ["all-schedules", "state-closure", "exclusion-holds"]
#                            tolerance { constraints = ["reentered > 0", "bad_states == 0"] } }
#         turn-first       { features = ["all-schedules", "state-closure", "violation-drawn"]
#                            tolerance { constraints = ["reentered > 0", "bad_states > 0"] } }
#         flag-after-check { features = ["all-schedules", "state-closure", "violation-drawn"]
#                            tolerance { constraints = ["reentered > 0", "bad_states > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the states two processes under one mutual-exclusion algorithm
         can reach, in every interleaving: both inside, or never
HISTORY  Mutual exclusion for two processes with nothing but reads and
writes was first solved by Th. J. Dekker; Dijkstra published the solution
in 'Cooperating Sequential Processes' (EWD123, 1965). G. L. Peterson's
algorithm ('Myths About the Mutual Exclusion Problem', Information
Processing Letters 12(3), 1981) does it in three lines and became the
textbook proof exercise: flag[i] = 1; turn = j; wait while flag[j] and
turn == j. Its two writes look interchangeable, and the naive lock 'wait
while the other's flag is up, then raise mine' looks fine. Both are wrong.

REQUIREMENT  Never are both processes in their critical section at once
             -- in ANY interleaving of their atomic steps, on any entry,
             the first or the hundredth.

THE UNIT  '../locks.py': each protocol as an explicit step machine, one
atomic read or write per step; each process loops FOREVER: entry protocol,
critical section, flag down, entry again. So the exit protocol is part of
what is judged (a wrong exit only harms the NEXT entry).

THE PROOF: EVERY INTERLEAVING, MERGED BY STATE  A schedule is a word over
{A, B}: which process takes the next step. Two schedules that lead to the
same system state -- (pc of A, pc of B, flag[0], flag[1], turn) -- have the
same futures. So the test walks the schedules breadth-first, extends each by
'A' and by 'B', and drops a schedule whose state was reached before. The
walk ends when a length adds no new state: then every reachable state has
been visited, and 'both inside' is a property of a state. Printed: the new
states per schedule length, their total, and '((bad_states: N))' -- the
reachable states with both inside. THE LAW IS ON bad_states.

THE PICTURE: all words of length 10, 'space_iterator.do([["A", "B"]] * 10)'
= 1024 schedules as a 32 x 32 grid. It illustrates; it does not prove (a
violation may need more than 10 steps). '((reentered: N))' counts the grid
schedules in which a process entered its critical section a SECOND time --
law 'reentered > 0' guards that the model really exercises re-entry.

CHOICES
    peterson          no reachable state has both inside. Law 'bad_states == 0'.
    turn-first        turn = j BEFORE flag[i] = 1: A sets turn, B sets turn
                      and flag and enters, A raises its flag, sees turn = A
                      (B wrote it last) and enters too.
    flag-after-check  the naive lock: both read the other's flag down, both
                      raise their own, both enter.

HOW TO READ THE GOOD  The grid: row = first five steps, column = last five
('A' = A steps); '.' never both inside, 'X' both inside at some step.
Under it, the SHORTEST violating schedule from the walk as two lanes, one
letter per step (f flag raised, t turn written, w read and waits, r read
and goes, C inside, x flag lowered); '^' marks where both are first inside.
All pictures '##! verbatim', all exact: no threads, no clock.
______________________________________________________________________________
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
import hwut.test_writing_support.python.space_iterator as space_iterator

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import locks

CHOICES = ("peterson", "turn-first", "flag-after-check")
LENGTH = 10


def apply(name, state, who):
    """RETURN: (next state, code) after one step of process 'who' (0 or 1)."""
    pc = list(state[:2])
    shared = locks.Shared()
    shared.flag, shared.turn = list(state[2:4]), state[4]
    pc[who], code = locks.step(name, shared, who, pc[who])
    return (pc[0], pc[1]) + shared.key(), code


def both_inside(name, state):
    return state[0] in locks.INSIDE[name] and state[1] in locks.INSIDE[name]


def walk(name):
    """RETURN: (new states per length, number of states, bad states,
               shortest word to a bad state or None)."""
    start = (0, 0, 0, 0, 0)
    seen, frontier, added, bad, first_bad = {start}, [(start, "")], [1], 0, None
    while frontier:
        nxt = []
        for state, word in frontier:
            for who, letter in ((0, "A"), (1, "B")):
                s2, _ = apply(name, state, who)
                if s2 in seen:
                    continue
                seen.add(s2)
                nxt.append((s2, word + letter))
                if both_inside(name, s2):
                    bad += 1
                    first_bad = first_bad or word + letter
        added.append(len(nxt))
        frontier = nxt
    return added, len(seen), bad, first_bad


def replay(name, word):
    """RETURN: ([(who, code)], step index where both are first inside or None,
               entries per process)."""
    state, codes, both_at, entries = (0, 0, 0, 0, 0), [], None, [0, 0]
    for k, letter in enumerate(word):
        who = "AB".index(letter)
        state, code = apply(name, state, who)
        codes.append((who, code))
        entries[who] += code == "C"
        if both_at is None and both_inside(name, state):
            both_at = k
    return codes, both_at, entries


def main(name):
    added, n_states, bad, first_bad = walk(name)
    print("protocol: %s    each process: entry, critical section, exit -- forever" % name)
    print("walk of all interleavings, merged by state:")
    print("  new states by schedule length 0..%d: %s" % (len(added) - 1, " ".join(map(str, added))))
    print("  reachable states: %d (a length adding none ends the walk)" % n_states)
    print("  states with both inside: ((bad_states: %d))   law == 0   %s" % (bad, "kept" if not bad else "BROKEN"))
    print()
    words = ["".join(w) for w in space_iterator.do([["A", "B"]] * LENGTH)]
    result = {w: replay(name, w) for w in words}
    half = LENGTH // 2
    heads = ["".join(w) for w in space_iterator.do([["A", "B"]] * half)]
    print("GRID of the %d schedules of length %d: row = first %d steps, column = last %d;"
          " '.' never both inside, 'X' both inside" % (len(words), LENGTH, half, half))
    print("(a schedule names, step by step, the process that takes the next atomic step: A or B)")
    print("##! verbatim")
    for k in range(half):
        print("%s %s" % (" " * half, "".join(h[k] for h in heads)))
    violations = reentered = 0
    for head in heads:
        row = ""
        for tail in heads:
            _, both_at, entries = result[head + tail]
            row += "X" if both_at is not None else "."
            violations += both_at is not None
            reentered += max(entries) >= 2
        print("%s %s" % (head, row))
    print("####")
    print("grid: both inside in %d of %d schedules" % (violations, len(words)))
    print("schedules that exercise re-entry (model guard): ((reentered: %d))   law > 0   %s"
          % (reentered, "kept" if reentered else "BROKEN"))
    if first_bad is None:
        return
    codes, both_at, _ = replay(name, first_bad)
    print()
    print("SHORTEST VIOLATING SCHEDULE %s -- both inside after step %d" % (first_bad, both_at + 1))
    print("##! verbatim")
    print("step " + "".join(str((k + 1) % 10) for k in range(len(first_bad))))
    for i, lane in enumerate("AB"):
        print(("%-4s " % lane + "".join(code if who == i else " " for who, code in codes)).rstrip())
    print("both " + "".join("^" if k == both_at else " " for k in range(len(first_bad))).rstrip())
    print("####")
    print("(f raised its flag  t wrote turn  r read, may go  w read and waits  C critical section")
    print(" x lowered its flag; ^ both inside)")


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICES:
        print("choices: %s" % ", ".join(CHOICES))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
