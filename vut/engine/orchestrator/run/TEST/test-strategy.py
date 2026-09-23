#! /usr/bin/env python3
#
# @hwut {
#     title      = "Strategy: when a directory's unit starts"
#     choices    = ["bundled", "contract", "linear", "parallel", "successor",
#                   "together"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE STRATEGY (O-15) -- when a directory's unit starts, shown
         as the trace of starts and ends over units of different length.

A unit here is ticks of work: it yields to the loop 'n' times, then
answers a CDirDone. No clock, no process: the trace is the strategy's
decisions and nothing else.

CHOICES: linear, successor, parallel, bundled, contract, together;

DESCRIPTION:

linear     one unit after another in walk order, whatever their length.
successor  the next unit starts beside the current one; the one after
           waits for an ending; the longest unit holds its successor's
           slot open.
parallel   every unit at once; they end in the order their lengths
           dictate.
contract   the template refuses a strategy without 'may_start'; results
           come back in walk order whatever the ending order; an empty
           unit list ends at once.
______________________________________________________________________________
"""
import asyncio
import sys
from config import HwutRunner                                # noqa: F401

from vut.engine.orchestrator.run.orchestrate import CDirDone
from vut.engine.orchestrator.run.strategy    import (
         CBundled, CLinear, CParallel, CStrategy, CSuccessor,
         applications_of, sort_key_of, strategy_of, words_of,
         E_SchedulerTestRun_Strategy      as E_Strategy,
         E_SchedulerTestRun_SelectionOrder as E_Order)


def units_of(trace, tick_list):
    """RETURN: list[callable], one coroutine factory per tick count;
    each notes its start and end in 'trace'."""
    def factory(index, tick_n):
        async def run():
            trace.append("start %s" % index)
            for _ in range(tick_n):
                await asyncio.sleep(0)
            trace.append("end   %s" % index)
            return CDirDone(True, index)
        return run
    return [factory(chr(ord("A") + i), n) for i, n in enumerate(tick_list)]


def drive(strategy, tick_list):
    """RETURN: None. Runs the units under 'strategy'; prints the trace
    and the results in walk order."""
    trace = []
    done_list = asyncio.run(strategy.run(units_of(trace, tick_list)))
    print("--- %s over ticks %s ---" % (strategy.name, tick_list))
    for line in trace:
        print("    %s" % line)
    print("    results in walk order: %s"
          % ", ".join(str(done.fail_n) for done in done_list))


#  A's length exceeds the loop's wake-up latency, so the window shows.
TICK_LIST = [6, 1, 3, 1]


def test_linear():    drive(CLinear(),    TICK_LIST)
def test_successor(): drive(CSuccessor(), TICK_LIST)
def test_parallel():  drive(CParallel(),  TICK_LIST)


class CModelUnit:
    """A directory's unit, scripted: PHASES of (ready_n, hold_n, ticks)
    -- what it would answer to 'ready_n', how many slots it holds, and
    for how long. 'None' before it starts, as CDirectoryWork answers
    before its Scheduler stands (intend 20)."""

    def __init__(self, name, phase_list, budget, trace):
        self.name = name; self.phase_list = phase_list
        self.budget = budget; self.trace = trace; self.phase = None

    def ready_n(self):
        """RETURN: int, the running phase's ready count; None before."""
        return None if self.phase is None else self.phase[0]

    async def run(self):
        """RETURN: CDirDone, after every phase held its slots."""
        self.trace.append("start %s" % self.name)
        for phase in self.phase_list:
            self.phase = phase
            for _ in range(phase[1]): await self.budget.take()
            for _ in range(phase[2]): await asyncio.sleep(0)
            for _ in range(phase[1]): self.budget.give()
        self.trace.append("end   %s" % self.name)
        return CDirDone(True, 0)


def test_bundled():
    """RETURN: None. BUNDLED opens the next directory only where the
    open ones cannot fill the budget: with 4 slots, A holding 3 and
    able to start 3 more keeps B shut; A's tail (one node, nothing
    else ready) opens B. C opens at the NEXT SLOT GIVEN BACK: a take
    wakes nothing, so a unit revealing a small ready count is read
    when a slot returns -- an underfill of one node's duration at
    most, never an over-open."""
    from vut.engine.orchestrator.scheduler.budget import CBudget
    async def scenario():
        budget = CBudget(4); trace = []
        unit_list = [CModelUnit("A", [(3, 3, 4), (0, 1, 3)], budget, trace),
                     CModelUnit("B", [(1, 1, 2)],            budget, trace),
                     CModelUnit("C", [(2, 2, 2)],            budget, trace)]
        strategy = CBundled()
        strategy.bind(budget, unit_list)
        await strategy.run([unit.run for unit in unit_list])
        return trace, budget.peak
    trace, peak = asyncio.run(scenario())
    print("--- bundled: budget 4, A holds 3 then 1, B 1, C 2 ---")
    for line in trace: print("    %s" % line)
    print("    peak slots held: %d" % peak)
    print("    wakes on budget: %s" % CBundled.wakes_on_budget_f)


class CNameOnly:
    """A plan node that answers its name and nothing else."""
    def __init__(self, name): self._name = name
    def name(self): return self._name


def test_together():
    """RETURN: None. AN APPLICATION'S CHOICES GO TOGETHER (O-32): the
    slowest application first, weighed as the sum of its choices,
    then its own slowest choice. Shown against the node-only key, which
    scatters 'a.py' round 'b.py' and defeats the display's ':'
    elision."""
    plan = [CNameOnly(n) for n in ("a.py one", "a.py two", "a.py three",
                                   "b.py one", "b.py two",
                                   "c.py only", "d.py fresh")]
    duration_db = {"a.py one": 50, "a.py two": 900, "a.py three": 40,
                   "b.py one": 800, "b.py two": 700,
                   "c.py only": 1500}                # d.py: never measured
    app_db = applications_of(plan, duration_db)
    for label, app_of in (("node key alone", None),
                          ("application first", lambda p: app_db[p[1]])):
        key_of = sort_key_of(E_Order.LONGEST_FIRST, duration_db.get, app_of)
        order  = sorted(enumerate(n.name() for n in plan), key=key_of)
        print("--- longest-first, %s ---" % label)
        for _, name in order:
            print("    %-10s %s" % (name, duration_db.get(name, "-")))
    print("--- application weights ---")
    for name in sorted(set(app_db), key=lambda n: app_db[n][1]):
        app = name.split(" ")[0]
        if name == [n for n in app_db if n.startswith(app + " ")][0]:
            print("    %-5s weight %s, first at plan index %d"
                  % (app, app_db[name][0], app_db[name][1]))


def test_contract():
    """RETURN: None. The template's own laws."""
    try:
        asyncio.run(CStrategy().run(units_of([], [1])))
    except NotImplementedError:
        print("a bare CStrategy: NotImplementedError -- 'may_start' is owed")
    print("an empty unit list: %s" % asyncio.run(CParallel().run([])))
    for member in E_Strategy:
        print("strategy_of(%s).name = %r"
              % (member.name, strategy_of(member).name))
    try:
        strategy_of(E_Order.LONGEST_FIRST)
    except KeyError:
        print("strategy_of(a selection order): KeyError -- "
              "the two enums are not interchangeable")

    #  ONE OPTION, TWO ENUMS (O-27). The words may stand in either
    #  order, long or short; an unnamed question keeps its default; two
    #  words of one question are refused rather than silently settled.
    print()
    for spec in ("p,lf", "longest-first,parallel", "l", "sf", "po,s",
                 "p , lf", "linear,parallel", "lf,shortest-first",
                 "bogus", "p,,l", ""):
        strategy, order, refusal = words_of(spec)
        if refusal is not None: print("%-24r REFUSED: %s" % (spec, refusal))
        else:                   print("%-24r %s + %s"
                                      % (spec, strategy.name, order.name))


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "Strategy: when a directory's unit starts;", {
        "linear":    test_linear,
        "successor": test_successor,
        "parallel":  test_parallel,
        "bundled":   test_bundled,
        "together":  test_together,
        "contract":  test_contract,
    }).run()
