"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       PROVISION -- how the subjects of a test come to exist.

DESCRIPTION
       ONE PROVISION, FIVE STAGES, ONE FILE PER STAGE. A Provision
       holds its stages as MEMBERS; a member that is None is a stage
       this provision does not have. Absence is DATA -- inspectable,
       reported in the book -- never a null object pretending
       something ran:

           stage_acquire       the world   -> THE DEPENDENCIES
           stage_build         sources     -> THE APPLICATION
           stage_execute       application -> raw streams, fanned out
           stage_canonicalise  raw         -> THE SUBJECT
           stage_load          store       -> THE SUBJECT

       Each stage lives in its own module, 'stage_<name>.py', named
       exactly like the member that holds it. THIS module holds what is
       not a stage: the answer shape ('Supply'), the delivery
       ('Subjects'), the orchestrator ('Provision'), and the planners
       ('Run', 'Replay', 'provision_of').

       EXACTLY ONE PATH. 'stage_execute' and 'stage_load' exclude each
       other; 'stage_acquire', 'stage_build' and 'stage_canonicalise'
       stand only beside 'stage_execute' -- a loaded subject is ALREADY
       canonical, which is why a canonicaliser change demands a re-run,
       and REPLAY IS OFFLINE: a replayed test touches no network, by
       construction. The invariants are checked at construction, where
       the wiring is written.

       EVERY STAGE IS A SUPPLIER, AND EVERY SUPPLIER ANSWERS IN ONE
       SHAPE: 'Supply(product, report, record_list)'. The product is
       the stage's own kind of thing; product None means provision
       cannot continue; the report is one token of the brief
       vocabulary; the records are the attribution. NO STAGE RAISES.
       Provision failure is TEST failure and the suite runs on -- that
       robustness is not built on top of this contract, it is a
       consequence of it (README 2.6). One shape also means a stage is
       free to become a REQUEST to a scheduling component later --
       'supply()' is already a future; only its inside would change.

       SHARING IS INSTANCE IDENTITY. A stage that must not repeat its
       work REMEMBERS it ('StageBuild', 'StageAcquire'): wire the SAME
       instance into every Provision concerned, and the tool builds --
       the world is asked -- once. Sharing is the planner's deliberate
       act, never the stage's.

       EVERY SLOT HAS ITS OWN INTERFACE (provider.py): what fills it is
       anything derived from that role's ABC -- the local stage, or a
       proxy a TestDirectoryOrchestrator plugs. The role is the TYPE,
       and a provider in the wrong slot is REFUSED AT THE DOOR, by
       name, at construction.

       THE PLANNERS ARE FUNCTIONS, NOT CLASSES. 'Run(...)' wires
       execution, 'Replay(...)' wires load, 'provision_of(...)' chooses
       from the request -- the STANDALONE wiring, used when no
       orchestrator plugs. After wiring there is ONE kind of Provision:
       nothing downstream can tell a subject's provenance by type
       (README 2.4). The 'kind' attribute exists for OBSERVATION only,
       and is DECLARED by the planner -- a proxy in the execute slot
       reading a filled sink is mechanically a load, so inference from
       the filled slot would report the wrong thing.

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
from   dataclasses import dataclass
from   pathlib     import Path

from   ..result        import E_TestRunResult
from   ..configuration import E_SourceKind
from   ..report        import Provision as ProvisionRecord
from   .provider       import (I_AcquireProvider, I_BuildProvider,
                               I_ExecuteProvider, I_CanonicaliseProvider,
                               I_LoadProvider)


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


async def read_all(reader):
    """RETURN: str, everything the reader yields, to EOF."""
    chunk_list = []
    while not reader.at_eof():
        data = await reader.read(4096)
        if data: chunk_list.append(data)
    return b"".join(chunk_list).decode("utf-8", errors="replace")


async def read_all_timed(reader):
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


@dataclass(frozen=True)
class Supply:
    """THE ONE ANSWER SHAPE of every stage.

    'product' is the stage's own kind of thing -- an outcome, raw
    streams, readers -- and None when the stage could not deliver, which
    ENDS provision. 'report' is one token of the brief vocabulary; it
    may be a failure token WHILE a product exists (a stalled run still
    delivers its partial streams -- they are canonicalised, compared,
    and the token speaks). 'record_list' is the attribution: one record
    per supervised call the stage made, kept even in failure.
    """
    product:     object
    report:      E_TestRunResult = E_TestRunResult.OK
    record_list: tuple           = ()


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


class Provision:
    """ONE PROVISION -- its stages as members, None for a stage it does
    not have. Constructed by the planners below ('Run', 'Replay',
    'provision_of'); the invariants live HERE, at construction, where
    the wiring is written.
    """

    def __init__(self, stage_acquire=None, stage_build=None,
                 stage_execute=None, stage_canonicalise=None,
                 stage_load=None, keep_raw=False, observer=None,
                 kind=None):
        assert (stage_execute is None) != (stage_load is None), \
               "exactly one of stage_execute/stage_load: a provision " \
               "either runs or loads"
        assert stage_acquire is None or stage_execute is not None, \
               "dependencies are acquired for a RUN -- replay is offline"
        assert stage_build is None or stage_execute is not None, \
               "a build stands only before an execution"
        assert stage_canonicalise is None or stage_execute is not None, \
               "a loaded subject is already canonical"
        #  THE ROLE IS THE TYPE: a provider in the wrong slot is refused
        #  HERE, by name -- never discovered as a wrong product shape
        #  three stages later.
        for slot_name, provider, interface in (
                ("stage_acquire",      stage_acquire,      I_AcquireProvider),
                ("stage_build",        stage_build,        I_BuildProvider),
                ("stage_execute",      stage_execute,      I_ExecuteProvider),
                ("stage_canonicalise", stage_canonicalise,
                                                    I_CanonicaliseProvider),
                ("stage_load",         stage_load,         I_LoadProvider)):
            assert provider is None or isinstance(provider, interface), \
                   "%s requires an %s; received a %s" \
                   % (slot_name, interface.__name__, type(provider).__name__)
        self.stage_acquire      = stage_acquire
        self.stage_build        = stage_build
        self.stage_execute      = stage_execute
        self.stage_canonicalise = stage_canonicalise
        self.stage_load         = stage_load
        self.keep_raw           = keep_raw
        self.observer           = observer
        #  OBSERVATION only, DECLARED by the planner; inferred from the
        #  wiring only where no planner said otherwise.
        self.kind               = kind if kind is not None else \
                                  ("Replay" if stage_load is not None
                                   else "Run")
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

        The stages, in their one lawful order: acquire, build (each if
        any), execute, canonicalise -- or load. Every stage answers in
        the ONE shape, so there is ONE rule: a stage whose product is
        None ENDS provision with its token, and the stages beyond it
        never run.
        """
        if self.stage_load is not None:
            supply = await self.stage_load.supply(stop_event=stop_event)
            return Subjects(supply.product or {},
                            ProvisionRecord(report=supply.report))

        record_list = []

        def failed(supply):
            """RETURN: Subjects, the empty delivery that ends provision
            with 'supply's token and everything attributed so far."""
            return Subjects({}, ProvisionRecord(
                report  = supply.report,
                records = tuple(record_list)))

        #  THE PRE-STAGES: suppliers before the run, in their order.
        for stage in (self.stage_acquire, self.stage_build):
            if stage is None: continue
            supply = await stage.supply(stop_event=stop_event)
            record_list += supply.record_list
            if supply.product is None: return failed(supply)

        executed = await self.stage_execute.supply(stop_event=stop_event)
        record_list += executed.record_list
        if executed.product is None: return failed(executed)
        raw_db, timing_db = executed.product

        canonicalised = await self.stage_canonicalise.supply(
            raw_db, stop_event=stop_event)

        #  THE MERGE OF THE REPORTS is the orchestrator's: the earlier
        #  stage's token speaks over the later one's.
        report = executed.report \
                 if executed.report is not E_TestRunResult.OK \
                 else canonicalised.report

        return Subjects(canonicalised.product,
                        ProvisionRecord(report  = report,
                                        records = tuple(record_list)),
                        raw_db    = dict(raw_db) if self.keep_raw else None,
                        #  the cadence rides IN the delivery: a dict where
                        #  the provider measured, None where it could not
                        #  -- never asked of the provider's person.
                        timing_db = timing_db)


def Run(configuration, choice_name=None, observer=None,
        keep_raw=False, keep_timing=False, stage_acquire=None):
    """
    RETURN: Provision, wired for EXECUTION: acquire (when handed one),
            build (COMPILED sources only), execute, canonicalise. Reads
            the source, build, place, caps, canonicaliser and store
            keys of the configuration -- and none of the stored-data
            keys.

    A PLANNER, not a class: it wires stages and hands over the ONE
    Provision kind. Stages are fresh per call; wiring a SHARED stage
    (one build for many choices, one acquisition for a suite) is a
    caller's deliberate act -- which is why 'stage_acquire' is taken
    READY-MADE: dependencies are suite property, not conjured per test.
    """
    #  Imported lazily: the stage modules import THIS module for the
    #  answer shape, and a planner is the one place that names them --
    #  the same law as 'driver_for' and its drivers (feed.py).
    from .stage_build                                     import StageBuild
    from .stage_execute                                   import StageExecute
    from .stage_canonicalise import \
                                                          StageCanonicalise
    stage_build = StageBuild(configuration, observer=observer) \
                  if configuration.source_kind is E_SourceKind.COMPILED \
                  else None
    return Provision(
        stage_acquire      = stage_acquire,
        stage_build        = stage_build,
        stage_execute      = StageExecute(configuration, choice_name,
                                          keep_timing=keep_timing),
        stage_canonicalise = StageCanonicalise(configuration, choice_name),
        keep_raw           = keep_raw,
        observer           = observer,
        kind               = Run.kind)


Run.kind = "Run"


def Replay(store, test_name, choice_name=None, subject_name_list=None,
           observer=None):
    """
    RETURN: Provision, wired for LOAD: the recorded subjects, read
            back.

    A PLANNER, not a class -- see 'Run'.
    """
    from .stage_load import StageLoad
    return Provision(
        stage_load = StageLoad(store, test_name, choice_name,
                               subject_name_list),
        observer   = observer,
        kind       = Replay.kind)


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
