#! /usr/bin/env python3
#
# @hwut {
#     title      = "The feature wish: -F and -k choose runs by feature and key"
#     choices {
#         glob    { features = ["feature-wish-selects"] }
#         keys    { features = ["feature-wish-selects"] }
#         map     { features = ["feature-wish-selects"] }
#         refused { features = ["feature-wish-selects"] }
#         view    { features = ["feature-wish-selects"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FEATURE WISH ('feature_wish.py'): which test runs '-F' (an id
         glob) and '-k' (an expression over keys) want, over a tree with
         ids, keys that travel down, and a feature map.

CHOICES: glob, view, keys, map, refused;

glob     the id glob alone: '*', '**', braces, a bare key, a component
         bringing its subtree.

view     the runs wanted over a tree: -F alone, several -F (a union),
         -F and -k together (ONE feature must satisfy both), a run
         linked to nothing (never wanted).

keys     the expression over EFFECTIVE keys: keys flowing down from a
         component, never up; AND, OR, NOT, ','.

map      a published id means what the map binds it to; a glob-free id
         that is no published id is a glob.

refused  a retired id, a key no feature carries, a brace not closed:
         refused by name.
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from hwut.engine.orchestrator.exploration import feature_wish    # noqa E402
from hwut.engine.orchestrator.exploration.task_list import SelectionError  # noqa E402
from hwut.engine.orchestrator.plan.wish import Wish, parse_wish  # noqa E402


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


def _test(root, path, body):
    """RETURN: None. Writes a shell test whose block holds 'body'."""
    _write(root, path, "#! /bin/sh\n# @hwut {\n%s\n# }\necho x\n"
           % "\n".join("#     " + line for line in body))


def _tree(root):
    """RETURN: None. display / game, console, and engine / comparison /
    csp, scheduler, with keys, the runs linking to them, and the map."""
    _write(root, "hwut-root.conf", "hwut {\n}\n")
    _write(root, "hwut-features.conf",
           'features {\n  childs { display = "./display"  engine = "./engine"'
           '  console = "./console" }\n}\n')
    _write(root, "display/hwut-features.conf",
           'features {\n  keys = ["display-related"]\n'
           '  childs { game = "./game" }\n}\n')
    _write(root, "display/game/hwut-features.conf", 'features {\n}\n')
    _write(root, "display/game/TEST/hwut-features.conf",
           'features {\n  childs {\n'
           '    scroll { title = "The screen scrolls."  keys = ["gui"] }\n'
           '    zoom   { title = "The screen zooms." }\n'
           '    007    { title = "Loads fast."  keys = ["heavy-test"] }\n'
           '  }\n}\n')
    _test(root, "display/game/TEST/test-view.sh",
          ['title = "View"', 'features = ["scroll"]',
           'choices { plain { }  fast { features = ["scroll", "007"] }'
           '  zoomed { features = ["zoom"] } }'])
    _write(root, "console/hwut-features.conf",
           'features {\n  keys = ["display-related"]\n}\n')
    _write(root, "console/TEST/hwut-features.conf",
           'features {\n  childs { echo { title = "Echo." } }\n}\n')
    _test(root, "console/TEST/test-echo.sh",
          ['title = "Echo"', 'features = ["echo"]'])
    _write(root, "engine/hwut-features.conf",
           'features {\n  childs { comparison = "./comparison"\n'
           '           orchestrator = "./orchestrator" }\n}\n')
    _write(root, "engine/comparison/hwut-features.conf",
           'features {\n  childs { csp = "./csp"  other = "./other" }\n}\n')
    _write(root, "engine/comparison/csp/hwut-features.conf",
           'features {\n  keys = ["computational"]\n}\n')
    _write(root, "engine/comparison/csp/TEST/hwut-features.conf",
           'features {\n  childs { solve { title = "Solves." } }\n}\n')
    _test(root, "engine/comparison/csp/TEST/test-solve.sh",
          ['title = "Solve"', 'features = ["solve"]'])
    _write(root, "engine/comparison/other/hwut-features.conf",
           'features {\n}\n')
    _write(root, "engine/comparison/other/TEST/hwut-features.conf",
           'features {\n  childs { plain { title = "Plain." } }\n}\n')
    _test(root, "engine/comparison/other/TEST/test-plain.sh",
          ['title = "Plain"', 'features = ["plain"]'])
    _write(root, "engine/orchestrator/hwut-features.conf",
           'features {\n  childs { scheduler = "./scheduler" }\n}\n')
    _write(root, "engine/orchestrator/scheduler/hwut-features.conf",
           'features {\n  keys = ["computational"]\n}\n')
    _write(root, "engine/orchestrator/scheduler/TEST/hwut-features.conf",
           'features {\n  childs { order { title = "Orders." } }\n}\n')
    _test(root, "engine/orchestrator/scheduler/TEST/test-order.sh",
          ['title = "Order"', 'features = ["order"]'])
    _test(root, "engine/orchestrator/scheduler/TEST/test-nothing.sh",
          ['title = "Nothing"'])
    _write(root, "hwut-feature-map.conf",
           'map {\n'
           '    "xyz"   = "display.game.scroll"\n'
           '    "ghost" = none\n'
           '    "display.game.zoom" = "display.game.zoom"\n'
           '}\n')


def _wanted(root, argv):
    """RETURN: None. Prints the runs the wish 'argv' wants, or why not."""
    wish, rest = parse_wish(argv)
    print("%-44s" % " ".join(argv), end="  ")
    try:
        case_set = feature_wish.case_set_of(root, wish)
    except SelectionError as error:
        print("REFUSED: %s" % error)
        return
    print("%i run(s)" % len(case_set))
    for path, choice in sorted(case_set, key=lambda x: (x[0], x[1] or "")):
        print("    %s %s" % (os.path.relpath(path, root), choice))


def _in_tree(function):
    """RETURN: None. Calls 'function(root)' on a fresh tree."""
    feature_wish.forget_views()
    root = os.path.realpath(tempfile.mkdtemp(prefix="hwut-fwish-"))
    try:
        _tree(root)
        function(root)
    finally:
        feature_wish.forget_views()
        shutil.rmtree(root, ignore_errors=True)


def test_glob():
    """RETURN: None. The glob matcher over chains of keys."""
    chain = ("engine", "comparison", "csp", "solve")
    for glob in ("engine.comparison.csp.solve", "engine.comparison.csp",
                 "engine.comparison", "engine", "engine.*", "engine.*.csp",
                 "engine.**", "**", "**.solve", "solve", "csp", "comparison",
                 "**.csp.**", "engine.**.solve", "engine.**.csp.solve",
                 "engine.{comparison,x}.csp", "{display,engine}.**",
                 "{a.b,engine}", "e*.c*.csp", "engine.?omparison", "display",
                 "engine.csp", "engine.comparison.solve", "*"):
        print("%-30s %s" % (glob, feature_wish.glob_hit_f(glob, chain)))
    banner("braces expanded")
    for glob in ("a", "{a,b}", "{a,b}.{c,d}", "x.{a,{b,c}}.y", "{a.b,c}"):
        print("%-16s %s" % (glob, feature_wish.brace_alternative_tuple(glob)))
    banner("braces unbalanced")
    for glob in ("{a,b", "a}"):
        try:
            feature_wish.brace_alternative_tuple(glob)
        except SelectionError as error:
            print("%-8s REFUSED: %s" % (glob, error))


def test_view():
    """RETURN: None. The runs a wish wants over a tree."""
    def body(root):
        for argv in (["-F", "scroll"],
                     ["-F", "display"],
                     ["-F", "display.game.zoom"],
                     ["-F", "display.game.scroll", "-F", "console"],
                     ["-F", "engine.**"],
                     ["-F", "**.plain"],
                     ["-F", "*"],
                     ["-F", "nothing-like-it"],
                     ["-F", "display", "-k", "gui"]):
            _wanted(root, argv)
        banner("a run linked to nothing is never wanted")
        _wanted(root, ["-F", "engine.orchestrator.**"])
        _wanted(root, ["-k", "all"])
        banner("narrowing: -F and the rest of the wish stand together")
        wish, _ = parse_wish(["-F", "display", "--fail"])
        print("%s   asks features: %s" % (wish, wish.asks_feature_f()))
    _in_tree(body)


def test_keys():
    """RETURN: None. Keys flow down, never up."""
    def body(root):
        for argv in (["-k", "display-related"],
                     ["-k", "gui"],
                     ["-k", "gui AND display-related"],
                     ["-k", "display-related AND NOT gui"],
                     ["-k", "gui, computational"],
                     ["-k", "computational"],
                     ["-k", "heavy-test OR gui"],
                     ["-k", "computational AND NOT heavy-test"],
                     ["-k", "(gui OR heavy-test) AND display-related"],
                     ["-F", "engine", "-k", "computational"],
                     ["-F", "display", "-k", "computational"]):
            _wanted(root, argv)
        banner("what a component 'has': derived from the features below")
        from hwut.engine.orchestrator.exploration.feature_relation \
            import relation_of_tree
        relation = relation_of_tree(root)
        for path in sorted(relation.component_db):
            print("%-34s %s" % (path, relation.derived_key_tuple(path)))
    _in_tree(body)


def test_map():
    """RETURN: None. Published ids."""
    def body(root):
        for argv in (["-F", "xyz"],
                     ["-F", "display.game.zoom"],
                     ["-F", "display.game.scroll"],
                     ["-F", "xyz", "-F", "display.game.zoom"]):
            _wanted(root, argv)
    _in_tree(body)


def test_refused():
    """RETURN: None. What the wish cannot mean over the tree."""
    def body(root):
        for argv in (["-F", "ghost"],
                     ["-F", "scroll", "-F", "ghost"],
                     ["-k", "no-such-key"],
                     ["-k", "gui AND no-such AND other"],
                     ["-F", "{a,b"],
                     ["-F", "a}"]):
            _wanted(root, argv)
        banner("no root reaches the selection")
        from hwut.engine.orchestrator.exploration.task_list_query \
            import CTestTaskListQuery
        wish, _ = parse_wish(["-F", "scroll"])
        try:
            CTestTaskListQuery(wish).get_test_cases(())
        except SelectionError as error:
            print("REFUSED: %s" % error)
    _in_tree(body)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The feature wish: -F and -k choose runs by feature "
                     "and key",
        choice_map = {
            "glob":    test_glob,
            "view":    test_view,
            "keys":    test_keys,
            "map":     test_map,
            "refused": test_refused,
        },
    ).run()
