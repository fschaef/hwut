"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE TWO ROLES OF A COVERAGE TOOL -- the FRAMEWORK that is
         invoked and the FORMAT that is read -- and the registry that
         finds a framework by its tool's name (RATIONALE D-23).

DESCRIPTION
       CCoverageFramework      one per TOOL: gcov, coverage.py, jacoco
           wrap(argv)          the tool's own call form -- THE one place
                               a language's coverage tool is named
           report_argv()       the SECOND supervised call, where the tool
                               needs one to turn its raw data into
                               something readable ('coverage json',
                               'gcov'); None where it does not
           instrumented_f()    OPTIONAL: does the built target carry the
                               instrumentation; None where the tool
                               leaves nothing to check
           format              the CCoverageFormat it writes
           harvest()           'format.read', the tool's name stamped

       CCoverageFormat         one per ARTEFACT FORMAT: lcov tracefile,
           read(directory)     cobertura xml, gcov annotated source ->
                               a CoverageRecord, its tool left empty

       TWO CLASSES BECAUSE THE TWO ARE TWO FACTS (D-7): several tools
       write one format (c8, gcovr, cargo-llvm-cov all write LCOV), and
       the record names both the tool that ran and the format it wrote.
       Admitting a tool that writes a known format is one framework
       subclass naming that format; admitting a new format is one
       format subclass.

       WHY A SECOND CALL EXISTS. Most coverage tools leave BINARY state,
       not a report: coverage.py leaves a '.coverage' database, gcc
       leaves '.gcda' counters. Turning either into text is itself a
       PROCESS, and every process HWUT runs goes through the procsitter
       (procsitter MANUAL, rule of thumb 1). So the framework NAMES the
       call and the execute stage MAKES it -- a framework spawns nothing.

       NEITHER ROLE renders, judges, or decides whether coverage was
       wanted; neither re-derives what the store already holds.

       PATHS ARE MADE RELATIVE TO THE TEST DIRECTORY by the format, at
       the moment it knows both -- the one point where the absolute path
       the tool emitted is still available and can be discarded for good
       (RATIONALE D-4).

       THE GATHER SET, TWICE. 'include'/'omit' are a GATHERING knob
       (D-3). A tool that takes them gets them in 'wrap'; a tool that
       does not gets them applied at READ instead. Either way the same
       globs decide, and neither is a reporting filter.

       A FRAMEWORK NEED NOT redirect its artefact per run and MAY NOT
       assume it is alone across directories -- only within one: under
       coverage the dispatcher runs one test at a time per directory
       and empties 'OUT/COVERAGE' before each (D-22).

       IMPORTING THIS MODULE REGISTERS NOTHING. The implementations live
       in 'readers/'; 'framework_of' imports that package on its first
       miss, so a caller that never elects a tool never pays for any of
       them.
______________________________________________________________________________
"""
import os
from abc import ABC, abstractmethod
from fnmatch import fnmatch

from .configuration import CoverageRefused
from .record        import CoverageRecord, FileCoverage, ranges_of


ARTIFACT_DIRECTORY = "OUT/COVERAGE"


class CCoverageFormat(ABC):
    """THE ARTEFACT'S SHAPE -- one per format, whoever wrote it.

    'name' lands in the record's header as 'format' (RATIONALE D-7).
    A format knows how to READ; it knows nothing of the tool that ran,
    and stamps no tool into the record -- the framework does (D-23).
    """
    name = None

    @abstractmethod
    def read(self, work_dir, source_root, config=None):
        """
        RETURN: CoverageRecord, read from the artefact under
                'work_dir/OUT/COVERAGE', its 'tool' left EMPTY for the
                framework to stamp.
                None, where no artefact stands -- ABSENT, which is not
                the same as an empty measurement and must not be
                reported as one.

        'source_root' is the TEST DIRECTORY: every path in the record is
        made relative to it here. 'config' is the CoverageConfig, so
        that a format whose tool could not apply the gather set can
        apply it itself.
        """


class CCoverageFramework(ABC):
    """THE TOOL -- one per coverage framework: how it is INVOKED, what
    it LEAVES, and which format that is in (RATIONALE D-23).

    'name' is the tool as the configuration spells it and lands in the
    record's header as 'tool'; 'format' is the CCoverageFormat it
    writes. Several frameworks share one format (c8 and cargo-llvm-cov
    both write LCOV), which is why the two are two classes.

    Every framework is derived from this and registered; admitting a
    tool is one subclass and one line in the registry's candidate
    table.
    """
    name   = None
    format = None                 # a CCoverageFormat instance

    @abstractmethod
    def wrap(self, argv, config, work_dir):
        """
        RETURN: list[str], the argv that runs 'argv' UNDER the coverage
                tool -- the only change a coverage run makes to the
                execute stage. 'argv' unchanged where the tool
                instruments at build time.
        """

    def report_argv(self, config, work_dir):
        """
        RETURN: list[str], the SECOND supervised call, run after the
                application, that turns the tool's raw state into the
                artefact 'format.read' reads.
                None, where the tool needs no second call.

        The framework NAMES it; the execute stage MAKES it, under the
        procsitter like every other process.
        """
        return None

    def instrumented_f(self, target, work_dir):
        """
        RETURN: True,  the built target carries this tool's
                       instrumentation, as far as the tool leaves a
                       trace to check (gcov: '.gcno' beside the object).
                False, it demonstrably does not.
                None,  this framework CANNOT CHECK -- the tool leaves no
                       trace before the run. The default; never
                       answered as False for want of a way to know.

        OPTIONAL. A None is reported as 'unchecked', never as a
        finding: guessing here is detection by another name (D-19).
        """
        return None

    def harvest(self, work_dir, source_root, config=None):
        """
        RETURN: CoverageRecord, 'format.read' with THIS tool's name
                stamped as the record's 'tool' -- the format is shared,
                the tool that wrote it is not (D-7).
                None, where no artefact stands.
        """
        from dataclasses import replace
        record = self.format.read(work_dir, source_root, config)
        return None if record is None else replace(record, tool=self.name)

    @property
    def source_format(self):
        """RETURN: str, the format's name -- the header's 'format'."""
        return self.format.name


# ------------------------------------------------------------- helpers

def artifact_directory_of(work_dir):
    """RETURN: str, where a tool leaves its artifact for this run."""
    return os.path.join(work_dir, *ARTIFACT_DIRECTORY.split("/"))


def relative_path(path, source_root):
    """
    RETURN: str, 'path' relative to 'source_root', with '/' separators --
            the one form a record ever holds. A path ABOVE the root keeps
            its '../', which is correct and is what an aggregator later
            rebases.

    A path that is ALREADY RELATIVE is left alone. It was written
    relative to where the tool RAN -- the test directory -- which is
    exactly the form wanted; re-basing it would silently measure it
    against this process's working directory instead, and turn 'app.py'
    into '../../app.py' on a machine that happened to run from
    elsewhere.

    This is where an ABSOLUTE path the tool emitted is discarded for
    good: after this, no record names a machine.
    """
    if not os.path.isabs(path):
        return os.path.normpath(path).replace(os.sep, "/")
    try:    relative = os.path.relpath(path, source_root)
    except ValueError:
        relative = path                     # different drive: nothing to do
    return relative.replace(os.sep, "/")


def wanted(path, config):
    """
    RETURN: True,  'path' is inside the gather set.
            False, the 'omit' globs exclude it, or an 'include' set was
                   stated and this path is outside it.

    THE GATHER SET, applied where the tool could not apply it (D-3). An
    empty 'include' means 'whatever the tool would take by itself'.
    """
    if config is None: return True
    if config.include and not any(fnmatch(path, p) for p in config.include):
        return False
    return not any(fnmatch(path, p) for p in (config.omit or ()))


def record_of(fmt, language, entry_iterable, counts_f=False):
    """
    RETURN: CoverageRecord, built from (path, executable_lines,
            covered_lines, count_list) tuples -- the ONE place a format
            turns its findings into the homogeneous shape. 'tool' is
            left EMPTY: the framework stamps it ('harvest').

    'run' is left EMPTY here: a format knows the ARTEFACT, not the run.
    The caller that knows the id seats it ('record.seated', D-8, D-18).
    """
    file_db = {}
    for path, executable, covered, count_list in entry_iterable:
        covered_range = ranges_of(covered)
        file_db[path] = FileCoverage(
            path, ranges_of(executable), covered_range,
            tuple(count_list) if counts_f and count_list is not None
            else None)
    return CoverageRecord(language = language,
                          tool     = "",
                          source   = fmt.name,
                          counts_f = counts_f,
                          file_db  = file_db)


# ------------------------------------------------------------ registry

_FRAMEWORK_DB  = {}
_LOADED_F      = [False]


def register(framework):
    """
    RETURN: CCoverageFramework, the framework now standing for its tool.

    Raises CoverageRefused where the tool already has one: two
    frameworks for one tool is two truths, and the second would win by
    import order; or where 'framework' is no CCoverageFramework -- the
    role is the type.
    """
    if not isinstance(framework, CCoverageFramework):
        raise CoverageRefused("'%s' is no CCoverageFramework"
                              % type(framework).__name__)
    if framework.name in _FRAMEWORK_DB:
        raise CoverageRefused("tool '%s' already has a framework"
                              % framework.name)
    _FRAMEWORK_DB[framework.name] = framework
    return framework


def _load():
    """RETURN: None. Imports the implementations, once. Importing them is
    what registers them."""
    if _LOADED_F[0]: return
    _LOADED_F[0] = True
    from . import readers                                      # noqa: F401


def framework_of(tool):
    """
    RETURN: CCoverageFramework, the framework registered for 'tool'.

    Raises CoverageRefused naming the tool and what IS registered -- a
    configuration may name a tool this build has no framework for, and
    that is a refusal at the door, not a silent absence of coverage.
    """
    _load()
    framework = _FRAMEWORK_DB.get(tool)
    if framework is None:
        raise CoverageRefused(
            "no framework is registered for coverage tool '%s'; this "
            "build knows %s" % (tool, ", ".join("'%s'" % k
                                          for k in sorted(_FRAMEWORK_DB))
                                or "nothing"))
    return framework


def registered_tuple():
    """RETURN: tuple of str, every tool this build has a framework for,
    sorted."""
    _load()
    return tuple(sorted(_FRAMEWORK_DB))
