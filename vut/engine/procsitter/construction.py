"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       CONSTRUCTION BLOCKS for supervised calls -- the byte edges between
       them, and the pipelines built from those edges.

DESCRIPTION
       A supervised call (see 'procsitter.py') owns one process: its caps,
       its kill ladder, its attribution record. It knows nothing of any
       other call. What connects calls lives here:

           Link              the directed edge: one production port to
                             one control port
           tee()             the consumer sum: many listeners on one
                             production port
           chain()           a pipeline of supervised calls, obeying the
                             three rules
           ProcsitterChain   the launched pipeline as plain data

       This module holds no knowledge of any application. It composes
       supervised calls; what those calls do is the caller's affair.
______________________________________________________________________________
"""
import asyncio
from   contextlib  import suppress
from   dataclasses import dataclass


class Link:
    """RETURN: --. THE DIRECTED EDGE of the byte world: it carries a
                   stream from a PRODUCTION port to a CONTROL port.

    THE TWO AXES. Every component spans the same two orthogonal
    directions:

        PRODUCTION  what flows OUT   (stdout; stderr is a second,
                                      diagnostic production channel)
        CONTROL     what flows IN    (stdin: the component obeys it)

    A Link connects one production to one control: its '.feed' is
    given as a producer's 'stdout_handler' (or 'stderr_handler'); its
    '.reader' is given as a consumer's 'stdin_reader'. '.close()'
    propagates end-of-stream. The law of the axes: production may be
    LISTENED to by many ('tee', below -- consumers add); a control
    port obeys ONE voice (byte streams do not merge
    deterministically).

    Every process on a wired graph runs in its OWN procsitter: own
    caps, own attribution -- supervised at every link.
    """
    def __init__(self):
        self.reader = asyncio.StreamReader()

    async def feed(self, data: bytes):
        """RETURN: None. Upstream stdout handler: pass one chunk on."""
        self.reader.feed_data(data)

    def close(self):
        """RETURN: None. Upstream ended: downstream sees EOF."""
        with suppress(Exception):
            self.reader.feed_eof()


def tee(*consumer_list):
    """
    RETURN: async handler, feeding every consumer in 'consumer_list'
            with each chunk -- THE CONSUMER SUM.

    Fan-out is NOT a building block: a consumer is a plain async
    function, and functions ADD. 'tee(judge_link.feed, observer.feed)'
    is the sum of two consumers -- anyone may LISTEN to a production
    port. (The reverse does not exist: two productions cannot merge
    into one control port deterministically -- ONE VOICE COMMANDS.)
    """
    async def handler(data: bytes):
        for consume in consumer_list:
            await consume(data)
    return handler

# ---------------------------------------------------------------------------
# THE WIRING IDIOMS -- everything above the two building blocks is
# composition; no further class is needed.
#
# CHAIN (a pipeline A | B), with THE THREE RULES every chain obeys:
#   (1) EOF ONWARD: when a stage ends, close its outgoing Link
#       ('finally: link.close()') -- downstream sees end-of-stream.
#   (2) STOP ON EARLY DEATH: a stage that ends while an UPSTREAM stage
#       still runs sets the shared stop_event -- SIGPIPE semantics,
#       supervised; this is also what BOUNDS MEMORY (an in-memory
#       'feed' never blocks; without the rule an upstream would fill
#       a dead chain's buffer without limit).
#   (3) EVERY STAGE ACCOUNTED: gather ALL stage tasks; one
#       ProcsitterResult per stage, nothing disappears.
#
#     stop = asyncio.Event()
#     link = Link()
#     async def stage_a():
#         try:     return await a.run(argv_a, stdout_handler=link.feed,
#                                     stop_event=stop)
#         finally: link.close()                              # rule 1
#     async def stage_b():
#         try:     return await b.run(argv_b, stdin_reader=link.reader,
#                                     stdout_handler=consume,
#                                     stop_event=stop)
#         finally:
#             if not task_a.done(): stop.set()               # rule 2
#     record_a, record_b = await asyncio.gather(stage_a(), stage_b())
#                                                            # rule 3
#
# MAN IN THE MIDDLE (controller C rides subject A, consumer B keeps
# listening undisturbed): production is TEE'D, control is answered --
#
#     to_b, to_c, back = Link(), Link(), Link()   # B and C listen; C answers
#     A.run(argv, stdout_handler=tee(to_b.feed, to_c.feed),
#           stdin_reader=back.reader)             # finally: to_b/to_c.close()
#     C.run(ctrl_argv, stdin_reader=to_c.reader,
#           stdout_handler=back.feed)             # finally: back.close()
#     B consumes to_b.reader (a judge, a pype link, a log)
#
# A dialogue where both ends wait is an accident like any other: the
# wall clocks contain it. A supervised answerer must be UNBUFFERED
# (e.g. 'python3 -u') -- a buffered answer never arrives.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProcsitterChain:
    """RETURN: --. PLAIN DATA handed back by 'chain()': the
                   chain's production end ('.tail', a Link), the shared
                   stop_event, and ONE TASK PER STAGE. No behavior --
                   the chain's rules live in 'chain'; the data
                   is dumb:

        records  = await asyncio.gather(*c.task_tuple)
        running  = any(not t.done() for t in c.task_tuple)
        stop     = c.stop_event.set()
    """
    tail:       "Link"
    stop_event: "asyncio.Event"
    task_tuple: tuple


def chain(stage_list, stop_event=None, stdin_reader=None):
    """
    RETURN: ProcsitterChain, the LAUNCHED chain: every stage runs; the last
            stage's production feeds '.tail'.

    THE POLICY FUNCTION of the chain idiom -- the three rules, encoded
    once (see the idiom block above): (1) EOF onward -- a stage that
    ends closes its outgoing Link; (2) stop on early death -- a stage
    ending while an UPSTREAM stage still runs sets the shared
    stop_event (SIGPIPE semantics, supervised; bounds the in-memory
    buffers); (3) every stage accounted -- one task per stage, gather
    them for the records.

    'stage_list' entries are (procsitter, argv) or (procsitter, argv,
    extra_run_kwargs) -- the extra kwargs go verbatim into that
    stage's 'run()' (e.g. {'stderr_handler': err_link.feed} to wire a
    stage's diagnostic production). ONE exception: a 'stdout_handler'
    in the extra kwargs is not a replacement but a LISTENER -- it is
    TEE'D with the chain edge, so the stage's production reaches both
    the next stage AND the listener (a log tap, a mirror); anyone may
    LISTEN to a production, the pipeline still flows. 'stdin_reader'
    feeds the FIRST stage's control port (recorded input, or a
    dialogue's back edge).

    'stdin_reader' and 'stop_event' are THE CHAIN'S: the upstream stage
    feeds the one, every stage shares the other. Either of them in a
    stage's extra kwargs is a wiring mistake, caught HERE, where it is
    written -- not later, as a duplicate-keyword TypeError inside the
    stage's task, surfacing at the 'gather'.
    """
    OWNED = ("stdin_reader", "stop_event")
    for i, stage in enumerate(stage_list):
        for key in (stage[2] if len(stage) > 2 else ()):
            assert key not in OWNED, \
                   "chain(): stage %i passes '%s' -- that is the chain's. " \
                   "Pass it to chain(), not to a stage." % (i, key)

    stop      = stop_event if stop_event is not None else asyncio.Event()
    tail      = Link()
    task_list = []
    last_i    = len(stage_list) - 1
    upstream  = stdin_reader
    for i, stage in enumerate(stage_list):
        procsitter, argv = stage[0], stage[1]
        extra    = dict(stage[2]) if len(stage) > 2 else {}
        listener = extra.pop("stdout_handler", None)   # a production tap
        out_link = tail if i == last_i else Link()
        # chain edge FIRST: a chunk reaches the next stage before the
        # listener runs, so a failing tap (e.g. an unwritable log) never
        # starves the pipeline of that chunk -- it surfaces afterwards
        # as a loud harness fault, the chain already fed.
        handler  = out_link.feed if listener is None \
                   else tee(out_link.feed, listener)

        async def run_stage(ps=procsitter, av=argv, up=upstream,
                            out=out_link, idx=i, kw=extra, h=handler):
            try:
                return await ps.run(av, stdin_reader=up,
                                    stdout_handler=h,
                                    stop_event=stop, **kw)
            finally:
                out.close()                                   # rule 1
                if any(not t.done() for t in task_list[:idx]):
                    stop.set()                                # rule 2

        task_list.append(asyncio.create_task(run_stage()))
        upstream = out_link.reader
    return ProcsitterChain(tail=tail, stop_event=stop,
                           task_tuple=tuple(task_list))        # rule 3
