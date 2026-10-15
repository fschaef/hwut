"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.features.retire' COMMAND LINE -- a claim is no longer
         made (spec 23 VERSION 10 section 3, R-96).

    hwut.features.retire <id> [--directory=<path>]

<id> is a leaf's external id or an aggregate's key. The claim moves into
the section 'retired' of 'hwut-root-features.conf' AS IT WAS: a leaf with
its internal id and the definition its TEST directory stated (taken out
of that TEST directory's 'hwut-features.conf'); an aggregate with every
claim below it. A retired id is never given again; it has no verdict and
counts nowhere.

REVIVAL is by hand: the block back into 'tree', the definition back into
its TEST directory. A test that still links a retired feature is named by
'hwut.report.features'.

Only this face retires. 'hwut.features.register' and the sanitizer report
what has disappeared; they never retire it.

EXIT STATUS (E-1, services/_exit.py):
    0  OK       retired
    2  REFUSED  no root, no central file, an id that is no claim of the
                tree, or an edit that would leave a file with a fault
______________________________________________________________________________
"""
import sys

from hwut.engine.orchestrator.exploration.feature_registry_act import retire
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
