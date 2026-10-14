#! /usr/bin/env python3
#
# @hwut {
#     title      = "The feature relation: feature file, claim file, map, the link, the tree"
#     choices {
#         block        { features = ["features-linked-in-block"] }
#         claim        { features = ["feature-statements-read"] }
#         faults       { features = ["statement-faults-named"] }
#         feature_file { features = ["feature-statements-read"] }
#         map          { features = ["feature-statements-read"] }
#         mismatch     { features = ["feature-states"] }
#         tree         { features = ["feature-states"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FEATURE RELATION, read: what 'hwut-features.conf' states in
         a TEST directory and in a component, what 'hwut-feature-map.conf'
         binds, what a test's block links, and what these say together
         over a tree.

CHOICES: feature_file, claim, map, block, faults, mismatch, tree;

feature_file  the features of a TEST directory's file: name = key in
              'childs', title, 'doc' in triple quotes, documents, own
              keys, the keys of the whole file; names of digits.

claim         a component's file: title, doc, keys and the directories
              its 'childs' refer to, each under its key.

map           the map: published id -> full id, or none (RETIRED).

block         'features' in a test's block: at the root, in a choice
              (which replaces the root's), the empty list, and what the
              validator refuses.

faults        what a feature file, a claim and a map state that is not
              read, each named with its place.

mismatch      what a tree states in files against how it stands: an
              explicit tree judged, an implicit one not; the moves.

tree          the relation over a tree: ids, keys that travel down,
              states of features from the verdicts of 'GOOD/book.csv',
              counts summed over the parts, and what stands outside.
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
                                         claim_of_text,
                                         directory_of_reference,
                                         feature_map_of_text,
                                         mismatch_list,
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

CLAIM_TEXT = """features {
    title  = "Compare"
    doc    = "Decides whether an output is equivalent to its nominal."
    keys   = ["engine-part"]
    childs {
        core      = "./core"
        pat       = "./patterns"
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


def test_claim():
    """RETURN: None. Prints a component's file as read."""
    found = claim_of_text(CLAIM_TEXT)
    banner("the component")
    print("title:     %s" % found.title)
    print("doc:       %s" % found.doc)
    print("keys:      %s" % (found.key_tuple,))
    banner("the childs, file order")
    for child in found.child_tuple:
        print("%-9s -> %-10s line=%i" % (child.key, child.directory,
                                         child.line_n))
    banner("asked by directory")
    for directory in ("core", "patterns", "gone"):
        child = found.child_of_directory(directory)
        print("%-9s -> %s" % (directory, None if child is None
                              else child.key))
    banner("the forms of a reference")
    for text in ("./core", "core", "./core/", "../core", "a/b", "/abs", "."):
        print("%-8s -> %s" % (text, directory_of_reference(text)))
    banner("a component that states nothing but the outer node")
    bare = claim_of_text('features { }')
    print("title: %s   childs: %i   keys: %s   faults: %i"
          % (bare.title, len(bare.child_tuple), bare.key_tuple,
             len(bare.fault_tuple)))


def test_map():
    """RETURN: None. Prints a map as read."""
    found = feature_map_of_text('''map {
    "scroll"        = "display.game.scroll"
    "old-scroll"    = none
    "with space"    = "a.b"
}
''')
    banner("the entries, file order")
    for published, target, line in found.entry_tuple:
        print("%-12s -> %-22s line=%i" % (published, target, line))
    banner("asked")
    for published in ("scroll", "old-scroll", "nobody"):
        print("%-12s target=%s standing=%s" % (
            published, found.target_of(published),
            found.standing_f(published)))
    print("published: %s" % (found.published_tuple(),))
    print("faults: %i" % len(found.fault_tuple))


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
        ("claim: an inline feature",
         claim_of_text, 'features {\n  childs { a { title = "x" } }\n}'),
        ("claim: references that name more than one level",
         claim_of_text,
         'features {\n  childs {\n    a = "../a"\n    b = "x/y"\n'
         '    c = 3\n  }\n}'),
        ("claim: 'childs' that is no scope",
         claim_of_text, 'features {\n  childs = ["core"]\n}'),
        ("claim: the old words",
         claim_of_text,
         'features {\n  id = "x"\n  parent = "y"\n  issued = 3\n}'),
        ("map: the outer node is another",
         feature_map_of_text, 'features { }'),
        ("map: entries that are no id, no text",
         feature_map_of_text,
         'map {\n  "" = "a"\n  x = 3\n  y { }\n}'),
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
    """RETURN: None. Builds the tree of the concept's picture below
    'root', with the book verdicts written by the bookkeeper."""
    _write(root, "hwut-root.conf", "hwut {\n}\n")
    _write(root, "hwut-features.conf",
           'features {\n  title = "All"\n  childs {\n'
           '    engine = "./engine"\n  }\n}\n')
    _write(root, "engine/hwut-features.conf",
           'features {\n  title = "Engine"\n  keys = ["engine-part"]\n'
           '  childs {\n    cmp = "./compare"\n    empty = "./empty"\n  }\n}\n')
    _write(root, "engine/compare/hwut-features.conf", CLAIM_TEXT)
    _write(root, "engine/compare/core/hwut-features.conf",
           'features {\n  title = "Core"\n}\n')
    _write(root, "engine/compare/core/TEST/hwut-features.conf", FEATURE_TEXT)
    _write(root, "engine/compare/TEST/hwut-features.conf",
           'features {\n  childs {\n'
           '    whole-page { title = "A whole page is judged." }\n  }\n}\n')
    _write(root, "engine/compare/patterns/hwut-features.conf",
           'features {\n  title = "Patterns"\n}\n')
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
    _write(root, "engine/empty/hwut-features.conf",
           'features {\n  title = "Empty"\n}\n')

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
        banner("explicit tree? the top? the map?")
        print("explicit=%s top=%s map=%s" % (
            relation.explicit_f, relation.top_f, relation.feature_map))
        banner("the components, their parts and their own TEST directory")
        for path in sorted(relation.component_db):
            component = relation.component_db[path]
            print("%-24s key=%-7s claim=%-5s TEST=%s"
                  % (path, component.key, component.claim is not None,
                     component.test_directory))
            for part in component.part_tuple: print("    part %s" % part)
        banner("the TEST directories: full ids, keys, runs, verdicts")
        for path in sorted(relation.test_directory_db):
            each = relation.test_directory_db[path]
            print("%s   feature file: %s"
                  % (path, each.feature_file is not None))
            for state in each.state_tuple:
                name = state.feature.name
                print("    %-8s %s" % (state.state, relation.id_of(path, name)))
                print("        keys: %s" % (
                    relation.effective_key_tuple(path, state.feature),))
                for run in state.run_tuple:
                    print("        %-10s %s %s"
                          % (run.verdict, run.test, run.choice))
            for test, choice in each.unlinked_tuple:
                print("    unlinked   %s %s" % (test, choice))
            for test, choice, name in each.undefined_tuple:
                print("    undefined  %s %s '%s'" % (test, choice, name))
        banner("the keys a component has: derived, from what lies below")
        for path in sorted(relation.component_db):
            print("%-24s %s" % (path, relation.derived_key_tuple(path)))
        banner("the counts, summed over the parts")
        for path in sorted(relation.component_db) \
                    + sorted(relation.test_directory_db):
            count_db = relation.count_of(path)
            print("%-28s %s" % (path, "  ".join(
                "%s=%i" % (state, n) for state, n in count_db.items())))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _mismatch(relation):
    """RETURN: None. Prints the mismatches of 'relation', sorted."""
    result = sorted((m.kind, m.path, m.id or "", m.from_path or "")
                    for m in mismatch_list(relation))
    for each in result: print("  %s" % " | ".join(each))
    if not result: print("  none")


def test_mismatch():
    """RETURN: None. Prints what a tree states against how it stands."""
    root = tempfile.mkdtemp(prefix="hwut-features-")
    try:
        _tree(root)
        banner("the tree as built: no map yet")
        _mismatch(relation_of_tree(root))
        banner("a directory the parent does not list")
        _write(root, "engine/compare/extra/hwut-features.conf",
               'features {\n  title = "Extra"\n}\n')
        _write(root, "engine/compare/extra/TEST/hwut-features.conf",
               'features {\n  childs { x { } }\n}\n')
        _test(root, "engine/compare/extra/TEST/test-x.sh",
              ['title = "X"', 'features = ["x"]'])
        _mismatch(relation_of_tree(root))
        banner("a listed directory that is not there")
        shutil.rmtree(os.path.join(root, "engine/compare/extra"))
        shutil.rmtree(os.path.join(root, "engine/empty"))
        _mismatch(relation_of_tree(root))
        banner("a directory moved by hand: found where the files still "
               "list it")
        _write(root, "engine/empty/hwut-features.conf",
               'features {\n  title = "Empty"\n}\n')
        shutil.move(os.path.join(root, "engine/compare/patterns"),
                    os.path.join(root, "engine/empty"))
        _mismatch(relation_of_tree(root))
        banner("an implicit tree: TEST files only, nothing judged")
    finally:
        shutil.rmtree(root, ignore_errors=True)
    root = tempfile.mkdtemp(prefix="hwut-features-")
    try:
        _write(root, "hwut-root.conf", "hwut {\n}\n")
        _write(root, "a/TEST/hwut-features.conf",
               'features {\n  childs { x { } }\n}\n')
        _test(root, "a/TEST/test-x.sh", ['title = "X"', 'features = ["x"]'])
        relation = relation_of_tree(root)
        print("explicit=%s" % relation.explicit_f)
        for path in sorted(relation.test_directory_db):
            for state in relation.test_directory_db[path].state_tuple:
                print("%s keys=%s" % (relation.id_of(path, state.feature.name),
                                      relation.effective_key_tuple(
                                          path, state.feature)))
        _mismatch(relation)
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The feature relation: feature file, claim file, "
                     "map, the link, the tree",
        choice_map = {
            "feature_file": test_feature_file,
            "claim":        test_claim,
            "map":          test_map,
            "mismatch":     test_mismatch,
            "block":        test_block,
            "faults":       test_faults,
            "tree":         test_tree,
        },
    ).run()
