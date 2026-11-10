"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: PROVISIONAL flat configuration faces, standing in until each owning
         component declares its own
         (adm/WORK/gathered/0x-todo-1-owner-defaults-relocation.txt).

Each class below belongs to a named owner. When the owner declares its face,
this class is deleted and 'relation.RELATION' names the owner's class
instead; nothing else changes, because the table already relates our word to
a (class, member) pair and reads the default out of the declaration.

The values here are PROVISIONAL. A default is the value that causes the
least astonishment, and only the component that knows what the parameter
means can judge it; the owner's declaration replaces these without
re-litigation.
______________________________________________________________________________
"""
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfigBuild:
    """OWED TO: the build component.

    'framework' unstated means there is nothing to build: the source file
    is the test application. 'target' unstated means 'app' (o-48: it was
    'executable')."""
    framework:  str | None = None
    target:     str | None = None


@dataclass(frozen=True, slots=True)
class ConfigDeploy:
    """OWED TO: the deploy (engine/operations/deploy_action.py).

    'flash' unstated means there is nothing to deploy: the test reaches
    what it tests without (intend/26 o-40, o-41)."""
    flash:      str | None = None


@dataclass(frozen=True, slots=True)
class ConfigCaps:
    """OWED TO: procsitter -- and PAID for what it enforces (R-78): the
    wall clock, cpu, memory, file size and pids now read their defaults
    from 'ProcsitterConfig' on the supervisor's door. What stands here
    is only what the supervisor does not enforce.

    'write_directory_list' defaults to the directory of the test source
    and all of its sub-directories; 'None' here says exactly that -- the
    location is not known until a case is run, and procsitter fills it."""
    timeout_sec:          float       = 60.0
    cpu_sec:              float | None = None
    memory_mb:            int   | None = None
    file_size_mb:         int   | None = None
    child_process_max_n:  int   | None = None
    file_handle_max_n:    int   | None = None
    network:              bool         = True
    write_directory_list: tuple | None = None


@dataclass(frozen=True, slots=True)
class ConfigCanonicalise:
    """OWED TO: the pype component.

    'pype' unstated means no canonicalisation: the stream stands as it
    came."""
    pype: str | None = None


@dataclass(frozen=True, slots=True)
class ConfigCompare:
    """OWED TO: hwut.engine.compare.configuration.

    This MIRRORS compare's own 'ConfigurationPatternFinder', member for
    member and default for default. No face is asked of compare: the
    adapters in 'relation.py' bridge the shapes, and the defaults are read
    out of compare's own declaration (R-57)."""
    strip_whitespace_f:           bool  = True
    analogy_f:                    bool  = True
    constraint_f:                 bool  = True
    whitespace_f:                 bool  = True
    numeric_tolerance_ratio:      float = 0.0
    equivalent_pattern_list:      tuple = ()
    visible_nothing_pattern_list: tuple = ()
    ignored_line_f:               bool  = True
    regions_f:              bool  = True
    ignored_line_begin_marker:    str   = "##"
    ignored_line_end_marker:      str   = "##"
    analogy_begin_marker:         str   = "(("
    analogy_end_marker:           str   = "))"
    constraint_db:                dict  = None


@dataclass(frozen=True, slots=True)
class ConfigStore:
    """OWED TO: the result store.

    'same_nominal_f' -- all choices of one file share ONE nominal file: a
    storage economy (R-45)."""
    same_nominal_f: bool = False


@dataclass(frozen=True, slots=True)
class ConfigRunner:
    """OWED TO: the runner ('operations.TestConfiguration' already carries an
    'interactive' flag).

    'interactive_f' -- the application serves a SESSION: choices driven
    over stdin, several per call, no restart per choice (R-46).

    'execute' -- the call itself, stated verbatim (R-68). Unstated means
    the interpreter-derived call. The framework variables '$file',
    '$choice' and '$filestem' expand at the call; '$choice' expands
    empty for the choice-less call.

    'output' -- WHAT THE TEST PRODUCES, declared (todo-1): the subjects
    in order. '<stdout>' names the one channel; every other entry is a
    FILE, read after the run has ended and then removed. The default is
    the channel alone. stderr is NEVER here (E-5).

    'stderr_ignored_f' -- the test writes to stderr on purpose
    ('tolerance { stderr_ignored = true }', services E-136); false: a
    word there is an error."""
    interactive_f: bool = False
    stderr_ignored_f: bool = False
    output:        tuple = ("<stdout>",)
    execute:       str | None = None


@dataclass(frozen=True, slots=True)
class ConfigRequires:
    """OWED TO: the bubble decision ('plan/bubble.py' 'case_refusal').

    'tool_tuple' -- the tools ONE test needs beyond its directory's
    (intend/26 o-59). None: none; the case runs where its bubble runs."""
    tool_tuple: tuple | None = None


@dataclass(frozen=True, slots=True)
class ConfigFeatures:
    """OWED TO: the feature relation ('feature_relation.py').

    'feature_name_tuple' -- the features a test run PROVES, by their ids
    (spec 43: 'hwut-feature-forest.csv', 'hwut-feature-doc.dat'). None:
    the run links to no feature."""
    feature_name_tuple: tuple | None = None
