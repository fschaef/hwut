#! /usr/bin/env python3
# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
"""
______________________________________________________________________________
PURPOSE: THE PYTHON A SET OF FILES NEEDS -- the transitive closure of
         'import', over the modules of this tree.

    python3 adm/dependency.py <path>...        # the closure, one per line
    python3 adm/dependency.py --seeds <dir>    # what a directory seeds

'bundle.sh --deps' asks this: bundling one directory bundles a package
that will not import, because the modules it imports live elsewhere.
The closure answers WHICH ELSEWHERE.

ONE ANALYSIS, ONE PLACE. The walk, the dotted index and the per-module
imports are 'adm/import_graph.py's -- 'module_tuple', 'by_dotted_db',
'imported_tuple', '_matched'. This module adds only the CLOSURE over
them, so an import this tree resolves one way for the graph cannot
resolve another way for a bundle.

WHAT IS NOT FOUND IS NOT SILENT. A module that will not parse is
reported by name: a bundle short of a file it needed is a bundle that
fails on the far side, where nobody can fix it.
______________________________________________________________________________
"""
import os
import sys

_cur = os.path.abspath(os.path.dirname(__file__))
while os.path.basename(_cur) != "vut":
    _parent = os.path.dirname(_cur)
    if _parent == _cur:
        sys.exit("dependency.py: no directory 'vut' above '%s'" % __file__)
    _cur = _parent
sys.path.insert(0, os.path.dirname(_cur))
ROOT = _cur

from vut.adm.import_graph import (module_tuple, by_dotted_db,
                                  imported_tuple, _matched)


def seed_tuple(path_tuple, module_path_tuple):
    """
    RETURN: tuple[str], the modules of this tree the given paths NAME,
            as paths relative to the tree root.

    A DIRECTORY SEEDS EVERY MODULE BELOW IT; a file seeds itself where
    it is Python and nothing where it is not -- a GOOD file is not a
    module, and a shell script imports nothing.
    """
    found = []
    for path in path_tuple:
        rel = os.path.relpath(os.path.abspath(path), ROOT).replace(os.sep, "/")
        if rel.endswith(".py"):
            if rel in module_path_tuple: found.append(rel)
            continue
        prefix = rel.rstrip("/") + "/"
        found.extend(m for m in module_path_tuple if m.startswith(prefix))
    return tuple(sorted(set(found)))


def closure_of(seed_path_tuple, module_path_tuple, by_dotted):
    """
    RETURN: [0] tuple[str], every module of this tree reachable from
                the seeds by 'import', the seeds included, sorted.
            [1] tuple[(str, str)], (module, complaint) for every module
                that could not be read -- reported, never dropped.

    BREADTH FIRST OVER THE IMPORTS. A module already seen is not
    walked again, so a cycle terminates; a dotted name this tree does
    not answer to -- 'os', 'asyncio', a third party -- is not a file
    of ours and is passed over in silence.
    """
    seen, order, fault_list = set(seed_path_tuple), list(seed_path_tuple), []
    queue = list(seed_path_tuple)
    while queue:
        module_path = queue.pop(0)
        dotted_tuple, complaint = imported_tuple(ROOT, module_path)
        if complaint is not None:
            fault_list.append((module_path, complaint))
            continue
        for dotted in dotted_tuple:
            hit = _matched(dotted, by_dotted)
            if hit is None or hit in seen: continue
            seen.add(hit); order.append(hit); queue.append(hit)
    return tuple(sorted(order)), tuple(fault_list)


def needed_tuple(path_tuple):
    """
    RETURN: [0] tuple[str], every module the given paths need, as paths
                relative to the tree root -- the seeds and everything
                they import, transitively.
            [1] tuple[(str, str)], the modules that could not be read.
    """
    module_path_tuple = module_tuple(ROOT)
    by_dotted         = by_dotted_db(module_path_tuple)
    return closure_of(seed_tuple(path_tuple, module_path_tuple),
                      module_path_tuple, by_dotted)


def main(argv=None, write=None):
    """
    RETURN: int, 0 where every module read; 1 where one did not.

    Writes the closure, one path per line, relative to the tree root
    -- the form 'bundle.sh --from-list' takes.
    """
    if argv is None:  argv  = sys.argv[1:]
    if write is None: write = print
    seeds_f = "--seeds" in argv
    path_list = [word for word in argv if not word.startswith("-")]
    if not path_list:
        write("usage: dependency.py <path>...   [--seeds]")
        return 1
    if seeds_f:
        module_path_tuple = module_tuple(ROOT)
        for path in seed_tuple(path_list, module_path_tuple): write(path)
        return 0
    needed, fault_tuple = needed_tuple(path_list)
    for path in needed: write(path)
    for module_path, complaint in fault_tuple:
        sys.stderr.write("FAULT: %s -- %s\n" % (module_path, complaint))
    return 1 if fault_tuple else 0


if __name__ == "__main__":
    sys.exit(main())
