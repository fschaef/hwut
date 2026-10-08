#! /usr/bin/env python3
#
# @hwut {
#     title   = "Confinement: an unenforceable cap refuses the case, unless acknowledged"
#     choices = ["acknowledged", "gate", "reason", "required"]
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE CONFINEMENT GATE ('plan/confinement.py', exploration R-48,
         R-80) -- the caps a case requires against a capability board.
         Board and platform are STATED on this page; nothing is read
         from the machine it runs on.

CHOICES: required, reason, acknowledged, gate;

DESCRIPTION:

required      what is in force for a case: the caps carrying a default,
              always; an unfielded cap only where it is stated to
              confine; the choice's word over the application's.

reason        the refusal line for one cap and for several; with the
              utility whose absence is the cause, and its install,
              where the procsitter's 'UTILITY_DB' names one.

acknowledged  a board that watches nothing, and what remains refused
              as the acknowledgement grows.

gate          'admit_of' over an explored directory: per case, None or
              the reason; the acknowledgement of ANOTHER platform lifts
              nothing.
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile
from config import HwutRunner                                # noqa: F401

from vut.engine.orchestrator.exploration.configuration_tree import Caps
from vut.engine.orchestrator.exploration.explorer           import explore
from vut.engine.orchestrator.exploration.tree_explorer      import \
                                                            ascended_spec
from vut.engine.orchestrator.plan.confinement import (admit_of, reason_of,
                                                      required_tuple,
                                                      uncapped_tuple)
from vut.engine.procsitter.api                import capability_db

FULL_BOARD = capability_db(True, True)      # all but the three unfielded
BARE_BOARD = capability_db(False, False)


def test_required():
    def show(label, *caps_tuple):
        print("%s" % label)
        for name in required_tuple(*caps_tuple):
            print("    %s" % name)
    show("nothing stated")
    show("network = true", Caps(network=True))
    show("network = false", Caps(network=False))
    show("application: network = false; choice: network = true",
         Caps(network=False), Caps(network=True))
    show("application: nothing; choice: file_handle_max_n = 8",
         None, Caps(file_handle_max_n=8))
    show("write_directory_list = []", Caps(write_directory_list=()))


def test_reason():
    for uncapped, platform in ((("network",), "linux"),
                               (("child_process_max_n", "memory_mb"),
                                "linux"),
                               (("memory_mb", "network"), "windows"),
                               (("cpu_sec", "file_size_mb"), "linux"),
                               (("cpu_sec",), "windows")):
        head, _, remedy = reason_of(uncapped, platform).partition(" => ")
        print(head)
        print("    => %s" % remedy)


def test_acknowledged():
    required = required_tuple(Caps(network=False))
    for acknowledged in ((), ("network",),
                         ("network", "memory_mb", "child_process_max_n"),
                         ("network", "memory_mb", "child_process_max_n",
                          "cpu_sec", "file_size_mb")):
        print("acknowledged: %s" % (", ".join(acknowledged) or "(nothing)"))
        for name in uncapped_tuple(required, acknowledged, BARE_BOARD) \
                    or ("(runs)",):
            print("    %s" % name)


def _page(directory, name, body):
    with open(os.path.join(directory, name), "w") as handle:
        handle.write("#! /bin/sh\n# @hwut {\n#     title = \"%s\"\n%s# }\n"
                     % (name, body))


def test_gate():
    root = tempfile.mkdtemp()
    try:
        directory = os.path.join(root, "TEST")
        os.mkdir(directory)
        _page(directory, "test-free.sh", "")
        _page(directory, "test-net.sh",
              "#     choices = [\"a\", \"b\"]\n"
              "#     caps { network = false }\n")
        _page(directory, "test-one.sh",
              "#     choices {\n"
              "#         open {}\n"
              "#         shut { caps { network = false } }\n"
              "#     }\n")
        for label, conf in (
            ("no acknowledgement", ""),
            ("acknowledged for 'linux'",
             "    procsitter { linux { network = false } }\n"),
            ("acknowledged for 'windows' only",
             "    procsitter { windows { network = false } }\n")):
            with open(os.path.join(root, "hwut-root.conf"), "w") as handle:
                handle.write("hwut {\n%s}\n" % conf)
            inherited, fault_list = ascended_spec(directory)
            result = explore(directory, inherited=inherited)
            admit  = admit_of(result.app_set, FULL_BOARD, "linux")
            print("%s" % label)
            for fault in list(fault_list) + list(result.fault_list):
                print("    FAULT %s" % fault)
            for test in sorted(result.app_set.app_db):
                for choice in result.app_set.app_db[test].choice_db:
                    print("    %-13s %-5s %s"
                          % (test, choice or "-",
                             admit(test, choice) or "admitted"))
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "Confinement: an unenforceable cap refuses the case, "
               "unless acknowledged;", {
        "required":     test_required,
        "reason":       test_reason,
        "acknowledged": test_acknowledged,
        "gate":         test_gate,
    }).run()
