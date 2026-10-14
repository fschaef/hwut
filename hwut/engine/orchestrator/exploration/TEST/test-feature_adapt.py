#! /usr/bin/env python3
#
# @hwut {
#     title      = "Feature files and the map adapted to the directories"
#     choices {
#         judged     { features = ["relation-judged"] }
#         moved      { features = ["relation-adapted"] }
#         relate     { features = ["relation-adapted"] }
#         removed    { features = ["removal-names-unproven"] }
#         retire     { features = ["relation-adapted"] }
#         surgery    { features = ["relation-adapted"] }
#         test_moved { features = ["features-follow-moved-test"] }
#         unrelate   { features = ["relation-adapted"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ONE ADAPTION ('feature_adapt.py') and the judgement it
         rests on ('feature_relation.mismatch_list'): the feature files'
         'childs' and the map held against where the directories stand,
         and made to agree.

CHOICES: judged, relate, moved, unrelate, retire, test_moved, removed,
         surgery;

judged      every kind of disagreement on one tree, and a tree that
            agrees.

relate      'adapt_directory' on each disagreeing directory, parents
            first: a file written, a directory listed, the map made
            whole -- the files as they stand afterwards.

moved       a directory moved by hand below another component: the move
            is DETECTED from the 'childs' that still lists it, the entry
            is carried with its key, the map follows.

unrelate    'child_dropped': an entry nothing carries goes; one a
            directory carries is refused; one not listed is nothing.

retire      'map_retired': a published id whose feature is gone is bound
            to none; one whose feature stands is refused.

test_moved  the features a test links to, carried into the feature file
            of its new TEST directory, and the map with them.

removed     the features a removed test leaves without a linked run.

surgery     the text edits alone: a comment and the layout around an
            edit stay byte for byte.
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from hwut.engine.orchestrator.exploration import amend          # noqa E402
from hwut.engine.orchestrator.exploration import feature_adapt as adapt  # noqa E402
from   hwut.engine.orchestrator.exploration.feature_relation \
                                 import (mismatch_list,          # noqa E402
                                         relation_of_tree)


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def _write(root, path, text):
    """RETURN: None. Writes 'text' to 'root/path', directories made."""
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as handle:
        handle.write(text)


def _test(root, path, body=()):
    """RETURN: None. Writes a shell test at 'root/path' whose block
    holds a title and the lines of 'body'."""
    _write(root, path, "#! /bin/sh\n# @hwut {\n#     title = \"T\"\n%s# }\necho x\n"
           % "".join("#     %s\n" % line for line in body))
    os.chmod(os.path.join(root, path), 0o755)


def _shown(root, path):
    """RETURN: None. Prints the file at 'root/path', indented."""
    print("%s:" % path)
    with open(os.path.join(root, path), encoding="utf-8") as handle:
        for line in handle.read().splitlines(): print("    | %s" % line)


def _mismatches(root):
    """RETURN: None. Prints every disagreement of the tree, or 'none'."""
    found = mismatch_list(relation_of_tree(root))
    for each in found:
        print("    %-9s %-24s id=%-30s from=%s"
              % (each.kind, each.path, each.id, each.from_path))
    if not found: print("    none")


def _adapted(root, path):
    """RETURN: None. Adapts the directory at 'path' and prints what was
    said."""
    done = adapt.adapt_directory(root, os.path.join(root, path))
    print("adapt_directory(%s)" % path)
    for line in done.said_tuple: print("    %s" % line)
    if done.reason:               print("    REASON %s" % done.reason)
    if not done.said_tuple and not done.reason: print("    nothing to do")


def _agreeing_tree(root):
    """RETURN: None. A tree whose files agree with its directories:
    all / engine / {compare / {core}, plain}, with its map."""
    _write(root, "hwut-root.conf", "hwut {\n}\n")
    _write(root, "hwut-features.conf",
           'features {\n    title  = "All"\n    childs {\n'
           '        engine = "./engine"\n    }\n}\n')
    _write(root, "engine/hwut-features.conf",
           'features {\n    title = "Engine"\n'
           '    childs {\n'
           '        cmp   = "./compare"   # the heart\n'
           '        plain = "./plain"\n'
           '    }\n}\n')
    _write(root, "engine/compare/hwut-features.conf",
           'features {\n    title  = "Compare"\n'
           '    childs {\n        core = "./core"\n    }\n}\n')
    _write(root, "engine/compare/core/hwut-features.conf",
           'features {\n    title  = "Core"\n}\n')
    _write(root, "engine/compare/core/TEST/hwut-features.conf",
           'features {\n'
           '    childs {\n'
           '        line-pairing { title = "Two streams are aligned line by line." }\n'
           '        missing-side { }\n'
           '    }\n}\n')
    _write(root, "engine/compare/TEST/hwut-features.conf",
           'features {\n    childs {\n'
           '        whole-page { title = "A whole page is judged." }\n'
           '    }\n}\n')
    _write(root, "engine/plain/hwut-features.conf",
           'features {\n    title = "Plain"\n}\n')
    _write(root, "hwut-feature-map.conf",
           'map {\n'
           '    "engine.cmp.core.line-pairing" = "engine.cmp.core.line-pairing"\n'
           '    "engine.cmp.core.missing-side" = "engine.cmp.core.missing-side"\n'
           '    "engine.cmp.whole-page"        = "engine.cmp.whole-page"\n'
           '}\n')
    _test(root, "engine/compare/core/TEST/test-pair.sh",
          ['features = ["line-pairing", "missing-side"]'])
    _test(root, "engine/compare/core/TEST/test-side.sh",
          ['features = ["missing-side"]'])
    _test(root, "engine/compare/TEST/test-pages.sh",
          ['features = ["whole-page"]'])
    _test(root, "engine/plain/TEST/test-plain.sh")


def _disagreeing_tree(root):
    """RETURN: None. The agreeing tree, with one disagreement of every
    kind written into it."""
    _agreeing_tree(root)
    #  UNLISTED: 'plain' no longer listed. DANGLING: 'old'. TWIN: 'compare'
    #  listed under two keys.
    _write(root, "engine/hwut-features.conf",
           'features {\n    title = "Engine"\n'
           '    childs {\n'
           '        cmp   = "./compare"   # the heart\n'
           '        again = "./compare"\n'
           '        old   = "./old"\n'
           '    }\n}\n')
    #  NO_FILE: 'core' states nothing.
    os.remove(os.path.join(root, "engine/compare/core/hwut-features.conf"))
    #  UNMAPPED: a feature the map does not know.
    _write(root, "engine/compare/TEST/hwut-features.conf",
           'features {\n    childs {\n'
           '        whole-page { title = "A whole page is judged." }\n'
           '        extra      { title = "Written today." }\n'
           '    }\n}\n')
    #  MAP_GONE: an entry that means what stands nowhere.
    _write(root, "hwut-feature-map.conf",
           'map {\n'
           '    "engine.cmp.core.line-pairing" = "engine.cmp.core.line-pairing"\n'
           '    "engine.cmp.core.missing-side" = "engine.cmp.core.missing-side"\n'
           '    "engine.cmp.whole-page"        = "engine.cmp.whole-page"\n'
           '    "old-name"                     = "engine.old.thing"\n'
           '}\n')


def _in_tree(build, function):
    """RETURN: None. Calls 'function(root)' on a fresh tree that
    'build(root)' filled; removes it afterwards."""
    ground = tempfile.mkdtemp(prefix="hwut-adapt-")
    root   = os.path.join(ground, "tree")
    try:
        os.makedirs(root)
        build(root)
        function(root)
    finally:
        shutil.rmtree(ground, ignore_errors=True)


def test_judged():
    """RETURN: None. Prints the disagreements of two trees."""
    def agreeing(root):
        banner("a tree whose files agree with its directories")
        _mismatches(root)
    def disagreeing(root):
        banner("one disagreement of every kind")
        _mismatches(root)
    _in_tree(_agreeing_tree, agreeing)
    _in_tree(_disagreeing_tree, disagreeing)


def test_relate():
    """RETURN: None. Adapts every disagreeing directory, parents
    first, and prints the files."""
    def body(root):
        banner("before")
        _mismatches(root)
        banner("adapted, parents first")
        for path in (".", "engine", "engine/plain", "engine/compare/core",
                     "engine/compare/TEST", "engine/compare"):
            _adapted(root, path)
        banner("after: what no adaption heals stays")
        _mismatches(root)
        banner("the files")
        for path in ("engine/hwut-features.conf",
                     "engine/compare/core/hwut-features.conf",
                     "engine/compare/TEST/hwut-features.conf",
                     "hwut-feature-map.conf"):
            _shown(root, path)
    _in_tree(_disagreeing_tree, body)
    banner("a tree without a map")
    def mapless(root):
        os.remove(os.path.join(root, "hwut-feature-map.conf"))
        _mismatches(root)
        _adapted(root, ".")
        _mismatches(root)
        _shown(root, "hwut-feature-map.conf")
    _in_tree(_agreeing_tree, mapless)


def test_moved():
    """RETURN: None. Moves a directory by hand and adapts it."""
    def body(root):
        banner("'engine/compare/core' moved by hand to 'engine/plain/core'")
        shutil.move(os.path.join(root, "engine/compare/core"),
                    os.path.join(root, "engine/plain/core"))
        _mismatches(root)
        banner("adapted: the directory, then its TEST directory, whose "
               "features the map points elsewhere")
        _adapted(root, "engine/plain/core")
        _adapted(root, "engine/plain/core/TEST")
        _mismatches(root)
        banner("the files: where it came from, where it stands, the map")
        for path in ("engine/compare/hwut-features.conf",
                     "engine/plain/hwut-features.conf",
                     "hwut-feature-map.conf"):
            _shown(root, path)
        banner("the map is repointed, the published ids stay")
        relation = relation_of_tree(root)
        for published, target, _ in relation.feature_map.entry_tuple:
            print("    %-30s -> %s" % (published, target))
        banner("adapted again")
        _adapted(root, "engine/plain/core")
    _in_tree(_agreeing_tree, body)


def test_unrelate():
    """RETURN: None. Drops 'childs' entries, and what refuses."""
    def body(root):
        for label, path, name in (
                ("a directory that is gone",       "engine", "old"),
                ("a directory that stands",        "engine", "compare"),
                ("a directory that is not listed", "engine", "nobody")):
            banner(label)
            done = adapt.child_dropped(root, os.path.join(root, path), name)
            print("child_dropped(%s, '%s')" % (path, name))
            for line in done.said_tuple: print("    %s" % line)
            if done.reason:              print("    REASON %s" % done.reason)
            if not done.said_tuple and not done.reason:
                print("    nothing to do")
        banner("the file")
        _shown(root, "engine/hwut-features.conf")
    _in_tree(_disagreeing_tree, body)


def test_retire():
    """RETURN: None. Retires published ids, and what refuses."""
    def body(root):
        for label, published in (
                ("an id whose feature is gone",    "old-name"),
                ("an id whose feature stands",     "engine.cmp.whole-page"),
                ("an id the map does not hold",    "nobody"),
                ("an id retired already",          "old-name")):
            banner(label)
            done = adapt.map_retired(root, published)
            print("map_retired('%s')" % published)
            for line in done.said_tuple: print("    %s" % line)
            if done.reason:              print("    REASON %s" % done.reason)
            if not done.said_tuple and not done.reason:
                print("    nothing to do")
        banner("the map")
        _shown(root, "hwut-feature-map.conf")
        banner("what the relation says of it")
        relation = relation_of_tree(root)
        print("    retired: %s" % (relation.retired_tuple(),))
        _mismatches(root)
    _in_tree(_disagreeing_tree, body)


def _moved(root, source, target, test):
    """RETURN: None. Carries the features of 'test' from the TEST
    directory 'source' to 'target', as 'hwut.move' does after the
    author moved the application."""
    source_dir = os.path.join(root, source)
    target_dir = os.path.join(root, target)
    name_set   = adapt.linked_name_set(source_dir, test=test)
    shutil.move(os.path.join(source_dir, test),
                os.path.join(target_dir, test))
    done = adapt.test_moved(source_dir, target_dir, name_set,
                            adapt.linked_name_set(source_dir, without=test))
    print("test_moved(%s -> %s, %s)   links %s"
          % (source, target, test, sorted(name_set)))
    for line in done.said_tuple: print("    %s" % line)
    if done.reason:              print("    REASON %s" % done.reason)
    if not done.said_tuple and not done.reason: print("    nothing to do")


def test_test_moved():
    """RETURN: None. Moves tests across TEST directories and prints the
    feature files and the map."""
    def body(root):
        core, page = "engine/compare/core/TEST", "engine/compare/TEST"
        banner("a test whose features another test here still links to: "
               "the features are copied, the old stay")
        _moved(root, core, page, "test-pair.sh")
        _shown(root, core + "/hwut-features.conf")
        _shown(root, page + "/hwut-features.conf")
        _shown(root, "hwut-feature-map.conf")
        banner("the last test linking to a feature: the feature follows, "
               "its published id with it")
        _moved(root, core, page, "test-side.sh")
        _shown(root, core + "/hwut-features.conf")
        _shown(root, "hwut-feature-map.conf")
        banner("into a directory without a feature file")
        _moved(root, page, "engine/plain/TEST", "test-pages.sh")
        _shown(root, "engine/plain/TEST/hwut-features.conf")
        _shown(root, "hwut-feature-map.conf")
        banner("a test that links to nothing")
        _moved(root, "engine/plain/TEST", core, "test-plain.sh")
    _in_tree(_agreeing_tree, body)


def test_removed():
    """RETURN: None. Prints the features a removal leaves unproven."""
    def body(root):
        core = os.path.join(root, "engine/compare/core/TEST")
        _test(root, "engine/compare/core/TEST/test-many.sh",
              ['choices {', '    a { features = ["line-pairing"] }',
               '    b { features = ["missing-side"] }', '}'])
        for test, choice in (("test-pair.sh", None), ("test-side.sh", None),
                             ("test-many.sh", "a"), ("test-many.sh", None),
                             ("test-nobody.sh", None)):
            print("%-14s %-5s leaves unproven: %s"
                  % (test, choice,
                     list(adapt.unproven_by_removal(core, test, choice))))
        banner("with 'test-side.sh' and 'test-many.sh' gone first")
        os.remove(os.path.join(core, "test-side.sh"))
        os.remove(os.path.join(core, "test-many.sh"))
        print("%-14s %-5s leaves unproven: %s"
              % ("test-pair.sh", None,
                 list(adapt.unproven_by_removal(core, "test-pair.sh"))))
        banner("a directory without a feature file")
        print(list(adapt.unproven_by_removal(
            os.path.join(root, "engine/plain/TEST"), "test-plain.sh")))
    _in_tree(_agreeing_tree, body)


SURGERY_TEXT = """# What compare is made of.
features {
    title  = "Compare"            # shown in the report

    childs {
        # the alignment
        core = "./core"
        "odd id" = "./odd"   # stays
    }
}
"""

MAP_TEXT = """# the published ids
map {
    "scroll"   = "display.scroll"   # customers know it
    "old"      = "display.old"
}
"""


def test_surgery():
    """RETURN: None. Prints texts after each edit."""
    def shown(text):
        for line in text.splitlines(): print("    | %s" % line)

    banner("the text")
    shown(SURGERY_TEXT)
    banner("two childs added")
    text = adapt.child_text_added(SURGERY_TEXT, "pat", "patterns")
    text = adapt.child_text_added(text, "007", "digits")
    shown(text)
    banner("two childs removed (by directory); what each carried")
    text, first  = adapt.child_text_removed(text, "core")
    text, second = adapt.child_text_removed(text, "odd")
    text, third  = adapt.child_text_removed(text, "nobody")
    print("    carried: %s | %s | %s" % (first, second, third))
    shown(text)

    banner("nothing listed yet: 'childs' is made")
    text = adapt.child_text_added('features {\n    title = "New"\n}\n',
                                  "first", "first-dir")
    shown(text)
    banner("the forms on one line")
    text = adapt.child_text_added('features { childs { a = "./a" } }\n',
                                  "b", "b")
    shown(text)
    text, carried = adapt.child_text_removed(text, "a")
    print("    carried: %s" % carried)
    shown(text)

    banner("the map: entered, bound to another, retired")
    container = amend.named_container(MAP_TEXT, "map")
    text = adapt.map_text_added(MAP_TEXT, container, "zoom", "display.zoom")
    text = adapt.map_text_bound(text, amend.named_container(text, "map"),
                                "scroll", "display.game.scroll")
    text = adapt.map_text_bound(text, amend.named_container(text, "map"),
                                "old", None)
    text = adapt.map_text_bound(text, amend.named_container(text, "map"),
                                "nobody", "x")
    shown(text)
    banner("a feature with a doc in triple quotes: the text around it "
           "is not hurt")
    text = ('features {\n    childs {\n        a {\n            doc = '
            '\"\"\"\n                says "x" and } and { too\n'
            '            \"\"\"\n        }\n        b { }\n    }\n}\n')
    shown(text)
    from hwut.engine.orchestrator.exploration import feature_adapt as fa
    text = fa._feature_removed(text, "a")
    shown(text)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Feature files and the map adapted to the "
                     "directories",
        choice_map = {
            "judged":     test_judged,
            "relate":     test_relate,
            "moved":      test_moved,
            "unrelate":   test_unrelate,
            "retire":     test_retire,
            "test_moved": test_test_moved,
            "removed":    test_removed,
            "surgery":    test_surgery,
        },
    ).run()
