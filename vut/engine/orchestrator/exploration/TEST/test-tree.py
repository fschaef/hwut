#! /usr/bin/env python3
#
# @hwut {
#     title      = "Tree walk: markers found, configuration folded down"
#     choices    = ["inherit", "locals", "marker", "root",
#                   "stream", "walk"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE TREE WALK (R-69) -- finding test directories, folding the
         configuration down.

CHOICES: walk, inherit, marker, locals, root, stream;

DESCRIPTION:

walk     three levels, two test directories, walk order; the walk does
         not descend into a test directory.

inherit  'app_defaults' flows down and merges parameter by parameter;
         a level's own word wins; a test directory's own 'hwut.conf'
         wins last.

marker   'test_directory' renames the marker for everything BELOW the
         level that states it; the default 'TEST' holds elsewhere.

locals   a LOCAL key at a tree level ('on_entry', 'collision', ...):
         a fault, and it flows nowhere.

stream   the generators and the snapshots walk the SAME directories in
         the SAME order (E-71): 'explore_tree_stream' against
         'explore_tree', 'of_tree_stream' against 'of_tree' -- and the
         stream's fault accumulator is whole once it is exhausted.
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile
from config import HwutRunner                                # noqa: F401

from vut.engine.orchestrator.exploration.tree_explorer import (explore_tree,
                                                               explore_tree_stream,
                                                               RootConfMissing)
from vut.test_writing_support.python.script_runner import tree_boundary  # noqa: E402


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def tree_of(file_db):
    """
    RETURN: [0] CTreeExploration of a tree holding 'file_db'
                (relative path -> content).
            [1] str, the root, for the caller to remove.
    """
    root = tempfile.mkdtemp(prefix="vut_walk_")
    #  THE TREE'S BOUNDARY: the climb stops here (see tree_explorer).
    tree_boundary(root)
    for relative, content in file_db.items():
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(content)
    return explore_tree(root), root


def show(tree, detail=None):
    """
    RETURN: None. Every test directory in walk order, its
            applications, and -- where 'detail' names a parameter --
            that parameter per choice-less application.
    """
    for directory, result in tree:
        name_list = sorted(result.app_set.app_db)
        print("    %-24s %s" % (directory, ", ".join(name_list)))
        if detail is None: continue
        for name in name_list:
            app = result.app_set.app_db[name]
            print("        %-12s %s=%r"
                  % (name, detail,
                     getattr(app.choice_db[None], detail)))
    for fault in tree.fault_tuple:
        print("    FAULT %s" % fault)


def test_walk():
    """RETURN: None. Order, and no descent into a test directory."""
    tree, root = tree_of({
        "alpha/TEST/test-a.py":        '# @hwut { title = "A" }\n',
        "alpha/TEST/deeper/unrelated": 'not walked\n',
        "beta/gamma/TEST/test-b.py":   '# @hwut { title = "B" }\n',
        "beta/plain/readme.txt":       'no tests here\n',
    })
    try:
        banner("two test directories, walk order")
        show(tree)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_inherit():
    """RETURN: None. The configuration tree, three levels deep."""
    tree, root = tree_of({
        "hwut.conf":            'hwut { app_defaults { tolerance { numeric_ratio = 0.5 }\n'
                                '                     pype = "root.pype" '
                                '} }\n',
        "sub/hwut.conf":        'hwut { app_defaults { tolerance { numeric_ratio = 0.1 } } '
                                '}\n',
        "sub/TEST/test-a.py":   '# @hwut { title = "A" }\n',
        "sub/TEST/hwut.conf":   'hwut { app_defaults { pype = '
                                '"own.pype" } }\n',
        "other/TEST/test-b.py": '# @hwut { title = "B" }\n',
    })
    try:
        banner("parameter by parameter: the nearer word wins")
        show(tree, detail="tolerance")
        banner("the untouched sibling still flows from the root")
        show(tree, detail="pype")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_marker():
    """RETURN: None. 'test_directory' renames the marker below."""
    tree, root = tree_of({
        "hwut.conf":              'hwut { test_directory = "checks" }\n',
        "one/checks/test-a.py":   '# @hwut { title = "A" }\n',
        "one/TEST/not-found.py":  '# @hwut { title = "Ghost" }\n',
    })
    try:
        banner("the marker is 'checks'; 'TEST' is an ordinary name")
        show(tree)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_locals():
    """RETURN: None. A local key at a tree level."""
    tree, root = tree_of({
        "hwut.conf":          'hwut { on_entry  = "prepare.sh"\n'
                              '       collision = ["test-a.py"] }\n',
        "TEST/test-a.py":     '# @hwut { title = "A" }\n',
    })
    try:
        banner("named, faulted, and not flowed")
        show(tree)
        for directory, result in tree:
            spec = result.app_set.directory_spec
            print("    %-24s on_entry=%r collision=%r"
                  % (directory, spec.on_entry,
                     [str(x) for x in spec.collision]))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_root():
    """RETURN: None. THE ROOT IS ITSELF A CANDIDATE: a walk started IN
    a test directory explores THAT directory, and not only the ones
    below it. Standing where the tests are is the ordinary case -- it
    is where an author works -- and a walk that enters only CHILDREN
    named 'TEST' looked everywhere except where it already stood.
    """
    file_db = {
        "TEST/hwut.conf": 'hwut {\n    on_entry = "true"\n}\n',
        "TEST/test-a.py": '# @hwut { title = "A"  choices = ["one","two"] }\n',
        "TEST/test-b.py": '# @hwut { title = "B" }\n',
    }

    banner("started ABOVE the test directory")
    tree, root = tree_of(file_db)
    for where, result in tree:
        print("    %-8s %s" % (where, ", ".join(
              sorted(a.source_file for a in result.app_set))))

    banner("started IN the test directory -- the root itself")
    for where, result in explore_tree(os.path.join(root, "TEST")):
        print("    %-8s %s" % (where, ", ".join(
              sorted(a.source_file for a in result.app_set))))
    shutil.rmtree(root, ignore_errors=True)

    banner("a root that is NOT a test directory, and holds none")
    plain = tempfile.mkdtemp(prefix="vut_walk_")
    tree_boundary(plain)
    print("    directories explored: %d" % len(list(explore_tree(plain))))
    shutil.rmtree(plain, ignore_errors=True)

    banner("and one with NO boundary above it: refused, not guessed")
    naked = tempfile.mkdtemp(prefix="vut_walk_")
    try:
        explore_tree(naked)
        print("    NOT REFUSED -- which would be wrong")
    except RootConfMissing:
        print("    RootConfMissing, as owed")
    shutil.rmtree(naked, ignore_errors=True)


def test_stream():
    """RETURN: None. Generator and snapshot, side by side (E-71).

    A tree of four test directories at three depths, one with a
    faulted tree-level 'hwut.conf', so order and faults both have
    something to disagree about. After the FIRST yield no fault is
    known yet -- the faulted level lies later in the walk -- which is
    what shows the stream hands a directory over before walking on.
    """
    from vut.engine.orchestrator.exploration.selection import (of_tree,
                                                               of_tree_stream)
    from vut.engine.orchestrator.plan.wish             import Wish
    tree, root = tree_of({
        "zeta/TEST/test-z.py":         '# @hwut { title = "Z" }\n',
        "alpha/TEST/test-a.py":        '# @hwut { title = "A" choices = ["x","y"] }\n',
        "alpha/beta/TEST/test-b.py":   '# @hwut { title = "B" }\n',
        "mid/hwut.conf":               'hwut { on_entry = "prepare.sh" }\n',
        "mid/TEST/test-m.py":          '# @hwut { title = "M" }\n',
    })
    try:
        banner("explore_tree_stream against explore_tree")
        fault_list  = []
        stream      = explore_tree_stream(root, fault_list=fault_list)
        first, _    = next(stream)
        print("    first yield              %s" % first)
        print("    faults known by then     %d" % len(fault_list))
        stream_list = [first] + [directory for directory, _ in stream]
        snap_list   = [directory for directory, _ in tree]
        print("    stream                   %s" % ", ".join(stream_list))
        print("    snapshot                 %s" % ", ".join(snap_list))
        print("    same order               %s" % (stream_list == snap_list))
        print("    faults stream/snapshot   %d/%d, same: %s"
              % (len(fault_list), len(tree.fault_tuple),
                 [str(f) for f in fault_list]
                 == [str(f) for f in tree.fault_tuple]))

        banner("of_tree_stream against of_tree")
        wish     = Wish()
        snapshot = of_tree(root, wish)
        row_list = list(of_tree_stream(root, wish))
        s_dir    = [directory for directory, _, _, _ in row_list]
        s_case   = [(c.directory, str(c.case))
                    for _, _, _, case_list in row_list for c in case_list]
        n_case   = [(c.directory, str(c.case)) for c in snapshot.case_list]
        print("    stream                   %s" % ", ".join(s_dir))
        print("    snapshot                 %s"
              % ", ".join(snapshot.result_db))
        print("    same order               %s"
              % (s_dir == list(snapshot.result_db)))
        print("    cases stream/snapshot    %d/%d, same order: %s"
              % (len(s_case), len(n_case), s_case == n_case))
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "Tree walk: markers found, configuration folded down;", {
        "walk":    test_walk,
        "inherit": test_inherit,
        "root":       test_root,
        "marker":  test_marker,
        "locals":  test_locals,
        "stream":  test_stream,
    }).run()
