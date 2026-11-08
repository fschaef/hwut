"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE DEPLOY RUNG of the provision ladder (P-18; intend/26 o-47) --
         an application stating 'deploy' gets ONE DEPLOY node: supported
         by the build actions that build it, supporting every TEST node of
         its file.

             build[make f] ==> deploy[f] ==> f a
                                         ==> f b

         A deploy broken, its tests FAIL; a build broken, its deploy and
         its tests FAIL. The deploy runs once per run, never per choice.
______________________________________________________________________________
"""
from .form import CPlanNode, CPlanLink, E_LinkKind


def deploy_nodes(case_list, name_of, build_link_list):
    """
    RETURN: [0] list[CPlanNode], one DEPLOY node per file whose case
                states 'deploy { flash }', in first-met order.
            [1] list[CPlanLink], the SUPPORTS links: each DEPLOY node to
                every TEST node of its file, and every BUILD node that
                supports a TEST node of that file to the DEPLOY node.

    'build_link_list' is the build rung's SUPPORTS links; 'name_of' maps
    (file, choice) to the TEST node's name.
    """
    file_list = []
    for case in case_list:
        deploy = case.parameters.deploy
        if deploy is None or not deploy.flash: continue
        if case.source_file not in file_list:
            file_list.append(case.source_file)

    node_list = []
    link_list = []
    file_of   = {name: pair[0] for pair, name in name_of.items()}
    for file in file_list:
        node = CPlanNode.deploy(file)
        node_list.append(node)
        builder_list = []
        for link in build_link_list:
            if file_of.get(link.target) != file:  continue
            if link.source in builder_list:       continue
            builder_list.append(link.source)
        for builder in builder_list:
            link_list.append(CPlanLink(E_LinkKind.SUPPORTS, builder,
                                       node.name()))
        for pair, target in name_of.items():
            if pair[0] != file: continue
            link_list.append(CPlanLink(E_LinkKind.SUPPORTS, node.name(),
                                       target))
    return node_list, link_list
