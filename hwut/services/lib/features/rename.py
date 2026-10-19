"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.features.rename' COMMAND LINE -- a feature gets a new
         name and keeps its external id (spec 23 VERSION 10, R-96;
         services E-157).

    hwut.features.rename <external id> <new name> [--directory=<path>]

The feature behind the leaf <external id> is renamed in the three places
that name it: its definition in its TEST directory's 'hwut-features.conf',
every link to it in that directory's test headers ('features = [...]'),
and the leaf's internal id in 'hwut-root-features.conf'. The external id
-- what customers, documents and tickets name -- stays as it was.

A rename by hand in the feature file is no rename: 'hwut.features.register'
then sees a feature gone and one new, and pairs them only where that is
certain.

EXIT STATUS (E-1, services/_exit.py):
    0  OK       renamed
    2  REFUSED  no root, no central file, an id that is no leaf, a new name
                that is no word, stands already or was retired, or an edit
                that would leave a file with a fault
______________________________________________________________________________
"""
import sys

from hwut.engine.orchestrator.exploration.feature_registry_act import rename
from ..._core                            import usage_line
from .                                   import _common

NAME  = "hwut.features.rename"
USAGE = usage_line("usage: %s" % NAME,
                   ("<external id>", "<new name>", "[--directory=<path>]"))
HELP  = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
        + "\n" + USAGE


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).
    """
    return _common.act_main(NAME, HELP, USAGE, argv, write, 2,
                            lambda root, directory, write, external, new:
                            rename(root, external, new))


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded(NAME, main))
