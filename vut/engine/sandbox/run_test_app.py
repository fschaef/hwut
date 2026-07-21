"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       Judging a test application run on either of the two axes of the
       comparison engine.

DESCRIPTION
       THE GROUND is the supervised system call, 'Sandbox.run()';
       COMPOSITION is the SandboxSequence -- supervised calls chained
       stdout -> stdin (both in sandbox.py). This module adds ONLY the
       JUDGING: a test application run is an ordinary SandboxSequence
       whose tail is read by compare.

       PIPE-CONSTRUCTION IS THE INTERFACE, in both directions: between
       sandboxes ('SandboxPipe' links the stages) and toward the
       comparison engine (the judge_* functions consume
       'sequence.tail.reader' -- the same pipe face, nothing special).

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

import vut.engine.compare.main as compare_main


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
    verdict = False
    try:
        verdict = await compare_main.is_equivalent(
            compare_config, sequence.tail.reader, nominal_provider)
    finally:
        # A verdict (or an error) while stages still run decides the
        # judgement EARLY -- stop the sequence, then collect. A
        # naturally ended sequence leaves the stop_event untouched.
        if sequence.running():
            sequence.stop_event.set()
        result_list = await sequence.collect()

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
        async for chunk_pair in compare_main.associate(
                compare_config, sequence.tail.reader, nominal_provider):
            outcome = consumer(chunk_pair)
            if asyncio.iscoroutine(outcome):
                await outcome
    finally:
        if sequence.running():
            sequence.stop_event.set()   # error paths only; natural
                                        # completion ends every stage
        result_list = await sequence.collect()
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
class TestRunSpec:
    """RETURN: --. CHANNEL vs. COMPARATOR: what of a test run is
                   judged, and how.

    channel   Comparator of the stdout channel.
              None: stdout is drained, unjudged.
    file_db   file name (relative to the test app's work dir) ->
              Comparator; judged POST-EXIT only.
    """
    channel: Optional[Comparator] = None
    file_db: dict                 = field(default_factory=dict)


@dataclass
class TestRunJudgement:
    """RETURN: --. THE COMPLETE ACCOUNT of a judged test run: verdict
                   per subject, attribution record per stage --
                   nothing disappears.
    """
    stage_result_list:  tuple    # live sequence stages, pipeline order
    subject_verdict_db: dict     # "stdout" / file name -> bool
    file_stage_db:      dict     # file name -> tuple[SandboxResult,...]
                                 # (post-exit deterministicalization)

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


async def _judge_file(file_path, comparator):
    """
    RETURN: [0] bool,  the file subject's verdict.
            [1] tuple, SandboxResult records of the post-exit
                       deterministicalization (empty without pype).

    POST-EXIT ONLY. With a pype comparator, the file is read by a
    one-stage SandboxSequence (pype with the file as INPUT-FILE
    argument); compare reads its tail.
    """
    nominal, close_f = _open_nominal(comparator.nominal)
    try:
        if comparator.pype_sandbox is None:
            verdict = await judge_output_file(file_path, nominal,
                                              comparator.compare_config)
            return verdict, ()

        if not os.path.exists(file_path):
            return False, ()
        sequence = SandboxSequence([
            (comparator.pype_sandbox,
             comparator.pype_command_line + " "
             + shlex.quote(str(file_path)))])
        verdict = False
        try:
            verdict = await compare_main.is_equivalent(
                comparator.compare_config, sequence.tail.reader, nominal)
        finally:
            if sequence.running():
                sequence.stop_event.set()
            record_list = await sequence.collect()
        if not _all_stages_accounted(record_list):
            verdict = False
        return verdict, record_list
    finally:
        if close_f: nominal.close()


async def judge_test_run(sequence: SandboxSequence,
                         spec:     TestRunSpec) -> TestRunJudgement:
    """
    RETURN: TestRunJudgement, verdict per subject and attribution
            record per stage.

    THE JUDGE over the WHOLE run specification. Order is mandatory:

        1. the stdout CHANNEL is judged LIVE (fast-fail applies);
           without a channel comparator the run is awaited with the
           channel drained;
        2. only AFTER the run terminated, each file of 'spec.file_db'
           is judged -- deterministicalized post-exit where its
           comparator says so.

    Files are judged even when the channel already failed: the
    judgement is the complete account; the overall '.verdict' is the
    reduction.
    """
    subject_verdict_db = {}
    file_stage_db      = {}

    if spec.channel is not None:
        assert spec.channel.pype_sandbox is None, \
               "channel deterministicalization is a pype STAGE of the " \
               "sequence, not a comparator property"
        nominal, close_f = _open_nominal(spec.channel.nominal)
        try:
            stage_result_list, verdict = await judge_equivalence(
                sequence, nominal, spec.channel.compare_config)
        finally:
            if close_f: nominal.close()
        subject_verdict_db["stdout"] = verdict
    else:
        drain_task = asyncio.create_task(_drain(sequence.tail.reader))
        stage_result_list = await sequence.collect()
        await drain_task

    work_dir = sequence.sandbox_list[0].work_dir
    for name in sorted(spec.file_db):
        verdict, record_list = await _judge_file(
            os.path.join(work_dir, name), spec.file_db[name])
        subject_verdict_db[name] = verdict
        if record_list:
            file_stage_db[name] = record_list

    return TestRunJudgement(stage_result_list  = stage_result_list,
                            subject_verdict_db = subject_verdict_db,
                            file_stage_db      = file_stage_db)


async def associate_test_run(sequence: SandboxSequence,
                             spec:     TestRunSpec,
                             consumer) -> TestRunJudgement:
    """
    RETURN: TestRunJudgement, as judge_test_run -- with the verdicts
            derived through the Lawyer (THE LAW: the reduction over
            ChunkPair.is_equivalent() equals the Judge's verdict).

    THE LAWYER over the WHOLE run specification: for every judged
    subject the full alignment is produced and each ChunkPair goes to
    'consumer(subject_name, chunk_pair)' -- subject_name is "stdout"
    or the file name. No fast-fail; the same live/post-exit order as
    judge_test_run holds.
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

    if spec.channel is not None:
        assert spec.channel.pype_sandbox is None
        nominal, close_f = _open_nominal(spec.channel.nominal)
        try:
            subject_verdict_db["stdout"] = await consume(
                "stdout", sequence.tail.reader, nominal,
                spec.channel.compare_config)
        finally:
            if close_f: nominal.close()
            if sequence.running():
                sequence.stop_event.set()   # error paths only
            stage_result_list = await sequence.collect()
    else:
        drain_task = asyncio.create_task(_drain(sequence.tail.reader))
        stage_result_list = await sequence.collect()
        await drain_task

    work_dir = sequence.sandbox_list[0].work_dir
    for name in sorted(spec.file_db):
        comparator       = spec.file_db[name]
        nominal, close_f = _open_nominal(comparator.nominal)
        file_path        = os.path.join(work_dir, name)
        try:
            if comparator.pype_sandbox is not None \
               and os.path.exists(file_path):
                file_sequence = SandboxSequence([
                    (comparator.pype_sandbox,
                     comparator.pype_command_line + " "
                     + shlex.quote(str(file_path)))])
                try:
                    verdict = await consume(name,
                                            file_sequence.tail.reader,
                                            nominal,
                                            comparator.compare_config)
                finally:
                    if file_sequence.running():
                        file_sequence.stop_event.set()
                    record_list = await file_sequence.collect()
                if not _all_stages_accounted(record_list):
                    verdict = False
                file_stage_db[name] = record_list
            elif os.path.exists(file_path):
                with open(file_path, "r") as fh:
                    verdict = await consume(name, fh, nominal,
                                            comparator.compare_config)
            else:
                verdict = False
            subject_verdict_db[name] = verdict
        finally:
            if close_f: nominal.close()

    return TestRunJudgement(stage_result_list  = stage_result_list,
                            subject_verdict_db = subject_verdict_db,
                            file_stage_db      = file_stage_db)
