"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.report.wallflowers' COMMAND LINE -- print, one per line,
         every file in the tree's test directories that no carrier speaks
         for (X-SILENT): not ignored, not under 'apps', no '@hwut { }'.

    hwut.report.wallflowers [--directory=<path>]

Each path is relative to where the face is called, so the output pipes
into the one face that settles them:

    hwut.config.ignore $(hwut.report.wallflowers)

The tree is EXPLORED, as 'hwut.run' and 'hwut.report' explore it, and
the wallflower lists ('**/TMP/wallflowers.txt') are refreshed on the
way -- this face finds them afresh; it does not read old lists.

EXIT STATUS
    0    wallflowers stand, and were printed
    2    the command line cannot be read, or no root bounds the tree
    3    no wallflower stands below the directory
______________________________________________________________________________
"""
import os
import sys

from   vut.services._exit                        import E_ExitCode
from   vut.services.lib.wallflowers              import wallflowers_writer
from   vut.engine.orchestrator.exploration.tree_explorer \
                                                 import (explore_tree_stream,
                                                         RootConfMissing)

USAGE = "usage: hwut.report.wallflowers [--directory=<path>] [--help]"


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode -- OK where wallflowers stand (printed), EMPTY
            where none does, REFUSED where the command line cannot be
            read or no root bounds the tree.
    """
    if write is None: write = print
    if argv  is None: argv  = sys.argv[1:]
    directory = "."
    for word in argv:
        if word == "--help":
            write(__doc__.split("PURPOSE:", 1)[1].rsplit("_" * 10, 1)[0]
                  .rstrip())
            return E_ExitCode.OK
        elif word.startswith("--directory="):
            directory = word[len("--directory="):]
        else:
            write("REFUSED: 'hwut.report.wallflowers' does not take '%s'"
                  % word)
            write(USAGE)
            return E_ExitCode.REFUSED
    if not os.path.isdir(directory):
        write("REFUSED: the directory '%s' does not exist" % directory)
        write(USAGE)
        return E_ExitCode.REFUSED

    root = os.path.abspath(directory)
    directory_db = {}
    try:
        for relative, result in explore_tree_stream(root):
            directory_db[os.path.relpath(os.path.join(root, relative))] = \
                sorted(result.app_set.silent_tuple)
    except RootConfMissing as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    wallflowers_writer(lambda line: print(line, file=sys.stderr))(
        directory_db)
    path_list = sorted(os.path.normpath(os.path.join(where, name))
                       for where, name_list in directory_db.items()
                       for name in name_list)
    for path in path_list: write(path)
    return E_ExitCode.OK if path_list else E_ExitCode.EMPTY


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from   vut.services._exit import guarded
    sys.exit(guarded("hwut.report.wallflowers", main, sys.argv[1:]))
