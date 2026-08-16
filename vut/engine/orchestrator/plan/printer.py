"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE CANONICAL PRINT of a test plan -- what the service
         'hwut.plan' emits. One text form, byte-stable, one-way: a
         print is never read back as input.

Order is CONSTRUCTION ORDER throughout -- the determiner's account,
verbatim. Sections print '(none)' where empty, so an empty plan and a
truncated print cannot be mistaken for one another.

    NODES        name, kind, then the annotations: '[MISDEP]' and
                 '<= required by <target>'
    LINKS        'x -> y' ordering, 'w ==> t' supports
    EXCLUSIONS   '{ member, member }' -- at most one member standing
                 at a time
______________________________________________________________________________
"""
from .form import E_LinkKind, E_NodeKind, E_Provenance


def print_plan(plan, write=None):
    """
    RETURN: None. Writes the canonical text of 'plan' line by line
            through 'write' -- 'print' where none is given.
    """
    if write is None: write = print

    write("TEST PLAN: %d node(s), %d link(s), %d exclusion set(s)"
          % (len(plan.node_tuple), len(plan.link_tuple),
             len(plan.exclusion_tuple)))

    write("NODES")
    if not plan.node_tuple:
        write("    (none)")
    else:
        width = max(len(node.name()) for node in plan.node_tuple)
        for node in plan.node_tuple:
            write("    %s" % _node_line(node, width))

    write("LINKS")
    if not plan.link_tuple:
        write("    (none)")
    else:
        for link in plan.link_tuple:
            arrow = "->" if link.kind is E_LinkKind.ORDERING else "==>"
            write("    %s %s %s" % (link.source, arrow, link.target))

    write("EXCLUSIONS")
    if not plan.exclusion_tuple:
        write("    (none)")
    else:
        for exclusion in plan.exclusion_tuple:
            write("    { %s }" % ", ".join(exclusion.member_tuple))


def _node_line(node, width):
    """
    RETURN: str, one node's line: the name padded to 'width', the
            kind, then '[MISDEP]' and '<= required by <target>' where
            they apply; no trailing blanks.
    """
    text = "%-*s  %-7s" % (width, node.name(), node.kind.name)
    if node.misdep_f:
        text += "  [MISDEP]"
    if node.provenance is E_Provenance.IMPLIED:
        text += "  <= required by %s" % node.implied_by
    return text.rstrip()
