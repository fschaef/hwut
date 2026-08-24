"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Settle which cases can be reached at all.

'dependency' is an ORDERING relation: it says that one case ran to
completion before another started, and no verdict enters it. So whether a
case's dependencies CAN BE MET is a property of the graph alone, and the
graph is complete once both carriers are read -- before anything runs.

A case carries '[MISDEP]' where its dependencies cannot be met:

    it stands in a dependency cycle
    it depends on a case that stands in one
    it depends on a case that carries [MISDEP]
    it names a target the directory does not offer

The cycle itself is a DIRECTORY failure and is named there; the token on a
case says only that the case cannot be reached.
______________________________________________________________________________
"""
from .fault         import Fault, E_FaultKind
from .configuration_tree import Target


def check(app_db, dependency_db, collision_list, conf_file, position):
    """
    RETURN: [0] frozenset, the cases -- '(source_file, choice)' pairs --
                whose dependencies cannot be met.
            [1] list[Fault], a DIRECTORY fault per target naming what the
                directory does not offer, and one naming each cycle.

    'dependency_db' maps Target to a tuple of Targets; 'collision_list'
    holds Targets that are checked for existence and nothing more --
    what a collision MEANS is the orchestrator's affair.
    """
    fault_list  = []
    unknown_set = set()

    for target in collision_list:
        if not _known_f(target, app_db):
            fault_list.append(_unknown_fault(target, "collision",
                                             conf_file, position))

    edge_db = {}
    for target, needed_list in (dependency_db or {}).items():
        if not _known_f(target, app_db):
            fault_list.append(_unknown_fault(target, "dependency",
                                             conf_file, position))
            continue
        case_list = _expanded(target, app_db)
        bad_f     = False
        needed_case_list = []
        for needed in needed_list:
            if not _known_f(needed, app_db):
                fault_list.append(_unknown_fault(needed, "dependency",
                                                 conf_file, position))
                bad_f = True
                continue
            needed_case_list.extend(_expanded(needed, app_db))
        for case in case_list:
            edge_db.setdefault(case, []).extend(needed_case_list)
            if bad_f: unknown_set.add(case)

    cycle_list = _cycle_list(edge_db)
    for cycle in cycle_list:
        fault_list.append(Fault(
            E_FaultKind.DIRECTORY, conf_file, position,
            "dependency cycle: %s"
            % " -> ".join([str(Target(*case)) for case in cycle]
                          + [str(Target(*cycle[0]))])))

    poisoned_set = set(unknown_set)
    for cycle in cycle_list:
        poisoned_set.update(cycle)

    #  What depends on a poisoned case is poisoned too, however far away.
    while True:
        added_f = False
        for case, needed_list in edge_db.items():
            if case in poisoned_set: continue
            if any(needed in poisoned_set for needed in needed_list):
                poisoned_set.add(case)
                added_f = True
        if not added_f: break

    return frozenset(poisoned_set), fault_list


def _known_f(target, app_db):
    """RETURN: bool, the directory offers this target."""
    app = app_db.get(target.file)
    if app is None:                 return False
    if target.choice is None:       return True
    return target.choice in app.choice_db


def _expanded(target, app_db):
    """
    RETURN: list, the '(source_file, choice)' cases the target names --
            one, or every choice of the file where it names none.
    """
    app = app_db[target.file]
    if target.choice is not None:
        return [(target.file, target.choice)]
    return [(target.file, choice) for choice in app.choice_db]


def _unknown_fault(target, key, conf_file, position):
    """RETURN: Fault, DIRECTORY: a target the directory does not
    offer."""
    return Fault(
        E_FaultKind.DIRECTORY, conf_file, position,
        "'%s' names '%s', which this directory does not offer"
        % (key, target))


def _cycle_list(edge_db):
    """
    RETURN: list[list], each a cycle of cases in the order met; empty
            where the graph is acyclic.

    Depth-first, the path kept: an edge back into the path closes a
    cycle, and the path from that point IS the cycle.
    """
    result    = []
    seen_set  = set()
    found_set = set()

    def walk(case, path):
        """RETURN: None. Depth-first from 'case', 'path' the way here."""
        if case in path:
            cycle = path[path.index(case):]
            key   = frozenset(cycle)
            if key not in found_set:
                found_set.add(key)
                result.append(cycle)
            return
        if case in seen_set: return
        seen_set.add(case)
        for needed in edge_db.get(case, ()):
            walk(needed, path + [case])

    for case in sorted(edge_db, key=lambda c: (c[0], c[1] or "")):
        walk(case, [])
    return result
