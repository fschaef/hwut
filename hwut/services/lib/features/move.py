"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.features.move' COMMAND LINE -- a directory moved, and
         the central file following in the same step (spec 23 VERSION 10
         section 8, R-96).

    hwut.features.move <directory> <new directory> [--directory=<path>]

renames <directory> to <new directory> -- a 'mv' -- and rewrites every
'directory_map' line at or below it to the new place. The ids stay; every
external id of a feature below stays valid. Nothing else changes: the
'tree' does not, and neither do the TEST directories.

A directory moved by hand is found by 'hwut.features.register', which
proposes the same lines ('redirect'); this face does it in one step.

EXIT STATUS (E-1, services/_exit.py):
    0  OK       moved
    2  REFUSED  no root, no central file, the root itself, a directory that
                does not stand, a target that stands already, lies inside
                the directory, or whose parent does not stand
______________________________________________________________________________
"""
import sys

from hwut.engine.orchestrator.exploration.feature_registry_act import move
from ..._core                            import usage_line
from .                                   import _common

NAME  = "hwut.features.move"
USAGE = usage_line("usage: %s" % NAME,
                   ("<directory>", "<new directory>", "[--directory=<path>]"))
HELP  = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
        + "\n" + USAGE


def _act(root, directory, write, old, new):
    """RETURN: list of str, what 'move' did; the two paths taken from
    'directory'."""
    return move(root, _common.path_below(root, directory, old, write),
                _common.path_below(root, directory, new, write))


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).
    """
    return _common.act_main(NAME, HELP, USAGE, argv, write, 2, _act)


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded(NAME, main))
