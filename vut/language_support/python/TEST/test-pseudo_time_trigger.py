#! /usr/bin/env python3
"""
PURPOSE: Testing the TriggerDispatcher for deterministic async flow.

DESCRIPTION:
    This test verifies that:
    1. Triggers fire at the correct pseudo-time tick.
    2. Within a tick, lower digits (higher priority) fire first.
    3. If digits are identical, registration order determines the sequence.

CHOICES: simple-sequence, priority-tie-break, stable-sort;
"""

import sys
import asyncio

sys.path.insert(0, "../../../../")

from   vut.language_support.python.racing_condition_sim import TriggerDispatcher, Trigger #noqa E402

# Assuming the implementation above is in a file named trigger_dispatcher.py
# or included in the same directory.
# from trigger_dispatcher import Trigger, TriggerDispatcher

class PrintTrigger(Trigger):
    """A concrete implementation of Trigger for HWUT verification."""
    def __init__(self, name: str, timeline: str):
        super().__init__(timeline)
        self.name = name
        print("SETUP: %7s |%s|" % (name, timeline))

    async def fire(self, pseudo_time: int):
        """ACTION: Print the firing event to stdout for HWUT comparison."""
        print(f"[t:{pseudo_time}] Trigger '{self.name}' fired.")

async def test_simple_sequence():
    """Tests basic staggered triggers."""
    print("=> Testing Simple Sequence")
    t1 = PrintTrigger("A", "1    ") # Fires at 0
    t2 = PrintTrigger("B", "  1  ") # Fires at 2
    t3 = PrintTrigger("C", "    1") # Fires at 4
    
    dispatcher = TriggerDispatcher([t1, t2, t3])
    await dispatcher.run()
    print()

async def test_priority_tie_break():
    """Tests that lower digits fire before higher digits at the same tick."""
    print("=> Testing Priority Tie-Break (Same Tick)")
    print("A, B -- Both fire at tick 0, but B(1) should beat A(2) ... ")
    t1 = PrintTrigger("A", "21   3") 
    t2 = PrintTrigger("B", "12   2")
    
    print("C, D -- Both fire at tick 2, but C(0) should beat D(9)")
    t3 = PrintTrigger("C", "  0  1")
    t4 = PrintTrigger("D", "  9  0")
    
    dispatcher = TriggerDispatcher([t1, t2, t3, t4])
    await dispatcher.run()
    print()

async def test_stable_sort():
    """Tests that identical digits fire in registration order."""
    print("=> Testing Stable Sort (Same Priority, Same Tick)")
    print("All fire at tick 0 with priority 1. Order should be First -> Second -> Third.")
    t1 = PrintTrigger("First",  "1")
    t2 = PrintTrigger("Second", "1")
    t3 = PrintTrigger("Third",  "1")
    
    dispatcher = TriggerDispatcher([t1, t2, t3])
    await dispatcher.run()
    print()

# Main HWUT Entry Point
if __name__ == "__main__":
    if "--hwut-info" in sys.argv:
        print("TriggerDispatcher Logic;")
        print("CHOICES: simple, priority-tie, stable-sort;")
        sys.exit()

    choice = sys.argv[1] if len(sys.argv) > 1 else ""

    if "simple" in choice:
        asyncio.run(test_simple_sequence())
    elif "priority-tie" in choice:
        asyncio.run(test_priority_tie_break())
    elif "stable-sort" in choice:
        asyncio.run(test_stable_sort())
    else:
        # Default run if no specific choice is matched
        asyncio.run(test_simple_sequence())
        asyncio.run(test_priority_tie_break())
        asyncio.run(test_stable_sort())
