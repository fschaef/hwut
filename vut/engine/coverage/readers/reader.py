"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE TWO ROLES OF A COVERAGE TOOL -- the FRAMEWORK that is
         invoked and the FORMAT that is read -- and the registry that
         finds a framework by its tool's name (RATIONALE D-23).

DESCRIPTION
       CCoverageFramework      one per TOOL: gcov, coverage.py, jacoco
           specify_command_line()
                               the command line by which the tool runs
                               the test application, from the class's
                               'call_scheme' (D-39) -- THE one place a
                               coverage tool's call is spelt
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
       (D-3). A tool that takes them gets them in its call scheme; a tool that
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
from abc import ABC
from fnmatch import fnmatch

from ..configuration import CoverageRefused
from ..database.record        import CoverageRecord, FileCoverage, ranges_of


ARTIFACT_DIRECTORY = "OUT/COVERAGE"


class CCoverageFormat(ABC):
    """THE ARTEFACT'S SHAPE -- one per format, whoever wrote it.

    'name' lands in the record's header as 'format' (RATIONALE D-7).
    A format knows how to READ; it knows nothing of the tool that ran,
    and stamps no tool into the record -- the framework does (D-23).

    THE WALK IS THE BASE'S, THE THREE VARIABLE POINTS ARE THE
    FORMAT'S. 'read' below is CONCRETE: it finds the artefact
    directory, takes every file ending in 'suffix' in sorted order,
    hands each to 'absorb', and distinguishes ABSENT from an empty
    measurement. What differs between formats is only:

        suffix       the artefact's file suffix(es)
        empty()      a fresh accumulator
        absorb()     one file into it
        record_of()  the accumulator into a CoverageRecord

    Ten readers wrote that walk out by hand to reach those three
    points -- the base declared the CONTRACT and gave no SHAPE, so
    the shape was copied, along with the one-line policy
    'counts_f = bool(config is not None and config.counts)'. A format
    whose reading does not fit the walk at all overrides 'read'
    itself and says why ('lcov' merges text after the walk;
    'python_coverage' reaches the directory twice).
    """
    name   = None
    suffix = None                 # tuple[str] | str, the artefact's

    def empty(self):
        """RETURN: object, a fresh accumulator for one read -- a dict
        for most formats, which is the default."""
        return {}

    def absorb(self, accumulator, path):
        """RETURN: None. One artefact file folded into 'accumulator'.
        A format that cannot read a file leaves the accumulator
        untouched: an unreadable artefact is not a measurement of
        zero."""
        raise NotImplementedError

    def record_of(self, accumulator, source_root, config, counts_f):
        """RETURN: CoverageRecord over what was absorbed."""
        raise NotImplementedError

    def record_from(self, file_db, counts_f, language):
        """
        RETURN: CoverageRecord over a FILE DATABASE the format built
                itself -- for a format whose artefact is not
                line-shaped and so cannot use 'line_record_of'.

        THE HEADER IS FILLED THE ONE CORRECT WAY, which is why this
        exists rather than four hand-written constructors:

            'source' IS THE FORMAT'S NAME, never the framework's -- one
                     format is written by several tools (c8 and
                     cargo-llvm-cov both write LCOV).
            'tool'   IS LEFT EMPTY. The FRAMEWORK stamps it in
                     'harvest', because with a candidate list which
                     tool served is decided at run time (D-7). A format
                     that stamped it would be guessing.
            'run'    IS LEFT EMPTY, its default. A reader knows the
                     ARTEFACT, not the run; whoever holds the id calls
                     'record.seated' (D-8, D-18).
        """
        return CoverageRecord(language = language,
                              tool     = "",
                              source   = self.name,
                              counts_f = counts_f,
                              file_db  = file_db)

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
        accumulator = self.empty()
        directory   = artifact_directory_of(work_dir)
        if os.path.isdir(directory):
            suffix_tuple = (self.suffix,) if isinstance(self.suffix, str) \
                           else tuple(self.suffix)
            for name in sorted(os.listdir(directory)):
                if not name.endswith(suffix_tuple): continue
                self.absorb(accumulator, os.path.join(directory, name))
        if not accumulator: return None

        counts_f = bool(config is not None and config.counts)
        return self.record_of(accumulator, source_root, config, counts_f)


SCHEME_FIELD_TUPLE = ("include", "omit", "test", "choice")


def scheme_argv(call_scheme, included_paths, omitted_paths, test_app,
                choice):
    """
    RETURN: list[str], the words of 'call_scheme' with its fields
            filled:

                {include}   the included paths, ',' between
                {omit}      the omitted paths, ',' between
                {test}      the test application; where it is several
                            words (a stated call, R-68) they stay
                            several
                {choice}    the choice

            A WORD WHOSE FIELD IS EMPTY IS DROPPED WHOLE: '--omit={omit}'
            leaves no '--omit=' behind where nothing is omitted, and
            '{choice}' leaves nothing where the application has no
            choice.

    Raises ValueError where the scheme names a field that is none of
    the four.
    """
    import re
    import shlex
    value_db = {"include": ",".join(str(p) for p in included_paths or ()),
                "omit":    ",".join(str(p) for p in omitted_paths or ()),
                "test":    str(test_app),
                "choice":  "" if choice is None else str(choice)}
    argv = []
    for word in shlex.split(call_scheme):
        field_list = re.findall(r"\{([^{}]*)\}", word)
        for field in field_list:
            if field not in SCHEME_FIELD_TUPLE:
                raise ValueError(
                    "call scheme '%s' names '{%s}'; the fields are %s"
                    % (call_scheme, field,
                       ", ".join("{%s}" % f for f in SCHEME_FIELD_TUPLE)))
        if any(not value_db[field] for field in field_list): continue
        if word == "{test}":
            argv += shlex.split(value_db["test"])
            continue
        for field in field_list:
            word = word.replace("{%s}" % field, value_db[field])
        argv.append(word)
    return argv


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

    #  THE CALL SCHEME (D-39): the tool's command line as a template.
    #  None: this tool is not on the command line at all, and the
    #  application is called as it stands.
    call_scheme = None

    def specify_command_line(self, included_paths, omitted_paths,
                             test_app, choice):
        """
        RETURN: list[str], the command line by which the TOOL runs the
                test application: 'call_scheme' with its fields filled
                ('scheme_argv').
                None, where the tool is not on the command line -- the
                application is then called as it stands. The default,
                and the answer for every tool that instruments
                somewhere this component does not reach: at BUILD time
                (gcov's '--coverage', verilator's, ghdl's '-fpsl'),
                through a JVM AGENT (jacoco), or from INSIDE the
                process (simplecov, luacov). Each such framework says
                WHY in its own class docstring.

        'included_paths', 'omitted_paths'  the gather set (D-3), as the
                    run states it; either may be empty.
        'test_app'  the test application, as the tool is handed it:
                    the source file of an interpreted test, the built
                    coverage target of a compiled one.
        'choice'    the choice of this run; None where the application
                    has none.
        """
        if self.call_scheme is None: return None
        return scheme_argv(self.call_scheme, included_paths,
                           omitted_paths, test_app, choice)

    def report_argv(self, config, work_dir):
        """
        RETURN: list[str], the SECOND supervised call, run after the
                application, that turns the tool's raw state into the
                artefact 'format.read' reads.
                None, where the tool needs no second call.

        The framework NAMES it; the execute stage MAKES it, under the
        procsitter like every other process.
        """
        return

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
        return

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

def language_of(file_db, suffix_db, collapse_tuple=()):
    """
    RETURN: str, the language the report is OF, worked out from the
            extensions the paths carry; 'unknown' where they disagree
            or say nothing.

    A DOCUMENT THAT NAMES NO LANGUAGE OF ITS OWN must work it out, and
    five formats are in that position: Cobertura is shared by five
    ecosystems, a JaCoCo report covers the JVM rather than one
    language of it, UCIS covers a whole verification environment.
    They differ in exactly two things, which are their own and stay
    theirs -- the SUFFIX MAP, and which mixes are LEGITIMATE:

        'collapse_tuple'  ((member_set, answer), ...): where every
                          language found lies inside 'member_set', the
                          answer is 'answer' rather than 'unknown'.
                          Verilog and SystemVerilog mix by design and
                          read 'verilog' -- the subset relation makes
                          that honest, where java and kotlin's would
                          not, so JaCoCo declares no collapse and its
                          mix reads 'unknown'.

    'unknown' IS SAID, never defaulted to the commonest member: a
    header that guesses is a header nobody can trust.
    """
    name_set = set()
    for path in file_db:
        name = suffix_db.get(os.path.splitext(path)[1].lower())
        if name is not None: name_set.add(name)
    if not name_set:          return "unknown"
    if len(name_set) == 1:    return name_set.pop()
    for member_set, answer in collapse_tuple:
        if name_set <= set(member_set): return answer
    return "unknown"


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
            turns its findings into the homogeneous shape. A fifth
            element, a dict of measure name -> points ('measure.py'),
            seats the measures beside the lines; a format that has none
            gives four. 'tool' is left EMPTY: the framework stamps it
            ('harvest').

    'run' is left EMPTY here: a format knows the ARTEFACT, not the run.
    The caller that knows the id seats it ('record.seated', D-8, D-18).
    """
    file_db = {}
    for path, executable, covered, count_list, *rest in entry_iterable:
        covered_range = ranges_of(covered)
        file_db[path] = FileCoverage(
            path, ranges_of(executable), covered_range,
            tuple(count_list) if counts_f and count_list is not None
            else None,
            {name: tuple(point_tuple)
             for name, point_tuple in (rest[0] if rest else {}).items()
             if point_tuple})
    return CoverageRecord(language = language,
                          tool     = "",
                          source   = fmt.name,
                          counts_f = counts_f,
                          file_db  = file_db)


def line_record_of(fmt, entry_db, config, source_root, counts_f,
                   language_of):
    """
    RETURN: CoverageRecord, built from a LINE DATABASE -- the shape
            'path -> {line number: format-specific tuple}' that every
            line-oriented format arrives at once its own parsing is
            done.

    THE COMMON FOLD: relativise the path, drop what the configuration
    does not want, split executable from covered, and -- where
    'counts_f' -- the per-range maximum hit count. Field [0] of each
    line's tuple is ITS HIT COUNT, which is all this fold reads of a
    format's own shape.

    A format that names no arm of a decision (a count of taken and
    missing) seats no branch measure: the measure is the SET of arms
    taken (RATIONALE D-43), and a count is not one.

    'language_of' is likewise the format's: a document that names no
    language of its own works it out from the extensions it carries.
    """
    file_db = {}
    for raw_path in sorted(entry_db):
        path = relative_path(raw_path, source_root)
        if not wanted(path, config): continue
        line_db    = entry_db[raw_path]
        executable = sorted(line_db)
        covered    = [n for n in executable if line_db[n][0] > 0]

        count_list = None
        if counts_f:
            count_list = tuple(max(line_db[n][0] for n in range(begin, end)
                                   if n in line_db)
                               for begin, end in ranges_of(covered))

        file_db[path] = FileCoverage(path, ranges_of(executable),
                                     ranges_of(covered), count_list)

    return CoverageRecord(language = language_of(file_db),
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
    """RETURN: None. A NO-OP since the component split (session
    2026-09-04): 'reader.py' used to be a SIBLING of the 'readers'
    package it deferred importing, so a caller could reach
    'framework_of' without pulling in any format's tooling until it
    was actually called. Now that this module lives INSIDE 'readers/',
    Python initialises the package's own '__init__.py' -- which
    registers every format -- before this module is reachable at all,
    by the ordinary rule that a submodule cannot be imported ahead of
    its package. The deferral this function performed is therefore
    unreachable: '_FRAMEWORK_DB' is already populated by the time
    anything here runs. Kept, rather than deleted outright, so
    'framework_of' need not change and so the loss of the
    optimisation is named at the one place it happened, not silently
    absorbed."""
    _LOADED_F[0] = True


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
