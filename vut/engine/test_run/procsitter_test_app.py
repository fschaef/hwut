"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       Judging a test application run on either of the two axes of the
       comparison engine.

THE INTERFACE
       One door; input = configuration, output = result:

           config  'ProcsitterConfigTestRun'  -- THE COMPLETE INPUT: what runs
                                       (command line, procsitter, pype
                                       stage) and what is judged
                                       (subjects -> comparators).
           result  'ProcsitterResultTestRun'  -- THE COMPLETE OUTPUT: verdict
                                       per subject, attribution record
                                       per stage, THE BRIEF REPORT.

           result = await run_test_app(config)            THE JUDGE
           result = await run_test_app(config, consumer)  THE LAWYER

DESCRIPTION
       THE GROUND is the supervised system call, 'Procsitter.run()';
       COMPOSITION is the CHAIN (chain) -- supervised calls
       stdout -> stdin (both in procsitter.py). This module adds ONLY the
       JUDGING: a test application run is an ordinary chain
       whose tail is read by compare.

       PIPE-CONSTRUCTION IS THE INTERFACE, in both directions: between
       procsitters ('Link' links the stages, bytes) and toward
       the comparison engine (the judge_* functions read the tail
       through their own TEXT face, '_TextLineReader' -- the judging
       layer decodes; it assumes NOTHING about compare's byte
       handling).

       The typical judged sequences:

           [(procsitter, test_app_cmd)]                     deterministic
                                                         output

           [(procsitter, test_app_cmd),                     output is
            (pype_procsitter, pype_cmd)]                    non-determin-
                                                         istic

       The pype stage is NOT a filter: it DETERMINISTICALIZES
       non-deterministic output. The triad of the hwut_pype manual,
       one concern per stage:

           the test app PROVOKES and REPORTS,
           pype CANONICALISES,
           compare JUDGES.

        ------------- RUNNING --------------      ------ JUDGING ------

         supervised call      supervised call
        +--------------+     +--------------+       +--------------+
        | test app     |     | pype         | lines | compare      |
        | [Procsitter] |---->| [Procsitter] |------>| Judge or     |
        | PROVOKES,    |pipe | CANONICALISES|       | Lawyer       |
        | REPORTS      |     | the stream   | .tail |              |
        +--------------+     +--------------+       +--------------+
         \________________ chain ____________/  judge_equivalence
                                                     judge_association

       Test applications are judged on TWO AXES, the terms of
       compare/main.py:

           judge_equivalence  'is_equivalent' -- THE JUDGE:
                              investigating correctness, QUICKLY;
                              boolean verdict, fast-fail.
           judge_association  'associate' -- THE LAWYER: associating
                              subject lines with nominal lines FOR
                              DISPLAY; full alignment, no fast-fail.
           judge_output_file  output FILES, judged post-exit.

       Every judge_* over a sequence returns ONE ATTRIBUTION RECORD
       PER STAGE, in pipeline order. EVERY stage must have COMPLETED
       (or been STOPPED by the fast-fail) for a verdict to stand: a
       pype stage contained by a resource cap means the judgement
       machinery itself failed -- never equivalent, and the report
       names the stage.

       FAST-FAIL BOTH WAYS (equivalence axis only):
       -- compare returns False -> the sequence's stop_event is set ->
          every stage is stopped (containment STOPPED).
       -- a containment kill in any stage ends its stream ->
          downstream sees EOF, settles, exits -> compare judges what
          arrived (normally: False).
       -- a stage ends while an upstream stage still runs (e.g.
          'sys.exit(n)' gating in a pype block) -> the sequence stops
          itself: SIGPIPE semantics, supervised (the chain rules).
"""
import asyncio
import os
from   dataclasses import dataclass, field
from   typing      import Optional, Sequence

from   vut.engine.procsitter.procsitter   import (Procsitter,
                                                  ProcsitterResult,
                                                  E_Containment)
from   vut.engine.procsitter.construction import (Link, ProcsitterChain,
                                                  chain, tee)

from   vut.auxiliary.test_run_result import E_TestRunResult

import vut.engine.compare.main as compare_main


class _TextLineReader:
    """RETURN: --. The TEXT face of a sequence tail: wraps the tail's
                   byte StreamReader into a '.readline() -> str' line
                   provider, as the comparison engine wants to read it.

    The judging layer performs the decoding ITSELF -- it makes no
    assumption about compare's byte handling. Buffering is unbounded
    per line (a test line longer than any StreamReader limit must not
    break the judgement).
    """
    def __init__(self, byte_reader):
        self._reader = byte_reader
        self._buf    = b""
        self.byte_n  = 0          # total bytes seen: feeds the
                                  # 'test-app-no-output' classification

    async def readline(self) -> str:
        """
        RETURN: str, the next complete line (decoded, newline kept).
                "",  at end of stream.
        """
        while True:
            i = self._buf.find(b"\n")
            if i >= 0:
                line, self._buf = self._buf[:i + 1], self._buf[i + 1:]
                return line.decode("utf-8", errors="replace")
            chunk = await self._reader.read(65536)
            if not chunk:
                line, self._buf = self._buf, b""
                return line.decode("utf-8", errors="replace")
            self.byte_n += len(chunk)
            self._buf   += chunk


# A stage is ACCOUNTED when it RAN TO ITS OWN END (exit 0 or nonzero)
# or was STOPPED by the judging's fast-fail -- i.e. NOT contained by a
# resource cap and NOT a launch failure.
_ACCOUNTED = frozenset((E_Containment.OK_COMPLETED,
                        E_Containment.FAIL_COMPLETED,
                        E_Containment.FAIL_STOPPED))


def _all_stages_accounted(result_list) -> bool:
    """
    RETURN: True,  every stage ran to its own end (OK_/FAIL_COMPLETED)
                   or was STOPPED by the judging's fast-fail.
            False, else -- some stage was contained by a resource cap
                   or failed to launch: the run is broken, whatever
                   fragment of output happened to match.
    """
    return all(r.containment in _ACCOUNTED for r in result_list)


def _running(c: ProcsitterChain) -> bool:
    """
    RETURN: True,  some stage of the chain still executes.
            False, else.
    """
    return any(not task.done() for task in c.task_tuple)


async def _collect(c: ProcsitterChain) -> tuple:
    """
    RETURN: tuple[ProcsitterResult, ...], one attribution record per
            stage, in chain order.
    """
    return tuple(await asyncio.gather(*c.task_tuple))


async def judge_equivalence(c: ProcsitterChain,
                            nominal_provider,
                            compare_config
                            ) -> tuple[tuple[ProcsitterResult, ...], bool]:
    """
    RETURN: [0] tuple[ProcsitterResult, ...], one attribution record per
                stage of the sequence, in pipeline order (for the
                pype-canonicalised run: [test app, pype]).
            [1] True,  subject stream equivalent to nominal AND every
                       stage accounted for.
                False, else.

    FIRST AXIS -- 'is_equivalent', THE JUDGE: investigating
    correctness, quickly. Compare reads the chain's tail; fast-fail
    both ways (module docstring): an early False stops the whole
    chain; a containment kill ends the subject, and compare judges
    what arrived.
    """
    verdict = False
    try:
        verdict = await compare_main.is_equivalent(
            compare_config, _TextLineReader(c.tail.reader),
            nominal_provider)
    finally:
        # A verdict (or an error) while stages still run decides the
        # judgement EARLY -- stop the chain, then collect. A
        # naturally ended chain leaves the stop_event untouched.
        if _running(c):
            c.stop_event.set()
        result_list = await _collect(c)

    if not _all_stages_accounted(result_list):
        verdict = False
    return result_list, verdict


async def judge_association(c: ProcsitterChain,
                            nominal_provider,
                            compare_config,
                            consumer
                            ) -> tuple[ProcsitterResult, ...]:
    """
    RETURN: tuple[ProcsitterResult, ...], one attribution record per
            stage of the sequence, in pipeline order.

    SECOND AXIS -- 'associate', THE LAWYER: associating subject lines
    with nominal lines for display. Every ChunkPair the Lawyer yields
    goes to 'consumer' (sync callable or coroutine function; e.g.
    feeder adaptors rendering the side-by-side view). NO fast-fail:
    association exists to SHOW the divergence, so the sequence is left
    to reach its natural end -- the containment caps of every stage
    still apply. THE LAW holds across the pipeline: the reduction over
    'ChunkPair.is_equivalent()' equals the Judge's verdict.
    """
    try:
        async for chunk_pair in compare_main.associate(
                compare_config, _TextLineReader(c.tail.reader),
                nominal_provider):
            outcome = consumer(chunk_pair)
            if asyncio.iscoroutine(outcome):
                await outcome
    finally:
        if _running(c):
            c.stop_event.set()      # error paths only; natural
                                        # completion ends every stage
        result_list = await _collect(c)
    return result_list


async def judge_output_file(file_path,
                            nominal_provider,
                            compare_config) -> bool:
    """
    RETURN: True,  the file's content is equivalent to the nominal.
            False, else (including: file absent).

    Output FILES are judged POST-EXIT: channels are judged live, files
    after termination (no tail-following).
    """
    try:
        fh = open(file_path, "r")
    except OSError:
        return False
    with fh:
        return await compare_main.is_equivalent(
            compare_config, fh, nominal_provider)


# ------------------------------------------- THE RUN SPECIFICATION
#
# A test run produces SUBJECTS: the stdout channel, and output files.
# The specification maps every subject to its COMPARATOR. The two
# subject kinds differ in WHEN they can be judged:
#
#     subject          judged      canonicalisation (pype)
#     ---------------  ----------  ---------------------------------
#     stdout channel   LIVE        a pype STAGE of the running
#                                  sequence (section RUNNING)
#     output file      POST-EXIT   applied post-exit by the
#                                  comparator -- a file may change at
#                                  any moment while the test lives;
#                                  judging or filtering it earlier
#                                  would fail on transients
#
# Post-exit file canonicalisation reuses the ground: it is a
# one-stage chain -- pype reading the file as its INPUT-FILE
# argument -- whose tail compare reads. Pipes are the interface,
# everywhere.

@dataclass
class Comparator:
    """RETURN: --. HOW one subject is judged: the nominal it is held
                   against, the compare configuration, and -- for FILE
                   subjects -- an optional pype canonicalisation
                   applied POST-EXIT before judging.

    'nominal' is a '.readline()' provider or a path (opened lazily).
    For the stdout CHANNEL the pype fields stay None: channel
    canonicalisation is a pype STAGE of the running chain.
    """
    nominal:           object
    compare_config:    object
    pype_procsitter:      Optional[Procsitter]         = None
    pype_command:      Optional[Sequence[str]]   = None


@dataclass
class ProcsitterConfigTestRun:
    """RETURN: --. THE COMPLETE INPUT of a judged test application
                   run -- the interface definition: hand this to
                   'run_test_app()', receive a 'ProcsitterResultTestRun'.

    THE RUN -- what becomes the chain (chain):

    command            argv of the test application -- a Sequence[str],
                       [program, arg, ...]; executed directly, no
                       shell, nothing to escape.
    procsitter            its supervised call: Procsitter(config, work_dir).
    pype_command       argv of the pype stage canonicalising the
                       stdout channel LIVE ([python, hwut_pype, SCRIPT]);
                       it becomes the second stage of the sequence, in
                       its OWN supervised call.
                       None: the channel is judged as it comes.
    pype_procsitter       the pype stage's supervised call; mandatory
                       exactly when 'pype_command' is given.

    THE SUBJECTS -- channel vs. comparator, what is judged and how:

    channel        Comparator of the stdout channel, judged LIVE.
                   None: stdout is drained, unjudged.
    error_channel  Comparator of the STDERR channel -- stderr is a
                   channel like any other; nominal behavior may be
                   defined on it. Judged LIVE and CONCURRENTLY with
                   stdout; both feed the fast-fail.
                   None: stderr follows the ground's default (tail
                   capture into the stage record).
    file_db        file name (relative to the test app's work dir) ->
                   Comparator; judged POST-EXIT only. A file
                   comparator may carry its own post-exit pype.

    LOGGING -- the stdout production, tapped to files (a log is a plain
    consumer on a production port; tee, producer side). Independent of
    judging: set them or not, the verdict is unchanged.

    stdout_log_before_pype  path to write the test app's RAW stdout
                   (stage 0's production, before any pype). None: not
                   logged.
    stdout_log_after_pype   path to write the DETERMINIZED stdout (the
                   last stage's production -- what is judged). None: not
                   logged. Without a pype stage this is the same stream
                   as 'before', so the two files then hold identical
                   bytes. stderr is NOT logged here: it is already kept
                   as the record's last-100-lines tail (or judged, when
                   an error_channel is given).
    """
    command:           Sequence[str]
    procsitter:           Procsitter
    pype_command:      Optional[Sequence[str]] = None
    pype_procsitter:      Optional[Procsitter]       = None

    channel:           Optional[Comparator] = None
    error_channel:     Optional[Comparator] = None
    file_db:           dict                 = field(default_factory=dict)

    stdout_log_before_pype: Optional[str] = None
    stdout_log_after_pype:  Optional[str] = None


@dataclass
class ProcsitterResultTestRun:
    """RETURN: --. THE COMPLETE OUTPUT of a judged test application
                   run: verdict per subject, attribution record per
                   stage, THE BRIEF REPORT -- nothing disappears.
    """
    stage_result_list:  tuple    # live sequence stages, pipeline order
    subject_verdict_db: dict     # "stdout" / "stderr" / file name -> bool
    file_stage_db:      dict     # file name -> tuple[ProcsitterResult,...]
                                 # (post-exit canonicalisation)
    report:             E_TestRunResult = E_TestRunResult.OK
                                 # THE BRIEF REPORT: 'ok' or the reason
                                 # of failure; 'str(report)' prints the
                                 # token (vut.auxiliary.test_run_result)

    @property
    def verdict(self) -> bool:
        """
        RETURN: True,  every subject judged equivalent AND every stage
                       -- live and post-exit -- accounted for
                       (COMPLETED, or STOPPED by the fast-fail).
                False, else.
        """
        if not all(self.subject_verdict_db.values()):
            return False
        if not _all_stages_accounted(self.stage_result_list):
            return False
        return all(_all_stages_accounted(record_list)
                   for record_list in self.file_stage_db.values())

    @property
    def cpu_time_sec(self) -> "Optional[float]":
        """
        RETURN: float, TOTAL cpu seconds of the run -- SUMMED over every
                       stage (live pipeline AND post-exit file pype):
                       cpu time is WORK, it adds up whether stages ran
                       concurrently or in sequence. This is the most
                       machine-INDEPENDENT cost the run exposes (it
                       excludes waiting/scheduling); scale it by a
                       per-machine speed factor to estimate elsewhere.
                None,  no stage could measure cpu time (no 'resource').
        """
        values = [r.cpu_time_sec for r in self._all_records()
                  if r.cpu_time_sec is not None]
        return sum(values) if values else None

    @property
    def wall_clock_sec(self) -> float:
        """
        RETURN: float, ELAPSED seconds of the run: the live stages run
                       CONCURRENTLY (pipe-connected), so their share is
                       the MAX stage wall; the post-exit file stages run
                       afterwards in SEQUENCE, so their walls ADD. Hence
                       max(live) + sum(post-exit). 0.0 for an empty run.
        """
        live = [r.wall_clock_sec for r in self.stage_result_list]
        post = [r.wall_clock_sec for record_list in self.file_stage_db.values()
                for r in record_list]
        return (max(live) if live else 0.0) + sum(post)

    @property
    def peak_memory_mb(self) -> "Optional[float]":
        """
        RETURN: float, the high-water memory mark: the MAX peak observed
                       across stages (MB). The true concurrent peak lies
                       between this and the sum of stage peaks; the max
                       is the honest, always-valid lower bound.
                None,  no stage could measure memory (no psutil).
        """
        values = [r.peak_memory_mb for r in self._all_records()
                  if r.peak_memory_mb is not None]
        return max(values) if values else None

    def _all_records(self) -> tuple:
        """
        RETURN: tuple[ProcsitterResult, ...], every attribution record of
                the run -- live pipeline stages AND post-exit file pype
                stages, for resource aggregation.
        """
        return tuple(self.stage_result_list) + tuple(
            r for record_list in self.file_stage_db.values()
            for r in record_list)


def _launch(config: ProcsitterConfigTestRun):
    """
    RETURN: [0] ProcsitterChain, THE RUNNING side of 'config': the test
                application, followed by the pype stage where
                configured (chain -- the chain rules apply).
            [1] Link|None, the test app's stderr production, wired
                exactly when the configuration JUDGES the stderr
                channel (else stderr keeps the ground's default:
                capture into the record).
            [2] Task|None, the closer handing stderr EOF onward when
                the test app ends (await it before reading records).
            [3] tuple, the close callables of the stdout LOG files
                opened for this run (before/after the pype tap); call
                them AFTER the records are collected. Empty when no
                logging was asked.
    """
    assert (config.pype_command is None) \
           == (config.pype_procsitter is None), \
           "pype_command and pype_procsitter come together"
    err_link = Link() if config.error_channel is not None else None
    last_i   = 1 if config.pype_command is not None else 0

    # stdout LOG TAPS -- a log file is a plain consumer on a production
    # port (tee, producer side; chain tees it onto the chain
    # edge). 'before' listens to the test app's raw stdout (stage 0);
    # 'after' listens to the last stage's stdout -- the canonicalised
    # stream that is judged (stage 0 itself when no pype runs, so the
    # two then capture the same bytes).
    tap_db  = {}                     # stage index -> [consumer, ...]
    closers = []
    def add_log(path, stage_i):
        if path is None:
            return
        fh = open(path, "wb")
        closers.append(fh.close)
        async def consume(data, _write=fh.write):
            _write(data)
        tap_db.setdefault(stage_i, []).append(consume)
    add_log(config.stdout_log_before_pype, 0)
    add_log(config.stdout_log_after_pype, last_i)

    kwargs_0 = {}
    if err_link is not None:
        kwargs_0["stderr_handler"] = err_link.feed
    if tap_db.get(0):
        kwargs_0["stdout_handler"] = tee(*tap_db[0])
    stage_list = [(config.procsitter, config.command, kwargs_0)]

    if config.pype_command is not None:
        kwargs_1 = {}
        if tap_db.get(1):
            kwargs_1["stdout_handler"] = tee(*tap_db[1])
        stage_list.append((config.pype_procsitter, config.pype_command,
                           kwargs_1))

    c = chain(stage_list)

    err_closer = None
    if err_link is not None:
        async def close_err():
            """RETURN: None. Stage 0 ended -> its stderr listeners
            see EOF (rule 1, applied to the diagnostic production)."""
            with suppress_exception():
                await asyncio.shield(c.task_tuple[0])
            err_link.close()
        err_closer = asyncio.create_task(close_err())
    return c, err_link, err_closer, tuple(closers)


def suppress_exception():
    """
    RETURN: context manager, swallowing any exception -- the stderr
            closer must close the link whatever stage 0 died of.
    """
    from contextlib import suppress
    return suppress(BaseException)


async def run_test_app(config:   ProcsitterConfigTestRun,
                       consumer=None) -> ProcsitterResultTestRun:
    """
    RETURN: ProcsitterResultTestRun, THE COMPLETE OUTPUT: verdict per subject,
            attribution record per stage, THE BRIEF REPORT.

    THE DOOR of this module: input = configuration, output = result.
    The axis is chosen by 'consumer':

        None      THE JUDGE ('is_equivalent'): investigating
                  correctness, QUICKLY -- fast-fail from any judged
                  channel.
        callable  THE LAWYER ('associate'): the full alignment for
                  display; every ChunkPair goes to
                  'consumer(subject_name, chunk_pair)' (sync callable
                  or coroutine function); no fast-fail.
    """
    c, err_link, err_closer, log_closers = _launch(config)
    try:
        if consumer is None:
            return await _judge_test_run(c, err_link, config)
        return await _associate_test_run(c, err_link, config,
                                         consumer)
    finally:
        if err_closer is not None:
            await err_closer
        for close in log_closers:      # records collected -> flush the logs
            close()


def _open_nominal(nominal):
    """
    RETURN: [0] object, a '.readline()' line provider for 'nominal'.
            [1] bool,   True if [0] was opened here and must be closed.
    """
    if isinstance(nominal, (str, os.PathLike)):
        return open(nominal, "r"), True
    return nominal, False


async def _drain(reader):
    """RETURN: None. Consumes 'reader' to EOF (unjudged channel)."""
    while not reader.at_eof():
        await reader.read(4096)


def _classify_pype_record(record) -> "E_TestRunResult | None":
    """
    RETURN: E_TestRunResult, the reason a failed pype stage contributes
                             to the brief report.
            None,            the stage is unsuspicious: clean, or
                             STOPPED by the judging's own fast-fail.

    Classification of nonzero exits rests on the CAPTURED STDERR TAIL:
    the interpreter path failing to open ("can't open file") is the
    interpreter missing; 'pype:'-prefixed errors are script problems
    (missing script/import vs. any other script error).
    """
    if record.containment is E_Containment.FAIL_LAUNCH:
        return E_TestRunResult.PYPE_INTERPRETER_NOT_FOUND
    if record.containment is E_Containment.OK_COMPLETED \
       or record.containment is E_Containment.FAIL_STOPPED:
        return None
    if record.containment is not E_Containment.FAIL_COMPLETED:
        return E_TestRunResult.PYPE_CONTAINED   # a resource cap fired
    # FAIL_COMPLETED: exited by itself, nonzero -- classify by the tail.
    tail = record.stderr_last_100_lines
    if "can't open file" in tail:
        return E_TestRunResult.PYPE_INTERPRETER_NOT_FOUND
    if "pype:" in tail:
        if "Errno 2" in tail or "No such file" in tail \
           or "cannot find import" in tail:
            return E_TestRunResult.PYPE_FILE_NOT_FOUND
        return E_TestRunResult.PYPE_FILE_SYNTAX_ERROR
    return E_TestRunResult.PYPE_FAILED


async def _judge_file(file_path, comparator):
    """
    RETURN: [0] bool,  the file subject's verdict.
            [1] tuple, ProcsitterResult records of the post-exit
                       canonicalisation (empty without pype).
            [2] E_TestRunResult, the reason this subject contributes
                       to the brief report; None if unsuspicious.

    POST-EXIT ONLY. With a pype comparator, the file is read by a
    one-stage chain (pype with the file as INPUT-FILE
    argument); compare reads its tail.
    """
    try:
        nominal, close_f = _open_nominal(comparator.nominal)
    except OSError:
        return False, (), E_TestRunResult.NOMINAL_FILE_NOT_FOUND
    try:
        if not os.path.exists(file_path):
            return False, (), E_TestRunResult.OUTPUT_FILE_NOT_FOUND

        if comparator.pype_procsitter is None:
            verdict = await judge_output_file(file_path, nominal,
                                              comparator.compare_config)
            return verdict, (), None

        c = chain([
            (comparator.pype_procsitter,
             [*comparator.pype_command, str(file_path)])])
        verdict = False
        try:
            verdict = await compare_main.is_equivalent(
                comparator.compare_config,
                _TextLineReader(c.tail.reader), nominal)
        finally:
            if _running(c):
                c.stop_event.set()
            record_list = await _collect(c)
        reason = _classify_pype_record(record_list[0])
        if not _all_stages_accounted(record_list) or reason is not None:
            verdict = False
        return verdict, record_list, reason
    finally:
        if close_f: nominal.close()


async def _judge_test_run(c:    ProcsitterChain,
                          err_link, config) -> ProcsitterResultTestRun:
    """
    RETURN: ProcsitterResultTestRun, verdict per subject and attribution record
            per stage.

    THE JUDGE over the WHOLE configuration (machinery behind
    'run_test_app'; only the SUBJECT fields of 'config' are consulted
    -- the run is the given 'c'). Order is mandatory:

        1. the stdout CHANNEL is judged LIVE (fast-fail applies);
           without a channel comparator the run is awaited with the
           channel drained;
        2. only AFTER the run terminated, each file of 'config.file_db'
           is judged -- canonicalised post-exit where its
           comparator says so.

    Files are judged even when the channel already failed: the result
    is the complete account; the overall '.verdict' is the reduction,
    '.report' the BRIEF REPORT -- 'ok' or the reason of failure
    (E_TestRunResult), with test-app reasons outranking pype reasons
    outranking subject/nominal reasons.
    """
    subject_verdict_db  = {}
    file_stage_db       = {}
    reason_list         = []     # deterministic order, first one wins

    # LIVE CHANNELS -- stdout AND stderr: stderr is a channel like any
    # other; nominal behavior may be defined on it. Judged channels
    # run CONCURRENTLY; a False verdict on EITHER fast-fails the whole
    # chain. The unjudged stdout is drained; unjudged stderr keeps
    # the ground's default (capture into the record) -- no link, no
    # draining.
    channel_list = []            # (subject_name, comparator, reader)
    if config.channel is not None:
        assert config.channel.pype_procsitter is None, \
               "channel canonicalisation is a pype STAGE of the " \
               "chain, not a comparator property"
        channel_list.append(("stdout", config.channel,
                             _TextLineReader(c.tail.reader)))
    if config.error_channel is not None:
        assert config.error_channel.pype_procsitter is None
        assert err_link is not None
        channel_list.append(("stderr", config.error_channel,
                             _TextLineReader(err_link.reader)))

    drain_task_list = []
    if config.channel is None:
        drain_task_list.append(
            asyncio.create_task(_drain(c.tail.reader)))

    async def judge_channel(subject_name, comparator, reader):
        """
        RETURN: (str, bool, E_TestRunResult|None, int) -- subject
                name, verdict, reason, bytes seen. A False verdict
                stops the whole chain: fast-fail from EITHER
                channel.
        """
        try:
            nominal, close_f = _open_nominal(comparator.nominal)
        except OSError:
            return (subject_name, False,
                    E_TestRunResult.NOMINAL_FILE_NOT_FOUND, 0)
        verdict = False
        try:
            verdict = await compare_main.is_equivalent(
                comparator.compare_config, reader, nominal)
        finally:
            if close_f: nominal.close()
            if not verdict and _running(c):
                c.stop_event.set()
        return subject_name, verdict, None, reader.byte_n

    try:
        channel_outcome_list = await asyncio.gather(
            *(judge_channel(*entry) for entry in channel_list))
    except BaseException:
        c.stop_event.set()
        await _collect(c)
        for drain_task in drain_task_list:
            drain_task.cancel()
        raise
    # Channels judged -> the pipeline is decided; a run that still
    # lives is stopped. WITHOUT judged channels there is no early
    # decision: the run completes naturally (collect() waits).
    if channel_list and _running(c):
        c.stop_event.set()
    stage_result_list = await _collect(c)
    for drain_task in drain_task_list:
        await drain_task

    accounted_f         = _all_stages_accounted(stage_result_list)
    channel_no_output_f = bool(channel_outcome_list)
    for subject_name, verdict, reason, byte_n in channel_outcome_list:
        if not accounted_f:
            verdict = False
        subject_verdict_db[subject_name] = verdict
        if reason is not None:
            reason_list.append(reason)
        if verdict or byte_n > 0:
            channel_no_output_f = False

    # Live stage reasons: the test app (stage 0) outranks everything;
    # further live stages are pype canonicalisation.
    test_record = stage_result_list[0]
    if test_record.containment is E_Containment.FAIL_LAUNCH:
        reason_list.insert(0, E_TestRunResult.TEST_APP_LAUNCH_FAILED)
    elif test_record.containment not in _ACCOUNTED:
        reason_list.insert(0, E_TestRunResult.TEST_APP_CONTAINED)
    for record in stage_result_list[1:]:
        pype_reason = _classify_pype_record(record)
        if pype_reason is not None:
            reason_list.append(pype_reason)

    work_dir = config.procsitter.work_dir
    for name in sorted(config.file_db):
        verdict, record_list, reason = await _judge_file(
            os.path.join(work_dir, name), config.file_db[name])
        subject_verdict_db[name] = verdict
        if record_list:
            file_stage_db[name] = record_list
        if reason is not None:
            reason_list.append(reason)

    if channel_no_output_f and not reason_list:
        reason_list.append(E_TestRunResult.TEST_APP_NO_OUTPUT)

    result = ProcsitterResultTestRun(stage_result_list  = stage_result_list,
                           subject_verdict_db = subject_verdict_db,
                           file_stage_db      = file_stage_db)
    if reason_list:
        result.report = reason_list[0]
    elif not result.verdict:
        result.report = E_TestRunResult.NOT_EQUIVALENT_WITH_NOMINAL
    else:
        result.report = E_TestRunResult.OK
    return result


async def _associate_test_run(c:    ProcsitterChain,
                              err_link, config,
                              consumer) -> ProcsitterResultTestRun:
    """
    RETURN: ProcsitterResultTestRun, as _judge_test_run -- with the verdicts
            derived through the Lawyer (THE LAW: the reduction over
            ChunkPair.is_equivalent() equals the Judge's verdict).

    THE LAWYER over the WHOLE configuration (machinery behind
    'run_test_app'; only the SUBJECT fields of 'config' are consulted
    -- the run is the given 'c'): for every judged subject the
    full alignment is produced and each ChunkPair goes to
    'consumer(subject_name, chunk_pair)' -- subject_name is "stdout",
    "stderr" or the file name. No fast-fail; the same live/post-exit
    order as _judge_test_run holds.
    """
    async def consume(subject_name, provider, nominal, compare_config):
        """RETURN: bool, the Lawyer's reduction for one subject."""
        equivalent_f = True
        async for chunk_pair in compare_main.associate(
                compare_config, provider, nominal):
            equivalent_f = equivalent_f and chunk_pair.is_equivalent()
            outcome = consumer(subject_name, chunk_pair)
            if asyncio.iscoroutine(outcome):
                await outcome
        return equivalent_f

    subject_verdict_db = {}
    file_stage_db      = {}
    reason_list        = []

    if config.channel is not None:
        assert config.channel.pype_procsitter is None
        try:
            nominal, close_f = _open_nominal(config.channel.nominal)
        except OSError:
            reason_list.append(E_TestRunResult.NOMINAL_FILE_NOT_FOUND)
            subject_verdict_db["stdout"] = False
            drain_task = asyncio.create_task(_drain(c.tail.reader))
            stage_result_list = await _collect(c)
            await drain_task
        else:
            try:
                subject_verdict_db["stdout"] = await consume(
                    "stdout", _TextLineReader(c.tail.reader),
                    nominal, config.channel.compare_config)
            finally:
                if close_f: nominal.close()
                if _running(c):
                    c.stop_event.set()      # error paths only
                stage_result_list = await _collect(c)
    else:
        drain_task = asyncio.create_task(_drain(c.tail.reader))
        stage_result_list = await _collect(c)
        await drain_task

    # STDERR channel, judged by the Lawyer as well. The run has ended
    # (collected above); the err link holds the buffered stream --
    # sequential consumption is exact, order per subject preserved.
    if config.error_channel is not None:
        assert config.error_channel.pype_procsitter is None
        assert err_link is not None
        try:
            nominal, close_f = _open_nominal(config.error_channel.nominal)
        except OSError:
            reason_list.append(E_TestRunResult.NOMINAL_FILE_NOT_FOUND)
            subject_verdict_db["stderr"] = False
        else:
            try:
                subject_verdict_db["stderr"] = await consume(
                    "stderr", _TextLineReader(err_link.reader),
                    nominal, config.error_channel.compare_config)
            finally:
                if close_f: nominal.close()

    test_record = stage_result_list[0]
    if test_record.containment is E_Containment.FAIL_LAUNCH:
        reason_list.insert(0, E_TestRunResult.TEST_APP_LAUNCH_FAILED)
    elif test_record.containment not in _ACCOUNTED:
        reason_list.insert(0, E_TestRunResult.TEST_APP_CONTAINED)
    for record in stage_result_list[1:]:
        pype_reason = _classify_pype_record(record)
        if pype_reason is not None:
            reason_list.append(pype_reason)

    work_dir = config.procsitter.work_dir
    for name in sorted(config.file_db):
        comparator = config.file_db[name]
        file_path  = os.path.join(work_dir, name)
        try:
            nominal, close_f = _open_nominal(comparator.nominal)
        except OSError:
            reason_list.append(E_TestRunResult.NOMINAL_FILE_NOT_FOUND)
            subject_verdict_db[name] = False
            continue
        try:
            if not os.path.exists(file_path):
                reason_list.append(E_TestRunResult.OUTPUT_FILE_NOT_FOUND)
                verdict = False
            elif comparator.pype_procsitter is not None:
                file_chain = chain([
                    (comparator.pype_procsitter,
                     [*comparator.pype_command, str(file_path)])])
                try:
                    verdict = await consume(
                        name,
                        _TextLineReader(file_chain.tail.reader),
                        nominal,
                        comparator.compare_config)
                finally:
                    if _running(file_chain):
                        file_chain.stop_event.set()
                    record_list = await _collect(file_chain)
                pype_reason = _classify_pype_record(record_list[0])
                if not _all_stages_accounted(record_list) \
                   or pype_reason is not None:
                    verdict = False
                if pype_reason is not None:
                    reason_list.append(pype_reason)
                file_stage_db[name] = record_list
            else:
                with open(file_path, "r") as fh:
                    verdict = await consume(name, fh, nominal,
                                            comparator.compare_config)
            subject_verdict_db[name] = verdict
        finally:
            if close_f: nominal.close()

    result = ProcsitterResultTestRun(stage_result_list  = stage_result_list,
                           subject_verdict_db = subject_verdict_db,
                           file_stage_db      = file_stage_db)
    if reason_list:
        result.report = reason_list[0]
    elif not result.verdict:
        result.report = E_TestRunResult.NOT_EQUIVALENT_WITH_NOMINAL
    else:
        result.report = E_TestRunResult.OK
    return result
