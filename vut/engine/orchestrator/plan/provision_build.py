"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE BUILD RUNG of the provision ladder (P-18) -- what must be
         BUILT before the selected cases run becomes BUILD nodes with
         SUPPORTS links (P-5); the interview answers which actions.

One file per hoisted rung, 'provision_<stage>.py'; 'determine.py'
walks the ladder and assembles. 'provision_acquire.py' is the empty
rung, created the day acquisition returns.
______________________________________________________________________________
"""
from abc import ABC, abstractmethod

from .form import CPlanNode, CPlanLink, E_LinkKind


class I_BuildInterview(ABC):
    """WHAT MUST BE BUILT BEFORE THE SELECTED CASES RUN. One
    implementation per source of that knowledge; test_run's
    multi-builder is the one the orchestrator hands down."""

    @abstractmethod
    def actions(self, case_list):
        """
        RETURN: sequence of (str, tuple) -- an action's name, and the
                (file, choice) pairs of the cases it supports. Every
                pair names a case of 'case_list'; an action supporting
                no case of it is not answered.
        """


class SpecificationBuildInterview(I_BuildInterview):
    """The interview the SPECIFICATION alone can answer: a case stating
    'build' needs the named framework built for its file, and one
    action serves every case of that file stating it.

    Action name: '<framework> <file>'."""

    def actions(self, case_list):
        """
        RETURN: list of (str, tuple), one entry per (file, framework)
                met, in first-met order, with the cases it supports.
        """
        action_list = []
        index_db    = {}
        for case in case_list:
            build = case.parameters.build
            if build is None or build.framework is None: continue
            key = (case.source_file, build.framework)
            if key not in index_db:
                index_db[key] = len(action_list)
                action_list.append(("%s %s" % (build.framework,
                                               case.source_file), []))
            action_list[index_db[key]][1].append((case.source_file,
                                                  case.choice))
        return [(name, tuple(pair_list))
                for name, pair_list in action_list]


def build_nodes(build_interview, case_list, name_of):
    """
    RETURN: [0] list[CPlanNode], one BUILD node per action answered.
            [1] list[CPlanLink], one SUPPORTS link per case an action
                supports, dropping a pair that names no TEST node of
                the plan.
    """
    node_list = []
    link_list = []
    for action, pair_tuple in build_interview.actions(case_list):
        node = CPlanNode.build(action)
        node_list.append(node)
        for pair in pair_tuple:
            target = name_of.get(pair)
            if target is None: continue
            link_list.append(CPlanLink(E_LinkKind.SUPPORTS,
                                       node.name(), target))
    return node_list, link_list
