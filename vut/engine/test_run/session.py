"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE FRONT DOOR -- run this test, this choice, this goal.

DESCRIPTION
       Everything below is assembled here, so nothing above has to know
       that procsitter, compare or a build exist (README 2.2). A caller
       brings a TestConfiguration and a Bookkeeper, and names a GOAL.

       THE CEREMONY of entering a test directory, in order:

           verify      an unservable configuration is refused HERE,
                       before anything runs
           lock        the directory admits ONE live holder
           operate     the goal selects the operation; its sub-processes
                       activate upon need
           record      a Run's subjects are stored as candidates, so
                       Replay has something to read
           book        what happened is entered in the book, overwriting
                       the entry
           unlock      however it ended

       THESE BELONG HERE AND NOT IN THE OPERATIONS. The lock is taken
       when a DIRECTORY is entered, the entry booked when an operation
       FINISHES, the recording done when a Run DELIVERS -- one place
       each, rather than three operations each remembering.
______________________________________________________________________________
"""
from   dataclasses import dataclass, field
from   enum        import Enum
from   typing      import Mapping, Optional, Sequence

from   .result                        import E_TestRunResult
from   .operations.accept             import (Accept, AcceptConfig,
                                              AcceptStep)
from   .configuration                 import (verify,
                                              ConfigurationError)
from   .operations.difference_display import (DifferenceDisplay,
                                              DifferenceDisplayConfig)
from   .operations.equivalence_check  import (EquivalenceCheck,
                                              EquivalenceCheckConfig)
from   .interaction.feed              import (driver_for,
                                              E_DisplayTarget)
from   .provision.core                import provision_of
from   .store                         import (Store,
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
    entry:       Optional[dict]    = None     # the book entry, as written

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


def store_of(configuration, bookkeeper):
    """
    RETURN: Store, where this test's artifacts live -- constructed OVER
            the Bookkeeper.

    THE CONFIGURATION SAYS WHERE, and nobody says it twice: the store's
    own struct names the directory when it wants one elsewhere, and the
    test's own directory serves otherwise. A Bookkeeper handed in over a
    DIFFERENT directory would be a second source of truth, and the two
    could disagree -- refused here, at the door.

    Raises ConfigurationError on that disagreement.
    """
    store_config = configuration.store
    directory    = store_config.directory if store_config is not None \
                                          else configuration.test_directory
    from pathlib import Path
    if Path(bookkeeper.directory) != Path(directory):
        raise ConfigurationError(
            "the configuration says '%s'; the Bookkeeper is over '%s' "
            "-- the configuration says where, and nobody says it twice"
            % (directory, bookkeeper.directory))
    return Store(bookkeeper, store_config)


async def run_test(configuration, request=None, bookkeeper=None):
    """
    RETURN: Outcome, the operation's result and what the ceremony did.

    TWO THINGS: what the test IS, and what is asked OF it. Where its
    artifacts live follows from the first; how to stop it is part of the
    second. The BOOKKEEPER is made ABOVE -- by the orchestrator, from
    the test's directory -- and handed in; nothing here makes its own.

    Raises ConfigurationError if the configuration cannot serve any goal
    or no Bookkeeper is handed in, and DirectoryBusy if a live process
    holds the test directory.
    """
    request = request if request is not None else Request()
    verify(configuration)
    if bookkeeper is None:
        raise ConfigurationError(
            "no Bookkeeper -- it is made above and handed in")
    store = store_of(configuration, bookkeeper)
    with store.lock():
        return await run_test_held(configuration, request, store=store)


async def run_test_held(configuration, request=None, store=None,
                        provision=None, bookkeeper=None):
    """
    RETURN: Outcome, the operation's result and what the ceremony did.

    THE HELD ENTRY: the caller HOLDS the test directory and has verified
    the configuration -- an orchestrator spanning a session locks ONCE
    (the mutex is non-recursive; auxiliary RATIONALE D-2) and enters the
    per-choice ceremony here. 'run_test' is this entry wrapped in its
    own lock: the standalone law, untouched.

    'provision' -- a pre-wired Provision (an orchestrator's plugged
    providers); None: planned by 'provision_of', as ever.
    'store'     -- the holder's Store, already OVER a Bookkeeper; where
    only a 'bookkeeper' is handed in, the Store is made here.

    Raises ConfigurationError if neither a Store nor a Bookkeeper is
    handed in -- the Bookkeeper is made above, never here.
    """
    request = request if request is not None else Request()
    goal, choice_name, observer = request.goal, request.choice, \
                                  request.observer
    subject_name_list = request.subjects
    stop_event        = request.stop_event
    if store is None:
        if bookkeeper is None:
            raise ConfigurationError(
                "no Bookkeeper -- it is made above and handed in")
        store = store_of(configuration, bookkeeper)
    test_name = configuration.stem

    groundwork = provision if provision is not None \
                 else _groundwork(configuration, store, test_name,
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

    entry = store.bookkeeper.record(result, configuration, goal,
                                    choice_name)
    return Outcome(result=result, recorded_db=recorded_db, entry=entry)


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
