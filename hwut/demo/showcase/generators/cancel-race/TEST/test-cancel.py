#! /usr/bin/env python3
# @hwut {
#     title       = "Reply racing a cancel: exactly one callback, one released slot -- a HwutRunner test application"
#     features    = ["one-outcome"]
#     interactive = true
#     choices {
#         atomic         { features = ["one-outcome", "one-callback"]
#                          tolerance { constraints = ["breaches == 0"] } }
#         check-then-set { features = ["one-outcome", "two-callbacks-named"]
#                          tolerance { constraints = ["breaches > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the callbacks and slot releases of ../request.py in every order of
         the reply's and the cancel's steps
REQUIREMENT  When the reply of an RPC request races its cancellation, the
             user's callback is called exactly once (done OR cancelled) and
             the connection slot is released exactly once.

The unit is '../request.py': complete and cancel as generators of two
atomic steps. '*_check_then_set' looks at the state, then sets it and
notifies; '*_atomic' does compare-and-set in one step, then notifies.

THE GENERATOR INSTRUCTIONS -- EVERY order of the steps, enumerated, the
same for both units (R the reply, X the cancel):

    r, x  = steps of the reply alone, of the cancel alone   (measured: 2, 2)
    words = [w for w in space_iterator.do([["R", "X"]] * (r + x))
             if w.count("R") == r]                       16 -> 6 words
    word 'RXXR' -> timelines R = "1  1"   X = " 11 "     (deterministic_timeline)

Six orders exist for two 2-step tasks, and each is a row: no order is left
to a reviewer's imagination. (Five hand-drawn timelines, an earlier
version of this test, covered four of them; a losing cancel that notifies
"because nobody has been told yet" hid in R X X R.)

THE STEPS ARE A MODEL: reply and cancel are generators stepped by one
thread in the dispatcher's order -- no real threads, no real RPC; the test
proves the step model of the code.

THE FRONT END is hwut's HwutRunner: the choice map names two COROUTINE
functions ('async def'), which await the TriggerDispatcher directly --
HwutRunner sees a coroutine function and runs it with asyncio.run. It
answers '--hwut-info' from the map, suggests the nearest choice for a typo,
accepts a choice by index, prints '<hwut-end>' itself, and serves
'interactive = true': hwut starts the application ONCE and requests both
choices over stdin (see ../../runner-session for what that buys and costs).

atomic          every order: one callback, one release. Law 'breaches == 0'.
check-then-set  the four orders in which both look while pending: both
                notify -- the user hears 'done' AND 'cancelled', the slot
                is released twice (the pool now believes it has one
                connection more than it has). Law 'breaches > 0'.

HOW TO READ THE GOOD   One row per order: the word (who takes each step;
the timeline strings it implies are not printed, they repeat it), each
task's steps as n:step, what the user was told, the slots released, the
verdict. All exact: the dispatcher's order is the only
order; the count of broken rows is a binding, judged by the law.
______________________________________________________________________________
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
import hwut.test_writing_support.python.space_iterator as space_iterator
from hwut.test_writing_support.python.deterministic_timeline import Trigger, TriggerDispatcher
from hwut.test_writing_support.python.hwut_runner import HwutRunner

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import request as unit



class StepTrigger(Trigger):
    def __init__(self, timeline, name, steps):
        super().__init__(timeline, name)
        self.steps, self.done = steps, []

    async def fire(self, tick):
        step = next(self.steps, None)
        if step is not None:
            self.done.append("%d:%s" % (tick, step))


async def judge(complete, cancel):
    r_n = len(list(complete(unit.Request(), 42)))
    x_n = len(list(cancel(unit.Request())))
    space = list(space_iterator.do([["R", "X"]] * (r_n + x_n)))
    words = ["".join(w) for w in space if w.count("R") == r_n]
    print("unit:  request.%s / request.%s" % (complete.__name__, cancel.__name__))
    print("steps: measured alone, R %d, X %d" % (r_n, x_n))
    print("space: space_iterator over {R,X}^%d = %d words, %d pruned (not %d R), %d orders"
          % (r_n + x_n, len(space), len(space) - len(words), r_n, len(words)))
    print("order: who takes each global step, R the reply, X the cancel; 'n:' = global step number")
    print()
    print("  %-6s %-34s %-32s %-22s %s"
          % ("order", "R steps", "X steps", "user told", "released"))
    broken_n = 0
    for word in words:
        r_line, x_line = ["".join("1" if c == who else " " for c in word) for who in "RX"]
        r = unit.Request()
        rt = StepTrigger(r_line, "R", complete(r, 42))
        xt = StepTrigger(x_line, "X", cancel(r))
        await TriggerDispatcher([rt, xt]).run()
        ok = len(r.callback) == 1 and r.released == 1
        broken_n += not ok
        print("  %-6s %-34s %-32s %-22s %d  %s"
              % (word, ", ".join(rt.done), ", ".join(xt.done),
                 " + ".join(r.callback), r.released, "ok" if ok else "!!"))
    print()
    print("orders: %d   told or released other than once ((breaches: %d))   law == 0   %s"
          % (len(words), broken_n, "kept" if broken_n == 0 else "BROKEN"))


async def atomic():
    await judge(unit.complete_atomic, unit.cancel_atomic)


async def check_then_set():
    await judge(unit.complete_check_then_set, unit.cancel_check_then_set)


if __name__ == "__main__":
    HwutRunner(sys.argv, "Reply racing a cancel",
               {"atomic": atomic, "check-then-set": check_then_set}).run()
