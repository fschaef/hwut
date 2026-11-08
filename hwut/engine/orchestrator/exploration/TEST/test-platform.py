#! /usr/bin/env python3
#
# @hwut {
#     title      = "The conf key 'platform': read, or refused by name"
#     choices {
#         reads           { features = ["platform-list-read"] }
#         bubble          { features = ["platform-bubble-decides-alone"] }
#         root-only       { features = ["platform-root-only"] }
#         not-list        { features = ["platform-faults-named"] }
#         empty           { features = ["platform-faults-named"] }
#         bare-name       { features = ["platform-faults-named"] }
#         name-missing    { features = ["platform-faults-named"] }
#         name-doubled    { features = ["platform-faults-named"] }
#         local-keys      { features = ["platform-faults-named"] }
#         kind-missing    { features = ["platform-faults-named"] }
#         kind-unknown    { features = ["platform-faults-named"] }
#         key-unknown     { features = ["platform-faults-named"] }
#         image-missing   { features = ["platform-faults-named"] }
#         engine-unknown  { features = ["platform-faults-named"] }
#         value-no-string { features = ["platform-faults-named"] }
#         tools           { features = ["platform-list-read"] }
#         requires        { features = ["platform-list-read"] }
#         tools-faults    { features = ["platform-faults-named"] }
#     }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'platform = [ ... ]' OF A BUBBLE'S 'hwut-root.conf' (spec/42
         section 1; intend/42 rulings 3, 4, 10, 14, 15, 16, 19): the
         list a tree walk reads, and every fault of it by name.

CHOICES: reads, bubble, root-only, tools, requires, tools-faults, and one
         per fault;

reads           "local" and a 'container' entry: the tuple of (name,
                spec) in the list's order, and it reaches the bubble's
                test directory.
bubble          an inner bubble with no 'platform' decides alone: its
                test directory carries none, the outer one's list stops
                at its root (rulings 10, 19).
root-only       'platform' in a tree level's 'hwut.conf' and in a test
                directory's own: refused, the root's alone.
tools           'tools' on each entry, 'local' with 'tools' alone (intend/26
                o-50, o-56): kept with the entry, a tuple.
requires        'requires' in the root, added to by a tree level's
                'hwut.conf' and a test directory's own, replaced by an
                inner root (o-54, o-57).
tools-faults    'tools' and 'requires' that do not read: refused by name.
not-list .. value-no-string
                one fault each: the shape, the bare name, the name, the
                kind, and the kind's own keys (checked by the kind,
                ruling 14). A refused list reaches nothing.
______________________________________________________________________________
"""
import shutil
import sys
import tempfile
import os
from config import HwutRunner                                # noqa: F401

from hwut.engine.orchestrator.exploration.tree_explorer import explore_tree
from hwut.support.test_writing.python.script_runner import tree_boundary  # noqa: E402

LINUX = ('{ name = "linux", kind = "container", image = "hwut-dev", '
         'recipe = "../adm/container/Containerfile" }')


def walked(root_text, file_db=None):
    """
    RETURN: None. A tree whose 'hwut-root.conf' says 'root_text' inside
            'hwut { }', one test directory 'TEST' (and 'file_db' beside
            it), walked: per test directory its 'platform_tuple', then
            whether its cases run (no conf fault at it or above), its own
            faults; then every fault of the walk.
    """
    root = tempfile.mkdtemp(prefix="hwut_platform_")
    try:
        tree_boundary(root, "hwut {\n    %s\n}\n" % root_text)
        file_db = dict({"TEST/test-a.py": '# @hwut { title = "A" }\n'},
                       **(file_db or {}))
        for relative, content in file_db.items():
            path = os.path.join(root, relative)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as fh: fh.write(content)
        print("hwut-root.conf:  hwut { %s }" % root_text)
        for relative in sorted(file_db):
            if not relative.endswith(".py"):
                print("%-16s %s" % (relative + ":", file_db[relative].strip()))
        tree = explore_tree(root, boundary_f=False)
        for directory, result in tree:
            spec = result.app_set.directory_spec
            print("    %-12s platform_tuple=%r"
                  % (directory, spec.platform_tuple))
            if spec.requires_tuple is not None:
                print("    %-12s requires_tuple=%r" % ("", spec.requires_tuple))
            print("    %-12s %s" % ("", "runs" if not result.conf_fault_tuple
                                     else "runs not: %i conf fault(s)"
                                          % len(result.conf_fault_tuple)))
            for fault in result.fault_list:
                print("    %-12s FAULT %s" % ("", fault))
        for fault in tree.fault_tuple:
            print("    FAULT %s" % fault)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_reads():
    """RETURN: None. A list that reads, and where it reaches."""
    walked('platform = [ "local", %s ]' % LINUX)


def test_bubble():
    """RETURN: None. An inner bubble with no 'platform' of its own."""
    walked("platform = [ %s ]" % LINUX,
           {"inner/hwut-root.conf":     "hwut {\n}\n",
            "inner/TEST/test-b.py":     '# @hwut { title = "B" }\n'})


def test_root_only():
    """RETURN: None. 'platform' below the root: refused, both places."""
    walked("", {"sub/hwut.conf":
                    'hwut { platform = [ "local" ] }\n',
                "sub/TEST/test-b.py":
                    '# @hwut { title = "B" }\n',
                "TEST/hwut.conf":
                    'hwut { platform = [ "local" ] }\n'})


def test_tools():
    """RETURN: None. 'tools' read, 'local' carrying them."""
    walked('platform = [ { name = "local", tools = ["iverilog"] }, '
           '{ name = "linux", kind = "container", image = "hwut-dev", '
           'tools = ["iverilog", "ghdl"] } ]')


def test_requires():
    """RETURN: None. 'requires' added down, replaced at an inner root."""
    walked('requires = ["iverilog"]',
           {"sub/hwut.conf":          'hwut { requires = ["ghdl"] }\n',
            "sub/TEST/test-b.py":     '# @hwut { title = "B" }\n',
            "sub/TEST/hwut.conf":     'hwut { requires = ["ghdl", "gcc"] }\n',
            "inner/hwut-root.conf":   'hwut { requires = ["gcc"] }\n',
            "inner/TEST/test-c.py":   '# @hwut { title = "C" }\n',
            "bare/hwut-root.conf":    'hwut {\n}\n',
            "bare/TEST/test-d.py":    '# @hwut { title = "D" }\n'})


def test_tools_faults():
    """RETURN: None. 'tools' and 'requires' that do not read."""
    walked('platform = [ { name = "linux", kind = "container", '
           'image = "x", tools = [7] }, '
           '{ name = "lab", kind = "container", image = "y", tools = [""] } ]'
           '\n    requires = ["", "gcc"]')


_FAULT_DB = {
    "not-list":        'platform = "local"',
    "empty":           'platform = []',
    "bare-name":       'platform = [ "linux" ]',
    "name-missing":    'platform = [ { kind = "container", image = "x" } ]',
    "name-doubled":    'platform = [ "local", "local" ]',
    "local-keys":      'platform = [ { name = "local", kind = "container" } ]',
    "kind-missing":    'platform = [ { name = "linux", image = "x" } ]',
    "kind-unknown":    'platform = [ { name = "lab-3", kind = "host", '
                       'ssh = "lab-pc-3" } ]',
    "key-unknown":     'platform = [ { name = "linux", kind = "container", '
                       'imgae = "hwut-dev" } ]',
    "image-missing":   'platform = [ { name = "linux", kind = "container" } ]',
    "engine-unknown":  'platform = [ { name = "linux", kind = "container", '
                       'image = "x", engine = "lxc" } ]',
    "value-no-string": 'platform = [ { name = "linux", kind = "container", '
                       'image = 7 } ]',
}


def fault_choice(choice):
    """RETURN: function, the test of fault choice 'choice': its conf
    walked, the fault named, nothing reaching the test directory."""
    def test():
        """RETURN: None. One fault of 'platform', shown."""
        walked(_FAULT_DB[choice])
    return test


if __name__ == "__main__":
    choice_db = {"reads":     test_reads,
                 "bubble":    test_bubble,
                 "root-only": test_root_only,
                 "tools":     test_tools,
                 "requires":  test_requires,
                 "tools-faults": test_tools_faults}
    choice_db.update((choice, fault_choice(choice)) for choice in _FAULT_DB)
    HwutRunner(sys.argv,
               "The conf key 'platform': read, or refused by name;",
               choice_db).run()
