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
from .specification import (CTestApp, CTestAppSet, DirectorySpec,
                            TestParameters)


@dataclass(frozen=True, slots=True)
class ExplorationResult:
    """What one TEST directory yields: the set of what exists, and every
    fault met on the way."""
    app_set:    CTestAppSet
    fault_list: tuple


def explore(directory, interview_runner=None):
    """
    RETURN: ExplorationResult -- the CTestAppSet of 'directory' and the
            accumulated faults.

    'interview_runner' calls a candidate that neither carrier speaks for
    and returns its '--hwut-info' answer; the default runs it under
    procsitter (R-44). It is a parameter so that a test may drive the
    third carrier without a process.
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
        if directory_spec is None:
            directory_spec = DirectorySpec(language_setup={},
                                           dependency={})

    #  THE WALK, then the headers.
    app_db = {}
    for name in finder.candidate_list(directory, directory_spec.ignore):
        with open(os.path.join(directory, name), "r",
                  encoding="utf-8", errors="replace") as fh:
            content = fh.read()
        spec, file_fault_list = reader.read_header(content, name)
        fault_list.extend(file_fault_list)
        if file_fault_list:              continue      # refused, not guessed
        if spec is None:
            #  NEITHER CARRIER SPEAKS. The file may be an hwut 1.0 test
            #  application, which predates the trigger: ask it (R-44).
            if name in conf_app_db:      continue
            spec = hwut_info_interview.interview(directory, name,
                                                 runner=interview_runner)
            if spec is None:             continue
        app_db[name] = _resolve(spec, directory_spec)

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
        app_db[name] = _resolve(spec, directory_spec)

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
                                 misdep_set     = misdep_set),
        fault_list = tuple(fault_list))


def _resolve(spec, directory_spec=None):
    """
    RETURN: CTestApp, 'spec' folded: the directory's 'default_app' is the
            outermost default, the application's own root the next, and a
            choice's own value stands over both.

    The provenance of every value is settled here, while the three
    sources still stand apart, and travels in 'origin_db'.
    """
    default_app = getattr(directory_spec, "default_app", None) \
                  if directory_spec is not None else None

    base = TestParameters()
    if default_app is not None: base = base.overwritten_by(default_app)
    base = base.overwritten_by(spec.root_parameters)

    choice_db = {}
    origin_db = {}
    for name, parameters in spec.choice_db.items():
        choice_db[name] = base.overwritten_by(parameters)
        origin_db[name] = provenance.of_choice(spec, name, default_app,
                                               directory_spec)

    return CTestApp(source_file = spec.source_file,
                    title       = spec.title,
                    language    = spec.language,
                    choice_db   = choice_db,
                    origin      = spec.origin,
                    position    = spec.position,
                    origin_db   = origin_db)
