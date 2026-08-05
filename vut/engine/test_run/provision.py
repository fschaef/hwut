"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       PROVISION -- how the subjects of a test come to exist.

DESCRIPTION
       ONE PROVISION, FOUR STAGES. A Provision holds its stages as
       MEMBERS; a member that is None is a stage this provision does not
       have. Absence is DATA -- inspectable, reported by the footprint --
       never a null object pretending something ran:

           stage_build         sources     -> THE APPLICATION
           stage_execute       application -> raw streams, fanned out
           stage_canonicalise  raw         -> THE SUBJECT
           stage_load          store       -> THE SUBJECT

       EXACTLY ONE PATH. 'stage_execute' and 'stage_load' exclude each
       other; 'stage_build' and 'stage_canonicalise' stand only beside
       'stage_execute' -- a loaded subject is ALREADY canonical, which
       is why a canonicaliser change demands a re-run. The invariants
       are checked at construction, where the wiring is written.

       EVERY STAGE IS A SUPPLIER: it hands over its product, or one
       token of the brief vocabulary saying why not. NO STAGE RAISES.
       Provision failure is TEST failure and the suite runs on -- that
       robustness is not built on top of this contract, it is a
       consequence of it (README 2.6).

       SHARING IS INSTANCE IDENTITY. A stage that must not repeat its
       work REMEMBERS it ('BuildStage'): wire the SAME instance into
       every Provision of one application, and the tool builds once.
       Sharing is the planner's deliberate act, never the stage's.

       THE PLANNERS ARE FUNCTIONS, NOT CLASSES. 'Run(...)' wires
       execution, 'Replay(...)' wires load, 'provision_of(...)' chooses
       from the request. After wiring there is ONE kind of Provision:
       nothing downstream can tell a subject's provenance by type
       (README 2.4). The 'kind' attribute exists for OBSERVATION only.

       A SUBJECT IS A NOMINAL-KIND OBJECT. Subject and nominal are the
       same kind of thing (README 2.3); a comparison merely aligns two
       readers. So provision hands back 'subject name -> Nominal', and
       nothing downstream can tell a subject from a nominal by its type.

       CANONICALISATION IS PROVISION, not comparison: a pype stage is HOW
       a raw stream becomes the comparable stream. It happens here, per
       subject, and what is stored and compared is its result. A subject
       with no canonicaliser declared is comparable raw -- raw IS
       canonical for it.

       PROVISION JUDGES NOTHING. It reports what happened as one token of
       the brief vocabulary and hands over readers. Whether the test
       passes is decided above.
______________________________________________________________________________
"""
import asyncio
from   dataclasses import dataclass
from   pathlib     import Path

from   vut.engine.test_run.result       import E_TestRunResult
from   vut.engine.procsitter.procsitter  import Procsitter, E_Containment
from   vut.engine.procsitter.construction import Link, chain
from   vut.engine.test_run.build         import build
from   vut.engine.test_run.configuration import E_SourceKind
from   vut.engine.test_run.nominal       import BytesNominal
from   vut.engine.test_run.report        import Provision as ProvisionRecord


STDOUT = "stdout"
STDERR = "stderr"


def application_argv(configuration, choice_name):
    """
    RETURN: list[str], the command line of ONE call of the test
            application: the source kind decides the prefix, and the
            CHOICE NAME is appended as the argument that selects it.

    A test without choices is keyed by 'None' and gets no such argument.
    """
    kind = configuration.source_kind
    if   kind is E_SourceKind.INTERPRETED:
        argv = [str(x) for x in configuration.interpreter]
        argv.append(str(configuration.source_file))
    elif kind is E_SourceKind.COMPILED:
        target_list = list(configuration.build.target_list)
        artifact    = target_list[0] if target_list \
                                     else configuration.stem
        argv = [str(configuration.build_directory / artifact)]
    else:
        argv = [str(Path(configuration.test_directory)
                    / configuration.source_file)]
    if choice_name is not None:
        argv.append(str(choice_name))
    return argv


async def _read_all(reader):
    """RETURN: str, everything the reader yields, to EOF."""
    chunk_list = []
    while not reader.at_eof():
        data = await reader.read(4096)
        if data: chunk_list.append(data)
    return b"".join(chunk_list).decode("utf-8", errors="replace")


async def _read_all_timed(reader):
    """
    RETURN: (str, tuple), everything the reader yields, and the DELTA
            time before each line, in seconds.

    The cadence is a property of the RAW stream, measured as the lines
    ARRIVE -- which is why it is taken here and not reconstructed later.
    The first delta is measured from the first read, so it is the gap
    before the first line, not the process's start-up.
    """
    import time
    line_list, delta_list = [], []
    mark = time.monotonic()
    while not reader.at_eof():
        raw = await reader.readline()
        if not raw: break
        now = time.monotonic()
        delta_list.append(round(now - mark, 6))
        mark = now
        line_list.append(raw)
    return (b"".join(line_list).decode("utf-8", errors="replace"),
            tuple(delta_list))


async def canonicalise(text, pype_argv, procsitter):
    """
    RETURN: (str, E_TestRunResult), the canonicalised text and the report.

    The canonicaliser is a supervised call like any other: its own caps,
    its own attribution. A canonicaliser that fails leaves the text
    UNCHANGED and says so -- it never silently returns half a stream,
    which would be compared and called a difference in the subject.
    """
    source = Link()
    await source.feed(text.encode("utf-8"))
    source.close()

    c      = chain([(procsitter, list(pype_argv))],
                   stdin_reader=source.reader)
    record = (await asyncio.gather(*c.task_tuple))[0]
    result = await _read_all(c.tail.reader)

    if record.containment is E_Containment.FAIL_LAUNCH:
        return text, E_TestRunResult.PYPE_INTERPRETER_NOT_FOUND
    if record.containment is E_Containment.FAIL_COMPLETED:
        return text, E_TestRunResult.PYPE_FAILED
    if record.containment is not E_Containment.OK_COMPLETED:
        return text, E_TestRunResult.PYPE_CONTAINED
    return result, E_TestRunResult.OK


@dataclass(frozen=True)
class Subjects:
    """What provision delivered: readers by subject name, and the record
    of how they came to be.

    'raw_db' and 'timing_db' are the material for RECORDING (README 4).
    They are kept only when asked for, since the raw content of a noisy
    run can be large where its cadence never is.
    """
    reader_db: dict
    provision: ProvisionRecord
    raw_db:    dict = None
    timing_db: dict = None

    def __contains__(self, subject_name):
        """RETURN: True, that subject was provided."""
        return subject_name in self.reader_db

    def __getitem__(self, subject_name):
        """RETURN: Nominal, the reader of that subject."""
        return self.reader_db[subject_name]

    def names(self):
        """RETURN: list[str], the provided subject names, sorted."""
        return sorted(self.reader_db)


class BuildStage:
    """THE APPLICATION comes to exist -- once.

    A build stage REMEMBERS its outcome: however many Provisions share
    this instance, the build tool runs a single time. That memo is what
    'build if necessary' means at suite scale. A fresh stage per
    Provision -- the planners' default -- reproduces per-run building
    exactly.

    Reads the source and build keys of the configuration.
    """

    def __init__(self, configuration, observer=None):
        self.configuration = configuration
        self.observer      = observer
        self._outcome      = None
        self._lock         = asyncio.Lock()

    async def supply(self, stop_event=None):
        """
        RETURN: BuildOutcome, the product ('succeeded') or the reason
                ('report'), with the build's own attribution record.

        MEMOIZED behind a lock: a second caller -- even a concurrent
        one -- receives the FIRST call's outcome, never a second build.
        """
        async with self._lock:
            if self._outcome is None:
                self._outcome = await build(self.configuration,
                                            stop_event=stop_event,
                                            observer=self.observer)
            return self._outcome


class ExecuteStage:
    """RAW BEHAVIOR comes to exist: launch, contain, collect -- the
    channels, the output files, and the cadence when asked for.

    Reads the source, place and caps keys of the configuration.
    """

    def __init__(self, configuration, choice_name=None, keep_timing=False):
        self.configuration = configuration
        self.choice_name   = choice_name
        self.keep_timing   = keep_timing

    async def supply(self, stop_event=None):
        """
        RETURN: (dict, list, E_TestRunResult, dict), the raw texts by
                subject name, the attribution records, the report, and
                the cadence by subject name (empty unless asked for).
                (None, list, report, {}), the launch failed: there is
                nothing to canonicalise and nothing to deliver.
        """
        configuration = self.configuration
        procsitter = Procsitter(configuration.caps,
                                work_dir=str(configuration.test_directory))
        error_link = Link()
        c = chain([(procsitter,
                    application_argv(configuration, self.choice_name),
                    {"stderr_handler": error_link.feed})])
        timing_db = {}
        try:
            if self.keep_timing:
                stdout_text, delta_tuple = await _read_all_timed(c.tail.reader)
                timing_db[STDOUT] = delta_tuple
            else:
                stdout_text = await _read_all(c.tail.reader)
            record = (await asyncio.gather(*c.task_tuple))[0]
        finally:
            error_link.close()                 # not an edge: ours to close
        stderr_text = await _read_all(error_link.reader)
        record_list = [record]

        if record.containment is E_Containment.FAIL_LAUNCH:
            return (None, record_list,
                    E_TestRunResult.TEST_APP_LAUNCH_FAILED, {})

        raw_db = {STDOUT: stdout_text, STDERR: stderr_text}
        raw_db.update(self._output_files())

        report    = E_TestRunResult.OK
        if record.containment is E_Containment.FAIL_STALLED:
            report = E_TestRunResult.TEST_APP_STALLED
        elif record.containment is not E_Containment.OK_COMPLETED \
             and record.containment is not E_Containment.FAIL_COMPLETED:
            report = E_TestRunResult.TEST_APP_CONTAINED

        return raw_db, record_list, report, timing_db

    def _output_files(self):
        """
        RETURN: dict, subject name -> text, for every file the run left
                under 'OUT/'. A file subject is named by its file name.
        """
        directory = self.configuration.output_directory
        file_db   = {}
        if not directory.is_dir(): return file_db
        for path in sorted(directory.iterdir()):
            if not path.is_file(): continue
            try:
                file_db[path.name] = path.read_text(encoding="utf-8",
                                                    errors="replace")
            except OSError:
                pass
        return file_db


class CanonicaliseStage:
    """THE SUBJECT comes to exist: each raw stream rewritten by its
    declared pype, comparable after. A stream with no canonicaliser
    declared is comparable raw -- raw IS canonical for it.

    Reads the canonicaliser and caps keys of the configuration.
    """

    def __init__(self, configuration, choice_name=None):
        self.configuration = configuration
        self.choice_name   = choice_name

    async def supply(self, raw_db, report, stop_event=None):
        """
        RETURN: (dict, E_TestRunResult), readers by subject name, and
                the report: the given one or -- only when it was OK --
                the first canonicaliser failure.

        A failing canonicaliser leaves its text UNCHANGED and says so
        ('canonicalise'); the subject is delivered either way.
        """
        configuration = self.configuration
        procsitter = Procsitter(configuration.caps,
                                work_dir=str(configuration.test_directory))
        reader_db = {}
        entry     = configuration.choice_configuration(self.choice_name)
        for name, text in raw_db.items():
            pype_argv = entry.canonicalisers.get(name)
            if pype_argv is not None:
                text, pype_report = await canonicalise(text, pype_argv,
                                                       procsitter)
                if pype_report is not E_TestRunResult.OK \
                   and report is E_TestRunResult.OK:
                    report = pype_report
            reader_db[name] = BytesNominal(text, name=name)
        return reader_db, report


class LoadStage:
    """THE SUBJECT comes to exist from the STORE: what a run recorded,
    read back. Nothing executes, nothing is contained, there is no
    attribution to make -- and NOTHING IS INVENTED: an absent recording
    is REPORTED, never an empty subject that would be compared and
    called a difference.

    Reads the store keys and NONE of the source, build, place or caps
    keys.
    """

    def __init__(self, store, test_name, choice_name=None,
                 subject_name_list=None):
        self.store             = store
        self.test_name         = test_name
        self.choice_name       = choice_name
        self.subject_name_list = subject_name_list

    async def supply(self, stop_event=None):
        """
        RETURN: Subjects, readers over the stored candidates.
        """
        name_list = self.subject_name_list
        if name_list is None:
            name_list = [STDOUT, STDERR]

        reader_db, missing = {}, []
        for name in name_list:
            candidate = self.store.candidate(self.test_name,
                                             self.choice_name, name)
            if not candidate.exists():
                missing.append(name)
                continue
            with candidate.open() as reader:
                reader_db[name] = BytesNominal(reader.read(), name=name)

        if not reader_db:
            return Subjects({}, ProvisionRecord(
                report=E_TestRunResult.RECORDING_MISSING))
        return Subjects(reader_db, ProvisionRecord(report=E_TestRunResult.OK))


class Provision:
    """ONE PROVISION -- its stages as members, None for a stage it does
    not have. Constructed by the planners below ('Run', 'Replay',
    'provision_of'); the invariants live HERE, at construction, where
    the wiring is written.
    """

    def __init__(self, stage_build=None, stage_execute=None,
                 stage_canonicalise=None, stage_load=None,
                 keep_raw=False, observer=None):
        assert (stage_execute is None) != (stage_load is None), \
               "exactly one of stage_execute/stage_load: a provision " \
               "either runs or loads"
        assert stage_build is None or stage_execute is not None, \
               "a build stands only before an execution"
        assert stage_canonicalise is None or stage_execute is not None, \
               "a loaded subject is already canonical"
        self.stage_build        = stage_build
        self.stage_execute      = stage_execute
        self.stage_canonicalise = stage_canonicalise
        self.stage_load         = stage_load
        self.keep_raw           = keep_raw
        self.observer           = observer
        self.kind               = "Replay" if stage_load is not None \
                                  else "Run"
        self.last_provided      = None   # what 'provide()' last produced,
                                         # so a caller may RECORD it
                                         # without provisioning twice

    async def provide(self, stop_event=None):
        """
        RETURN: Subjects, the readers and the record of provision.

        REMEMBERS the product, so a caller that must both compare and
        record does not provision twice -- which for an executing
        provision would mean running the application a second time and
        recording a DIFFERENT execution than the one that was judged.
        """
        self.last_provided = await self._provide(stop_event=stop_event)
        return self.last_provided

    async def _provide(self, stop_event=None):
        """
        RETURN: Subjects, the readers and the record of provision.

        The stages, in their one lawful order: build (if any), execute,
        canonicalise -- or load. The first stage that cannot deliver
        ENDS provision with its token; the stages beyond it never run.
        """
        if self.stage_load is not None:
            return await self.stage_load.supply(stop_event=stop_event)

        record_list = []
        if self.stage_build is not None:
            outcome = await self.stage_build.supply(stop_event=stop_event)
            record_list.append(outcome.record)
            if not outcome.succeeded:
                return Subjects({}, ProvisionRecord(
                    report  = outcome.report,
                    records = tuple(record_list)))

        raw_db, records, report, timing_db = \
            await self.stage_execute.supply(stop_event=stop_event)
        record_list += records
        if raw_db is None:
            return Subjects({}, ProvisionRecord(
                report  = report,
                records = tuple(record_list)))

        reader_db, report = await self.stage_canonicalise.supply(
            raw_db, report, stop_event=stop_event)

        return Subjects(reader_db,
                        ProvisionRecord(report  = report,
                                        records = tuple(record_list)),
                        raw_db    = dict(raw_db) if self.keep_raw else None,
                        timing_db = timing_db
                                    if self.stage_execute.keep_timing
                                    else None)


def Run(configuration, choice_name=None, observer=None,
        keep_raw=False, keep_timing=False):
    """
    RETURN: Provision, wired for EXECUTION: build (COMPILED sources
            only), execute, canonicalise. Reads the source, build,
            place, caps, canonicaliser and store keys of the
            configuration -- and none of the stored-data keys.

    A PLANNER, not a class: it wires stages and hands over the ONE
    Provision kind. Stages are fresh per call; wiring a SHARED stage
    (one build for many choices) is a caller's deliberate act.
    """
    stage_build = BuildStage(configuration, observer=observer) \
                  if configuration.source_kind is E_SourceKind.COMPILED \
                  else None
    return Provision(
        stage_build        = stage_build,
        stage_execute      = ExecuteStage(configuration, choice_name,
                                          keep_timing=keep_timing),
        stage_canonicalise = CanonicaliseStage(configuration, choice_name),
        keep_raw           = keep_raw,
        observer           = observer)


Run.kind = "Run"


def Replay(store, test_name, choice_name=None, subject_name_list=None,
           observer=None):
    """
    RETURN: Provision, wired for LOAD: the recorded subjects, read
            back.

    A PLANNER, not a class -- see 'Run'.
    """
    return Provision(
        stage_load = LoadStage(store, test_name, choice_name,
                               subject_name_list),
        observer   = observer)


Replay.kind = "Replay"


def provision_of(configuration, store, test_name, choice_name, replay,
                 observer=None):
    """
    RETURN: Provision, the one the REQUEST asks for: load when
            'replay', execution otherwise -- with the recording
            appetite (raw, cadence) read from the configuration's
            store keys.

    Provision by execution and by stored data are chosen HERE, once,
    so no operation below ever asks which one it got.
    """
    if replay:
        return Replay(store, test_name, choice_name, observer=observer)
    store_config = configuration.store
    return Run(configuration, choice_name, observer=observer,
               keep_raw    = bool(store_config and store_config.record_raw),
               keep_timing = bool(store_config and store_config.record_timing))
