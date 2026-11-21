"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: The exploration step. Read 'hwut.conf' first -- its directory keys
         govern what follows -- then the headers of the directory's files.
         Interview what neither carrier speaks for. Cross-check the
         carriers, resolve the root defaults into each
         choice, settle which cases can be reached at all, and state what
         exists: a CTestAppSet.

Faults accumulate; exploration completes and reports every fault at once.
A file whose specification carried faults yields no CTestApp: a partially
understood specification is refused, not guessed at.
______________________________________________________________________________
"""
import os

from dataclasses    import dataclass

from .              import finder
from .              import reader
from .              import satisfiability
from .              import hwut_info_interview
from .fault         import Fault, E_FaultKind
from .              import provenance
from .configuration_tree import (CTestApp, CTestAppSet, DirectorySpec,
                            TestParameters)


def _execute_interactive_refused(app):
    """
    RETURN: list[Fault], one fault per choice of 'app' that states
            'execute' beside 'interactive' -- the session protocol
            assumes the runner, so the pair is refused (R-68); empty
            where the pair does not stand.
    """
    fault_list = []
    for choice, parameters in sorted(app.choice_db.items(),
                                     key=lambda item: item[0] or ""):
        if parameters.execute is not None and parameters.interactive:
            fault_list.append(Fault(
                E_FaultKind.TYPE, app.source_file, app.position,
                "'execute' beside 'interactive': the session protocol "
                "assumes the runner; state one"))
    return fault_list


def _constraint_module_set(app_db, directory):
    """
    RETURN: set[str], the absolute path of every constraint module a choice
            of an application of 'app_db' names.
    """
    from ...compare.engine.constraint_namespace import module_path_of
    return {module_path_of(parameters.tolerance.constraint_module, directory)
            for app in app_db.values()
            for parameters in app.choice_db.values()
            if parameters.tolerance is not None
               and parameters.tolerance.constraint_module is not None}


def _constraint_module_refused(app, directory, spec, directory_spec):
    """
    RETURN: list[Fault], one fault per choice of 'app' whose constraint
            module does not load, or one of whose constraints calls a
            name neither the fixed namespace nor that module holds -- at
            the place the module, or the list of laws, is written;
            empty where every choice's laws stand.

    THE DOOR OF ONE SCOPE cannot judge a call: the module may be stated in
    a 'hwut.conf' above (ruled 2026-11-18). Here both are folded, the
    test directory is known, and the fault is said before any line is
    read -- the application is refused, 'spec [FAIL]'. 'spec' and
    'directory_spec' are what 'app' was folded from: they say where a
    value was written.
    """
    from ...compare.api import constraint_fault_of
    from ...compare.engine.constraint_namespace import (
                                FIXED_NAMESPACE, ConstraintModuleError,
                                module_path_of, namespace_for)
    from .validator import CONSTRAINTS_VALUE_KEY
    fault_list, said_set = [], set()
    for choice, parameters in sorted(app.choice_db.items(),
                                     key=lambda item: item[0] or ""):
        tolerance = parameters.tolerance
        if tolerance is None: continue
        namespace = FIXED_NAMESPACE
        if tolerance.constraint_module is not None:
            path = module_path_of(tolerance.constraint_module, directory)
            try:
                namespace = namespace_for(path)
            except ConstraintModuleError as error:
                if str(error) not in said_set:
                    said_set.add(str(error))
                    file, position = _written_at(
                        spec, directory_spec, choice,
                        "tolerance.constraint_module", app)
                    fault_list.append(Fault(E_FaultKind.REFUSED, file,
                                            position, str(error)))
                continue
        for expression in tolerance.constraints or ():
            reason = constraint_fault_of(expression, namespace)
            if reason is None or reason in said_set: continue
            said_set.add(reason)
            file, position = _written_at(spec, directory_spec, choice,
                                         CONSTRAINTS_VALUE_KEY, app)
            fault_list.append(Fault(E_FaultKind.REFUSED, file, position,
                                    "constraint %s" % reason))
    return fault_list


def _written_at(spec, directory_spec, choice, key, app):
    """
    RETURN: (str, Position), the file and the place where 'key' stands for
            'choice' -- the choice's own word, else the application's
            root, else the directory's 'app_defaults' -- as provenance
            reads them; the application's own place where none records it.
    """
    choice_position_db = (spec.choice_position_db or {}).get(choice, {})
    for file, position_db in (
            (spec.source_file, choice_position_db),
            (spec.source_file, spec.position_db or {})):
        if key in position_db: return file, position_db[key]
    conf_position_db = getattr(directory_spec, "app_defaults_position_db",
                               None) or {}
    if key in conf_position_db:
        conf_file_db = getattr(directory_spec, "app_defaults_file_db",
                               None) or {}
        return conf_file_db.get(key, "hwut.conf"), conf_position_db[key]
    return app.source_file, app.position


@dataclass(frozen=True, slots=True)
class ExplorationResult:
    """What one TEST directory yields: the set of what exists, every
    fault met on the way, and every file REFUSED as a candidate by its
    name (E-41) -- (name, reason), reported and never silent."""
    app_set:       CTestAppSet
    fault_list:    tuple
    refused_tuple: tuple = ()
    #  THE CONFIGURATION THAT CANNOT BE READ (ND7, services E-190): every
    #  fault of a 'HWUT_ROOT/setup.conf' or 'hwut.conf' at this directory or
    #  above it. Where one stands, no case here runs: each fails by name.
    conf_fault_tuple: tuple = ()


def conf_fault_f(fault):
    """
    RETURN: bool, True if 'fault' says a configuration file --
            'hwut.conf' or 'HWUT_ROOT/setup.conf' -- does not READ as written:
            a syntax, a key refused or unknown, a value of the wrong
            shape;
            False, else: a test's header, a candidate, no file at all,
            or a DIRECTORY conflict -- keys that read, whose values
            disagree with what the directory offers ('dependency' naming
            a test that is not there), answered case by case (P-6).
    """
    from hwut.auxiliary.no_entry import root_conf_path_f
    path = getattr(fault, "file", None) or ""
    if os.path.basename(path) != finder.CONF_NAME \
       and not root_conf_path_f(path): return False
    return getattr(fault, "kind", None) is not E_FaultKind.DIRECTORY


def governed(result, above_tuple):
    """
    RETURN: ExplorationResult, 'result' carrying in 'conf_fault_tuple'
            the faults of the configuration that governs it -- those
            of the files above it ('above_tuple', as the walk met them)
            and of its own 'hwut.conf'.
    """
    from dataclasses import replace
    own_tuple = tuple(f for f in result.fault_list if conf_fault_f(f))
    return replace(result, conf_fault_tuple=tuple(above_tuple) + own_tuple)


def explore(directory, interview_runner=None, inherited=None):
    """
    RETURN: ExplorationResult -- the CTestAppSet of 'directory' and the
            accumulated faults.

    'interview_runner' calls a candidate that neither carrier speaks for
    and returns its '--hwut-info' answer; the default runs it under
    procsitter (R-44). It is a parameter so that a test may drive the
    third carrier without a process.

    'inherited' is the DirectorySpec the CONFIGURATION TREE hands down
    (R-69): its inheritable fields govern where this directory states
    no word of its own; the directory's own 'hwut.conf' wins field by
    field, 'app_defaults' parameter by parameter.
    """
    fault_list = []

    #  hwut.conf FIRST: its 'ignore' governs the walk, its 'apps' carries
    #  the header-less files.
    text = finder.conf_text(directory)
    if text is None:
        directory_spec, conf_app_db = DirectorySpec(language_setup={},
                                                    dependency={}), {}
    else:
        directory_spec, conf_app_db, conf_fault_list = \
                                      reader.read_conf(text, finder.CONF_NAME)
        fault_list.extend(conf_fault_list)
        #  A VARIANT GROUP IS THE ROOT'S ALONE (tree_explorer). A test
        #  directory's own conf is read HERE and not by the walk, so
        #  the refusal has to stand here too, or the one place the key
        #  is most tempting to write is the one place nobody checks.
        if directory_spec is not None:
            from .tree_explorer import (ROOT_CONF_ONLY_REASON_DB,
                                        root_only_fault)
            for name in ROOT_CONF_ONLY_REASON_DB:
                if getattr(directory_spec, name):
                    fault_list.append(root_only_fault(
                        name, finder.CONF_NAME, directory_spec.position))
        if directory_spec is None:
            directory_spec = DirectorySpec(language_setup={},
                                           dependency={})
    if inherited is not None:
        from .tree_explorer import inherited_spec
        directory_spec = inherited_spec(inherited, directory_spec)

    #  THE WALK, then the headers.
    app_db = {}
    silent_list = []
    candidate_list = finder.candidate_list(directory, directory_spec.ignore,
                                           directory_spec.admit)
    refused_list   = []
    for name in candidate_list:
        with open(os.path.join(directory, name), "r",
                  encoding="utf-8", errors="replace") as fh:
            content = fh.read()
        spec, file_fault_list = reader.read_header(content, name)
        fault_list.extend(file_fault_list)
        if file_fault_list:              continue      # refused, not guessed
        if spec is None:
            #  NEITHER CARRIER SPEAKS, so this is NO TEST APPLICATION
            #  (X-SILENT). A file says it is one by carrying 'hwut { }',
            #  or its directory says so under 'apps'; nothing is guessed
            #  and nothing is asked. It is not a fault -- a helper, a log
            #  and a table are all ordinary -- but the run NAMES the
            #  silent files once at its end, so a test that stopped being
            #  seen does not vanish without a word.
            if name in conf_app_db:      continue
            if interview_runner is not None:
                #  An injected runner still asks: the interview lives on
                #  as 'hwut.renovate's reader, not as a carrier.
                spec = hwut_info_interview.interview(directory, name,
                                                     runner=interview_runner)
            if spec is None:
                silent_list.append(name)
                continue
        app = _resolve(spec, directory_spec, directory)
        pair_fault_list = _execute_interactive_refused(app) \
                          + _constraint_module_refused(app, directory, spec,
                                                       directory_spec)
        if pair_fault_list:
            fault_list.extend(pair_fault_list)
            continue                                 # refused, not guessed
        app_db[name] = app

    #  CROSS-CHECK -- only knowable once both carriers are read.
    for name, spec in conf_app_db.items():
        if name in app_db:
            fault_list.append(Fault(
                E_FaultKind.DIRECTORY, finder.CONF_NAME, spec.position,
                "'%s' carries a header AND is named under 'apps': one "
                "file, one carrier" % name))
            continue
        if not os.path.isfile(os.path.join(directory, name)):
            fault_list.append(Fault(
                E_FaultKind.DIRECTORY, finder.CONF_NAME, spec.position,
                "'apps' names '%s', which does not exist" % name))
            continue
        app = _resolve(spec, directory_spec, directory)
        pair_fault_list = _execute_interactive_refused(app) \
                          + _constraint_module_refused(app, directory, spec,
                                                       directory_spec)
        if pair_fault_list:
            fault_list.extend(pair_fault_list)
            continue                                 # refused, not guessed
        app_db[name] = app


    #  SATISFIABILITY -- the dependency graph is complete only now, and
    #  no verdict enters it: what cannot be reached is knowable here.
    misdep_set, graph_fault_list = satisfiability.check(
        app_db         = app_db,
        dependency_db  = directory_spec.dependency,
        collision_list = directory_spec.collision,
        conf_file      = finder.CONF_NAME,
        position       = directory_spec.position)
    fault_list.extend(graph_fault_list)

    #  A CONSTRAINT MODULE IS NO WALLFLOWER (ruled 2026-11-18): like a
    #  pype, it stands beside the tests that name it and is no test.
    module_set = _constraint_module_set(app_db, directory)
    silent_list = [name for name in silent_list
                   if os.path.abspath(os.path.join(directory, name))
                      not in module_set]

    return ExplorationResult(
        app_set    = CTestAppSet(directory      = directory,
                                 app_db         = app_db,
                                 directory_spec = directory_spec,
                                 misdep_set     = misdep_set,
                                 silent_tuple   = tuple(sorted(silent_list))),
        fault_list    = tuple(fault_list),
        refused_tuple = tuple(refused_list))


def _language_of(spec, directory_spec):
    """
    RETURN: [0] str | None, the language of the test application: the
                header's 'language' word where stated, else the one
                whose 'language-setup' entry claims the file's
                extension, else None -- an EXECUTABLE, the she-bang
                decides (R-73).
            [1] bool, True where [0] was DERIVED from the extension
                rather than stated: never silent.
    """
    if spec.language is not None: return spec.language, False
    setup_db = getattr(directory_spec, "language_setup", None) or {}
    suffix   = os.path.splitext(spec.source_file)[1]
    if not suffix: return None, False
    for language, setup in setup_db.items():
        if suffix in setup.extensions: return language, True
    return None, False


def _resolve(spec, directory_spec=None, directory=None):
    """
    RETURN: CTestApp, 'spec' folded: the directory's 'app_defaults' is the
            outermost default, the application's own root the next, and a
            choice's own value stands over both.

    The provenance of every value is settled here, while the three
    sources still stand apart, and travels in 'origin_db'. 'directory'
    is the test directory: a conf above it is named from there.
    """
    app_defaults = getattr(directory_spec, "app_defaults", None) \
                  if directory_spec is not None else None

    base = TestParameters()
    if app_defaults is not None: base = base.overwritten_by(app_defaults)
    base = base.overwritten_by(spec.root_parameters)

    choice_db = {}
    origin_db = {}
    for name, parameters in spec.choice_db.items():
        choice_db[name] = base.overwritten_by(parameters)
        origin_db[name] = provenance.of_choice(spec, name, app_defaults,
                                               directory_spec, directory)

    language, derived_f = _language_of(spec, directory_spec)
    return CTestApp(source_file = spec.source_file,
                    title       = spec.title,
                    language    = language,
                    language_derived_f = derived_f,
                    choice_db   = choice_db,
                    root        = base,
                    origin      = spec.origin,
                    position    = spec.position,
                    origin_db   = origin_db,
                    doc         = getattr(spec, "doc", None))
