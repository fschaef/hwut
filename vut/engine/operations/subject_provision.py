"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE
       SUBJECT PROVISION -- THE ONE CHANNEL through which a subject
       stream is obtained, with the UPDATE CHECK inside it (operations
       disc-2, ruled 2026-08-31; the channel made whole 2026-09-02).
       Every face and every component that needs a subject -- run,
       accept, play, merge, stability, report -- calls 'provider_of()'
       and takes what it hands back; none decides, executes, loads or
       records on its own.
DESCRIPTION
       THREE VERBS, ONE PLACE:

         decide()       what is to happen for one (test, choice):
                        execute, or read the recording back
         provider_of()  the decision MADE INTO A WIRING: a Provision
                        that executes, or a Loaded that reads back --
                        both answer 'provide()' with the one 'Subjects'
                        shape, so nothing above ever asks which
         record()       what an EXECUTING provider produced, written
                        as the candidate; a Loaded provider records
                        nothing, since it would write back what it
                        just read

       THE DECISION, as ruled, and IN THIS ORDER:

         (0)   no subject stream recorded            -> PROVIDE
         (A)   the application is INTERPRETED (configuration.build is
               None)
         (A.1) its source, or any code it declares it covers, is
               younger than the recorded subject     -> RE-RUN
         (A.2) otherwise                              -> the RECORDED
                                                        stream
         (B)   the application is BUILT
         (B.1) build it -- the plan's BUILD node does, and the build
               TOOL decides whether anything is out of date (disc-2
               f-2: provision does not second-guess 'make');
               'force_build' says: build regardless
         (B.2) the built application is younger than the recorded
               subject                               -> RE-RUN
               otherwise                             -> the RECORDED
                                                        stream

       'production=False' (disc-2 f-4) means the caller may never
       cause an execution: a report is a report of what happened. Then
       (0) answers ABSENT, and (A.1)/(B.2) answer STALE -- the recorded
       stream is still delivered, and the caller is told it is stale,
       so 'hwut.report' can say "this is what the PREVIOUS text
       printed" rather than presenting it as current.

       'force_run=True' is the opposite word: (A.1)/(B.2) are taken as
       younger. 'hwut.play' says it, since a play IS the request to
       execute now.

       NO CONFIGURATION IN HAND ('configuration=None'): a face that has
       only a directory and a file name -- 'hwut.merge', 'hwut.
       stability' -- gets the (A) closure of THAT FILE ALONE and can
       only READ: the channel refuses to execute what it cannot
       describe. This is the one place that fallback is written.

       MTIME, NOT CONTENT (disc-2 f-3): a test whose text changed and
       whose output did not must still re-run, because the store's
       business is what THIS text produced. THE CLOSURE OF (A.1) is
       the application and what it declares it covers ('coverage_
       target', R-73), and no wider (disc-2 f-1): 'hwut.conf' changes
       every test in the directory and is 'hwut.run's to notice.
______________________________________________________________________________
"""
import os
from   enum        import Enum
from   dataclasses import dataclass
from   pathlib     import Path

from   .result     import E_TestRunResult


class E_Decision(Enum):
    """What subject provision decided, before anything is read or run."""
    PROVIDE  = "provide"     # (0) nothing recorded, or (A.1)/(B.2)
                             # younger: execute, then deliver
    RECORDED = "recorded"    # the recorded stream, and it is current
    STALE    = "stale"       # production=False and the recording is
                             # older than its source: delivered, with
                             # this word beside it
    ABSENT   = "absent"      # production=False and nothing recorded


@dataclass(frozen=True)
class Decision:
    """
    'what'    the E_Decision.
    'because' one line a face may print verbatim -- the step that
              decided, and the file that made it so.
    """
    what:    E_Decision
    because: str


def _mtime(path):
    """
    RETURN: float, the file's mtime
            None, where it cannot be stat'ed -- an unreadable clock
            accuses nobody (disc-2 f-3).
    """
    try:               return os.stat(str(path)).st_mtime
    except OSError:    return None


def _younger_than(path_list, than_path):
    """
    RETURN: str, the FIRST path in 'path_list' whose mtime is younger
                 than 'than_path's
            None, where none is, or 'than_path' cannot be stat'ed.
    """
    reference = _mtime(than_path)
    if reference is None: return None
    for path in path_list:
        stamp = _mtime(path)
        if stamp is not None and stamp > reference: return str(path)
    return None


def decide(configuration, candidate_path, built_path=None,
           production=True, force_run=False, force_build=False,
           source_directory=None):
    """
    RETURN: Decision, what provision does for this (test, choice) --
            see the module header for the steps, which this function
            walks in their ruled order and NOWHERE ELSE.

    'configuration'   the test's; '.build' None for interpreted,
                      '.source_file' the application, '.coverage_
                      target_list' (may be absent) what it covers.
    'candidate_path'  where the recorded subject stands (the Book's
                      'candidate_path'); may not exist.
    'built_path'      the built application, for (B); None where the
                      plan has not built it.
    'production'      False: never PROVIDE; answer STALE/ABSENT instead.
    'force_run'       True: (A.1)/(B.2) are taken as younger.
    'force_build'     True: passed on to whoever builds; recorded here
                      in the reason so the face can say so.

    'source_directory' anchors every RELATIVE path of the closure --
    the source file and the coverage targets are named relative to
    their own directory, and the process's cwd is no coordinate
    system. Absolute paths pass through; None leaves relative paths
    as they stand (a caller whose cwd IS the directory).

    No file is read here, only stat'ed. The caller executes on PROVIDE
    ('Provision.provide()') and loads on RECORDED/STALE
    ('consume/loaded.py'); this function is the ONE that says which.
    """
    def anchored(path):
        """RETURN: str, 'path' resolved against 'source_directory'
        where it is relative and an anchor was given; verbatim else."""
        if source_directory is None or os.path.isabs(str(path)):
            return str(path)
        return os.path.join(str(source_directory), str(path))

    source_path = anchored(configuration.source_file)

    #  (0)  NOTHING RECORDED.
    if _mtime(candidate_path) is None:
        if not production:
            return Decision(E_Decision.ABSENT,
                            "(0) nothing recorded for this choice")
        return Decision(E_Decision.PROVIDE,
                        "(0) nothing recorded for this choice")

    if configuration.build is None:
        #  (A)  INTERPRETED.
        closure = [source_path]
        closure += [anchored(p) for p in
                    (getattr(configuration, "coverage_target_list",
                             ()) or ())]
        #  (A.1)  SOURCE OR COVERED CODE YOUNGER THAN THE RECORDING.
        younger = "forced" if force_run \
                  else _younger_than(closure, candidate_path)
        if younger is not None:
            because = "(A.1) '%s' is younger than the recording" % younger
            if not production: return Decision(E_Decision.STALE, because)
            return Decision(E_Decision.PROVIDE, because)
        #  (A.2)  THE RECORDED STREAM IS CURRENT.
        return Decision(E_Decision.RECORDED,
                        "(A.2) the recording is current")

    #  (B)  BUILT.
    #  (B.1)  THE BUILD is the plan's BUILD node; the build TOOL
    #         decides freshness. Provision only records that a forced
    #         build was asked for, so the reason can say so.
    forced = " (force_build)" if force_build else ""
    if built_path is None or _mtime(built_path) is None:
        because = "(B.1) the application is not built%s" % forced
        if not production: return Decision(E_Decision.ABSENT, because)
        return Decision(E_Decision.PROVIDE, because)
    #  (B.2)  BUILT APPLICATION YOUNGER THAN THE RECORDING.
    younger = "forced" if force_run \
              else _younger_than([built_path], candidate_path)
    if younger is not None:
        because = "(B.2) the built application is younger than the " \
                  "recording%s" % forced
        if not production: return Decision(E_Decision.STALE, because)
        return Decision(E_Decision.PROVIDE, because)
    return Decision(E_Decision.RECORDED,
                    "(B.2) the recording is current")


#  ---------------------------------------------------------------------------
#  THE WIRING HALF: the decision made into a provider, and its recording.
#  ---------------------------------------------------------------------------

class Loaded:
    """THE RECORDED-STREAM BRANCH of provision: 'provide()' answers the
    stored candidates read back ('consume/loaded.py'); 'last_provided'
    remembers them, the same bargain as an executing Provision's, so a
    caller that compares and records reads once. It has no
    'stage_execute': that absence is how 'record()' knows there is
    nothing to write back."""

    kind = "Loaded"

    def __init__(self, store, test_name, choice_name=None,
                 subject_name_list=None):
        self.store             = store
        self.test_name         = test_name
        self.choice_name       = choice_name
        self.subject_name_list = subject_name_list
        self.last_provided     = None

    async def provide(self, stop_event=None):
        """RETURN: Subjects, the recorded candidates, read back."""
        from .consume.loaded import loaded
        self.last_provided = loaded(self.store, self.test_name,
                                    self.choice_name,
                                    self.subject_name_list)
        return self.last_provided


class _BareConfiguration:
    """The (A) closure of ONE FILE, for a caller with no configuration
    in hand. Interpreted, covers nothing, keyed by its own name."""

    build                = None
    coverage_target_list = ()
    store                = None

    def __init__(self, directory, source_file):
        self.test_directory = str(directory)
        self.source_file    = source_file
        self.key_name       = source_file


def provider_of(configuration, store, choice_name=None, production=True,
                force_run=False, force_build=False, observer=None,
                keep_raw=None, subject_name_list=None, built_path=None):
    """
    RETURN: [0] Provision | Loaded, THE PROVIDER: answers 'provide()'
                with 'Subjects' and remembers them as 'last_provided'.
                A Provision EXECUTES (build, launch, contain, collect,
                canonicalise); a Loaded reads the recording back.
            [1] Decision, the ruled step that chose, with its reason --
                a face may print 'because' verbatim.

    'configuration'      the test's ('key_name' is the test); None: a
                         bare closure over 'store.directory/test_name'
                         -- then 'test_name' MUST be given, and only a
                         Loaded is ever returned.
    'store'              the Store over the test's Bookkeeper: the
                         candidate paths and the directory.
    'production'         False: never execute; STALE/ABSENT still hand
                         back a Loaded, and the decision says so.
    'force_run'          True: execute regardless of the clocks.
    'keep_raw'           None: as the store's 'record_raw' says; True
                         asks for the raw streams whatever it says
                         ('hwut.play' shows them).
    'subject_name_list'  for a Loaded: which subjects to read back;
                         None means the standard pair.

    Raises ValueError where 'configuration' is None and 'test_name'
    cannot be known.
    """
    test_name = configuration.key_name if configuration is not None \
                else None
    if test_name is None:
        raise ValueError("provider_of: no configuration and no test "
                         "name -- nothing to provide for")
    candidate = store.candidate_path(test_name, choice_name, "stdout")
    #  THE SOURCE IS NAMED RELATIVE TO ITS OWN DIRECTORY, and the
    #  process's cwd is nobody's coordinate system: resolve against the
    #  book's directory, which IS the test's, before any clock is read
    #  -- a mis-anchored stat reads as 'no clock' and would silently
    #  call every recording current.
    decision = decide(configuration, candidate, built_path=built_path,
                      production=production, force_run=force_run,
                      force_build=force_build,
                      source_directory=store.directory)
    if decision.what is not E_Decision.PROVIDE:
        return Loaded(store, test_name, choice_name,
                      subject_name_list), decision
    from .run.core import provision_of
    provision = provision_of(configuration, choice_name, observer=observer)
    if keep_raw is not None: provision.keep_raw = keep_raw
    return provision, decision


def bare_provider_of(store, test_name, choice_name=None,
                     subject_name_list=None):
    """
    RETURN: [0] Loaded, a reader of the recording -- never an executor:
                without a configuration nothing can be run.
            [1] Decision, RECORDED, STALE or ABSENT for the (A) closure
                of the file alone.

    The one road for a face that holds a directory and a name and no
    configuration ('hwut.merge', 'hwut.stability').
    """
    configuration = _BareConfiguration(store.directory, test_name)
    return provider_of(configuration, store, choice_name,
                       production=False,
                       subject_name_list=subject_name_list)


def record(store, configuration, choice_name, provider, wanted=None):
    """
    RETURN: dict, subject name -> the text stored as its candidate.
            None, nothing was recorded: a Loaded provider (it would
            write back what it just read), a provision whose report is
            not OK (a partial subject is never stored as if whole --
            the abort is the outcome's to tell), nothing provided yet,
            or the store knob says no.

    'wanted' is THE STORE KNOB: None follows the configuration ('store'
    declared); a face's '--no-store' or '--save' is a later word over
    it. The raw stream and the cadence ride along where the provider
    kept them.
    """
    if getattr(provider, "stage_execute", None) is None: return None
    if wanted is None: wanted = configuration.store is not None
    if not wanted:                                       return None
    #  THE RAW STREAM IS KEPT ON THE STORE'S WORD ('record_raw') and
    #  not on the provider's appetite: 'hwut.play' asks for raw to
    #  SHOW it, and its '--save' must store what a run would store.
    raw_f = bool(configuration.store and configuration.store.record_raw)
    provided = getattr(provider, "last_provided", None)
    if provided is None:                                 return None
    if provided.provision.report is not E_TestRunResult.OK:
        return None
    from ..bookkeeper.api import source_digest_of
    test_name     = configuration.key_name
    source_digest = source_digest_of(
        Path(configuration.test_directory) / configuration.source_file)
    recorded_db = {}
    for name in provided.names():
        with provided[name].open() as reader:
            text = reader.read()
        store.write_candidate(test_name, choice_name, name, text,
                              source_digest=source_digest)
        recorded_db[name] = text
        if raw_f and provided.raw_db and name in provided.raw_db:
            store.write_raw(test_name, choice_name, name,
                            provided.raw_db[name])
        if provided.timing_db and name in provided.timing_db:
            store.write_timing(test_name, choice_name, name,
                               provided.timing_db[name])
    return recorded_db
