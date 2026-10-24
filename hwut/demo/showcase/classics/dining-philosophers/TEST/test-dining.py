#! /usr/bin/env python3
# @hwut {
#     title    = "Dining philosophers (Dijkstra): real threads, a waits-for cycle found, resource ordering fixes it"
#     choices {
#         naive   { features = ["threads-named", "cycle-found", "cycle-drawn"]
#                   tolerance { constraints = ["cycles > 0"] } }
#         ordered { features = ["threads-named", "everyone-eats"]
#                   tolerance { constraints = ["cycles == 0", "hungry == 0"] } }
#     }
#     caps { timeout_sec = 30 }
# }
"""
______________________________________________________________________________
SUBJECT  the order in which five philosopher threads take their forks, the
         waits-for cycle they may form, and who finished eating
HISTORY  E. W. Dijkstra posed the problem around 1965 as an exam exercise
(five computers competing for shared tape drives); the story of five
philosophers who need two forks each was told by C. A. R. Hoare. In
'Hierarchical Ordering of Sequential Processes' (EWD310, 1971) Dijkstra
discusses it: if every philosopher takes the left fork and then waits for
the right, all five can hold one fork and wait forever -- a deadlock. One
classic cure is a global order on the resources: always take the lower-
numbered fork first; then no cycle of waits can close.

REQUIREMENT  The philosophers never deadlock: the waits-for graph (a
             philosopher waits for a fork, the fork's holder is the next
             philosopher) never contains a cycle, and every philosopher eats
             all his meals.

THE UNIT  '../philosophers.py': five REAL threads, five forks as locks that
report who holds and who waits; 'naive' (left, then right) and 'ordered'
(lower fork first). A rendezvous -- everyone has his first fork, or is
blocked on it, before anyone reaches for the second -- makes the naive
deadlock certain on every run instead of a matter of scheduling luck, so
the violation report is stable (hwut.run.stability over the area).

THE DETECTOR (application logic, not a timeout)  The test reads the table's
holder/waiter record every 20 ms under its lock -- a consistent snapshot --
and follows the waits-for edges. A cycle in a consistent snapshot is a
deadlock: every philosopher on it waits for a lock held by one who waits.
The cycle is printed and the process ends. A TIMEOUT GUARD of 10 s ends a
run that neither finishes nor shows a cycle (a livelock, a lost wakeup);
'caps { timeout_sec = 30 }' is hwut's guard above that.

ANALOGIES  A fork's address changes on every run, but inside one run it
must be used consistently. It is printed as an analogy '((0x...))' beside
the fork's number: the seat list binds each fork once; every later row --
'seat 2  holds F2 ((F))  waits for F3 ((G))  held by seat 3' -- must use the
same values for the same forks. A detector that named the wrong fork would
break a binding; a hard-coded report would not even have the values. The
seats identify the threads, so thread idents are not printed (they added
clutter, no check). Seat and fork numbers are plain.

CHOICES
    naive    the five-way cycle P0 -> P1 -> P2 -> P3 -> P4 -> P0, nobody
             eats. Law 'cycles > 0'.
    ordered  no cycle, 15 meals. Laws 'cycles == 0', 'hungry == 0'.

HOW TO READ THE GOOD  The chain 'P0 -[F1]-> P1' reads: philosopher 0 waits
for fork 1, which philosopher 1 holds. It closes on P0: the cycle. It
stands in '##! verbatim'. Meals are counts per seat -- the ORDER of
eating varies with the scheduler and is not printed.
______________________________________________________________________________
"""
import os
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import philosophers as ph

POLICIES = ("naive", "ordered")
GUARD_S = 10.0


def find_cycle(table, seat_of):
    """RETURN: [(seat, held fork, wanted fork, next seat)] of a waits-for
               cycle in a consistent snapshot, or None."""
    with table.cond:
        holder = dict(table.holder)
        waiting = dict(table.waiting)
    for start in sorted(waiting, key=lambda t: seat_of.get(t, 99)):
        path, t = [], start
        while t in waiting and waiting[t] in holder:
            nxt = holder[waiting[t]]
            path.append((t, waiting[t], nxt))
            t = nxt
            if t == start:
                return [(seat_of[a], [f for f, h in holder.items() if h == a], w, seat_of[b])
                        for a, w, b in path]
            if len(path) > ph.SEATS:
                break
    return None


def main(policy):
    table = ph.Table()
    forks = [ph.Fork(table, i) for i in range(ph.SEATS)]
    threads = [threading.Thread(target=ph.philosopher, args=(table, forks, i, policy), daemon=True)
               for i in range(ph.SEATS)]
    for t in threads:
        t.start()
    seat_of = {t.ident: i for i, t in enumerate(threads)}

    def fork_id(f):
        return "((0x%x))" % id(f)

    print("table: %s, %d seats, %d meals each, real threads; fork k lies between seats k-1 and k"
          % (policy, ph.SEATS, ph.MEALS))
    print("policy: %s" % ("each seat takes fork n first, then fork n+1" if policy == "naive"
                          else "each seat takes the lower-numbered of its two forks first"))
    print("seat  takes first          then")
    for i, t in enumerate(threads):
        first, second = ph.fork_order(forks, i, policy)
        print("%-4d  F%d %-18s F%d %s" % (i, first.number, fork_id(first), second.number, fork_id(second)))
    print("(Fk and its object id: the same id must stand for the same fork in every line below)")
    print()
    started, cycle = time.monotonic(), None
    while any(t.is_alive() for t in threads) and time.monotonic() - started < GUARD_S:
        cycle = find_cycle(table, seat_of)
        if cycle:
            break
        time.sleep(0.02)
    alive = sum(t.is_alive() for t in threads)
    if cycle:
        print("DEADLOCK: a waits-for cycle through %d philosophers" % len(cycle))
        print("##! verbatim")
        print("P%d " % cycle[0][0] + " ".join("-[F%d]-> P%d" % (w.number, b) for _, _, w, b in cycle))
        print("####")
        print("(Pn the philosopher at seat n; -[Fk]-> waits for fork k, which the next one holds)")
        print("seat  holds                 waits for             held by")
        for a, held, w, b in cycle:
            print("%-4d  %-21s F%d %-18s seat %d"
                  % (a, " ".join("F%d %s" % (f.number, fork_id(f)) for f in held), w.number, fork_id(w), b))
    elif alive:
        print("TIMEOUT: %d philosopher(s) still at the table after %.0f s, no cycle seen" % (alive, GUARD_S))
    else:
        print("no waits-for cycle seen; every thread finished")
    with table.cond:
        meals = dict(table.meals)
    print("meals eaten per seat: %s   (total %d of %d)"
          % ("  ".join("P%d %d" % (i, meals.get(i, 0)) for i in range(ph.SEATS)),
             sum(meals.values()), ph.SEATS * ph.MEALS))
    hungry = sum(meals.get(i, 0) < ph.MEALS for i in range(ph.SEATS))
    print("waits-for cycles: ((cycles: %d))   law == 0   %s" % (1 if cycle else 0, "BROKEN" if cycle else "kept"))
    print("philosophers who did not finish: ((hungry: %d))   law == 0   %s" % (hungry, "BROKEN" if hungry else "kept"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in POLICIES:
        print("choices: %s" % ", ".join(POLICIES))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
    sys.stdout.flush()
    os._exit(0)                       # deadlocked daemon threads stay blocked
