"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE
       SUBJECT PROVISION -- the ONE place a subject stream is obtained,
       with the UPDATE CHECK inside it (operations disc-2, ruled
       2026-08-31). Every face that needs a subject -- run, accept,
       report, merge -- comes through 'decide()' and takes what it
       says; none performs a freshness check of its own.
DESCRIPTION
       The procedure, as ruled, and IN THIS ORDER:

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
