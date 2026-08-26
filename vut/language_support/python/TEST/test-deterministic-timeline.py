#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Pin the TriggerDispatcher's CONTRACT -- when a trigger fires, in
         what order, and what it is told when the timeline has passed.

CHOICES: schedule, priority, stable, termination, yielding, stop, cancel,
         edges, abstract;

DESCRIPTION:

The dispatcher exists so a test can DRAW an interleaving instead of sleeping
for one. Every claim below is therefore about ORDER and about the pseudo-time
a trigger is handed -- never about a duration, and never about the wall clock.

    schedule     a digit's POSITION is its tick: three staggered triggers
                 fire at 0, 2, 4, and a timeline shorter than its neighbours
                 simply stops contributing.

    priority     within ONE tick the LOWER digit fires first, whatever the
                 registration order -- and the same two triggers swap places
                 at a later tick where their digits swap.

    stable       equal digits in one tick fire in REGISTRATION order; the
                 sort is stable, so 'first, second, third' stays that.

    termination  the end of the timeline is an EVENT. Every trigger is told
                 'on_termination(end_tick)', overriding or not, and 'end_tick'
                 is the timeline's LENGTH -- one past the last tick that could
                 fire, and NOT the tick that happened to fire last. A trigger
                 that never fired is told too.

    yielding     what the dispatcher is FOR: the run yields between firings,
                 so a consumer takes each item BEFORE the next tick prepares
                 one. Drop the yield and the whole timeline would pass before
                 the consumer ran once -- the drawn interleaving would not be
                 the one that happened.

    stop         'stop()' leaves the timeline early -- and the announcement
                 STILL follows: a stopped run is an ended run, and a consumer
                 promised an end-of-stream is owed it.

    cancel       cancelling the task that carries 'run()' announces NOTHING.
                 A cancellation is not an ending, it is an abandonment.

    edges        an empty timeline, a timeline of blanks, and no triggers at
                 all: each announces and none fails.

    abstract     'fire' is abstract and refuses; 'on_termination' is optional
                 and is silent. That asymmetry is the design.

Every trigger here is given a NAME, so what is printed is the name the test
chose and never an address the machine chose.
______________________________________________________________________________
"""
import sys
import asyncio

import config                                                    # noqa: F401

from vut.language_support.python.hwut_runner          import HwutRunner
from vut.language_support.python.deterministic_timeline import (Trigger,
                                                                TriggerDispatcher)


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


class SpeakingTrigger(Trigger):
    """A trigger that says what it is asked to do, and when."""
    def __init__(self, name, timeline, silent_termination_f=False):
        super().__init__(timeline, name)
        self.silent_termination_f = silent_termination_f
        print("SETUP: %-7s |%s|" % (name, timeline))

    async def fire(self, pseudo_time):
        """RETURN: None. Says that this trigger fired, and at which tick."""
        print("  [t:%d] %s fires" % (pseudo_time, self.name))

    def on_termination(self, end_tick):
        """RETURN: None. Says that the timeline has passed, and where."""
        if self.silent_termination_f: return
        print("  [end:%d] %s notified" % (end_tick, self.name))


class MuteTrigger(Trigger):
    """A trigger that fires and does NOT override 'on_termination' -- the
    base's silence is what this one demonstrates."""
    def __init__(self, name, timeline):
        super().__init__(timeline, name)
        print("SETUP: %-7s |%s|  (no on_termination override)"
              % (name, timeline))

    async def fire(self, pseudo_time):
        """RETURN: None. Says that this trigger fired, and at which tick."""
        print("  [t:%d] %s fires" % (pseudo_time, self.name))


def dispatch(trigger_list):
    """RETURN: None. Builds a dispatcher over 'trigger_list' and runs it
    to completion."""
    asyncio.run(TriggerDispatcher(trigger_list).run())


def run_schedule():
    """RETURN: None. A digit's position is its tick."""
    banner("staggered: A at 0, B at 2, C at 4")
    dispatch([SpeakingTrigger("A", "1    "),
              SpeakingTrigger("B", "  1  "),
              SpeakingTrigger("C", "    1")])

    banner("a SHORT timeline stops contributing; the long one goes on")
    dispatch([SpeakingTrigger("SHORT", "11"),
              SpeakingTrigger("LONG",  "111111")])

    banner("the SCHEDULE as built -- '[tick] (priority)name'")
    print(repr(TriggerDispatcher([SpeakingTrigger("A", "12"),
                                  SpeakingTrigger("B", "21")])))


def run_priority():
    """RETURN: None. Lower digit first within one tick, registration
    order notwithstanding."""
    banner("digits swap between ticks: B leads at 0, A leads at 1")
    dispatch([SpeakingTrigger("A", "21"),
              SpeakingTrigger("B", "12")])

    banner("0 is the strongest digit, 9 the weakest")
    dispatch([SpeakingTrigger("WEAK",   "9"),
              SpeakingTrigger("STRONG", "0")])


def run_stable():
    """RETURN: None. Equal digits fire in registration order."""
    banner("three triggers, all digit 1 at tick 0")
    dispatch([SpeakingTrigger("first",  "1"),
              SpeakingTrigger("second", "1"),
              SpeakingTrigger("third",  "1")])

    banner("registered BACKWARDS -- the order follows registration, "
           "not the name")
    dispatch([SpeakingTrigger("third",  "1"),
              SpeakingTrigger("second", "1"),
              SpeakingTrigger("first",  "1")])


def run_termination():
    """RETURN: None. The end of the timeline is an event with a stated tick."""
    banner("end_tick is the LENGTH -- 5 characters, last firing at tick 0")
    dispatch([SpeakingTrigger("EARLY", "1    ")])

    banner("a trigger that NEVER fires is notified all the same")
    dispatch([SpeakingTrigger("FIRES",  "1  "),
              SpeakingTrigger("SILENT", "   ")])

    banner("the LONGEST timeline sets end_tick for everybody")
    dispatch([SpeakingTrigger("SHORT", "1"),
              SpeakingTrigger("LONG",  "1      ")])

    banner("a trigger that does not override is simply silent at the end")
    dispatch([SpeakingTrigger("SPEAKS", "1 "),
              MuteTrigger("MUTE",       "1 ")])


def run_yielding():
    """RETURN: None. The run yields to a consumer between firings.

    This is what the dispatcher is FOR: a provider trigger prepares one
    item per tick and a consumer waiting on it wakes up between ticks.
    Without the yield after each 'fire', the whole timeline would pass
    before the consumer ran once, and the interleaving the timeline
    DRAWS would not be the interleaving that happened.
    """
    banner("producer fires at every tick; consumer waits between them")

    class ProducingTrigger(Trigger):
        def __init__(self, name, timeline):
            super().__init__(timeline, name)
            self.item     = None
            self.finished = False
            print("SETUP: %-7s |%s|" % (name, timeline))

        async def fire(self, pseudo_time):
            """RETURN: None. Prepares one item, stamped with its tick."""
            self.item = "item@%d" % pseudo_time
            print("  [t:%d] %s prepared %s"
                  % (pseudo_time, self.name, self.item))

        def on_termination(self, end_tick):
            """RETURN: None. Announces end-of-stream to the consumer."""
            self.finished = True
            print("  [end:%d] %s announced end-of-stream"
                  % (end_tick, self.name))

    async def consume(producer):
        """RETURN: None. Takes each item as it appears, until the end
        is announced."""
        taken = 0
        while True:
            while producer.item is None:
                if producer.finished:
                    print("  consumer saw end-of-stream after %d item(s)"
                          % taken)
                    return
                await asyncio.sleep(0)
            taken += 1
            print("        consumer took %s" % producer.item)
            producer.item = None

    async def both():
        """RETURN: None. Runs dispatcher and consumer side by side."""
        producer = ProducingTrigger("PROD", "111")
        await asyncio.gather(TriggerDispatcher([producer]).run(),
                             consume(producer))

    asyncio.run(both())
    print()
    print("Each item was taken BEFORE the next tick prepared one: "
          "the run yields.")


def run_stop():
    """RETURN: None. A stopped run is an ended run: it still announces."""
    banner("stop() after the first tick -- ticks 1.. are not walked, "
           "the announcement still comes")

    class StoppingTrigger(SpeakingTrigger):
        def __init__(self, name, timeline):
            super().__init__(name, timeline)
            self.dispatcher = None

        async def fire(self, pseudo_time):
            """RETURN: None. Fires once, then asks the run to leave."""
            await super().fire(pseudo_time)
            print("  ... asks the dispatcher to stop")
            self.dispatcher.stop()

    stopper    = StoppingTrigger("STOPPER", "1111")
    bystander  = SpeakingTrigger("OTHER",   "1111")
    dispatcher = TriggerDispatcher([stopper, bystander])
    stopper.dispatcher = dispatcher
    asyncio.run(dispatcher.run())

    print()
    print("end_tick is still the timeline's length, "
          "not the tick the run stopped at.")


def run_cancel():
    """RETURN: None. A cancellation is an abandonment: it announces nothing."""
    banner("cancel() the task carrying run() -- no announcement follows")

    async def cancelled_run():
        """RETURN: None. Starts a run, lets one tick pass, cancels it."""
        dispatcher = TriggerDispatcher([SpeakingTrigger("A", "1111111111")])
        task       = asyncio.create_task(dispatcher.run())
        await asyncio.sleep(0)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            print("  run() was cancelled")

    asyncio.run(cancelled_run())
    print()
    print("No '[end:..]' line above: the triggers were abandoned, not ended.")


def run_edges():
    """RETURN: None. Degenerate timelines announce and do not fail."""
    banner("an EMPTY timeline -- end_tick 0")
    dispatch([SpeakingTrigger("EMPTY", "")])

    banner("a timeline of BLANKS -- no digit, so nothing fires")
    dispatch([SpeakingTrigger("BLANK", "    ")])

    banner("NO TRIGGERS at all -- nothing to announce, and no failure")
    dispatch([])
    print("  (dispatcher ran; nothing was scheduled)")

    banner("a timeline of blanks beside one that fires")
    dispatch([SpeakingTrigger("BLANK", "   "),
              SpeakingTrigger("FIRES", " 1 ")])


def run_abstract():
    """RETURN: None. 'fire' refuses; 'on_termination' is silent."""
    banner("the BASE 'fire' is abstract -- it refuses")

    class BareTrigger(Trigger):
        pass

    try:
        dispatch([BareTrigger("1", "BARE")])
    except NotImplementedError:
        print("  NotImplementedError -- as owed: a trigger must say "
              "what it does")

    banner("the BASE 'on_termination' is optional -- it is silent")
    bare = BareTrigger("", "BARE")
    bare.on_termination(0)
    print("  returned quietly; nothing raised, nothing printed")

    banner("a NAME given is the name kept")
    print("  name:", Trigger("1", "GIVEN").name)


HwutRunner(
    argv       = sys.argv,
    title      = "TriggerDispatcher: schedule, priority, and the end of time",
    choice_map = {
        "schedule":    run_schedule,
        "priority":    run_priority,
        "stable":      run_stable,
        "termination": run_termination,
        "yielding":    run_yielding,
        "stop":        run_stop,
        "cancel":      run_cancel,
        "edges":       run_edges,
        "abstract":    run_abstract,
    },
).run()
