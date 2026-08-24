"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: DETERMINATION -- the policy that turns a wish and what the
         directory offers into a CTestPlan. The form is next door and
         holds no policy (P-1).

    determine(app_set, task_list, ...) -> CTestPlan

THE STEPS, in order:

    1  SELECT through the one door: 'task_list.get_test_cases(app_set)'.
    2  IMPLICATION CLOSURE over the directory's 'dependency' relation:
       a case required by a selected case enters the plan, marked
       IMPLIED with the target that required it (P-7). The closure runs
       to a fixed point; a case's own declarations give its parameters.
    3  BUILD ACTIONS: the build interview answers which actions the
       selected cases need and which cases each action supports. The
       actions become BUILD nodes, supports-linked (P-5).
    4  SESSIONS: per interactive file holding a selected case, one
       SESSION node, supports-linked to that file's TEST nodes (P-5).
    5  ORDERING LINKS out of 'dependency', restricted to targets that
       stand in the plan and never leaving a [MISDEP] node for a node
       that is not one (the R-35 closure the form asserts).
    6  EXCLUSION SETS out of 'collision', each PRUNED to the members
       covering a TEST node of the plan; a set left with fewer than two
       members constrains nothing and is dropped.

NODE ORDER: BUILD nodes, then SESSION nodes, then TEST nodes in
selection order. Determination is deterministic -- the same wish on the
same directory yields the same plan, and the print may be blessed
byte-exact (P-4).

THE PROVISION LADDER (P-18) is the organising figure: this module
walks the selection and raises the TEST nodes; each HOISTED rung has
its own file, 'provision_<stage>.py' -- build actions
(provision_build.py), the shared facet of execution
(provision_execute.py) -- and acquisition lands someday as one more
rung, not a redesign. The scheduler stays STAGE-BLIND: stage meaning
enters only through node kind, read by the dispatcher alone.
______________________________________________________________________________
"""
from ..exploration.configuration_tree import Target
from .provision_build   import (I_BuildInterview,
                                SpecificationBuildInterview,
                                build_nodes)
from .provision_execute import session_nodes
from .form import (CExclusionSet, CPlanLink, CPlanNode, CTestPlan,
                   E_LinkKind, E_Provenance)


def determine(app_set, task_list, build_interview=None):
    """
    RETURN: [0] CTestPlan, what the wish comes to on this directory.
            [1] list[str], the reports met -- an empty selection says
                so here (P-9), naming no machine-chosen path; empty
                where there is nothing to report.

    'build_interview' answers which build actions the selected cases
    need; the specification's own answer where none is handed down.

    Raises SelectionError out of the task list, unchanged: a wish
    naming what does not exist is refused at the door, by name.
    """
    if build_interview is None:
        build_interview = SpecificationBuildInterview()

    case_list   = list(task_list.get_test_cases(app_set))
    report_list = []
    if not case_list:
        report_list.append("the selection is empty: no test case "
                           "answers the wish")

    case_list, implied_db = _closed(case_list, app_set)

    test_node_list = [
        CPlanNode.test(file       = case.source_file,
                       choice     = case.choice,
                       misdep_f   = case.misdep_f,
                       provenance = (E_Provenance.IMPLIED
                                     if (case.source_file, case.choice)
                                        in implied_db
                                     else E_Provenance.NAMED),
                       implied_by = implied_db.get((case.source_file,
                                                    case.choice)),
                       payload    = case)
        for case in case_list]

    name_of = {(node.file, node.choice): node.name()
               for node in test_node_list}

    build_node_list, build_link_list = \
        build_nodes(build_interview, case_list, name_of)
    session_node_list, session_link_list = \
        session_nodes(case_list, app_set, name_of)

    ordering_link_list = _ordering_links(app_set, name_of, case_list)
    exclusion_list     = _exclusion_sets(app_set, test_node_list)

    plan = CTestPlan(build_node_list + session_node_list + test_node_list,
                     ordering_link_list + build_link_list
                                        + session_link_list,
                     exclusion_list)
    return plan, report_list


def _closed(case_list, app_set):
    """
    RETURN: [0] list[CTestCase], the selected cases and, after them,
                every case the 'dependency' relation requires, to a
                fixed point.
            [1] dict, (file, choice) -> str, the target that required
                an implied case -- the FIRST that required it, so the
                account does not depend on the order of a set.

    A required target the directory does not offer adds nothing: the
    case naming it already carries '[MISDEP]' (R-35).
    """
    dependency_db = app_set.directory_spec.dependency or {}
    present_set   = {(case.source_file, case.choice) for case in case_list}
    result_list   = list(case_list)
    implied_db    = {}

    index = 0
    while index < len(result_list):
        case  = result_list[index]
        index += 1
        for target in _needed_targets(dependency_db, case):
            for pair in _pairs_of_target(target, app_set):
                if pair in present_set: continue
                required = _case_of_pair(pair, app_set)
                if required is None:    continue
                present_set.add(pair)
                implied_db[pair] = str(Target(case.source_file,
                                              case.choice))
                result_list.append(required)
    return result_list, implied_db


def _needed_targets(dependency_db, case):
    """
    YIELD: [0] Target  one target the case depends on -- those stated
                       for the call itself and those stated for its
                       file as a whole.
    """
    for key in (Target(case.source_file, case.choice),
                Target(case.source_file, None)):
        for target in dependency_db.get(key, ()):
            yield target


def _pairs_of_target(target, app_set):
    """
    YIELD: [0] tuple  one (file, choice) the target names -- every
                      choice of the file where it names no choice
                      (R-34); nothing where the directory does not
                      offer the file.
    """
    app = app_set.app_db.get(target.file)
    if app is None: return
    if target.choice is not None:
        if target.choice in app.choice_db:
            yield (target.file, target.choice)
        return
    for choice in _sorted_choices(app):
        yield (target.file, choice)


def _case_of_pair(pair, app_set):
    """
    RETURN: CTestCase, the case of that (file, choice) with its own
            declarations and its '[MISDEP]' marking / None, where the
            directory does not offer it.
    """
    from ..exploration.task_list import _case
    file, choice = pair
    app = app_set.app_db.get(file)
    if app is None or choice not in app.choice_db: return None
    return _case(app, choice, app_set)


def _sorted_choices(app):
    """RETURN: list, the app's choice names sorted; '[None]' for the
    choice-less application."""
    if None in app.choice_db: return [None]
    return sorted(app.choice_db)


def _ordering_links(app_set, name_of, case_list):
    """
    RETURN: list[CPlanLink], one ORDERING link per (required, requiring)
            pair standing in the plan, in plan order.

    A link out of a [MISDEP] node stands only towards another: the
    dependant of an unsatisfiable case is itself unsatisfiable (R-35),
    and a link that would leave the closure is dropped rather than
    offered to a form that refuses it.
    """
    dependency_db = app_set.directory_spec.dependency or {}
    misdep_set    = {(case.source_file, case.choice)
                     for case in case_list if case.misdep_f}
    link_list     = []
    for case in case_list:
        target_name = name_of[(case.source_file, case.choice)]
        for target in _needed_targets(dependency_db, case):
            for pair in _pairs_of_target(target, app_set):
                source_name = name_of.get(pair)
                if source_name is None:                     continue
                if source_name == target_name:              continue
                if pair in misdep_set \
                   and (case.source_file, case.choice) not in misdep_set:
                    continue
                link = CPlanLink(E_LinkKind.ORDERING,
                                 source_name, target_name)
                if link not in link_list: link_list.append(link)
    return link_list


def _exclusion_sets(app_set, test_node_list):
    """
    RETURN: list[CExclusionSet], the directory's collision group,
            pruned to the members covering a TEST node of the plan --
            an empty list where fewer than two members remain, since a
            group of one constrains nothing.

    'DirectorySpec.collision' is ONE group of targets; the plan's form
    carries several, and a directory stating several is exploration's
    affair, not determination's.
    """
    member_list = [str(member)
                   for member in (app_set.directory_spec.collision or ())]
    kept = [member for member in member_list
            if any(_covers_f(member, node) for node in test_node_list)]
    if len(kept) < 2: return []
    return [CExclusionSet(tuple(kept))]


def _covers_f(member, node):
    """
    RETURN: bool, True where the target text 'member' names the TEST
            node -- by its call, or by its file alone.
    """
    return member == node.name() or member == node.file
