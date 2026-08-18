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


def test_configuration_of(app, directory):
    """
    RETURN: TestConfiguration for 'app' as it stands in 'directory' --
            source kind and interpreter from the language, the build
            struct from the root choice's 'build', caps folded onto
            procsitter's defaults, one TestChoiceConfiguration per
            choice with its pype as the stdout canonicaliser.

    Raises AssertionError for a language no interpreter is declared
    for -- refused at the door, not guessed.
    """
    root = app.choice_db.get(None) or \
           app.choice_db[sorted(app.choice_db, key=lambda c: c or "")[0]]

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
                             app.choice_db.values()))


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
    RETURN: TestChoiceConfiguration of one choice: a stated 'pype'
            becomes the stdout canonicaliser, its argv split by shell
            words.
    """
    canonicalisers = {}
    if parameters.pype is not None:
        canonicalisers["stdout"] = tuple(shlex.split(parameters.pype))
    return TestChoiceConfiguration(canonicalisers=canonicalisers)
