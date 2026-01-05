#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Testing 'is_equivalent' early abort under race conditions.

DESCRIPTION:
    This test verifies that the equivalence check aborts as soon as a mismatch
    is found, even if one provider is significantly faster than the other.
    
    The TriggerDispatcher ensures that the "Fast" provider pushes many lines
    into the buffer, while the "Slow" provider lags behind. The test succeeds
    only if the engine stops reading before consuming the entire stream.

CHOICES: subject-slow, nominal-slow, both-jittery;
________________________________________________________________________________
"""
import sys
import asyncio

sys.path.insert(0, "../../../../")

from vut.engine.compare.configuration import Configuration
import vut.engine.compare.main          as main
from vut.language_support.python.pseudo_time_trigger import Trigger, TriggerDispatcher

if "--hwut-info" in sys.argv:
    print("Async Racing: is_equivalent Early Abort;")
    print("CHOICES: subject-slow, nominal-slow, both-jittery;")
    sys.exit()

class LineTrigger(Trigger):
    def __init__(self, name, timeline, lines):
        super().__init__(timeline)
        self.name  = name
        self.lines = list(lines)

        self.prepared_line = None
        self.lines_consumed = 0
        self.pseudo_time_at_preparation = 0

    async def fire(self, pseudo_time):
        if self.lines:
            self.prepared_line = self.lines.pop(0)
        self.pseudo_time_at_preparation = pseudo_time

    async def readline(self):
        while self.prepared_line is None:
            await asyncio.sleep(0)
        result = self.prepared_line
        self.lines_consumed += 1
        print(f"[{self.pseudo_time_at_preparation}] {self.name}: => ({self.lines_consumed}) '{self.prepared_line.rstrip()}'")
        self.prepared_line = None
        return result

async def run_test(sub_timeline_pattern, nom_timeline_pattern):
    config = Configuration()
    
    # Test Data: 100 lines, with a mismatch at line 5 (Index 4)
    lines_n = [f"Line {i}\n" for i in range(100)]
    lines_s = [f"Line {i}\n" for i in range(100)]
    lines_n[4] = "SWEET\n"
    lines_s[4] = "SALTY\n"

    # Generate sufficient timeline string from the pattern
    t_sub_str = (sub_timeline_pattern * 7)[:500] 
    t_nom_str = (nom_timeline_pattern * 7)[:500]

    print("## SUBJECT: timeline: |%s|" % t_sub_str)
    print("## NOMINAL: timeline: |%s|" % t_nom_str)

    subject = LineTrigger("SUBJECT", t_sub_str, lines_s)
    nominal = LineTrigger("NOMINAL", t_nom_str, lines_n)

    dispatcher = TriggerDispatcher([subject, nominal])
    clock_task = asyncio.create_task(dispatcher.run())
    
    try:
        verdict = await main.is_equivalent(config, subject, nominal)
    finally:
        dispatcher.stop() # prevent further sendings
        clock_task.cancel()
        try: await clock_task
        except asyncio.CancelledError: pass

    print(f"Verdict: {verdict}")
    
    # VERIFICATION: Did we stop early?
    # We started with 100 lines. 
    # Mismatch is at line 5. 
    # Even with buffering, we shouldn't have read all 100 lines.
    print(f"Lines Consumed - Subject: {subject.lines_consumed}, Nominal: {nominal.lines_consumed}")

if __name__ == "__main__":
    if "subject-slow" in sys.argv:
        # Subject is sparse (Priority 1), Nominal is dense
        asyncio.run(run_test("1    ", "111111"))
        print("NOTE: The of NOMINAL at time 21 is ok, since we try to consume from both")
        print("      streams at the same time, even if we wait for slower one to deliver")
    elif "nominal-slow" in sys.argv:
        # Subject is dense, Nominal is sparse
        asyncio.run(run_test("1111111", "1    "))
        print("NOTE: The eat of SUBJECT at time 21 is ok, since we try to consume from both")
        print("      streams at the same time, even if we wait for slower one to deliver")
    else: 
        # both-jittery: Irregular staggered patterns
        asyncio.run(run_test("1 1   1 ", "  1 1 1 "))
        print("NOTE: The eat SUBJECT at time 14, since we try to consume from both")
        print("      streams at the same time, even if we wait for slower one to deliver")
