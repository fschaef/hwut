#! /usr/bin/env python3
#
# @hwut {
#     title      = "Feature statements adapted: ids, parent, childs against the directories"
#     choices    = ["judged", "moved", "relate", "removed", "surgery", "test_moved", "unrelate"]
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ONE ADAPTION ('feature_adapt.py') and the judgement it
         rests on ('feature_relation.mismatch_list'): the statement
         files' ids, 'parent' and 'childs' held against where the
         directories stand, and made to agree.

CHOICES: judged, relate, moved, unrelate, test_moved, removed, surgery;

judged      every kind of disagreement on one tree, and a tree that
            agrees.

relate      'adapt_directory' on each disagreeing directory, parents
            first: an id given, 'parent' set, the id entered above --
            the files as they stand afterwards.

moved       a directory moved by hand below another component: the move
            is DETECTED from the 'childs' that still lists it, and the
            entry is carried, sentence and all.

unrelate    'child_dropped': an entry nothing carries goes; one a
            directory carries is refused; one not listed is nothing.

test_moved  the features a test links to, carried into the feature file
            of its new TEST directory under that file's next number.

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

from   vut.engine.orchestrator.exploration import amend          # noqa E402
from   vut.engine.orchestrator.exploration import feature_adapt as adapt  # noqa E402
from   vut.engine.orchestrator.exploration.feature_relation \
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
        print("    %-9s %-24s id=%-10s from=%s"
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
    """RETURN: None. A tree whose statements agree with its
    directories: all / eng / {cmp / {core, TEST}, plain}."""
    _write(root, "hwut-root.conf", "hwut {\n}\n")
    _write(root, "hwut-composition.conf",
           'component {\n    id     = "all"\n    title  = "All"\n'
           '    childs = ["eng"]\n}\n')
    _write(root, "engine/hwut-composition.conf",
           'component {\n    id    = "eng"\n    title = "Engine"\n'
           '    parent = "all"\n'
           '    childs {\n'
           '        cmp   = "Gives the verdict."   # the heart\n'
           '        plain = "Plain things."\n'
           '    }\n}\n')
    _write(root, "engine/compare/hwut-composition.conf",
           'component {\n    id     = "cmp"\n    title  = "Compare"\n'
           '    parent { eng = "The engine\'s verdict rests on it." }\n'
           '    childs {\n'
           '        core      = "Aligns two streams line by line."\n'
           '        cmp-proof = "Proves the whole comparison on real pages."\n'
           '    }\n}\n')
    _write(root, "engine/compare/core/hwut-composition.conf",
           'component {\n    id     = "core"\n    title  = "Core"\n'
           '    parent { cmp = "Alignment is what compare shows." }\n'
           '    childs { core-proof = "The proof of pairing." }\n}\n')
    _write(root, "engine/compare/core/TEST/hwut-features.conf",
           'features {\n    id     = "core-proof"\n'
           '    parent { core = "What \'core\' promises, proven." }\n'
           '    issued = 2\n'
           '    1 { name  = "line-pairing"\n'
           '        title = "Two streams are aligned line by line." }\n'
           '    2 { name = "missing-side" }\n}\n')
    _write(root, "engine/compare/TEST/hwut-features.conf",
           'features {\n    id     = "cmp-proof"\n    parent = "cmp"\n'
           '    issued = 1\n'
           '    1 { name = "whole-page"  title = "A whole page is judged." }\n}\n')
    _write(root, "engine/plain/hwut-composition.conf",
           'component { id = "plain"  parent = "eng" }\n')
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
    #  NO_ID at the top; UNJUDGED below it.
    _write(root, "hwut-composition.conf",
           'component {\n    title  = "All"\n    childs = ["eng"]\n}\n')
    #  GONE: 'old'. UNLISTED: 'plain' no longer listed.
    _write(root, "engine/hwut-composition.conf",
           'component {\n    id    = "eng"\n    title = "Engine"\n'
           '    parent = "all"\n'
           '    childs {\n'
           '        cmp = "Gives the verdict."   # the heart\n'
           '        old = "Was here once."\n'
           '    }\n}\n')
    #  PARENT: 'core' names another parent.
    _write(root, "engine/compare/core/hwut-composition.conf",
           'component {\n    id     = "core"\n    title  = "Core"\n'
           '    parent { compare = "Alignment is what compare shows." }\n'
           '    childs { core-proof = "The proof of pairing." }\n}\n')
    #  NO_ID in a TEST directory.
    _write(root, "engine/compare/TEST/hwut-features.conf",
           'features {\n    parent = "cmp"\n    issued = 1\n'
           '    1 { name = "whole-page"  title = "A whole page is judged." }\n}\n')
    #  TWIN: a second child of 'eng' calling itself 'cmp'.
    _write(root, "engine/twin/hwut-composition.conf",
           'component { id = "cmp"  parent = "eng" }\n')
    _test(root, "engine/twin/TEST/test-twin.sh")


def _in_tree(build, function):
    """RETURN: None. Calls 'function(root)' on a fresh tree that
    'build(root)' filled; removes it afterwards."""
    #  THE TREE'S OWN NAME IS FIXED: a statement file without an id is
    #  given its directory's name, and a temporary name is no content
    #  for a nominal.
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
        banner("a tree whose statements agree with its directories")
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
        for path in ("hwut-composition.conf", "engine/hwut-composition.conf",
                     "engine/compare/hwut-composition.conf",
                     "engine/compare/core/hwut-composition.conf",
                     "engine/compare/TEST/hwut-features.conf"):
            _shown(root, path)
        banner("a directory without a statement file")
        _adapted(root, "engine/twin/TEST")
    _in_tree(_disagreeing_tree, body)


def test_moved():
    """RETURN: None. Moves a directory by hand and adapts it."""
    def body(root):
        banner("'engine/compare/core' moved by hand to 'engine/plain/core'")
        shutil.move(os.path.join(root, "engine/compare/core"),
                    os.path.join(root, "engine/plain/core"))
        _mismatches(root)
        banner("adapted")
        _adapted(root, "engine/plain/core")
        _mismatches(root)
        banner("the three files: where it came from, where it stands, itself")
        for path in ("engine/compare/hwut-composition.conf",
                     "engine/plain/hwut-composition.conf",
                     "engine/plain/core/hwut-composition.conf"):
            _shown(root, path)
        banner("what stood below it travelled with it and still agrees")
        _shown(root, "engine/plain/core/TEST/hwut-features.conf")
        banner("adapted again")
        _adapted(root, "engine/plain/core")
    _in_tree(_agreeing_tree, body)


def test_unrelate():
    """RETURN: None. Drops 'childs' entries, and what refuses."""
    def body(root):
        for label, path, child_id in (
                ("an id nothing carries",        "engine", "old"),
                ("an id a directory carries",    "engine", "cmp"),
                ("an id that is not listed",     "engine", "nobody"),
                ("a directory with a feature file", "engine/compare/TEST",
                                                 "x")):
            banner(label)
            done = adapt.child_dropped(root, os.path.join(root, path),
                                       child_id)
            print("child_dropped(%s, '%s')" % (path, child_id))
            for line in done.said_tuple: print("    %s" % line)
            if done.reason:              print("    REASON %s" % done.reason)
            if not done.said_tuple and not done.reason:
                print("    nothing to do")
        banner("the file")
        _shown(root, "engine/hwut-composition.conf")
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
    feature files."""
    def body(root):
        core, page = "engine/compare/core/TEST", "engine/compare/TEST"
        banner("a test whose features another test here still links to, "
               "or alone")
        _moved(root, core, page, "test-pair.sh")
        _shown(root, core + "/hwut-features.conf")
        _shown(root, page + "/hwut-features.conf")
        banner("the last test linking to a feature follows")
        _moved(root, core, page, "test-side.sh")
        _shown(root, core + "/hwut-features.conf")
        banner("moved back: the feature receives a NEW number there")
        _moved(root, page, core, "test-side.sh")
        _shown(root, core + "/hwut-features.conf")
        _shown(root, page + "/hwut-features.conf")
        banner("into a directory without a feature file")
        _moved(root, page, "engine/plain/TEST", "test-pages.sh")
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
component {
    title  = "Compare"            # shown in the report
    parent { eng = "The engine's verdict rests on it." }

    childs {
        # the alignment
        core = "Aligns two streams."
        "odd id" = "Quoted, with \\"quotes\\" inside."   # stays
    }
}
"""


def test_surgery():
    """RETURN: None. Prints texts after each edit."""
    def shown(text):
        for line in text.splitlines(): print("    | %s" % line)
    def outer(text):
        return amend.named_container(text, "component")

    banner("the text")
    shown(SURGERY_TEXT)
    banner("id set, parent renamed (its sentence kept), a child added")
    text = adapt.id_text_set(SURGERY_TEXT, outer(SURGERY_TEXT), "cmp")
    text = adapt.parent_text_set(text, outer(text), "engine 2")
    text = adapt.child_text_added(text, outer(text), "cmp-proof",
                                  '"Proves it."')
    text = adapt.child_text_added(text, outer(text), "no sentence", None)
    shown(text)
    banner("two childs removed; what each carried")
    text, first  = adapt.child_text_removed(text, outer(text), "core")
    text, second = adapt.child_text_removed(text, outer(text), "odd id")
    text, third  = adapt.child_text_removed(text, outer(text), "nobody")
    print("    carried: %s | %s | %s" % (first, second, third))
    shown(text)

    banner("the forms without sentences, on one line")
    text = 'component { id = "cmp"  parent = "eng"  childs = ["core"] }\n'
    shown(text)
    text = adapt.parent_text_set(text, outer(text), "all")
    text = adapt.child_text_added(text, outer(text), "pat", '"ignored"')
    text, carried = adapt.child_text_removed(text, outer(text), "core")
    print("    carried: %s" % carried)
    shown(text)

    banner("nothing stated yet")
    text = 'component {\n    title = "New"\n}\n'
    text = adapt.id_text_set(text, outer(text), "new")
    text = adapt.parent_text_set(text, outer(text), "all")
    text = adapt.child_text_added(text, outer(text), "first", None)
    shown(text)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Feature statements adapted: ids, parent, childs "
                     "against the directories",
        choice_map = {
            "judged":     test_judged,
            "relate":     test_relate,
            "moved":      test_moved,
            "unrelate":   test_unrelate,
            "test_moved": test_test_moved,
            "removed":    test_removed,
            "surgery":    test_surgery,
        },
    ).run()
