"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.features.key.remove' COMMAND LINE -- a key taken off
         the keys a claim states itself, or off every claim (spec 23
         VERSION 10 section 9, R-96).

    hwut.features.key.remove <id> <key> [--directory=<path>]
    hwut.features.key.remove --all <key> [--directory=<path>]

<id> is a leaf's external id or an aggregate's key; only a key the claim
states ITSELF is taken off -- one it carries from above is taken off where
it is stated. '--all' takes the key off every aggregate, every definition
of a registered feature, and every TEST directory's feature file that
states it for all its features: a category given up. It is spelt out on
purpose -- a mistyped id must not wipe out a category.

EXIT STATUS (E-1, services/_exit.py):
    0  OK       taken off
    2  REFUSED  no root, no central file, an id that is no claim of the
                tree, a key the claim does not state itself, or (with
                '--all') a key no claim states
______________________________________________________________________________
"""
import sys

from hwut.engine.orchestrator.exploration.feature_registry_act \
                                         import key_remove, key_remove_all
from ...._core                           import usage_line
from ...._exit                           import E_ExitCode
from ..                                  import _common

NAME  = "hwut.features.key.remove"
USAGE = usage_line("usage: %s" % NAME,
                   ("<id> <key> | --all <key>", "[--directory=<path>]"))
HELP  = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
        + "\n" + USAGE


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).
    """
    if argv is None: argv = sys.argv[1:]
    if argv and argv[0] == "--all":
        if len([each for each in argv if not each.startswith("--")]) != 1:
            (write or print)("REFUSED: '%s --all' takes one key" % NAME)
            (write or print)(USAGE)
            return E_ExitCode.REFUSED
        return _common.act_main(NAME, HELP, USAGE, argv[1:], write, 1,
                                lambda root, directory, write, key:
                                key_remove_all(root, key))
    return _common.act_main(NAME, HELP, USAGE, argv, write, 2,
                            lambda root, directory, write, name, key:
                            key_remove(root, name, key))


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ...._exit import guarded
    sys.exit(guarded(NAME, main))
