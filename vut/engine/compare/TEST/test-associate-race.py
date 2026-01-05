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

from vut.engine.compare.configuration import Configuration
import vut.engine.compare.main          as main
import vut.engine.pretty                as pretty
from vut.language_support.python.pseudo_time_trigger import Trigger, TriggerDispatcher

if "--hwut-info" in sys.argv:
    print("Async Racing: associate Stream Flow;")
    print("CHOICES: default, large-blocks;")
    sys.exit()

class LineTrigger(Trigger):
    """
    Adapts the push-based Trigger to the pull-based readline() expected by VUT.
    """
    def __init__(self, name, timeline, content_str):
        super().__init__(timeline)
        self.name = name
        self.lines = content_str.splitlines(keepends=True)
        self.queue = asyncio.Queue()

    async def fire(self, pseudo_time):
        """
        ACTION: Pushes the next available line to the queue.
        """
        line = ""
        if self.lines:
            line = self.lines.pop(0)
        
        # DOCUMENTATION: Log the exact moment and content of injection
        print(f"    [t:{pseudo_time}] '{self.name}' -> \"{line.rstrip()}\"")
        await self.queue.put(line)

    async def readline(self):
        """
        ACTION: Pulls data from the queue (called by main.associate).
        """
        return await self.queue.get()

async def run_association_race():
    config = Configuration()
    
    # Test Data: A mix of standard lines and potpourri regions
    subject_content = "s-line 1\ns-line 2\n||||\ns-pot 1\ns-pot 2\n||||\ns-line 3\n"
    nominal_content = "n-line 1\nn-line 2\n||||\nn-pot 1\nn-pot 2\n||||\nn-line 3\n"
    
    # TIMELINES:
    # Subject runs every tick (Fast): "1111111..."
    # Nominal runs every 3 ticks (Slow): "2  2  2..."
    # This forces the engine to buffer Subject while waiting for Nominal.
    t_sub = "1" * 30
    t_nom = ("2  " * 10)

    subject = LineTrigger("subject", t_sub, subject_content)
    nominal = LineTrigger("nominal", t_nom, nominal_content)

    dispatcher = TriggerDispatcher([subject, nominal])

    print("=> Starting Asynchronous Association Race")
    print("   (Subject is fast [every tick], Nominal is slow [every 3rd tick])")
    
    # Start the deterministic clock in the background
    clock_task = asyncio.create_task(dispatcher.run())

    try:
        pair_count = 0
        async for chunk_pair in main.associate(config, subject, nominal):
            pair_count += 1
            st, nt = chunk_pair.types()
            print(f"YIELD {pair_count}: {st.name} <-> {nt.name}")
            print(pretty.do(chunk_pair))
    finally:
        # Cleanup: Ensure the clock stops when the engine finishes or errors
        clock_task.cancel()
        try:
            await clock_task
        except asyncio.CancelledError:
            pass

    print(f"Finished with {pair_count} chunks.")

if __name__ == "__main__":
    # In HWUT, arguments control the flow, but here we map choices to the same function
    # or expand if 'large-blocks' requires different data.
    asyncio.run(run_association_race())
