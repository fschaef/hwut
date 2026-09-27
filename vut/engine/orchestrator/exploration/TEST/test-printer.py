#! /usr/bin/env python3
#
# @hwut {
#     title      = "hwut.parse: what the framework read"
#     choices    = ["directory", "faults", "file", "no_default",
#                   "origins", "places", "read_back"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: What 'hwut.parse' shows: the complete configuration as a tree,
         annotated only where a value is not this choice's own word.

CHOICES: file, origins, no_default, places, directory, faults, read_back;

DESCRIPTION:

file       one source file, printed IN THE SPECIFICATION LANGUAGE:
           what is printed can be read back. Every parameter the
           framework will use appears, including those the author never
           wrote, which carry 'default'.

origins    the provenances, in a comment, and only where the value is
           not this choice's own word: 'app' from the application's
           root, 'hwut.conf:<line>' from 'app_defaults' or from an
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

read_back  WHAT IS PRINTED READS BACK AS WRITTEN (X-PRINTED): a scope
           taken from the printed tree and pasted into a configuration
           section states the same values, and the whole tree pasted as
           a header prints the same tree again -- 'same' and
           'interactive' at the root, where they may stand -- backslashes and quotes
           escaped as the author wrote them; a value longer than the
           comment column keeps two blanks before its comment.

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
                            '#     tolerance { numeric_ratio = 0.01 }\n'
                            '#     caps    { timeout_sec = 30 }\n'
                            '#     choices {\n'
                            '#         one { }\n'
                            '#         two { tolerance { numeric_ratio = 0.05 }\n'
                            '#               caps { network = false } }\n'
                            '#     }\n'
                            '# }\n'},
              "test-a.py")


def test_no_default():
    """RETURN: None. With and without the values nobody stated."""
    file_db = {"test-a.py": '# @hwut {\n'
                            '#     title   = "Tolerances"\n'
                            '#     tolerance { numeric_ratio = 0.01 }\n'
                            '#     caps    { timeout_sec = 30 }\n'
                            '#     choices { two { tolerance { numeric_ratio = 0.05 } } }\n'
                            '# }\n',
               "hwut.conf": 'hwut {\n'
                            '    app_defaults { tolerance { comment = ["//", ""] } }\n'
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
                                   '#     tolerance { numeric_ratio = 0.01 }\n'
                                   '#     choices { two { tolerance { numeric_ratio = 0.05 } } }\n'
                                   '# }\n',
                    "hwut.conf":  'hwut {\n'
                                  '    app_defaults { tolerance { whitespace = no } }\n'
                                  '    apps {\n'
                                  '        gen.c { title = "generated"\n'
                                  '                tolerance { comment = ["//", "//"] } }\n'
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
                            '#     tolerance { numeric_ratio = 0.01 }\n'
                            '#     caps    { timeout_sec = 30 }\n'
                            '#     choices { two { tolerance { numeric_ratio = 0.05 } } }\n'
                            '# }\n',
               "hwut.conf": 'hwut {\n'
                            '    app_defaults {\n'
                            '        tolerance { whitespace = no }\n'
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


READ_BACK_HEADER = (
    '# @hwut {\n'
    '#     title = "Read back \\"as written\\""\n'
    '#     tolerance {\n'
    '#         eq_pattern = ["[\\\\\\\\/]+", "id=\\"[a-z]+\\"",\n'
    '#                       "(hello|bonjour|hallo|buongiorno|hola|ciao)"]\n'
    '#         nothing    = ["WARN\\\\s*"]\n'
    '#     }\n'
    '#     choices = ["one"]\n'
    '# }\n')


def _scope_of(text, name):
    """RETURN: list[str], the lines of the first scope 'name { ... }' in
               the printed 'text', braces included, unindented."""
    line_list = text.splitlines()
    i = next(i for i, line in enumerate(line_list)
             if line.strip().startswith(name + " {"))
    indent = len(line_list[i]) - len(line_list[i].lstrip())
    j = next(j for j in range(i + 1, len(line_list))
             if line_list[j] == " " * indent + "}")
    return [line[indent:] for line in line_list[i:j + 1]]


def test_read_back():
    """RETURN: None. The printed tolerance, pasted, reads back the same."""
    from vut.engine.orchestrator.exploration.explorer import explore
    banner("written")
    print(READ_BACK_HEADER, end="")
    directory = build_directory({"test-a.py": READ_BACK_HEADER})
    pasted    = None
    try:
        text, fault_list = hwut_parse.text_of_file(directory, "test-a.py")
        scope = _scope_of(text, "tolerance")
        banner("printed, the scope taken")
        print("\n".join(scope))
        pasted = build_directory({"test-a.py":
                     "# @hwut {\n#     title = \"pasted\"\n"
                     + "".join("#     %s\n" % line for line in scope)
                     + "#     choices = [\"one\"]\n# }\n"})
        first  = explore(directory).app_set.app_db["test-a.py"]
        second = explore(pasted)
        banner("pasted, read back")
        for fault in list(fault_list) + list(second.fault_list):
            print("FAULT %s" % fault)
        second = second.app_set.app_db.get("test-a.py")
        if second is None:
            print("FAIL: the pasted scope does not read back")
            return
        for name in ("eq_pattern", "nothing"):
            print("%-10s %s" % (name, list(getattr(
                                   second.choice_db["one"].tolerance, name))))
        #  JUDGED AS COMPARE WILL USE IT: the pasted scope states the
        #  defaults too, so the records differ in what was STATED while
        #  compare's configuration must not differ at all.
        from vut.engine.orchestrator.run.adapter import _compare_of
        same_f = _compare_of(first.choice_db["one"]).pattern_finder \
                 == _compare_of(second.choice_db["one"]).pattern_finder
        print("%s: the pasted scope configures compare the same"
              % ("SUCCESS" if same_f else "FAIL"))
    finally:
        shutil.rmtree(directory, ignore_errors=True)
        if pasted: shutil.rmtree(pasted, ignore_errors=True)
    _read_back_whole()


WHOLE_HEADER = (
    '# @hwut {\n'
    '#     title = "The whole tree"\n'
    '#     same  = yes\n'
    '#     tolerance { eq_pattern = ["[\\\\\\\\/]+"] }\n'
    '#     choices {\n'
    '#         one { }\n'
    '#         two { caps { timeout_sec = 5 } }\n'
    '#     }\n'
    '# }\n')


def _uncommented(text):
    """RETURN: list[str], the printed lines without their comments."""
    import re
    return [re.sub(r'\s+# [^"]*$', "", line) for line in text.splitlines()]


def _read_back_whole():
    """RETURN: None. The WHOLE printed application, pasted as a header,
    prints the same tree again -- comments aside, which name where a
    value came from (X-PRINTED): 'same' and 'interactive' stand at the
    root, where the validator admits them."""
    banner("the whole tree: printed, pasted, printed again")
    directory = build_directory({"test-a.py": WHOLE_HEADER})
    pasted    = None
    try:
        text, _ = hwut_parse.text_of_file(directory, "test-a.py")
        body    = text.splitlines()[1:-1]
        pasted  = build_directory({"test-a.py":
                      "# @hwut {\n" + "".join("# %s\n" % line[4:]
                                               for line in body) + "# }\n"})
        again, fault_list = hwut_parse.text_of_file(pasted, "test-a.py")
        for fault in fault_list: print("FAULT %s" % fault)
        print("\n".join(_uncommented(text)[:6]))
        same_f = _uncommented(text) == _uncommented(again)
        print("%s: the whole tree reads back as printed"
              % ("SUCCESS" if same_f and not fault_list else "FAIL"))
    finally:
        shutil.rmtree(directory, ignore_errors=True)
        if pasted: shutil.rmtree(pasted, ignore_errors=True)


def test_faults():
    """RETURN: None. A specification that does not parse."""
    show_file("a header with a fault prints no tree",
              {"test-bad.py": '# @hwut {\n'
                              '#     title   = "Bad"\n'
                              '#     tolerance { numeric_ratio = 1.5 }\n'
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
        "read_back":  test_read_back,
    }).run()
