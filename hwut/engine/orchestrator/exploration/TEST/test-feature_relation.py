#! /usr/bin/env python3
#
# @hwut {
#     title      = "The feature relation: the link, the TEST directories of a tree"
#     choices {
#         block { features = ["features-linked-in-block"] }
#         tree  { features = ["links-read"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FEATURE RELATION, read: what a test's block links, and what the
         links say per TEST directory of a tree (spec 43 section 4). What
         a feature is and where it stands is the forest's and the doc
         file's ('test-feature_forest.py', 'test-feature_doc.py').

CHOICES: block, tree;

block   'features' in a test's block: at the root, in a choice (which
        replaces the root's), the empty list, and what the validator
        refuses.

tree    the relation over a tree: per TEST directory every link, (test,
        choice, id), whatever id it names; the runs linking nothing; whether
        the directory takes part ('linking_f'); the runs of each id over
        the tree with the verdict of 'GOOD/book.csv' -- one id linked from
        two directories; a file of the past is read by nothing.
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from hwut.engine.bookkeeper.api import Bookkeeper               # noqa E402
from hwut.engine.orchestrator.exploration import reader         # noqa E402
from   hwut.engine.orchestrator.exploration.feature_relation \
                                 import relation_of_tree         # noqa E402


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def _block(body):
    """RETURN: None. Prints what the header reader makes of a test whose
    block holds 'body': the features of each choice, or the faults."""
    text = "# @hwut {\n#     title = \"T\"\n%s\n# }\n" \
           % "\n".join("#     " + line for line in body)
    spec, fault_list = reader.read_header(text, "test-x.sh")
    for line in body: print("    %s" % line)
    for fault in fault_list: print("  FAULT %s" % fault)
    if spec is None or fault_list: return
    root = spec.root_parameters
    for choice, parameters in spec.choice_db.items():
        print("  %-8s -> %s" % ("-" if choice is None else choice,
                                root.overwritten_by(parameters).features))


def test_block():
    """RETURN: None. Prints 'features' as a test's block states it."""
    banner("for the whole test")
    _block(['features = ["line-pairing", "missing-side"]'])
    banner("one name, written without the list")
    _block(['features = "line-pairing"'])
    banner("no word of features")
    _block(['choices = ["a", "b"]'])
    banner("for one choice: the choice's list replaces the root's")
    _block(['features = ["line-pairing"]',
            'choices {',
            '    plain { }',
            '    gap   { features = ["missing-side"] }',
            '    none  { features = [] }',
            '}'])
    banner("refused")
    _block(['features = ["a", "a"]'])
    _block(['features = ["a", ""]'])
    _block(['features = 3'])
    _block(['features = ["a", 3]'])


def _write(root, path, text):
    """RETURN: None. Writes 'text' to 'root/path', directories made."""
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as handle:
        handle.write(text)


def _test(root, path, body):
    """RETURN: None. Writes a shell test at 'root/path' whose block
    holds the lines of 'body'."""
    _write(root, path, "#! /bin/sh\n# @hwut {\n%s\n# }\necho x\n"
           % "\n".join("#     " + line for line in body))
    os.chmod(os.path.join(root, path), 0o755)


def _tree(root):
    """RETURN: None. A tree of four TEST directories below 'root' -- one
    whose tests link nothing -- a feature file of the past beside one,
    and the book verdicts written by the bookkeeper."""
    _write(root, "hwut-root.conf", "hwut {\n}\n")
    _write(root, "engine/compare/core/TEST/hwut-features.conf",
           'features {\n  childs { line-pairing { } }\n}\n')
    _test(root, "engine/compare/core/TEST/test-pair.sh",
          ['title    = "Pairing"', 'features = ["line-pairing"]',
           'choices {', '    plain { }',
           '    gap   { features = ["line-pairing", "missing-side"] }',
           '    odd   { features = [] }', '}'])
    _test(root, "engine/compare/core/TEST/test-stray.sh",
          ['title    = "Stray"', 'features = ["no-such", "untested"]'])
    _test(root, "engine/compare/TEST/test-pages.sh",
          ['title    = "Pages"', 'features = ["whole-page", "line-pairing"]',
           'choices = ["small", "large"]'])
    _test(root, "engine/compare/patterns/TEST/test-pat.sh",
          ['title    = "Patterns"'])

    core = Bookkeeper(os.path.join(root, "engine/compare/core/TEST"))
    core.note_accept("test-pair.sh", "plain")
    core.note_accept("test-pair.sh", "gap", equivalent_f=False)
    core.note_accept("test-stray.sh", None, aspirant_f=True)
    page = Bookkeeper(os.path.join(root, "engine/compare/TEST"))
    page.note_accept("test-pages.sh", "small")
    page.note_accept("test-pages.sh", "large")


def test_tree():
    """RETURN: None. Prints the relation of a tree."""
    root = tempfile.mkdtemp(prefix="hwut-features-", dir="/tmp")
    try:
        _tree(root)
        relation = relation_of_tree(root)
        print("root name: %s" % (relation.root_name == os.path.basename(root)))
        banner("the TEST directories: links, the runs linking nothing")
        for path in sorted(relation.test_directory_db):
            each = relation.test_directory_db[path]
            print("%s   takes part: %s" % (path, each.linking_f()))
            for test, choice, feature_id in each.link_tuple:
                print("    link       %s %s '%s'" % (test, choice, feature_id))
            for test, choice in each.unlinked_tuple:
                print("    unlinked   %s %s" % (test, choice))
        banner("the runs of each id, over the tree")
        run_db = relation.run_db()
        for feature_id in sorted(run_db):
            print("%s" % feature_id)
            for run in run_db[feature_id]:
                print("    %-10s %s/%s %s" % (run.verdict, run.path, run.test,
                                             run.choice))
        banner("asked inside one TEST directory")
        relation = relation_of_tree(os.path.join(root,
                                                 "engine/compare/TEST"))
        print(sorted(relation.test_directory_db))
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The feature relation: the link, the TEST "
                     "directories of a tree",
        choice_map = {
            "block":        test_block,
            "tree":         test_tree,
        },
    ).run()
