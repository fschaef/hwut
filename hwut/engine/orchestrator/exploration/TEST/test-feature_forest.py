#! /usr/bin/env python3
#
# @hwut {
#     title      = "The forest of features: lines, roots, and what may not stand"
#     choices {
#         read   { features = ["forest-read"] }
#         faults { features = ["forest-faults-named"] }
#         prototypes       { features = ["forest-prototypes-expand"] }
#         prototype-faults { features = ["forest-prototypes-expand"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut-feature-forest.csv', read (spec 43 section 1; intend/43 T-b,
         T-i, T-o): '<id> : <child>, ...' per line.

CHOICES: read, faults, prototypes, prototype-faults;

read    comments, blanks and whitespace dropped; the roots are what stands
        as no child, in file order; children in line order; a subtree and
        the ancestors of an id; case kept and compared; no file, None.

faults  each named with file and line: no colon, a line naming no child,
        an id that is no id (a dot, a colon, a slash, a glob, a blank), a
        left side twice, a child under two parents, a child twice under
        one, a circle.
______________________________________________________________________________
"""
import sys
import tempfile

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from hwut.engine.orchestrator.exploration.feature_forest \
    import forest_of_text, read_forest, ForestFault                # noqa E402

TEXT = """# the gateway
gateway    :  forwarding,buses     # two
forwarding : fwd , keeporder, dropunknown

buses      : decode
delivery   : onever, Onever
"""


def read():
    """RETURN: None. A forest and what it answers."""
    forest = forest_of_text(TEXT)
    print("roots      ", forest.root_tuple)
    for each in ("gateway", "forwarding", "buses", "delivery"):
        print("children   %-11s %s" % (each, forest.children_of[each]))
    print("parent     keeporder   %s" % forest.parent_of["keeporder"])
    print("subtree    gateway     %s" % (forest.subtree_tuple("gateway"),))
    print("ancestors  decode      %s" % (forest.ancestor_tuple("decode"),))
    print("ancestors  gateway     %s" % (forest.ancestor_tuple("gateway"),))
    print("id_set     %i ids, 'onever' and 'Onever' both: %s"
          % (len(forest.id_set), {"onever", "Onever"} <= forest.id_set))
    print("line_of    dropunknown %i" % forest.line_of["dropunknown"])
    print("no file    %s" % read_forest(tempfile.mkdtemp()))


def faults():
    """RETURN: None. Each fault as it is said."""
    for label, text in (
            ("no colon",      "gateway forwarding\n"),
            ("no child",      "gateway :\n"),
            ("dotted id",     "a.b : c\n"),
            ("colon in child", "a : b:c\n"),
            ("slash",         "a : x/y\n"),
            ("glob",          "a : b*\n"),
            ("blank inside",  "a : b c\n"),
            ("empty child",   "a : b, , c\n"),
            ("left twice",    "a : b\na : c\n"),
            ("two parents",   "a : x\nb : x\n"),
            ("twice under one", "a : x, x\n"),
            ("circle",        "a : b\nb : c\nc : a\n"),
            ("circle of one", "a : a\n")):
        try:
            forest_of_text(text)
            print("%-15s read" % label)
        except ForestFault as fault:
            print("%-15s %s" % (label, fault))


PROTOTYPE_TEXT = """port-a : +show, own
port-b : +show
+show  : greet, +talk
+talk  : ask, answer
"""


def prototypes():
    """RETURN: None. A prototype aggregated by two owners, expanded."""
    forest = forest_of_text(PROTOTYPE_TEXT)
    print("roots      ", forest.root_tuple)
    for each in ("port-a", "port-a+show", "port-b+show", "port-b+talk"):
        print("children   %-12s %s" % (each, forest.children_of[each]))
    print("parent     port-a+answer %s" % forest.parent_of["port-a+answer"])
    print("prototypes  %s" % sorted(forest.prototype_db.items()))
    print("member_of   %s" % sorted(forest.member_of.items()))
    for each in ("show", "greet", "port-a", "port-a+greet"):
        print("prototype_f %-12s %s" % (each, forest.prototype_f(each)))
    print("in id_set   greet %s, port-b+ask %s"
          % ("greet" in forest.id_set, "port-b+ask" in forest.id_set))


def prototype_faults():
    """RETURN: None. Each fault of a prototype as it is said."""
    for label, text in (
            ("undeclared",     "a : +p\n"),
            ("inner undeclared", "a : +p\n+p : m, +q\n"),
            ("two prototypes", "a : +p\n+p : m\n+q : m\n"),
            ("member feature", "a : +p, m\n+p : m\n"),
            ("prototype feature", "a : +p\np : x\n+p : m\n"),
            ("prototype child", "a : +p, p\n+p : m\n"),
            ("prototype twice", "a : +p\n+p : m\n+p : n\n"),
            ("without plus",   "a : +p\n+p : m, q\n+q : n\n"),
            ("circle",         "a : +p\n+p : m, +q\n+q : n, +p\n"),
            ("reached twice",  "a : +p, +q\n+p : m, +q\n+q : n\n")):
        try:
            forest_of_text(text)
            print("%-17s read" % label)
        except ForestFault as fault:
            print("%-17s %s" % (label, fault))


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The forest of features: lines, roots, and what may not stand",
        choice_map = {"read": read, "faults": faults,
                      "prototypes": prototypes,
                      "prototype-faults": prototype_faults},
    ).run()
