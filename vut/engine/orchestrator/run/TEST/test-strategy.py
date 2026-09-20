#! /usr/bin/env python3
#
# @hwut {
#     title      = "Strategy: when a directory's unit starts"
#     choices    = ["contract", "linear", "parallel", "successor"]
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

CHOICES: linear, successor, parallel, contract;

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
         CLinear, CParallel, CStrategy, CSuccessor, strategy_of, words_of,
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
        "contract":  test_contract,
    }).run()
