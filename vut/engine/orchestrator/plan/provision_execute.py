"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE EXECUTE RUNG of the provision ladder (P-18) -- the shared
         facet of execution, a standing interactive application,
         becomes one SESSION node per file with SUPPORTS links to its
         choices (P-5); the TEST nodes themselves are the cases,
         raised by 'determine.py' on the same rung.
______________________________________________________________________________
"""
from .form import CPlanNode, CPlanLink, E_LinkKind


def session_nodes(case_list, app_set, name_of):
    """
    RETURN: [0] list[CPlanNode], one SESSION node per interactive file
                holding a case of the plan, in first-met order.
            [1] list[CPlanLink], one SUPPORTS link per case of such a
                file.
    """
    node_list = []
    link_list = []
    seen_set  = set()
    for case in case_list:
        if not case.parameters.interactive:   continue
        if case.source_file not in seen_set:
            seen_set.add(case.source_file)
            node_list.append(CPlanNode.session(case.source_file))
        link_list.append(
            CPlanLink(E_LinkKind.SUPPORTS,
                      "session[%s]" % case.source_file,
                      name_of[(case.source_file, case.choice)]))
    return node_list, link_list
