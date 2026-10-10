#! /usr/bin/env python3
#
# @hwut {
#     title      = "The feature relation: feature file, composition file, the link, the tree"
#     choices    = ["block", "composition", "faults", "feature_file", "tree"]
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FEATURE RELATION, read: what 'hwut-features.conf' and
         'hwut-composition.conf' state, what a test's block links, and
         what the three say together over a tree.

CHOICES: feature_file, composition, block, faults, tree;

feature_file  the features of a file with their numbers; the scope the
              file hands out, counting from 1 and never below a number
              the file holds; a feature without a number.

composition   title, does, to-parent and the parts, as stated.

block         'features' in a test's block: at the root, in a choice
              (which replaces the root's), the empty list, and what the
              validator refuses.

faults        what a feature file and a composition file state that is
              not read, each named with its place.

tree          the relation over a tree: states of features from the
              verdicts of 'GOOD/book.csv', the counts of a component
              summed over its parts, and what stands outside.
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.bookkeeper.api import Bookkeeper               # noqa E402
from   vut.engine.orchestrator.exploration import reader         # noqa E402
from   vut.engine.orchestrator.exploration.feature_relation \
                                 import (feature_file_of_text,   # noqa E402
                                         composition_of_text,
                                         relation_of_tree)


FEATURE_TEXT = """features {
    id     = "core-proof"
    parent { core = "What 'core' promises, proven." }
    issued = 4
    1 { name        = "line-pairing"
        title       = "Two streams are aligned line by line."
        explanation = "Each line of the subject meets one of the nominal." }
    2 { name        = "missing-side"
        title       = "A line present on one side only is shown whole." }
    4 { name        = "untested" }
    fresh { name = "not-numbered"  title = "Written today." }
}
"""

COMPOSITION_TEXT = """component {
    id     = "cmp"
    title  = "Compare"
    does   = "Decides whether an output is equivalent to its nominal."
    parent { eng = "The engine's verdict rests on it." }
    childs {
        core      = "Aligns two streams line by line."
        pat       = "Lets declared variation pass."
        cmp-proof = "Proves the whole comparison on real pages."
    }
}
"""


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def test_feature_file():
    """RETURN: None. Prints a feature file as read, and its scope."""
    found = feature_file_of_text(FEATURE_TEXT)
    banner("the file's own keys")
    print("id:        %s" % found.id)
    print("parent:    %s -- %s" % (found.parent_id, found.parent_text))
    print("issued:    %s" % found.issued)
    banner("the features, file order")
    for feature in found.feature_tuple:
        print("number=%-4s key=%-6s name=%-13s line=%i"
              % (feature.number, feature.key, feature.name, feature.line_n))
        print("    title:       %s" % feature.title)
        print("    explanation: %s" % feature.explanation)
    banner("asked by name")
    for name in ("missing-side", "not-numbered", "nobody"):
        feature = found.feature_of_name(name)
        print("%-13s -> %s" % (name, None if feature is None
                               else "number %s" % feature.number))
    print("names: %s" % ", ".join(found.name_tuple()))
    banner("the scope: 'issued' is the mark")
    scope = found.scope()
    print("mark=%i, the next feature receives %i"
          % (scope.mark, scope.allocate()))
    banner("the scope where 'issued' lags behind a number in the file")
    lagging = feature_file_of_text(FEATURE_TEXT.replace("issued = 4",
                                                        "issued = 1"))
    scope = lagging.scope()
    print("issued=%i, mark=%i, the next feature receives %i"
          % (lagging.issued, scope.mark, scope.allocate()))
    banner("faults")
    print(len(found.fault_tuple))


def test_composition():
    """RETURN: None. Prints a composition file as read."""
    found = composition_of_text(COMPOSITION_TEXT)
    banner("the component")
    print("id:        %s" % found.id)
    print("title:     %s" % found.title)
    print("does:      %s" % found.does)
    print("parent:    %s -- %s" % (found.parent_id, found.parent_text))
    banner("the childs, file order")
    for child_id, text in found.child_tuple:
        print("%-9s %s" % (child_id, text))
    banner("asked by id")
    for child_id in ("core", "cmp-proof", "gone"):
        print("%-9s -> %s" % (child_id, found.child_text(child_id)))
    banner("the forms without sentences")
    short = composition_of_text(
        'component { id = "cmp"  parent = "eng"  childs = ["core", "pat"] }')
    print("parent: %s -- %s   childs: %s   faults: %i"
          % (short.parent_id, short.parent_text, short.child_tuple,
             len(short.fault_tuple)))
    banner("a component that states no id, no parent, no childs")
    bare = composition_of_text('component { title = "Root"  does = "All." }')
    print("id: %s   parent: %s   childs: %i   faults: %i"
          % (bare.id, bare.parent_id, len(bare.child_tuple),
             len(bare.fault_tuple)))


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
         feature_file_of_text, 'hwut { issued = 0 }'),
        ("nothing stands",
         feature_file_of_text, ''),
        ("a number standing twice",
         feature_file_of_text,
         'features {\n  issued = 2\n  1 { name = "a" }\n  1 { name = "b" }\n}'),
        ("a name standing twice",
         feature_file_of_text,
         'features {\n  issued = 2\n  1 { name = "a" }\n  2 { name = "a" }\n}'),
        ("number 0",
         feature_file_of_text, 'features {\n  0 { name = "a" }\n}'),
        ("'issued' that spells no mark",
         feature_file_of_text, 'features {\n  issued = "two"\n}'),
        ("'issued' below zero",
         feature_file_of_text, 'features {\n  issued = -1\n}'),
        ("an unknown key, and one inside a feature",
         feature_file_of_text,
         'features {\n  owner = "me"\n  1 { name = "a"  since = "v2" }\n}'),
        ("'parent' that names no id, an empty 'id', 'childs' in a feature file",
         feature_file_of_text,
         'features {\n  id = ""\n  parent = 7\n  childs = ["a"]\n}'),
        ("'parent' naming two ids",
         composition_of_text,
         'component {\n  parent { a = "x"  b = "y" }\n}'),
        ("a child id standing twice",
         composition_of_text,
         'component {\n  childs = ["a", "a"]\n}'),
        ("composition: the outer node is another",
         composition_of_text, 'features { }'),
        ("composition: an unknown key, a child that is no text",
         composition_of_text,
         'component {\n  owner = "me"\n  childs { core = 3 }\n}'),
        ("composition: 'childs' that is neither scope nor list",
         composition_of_text, 'component {\n  childs = "core"\n}'),
    ]
    for label, function, text in case_list:
        banner(label)
        found = function(text)
        for fault in found.fault_tuple: print("  %s" % fault)
        if not found.fault_tuple: print("  no fault")
        kept = getattr(found, "feature_tuple", None)
        if kept: print("  kept: %s" % ", ".join(
            "%s=%s" % (f.key, f.name) for f in kept))


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
    """RETURN: None. Builds the tree of the concept's picture below
    'root', with the book verdicts written by the bookkeeper."""
    _write(root, "hwut-root.conf", "hwut {\n}\n")
    _write(root, "engine/compare/hwut-composition.conf", COMPOSITION_TEXT)
    _write(root, "engine/compare/core/hwut-composition.conf",
           'component { id = "core"  title = "Core"\n'
           '            parent { cmp = "Alignment." }\n'
           '            childs { core-proof = "The proof." } }\n')
    _write(root, "engine/compare/core/TEST/hwut-features.conf", FEATURE_TEXT)
    _write(root, "engine/compare/TEST/hwut-features.conf",
           'features {\n  id = "cmp-proof"\n  parent = "cmp"\n  issued = 1\n'
           '  1 { name = "whole-page"  title = "A whole page is judged." }\n}\n')
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
    _write(root, "engine/empty/hwut-composition.conf",
           'component { id = "empty"  title = "Empty"  does = "Nothing yet." }\n')

    core = Bookkeeper(os.path.join(root, "engine/compare/core/TEST"))
    core.note_accept("test-pair.sh", "plain")
    core.note_accept("test-pair.sh", "gap", equivalent_f=False)
    core.note_accept("test-stray.sh", None, aspirant_f=True)
    page = Bookkeeper(os.path.join(root, "engine/compare/TEST"))
    page.note_accept("test-pages.sh", "small")
    page.note_accept("test-pages.sh", "large")


def test_tree():
    """RETURN: None. Prints the relation of a tree."""
    root = tempfile.mkdtemp(prefix="hwut-features-")
    try:
        _tree(root)
        relation = relation_of_tree(root)
        banner("the components, their parts and their own TEST directory")
        for path in sorted(relation.component_db):
            component = relation.component_db[path]
            print("%-24s composition=%-5s TEST=%s"
                  % (path, component.composition is not None,
                     component.test_directory))
            for part in component.part_tuple: print("    part %s" % part)
        banner("the TEST directories: features, runs, verdicts")
        for path in sorted(relation.test_directory_db):
            each = relation.test_directory_db[path]
            print("%s   feature file: %s"
                  % (path, each.feature_file is not None))
            for state in each.state_tuple:
                print("    %-8s #%s %s" % (state.state, state.feature.number,
                                           state.feature.name))
                for run in state.run_tuple:
                    print("        %-10s %s %s"
                          % (run.verdict, run.test, run.choice))
            for test, choice in each.unlinked_tuple:
                print("    unlinked   %s %s" % (test, choice))
            for test, choice, name in each.undefined_tuple:
                print("    undefined  %s %s '%s'" % (test, choice, name))
        banner("the counts, summed over the parts")
        for path in sorted(relation.component_db) \
                    + sorted(relation.test_directory_db):
            count_db = relation.count_of(path)
            print("%-28s %s" % (path, "  ".join(
                "%s=%i" % (state, n) for state, n in count_db.items())))
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The feature relation: feature file, composition "
                     "file, the link, the tree",
        choice_map = {
            "feature_file": test_feature_file,
            "composition":  test_composition,
            "block":        test_block,
            "faults":       test_faults,
            "tree":         test_tree,
        },
    ).run()
