#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.show' FACE -- the configuration the framework read.

The face is driven through 'main(argv, write)', so what is shown is the
face itself and no process stands between. The directory is stated with
'--directory='; its path is machine-chosen and never printed.

CHOICES: file, directory, faults, refused, help;

DESCRIPTION:

file       one file's specification, resolved; and the same with
           '--no-default', leaving what somebody chose.

directory  the whole directory: 'hwut.conf' first, then every test
           application.

faults     a broken header: its faults print, its tree does not; the
           status is 1.

refused    an unknown option; two source files: refused at the door,
           with the usage line.

help       '--help' answers the full documentation and status 0.
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile
from config import HwutRunner                                # noqa: F401

from vut.engine.orchestrator.services.show import main


FILE_DB = {
    "hwut.conf": 'hwut {\n'
                 '    dependency { "test-b.py" = ["test-a.py one"] }\n'
                 '}\n',
    "test-a.py": '# hwut { title = "A"  numeric = 0.01\n'
                 '#        choices = ["one", "two"] }\n',
    "test-b.py": '# hwut { title = "B" }\n',
}


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def build_directory(extra_db=None):
    """
    RETURN: str, a directory holding FILE_DB and whatever 'extra_db'
            adds, for the caller to remove.
    """
    directory = tempfile.mkdtemp(prefix="vut_show_")
    for name, content in dict(FILE_DB, **(extra_db or {})).items():
        with open(os.path.join(directory, name), "w") as fh:
            fh.write(content)
    return directory


def call(directory, argument_list):
    """
    RETURN: None. Shows the command line as an author writes it, the
            lines the face writes, and the exit status.
    """
    print("$ hwut.show %s" % " ".join(argument_list))
    line_list = []
    status    = main(argument_list + ["--directory=%s" % directory],
                     line_list.append)
    for line in line_list:
        for piece in str(line).split("\n"):
            print("    %s" % piece if piece else "")
    print("    [status %d]" % status)


def test_file():
    """RETURN: None. One file, resolved; then stated values alone."""
    directory = build_directory()
    try:
        banner("resolved")
        call(directory, ["test-a.py"])
        banner("--no-default: what somebody chose")
        call(directory, ["test-a.py", "--no-default"])
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_directory():
    """RETURN: None. The whole directory, stated values alone."""
    directory = build_directory()
    try:
        banner("the directory, --no-default")
        call(directory, ["--no-default"])
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_faults():
    """RETURN: None. A broken header yields faults, no tree."""
    directory = build_directory(
        {"test-broken.py": '# hwut { title = "Broken"  numeric = yes }\n'})
    try:
        banner("the broken file alone")
        call(directory, ["test-broken.py"])
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_refused():
    """RETURN: None. What the command line cannot mean."""
    directory = build_directory()
    try:
        banner("an unknown option")
        call(directory, ["--verbose"])
        banner("two source files")
        call(directory, ["test-a.py", "test-b.py"])
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_help():
    """RETURN: None. The documentation, on demand."""
    directory = build_directory()
    try:
        banner("--help")
        call(directory, ["--help"])
    finally:
        shutil.rmtree(directory, ignore_errors=True)


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "hwut.show: the configuration the framework read;", {
        "file":      test_file,
        "directory": test_directory,
        "faults":    test_faults,
        "refused":   test_refused,
        "help":      test_help,
    }).run()
