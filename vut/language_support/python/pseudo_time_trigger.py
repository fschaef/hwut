"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer

PURPOSE: Deterministic asynchronous event dispatcher.

    A utility to orchestrate multiple asynchronous tasks (Triggers) based on 
    digit-encoded timeline strings.

DESCRIPTION:

    The core power of this manager lies in the simplicity of its timeline 
    strings. The position of a trigger is given by the position in the 
    string (from left to right). For triggers to appear at the same time
    the priority is given by a digit from 0 to 9.
    
        Trigger A: "1  12 1"
        Trigger B: " 1  1 2"

    SHORT:

        - Ticks:       Each character position in a timeline string is one 
                       pseudo-time tick.
        - Triggers:    Any digit '0'-'9' triggers an event.

        - Priority:    Lower digits fire before higher digits within the 
                       same tick.

        - Determinism: Stable sorting ensures that even identical priorities 
                       execute in the order triggers were registered.

    This visual approach allows developers to "draw" complex race conditions 
    directly in the code. By simply looking at the string, you can see exactly 
    when events fire and, more importantly, who "wins" a tie-break (via the 
    digit's priority). This eliminates the need for complex math, delta-t 
    calculations, or unreliable sleep-based synchronization in unit tests.

    The TriggerDispatcher provides a robust framework for testing race conditions 
    and asynchronous flow in a 100% deterministic manner. It pre-calculates an 
    execution array from these strings, ensuring that even if the system is 
    under heavy load, the sequence of events remains stable and reproducible.

NOTE: Use '.stop()' to abort the trigger process.

USAGE EXAMPLE:
    class MyTrigger(Trigger):
        async def fire(self, pseudo_time):
            print(f"[{pseudo_time}] {self.name} fired with prio {priority}")

    async def run():
        # Visualizing the race: 
        # Tick 0: SUB(1) leads NOM(2). 
        # Tick 2: NOM(0) leads SUB(1).
        manager = TriggerDispatcher([
            MyTrigger("1 1 3 1   1")
            MyTrigger("2  121  1  ")
            MyTrigger("2   1 2 2  ")
        ])
        
        await manager.run()
"""

import asyncio
from   typing import Iterable

class Trigger:
    """
    Abstract base class for a dispatchable asynchronous event.

    A Trigger is defined by a 'timeline' string where digits 0-9 represent 
    activation points and their respective priorities. Derived classes 
    must implement the 'fire' method to define the behavior.
    """
    def __init__(self, timeline: str, name = ""):
        self.timeline = timeline
        self.name     = str(id(self))

    async def fire(self, pseudo_time: int):
        """Executions action related to trigger.
        """
        raise NotImplementedError


class TriggerDispatcher:
    """Dispatcher executes Triggers according to a pre-calculated timeline.

    The manager translates string-based timelines into a static _trigger_array. 
    Execution is performed by stepping through the array, ensuring absolute 
    determinism regardless of system performance or I/O jitter.
    """
    def __init__(self, triggers: Iterable[Trigger]):
        self._running_f     = True
        self._trigger_array = self._build(triggers)

    def _build(self, triggers: Iterable[Trigger]):
        """Translates string timelines into prioritized, sorted tick sequences.
        """
        triggers = list(triggers)
        end_tick = max(len(t.timeline) for t in triggers) if triggers else 0
        result   = [[] for _ in range(end_tick)]
        for trigger in triggers:
            for t, char in enumerate(trigger.timeline):
                if char.isdigit():
                    priority = int(char)
                    result[t].append((priority, trigger))
        
        for tick_sequence in result: # sort for each pseudo time tick by priority
            tick_sequence.sort(key=lambda x: x[0])

        return result

    def stop(self):
        self._running_f = False

    async def run(self):
        """Sequentially executes all scheduled triggers in the timeline.

        Iterates through the _trigger_array tick by tick. After each fire(), 
        it yields control (sleep 0) to allow other asynchronous tasks 
        (e.g., consumers of data produced by the trigger) to progress.
        """
        for pseudo_time, tick_sequence in enumerate(self._trigger_array):
            if not self._running_f: break
            for priority, trigger in tick_sequence:
                if not self._running_f: break
                await trigger.fire(pseudo_time)
                await asyncio.sleep(0)

    def __repr__(self):
        result = ["TriggerDispatcher"]
        for pseudo_time, trigger_list in enumerate(self._trigger_array):
            for priority, t in trigger_list:
                result.append(f"[pseudo_time] ({priority}){t.name}")
        return "\n".join(result)

