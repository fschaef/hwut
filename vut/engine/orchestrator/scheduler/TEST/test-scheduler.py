#! /usr/bin/env python3
#
# hwut {
#     title      = "Scheduler: the plan executed, trace and report"
#     choices    = ["budget", "build", "exclusion", "frame", "misdep",
#                   "ordering", "parallel", "session", "workers"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE SCHEDULER -- the execution of a plan, shown as the trace of
         what it handed to the dispatcher.

The dispatcher here is a TICK DISPATCHER: a piece of work of 'n' ticks
yields to the loop 'n' times. No clock, no process, no wall time -- the
trace is the scheduler's decisions and nothing else.

CHOICES: parallel, ordering, exclusion, build, session, frame, misdep,
         workers, budget;

DESCRIPTION:

parallel   three tests of different length, nothing standing between
           them: all three start at once, and they end in the order
           their lengths dictate -- the scheduler waits for the FIRST
           ending, not for a wave.

ordering   'b.py' waits for 'a.py' to run to completion; 'a.py' ending
           BAD releases it all the same.

exclusion  a collision group: its members never overlap, while a test
           outside it runs beside them.

build      a build serving two choices: broken, the choices FAIL
           without being dispatched; standing, they run.

session    one interactive session serving two choices: opened once,
           closed once every choice has ended; and a session that does
           not launch, whose choices FAIL undispatched and which is
           never closed.

frame      'on_entry' failing stops the run before any dispatch;
           'on_exit' runs in either case.

misdep     a [MISDEP] node is never dispatched and stands as a
           FAILURE; its [MISDEP] dependant likewise.

workers    the same plan under one worker and under no bound: the same
           work, a different amount of it standing at once.
budget     TWO schedulers over ONE CBudget: with one slot, nothing of
           either ever stands beside anything of the other -- frame
           scripts included (O-12); with two slots, they interleave
           and two stand at once; the budget's own peak says so.
______________________________________________________________________________
"""
import asyncio
import sys
from config import HwutRunner                                # noqa: F401

from vut.engine.orchestrator.plan.form      import (CExclusionSet, CPlanLink,
                                                    CPlanNode, CTestPlan,
                                                    E_LinkKind)
from vut.engine.orchestrator.scheduler.budget    import CBudget
from vut.engine.orchestrator.scheduler.scheduler import I_Dispatcher, Scheduler


class TickDispatcher(I_Dispatcher):
    """A dispatcher without a world: a piece of work of 'n' ticks
    yields to the event loop 'n' times, then answers what it was told
    to answer. Every act is written to the trace as it happens."""

    def __init__(self, tick_db=None, verdict_db=None, standing_max_n=0):
        """
        RETURN: TickDispatcher.

        'tick_db'     node name or script role -> ticks of work; one
                      tick where a name is absent.
        'verdict_db'  node name or script role -> the answer; True
                      where a name is absent.
        """
        self.tick_db        = tick_db or {}
        self.verdict_db     = verdict_db or {}
        self.trace_list     = []
        self.standing_n     = 0
        self.standing_max_n = standing_max_n

    def _note(self, text):
        """RETURN: None. One line of the trace."""
        self.trace_list.append(text)

    async def _work(self, kind, key):
        """
        RETURN: bool, what the dispatcher was told to answer for that
                key, after its ticks have passed.
        """
        self.standing_n     += 1
        self.standing_max_n  = max(self.standing_max_n, self.standing_n)
        self._note("%-6s %-22s start   (standing: %d)"
                   % (kind, key, self.standing_n))
        for _ in range(self.tick_db.get(key, 1)):
            await asyncio.sleep(0)
        answer = self.verdict_db.get(key, True)
        self.standing_n -= 1
        self._note("%-6s %-22s end     %s"
                   % (kind, key, "good" if answer else "BAD"))
        return answer

    async def run_script(self, role, command):
        """RETURN: bool, what the frame script answers."""
        return await self._work("script", role)

    async def run_build(self, node):
        """RETURN: bool, what the build answers."""
        return await self._work("build", node.name())

    async def open_session(self, node):
        """RETURN: bool, whether the session launched."""
        return await self._work("open", node.name())

    async def close_session(self, node):
        """RETURN: None. Notes the closing."""
        self._note("close  %s" % node.name())

    async def run_test(self, node):
        """RETURN: bool, the verdict of the test."""
        return await self._work("test", node.name())


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def drive(plan, dispatcher, **kwargs):
    """
    RETURN: None. Runs the plan, prints the trace and then the report.
    """
    scheduler = Scheduler(dispatcher, **kwargs)
    report    = asyncio.run(scheduler.run(plan))
    print("TRACE")
    for line in dispatcher.trace_list:
        print("    %s" % line)
    print("REPORT")
    print("    entry=%-5s exit=%-5s good=%s"
          % (report.entry_f, report.exit_f, report.good_f()))
    print("    dispatched: %s" % (", ".join(report.dispatched) or "-"))
    for node in plan:
        print("    %-22s %s"
              % (node.name(), report.state_db[node.name()].name))
    print("    most standing at once: %d" % dispatcher.standing_max_n)


def test_parallel():
    """RETURN: None. Three tests, nothing between them."""
    plan = CTestPlan([CPlanNode.test("slow.py", None),
                      CPlanNode.test("quick.py", None),
                      CPlanNode.test("middle.py", None)])
    banner("three lengths, one admission")
    drive(plan, TickDispatcher({"slow.py": 6, "middle.py": 3,
                                "quick.py": 1}))


def test_ordering():
    """RETURN: None. A dependency, and a dependency that breaks."""
    def plan_of():
        return CTestPlan([CPlanNode.test("a.py", None),
                          CPlanNode.test("b.py", None),
                          CPlanNode.test("free.py", None)],
                         [CPlanLink(E_LinkKind.ORDERING, "a.py", "b.py")])

    banner("'b.py' waits for 'a.py'")
    drive(plan_of(), TickDispatcher({"a.py": 4, "free.py": 2}))

    banner("'a.py' ends BAD -- 'b.py' runs all the same")
    drive(plan_of(), TickDispatcher({"a.py": 4, "free.py": 2},
                                    {"a.py": False}))


def test_exclusion():
    """RETURN: None. A collision group never overlaps."""
    plan = CTestPlan([CPlanNode.test("net.py", None),
                      CPlanNode.test("port.py", "two"),
                      CPlanNode.test("free.py", None)],
                     (),
                     [CExclusionSet(("net.py", "port.py two"))])
    banner("'net.py' and 'port.py two' collide; 'free.py' does not")
    drive(plan, TickDispatcher({"net.py": 4, "port.py two": 2,
                                "free.py": 6}))


def test_build():
    """RETURN: None. A build serving two choices, both ways."""
    def plan_of():
        return CTestPlan([CPlanNode.build("make a.py"),
                          CPlanNode.test("a.py", "one"),
                          CPlanNode.test("a.py", "two"),
                          CPlanNode.test("free.py", None)],
                         [CPlanLink(E_LinkKind.SUPPORTS, "build[make a.py]",
                                    "a.py one"),
                          CPlanLink(E_LinkKind.SUPPORTS, "build[make a.py]",
                                    "a.py two")])

    banner("the build stands")
    drive(plan_of(), TickDispatcher({"build[make a.py]": 3, "free.py": 5}))

    banner("the build breaks: the choices FAIL undispatched")
    drive(plan_of(),
          TickDispatcher({"build[make a.py]": 3, "free.py": 5},
                         {"build[make a.py]": False}))


def test_session():
    """RETURN: None. One session serving two choices, both ways."""
    def plan_of():
        return CTestPlan([CPlanNode.session("i.py"),
                          CPlanNode.test("i.py", "x"),
                          CPlanNode.test("i.py", "y")],
                         [CPlanLink(E_LinkKind.SUPPORTS, "session[i.py]",
                                    "i.py x"),
                          CPlanLink(E_LinkKind.SUPPORTS, "session[i.py]",
                                    "i.py y")])

    banner("the session launches: opened once, closed once")
    drive(plan_of(), TickDispatcher({"session[i.py]": 2, "i.py x": 4,
                                     "i.py y": 1}))

    banner("the session does not launch: never closed")
    drive(plan_of(), TickDispatcher({"session[i.py]": 2},
                                    {"session[i.py]": False}))


def test_frame():
    """RETURN: None. The frame around the plan."""
    plan = CTestPlan([CPlanNode.test("a.py", None)])

    banner("'on_entry' stands")
    drive(plan, TickDispatcher(),
          on_entry="prepare.sh", on_exit="cleanup.sh")

    banner("'on_entry' fails: nothing is dispatched, 'on_exit' runs")
    drive(plan, TickDispatcher(verdict_db={"on_entry": False}),
          on_entry="prepare.sh", on_exit="cleanup.sh")


def test_misdep():
    """RETURN: None. [MISDEP] nodes are never dispatched."""
    plan = CTestPlan([CPlanNode.test("c.py", None, misdep_f=True),
                      CPlanNode.test("d.py", None, misdep_f=True),
                      CPlanNode.test("free.py", None)],
                     [CPlanLink(E_LinkKind.ORDERING, "c.py", "d.py")])
    banner("two unsatisfiable cases beside one that runs")
    drive(plan, TickDispatcher({"free.py": 2}))


def test_workers():
    """RETURN: None. The same plan under one worker and under none."""
    def plan_of():
        return CTestPlan([CPlanNode.test("a.py", None),
                          CPlanNode.test("b.py", None),
                          CPlanNode.test("c.py", None)])

    banner("one worker")
    drive(plan_of(), TickDispatcher({"a.py": 3, "b.py": 2, "c.py": 1}),
          worker_max_n=1)

    banner("no bound")
    drive(plan_of(), TickDispatcher({"a.py": 3, "b.py": 2, "c.py": 1}))

    banner("a bound below one: refused")
    try:
        Scheduler(TickDispatcher(), worker_max_n=0)
    except AssertionError as error:
        print("REFUSED: %s" % error)


def test_budget():
    """RETURN: None. Two plans run at once over one shared budget."""
    def plan_of(prefix):
        return CTestPlan([CPlanNode.test(prefix + "1.py", None),
                          CPlanNode.test(prefix + "2.py", None)])

    def drive_two(limit):
        budget     = CBudget(limit)
        dispatcher = TickDispatcher({"a1.py": 3, "a2.py": 1,
                                     "b1.py": 2, "b2.py": 2,
                                     "on_entry": 1, "on_exit": 1})
        async def both():
            await asyncio.gather(
                Scheduler(dispatcher, on_entry="true", on_exit="true",
                          worker_max_n=budget).run(plan_of("a")),
                Scheduler(dispatcher, on_entry="true", on_exit="true",
                          worker_max_n=budget).run(plan_of("b")))
        asyncio.run(both())
        print("TRACE")
        for line in dispatcher.trace_list:
            print("    %s" % line)
        print("    most standing at once: %d   budget peak: %d"
              % (dispatcher.standing_max_n, budget.peak))

    banner("one slot shared by two schedulers")
    drive_two(1)
    banner("two slots shared by two schedulers")
    drive_two(2)
    banner("a budget below one: refused")
    try:
        CBudget(0)
    except AssertionError as error:
        print("REFUSED: %s" % error)


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "Scheduler: the plan executed, trace and report;", {
        "parallel":  test_parallel,
        "ordering":  test_ordering,
        "exclusion": test_exclusion,
        "build":     test_build,
        "session":   test_session,
        "frame":     test_frame,
        "misdep":    test_misdep,
        "workers":   test_workers,
        "budget":    test_budget,
    }).run()
