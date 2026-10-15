#! /usr/bin/env python3
#
# @hwut {
#     title      = "The feature relation: the feature file, the link, the TEST directories of a tree"
#     choices {
#         block        { features = ["features-linked-in-block"] }
#         faults       { features = ["statement-faults-named"] }
#         feature_file { features = ["feature-statements-read"] }
#         tree         { features = ["feature-states"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FEATURE RELATION, read: what 'hwut-features.conf' states in
         a TEST directory, what a test's block links, and what these say
         together per TEST directory of a tree. Where the features stand in
         the world is the central file's ('test-feature_registry.py').

CHOICES: feature_file, block, faults, tree;

feature_file  the features of a TEST directory's file: name = key in
              'childs', title, 'doc' in triple quotes, documents, own
              keys, the keys of the whole file; names of digits.

block         'features' in a test's block: at the root, in a choice
              (which replaces the root's), the empty list, and what the
              validator refuses.

faults        what a feature file states that is not read, each named
              with its place: the words of an aggregate, a directory
              reference, the vocabulary of the past.

tree          the relation over a tree: per TEST directory its features,
              the runs linked to each with the verdict of 'GOOD/book.csv',
              the runs linking nothing, the links to names not defined; a
              component file of the past is read by nothing.
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
                                 import (feature_file_of_text,   # noqa E402
                                         relation_of_tree)


FEATURE_TEXT = """features {
    keys = ["algorithm"]
    childs {
        line-pairing {
            title = "Two streams are aligned line by line."
            keys  = ["heavy"]
            doc   = \"\"\"
                Each line of the subject meets one of the nominal.
                The rest is said in the MANUAL.
                \"\"\"
            documents = ["../MANUAL.md#pairing"]
        }
        missing-side { title = "A line present on one side only is shown whole." }
        007          { title = "A feature named by digits." }
        untested     { }
    }
}
"""

def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def test_feature_file():
    """RETURN: None. Prints a TEST directory's feature file as read."""
    found = feature_file_of_text(FEATURE_TEXT)
    banner("the keys of the whole file")
    print("keys:      %s" % (found.key_tuple,))
    banner("the features, file order")
    for feature in found.feature_tuple:
        print("name=%-13s line=%i keys=%s" % (feature.name, feature.line_n,
                                              feature.key_tuple))
        print("    title:       %s" % feature.title)
        print("    doc:         %r" % feature.doc)
        print("    documents:   %s" % (feature.document_tuple,))
    banner("asked by name")
    for name in ("missing-side", "007", "nobody"):
        feature = found.feature_of_name(name)
        print("%-13s -> %s" % (name, None if feature is None
                               else "line %s" % feature.line_n))
    print("names: %s" % ", ".join(found.name_tuple()))
    banner("faults")
    print(len(found.fault_tuple))


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


def test_faults():
    """RETURN: None. Prints the faults of unreadable statements."""
    case_list = [
        ("the outer node is another",
         feature_file_of_text, 'hwut { }'),
        ("nothing stands",
         feature_file_of_text, ''),
        ("a feature name standing twice",
         feature_file_of_text,
         'features {\n childs {\n  a { }\n  a { }\n }\n}'),
        ("a name that is no key",
         feature_file_of_text,
         'features {\n childs {\n  "a.b" { }\n  "-x" { }\n }\n}'),
        ("an unknown key, and one inside a feature",
         feature_file_of_text,
         'features {\n  owner = "me"\n  childs { a { since = "v2" } }\n}'),
        ("'title', 'doc' and 'documents' in a TEST directory's file",
         feature_file_of_text,
         'features {\n  title = "T"\n  doc = "D"\n  documents = ["x"]\n}'),
        ("a directory reference in a TEST directory's file",
         feature_file_of_text,
         'features {\n  childs { a = "./a" }\n}'),
        ("keys: a dot, twice, a number",
         feature_file_of_text,
         'features {\n  keys = ["a.b", "c", "c"]\n'
         '  childs { x { keys = 3 } }\n}'),
        ("the vocabulary of the past: 'parent', numbers",
         feature_file_of_text,
         'features {\n  parent = "b"\n  issued = 1\n  1 { name = "x" }\n}'),
    ]
    for label, function, text in case_list:
        banner(label)
        found = function(text)
        for fault in found.fault_tuple: print("  %s" % fault)
        if not found.fault_tuple: print("  no fault")
        kept = getattr(found, "feature_tuple", None)
        if kept: print("  kept: %s" % ", ".join(f.name for f in kept))


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
    """RETURN: None. A tree of three TEST directories below 'root' -- two
    stating features, one not -- a component file of the past beside one,
    and the book verdicts written by the bookkeeper."""
    _write(root, "hwut-root.conf", "hwut {\n}\n")
    _write(root, "engine/compare/hwut-features.conf",
           'features {\n  title = "Compare"\n  childs { core = "./core" }\n}\n')
    _write(root, "engine/compare/core/TEST/hwut-features.conf", FEATURE_TEXT)
    _write(root, "engine/compare/TEST/hwut-features.conf",
           'features {\n  childs {\n'
           '    whole-page { title = "A whole page is judged." }\n  }\n}\n')
    _test(root, "engine/compare/core/TEST/test-pair.sh",
          ['title    = "Pairing"', 'features = ["line-pairing"]',
           'choices {', '    plain { }',
           '    gap   { features = ["line-pairing", "missing-side"] }',
           '    odd   { features = [] }', '}'])
    _test(root, "engine/compare/core/TEST/test-stray.sh",
          ['title    = "Stray"', 'features = ["no-such", "untested"]'])
    _test(root, "engine/compare/TEST/test-pages.sh",
          ['title    = "Pages"', 'features = ["whole-page"]',
           'choices = ["small", "large"]'])
    _test(root, "engine/compare/patterns/TEST/test-pat.sh",
          ['title    = "Patterns"', 'features = ["glob"]'])

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
        banner("the TEST directories: features, runs, verdicts")
        for path in sorted(relation.test_directory_db):
            each = relation.test_directory_db[path]
            print("%s   feature file: %s"
                  % (path, each.feature_file is not None))
            for state in each.state_tuple:
                print("    %s" % state.feature.name)
                for run in state.run_tuple:
                    print("        %-10s %s %s"
                          % (run.verdict, run.test, run.choice))
            for test, choice in each.unlinked_tuple:
                print("    unlinked   %s %s" % (test, choice))
            for test, choice, name in each.undefined_tuple:
                print("    undefined  %s %s '%s'" % (test, choice, name))
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
        title      = "The feature relation: the feature file, the link, "
                     "the TEST directories of a tree",
        choice_map = {
            "feature_file": test_feature_file,
            "block":        test_block,
            "faults":       test_faults,
            "tree":         test_tree,
        },
    ).run()
