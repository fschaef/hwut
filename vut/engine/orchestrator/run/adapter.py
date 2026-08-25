"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE CONFIGURATION ADAPTER (O-7) -- exploration's resolved
         CTestApp becomes operations' TestConfiguration, the shape the
         per-test ceremony consumes.

One direction, no memory: exploration owns WHAT WAS STATED; operations
owns WHAT A RUN NEEDS; this file owns the mapping and nothing else.
What the mapping does not cover yet (compare tolerances, 'execute',
language_setup) is named in run/DISCUSSIONS -- refused here rather
than guessed: an unmapped statement must not silently vanish into a
default.
______________________________________________________________________________
"""
import shlex

from ...bookkeeper.configuration  import NamingConfig
from ...operations.build_action  import BuildConfig, E_BuildSystem
from ...operations.configuration import (E_SourceKind,
                                         TestChoiceConfiguration,
                                         TestConfiguration)
from ...procsitter.procsitter    import ProcsitterConfig


#  language word (exploration) -> interpreter argv (operations).
INTERPRETER_DB = {
    "python": ("python3",),
    "bash":   ("bash",),
    "lua":    ("luau",),
}

#  Caps field (exploration) -> ProcsitterConfig field. Unmapped caps
#  keep procsitter's own defaults.
_CAPS_FIELD_DB = {
    "timeout_sec":         "max_wall_clock_sec",
    "cpu_sec":             "max_cpu_time_sec",
    "memory_mb":           "max_memory_mb",
    "file_size_mb":        "max_file_size_mb",
    "child_process_max_n": "max_pids",
}

_BUILD_SYSTEM_DB = {"make": E_BuildSystem.MAKE}


def naming_of(app):
    """
    RETURN: NamingConfig for that application -- 'same' stated means
            ALL CHOICES SHARE ONE NOMINAL (the choice part is dropped
            from the nominal's key; candidates keep their own names).

    'same' stands at the ROOT only (exploration's law), so the root
    choice's word is the application's word.
    """
    root = _root_of(app)
    return NamingConfig(same_nominal_f=bool(root.same))


def test_configuration_of(app, directory):
    """
    RETURN: TestConfiguration for 'app' as it stands in 'directory' --
            source kind and interpreter from the language, the build
            struct from the root choice's 'build', caps folded onto
            procsitter's defaults, a stated 'execute' as THE CALL
            itself (R-68), and one TestChoiceConfiguration per choice
            with its pype as the stdout canonicaliser and its stated
            tolerances as compare's Configuration.

    Raises AssertionError for a language no interpreter is declared
    for -- refused at the door, not guessed.
    """
    root = _root_of(app)

    build       = _build_of(root)
    interpreter = None
    if build is not None:
        source_kind = E_SourceKind.COMPILED
    elif app.language is None:
        source_kind = E_SourceKind.EXECUTABLE
    else:
        assert app.language in INTERPRETER_DB, \
               "no interpreter declared for language '%s'" % app.language
        source_kind = E_SourceKind.INTERPRETED
        interpreter = list(INTERPRETER_DB[app.language])

    choice_db = {choice: _choice_of(parameters)
                 for choice, parameters in app.choice_db.items()}

    return TestConfiguration(
        source_file    = app.source_file,
        source_kind    = source_kind,
        test_directory = directory,
        caps           = _caps_of(root),
        choice_db      = choice_db,
        interpreter    = interpreter,
        build          = build,
        interactive    = any(p.interactive for p in
                             app.choice_db.values()),
        execute        = (None if root.execute is None
                          else tuple(shlex.split(root.execute))))


def _build_of(parameters):
    """
    RETURN: BuildConfig from the stated 'build' key, 'None' where none
            stands. The framework word must be known; the executable
            is the one target.
    """
    stated = parameters.build
    if stated is None or stated.framework is None: return None
    assert stated.framework in _BUILD_SYSTEM_DB, \
           "no build system declared for framework '%s'" % stated.framework
    return BuildConfig(_BUILD_SYSTEM_DB[stated.framework],
                       [stated.executable or "app"])


def _caps_of(parameters):
    """
    RETURN: ProcsitterConfig, the stated caps folded onto procsitter's
            own defaults.
    """
    field_db = {}
    caps = parameters.caps
    if caps is not None:
        for source, target in _CAPS_FIELD_DB.items():
            value = getattr(caps, source)
            if value is not None: field_db[target] = value
    return ProcsitterConfig(**field_db)


def _choice_of(parameters):
    """
    RETURN: TestChoiceConfiguration of one choice: the stated 'pype'
            as the stdout canonicaliser (the D of the equivalence), and
            every stated TOLERANCE as compare's own Configuration (the
            T) -- 'None' where the author stated no tolerance at all,
            which is compare's default throughout.
    """
    canonicalisers = {}
    if parameters.pype is not None:
        canonicalisers["stdout"] = tuple(shlex.split(parameters.pype))
    #  'output' (todo-1): the spec's '<stdout>' becomes the plain
    #  subject name; file entries pass verbatim. None stays None --
    #  the default, ('stdout',), is resolved at the point of use.
    output = None
    if parameters.output is not None:
        output = tuple("stdout" if name == "<stdout>" else name
                       for name in parameters.output)
    return TestChoiceConfiguration(canonicalisers = canonicalisers,
                                   compare        = _compare_of(parameters),
                                   output         = output)


def _compare_of(parameters):
    """
    RETURN: compare's Configuration carrying every TOLERANCE the author
            stated; 'None' where none was stated -- an unstated
            tolerance is compare's own default, and a Configuration
            built here would only restate it.

    THE MAPPING, stated parameter -> compare's pattern finder:

        numeric         -> numeric_tolerance_ratio
        eq_pattern      -> equivalent_pattern_list
        nothing         -> visible_nothing_pattern_list
        analogy         -> analogy_begin/end_marker      (the PAIR)
        comment         -> ignored_line_begin/end_marker (the PAIR)
        constraints     -> constraint expressions
        slash_eqv       -> backslash_f
        whitespace_eqv  -> whitespace_f

    'analogy' and 'comment' are MARKER PAIRS: the empty tuple is the
    stated OFF (exploration's law -- 'None' is absence, '()' is off),
    and off is expressed to compare by the flag beside the markers.
    """
    stated = {name: getattr(parameters, name)
              for name in ("numeric", "eq_pattern", "nothing", "analogy",
                           "constraints", "comment", "slash_eqv",
                           "whitespace_eqv")}
    if all(value is None for value in stated.values()): return None

    from ...compare.configuration import Configuration
    options = Configuration()
    finder  = options.pattern_finder

    if stated["numeric"]        is not None:
        finder.numeric_tolerance_ratio      = stated["numeric"]
    if stated["eq_pattern"]     is not None:
        finder.equivalent_pattern_list      = list(stated["eq_pattern"])
    if stated["nothing"]        is not None:
        finder.visible_nothing_pattern_list = list(stated["nothing"])
    if stated["slash_eqv"]      is not None:
        finder.backslash_f                  = stated["slash_eqv"]
    if stated["whitespace_eqv"] is not None:
        finder.whitespace_f                 = stated["whitespace_eqv"]

    for name, flag, begin, end in (
            ("analogy", "analogy_f",      "analogy_begin_marker",
                                          "analogy_end_marker"),
            ("comment", "ignored_line_f", "ignored_line_begin_marker",
                                          "ignored_line_end_marker")):
        pair = stated[name]
        if pair is None: continue
        match len(pair):
            case 0:
                setattr(finder, flag, False)          # stated OFF
            case 2:
                setattr(finder, flag,  True)
                setattr(finder, begin, pair[0])
                setattr(finder, end,   pair[1])
            case _:
                assert False, \
                       "'%s' is a marker PAIR; %d stated" \
                       % (name, len(pair))

    if stated["constraints"] is not None:
        finder.constraint_f = bool(stated["constraints"])
        options.constraint_expression_list = \
                                     list(stated["constraints"])

    return options


def _root_of(app):
    """
    RETURN: TestParameters of the application's ROOT choice -- where
            the root-only words ('same', 'interactive') stand; the
            first choice by name where an application states no root.
    """
    return app.choice_db.get(None) or \
           app.choice_db[sorted(app.choice_db, key=lambda c: c or "")[0]]
