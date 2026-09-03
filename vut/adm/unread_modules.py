#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE
       UNREAD MODULES -- every '.py' file no ENTRY POINT REACHES, at
       MODULE depth ('import_graph.py --depth=0' would still merge
       them into their component; this asks module by module).

DESCRIPTION
       REUSES 'import_graph.py's OWN reading: 'module_tuple' finds
       every module, 'imported_tuple' reads what each one imports,
       '_matched' resolves a dotted name back to a module by its
       longest tail -- the same static, AST-only fact import_graph
       itself relies on (no call graph, no dynamic dispatch guessed).

       REACHABILITY, WALKED FROM ROOTS -- not bare in-degree. Two
       modules that import only EACH OTHER answer to no root and
       are DEAD however many edges point at them from inside their
       own island; a raw "zero incoming edges" filter misses exactly
       this shape (found the hard way: 'feed.py' and 'tui.py',
       engine/operations/interaction, import one another and nothing
       else in the tree imports either).

       THE ROOTS, and so the classification of what the walk never
       reaches:

           ENTRY     runs BY NAME, never imported: 'bin/*.py' (no
                     '.py' suffix on the command line, but the
                     interpreter still parses one), or a module
                     whose own text tests '__name__ == "__main__"'
           TEST      lives under a 'TEST/' directory: HWUT runs these
                     by name too, never by import
           PACKAGE   an '__init__.py' -- a package is entered by its
                     own name whether or not anything imports the file
           DEAD      unreached from every root. This is the
                     interesting bucket -- 'feed.py'/'tui.py' and
                     'analogy_db.py'/'semantics.py' (compare RATIONALE
                     C-3, deleted) were both mutual islands here
                     before deletion.

       DEAD IS A CLAIM ABOUT IMPORTS, NOT ABOUT USE: a module read via
       'importlib.import_module' with a name built at runtime, or
       loaded by a shell script, casts no static edge and would show
       DEAD wrongly ('services/_config.py', reached only through a
       bare 'import _config' after a sys.path trick, is exactly this
       case and is NOT dead). Read every DEAD hit before deleting
       anything -- this tool finds candidates, C-3's own care (grep
       for the name elsewhere, check every road) is still the
       reader's.
______________________________________________________________________________
"""
import ast
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import import_graph as G                                          # noqa E402


def entry_point_f(root, module_path):
    """
    RETURN: True, this module runs BY NAME rather than by import:
            it sits directly under a 'bin/' directory, or its own text
            guards a '__main__' block.
    """
    if module_path.split("/")[0] == "bin": return True
    whole = os.path.join(root, module_path)
    try:
        tree = ast.parse(open(whole, encoding="utf-8").read())
    except (SyntaxError, UnicodeDecodeError, OSError):
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.If): continue
        test = node.test
        if (isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == "__name__"):
            return True
    return False


def unread_db(root, exclude_tuple=()):
    """
    RETURN: dict, module path -> one of 'ENTRY', 'TEST', 'PACKAGE',
            'DEAD' -- every module NOT REACHABLE from any entry point,
            classified.

    REACHABILITY, NOT BARE IN-DEGREE: two modules that import only
    EACH OTHER have one incoming edge apiece and would pass an
    in-degree=0 filter clean, while nothing live reaches either --
    exactly the shape of 'feed.py' and 'tui.py' (engine/operations/
    interaction), which import one another and answer to no one else.
    The graph is walked from every ENTRY and TEST module instead
    (PACKAGE '__init__.py' files are roots too: a package is entered
    by its own name, whether or not anything imports the file); what
    the walk never reaches is DEAD, however many edges point at it
    from inside its own island.
    """
    path_tuple = G.module_tuple(root, exclude_tuple)
    by_dotted  = G.by_dotted_db(path_tuple)

    edge_db = {}
    for path in path_tuple:
        name_tuple, _fault = G.imported_tuple(root, path)
        target_set = set()
        for dotted in name_tuple:
            target = G._matched(dotted, by_dotted)
            if target is not None and target != path:
                target_set.add(target)
        edge_db[path] = target_set

    kind_db = {}
    for path in path_tuple:
        if path.endswith("/__init__.py") or path == "__init__.py":
            kind_db[path] = "PACKAGE"
        elif "/TEST/" in ("/" + path):
            kind_db[path] = "TEST"
        elif entry_point_f(root, path):
            kind_db[path] = "ENTRY"

    #  THE WALK: every root's own imports are reachable, and so is
    #  whatever THEY import, transitively -- an island answers to no
    #  root and stays unvisited whole.
    reached  = set(kind_db)
    frontier = list(kind_db)
    while frontier:
        path = frontier.pop()
        for target in edge_db.get(path, ()):
            if target in reached: continue
            reached.add(target)
            frontier.append(target)

    result = {}
    for path in path_tuple:
        if path in kind_db:
            result[path] = kind_db[path]
        elif path not in reached:
            result[path] = "DEAD"
    return result


def main(argv=None, write=None):
    """
    RETURN: int, 0 always -- this reports, it does not judge a
            layering rule (there is no fault to fail a build on: an
            unread module is a candidate for a person, not a
            violation for a machine).
    """
    if argv is None: argv = sys.argv[1:]
    if write is None: write = print
    root  = "."
    exclude_list = []
    for argument in argv:
        if argument.startswith("--exclude="):
            exclude_list.append(argument[len("--exclude="):])
        elif argument in ("--help", "-h"):
            write(__doc__.strip())
            write("")
            write("    adm/unread_modules.py [<root>] [--exclude=<glob>]...")
            return 0
        elif not argument.startswith("-"):
            root = argument
    db = unread_db(root, tuple(exclude_list))
    for bucket in ("DEAD", "PACKAGE", "ENTRY", "TEST"):
        member_list = sorted(p for p, b in db.items() if b == bucket)
        if not member_list: continue
        write("%s (%d)" % (bucket, len(member_list)))
        for path in member_list:
            write("    %s" % path)
    if not any(db.values()):
        write("every module is reached by something")
    return 0


if __name__ == "__main__":
    sys.exit(main())
