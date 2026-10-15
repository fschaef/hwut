"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.features.register' COMMAND LINE -- add what is new to
         the central file, below a directory, and name every disagreement
         (spec 23 VERSION 10 sections 7, 8; R-96).

    hwut.features.register [<directory>] [--directory=<path>]

Below <directory> -- the directory it is called in where none is named --
every directory whose TEST directory defines features and has no id gets
one, and every feature not yet registered becomes an UNPLACED leaf under
its first external id. Each line added is printed: read them -- a familiar
name registered afresh is a line that went missing.

What disagrees is NAMED, with what would heal it, and not acted on: a
directory that stands no more, one that moved ('redirect'), a feature
renamed ('repoint'), a twin ('fold'), a name that was retired and is
defined again. Pairings are proposed only where they are certain; else
'unpaired' lists the candidates. Nothing is ever retired here: that is
'hwut.features.retire'.

Run it after each structural step: a move, a rename, a regrouping.

EXIT STATUS (E-1, services/_exit.py):
    0  OK       everything below the directory is registered and agrees
    1  FAULT    disagreements are named; or the central file states a
                fault, and nothing was written
    2  REFUSED  no 'hwut-root.conf', no central file ('hwut.features.init'),
                or the command line cannot be read
______________________________________________________________________________
"""
import os
import sys

from hwut.engine.orchestrator.exploration.feature_detector \
                                         import UNPLACED
from hwut.engine.orchestrator.exploration.feature_registry_act \
                                         import (register, ActRefused,
                                                 ActFault)
from hwut.engine.orchestrator.exploration.finder import REGISTRY_FILE_NAME
from ..._core                            import usage_line
from ..._exit                            import E_ExitCode
from .                                   import _common

NAME  = "hwut.features.register"
USAGE = usage_line("usage: %s" % NAME,
                   ("[<directory>]", "[--directory=<path>]"))
HELP  = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
        + "\n" + USAGE


def main(argv=None, write=None, token=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).
    'token' stands in for the random source of directory ids (a test).
    """
    try:
        write, directory, rest = _common.opened(NAME, argv, write, HELP)
        option_list = [each for each in rest if each.startswith("-")]
        if option_list or len(rest) > 1:
            write("REFUSED: '%s' %s: %s"
                  % (NAME, "does not take" if option_list
                     else "takes one directory at most",
                     ", ".join(option_list or rest)))
            write(USAGE)
            return E_ExitCode.REFUSED
        root  = _common.root_of(directory, write)
        below = _common.below_of(root, directory, rest[0] if rest else None,
                                 write)
    except _common.Refused as refusal:
        return refusal.exit_code
    try:
        directory_list, leaf_list, found = register(root, below, token)
    except ActFault as error:
        write("FAULT: '%s' states what is not read; nothing written:"
              % REGISTRY_FILE_NAME)
        for fault in error.fault_list:
            write("    %s" % fault)
        return E_ExitCode.FAULT
    except ActRefused as error:
        #  An edit that would leave a fault is the file's matter: FAULT.
        #  No central file is the caller's: REFUSED.
        if os.path.exists(_common.registry_path(root)):
            write("FAULT: %s" % error)
            return E_ExitCode.FAULT
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    for directory_id, directory_path in directory_list:
        write("registered  %s  %s" % (directory_path, directory_id))
    for external, internal in leaf_list:
        write("registered  %s = %s" % (external, internal))

    left = [each for each in found if not each.hint_f]
    hint = [each for each in found if each.hint_f and each.kind != UNPLACED]
    unplaced_n = len([each for each in found if each.kind == UNPLACED])
    if left:
        write("NOT AS IT SHOULD STAND -- read, then heal by hand or by the "
              "lines after '=>':")
        for line in _common.finding_lines(left):
            write(line)
    if hint or unplaced_n:
        write("HINTS")
        for line in _common.finding_lines(hint):
            write(line)
        if unplaced_n:
            #  ONE LINE, NOT ONE PER LEAF: after 'init' every leaf is
            #  unplaced, and a page of them would bury what disagrees.
            write("    %d leaf(s) in no aggregate => %s"
                  % (unplaced_n, "hwut.features.tree"))
    if not (left or directory_list or leaf_list):
        write("nothing to register below '%s'" % below)
    return E_ExitCode.FAULT if left else E_ExitCode.OK


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded(NAME, main))
