"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.features.init' COMMAND LINE -- begin the features of a
         tree: an empty 'hwut-feature-forest.csv' and an empty
         'hwut-feature-doc.dat' beside 'hwut-root.conf' (spec 43 section 5).

    hwut.features.init [--directory=<path>]

Each file is written where none stands, and nothing else: there is no id
to generate -- the author picks the word (T-i). The files open with
comments that say how they are written. The map to external names is not
written: it starts absent (T-r).

EXIT STATUS (E-1, services/_exit.py):
    0  OK       written
    2  REFUSED  no 'hwut-root.conf', both files stand already, or the
                command line cannot be read
______________________________________________________________________________
"""
import sys

from hwut.engine.orchestrator.exploration.feature_act import init
from ..._core                            import usage_line
from .                                   import _common

NAME  = "hwut.features.init"
USAGE = usage_line("usage: %s" % NAME, ("[--directory=<path>]",))
HELP  = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
        + "\n" + USAGE


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).
    """
    return _common.act_main(NAME, HELP, USAGE, argv, write, 0,
                            lambda root, directory, write: init(root),
                            nearest_f=True)


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded(NAME, main))
