#! /usr/bin/env python3
#
# @hwut {
#     title   = "The capability board: what the procsitter can watch, announced before a call"
#     choices = ["board", "platform", "unenforced", "utility"]
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE CAPABILITY BOARD ('capability.py') -- cap by cap, whether
         the procsitter can watch it, as a function of what the
         platform provides.

CHOICES: board, platform, unenforced, utility;

DESCRIPTION:

board       the board for each of the four platforms a pair of modules
            makes: 'psutil' and 'resource' present or absent. Stated,
            not probed -- the page says nothing about this machine.

platform    'sys.platform' against the word a configuration names the
            platform by.

utility     'UTILITY_DB': per platform, the utility each cap's watching
            rests on, how it is installed -- and the board of a
            platform that has no 'resource' at all.

unenforced  what a call reports afterwards is what the board announced
            before: 'Procsitter._make_preexec' with 'psutil' taken away.
______________________________________________________________________________
"""
import sys
from config import HwutRunner                                # noqa: F401

from vut.engine.procsitter              import capability
from vut.engine.procsitter              import procsitter as procsitter_module
from vut.engine.procsitter.capability   import (INSTALL_DB, UTILITY_DB,
                                                capability_db,
                                                platform_name, utility_of)
from vut.engine.procsitter.procsitter   import Procsitter, ProcsitterConfig


def test_board():
    for psutil_f in (True, False):
        for resource_f in (True, False):
            print("psutil %s, resource %s"
                  % ("present" if psutil_f   else "absent",
                     "present" if resource_f else "absent"))
            board = capability_db(psutil_f, resource_f)
            for name in sorted(board):
                print("    %-22s %s" % (name,
                                        "watched" if board[name] else "NOT"))


def test_platform():
    saved = sys.platform
    try:
        for name in ("linux", "darwin", "win32", "cygwin", "freebsd13",
                     "sunos5", "aix"):
            capability.sys.platform = name
            print("%-10s -> %s" % (name, platform_name()))
    finally:
        capability.sys.platform = saved


def test_utility():
    for platform in ("linux", "darwin", "windows"):
        print("%s%s" % (platform,
                        "" if platform in UTILITY_DB else "  (the common row)"))
        for name in sorted(capability_db(True, True)):
            utility = utility_of(name, platform)
            if utility is None: continue
            print("    %-18s %-9s %s"
                  % (name, utility,
                     INSTALL_DB.get(utility, "(standard library)")))
    print("windows, psutil present -- 'resource' does not exist there")
    board = capability_db(True, False, "windows")
    for name in sorted(board):
        print("    %-22s %s" % (name, "watched" if board[name] else "NOT"))


def test_unenforced():
    saved = procsitter_module.psutil
    procsitter_module.psutil = None
    try:
        _, unenforced = Procsitter(ProcsitterConfig(), ".")._make_preexec()
    finally:
        procsitter_module.psutil = saved
    board = capability_db(False, procsitter_module.resource is not None)
    #  WHAT 'resource' ADDS IS THE MACHINE'S FACT, and stays off the page.
    print("memory and pid caps reported: %s"
          % ({"max_memory_mb", "max_pids"} <= set(unenforced)))
    print("agrees with the board: %s"
          % all(not board[name] for name in unenforced))


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "The capability board: what the procsitter can watch, "
               "announced before a call;", {
        "board":      test_board,
        "platform":   test_platform,
        "unenforced": test_unenforced,
        "utility":    test_utility,
    }).run()
