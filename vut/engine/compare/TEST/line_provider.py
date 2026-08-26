"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: LINE PROVIDERS ON A DRAWN TIMELINE -- a subject and a nominal that
         deliver their lines at ticks the caller chose.

    'compare/main.py' asks one thing of a stream: a '.readline()' coroutine
    (its own words -- "ONLY REQUIREMENT: line provider member function
    '.readline()'"). 'LineTrigger' is such a provider whose delivery moments
    are drawn, not slept for: a digit at position 't' in its timeline means
    "prepare the next line at tick t".

    BACKPRESSURE: a line already prepared and not yet taken is never
    overwritten -- 'fire' returns without popping. So a fast timeline cannot
    outrun a slow consumer; it can only get ahead of a slower PEER, which is
    the interleaving the test wants to draw.

    END OF STREAM: when the timeline has passed, 'on_termination' forces the
    terminating "" so a consumer waiting in 'readline' stops waiting. Without
    it a reader outliving the timeline would spin forever.

    'prepare_dispatcher' builds both providers and starts the dispatcher as a
    task; 'cleanup' stops and cancels it. Cancelling announces nothing, so a
    consumer that still needs end-of-stream must be done before cleanup.
________________________________________________________________________________
"""
from vut.language_support.python.deterministic_timeline import Trigger
from vut.language_support.python.deterministic_timeline import TriggerDispatcher

from   typeguard import typechecked
import asyncio

class LineTrigger(Trigger):
    def __init__(self, name, timeline, lines):
        super().__init__(timeline)
        self.name  = name
        self.lines = list(lines)

        self.prepared_line              = None
        self.lines_consumed             = 0
        self.pseudo_time_at_preparation = 0

    def on_termination(self, pseudo_time: int):
        # 'self.prepared_line == ""' indicates that all lines have been sent
        if self.prepared_line != "":
            self.prepared_line = "" # ensure that the terminating "" is sent
            self.pseudo_time_at_preparation = pseudo_time

    async def fire(self, pseudo_time: int):
        if self.prepared_line is not None: 
            return
        if self.lines: self.prepared_line = self.lines.pop(0)
        else:          self.prepared_line = ""
        self.pseudo_time_at_preparation = pseudo_time

    async def readline(self):
        while self.prepared_line is None:
            await asyncio.sleep(0)
        result = self.prepared_line
        self.lines_consumed += 1
        print(f"[{self.pseudo_time_at_preparation}] {self.name}: => ({self.lines_consumed}) '{self.prepared_line.rstrip()}'")
        self.prepared_line = None
        return result

@typechecked
def prepare_dispatcher(subject_timeline: str, subject_line_list: list[str], 
                       nominal_timeline: str, nominal_line_list: list[str]):
    print("SUBJECT timeline: |%s|" % subject_timeline)
    print("NOMINAL timeline: |%s|" % nominal_timeline)

    subject = LineTrigger("SUBJECT", subject_timeline, subject_line_list)
    nominal = LineTrigger("NOMINAL", nominal_timeline, nominal_line_list)

    dispatcher = TriggerDispatcher([subject, nominal])
    return subject, nominal, (dispatcher, asyncio.create_task(dispatcher.run()))

async def cleanup(dispatcher_handle):
    dispatcher, dispatcher_task = dispatcher_handle

    dispatcher.stop() # prevent further sendings
    dispatcher_task.cancel()
    try:                           await dispatcher_task
    except asyncio.CancelledError: pass
