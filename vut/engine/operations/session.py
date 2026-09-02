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
                       a loaded read has something to read
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
from ..bookkeeper.api import E_StderrNote

from .consume.accept             import (Accept, AcceptConfig,
                                              AcceptStep)
from   .configuration                 import (verify,
                                              ConfigurationError)
from .consume.difference_display import (DifferenceDisplay,
                                              DifferenceDisplayConfig)
from .consume.equivalence_check  import (EquivalenceCheck,
                                              EquivalenceCheckConfig)
from   .interaction.port              import DisplayAdapter  # noqa: F401 -- the port, not a viewer
from .                        import subject_provision
from   .nominal                       import RecordNominal
from   ..bookkeeper.api               import Store


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
    """WHERE a comparison is shown: an adapter the CALLER constructed.
    The engine never turns a target name into a driver -- the viewers
    are the services' ('services/lib/viewers'), and a face that wants
    one builds it there and hands it in. None: nothing is shown."""
    adapter:     Optional[object]          = None

    def driver(self):
        """
        RETURN: DisplayAdapter, the one to carry this session.
                None,           nothing is to be shown.
        """
        return self.adapter


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
    force_run:   bool              = False  # subject provision (A.1)/
                                            # (B.2) taken as younger:
                                            # execute regardless
    display:     Display           = field(default_factory=Display)
    observer:    Optional[object]  = None
    stderr:      Optional[object]  = None   # E_StderrNote to WRITE at
                                            # an acceptance goal; None:
                                            # not asked -- acceptance
                                            # refuses rather than guess
    record:      Optional[bool]    = None   # None: follow the store config
    stop_event:  Optional[object]  = None   # how the caller stops it


@dataclass(frozen=True)
class Outcome:
    """What the front door produced: the operation's own result, and what
    the ceremony did around it."""
    result:      object                       # TestResult | AcceptResult
    recorded_db: Mapping[str, str] = None
    entry:       Optional[dict]    = None     # the book entry, as written
    coverage:    object            = None     # E_CoverageResult; None
                                              # where none was asked

    @property
    def verdict(self):
        """RETURN: bool, the operation's verdict."""
        return self.result.verdict

    @property
    def report(self):
        """RETURN: E_TestRunResult, the operation's report."""
        return self.result.report


def _nominal_db(store, test_name, choice_name, subject_name_list):
    """
    RETURN: dict, subject name -> Nominal, read from the store.

    Every named subject gets a Nominal whether or not a record exists:
    absence is reported by the operation that tried to read it, not
    guessed at here.
    """
    return {name: RecordNominal(store.nominal_path(test_name,
                                                   choice_name, name))
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
                        provision=None, bookkeeper=None, run_id=None):
    """
    RETURN: Outcome, the operation's result and what the ceremony did.

    'run_id' -- the register's id of this run, where coverage is asked:
    the harvested record is seated with it (coverage D-18). Coverage
    asked and no run id handed in is a fault of the caller: a record
    nobody can attribute is not written.

    THE HELD ENTRY: the caller HOLDS the test directory and has verified
    the configuration -- an orchestrator spanning a session locks ONCE
    (the mutex is non-recursive; auxiliary RATIONALE D-2) and enters the
    per-choice ceremony here. 'run_test' is this entry wrapped in its
    own lock: the standalone law, untouched.

    'provision' -- a pre-wired Provision (an orchestrator's plugged
    providers); None: the channel's ('subject_provision.provider_of').
    'store'     -- the holder's Store, already OVER a Bookkeeper; where
    only a 'bookkeeper' is handed in, the Store is made here.

    Raises ConfigurationError if neither a Store nor a Bookkeeper is
    handed in -- the Bookkeeper is made above, never here.
    """
    request = request if request is not None else Request()
    goal, choice_name, observer = request.goal, request.choice, \
                                  request.observer
    #  SUBJECTS ARE THE TEST'S DESIGN ('output', todo-1): the choice's
    #  declaration governs; the request's default, ('stdout',), stands
    #  only where the author declared nothing. An EXPLICIT request
    #  still speaks -- a caller that names subjects has a reason.
    subject_name_list = request.subjects
    if subject_name_list == ("stdout",):
        declared = configuration.choice_db.get(choice_name)
        if declared is not None \
           and getattr(declared, "output", None) is not None:
            subject_name_list = tuple(declared.output)
    stop_event        = request.stop_event
    if store is None:
        if bookkeeper is None:
            raise ConfigurationError(
                "no Bookkeeper -- it is made above and handed in")
        store = store_of(configuration, bookkeeper)
    test_name = configuration.key_name

    #  THE ONE CHANNEL (subject_provision): decides execute-or-load and
    #  hands back the provider; 'replay' is its 'production=False'.
    if provision is not None: groundwork = provision
    else:
        #  THE DECLARED SUBJECTS ARE WHAT A LOADED PROVIDER READS BACK:
        #  a declared file ('output = ["<stdout>", "result.csv"]') is a
        #  recorded candidate like stdout, and a read-back of the
        #  standard pair alone would report it missing (E-41, found).
        groundwork, _ = subject_provision.provider_of(
                            configuration, store, choice_name,
                            production = not request.replay,
                            force_run  = request.force_run,
                            observer   = observer,
                            subject_name_list = tuple(subject_name_list)
                                                + (("stderr",)
                                                   if "stderr" not in
                                                      subject_name_list
                                                   else ()))
    if goal is E_Goal.NOMINAL:
        result = await Accept(
            AcceptConfig(name       = test_name,
                         subjects   = {n: AcceptStep()
                                       for n in subject_name_list},
                         choice     = choice_name,
                         groundwork = groundwork,
                         stderr     = request.stderr),
            store, observer=observer).run(stop_event=stop_event)
        recorded_db = None
    else:
        #  STDERR IS NEVER SUBJECT TO TESTING (E-5): the note governs
        #  only whether a spoken word is an ERROR ('forbidden') or
        #  disregarded ('ignored'); it is never compared like a
        #  subject, so it never enters 'judged_list'.
        note        = store.stderr_note(test_name, choice_name)
        judged_list = list(subject_name_list)
        if "stderr" in judged_list: judged_list.remove("stderr")
        nominal_db = _nominal_db(store, test_name, choice_name,
                                 judged_list)
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
                    name          = test_name,
                    groundwork    = groundwork,
                    subjects      = nominal_db,
                    stderr_forbidden_f = (note is E_StderrNote.FORBIDDEN),
                    compare    = _compare_options(configuration,
                                                  choice_name)),
                observer=observer)
        result      = await operation.run(stop_event=stop_event)
        recorded_db = subject_provision.record(store, configuration,
                                               choice_name, groundwork,
                                               request.record)

    coverage = None
    if configuration.coverage is not None and not request.replay:
        #  THE HARVEST is the run's closing act (coverage D-19): the
        #  application has ended, the artefacts stand, the run id is
        #  known. A replay executed nothing and harvests nothing.
        assert run_id is not None, \
               "coverage asked and no run id handed in: the record " \
               "could not be attributed"
        from .coverage_action import harvest
        coverage = await harvest(configuration, store.bookkeeper,
                                 test_name, choice_name, run_id,
                                 result.report)
    #  A DISPLAY DOES NOT RECORD (B-7): a viewing is not a run of
    #  record, and must not write a verdict into the book.
    entry = None
    if goal is not E_Goal.DISPLAY:
        entry = store.bookkeeper.record(result, configuration, goal,
                                        choice_name, coverage=coverage)
    return Outcome(result=result, recorded_db=recorded_db, entry=entry,
                   coverage=coverage)


def _compare_options(configuration, choice_name):
    """
    RETURN: the choice's compare setup, or None when it declares none.

    Raises KeyError if the choice is not in the database -- a caller
    asking for a scenario that was never described is a fault, not a
    default.
    """
    return configuration.choice_configuration(choice_name).compare
