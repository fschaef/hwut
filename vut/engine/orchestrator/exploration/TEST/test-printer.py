#! /usr/bin/env python3
#
# @hwut {
#     title      = "hwut.parse: what the framework read"
#     choices    = ["directory", "faults", "file", "no_default",
#                   "origins", "places"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: What 'hwut.parse' shows: the complete configuration as a tree,
         annotated only where a value is not this choice's own word.

CHOICES: file, origins, no_default, places, directory, faults;

DESCRIPTION:

file       one source file, printed IN THE SPECIFICATION LANGUAGE:
           what is printed can be read back. Every parameter the
           framework will use appears, including those the author never
           wrote, which carry 'default'.

origins    the provenances, in a comment, and only where the value is
           not this choice's own word: 'app' from the application's
           root, 'hwut.conf:<line>' from 'default_app' or from an
           'apps' entry, '--hwut-info' from the interview, 'default'
           from the owning component.

no_default '--no-default' drops every value nobody stated. A scope
           whose every leaf would go is dropped whole; a specification
           in which nothing was stated prints as an empty one.

places     '--provenance' names the place of every stated value in a
           comment -- the file and the line it stands on, the author's
           own file included. '--gnu' puts the place at the LINE'S
           BEGINNING, 'file:line:column:', where an error parser looks
           for it; the places stand in a column padded to the longest.
           EVERY line carries one: a brace, a title or a defaulted
           value takes the place of what ENCLOSES it, so no entry in
           an editor's error list jumps nowhere.

directory  the whole directory: the directory keys, then each
           application, then the cases that cannot be reached.

faults     a file whose specification does not parse prints no tree
           and its faults instead; the service completes.

Machine-chosen paths never enter this output.
______________________________________________________________________________
"""
import os
import sys
import shutil
import tempfile
from config import HwutRunner                                # noqa: F401

from vut.engine.orchestrator.exploration                  import hwut_parse


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def build_directory(file_db):
    """RETURN: str, a fresh directory holding 'file_db'."""
    directory = tempfile.mkdtemp(prefix="vut_parse_")
    for name, content in file_db.items():
        with open(os.path.join(directory, name), "w") as fh:
            fh.write(content)
    return directory


def show_file(label, file_db, name):
    """RETURN: None. Prints one file's tree and its faults."""
    banner(label)
    directory = build_directory(file_db)
    try:
        text, fault_list = hwut_parse.text_of_file(directory, name)
        print(text if text else "no specification")
        for fault in fault_list:
            print("FAULT %s" % fault)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def show_directory(label, file_db, runner=None):
    """RETURN: None. Prints the whole directory and its faults."""
    banner(label)
    directory = build_directory(file_db)
    try:
        text, fault_list = hwut_parse.text_of_directory(
            directory, interview_runner=runner)
        print(text)
        for fault in fault_list:
            print("FAULT %s" % fault)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_file():
    """RETURN: None. One file, every parameter shown."""
    show_file("a file with two choices",
              {"test-a.py": '# @hwut {\n'
                            '#     title   = "Tolerances"\n'
                            '#     numeric = 0.01\n'
                            '#     caps    { timeout_sec = 30 }\n'
                            '#     choices {\n'
                            '#         one { }\n'
                            '#         two { numeric = 0.05\n'
                            '#               caps { network = false } }\n'
                            '#     }\n'
                            '# }\n'},
              "test-a.py")


def test_no_default():
    """RETURN: None. With and without the values nobody stated."""
    file_db = {"test-a.py": '# @hwut {\n'
                            '#     title   = "Tolerances"\n'
                            '#     numeric = 0.01\n'
                            '#     caps    { timeout_sec = 30 }\n'
                            '#     choices { two { numeric = 0.05 } }\n'
                            '# }\n',
               "hwut.conf": 'hwut {\n'
                            '    default_app { comment = ["//", ""] }\n'
                            '}\n'}
    banner("everything")
    directory = build_directory(file_db)
    try:
        text, _ = hwut_parse.text_of_directory(directory)
        print(text)
    finally:
        shutil.rmtree(directory, ignore_errors=True)

    banner("--no-default: what somebody stated")
    directory = build_directory(file_db)
    try:
        text, _ = hwut_parse.text_of_directory(directory,
                                               no_default_f=True)
        print(text)
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def test_origins():
    """RETURN: None. Every annotation the printer uses."""
    show_directory("every provenance in one directory",
                   {"legacy.bas": "REM an hwut 1.0 application\n",
                    "test-own.py": '# @hwut {\n'
                                   '#     title   = "own"\n'
                                   '#     numeric = 0.01\n'
                                   '#     choices { two { numeric = 0.05 } }\n'
                                   '# }\n',
                    "hwut.conf":  'hwut {\n'
                                  '    default_app { slash_eqv = yes }\n'
                                  '    apps {\n'
                                  '        gen.c { title = "generated"\n'
                                  '                comment = ["//", "//"] }\n'
                                  '    }\n'
                                  '}\n',
                    "gen.c":      "int main() { return 0; }\n"},
                   runner=lambda path, caps:
                       "Iron and Blood;\nCHOICES: one;\nSAME;\n"
                       if os.path.basename(path) == "legacy.bas" else None)


def test_places():
    """RETURN: None. The two ways of naming a place."""
    file_db = {"test-a.py": '# @hwut {\n'
                            '#     title   = "Tolerances"\n'
                            '#     numeric = 0.01\n'
                            '#     caps    { timeout_sec = 30 }\n'
                            '#     choices { two { numeric = 0.05 } }\n'
                            '# }\n',
               "hwut.conf": 'hwut {\n'
                            '    default_app {\n'
                            '        slash_eqv = no\n'
                            '        comment   = ["//", "//"]\n'
                            '    }\n'
                            '}\n'}
    for label, keyword_db in (("--provenance", {"provenance_f": True}),
                              ("--gnu",        {"gnu_f":        True})):
        banner(label)
        directory = build_directory(file_db)
        try:
            text, _ = hwut_parse.text_of_directory(
                directory, no_default_f=True, **keyword_db)
            print(text)
        finally:
            shutil.rmtree(directory, ignore_errors=True)


def test_directory():
    """RETURN: None. Directory keys, applications, unreachable cases."""
    show_directory("the whole directory",
                   {"test-a.py": '# @hwut { title = "A"\n'
                                 '#        choices = ["one", "two"] }\n',
                    "test-b.py": '# @hwut { title = "B" }\n',
                    "hwut.conf": 'hwut {\n'
                                 '    on_entry  = "setup.sh"\n'
                                 '    collision = ["test-b.py"]\n'
                                 '    dependency {\n'
                                 '        "test-b.py" = ["test-a.py one"]\n'
                                 '        "test-a.py one" = ["test-b.py"]\n'
                                 '    }\n'
                                 '}\n'})


def test_faults():
    """RETURN: None. A specification that does not parse."""
    show_file("a header with a fault prints no tree",
              {"test-bad.py": '# @hwut {\n'
                              '#     title   = "Bad"\n'
                              '#     numeric = 1.5\n'
                              '#     pype    = unquoted\n'
                              '# }\n'},
              "test-bad.py")


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "hwut.parse: what the framework read;", {
        "file":       test_file,
        "origins":    test_origins,
        "no_default": test_no_default,
        "places":     test_places,
        "directory":  test_directory,
        "faults":     test_faults,
    }).run()
