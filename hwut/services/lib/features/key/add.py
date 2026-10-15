"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.features.key.add' COMMAND LINE -- a key added to the
         keys a claim states itself (spec 23 VERSION 10 section 9, R-96).

    hwut.features.key.add <id> <key> [--directory=<path>]

<id> is a leaf's external id -- the key goes into the definition in its
TEST directory's 'hwut-features.conf' -- or an aggregate's key -- the key
goes into the aggregate in 'hwut-root-features.conf', and travels down to
every claim below it. Written by text surgery: everything else in the file
stays as it was.

EXIT STATUS (E-1, services/_exit.py):
    0  OK       added
    2  REFUSED  no root, no central file, an id that is no claim of the
                tree, a key that is no key, or one the claim states already
______________________________________________________________________________
"""
import sys

from hwut.engine.orchestrator.exploration.feature_registry_act import key_add
from ...._core                           import usage_line
from ..                                  import _common

NAME  = "hwut.features.key.add"
USAGE = usage_line("usage: %s" % NAME,
                   ("<id>", "<key>", "[--directory=<path>]"))
HELP  = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
        + "\n" + USAGE


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).
    """
    return _common.act_main(NAME, HELP, USAGE, argv, write, 2,
                            lambda root, directory, write, name, key:
                            key_add(root, name, key))


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ...._exit import guarded
    sys.exit(guarded(NAME, main))
