#! /usr/bin/env python3
#
# hwut {
#     title      = "Tree plan: one plan per directory, walk order"
#     choices    = ["refused", "tree"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE TREE PLAN (P-17) -- one plan per test directory, walk
         order, printed whole.

CHOICES: tree, refused;

DESCRIPTION:

tree     two test directories under one root, one wish: the printed
         tree plan -- entry headings, a report where a directory's
         selection is empty, each entry's canonical plan.

refused  a wish asking the base without a Bookkeeper factory: refused
         at the door.
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile
from config import HwutRunner                                # noqa: F401

from vut.engine.orchestrator.exploration.tree_explorer import explore_tree
from vut.language_support.python.script_runner import tree_boundary  # noqa: E402
from vut.engine.orchestrator.plan.tree import (determine_tree,
                                               print_tree_plan)
from vut.engine.orchestrator.plan.wish import Wish





def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def tree_of():
    """
    RETURN: [0] CTreeExploration  two test directories.
            [1] str               the root, for the caller to remove.
    """
    root = tempfile.mkdtemp(prefix="vut_treeplan_")
    #  THE TREE'S BOUNDARY: every face ascends collecting
    #  'hwut.conf' until it meets this file; a tree without one
    #  is refused, so a fixture states its own.
    tree_boundary(root)
    file_db = {
        "alpha/TEST/hwut.conf":  'hwut { dependency { "test-b.py" = '
                                 '["test-a.py"] } }\n',
        "alpha/TEST/test-a.py":  '# hwut { title = "A"  build = '
                                 '"make" }\n',
        "alpha/TEST/test-b.py":  '# hwut { title = "B" }\n',
        "beta/TEST/test-z.py":   '# hwut { title = "Z" }\n',
    }
    for relative, content in file_db.items():
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as _fh:
            _fh.write(content)
    return explore_tree(root), root


def test_tree():
    """RETURN: None. The tree plan, printed."""
    tree, root = tree_of()
    try:
        banner("everything")
        print_tree_plan(determine_tree(tree, Wish()))

        banner("one glob: 'beta' comes up empty, and says so")
        print_tree_plan(determine_tree(
            tree, Wish(glob_tuple=("test-a.py",))))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_refused():
    """RETURN: None. The base asked without a factory."""
    tree, root = tree_of()
    try:
        banner("'--fail' without a Bookkeeper factory")
        try:
            determine_tree(tree, Wish(fail_f=True))
            print("NOT REFUSED -- a law is broken")
        except AssertionError as error:
            print("REFUSED: %s" % error)
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "Tree plan: one plan per directory, walk order;", {
        "tree":    test_tree,
        "refused": test_refused,
    }).run()
