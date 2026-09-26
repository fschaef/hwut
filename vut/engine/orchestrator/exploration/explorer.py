"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
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


@dataclass(frozen=True, slots=True)
class ExplorationResult:
    """What one TEST directory yields: the set of what exists, every
    fault met on the way, and every file REFUSED as a candidate by its
    name (E-41) -- (name, reason), reported and never silent."""
    app_set:       CTestAppSet
    fault_list:    tuple
    refused_tuple: tuple = ()


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
            from .tree_explorer import (ROOT_CONF_ONLY_FIELD_TUPLE,
                                        root_only_fault)
            for name in ROOT_CONF_ONLY_FIELD_TUPLE:
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
    candidate_list, refused_list = finder.candidate_list(
                                       directory, directory_spec.ignore)
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
        app = _resolve(spec, directory_spec)
        pair_fault_list = _execute_interactive_refused(app)
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
        app = _resolve(spec, directory_spec)
        pair_fault_list = _execute_interactive_refused(app)
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


def _resolve(spec, directory_spec=None):
    """
    RETURN: CTestApp, 'spec' folded: the directory's 'app_defaults' is the
            outermost default, the application's own root the next, and a
            choice's own value stands over both.

    The provenance of every value is settled here, while the three
    sources still stand apart, and travels in 'origin_db'.
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
                                               directory_spec)

    language, derived_f = _language_of(spec, directory_spec)
    return CTestApp(source_file = spec.source_file,
                    title       = spec.title,
                    language    = language,
                    language_derived_f = derived_f,
                    choice_db   = choice_db,
                    root        = base,
                    origin      = spec.origin,
                    position    = spec.position,
                    origin_db   = origin_db)
