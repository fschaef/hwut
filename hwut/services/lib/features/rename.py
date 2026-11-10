"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.features.rename' COMMAND LINE -- a feature id changes,
         and every reference follows IN ONE STEP (spec 43 section 5, t-4).

    hwut.features.rename <old id> <new id> [--directory=<path>]

The id is written anew on both sides of every line of
'hwut-feature-forest.csv', in the headings of 'hwut-feature-doc.dat', in
the left column of 'hwut-feature-external-map.csv', and in every
'features = [...]' of the test headers and the confs below the top. The
outside's names are untouched: that is what the map is for (T-e).

EXIT STATUS (E-1, services/_exit.py):
    0  OK       renamed
    2  REFUSED  no root, no forest, an old id that stands nowhere, a new
                one that is no id or stands already, or a file that states
                a fault
______________________________________________________________________________
"""
import sys

from hwut.engine.orchestrator.exploration.feature_act import rename
from ..._core                            import usage_line
from .                                   import _common

NAME  = "hwut.features.rename"
USAGE = usage_line("usage: %s" % NAME,
                   ("<old id>", "<new id>", "[--directory=<path>]"))
HELP  = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
        + "\n" + USAGE


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).
    """
    return _common.act_main(NAME, HELP, USAGE, argv, write, 2,
                            lambda root, directory, write, old, new:
                            rename(root, old, new))


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded(NAME, main))
