#! /usr/bin/env python3
# @hwut {
#     title    = "Last item in stock, two orders: EVERY interleaving enumerated, one verdict per row"
#     features = ["all-interleavings"]
#     choices {
#         conditional    { features = ["all-interleavings", "never-oversold"]
#                          tolerance { constraints = ["unfinished == 0", "breaches == 0"] } }
#         check-then-act { features = ["all-interleavings", "oversold-rows-named"]
#                          tolerance { constraints = ["unfinished == 0", "breaches > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the confirmed orders and the final stock of ../stock.py in every
         interleaving of two orders for the last item
REQUIREMENT  Of two orders racing for the last item, exactly one is
             confirmed and the stock ends at 0 -- in EVERY interleaving of
             their steps, not only in the ones a stress test happened to
             hit.

The unit is '../stock.py': a reservation as a generator of atomic steps. 'reserve_check_then_act' reads, checks and writes in three
statements; 'reserve_conditional' does check and write in one statement
(UPDATE ... WHERE n >= 1). Both first show the order page (a read that
decides nothing).

THE GENERATOR INSTRUCTIONS -- the tested space is ALL interleavings:

    a, b  = steps of A alone, steps of B alone       (measured, here 3 and 3)
    words = [w for w in space_iterator.do([["A", "B"]] * (a + b))
             if w.count("A") == a]                          64 -> 20 words
    word 'ABBAAB' -> timelines A = "1  11 "  B = " 11  1"   (deterministic_timeline)

A word says which task performs its next step at each tick; the timeline
of a task carries '1' where the word has its letter. The step counts are
MEASURED by running each task alone, not written into the test: a fourth
step added to the unit makes the words longer, and C(8,4) = 70 rows. The
words are all orders of a + b steps, so the matrix is COMPLETE for this
unit: no interleaving exists that is not a row. A task that is not
finished when its word ends (it took more steps in company than alone) is
reported '!! unfinished' and bound as '((unfinished: N))', law
'unfinished == 0'. space_iterator has no filter and hwut has no
interleaving enumerator; the comprehension above is both, and the test
prints how many words it pruned.

THE STEPS ARE A MODEL: each task is a generator stepped by one thread in
the dispatcher's order -- no real threads, no real database; the test
proves the step model, not the scheduler or the SQL engine.

conditional     20 rows, 20 'ok': one order confirmed, stock 0. Law
                'breaches == 0'.
check-then-act  every row in which one check falls between the other
                order's check and write sells the item twice (stock ends
                at 0, two orders confirmed: one item was promised that does
                not exist). The rows are marked '!!' and counted (12 of
                20); the 8 others are the placements in which one order's
                write lands before the other's check. Law 'breaches > 0'.

HOW TO READ THE GOOD   The step legend heads the page. Rows: the word
(the timelines it implies are not printed: they repeat it), each task's
steps, the stock at the end, who was confirmed and how many, the verdict.
Read the '!!' rows: in each,
'c1' stands in both step columns -- the second check came before the
first write. The page step is harmless: it is outside the window. All
exact: no threads, no clock; the two counts are bindings judged by the laws.
______________________________________________________________________________
"""
import asyncio
import os
import shutil
import sys

sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
import hwut.test_writing_support.python.space_iterator as space_iterator
from hwut.test_writing_support.python.deterministic_timeline import Trigger, TriggerDispatcher

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import stock as unit

CHOICE_DB = {"conditional": unit.reserve_conditional, "check-then-act": unit.reserve_check_then_act}


class StepTrigger(Trigger):
    def __init__(self, timeline, name, steps):
        super().__init__(timeline, name)
        self.steps, self.done = steps, []

    async def fire(self, tick):
        self.done.append(next(self.steps, "-"))

    def finished(self):
        """True when the task has no step left. Probing runs the next step,
        so it is called only after the verdict has been taken."""
        return next(self.steps, None) is None


def timelines_of(word):
    return ["".join("1" if c == who else " " for c in word) for who in "AB"]


def solo_steps(reserve, who):
    return len(list(reserve(unit.Stock(1), who)))


def run(reserve, word):
    stock = unit.Stock(1)
    a_line, b_line = timelines_of(word)
    a = StepTrigger(a_line, "A", reserve(stock, "A"))
    b = StepTrigger(b_line, "B", reserve(stock, "B"))
    asyncio.run(TriggerDispatcher([a, b]).run())
    verdict = (stock.n, list(stock.confirmed))
    unfinished = [t.name for t in (a, b) if not t.finished()]
    return a_line, b_line, a.done, b.done, verdict, unfinished


def main(choice):
    reserve = CHOICE_DB[choice]
    a_n, b_n = solo_steps(reserve, "A"), solo_steps(reserve, "B")
    space = list(space_iterator.do([["A", "B"]] * (a_n + b_n)))
    words = ["".join(w) for w in space if w.count("A") == a_n]
    print("unit:  stock.%s, stock 1, orders A and B" % reserve.__name__)
    print("steps: measured alone, A %d, B %d" % (a_n, b_n))
    print("space: space_iterator over {A,B}^%d = %d words, %d pruned (not %d A), %d interleavings"
          % (a_n + b_n, len(space), len(space) - len(words), a_n, len(words)))
    print("word:  who takes each step.  steps: pN peeks, stock N   cN checks, sees N   wN writes,")
    print("       stock N after   x gives up   u+ / u- the conditional update took / found none")
    print("       ok confirms")
    print()
    print("##! verbatim")
    print("   #  word    A steps     B steps     stock  confirmed   n  verdict")
    broken = unfinished_n = 0
    for i, word in enumerate(words):
        a_line, b_line, a_done, b_done, (n, confirmed), unfinished = run(reserve, word)
        ok = n == 0 and len(confirmed) == 1
        broken += not ok
        unfinished_n += len(unfinished)
        note = "ok" if ok else "!! %d confirmed, stock %d" % (len(confirmed), n)
        if unfinished:
            note += "  !! unfinished: %s" % ", ".join(unfinished)
        print("  %2d  %s  %-10s  %-10s  %5d  %-9s  %2d  %s"
              % (i + 1, word, " ".join(a_done), " ".join(b_done), n,
                 ",".join(confirmed) or "-", len(confirmed), note))
    print("####")
    print()
    law = lambda k: "law == 0   %s" % ("kept" if k == 0 else "BROKEN")
    print("interleavings: %d" % len(words))
    print("tasks unfinished ((unfinished: %d))   %s" % (unfinished_n, law(unfinished_n)))
    print("rows breaking the requirement ((breaches: %d))   %s" % (broken, law(broken)))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
