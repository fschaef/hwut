"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.features.retire' COMMAND LINE -- a claim is no longer
         made (spec 43 section 5; intend/43 T-s).

    hwut.features.retire <id> [--directory=<path>]

The feature's block in 'hwut-feature-doc.dat' takes the heading
'[[<id>:retired]]' -- the claim kept as it was -- and the id leaves every
line of 'hwut-feature-forest.csv'. A retired claim has no verdict, counts
nowhere, and 'f/<id>' refuses it. An id with children is refused: retire
them first, a retired claim has nothing below it.

REVIVAL is by hand: ':retired' struck from the heading, the id entered in
a forest line. A test that still links a retired feature is named by
'hwut.report.features'.

EXIT STATUS (E-1, services/_exit.py):
    0  OK       retired
    2  REFUSED  no root, no forest, an id that stands nowhere or is retired
                already, an id with children or named in the map, or a
                file that states a fault
______________________________________________________________________________
"""
import sys

from hwut.engine.orchestrator.exploration.feature_act import retire
from ..._core                            import usage_line
from .                                   import _common

NAME  = "hwut.features.retire"
USAGE = usage_line("usage: %s" % NAME, ("<id>", "[--directory=<path>]"))
HELP  = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
        + "\n" + USAGE


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).
    """
    return _common.act_main(NAME, HELP, USAGE, argv, write, 1,
                            lambda root, directory, write, name:
                            retire(root, name))


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded(NAME, main))
