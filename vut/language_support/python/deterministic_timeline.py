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

    THE END OF THE TIMELINE IS AN EVENT. When the last tick has passed, every
    trigger is told so through 'on_termination(end_tick)' -- the moment a
    provider announces end-of-stream, so a consumer waiting on it stops
    waiting instead of spinning forever. 'on_termination' is a PLAIN method,
    not a coroutine: the run is over, there is nobody left to yield to.

    'end_tick' is the length of the longest timeline -- ONE PAST the last
    tick that could fire, the way 'len' is one past the last index. It does
    not depend on which trigger fired last, or on whether any fired at all.

NOTE: Use '.stop()' to abort the trigger process. A stopped run still
      announces termination: the providers were promised an end-of-stream,
      and a stopped run is still an ended run. Cancelling the task that
      carries 'run()' does NOT announce it -- a cancellation is not an
      ending, it is an abandonment.

USAGE EXAMPLE:
    class MyTrigger(Trigger):
        async def fire(self, pseudo_time):
            print(f"[{pseudo_time}] {self.name} fired")

    async def run():
        # Visualizing the race:
        # Tick 0: SUB(1) leads NOM(2).
        # Tick 2: NOM(0) leads SUB(1).
        manager = TriggerDispatcher([
            MyTrigger("1 1 3 1   1", "SUB"),
            MyTrigger("2  121  1  ", "NOM"),
            MyTrigger("2   1 2 2  ", "AUX"),
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
    def __init__(self, timeline: str, name: str = ""):
        self.timeline = timeline
        self.name     = name if name else ("trigger-%s" % id(self))

    async def fire(self, pseudo_time: int):
        """
        RETURN: None. The action this trigger performs at 'pseudo_time',
                one of the ticks its own timeline marked with a digit.

        Raises NotImplementedError. A trigger that does nothing when its
        tick comes has no reason to stand in the timeline, so this one IS
        abstract: the base refuses rather than guesses.
        """
        raise NotImplementedError

    def on_termination(self, end_tick: int):
        """
        RETURN: None. The action this trigger performs once the timeline
                has passed -- announcing end-of-stream, typically, so that
                a consumer waiting on this trigger stops waiting.

        Does nothing by default: a trigger with nothing to wind down is
        ordinary, and a base that raised would force every such trigger to
        write an empty method. Overriding is optional, unlike 'fire'.

        NOT a coroutine: the run is over and there is nobody to yield to.
        """
        pass


class TriggerDispatcher:
    """Dispatcher executes Triggers according to a pre-calculated timeline.

    The manager translates string-based timelines into a static _trigger_time_db.
    Execution is performed by stepping through the array, ensuring absolute
    determinism regardless of system performance or I/O jitter.
    """
    def __init__(self, triggers: Iterable[Trigger]):
        self._running_f       = True
        self._triggers        = list(triggers)
        self._trigger_time_db = self._build(self._triggers)
        self._end_tick        = len(self._trigger_time_db)

    def _build(self, triggers: list[Trigger]):
        """
        RETURN: list of lists, one entry per tick; entry 't' holds the
                '(priority, trigger)' pairs whose timeline carries a digit
                at position 't', sorted by priority -- and, priorities
                being equal, in registration order, the sort being stable.

        The list is as long as the LONGEST timeline; a shorter timeline
        contributes nothing to the ticks beyond its own end. No trigger,
        or none with a timeline, yields the empty list.
        """
        end_tick = max((len(t.timeline) for t in triggers), default=0)
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
        """
        RETURN: None. Asks the run to leave the timeline at the next tick.

        The run still announces termination on its way out (see 'run').
        """
        self._running_f = False

    async def run(self):
        """
        RETURN: None. Steps the timeline tick by tick, awaiting every
                trigger due at that tick in priority order, and yields
                ('sleep(0)') after each one, so that a consumer of what the
                trigger produced may progress.

        THE ANNOUNCEMENT ALWAYS FOLLOWS: whether the timeline was walked to
        its end or 'stop()' cut it short, every trigger is told
        'on_termination(end_tick)' before this returns. 'end_tick' is the
        LENGTH of the timeline, never a leftover loop counter, so an empty
        timeline announces 0 instead of failing.

        A cancellation of the task carrying this coroutine is NOT an ending
        and announces nothing.
        """
        for pseudo_time, tick_sequence in enumerate(self._trigger_time_db):
            if not self._running_f: break
            for priority, trigger in tick_sequence:
                if not self._running_f: break
                await trigger.fire(pseudo_time)
                await asyncio.sleep(0)

        for trigger in self._triggers:
            trigger.on_termination(self._end_tick)

    def __repr__(self):
        """
        RETURN: str, the built timeline as one line per scheduled firing --
                '[tick] (priority)name', ticks ascending and, within a tick,
                in the order the run will fire them.
        """
        result = ["TriggerDispatcher"]
        for pseudo_time, trigger_list in enumerate(self._trigger_time_db):
            for priority, trigger in trigger_list:
                result.append("[%d] (%d)%s"
                              % (pseudo_time, priority, trigger.name))
        return "\n".join(result)
