"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.features.tree' COMMAND LINE -- the tree of features as
         the central file states it (spec 23 VERSION 10 section 8, R-96).

    hwut.features.tree [<base>] [--list] [-b] [-e] [--directory=<path>]

prints the aggregates and, under each, its leaves: a leaf by its name and
the directory that defines it, then its title.

    <base>      an aggregate's tree path ('gateway/forwarding'): only what
                stands below it
    --list      one line per leaf, '<tree path>/<external id>' -- a line
                '-F' takes as it stands; an unplaced leaf is its external
                id alone
    -b          the aggregates only, one tree path per line (branches)
    -e          the tree, each leaf with its external id

Retired claims are not printed. Unplaced leaves follow the tree, under
'(unplaced)'.

EXIT STATUS (E-1, services/_exit.py):
    0  OK       printed
    1  FAULT    the central file states what is not read; its faults
    2  REFUSED  no 'hwut-root.conf', no central file, a <base> that is no
                aggregate, or the command line cannot be read
    3  EMPTY    nothing to print
______________________________________________________________________________
"""
import os
import sys

from hwut.engine.orchestrator.exploration.feature_registry \
                                         import (read_registry, CLeaf,
                                                 aggregate_list)
from hwut.engine.orchestrator.exploration.feature_relation \
                                         import read_feature_file, TEST_NAME
from hwut.engine.orchestrator.exploration.finder import REGISTRY_FILE_NAME
from ..._core                            import usage_line
from ..._exit                            import E_ExitCode
from .                                   import _common

NAME  = "hwut.features.tree"
USAGE = usage_line("usage: %s" % NAME,
                   ("[<base>]", "[--list]", "[-b]", "[-e]",
                    "[--directory=<path>]"))
HELP  = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
        + "\n" + USAGE


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).
    """
    try:
        write, directory, rest = _common.opened(NAME, argv, write, HELP)
        root = _common.root_of(directory, write)
    except _common.Refused as refusal:
        return refusal.exit_code
    flag_set  = {each for each in rest if each.startswith("-")}
    base_list = [each for each in rest if not each.startswith("-")]
    unknown   = flag_set - {"--list", "-b", "-e"}
    if unknown or len(base_list) > 1 or {"--list", "-b"} <= flag_set:
        write("REFUSED: '%s' does not take: %s"
              % (NAME, ", ".join(sorted(unknown) + base_list[1:])
                 or "'--list' and '-b' together"))
        write(USAGE)
        return E_ExitCode.REFUSED
    registry = read_registry(root)
    if registry is None:
        write("REFUSED: no '%s' stands => hwut.features.init"
              % REGISTRY_FILE_NAME)
        return E_ExitCode.REFUSED
    if registry.fault_tuple:
        write("FAULT: '%s' states what is not read:" % REGISTRY_FILE_NAME)
        for fault in registry.fault_tuple:
            write("    %s" % fault)
        return E_ExitCode.FAULT

    base = base_list[0].strip("/") if base_list else ""
    top  = _subtree(registry, base)
    if top is None:
        write("REFUSED: no aggregate '%s' => %s -b lists them" % (base, NAME))
        return E_ExitCode.REFUSED
    if "-b" in flag_set:
        line_list = [path for path, _ in aggregate_list(registry)
                     if not base or path == base
                     or path.startswith(base + "/")]
    elif "--list" in flag_set:
        line_list = _list_lines(top, base, registry, not base)
    else:
        title_of = _Titles(root, registry)
        line_list = _tree_lines(top, 0, title_of, "-e" in flag_set)
        if not base:
            unplaced = [each for each in registry.tree_tuple
                        if isinstance(each, CLeaf)]
            if unplaced:
                line_list.append("(unplaced)")
                line_list += [_leaf_line(each, 1, title_of, "-e" in flag_set)
                              for each in unplaced]
    if not line_list:
        return E_ExitCode.EMPTY
    for line in line_list:
        write(line)
    return E_ExitCode.OK


def _subtree(registry, base):
    """
    RETURN: tuple of CAggregate | CLeaf, what stands below the aggregate
            whose tree path is 'base' -- the aggregates of the top where
            'base' is empty (the unplaced leaves left out)
            None, no aggregate has that path
    """
    if not base:
        return tuple(each for each in registry.tree_tuple
                     if not isinstance(each, CLeaf))
    for path, aggregate in aggregate_list(registry):
        if path == base: return (aggregate,)
    return None


def _list_lines(child_tuple, base, registry, unplaced_f):
    """RETURN: list of str, '<tree path>/<external id>' per leaf below
    'child_tuple' (whose parent's path is the parent of 'base'), then the
    unplaced leaves by their external id where 'unplaced_f'."""
    result = []
    parent = base.rpartition("/")[0]

    def walk(children, path):
        for each in children:
            if isinstance(each, CLeaf):
                result.append("%s/%s" % (path, each.external) if path
                              else each.external)
            else:
                walk(each.child_tuple,
                     "%s/%s" % (path, each.key) if path else each.key)

    walk(child_tuple, parent)
    if unplaced_f:
        result += [each.external for each in registry.tree_tuple
                   if isinstance(each, CLeaf)]
    return result


class _Titles:
    """The titles of leaves, read from the TEST directories lazily: a
    directory's feature file is read once, when a leaf of it is printed."""

    def __init__(self, root, registry):
        """RETURN: None."""
        self.root, self.registry, self.cache = root, registry, {}

    def path_of(self, leaf):
        """RETURN: str, the directory path of 'leaf'; '?' where its id has
        no line."""
        directory = self.registry.directory_of_id(leaf.directory_id)
        return directory.path if directory is not None else "?"

    def __call__(self, leaf):
        """RETURN: str, the title of 'leaf'; '' where none is stated or its
        directory defines it not."""
        path = self.path_of(leaf)
        if path not in self.cache:
            file = read_feature_file(os.path.join(self.root, path,
                                                  TEST_NAME)) \
                   if path != "?" else None
            self.cache[path] = {} if file is None else {
                each.name: each.title or "" for each in file.feature_tuple}
        return self.cache[path].get(leaf.name, "")


def _leaf_line(leaf, depth, title_of, external_f):
    """RETURN: str, one leaf of the tree view."""
    return "%s%s  (%s)%s  %s" % (
        "  " * depth, leaf.name, title_of.path_of(leaf),
        "  " + leaf.external if external_f else "", title_of(leaf))


def _tree_lines(child_tuple, depth, title_of, external_f):
    """RETURN: list of str, the tree view of 'child_tuple' at 'depth'."""
    result = []
    for each in child_tuple:
        if isinstance(each, CLeaf):
            result.append(_leaf_line(each, depth, title_of, external_f))
        else:
            result.append("%s%s%s" % ("  " * depth, each.key,
                                      "  " + each.title if each.title
                                      else ""))
            result += _tree_lines(each.child_tuple, depth + 1, title_of,
                                  external_f)
    return result


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded(NAME, main))
