"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.features.init' COMMAND LINE -- write the central file
         of the features, 'hwut-root-features.conf', beside
         'hwut-root.conf' (spec 23 VERSION 10, R-96).

    hwut.features.init [--directory=<path>]

Every directory whose TEST directory holds a 'hwut-features.conf' gets a
generated directory id; every feature defined there is registered as an
UNPLACED leaf under its first external id -- the directory's path, dotted,
and its name ('gw/router' + 'forward' -> 'gw.router.forward'). The file
opens with comments that say what each section is.

Afterwards: edit the left sides that shall read otherwise BEFORE they are
given out, and move the leaf lines into aggregates of 'tree'.

REFUSED where the central file stands already ('hwut.features.register'
adds to it), and where files of the past stand -- a 'hwut-features.conf'
outside a TEST directory, a 'hwut-feature-map.conf': they are named, and
the tree is migrated first.

EXIT STATUS (E-1, services/_exit.py):
    0  OK       written
    2  REFUSED  no 'hwut-root.conf', the file stands, files of the past
                stand, or the command line cannot be read
______________________________________________________________________________
"""
import os
import sys

from hwut.engine.orchestrator.exploration.feature_detector \
                                         import fact_db_of_tree
from hwut.engine.orchestrator.exploration.feature_registry_edit \
                                         import composed_text, write_atomic
from hwut.engine.orchestrator.exploration.finder import REGISTRY_FILE_NAME
from ..._core                            import usage_line
from ..._exit                            import E_ExitCode
from .                                   import _common

NAME  = "hwut.features.init"
USAGE = usage_line("usage: %s" % NAME, ("[--directory=<path>]",))
HELP  = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
        + "\n" + USAGE


def main(argv=None, write=None, id_list=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).
    'id_list' gives the directory ids in path order (a test).
    """
    try:
        write, directory, rest = _common.opened(NAME, argv, write, HELP)
        if rest:
            write("REFUSED: '%s' does not take: %s"
                  % (NAME, ", ".join(rest)))
            write(USAGE)
            return E_ExitCode.REFUSED
        root = _common.root_of(directory, write)
    except _common.Refused as refusal:
        return refusal.exit_code
    path = _common.registry_path(root)
    if os.path.exists(path):
        write("REFUSED: '%s' stands already => hwut.features.register"
              % REGISTRY_FILE_NAME)
        return E_ExitCode.REFUSED
    fact_db, old_tuple = fact_db_of_tree(root)
    if old_tuple:
        write("REFUSED: files of the past stand; migrate them first:")
        for each in old_tuple:
            write("    %s" % each)
        return E_ExitCode.REFUSED
    write_atomic(path, composed_text(fact_db, id_list))
    path_n    = len(fact_db)
    feature_n = sum(len(fact_db[p]) for p in fact_db)
    write("'%s' written -- %d directory id(s), %d feature(s), unplaced"
          % (REGISTRY_FILE_NAME, path_n, feature_n))
    if feature_n:
        write("=> move the leaf lines into aggregates of 'tree'")
    return E_ExitCode.OK


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded(NAME, main))
