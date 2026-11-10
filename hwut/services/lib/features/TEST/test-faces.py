#! /usr/bin/env python3
#
# @hwut {
#     title      = "hwut.features.init, register and tree on scratch trees"
#     choices {
#         init     { features = ["init-writes"] }
#         register { features = ["register-notes"] }
#         tree     { features = ["tree-prints"] }
#         bubbles  { features = ["forest-spans-bubbles"] }
#         prototypes { features = ["tree-prints", "register-notes"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FEATURE FACES that read and begin (spec 43 sections 5, 6),
         each called as a person calls it, on a scratch tree.

CHOICES: init, register, tree, bubbles, prototypes;

init      an empty forest and doc file written where none stands, their
          headers saying how they are written, no map; one standing kept
          and the other written; refused where both stand, where no
          'hwut-root.conf' stands, and for a word it does not take.

register  the notes, each with 'did you mean' where an id is near: a
          documented feature in no forest line, an undocumented root, a
          link to an id that stands nowhere and one to a retired id, a file
          of the past; a tree that agrees: 'nothing disagrees'; no forest,
          refused; a file that states a fault, FAULT.

tree      the forest with titles, roots first, children indented, the
          unplaced after it; '-e' with the outside's names; '--list' one id
          per line; a subtree; an id that stands nowhere, refused with
          'did you mean'; a word it does not take.

bubbles   a bubble without a forest of its own is the forest's above: its
          links are judged there, called inside it too; a bubble with one
          begins its own features (the showcase, 2026-11-08): not walked
          from above, NOTEd.

prototypes (intend/44) the tree shows the instances where their owners
          stand, each with the title that documents it -- its own block,
          its member's, its prototype's -- and the prototypes as declared
          under '(prototypes)'; '--list' the instances, no prototype, no
          member; 'register' notes a prototype nobody aggregates and a
          member documented by nothing.
______________________________________________________________________________
"""
import os
import sys

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

import _fixture as fx                                            # noqa E402
from hwut.services.lib.features import init, register, tree    # noqa E402


def run_init():
    """RETURN: None. 'hwut.features.init'."""
    root = fx.tree()
    fx.call("hwut.features.init", init, [], root)
    for each in ("hwut-feature-forest.csv", "hwut-feature-doc.dat"):
        print("    [%s]" % each)
        with open(os.path.join(root, each)) as fh:
            for line in fh.read().split("\n"):
                if line: print("    | %s" % line)
    fx.shown(root, "hwut-feature-external-map.csv")
    fx.call("again: both stand", init, [], root)
    os.remove(os.path.join(root, "hwut-feature-doc.dat"))
    fx.call("the doc file gone: only it is written", init, [], root)
    fx.call("a word it does not take", init, ["gw"], root)
    fx.call("no hwut-root.conf", init, [], "/")


def run_register():
    """RETURN: None. 'hwut.features.register'."""
    root = fx.gateway()
    fx.test(root, "bus/TEST/test-bus.sh",
            ['features = ["decod", "gone"]'])
    with open(os.path.join(root, "hwut-feature-doc.dat"), "a") as fh:
        fh.write("\n[[gone:retired]]\nOnce.\n")
    fx.write(root, "old/TEST/hwut-features.conf", "features { }\n")
    fx.call("hwut.features.register", register, [], root)
    fx.call("called below the top: the same notes", register, [],
            os.path.join(root, "gw/TEST"))
    agree = fx.tree({"hwut-feature-forest.csv": "gateway : fwd\n",
                     "hwut-feature-doc.dat": "[[gateway]]\nThe gateway.\n"})
    fx.test(agree, "gw/TEST/test-fwd.sh", ['features = ["fwd"]'])
    fx.call("a tree that agrees", register, [], agree)
    fx.call("a word it does not take", register, ["gw"], agree)
    os.remove(os.path.join(agree, "hwut-feature-forest.csv"))
    fx.call("no forest", register, [], agree)
    fx.write(agree, "hwut-feature-forest.csv", "a : b\nb : a\n")
    fx.call("a forest that states a fault", register, [], agree)


def run_tree():
    """RETURN: None. 'hwut.features.tree'."""
    root = fx.gateway()
    fx.call("hwut.features.tree", tree, [], root)
    fx.call("-e", tree, ["-e"], root)
    fx.call("--list", tree, ["--list"], root)
    fx.call("a subtree", tree, ["forwarding"], root)
    fx.call("a subtree, --list", tree, ["forwarding", "--list"], root)
    fx.call("an id that stands nowhere", tree, ["forwardng"], root)
    fx.call("a word it does not take", tree, ["-b"], root)
    fx.write(root, "hwut-feature-external-map.csv", "nobody ; X\n")
    fx.call("a map that names an id the forest does not hold", tree, [],
            root)


def run_bubbles():
    """RETURN: None. The forest and the bubbles below its root."""
    root = fx.gateway()
    fx.write(root, "inner/hwut-root.conf", "hwut {\n}\n")
    fx.test(root, "inner/x/TEST/test-x.sh", ['features = ["fwdd"]'])
    fx.write(root, "own/hwut-root.conf", "hwut {\n}\n")
    fx.write(root, "own/hwut-feature-forest.csv", "show : case\n")
    fx.write(root, "own/hwut-feature-doc.dat", "[[show]]\nThe showcase.\n")
    fx.test(root, "own/y/TEST/test-y.sh", ['features = ["case", "nix"]'])
    fx.call("from the top", register, [], root)
    fx.call("inside the bubble without a forest", register, [],
            os.path.join(root, "inner"))
    fx.call("inside the bubble with one", register, [],
            os.path.join(root, "own"))
    fx.call("its forest", tree, [], os.path.join(root, "own"))


def run_prototypes():
    """RETURN: None. Two ports aggregating one prototype."""
    root = fx.tree({
        "hwut-feature-forest.csv":
            "gateway   : can-port, most-port\n"
            "can-port  : +port\nmost-port : +port\n"
            "+port     : receive, send, +errors\n"
            "+errors   : bus-off, overrun\n+spare : idle\n",
        "hwut-feature-doc.dat":
            "[[gateway]]\nThe gateway forwards what reaches it.\n"
            "[[+port]]\nWhat every port does.\n"
            "[[receive]]\nA frame is received.\n"
            "[[most-port+receive]]\nA MOST frame is received, in its slot.\n"})
    fx.test(root, "can/TEST/test-rx.sh",
            ['features = ["can-port+receive", "receive"]'])
    fx.call("hwut.features.tree", tree, [], root)
    fx.call("--list", tree, ["--list"], root)
    fx.call("hwut.features.register", register, [], root)


if __name__ == "__main__":
    try:
        HwutRunner(
            argv       = sys.argv,
            title      = "hwut.features.init, register and tree on "
                         "scratch trees",
            choice_map = {"init": run_init, "register": run_register,
                          "prototypes": run_prototypes,
                          "tree": run_tree, "bubbles": run_bubbles},
        ).run()
    finally:
        fx.removed()
