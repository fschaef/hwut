#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Testing 'associate' with deterministic async race conditions.

DESCRIPTION:
    This test verifies the engine's ability to yield association chunks 
    while stream data arrives at different rates. It uses the TriggerDispatcher
    to force a specific, repeatable interleaving of input lines.

    Output format acts as documentation:
      [t:X] 'name' -> "content"   (Provider injects data)
      YIELD N: TYPE <-> TYPE      (Engine produces result)

CHOICES: default, large-blocks;
________________________________________________________________________________
"""
import sys
import asyncio

sys.path.insert(0, "../../../../")

from   vut.engine.compare.configuration import Configuration
import vut.engine.compare.main          as main
import vut.engine.pretty                as pretty
import vut.engine.compare.TEST.racing   as racing
from   vut.language_support.python.racing_condition_sim import Trigger
from   vut.language_support.python.deterministic_random import DeterministicStream

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

async def test(subject_timeline, nominal_timeline):
    config = Configuration()
    
    # Test Data: A mix of standard lines and potpourri regions
    subject_content = ["heidi", "heinz", "||||", "albert", "berta",  "carlos",   "damian", "||||", "kasper", "friedrich"]
    nominal_content = ["trudi", "hein",  "||||", "karlos", "damian", "adelbert", "berta",  "||||", "crisper", "friedolin"]
    
    subject, nominal, \
    dispatcher_handle = racing.prepare_dispatcher(subject_timeline, subject_content,
                                                  nominal_timeline, nominal_content)

    try:
        pair_count = 0
        async for chunk_pair in main.associate(config, subject, nominal):
            pair_count += 1
            st, nt = chunk_pair.types()
            print(f"YIELD {pair_count}: {st.name} <-> {nt.name}")
            print(pretty.do(chunk_pair))
    finally:
        await racing.cleanup(dispatcher_handle)

    print(f"Finished with {pair_count} chunks.")

if __name__ == "__main__":
    if "--hwut-info" in sys.argv:
        print("Async Racing: associate Stream Flow;")
        print("CHOICES: nominal-slow, subject-slow, jittery;")
    elif "nominal-slow" in sys.argv:
        t_sub = "11" * 10
        t_nom = "2 " * 10
        asyncio.run(test(t_sub, t_nom))
    elif "subject-slow" in sys.argv:
        t_sub = "2 " * 10
        t_nom = "11" * 10
        asyncio.run(test(t_sub, t_nom))
    elif "jittery" in sys.argv:
        rg = DeterministicStream(seed=17)
        t_sub = "".join(rg.select("123  ") for _ in range(17))
        t_nom = "".join(rg.select("123  ") for _ in range(17))
        asyncio.run(test(t_sub, t_nom))
    else:
        assert False, "missing choice argument 1"


