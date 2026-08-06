"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE FRONT DOOR -- run this test, this choice, this goal.

DESCRIPTION
       Everything below is assembled here, so nothing above has to know
       that procsitter, compare or a build exist (README 2.2). A caller
       brings a TestConfiguration and a Store, and names a GOAL.

       THE CEREMONY of entering a test directory, in order:

           verify      an unservable configuration is refused HERE,
                       before anything runs
           lock        the directory admits ONE live holder
           operate     the goal selects the operation; its sub-processes
                       activate upon need
           record      a Run's subjects are stored as candidates, so
                       Replay has something to read
           footprint   what happened is written, overwriting the entry
           unlock      however it ended

       THESE BELONG HERE AND NOT IN THE OPERATIONS. The lock is taken
       when a DIRECTORY is entered, the footprint written when an
       operation FINISHES, the recording done when a Run DELIVERS -- one
       place each, rather than three operations each remembering.
______________________________________________________________________________
"""
from   dataclasses import dataclass, field
from   enum        import Enum
from   typing      import Mapping, Optional, Sequence

from   vut.engine.test_run.result           import E_TestRunResult
from   vut.engine.test_run.operations.accept import (Accept, AcceptConfig,
                                                     AcceptStep)
from   vut.engine.test_run.configuration     import verify
from   vut.engine.test_run.operations.difference_display import (DifferenceDisplay,
                                                                 DifferenceDisplayConfig)
from   vut.engine.test_run.operations.equivalence_check import (EquivalenceCheck,
                                                                EquivalenceCheckConfig)
from   vut.engine.test_run.interaction.feed  import (driver_for,
                                                     E_DisplayTarget)
from   vut.engine.test_run.provision.core    import provision_of
from   vut.engine.test_run.store             import (Store,
                                                     DirectoryBusy)


class E_Goal(Enum):
    """WHAT IS ASKED FOR. The goal selects the operation; it is not the
    operation's name, because a caller asks for an outcome."""
    VERDICT = "verdict"    # did this test pass?
    DISPLAY = "display"    # show me what differs
    NOMINAL = "nominal"    # accept what it produces

    def __str__(self):
        """RETURN: str, the goal's token."""
        return self.value


@dataclass(frozen=True)
class Display:
    """WHERE a comparison is shown. A target names a driver; an adapter
    handed in directly WINS, because a caller that built its own driver
    has said exactly what it wants."""
    target:      Optional[E_DisplayTarget] = None
    adapter:     Optional[object]          = None
    argument_db: Mapping[str, object]      = field(default_factory=dict)

    def driver(self):
        """
        RETURN: DisplayAdapter, the one to carry this session.
                None,           nothing is to be shown.
        """
        if self.adapter is not None: return self.adapter
        if self.target  is None:     return None
        return driver_for(self.target, **dict(self.argument_db))


@dataclass(frozen=True)
class Request:
    """WHAT IS ASKED FOR, NOW -- the fourth thing beside the test's
    design, its artifacts, and the products in flight (README 2.7).

    A configuration says what the test IS and does not change between
    runs. A request says what is wanted OF it this time, and changes
    every time. Keeping them apart is why neither grows fields belonging
    to the other.
    """
    goal:        E_Goal            = E_Goal.VERDICT
    choice:      Optional[str]     = None
    subjects:    Sequence[str]     = ("stdout",)
    replay:      bool              = False
    display:     Display           = field(default_factory=Display)
    observer:    Optional[object]  = None
    record:      Optional[bool]    = None   # None: follow the store config
    stop_event:  Optional[object]  = None   # how the caller stops it


@dataclass(frozen=True)
class Outcome:
    """What the front door produced: the operation's own result, and what
    the ceremony did around it."""
    result:      object                       # TestResult | AcceptResult
    recorded_db: Mapping[str, str] = None
    footprint:   Optional[dict]    = None

    @property
    def verdict(self):
        """RETURN: bool, the operation's verdict."""
        return self.result.verdict

    @property
    def report(self):
        """RETURN: E_TestRunResult, the operation's report."""
        return self.result.report


def _groundwork(configuration, store, test_name, choice_name, replay,
                observer):
    """
    RETURN: Provision, the one the goal will read from -- planned by
            'provision_of', where run-vs-replay is decided once.
    """
    return provision_of(configuration, store, test_name, choice_name,
                        replay, observer=observer)


def _nominal_db(store, test_name, choice_name, subject_name_list):
    """
    RETURN: dict, subject name -> Nominal, read from the store.

    Every named subject gets a Nominal whether or not a record exists:
    absence is reported by the operation that tried to read it, not
    guessed at here.
    """
    return {name: store.nominal(test_name, choice_name, name)
            for name in subject_name_list}


def store_of(configuration):
    """
    RETURN: Store, where this test's artifacts live.

    THE CONFIGURATION SAYS WHERE, and nobody says it twice: the store's
    own struct names the directory when it wants one elsewhere, and the
    test's own directory serves otherwise. A store handed in beside a
    configuration that already declares one would be a second source of
    truth, and the two could disagree.
    """
    store_config = configuration.store
    directory    = store_config.directory if store_config is not None \
                                          else configuration.test_directory
    return Store(directory, store_config)


async def run_test(configuration, request=None):
    """
    RETURN: Outcome, the operation's result and what the ceremony did.

    TWO THINGS: what the test IS, and what is asked OF it. Where its
    artifacts live follows from the first; how to stop it is part of the
    second.

    Raises ConfigurationError if the configuration cannot serve any goal,
    and DirectoryBusy if a live process holds the test directory.
    """
    request = request if request is not None else Request()
    goal, choice_name, observer = request.goal, request.choice, \
                                  request.observer
    subject_name_list = request.subjects
    stop_event        = request.stop_event
    verify(configuration)
    store     = store_of(configuration)
    test_name = configuration.stem

    with store.lock():
        groundwork = _groundwork(configuration, store, test_name,
                                 choice_name, request.replay, observer)
        if goal is E_Goal.NOMINAL:
            result = await Accept(
                AcceptConfig(name       = test_name,
                             subjects   = {n: AcceptStep()
                                           for n in subject_name_list},
                             choice     = choice_name,
                             groundwork = groundwork),
                store, observer=observer).run(stop_event=stop_event)
            recorded_db = None
        else:
            nominal_db = _nominal_db(store, test_name, choice_name,
                                     subject_name_list)
            if goal is E_Goal.DISPLAY:
                operation = DifferenceDisplay(
                    DifferenceDisplayConfig(
                        name       = test_name,
                        groundwork = groundwork,
                        subjects   = nominal_db,
                        compare    = _compare_options(configuration,
                                                      choice_name),
                        adapter    = request.display.driver()),
                    observer=observer)
            else:
                operation = EquivalenceCheck(
                    EquivalenceCheckConfig(
                        name       = test_name,
                        groundwork = groundwork,
                        subjects   = nominal_db,
                        compare    = _compare_options(configuration,
                                                      choice_name)),
                    observer=observer)
            result      = await operation.run(stop_event=stop_event)
            recorded_db = await _record(store, configuration, test_name,
                                        choice_name, groundwork,
                                        request.record)

        footprint = _write_footprint(store, test_name, choice_name, goal,
                                     result, configuration)
        return Outcome(result=result, recorded_db=recorded_db,
                       footprint=footprint)


def _compare_options(configuration, choice_name):
    """
    RETURN: the choice's compare setup, or None when it declares none.

    Raises KeyError if the choice is not in the database -- a caller
    asking for a scenario that was never described is a fault, not a
    default.
    """
    return configuration.choice_configuration(choice_name).compare


async def _record(store, configuration, test_name, choice_name, groundwork,
                  record):
    """
    RETURN: dict, subject name -> what was stored as a candidate.
            None, nothing was recorded.

    A Replay records nothing: it would write back what it just read.
    """
    if groundwork.stage_load is not None:         return None
    wanted = record if record is not None else (configuration.store is not None)
    if not wanted:                                return None

    provided = getattr(groundwork, "last_provided", None)
    if provided is None:                          return None
    recorded_db = {}
    for name in provided.names():
        with provided[name].open() as reader:
            text = reader.read()
        store.write_candidate(test_name, choice_name, name, text)
        recorded_db[name] = text
        if provided.raw_db and name in provided.raw_db:
            store.write_raw(test_name, choice_name, name,
                            provided.raw_db[name])
        if provided.timing_db and name in provided.timing_db:
            store.write_timing(test_name, choice_name, name,
                               provided.timing_db[name])
    return recorded_db


def compare_setup_delta(options):
    """
    RETURN: dict, every compare setting that DIFFERS from the default.
            {},   the setup is compare's default throughout.

    ONLY THE DIFFERENCES. A default setup adds nothing to a footprint,
    and recording the whole of compare's Configuration would make every
    footprint grow whenever compare gained an option. What is worth
    keeping is what somebody CHOSE.

    Nothing here names a tolerance: the walk is over whatever compare
    declares, so a tolerance compare has not invented yet is recorded
    the day it is used.
    """
    if options is None: return {}
    from vut.engine.compare.configuration import Configuration
    default    = Configuration()
    difference = {}

    for name in getattr(Configuration, "__slots__", ()):
        chosen = getattr(options, name, None)
        plain  = getattr(default, name, None)
        if name == "pattern_finder":
            for field_name in vars(plain):
                a = getattr(chosen, field_name, None)
                b = getattr(plain,  field_name, None)
                if a != b: difference[field_name] = _plain(a)
            #  an option compare added but the default object lacks
            for field_name in vars(chosen):
                if field_name not in vars(plain):
                    difference[field_name] = _plain(getattr(chosen,
                                                            field_name))
            continue
        if chosen != plain:
            difference[name] = _plain(chosen)
    return difference


def _plain(value):
    """
    RETURN: the value if JSON can carry it; its repr otherwise.

    A footprint is read by anything, so nothing Python-shaped may reach
    it.
    """
    if isinstance(value, (str, int, float, bool, type(None))): return value
    if isinstance(value, (list, tuple)):  return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    return repr(value)


def _write_footprint(store, test_name, choice_name, goal, result,
                     configuration):
    """
    RETURN: dict, the footprint entry as written.

    The CANONICALISER is recorded with it: a record is history, and
    without knowing which canonicaliser produced it, a later Replay
    cannot tell that it is comparing two different freeings.
    """
    entry = configuration.choice_configuration(choice_name)
    fact_db = {"verdict": bool(result.verdict),
               "report":  str(result.report)}
    if entry.canonicalisers:
        fact_db["canonicaliser"] = {name: list(argv) for name, argv
                                    in entry.canonicalisers.items()}
    #  BOTH HALVES OF FREEING, or a later reader cannot tell what this
    #  verdict meant: the canonicaliser changed the RECORD, the compare
    #  setup changed the VERDICT.
    setup = compare_setup_delta(entry.compare)
    if setup:
        fact_db["compare"] = setup
    return store.write_footprint(test_name, choice_name,
                                 _OPERATION_NAME[goal], **fact_db)


_OPERATION_NAME = {E_Goal.VERDICT: "Run",
                   E_Goal.DISPLAY: "Display",
                   E_Goal.NOMINAL: "Accept"}
