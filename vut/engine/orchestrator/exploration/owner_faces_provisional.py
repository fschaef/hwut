"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: PROVISIONAL flat configuration faces, standing in until each owning
         component declares its own
         (DISCUSSIONS/todo-1-owner-defaults-relocation.txt).

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
    is the test application. 'executable' unstated means the source file's
    stem."""
    framework:  str | None = None
    executable: str | None = None


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
    """OWED TO: vut.engine.compare.configuration.

    This MIRRORS compare's own 'ConfigurationPatternFinder', member for
    member and default for default. No face is asked of compare: the
    adapters in 'relation.py' bridge the shapes, and the defaults are read
    out of compare's own declaration (R-57)."""
    strip_whitespace_f:           bool  = True
    analogy_f:                    bool  = True
    constraint_f:                 bool  = True
    whitespace_f:                 bool  = True
    backslash_f:                  bool  = True
    numeric_tolerance_ratio:      float = 0.0
    equivalent_pattern_list:      tuple = ()
    visible_nothing_pattern_list: tuple = ()
    ignored_line_f:               bool  = True
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
    the channel alone. stderr is NEVER here (E-5)."""
    interactive_f: bool = False
    output:        tuple = ("<stdout>",)
    execute:       str | None = None
