"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE CONFIGURATION ADAPTER (O-7) -- exploration's resolved
         CTestApp becomes operations' TestConfiguration, the shape the
         per-test ceremony consumes.

One direction, no memory: exploration owns WHAT WAS STATED; operations
owns WHAT A RUN NEEDS; this file owns the mapping and nothing else.
What the mapping does not cover yet (compare tolerances) is refused
here rather than guessed: an unmapped statement must not silently
vanish into a default.

THE LANGUAGE TABLE IS THE ROOT CONF'S (exploration R-73). 'language_setup'
is the resolved 'language-setup' dict of the tree; this module carries
NO table of its own. The interpreter is the entry's word, else the
language's own name (R-10).
______________________________________________________________________________
"""
import os
import shlex
from dataclasses import replace

from ...bookkeeper.api  import StoreConfig
from ..exploration.selection import naming_of           # noqa: F401
from ..exploration.configuration_tree import BUILD_FRAMEWORK_TUPLE
from ...operations.build_action  import BuildConfig, E_BuildSystem
from ...operations.configuration import (E_SourceKind,
                                         TestChoiceConfiguration,
                                         TestConfiguration)
from ...procsitter.api    import ProcsitterConfig

from ...bookkeeper.api    import CAPS_FIELD_DB as _CAPS_FIELD_DB

#  ONE PER FRAMEWORK THE HEADER ADMITS ('BUILD_FRAMEWORK_TUPLE').
_BUILD_SYSTEM_DB = {framework: E_BuildSystem(framework)
                    for framework in BUILD_FRAMEWORK_TUPLE}



def stem_expanded(text, source_file):
    """
    RETURN: str, 'text' with every '%' replaced by the STEM of
            'source_file' -- 'test-parse.c' gives 'test-parse' -- and
            '%%' by one literal '%' (R-74).
    """
    stem = os.path.splitext(os.path.basename(source_file))[0]
    return text.replace("%%", "\0").replace("%", stem).replace("\0", "%")


def interpreter_of(language, language_setup):
    """
    RETURN: list[str], the argv prefix that runs a test of 'language':
            the 'language-setup' entry's 'interpreter', split as a
            shell would; the language's own name where the entry
            states none, or where no entry stands (R-10 NOTE).
    """
    setup = (language_setup or {}).get(language)
    if setup is not None and setup.interpreter:
        return shlex.split(setup.interpreter)
    return [language]


def test_configuration_of(app, directory, variant_tuple=(), variant_db=None,
                          timing_f=False, language_setup=None,
                          free_disk_min_mb=None):
    """
    RETURN: TestConfiguration for 'app' as it stands in 'directory' --
            source kind and interpreter from the language, the build
            struct from the root choice's 'build', caps folded onto
            procsitter's defaults, a stated 'execute' as THE CALL
            itself (R-68), and one TestChoiceConfiguration per choice
            with its pype as the stdout canonicaliser and its stated
            tolerances as compare's Configuration.

    'variant_tuple' names the alternatives '--variant' selected (E-9);
    what each states is merged over the ROOT choice's parameters,
    before the build struct and the caps are taken from it. A variant
    states DIFFERENCES; what it leaves unstated keeps what the author
    wrote.

    'language_setup' is the tree's resolved 'language-setup' dict
    (R-73); None reads as empty, and every language is then called by
    its own name.

    'free_disk_min_mb' is the root's floor of free space on every disk
    (D-24); None leaves procsitter's own.

    'timing_f' asks for the RUN'S CADENCE ('--timing'): the per-line
    delta times are kept beside the candidate. It is the ONLY thing
    that raises a StoreConfig here -- WHERE and HOW MUCH is kept is the
    store's word, and until something asks for more than the candidate
    there is nothing for it to say.
    """
    root = _root_of(app)
    if variant_tuple:
        from ..exploration.variant import merged_parameters
        root = merged_parameters(variant_tuple, variant_db, root)

    build = _build_of(root, app.source_file)
    #  THE APPLICATION'S CAPS COME FROM ITS RESOLVED ROOT (O-20, O-21):
    #  'app.root' -- the directory's default folded with the header's
    #  root, what every choice inherits before its own word. Never
    #  from '_root_of', which answers the FIRST CHOICE BY NAME and
    #  would make one choice's cap the baseline its siblings inherit;
    #  and not from 'choice_db.get(None)' either, which exists only
    #  where the header names no choice at all.
    base  = ProcsitterConfig() if free_disk_min_mb is None \
            else ProcsitterConfig(min_free_disk_mb=free_disk_min_mb)
    caps  = _caps_of(app.root, base) if app.root is not None else base
    interpreter = None
    if build is not None:
        source_kind = E_SourceKind.COMPILED
    elif app.language is None:
        source_kind = E_SourceKind.EXECUTABLE
    else:
        source_kind = E_SourceKind.INTERPRETED
        interpreter = interpreter_of(app.language, language_setup)

    #  EVERY CHOICE CARRIES ITS OWN CAPS, COMPLETE (O-20): the record
    #  resolves no default, so the fold happens HERE, once, and the
    #  consumers read what they are handed.
    choice_db = {choice: _choice_of(parameters, _caps_of(parameters, caps))
                 for choice, parameters in app.choice_db.items()}

    return TestConfiguration(
        source_file    = app.source_file,
        source_kind    = source_kind,
        test_directory = directory,
        caps           = caps,
        choice_db      = choice_db,
        interpreter    = interpreter,
        build          = build,
        interactive    = any(p.interactive for p in
                             app.choice_db.values()),
        execute        = (None if root.execute is None
                          else tuple(shlex.split(root.execute))),
        store          = (StoreConfig(directory=directory,
                                      record_timing=True)
                          if timing_f else None))


def _build_of(parameters, source_file):
    """
    RETURN: BuildConfig from the stated 'build' key, 'None' where none
            stands. The framework word must be known; the executable
            is the one target. '%' in either is the source file's
            stem (R-74).
    """
    stated = parameters.build
    if stated is None or stated.framework is None: return None
    framework = stem_expanded(stated.framework, source_file)
    #  A NAME THE HEADER DID NOT ADMIT reaches here only through '%'
    #  (the validator judges every literal one): said by name.
    if framework not in _BUILD_SYSTEM_DB:
        raise ValueError("unknown build framework '%s' (from '%s'); "
                         "known: %s" % (framework, stated.framework,
                                        ", ".join(BUILD_FRAMEWORK_TUPLE)))
    target = stem_expanded(stated.executable or "app", source_file)
    return BuildConfig(_BUILD_SYSTEM_DB[framework], [target])


def _caps_of(parameters, inherited=None):
    """
    RETURN: ProcsitterConfig, the stated caps folded onto 'inherited',
            or onto procsitter's own defaults where none is given.

    CAPS TRAVEL BY INHERITANCE (O-20): the application's word stands
    over procsitter's, and a choice's word stands over both. A cap the
    choice does not state is the application's, exactly as every other
    parameter of a choice behaves.
    """
    base = inherited if inherited is not None else ProcsitterConfig()
    field_db = {}
    caps = parameters.caps
    if caps is not None:
        for source, target in _CAPS_FIELD_DB.items():
            value = getattr(caps, source)
            if value is not None: field_db[target] = value
    return replace(base, **field_db) if field_db else base


#  WHAT A DIRECTORY'S SCRIPT RUNS UNDER WHERE 'script_caps' STATES
#  NOTHING: the frame's minute of wall clock, procsitter's own else.
SCRIPT_CAPS = ProcsitterConfig(max_wall_clock_sec=60.0)


def script_config_of(directory_spec, env=None):
    """
    RETURN: ProcsitterConfig, the caps a script of the directory runs
            under -- 'on_entry', 'on_exit', 'on_before_test',
            'on_after_test' and the targets of 'hwut.execute' (B-17):
            'SCRIPT_CAPS' with the directory's 'script_caps' folded on,
            the root's 'free_disk_min_mb' as the floor, 'env' as the
            environment overlay.
    """
    base = SCRIPT_CAPS
    floor = getattr(directory_spec, "free_disk_min_mb", None)
    if floor is not None: base = replace(base, min_free_disk_mb=floor)
    stated = getattr(directory_spec, "script_caps", None)
    field_db = {}
    if stated is not None:
        for source, target in _CAPS_FIELD_DB.items():
            value = getattr(stated, source)
            if value is not None: field_db[target] = value
    if env is not None: field_db["env"] = env
    return replace(base, **field_db) if field_db else base


def _choice_of(parameters, caps):
    """
    RETURN: TestChoiceConfiguration of one choice: the stated 'pype'
            as the stdout canonicaliser (the D of the equivalence),
            every stated TOLERANCE as compare's own Configuration (the
            T) -- 'None' where the author stated no tolerance at all,
            which is compare's default throughout -- and the choice's
            CAPS, already folded onto the application's (O-20).
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
                                   output         = output,
                                   caps           = caps,
                                   stderr_ignored_f = bool(
                                       parameters.tolerance is not None
                                       and parameters.tolerance
                                                     .stderr_ignored))


def _compare_of(parameters):
    """
    RETURN: compare's Configuration carrying every TOLERANCE the author
            stated; 'None' where none was stated -- an unstated
            tolerance is compare's own default, and a Configuration
            built here would only restate it.

    THE MAPPING, stated parameter -> compare's pattern finder:

        tolerance.numeric_ratio -> numeric_tolerance_ratio   (R-77)
        tolerance.whitespace    -> whitespace_f
        tolerance.regions       -> regions_f                  (C-4)
        tolerance.eq_pattern    -> equivalent_pattern_list
        tolerance.nothing       -> visible_nothing_pattern_list
        tolerance.analogy       -> analogy_begin/end_marker      (PAIR)
        tolerance.comment       -> ignored_line_begin/end_marker (PAIR)
        tolerance.constraints   -> constraint expressions

    EVERY ONE IS A LEAF OF 'tolerance' (E-42): one scope, one walk.

    'analogy' and 'comment' are MARKER PAIRS: the empty tuple is the
    stated OFF (exploration's law -- 'None' is absence, '()' is off),
    and off is expressed to compare by the flag beside the markers.
    """
    #  THE TOLERANCE SCOPE flattens onto one table: absent scope,
    #  absent leaves.
    tolerance = parameters.tolerance
    stated    = {}
    for leaf in TOLERANCE_LEAF_TUPLE:
        stated["tolerance.%s" % leaf] = \
            getattr(tolerance, leaf) if tolerance is not None else None
    #  THE LINE LEVEL'S NUMBERS (compare C-16) travel the same way.
    matching = getattr(parameters, "diff_display_parameters", None)
    for leaf in ("search_budget", "margin", "lowest_n", "context_k"):
        stated["diff_display_parameters.%s" % leaf] = \
            getattr(matching, leaf) if matching is not None else None
    if all(value is None for value in stated.values()): return None

    from ...compare.api import Configuration
    options = Configuration()
    for leaf in ("search_budget", "margin", "lowest_n", "context_k"):
        if stated["diff_display_parameters.%s" % leaf] is not None:
            setattr(options.diff_display_parameters, leaf, stated["diff_display_parameters.%s" % leaf])

    tolerance_applied(options, tolerance)
    return options


TOLERANCE_LEAF_TUPLE = ("numeric_ratio", "whitespace", "regions",
                        "eq_pattern", "nothing", "analogy", "constraints",
                        "comment")


def tolerance_applied(options, tolerance):
    """
    RETURN: None. Every leaf 'tolerance' STATES is set on 'options'
            (compare's Configuration), by the mapping of '_compare_of';
            an absent leaf leaves compare's value as it stands.

    ONE MAPPING, TWO USERS: the run's own configuration, and the merge
    screen's tolerance pane (intend 21), which applies the author's text
    onto the configuration the session holds.
    """
    finder = options.pattern_finder
    stated = {"tolerance.%s" % leaf:
                  getattr(tolerance, leaf) if tolerance is not None else None
              for leaf in TOLERANCE_LEAF_TUPLE}
    if stated["tolerance.numeric_ratio"] is not None:
        finder.numeric_tolerance_ratio      = stated["tolerance.numeric_ratio"]
    if stated["tolerance.eq_pattern"]     is not None:
        finder.equivalent_pattern_list      = list(stated["tolerance.eq_pattern"])
    if stated["tolerance.nothing"]        is not None:
        finder.visible_nothing_pattern_list = list(stated["tolerance.nothing"])
    if stated["tolerance.whitespace"] is not None:
        finder.whitespace_f                 = stated["tolerance.whitespace"]
    if stated["tolerance.regions"]    is not None:
        finder.regions_f                    = stated["tolerance.regions"]

    for name, flag, begin, end in (
            ("tolerance.analogy", "analogy_f",
                                  "analogy_begin_marker",
                                  "analogy_end_marker"),
            ("tolerance.comment", "ignored_line_f",
                                  "ignored_line_begin_marker",
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
                raise AssertionError("'%s' is a marker PAIR; %d stated" \
                       % (name, len(pair)))

    if stated["tolerance.constraints"]:
        #  THE EXPRESSIONS ARE COMPILED HERE, NOT ONLY STORED: compare
        #  checks 'constraint_db', never the list as written. Setting the
        #  list alone left every page's 'constraints' unenforced (O-34).
        #  'constraints = []' IS THE DEFAULT, not an off: it leaves
        #  compare as it stands, so the printed default reads back as one.
        options.constraint_expression_list = \
                                     list(stated["tolerance.constraints"])
        options.derive_constraint_db()


def _root_of(app):
    """
    RETURN: TestParameters of the application's ROOT choice -- where
            the root-only words ('same', 'interactive') stand; the
            first choice by name where an application states no root.
    """
    return app.choice_db.get(None) or \
           app.choice_db[sorted(app.choice_db, key=lambda c: c or "")[0]]
