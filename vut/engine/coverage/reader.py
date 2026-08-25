"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE READER ROLE -- one tool's artifact becomes the homogeneous
         record, and nothing else happens here.

DESCRIPTION
       ONE READER PER TOOL. A reader knows three things and no more:

           wrap(argv)          the tool's own call form -- THE one place
                               a language's coverage tool is named
           report_argv()       the SECOND supervised call, where the tool
                               needs one to turn its raw data into
                               something readable ('coverage json',
                               'gcov'); None where it does not
           harvest(directory)  the artifact under 'OUT/COVERAGE/' ->
                               a CoverageRecord

       WHY A SECOND CALL EXISTS. Most coverage tools leave BINARY state,
       not a report: coverage.py leaves a '.coverage' database, gcc
       leaves '.gcda' counters. Turning either into text is itself a
       PROCESS, and every process HWUT runs goes through the procsitter
       (procsitter MANUAL, rule of thumb 1). So the reader NAMES the
       call and the execute stage MAKES it -- a reader spawns nothing.
       'report_argv' returning None says, honestly, that this tool needs
       no second call.

       A reader NEVER renders, never judges, never decides whether
       coverage was wanted. It also never re-derives what the store
       already holds: the store stores, the pack renders.

       PATHS ARE MADE RELATIVE TO THE TEST DIRECTORY by the reader, at
       the moment it knows both -- the one point where the absolute path
       the tool emitted is still available and can be discarded for good
       (RATIONALE D-4).

       THE GATHER SET, TWICE. 'include'/'omit' are a GATHERING knob
       (D-3). A tool that takes them gets them in 'wrap'; a tool that
       does not gets them applied at HARVEST instead. Either way the
       same globs decide, and neither is a reporting filter.

       IMPORTING THIS MODULE REGISTERS NOTHING. The implementations live
       in 'readers/'; 'reader_of' imports that package on its first miss,
       so a caller that never elects a tool never pays for any of them.
______________________________________________________________________________
"""
import os
from fnmatch import fnmatch

from .configuration import CoverageRefused
from .record        import CoverageRecord, FileCoverage, ranges_of


ARTIFACT_DIRECTORY = "OUT/COVERAGE"


class I_Reader:
    """THE ROLE. A tool's whole knowledge, behind three calls.

    'name' is the tool as the configuration spells it; 'source_format'
    names the shape its artifact is in, and lands in the record's header
    as the provenance (RATIONALE D-7).
    """
    name          = None
    source_format = None

    def wrap(self, argv, config, work_dir):
        """
        RETURN: list[str], the argv that runs 'argv' UNDER the coverage
                tool -- the only change a coverage run makes to the
                execute stage.
        """
        raise NotImplementedError

    def report_argv(self, config, work_dir):
        """
        RETURN: list[str], the SECOND supervised call, run after the
                application, that turns the tool's raw state into the
                artifact 'harvest' reads.
                None, where the tool needs no second call.

        The reader NAMES it; the execute stage MAKES it, under the
        procsitter like every other process.
        """
        return None

    def harvest(self, work_dir, source_root, config=None):
        """
        RETURN: CoverageRecord, read from this tool's artifact under
                'work_dir/OUT/COVERAGE'.
                None, where the tool left no artifact -- ABSENT, which is
                not the same as an empty measurement and must not be
                reported as one.

        'source_root' is the TEST DIRECTORY: every path in the record is
        made relative to it here. 'config' is the CoverageConfig, so that
        a reader whose tool could not apply the gather set can apply it
        itself.
        """
        raise NotImplementedError


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


def record_of(reader, language, entry_iterable, counts_f=False):
    """
    RETURN: CoverageRecord, built from (path, executable_lines,
            covered_lines, count_list) tuples -- the ONE place a reader
            turns its findings into the homogeneous shape.

    'run' is left EMPTY here: a reader knows the ARTIFACT, not the run.
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
                          tool     = reader.name,
                          source   = reader.source_format,
                          counts_f = counts_f,
                          file_db  = file_db)


# ------------------------------------------------------------ registry

_READER_DB     = {}
_LOADED_F      = [False]


def register(reader):
    """
    RETURN: I_Reader, the reader now standing for its tool.

    Raises CoverageRefused where the tool already has one: two readers
    for one tool is two truths, and the second would win by import order.
    """
    if reader.name in _READER_DB:
        raise CoverageRefused("tool '%s' already has a reader" % reader.name)
    _READER_DB[reader.name] = reader
    return reader


def _load():
    """RETURN: None. Imports the implementations, once. Importing them is
    what registers them."""
    if _LOADED_F[0]: return
    _LOADED_F[0] = True
    from . import readers                                      # noqa: F401


def reader_of(tool):
    """
    RETURN: I_Reader, the reader registered for 'tool'.

    Raises CoverageRefused naming the tool and what IS registered -- a
    configuration may name a tool this build has no reader for, and that
    is a refusal at the door, not a silent absence of coverage.
    """
    _load()
    reader = _READER_DB.get(tool)
    if reader is None:
        raise CoverageRefused(
            "no reader is registered for coverage tool '%s'; this build "
            "reads %s" % (tool, ", ".join("'%s'" % k
                                          for k in sorted(_READER_DB))
                          or "nothing"))
    return reader


def registered_tuple():
    """RETURN: tuple of str, every tool this build can read, sorted."""
    _load()
    return tuple(sorted(_READER_DB))
