"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       Judging a test application run on either of the two axes of the
       comparison engine.

THE INTERFACE
       One door; input = configuration, output = result:

           config  'SandboxConfigTestRun'  -- THE COMPLETE INPUT: what runs
                                       (command line, sandbox, pype
                                       stage) and what is judged
                                       (subjects -> comparators).
           result  'SandboxResultTestRun'  -- THE COMPLETE OUTPUT: verdict
                                       per subject, attribution record
                                       per stage, THE BRIEF REPORT.

           result = await run_test_app(config)            THE JUDGE
           result = await run_test_app(config, consumer)  THE LAWYER

DESCRIPTION
       THE GROUND is the supervised system call, 'Sandbox.run()';
       COMPOSITION is the SandboxSequence -- supervised calls chained
       stdout -> stdin (both in sandbox.py). This module adds ONLY the
       JUDGING: a test application run is an ordinary SandboxSequence
       whose tail is read by compare.

       PIPE-CONSTRUCTION IS THE INTERFACE, in both directions: between
       sandboxes ('SandboxPipe' links the stages, bytes) and toward
       the comparison engine (the judge_* functions read the tail
       through their own TEXT face, '_TextLineReader' -- the judging
       layer decodes; it assumes NOTHING about compare's byte
       handling).

       The typical judged sequences:

           [(sandbox, test_app_cmd)]                     deterministic
                                                         output

           [(sandbox, test_app_cmd),                     output is
            (pype_sandbox, pype_cmd)]                    non-determin-
                                                         istic

       The pype stage is NOT a filter: it DETERMINISTICALIZES
       non-deterministic output. The triad of the hwut_pype manual,
       one concern per stage:

           the test app PROVOKES and REPORTS,
           pype ANALYZES (deterministicalizes),
           compare JUDGES.

        ------------- RUNNING --------------      ------ JUDGING ------

         supervised call      supervised call
        +--------------+     +--------------+       +--------------+
        | test app     |     | pype         | lines | compare      |
        | [Sandbox]    |---->| [Sandbox]    |------>| Judge or     |
        | PROVOKES,    |pipe | ANALYZES:    |       | Lawyer       |
        | REPORTS      |     | DETERMINIST- | .tail |              |
        +--------------+     | ICALIZES     |       +--------------+
                             +--------------+
         \_________ SandboxSequence ________/        judge_equivalence
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
          itself: SIGPIPE semantics, supervised (SandboxSequence).
"""
import asyncio
import os
import shlex
from   dataclasses import dataclass, field
from   typing      import Optional

from   .sandbox import (Sandbox, SandboxSequence, SandboxResult,
                        E_Containment)

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


def _all_stages_accounted(result_list) -> bool:
    """
    RETURN: True,  every stage COMPLETED by itself or was STOPPED by
                   the judging's own fast-fail.
            False, else -- some stage was contained by a resource cap
                   or failed to launch: the run is broken, whatever
                   fragment of output happened to match.
    """
    return all(r.containment is E_Containment.COMPLETED
               or r.containment is E_Containment.STOPPED
               for r in result_list)


async def judge_equivalence(sequence: SandboxSequence,
                            nominal_provider,
                            compare_config
                            ) -> tuple[tuple[SandboxResult, ...], bool]:
    """
    RETURN: [0] tuple[SandboxResult, ...], one attribution record per
                stage of the sequence, in pipeline order (for the
                pype-deterministicalized run: [test app, pype]).
            [1] True,  subject stream equivalent to nominal AND every
                       stage accounted for.
                False, else.

    FIRST AXIS -- 'is_equivalent', THE JUDGE: investigating
    correctness, quickly. Compare reads the sequence's tail; fast-fail
    both ways (module docstring): an early False stops the whole
    sequence; a containment kill ends the subject, and compare judges
    what arrived.
    """
    err_drain = asyncio.create_task(_drain(sequence.err.reader)) \
                if sequence.err is not None else None
    verdict = False
    try:
        verdict = await compare_main.is_equivalent(
            compare_config, _TextLineReader(sequence.tail.reader),
            nominal_provider)
    finally:
        # A verdict (or an error) while stages still run decides the
        # judgement EARLY -- stop the sequence, then collect. A
        # naturally ended sequence leaves the stop_event untouched.
        if sequence.running():
            sequence.stop_event.set()
        result_list = await sequence.collect()
        if err_drain is not None:
            await err_drain

    if not _all_stages_accounted(result_list):
        verdict = False
    return result_list, verdict


async def judge_association(sequence: SandboxSequence,
                            nominal_provider,
                            compare_config,
                            consumer
                            ) -> tuple[SandboxResult, ...]:
    """
    RETURN: tuple[SandboxResult, ...], one attribution record per
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
        err_drain = asyncio.create_task(_drain(sequence.err.reader)) \
                    if sequence.err is not None else None
        async for chunk_pair in compare_main.associate(
                compare_config, _TextLineReader(sequence.tail.reader),
                nominal_provider):
            outcome = consumer(chunk_pair)
            if asyncio.iscoroutine(outcome):
                await outcome
    finally:
        if sequence.running():
            sequence.stop_event.set()   # error paths only; natural
                                        # completion ends every stage
        result_list = await sequence.collect()
        if err_drain is not None:
            await err_drain
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
#     subject          judged      deterministicalization (pype)
#     ---------------  ----------  ---------------------------------
#     stdout channel   LIVE        a pype STAGE of the running
#                                  sequence (section RUNNING)
#     output file      POST-EXIT   applied post-exit by the
#                                  comparator -- a file may change at
#                                  any moment while the test lives;
#                                  judging or filtering it earlier
#                                  would fail on transients
#
# Post-exit file deterministicalization reuses the ground: it is a
# one-stage SandboxSequence -- pype reading the file as its INPUT-FILE
# argument -- whose tail compare reads. Pipes are the interface,
# everywhere.

@dataclass
class Comparator:
    """RETURN: --. HOW one subject is judged: the nominal it is held
                   against, the compare configuration, and -- for FILE
                   subjects -- an optional pype deterministicalization
                   applied POST-EXIT before judging.

    'nominal' is a '.readline()' provider or a path (opened lazily).
    For the stdout CHANNEL the pype fields stay None: channel
    deterministicalization is a pype STAGE of the running sequence.
    """
    nominal:           object
    compare_config:    object
    pype_sandbox:      Optional[Sandbox] = None
    pype_command_line: Optional[str]     = None


@dataclass
class SandboxConfigTestRun:
    """RETURN: --. THE COMPLETE INPUT of a judged test application
                   run -- the interface definition: hand this to
                   'run_test_app()', receive a 'SandboxResultTestRun'.

    THE RUN -- what becomes the SandboxSequence:

    command_line       command line of the test application.
    sandbox            its supervised call: Sandbox(config, work_dir).
    pype_command_line  command line of the pype stage
                       deterministicalizing the stdout channel LIVE
                       ('python3 hwut_pype.py SCRIPT'); it becomes the
                       second stage of the sequence, in its OWN
                       supervised call.
                       None: the channel is judged as it comes.
    pype_sandbox       the pype stage's supervised call; mandatory
                       exactly when 'pype_command_line' is given.

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
    """
    command_line:      str
    sandbox:           Sandbox
    pype_command_line: Optional[str]        = None
    pype_sandbox:      Optional[Sandbox]    = None

    channel:           Optional[Comparator] = None
    error_channel:     Optional[Comparator] = None
    file_db:           dict                 = field(default_factory=dict)


@dataclass
class SandboxResultTestRun:
    """RETURN: --. THE COMPLETE OUTPUT of a judged test application
                   run: verdict per subject, attribution record per
                   stage, THE BRIEF REPORT -- nothing disappears.
    """
    stage_result_list:  tuple    # live sequence stages, pipeline order
    subject_verdict_db: dict     # "stdout" / "stderr" / file name -> bool
    file_stage_db:      dict     # file name -> tuple[SandboxResult,...]
                                 # (post-exit deterministicalization)
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
        RETURN: tuple[SandboxResult, ...], every attribution record of
                the run -- live pipeline stages AND post-exit file pype
                stages, for resource aggregation.
        """
        return tuple(self.stage_result_list) + tuple(
            r for record_list in self.file_stage_db.values()
            for r in record_list)


def _make_sequence(config: SandboxConfigTestRun) -> SandboxSequence:
    """
    RETURN: SandboxSequence, THE RUNNING side of 'config': the test
            application, followed by the pype stage where configured;
            the stderr pipe is exposed exactly when the configuration
            judges the stderr channel.
    """
    assert (config.pype_command_line is None) \
           == (config.pype_sandbox is None), \
           "pype_command_line and pype_sandbox come together"
    stage_list = [(config.sandbox, config.command_line)]
    if config.pype_command_line is not None:
        stage_list.append((config.pype_sandbox, config.pype_command_line))
    return SandboxSequence(
        stage_list, err_pipe_f=(config.error_channel is not None))


async def run_test_app(config:   SandboxConfigTestRun,
                       consumer=None) -> SandboxResultTestRun:
    """
    RETURN: SandboxResultTestRun, THE COMPLETE OUTPUT: verdict per subject,
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
    sequence = _make_sequence(config)
    if consumer is None:
        return await _judge_test_run(sequence, config)
    return await _associate_test_run(sequence, config, consumer)


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
    if record.containment is E_Containment.LAUNCH_FAILED:
        return E_TestRunResult.PYPE_INTERPRETER_NOT_FOUND
    if record.containment is E_Containment.STOPPED:
        return None
    if record.containment is not E_Containment.COMPLETED:
        return E_TestRunResult.PYPE_CONTAINED
    if record.exit_code == 0:
        return None
    tail = record.stderr_tail
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
            [1] tuple, SandboxResult records of the post-exit
                       deterministicalization (empty without pype).
            [2] E_TestRunResult, the reason this subject contributes
                       to the brief report; None if unsuspicious.

    POST-EXIT ONLY. With a pype comparator, the file is read by a
    one-stage SandboxSequence (pype with the file as INPUT-FILE
    argument); compare reads its tail.
    """
    try:
        nominal, close_f = _open_nominal(comparator.nominal)
    except OSError:
        return False, (), E_TestRunResult.NOMINAL_FILE_NOT_FOUND
    try:
        if not os.path.exists(file_path):
            return False, (), E_TestRunResult.OUTPUT_FILE_NOT_FOUND

        if comparator.pype_sandbox is None:
            verdict = await judge_output_file(file_path, nominal,
                                              comparator.compare_config)
            return verdict, (), None

        sequence = SandboxSequence([
            (comparator.pype_sandbox,
             comparator.pype_command_line + " "
             + shlex.quote(str(file_path)))])
        verdict = False
        try:
            verdict = await compare_main.is_equivalent(
                comparator.compare_config,
                _TextLineReader(sequence.tail.reader), nominal)
        finally:
            if sequence.running():
                sequence.stop_event.set()
            record_list = await sequence.collect()
        reason = _classify_pype_record(record_list[0])
        if not _all_stages_accounted(record_list) or reason is not None:
            verdict = False
        return verdict, record_list, reason
    finally:
        if close_f: nominal.close()


async def _judge_test_run(sequence: SandboxSequence,
                          config:   SandboxConfigTestRun) -> SandboxResultTestRun:
    """
    RETURN: SandboxResultTestRun, verdict per subject and attribution record
            per stage.

    THE JUDGE over the WHOLE configuration (machinery behind
    'run_test_app'; only the SUBJECT fields of 'config' are consulted
    -- the run is the given 'sequence'). Order is mandatory:

        1. the stdout CHANNEL is judged LIVE (fast-fail applies);
           without a channel comparator the run is awaited with the
           channel drained;
        2. only AFTER the run terminated, each file of 'config.file_db'
           is judged -- deterministicalized post-exit where its
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
    # sequence. Unjudged channels are drained.
    channel_list = []            # (subject_name, comparator, reader)
    if config.channel is not None:
        assert config.channel.pype_sandbox is None, \
               "channel deterministicalization is a pype STAGE of the " \
               "sequence, not a comparator property"
        channel_list.append(("stdout", config.channel,
                             _TextLineReader(sequence.tail.reader)))
    if config.error_channel is not None:
        assert config.error_channel.pype_sandbox is None
        assert sequence.err is not None, \
               "config.error_channel demands " \
               "SandboxSequence(..., err_pipe_f=True)"
        channel_list.append(("stderr", config.error_channel,
                             _TextLineReader(sequence.err.reader)))

    drain_task_list = []
    if config.channel is None:
        drain_task_list.append(
            asyncio.create_task(_drain(sequence.tail.reader)))
    if sequence.err is not None and config.error_channel is None:
        drain_task_list.append(
            asyncio.create_task(_drain(sequence.err.reader)))

    async def judge_channel(subject_name, comparator, reader):
        """
        RETURN: (str, bool, E_TestRunResult|None, int) -- subject
                name, verdict, reason, bytes seen. A False verdict
                stops the whole sequence: fast-fail from EITHER
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
            if not verdict and sequence.running():
                sequence.stop_event.set()
        return subject_name, verdict, None, reader.byte_n

    try:
        channel_outcome_list = await asyncio.gather(
            *(judge_channel(*entry) for entry in channel_list))
    except BaseException:
        sequence.stop_event.set()
        await sequence.collect()
        for drain_task in drain_task_list:
            drain_task.cancel()
        raise
    # Channels judged -> the pipeline is decided; a run that still
    # lives is stopped. WITHOUT judged channels there is no early
    # decision: the run completes naturally (collect() waits).
    if channel_list and sequence.running():
        sequence.stop_event.set()
    stage_result_list = await sequence.collect()
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
    # further live stages are pype deterministicalization.
    test_record = stage_result_list[0]
    if test_record.containment is E_Containment.LAUNCH_FAILED:
        reason_list.insert(0, E_TestRunResult.TEST_APP_LAUNCH_FAILED)
    elif test_record.containment is not E_Containment.COMPLETED \
         and test_record.containment is not E_Containment.STOPPED:
        reason_list.insert(0, E_TestRunResult.TEST_APP_CONTAINED)
    for record in stage_result_list[1:]:
        pype_reason = _classify_pype_record(record)
        if pype_reason is not None:
            reason_list.append(pype_reason)

    work_dir = sequence.sandbox_list[0].work_dir
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

    result = SandboxResultTestRun(stage_result_list  = stage_result_list,
                           subject_verdict_db = subject_verdict_db,
                           file_stage_db      = file_stage_db)
    if reason_list:
        result.report = reason_list[0]
    elif not result.verdict:
        result.report = E_TestRunResult.NOT_EQUIVALENT_WITH_NOMINAL
    else:
        result.report = E_TestRunResult.OK
    return result


async def _associate_test_run(sequence: SandboxSequence,
                              config:   SandboxConfigTestRun,
                              consumer) -> SandboxResultTestRun:
    """
    RETURN: SandboxResultTestRun, as _judge_test_run -- with the verdicts
            derived through the Lawyer (THE LAW: the reduction over
            ChunkPair.is_equivalent() equals the Judge's verdict).

    THE LAWYER over the WHOLE configuration (machinery behind
    'run_test_app'; only the SUBJECT fields of 'config' are consulted
    -- the run is the given 'sequence'): for every judged subject the
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

    err_drain = None
    if sequence.err is not None and config.error_channel is None:
        err_drain = asyncio.create_task(_drain(sequence.err.reader))

    if config.channel is not None:
        assert config.channel.pype_sandbox is None
        try:
            nominal, close_f = _open_nominal(config.channel.nominal)
        except OSError:
            reason_list.append(E_TestRunResult.NOMINAL_FILE_NOT_FOUND)
            subject_verdict_db["stdout"] = False
            drain_task = asyncio.create_task(_drain(sequence.tail.reader))
            stage_result_list = await sequence.collect()
            await drain_task
        else:
            try:
                subject_verdict_db["stdout"] = await consume(
                    "stdout", _TextLineReader(sequence.tail.reader),
                    nominal, config.channel.compare_config)
            finally:
                if close_f: nominal.close()
                if sequence.running():
                    sequence.stop_event.set()   # error paths only
                stage_result_list = await sequence.collect()
    else:
        drain_task = asyncio.create_task(_drain(sequence.tail.reader))
        stage_result_list = await sequence.collect()
        await drain_task
    if err_drain is not None:
        await err_drain

    # STDERR channel, judged by the Lawyer as well. The run has ended
    # (collected above); the err pipe holds the buffered stream --
    # sequential consumption is exact, order per subject preserved.
    if config.error_channel is not None:
        assert config.error_channel.pype_sandbox is None
        assert sequence.err is not None, \
               "config.error_channel demands " \
               "SandboxSequence(..., err_pipe_f=True)"
        try:
            nominal, close_f = _open_nominal(config.error_channel.nominal)
        except OSError:
            reason_list.append(E_TestRunResult.NOMINAL_FILE_NOT_FOUND)
            subject_verdict_db["stderr"] = False
        else:
            try:
                subject_verdict_db["stderr"] = await consume(
                    "stderr", _TextLineReader(sequence.err.reader),
                    nominal, config.error_channel.compare_config)
            finally:
                if close_f: nominal.close()

    test_record = stage_result_list[0]
    if test_record.containment is E_Containment.LAUNCH_FAILED:
        reason_list.insert(0, E_TestRunResult.TEST_APP_LAUNCH_FAILED)
    elif test_record.containment is not E_Containment.COMPLETED \
         and test_record.containment is not E_Containment.STOPPED:
        reason_list.insert(0, E_TestRunResult.TEST_APP_CONTAINED)
    for record in stage_result_list[1:]:
        pype_reason = _classify_pype_record(record)
        if pype_reason is not None:
            reason_list.append(pype_reason)

    work_dir = sequence.sandbox_list[0].work_dir
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
            elif comparator.pype_sandbox is not None:
                file_sequence = SandboxSequence([
                    (comparator.pype_sandbox,
                     comparator.pype_command_line + " "
                     + shlex.quote(str(file_path)))])
                try:
                    verdict = await consume(
                        name,
                        _TextLineReader(file_sequence.tail.reader),
                        nominal,
                        comparator.compare_config)
                finally:
                    if file_sequence.running():
                        file_sequence.stop_event.set()
                    record_list = await file_sequence.collect()
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

    result = SandboxResultTestRun(stage_result_list  = stage_result_list,
                           subject_verdict_db = subject_verdict_db,
                           file_stage_db      = file_stage_db)
    if reason_list:
        result.report = reason_list[0]
    elif not result.verdict:
        result.report = E_TestRunResult.NOT_EQUIVALENT_WITH_NOMINAL
    else:
        result.report = E_TestRunResult.OK
    return result
