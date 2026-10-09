#! /usr/bin/env python3
#
# @hwut {
#     title      = "The keyed merge screen AS DRAWN: 'hwut.accept.interactive' in a terminal."
#     choices    = ["asking", "open", "quit"]
#     tolerance { comment = []  analogy = [] }
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE SCREEN A PERSON SEES (audit r10, r-11d), not what the driver
         decided: 'hwut.accept.interactive' is started by its launcher in
         a terminal ('test_writing_support/python/hwut_vterm.py',
         libvterm), on a tree whose one test changed after it was
         accepted. The face cannot tell this terminal from a person's.

         WANTS 'libvterm'. Where it is not found, one line says so.

    open     the first screen: OUTPUT left, GOOD right, the foot's keys;
             and that the pane the keys drive wears its title in bold
    asking   the question at the foot (services E-89, AMENDED r-11c): 'q'
             asks and 'n' drops it; 's' asks and 'y' saves and leaves.
             ONLY THE FOOT IS OBSERVED, and only its changes are told.
             Then the report, the exit status and the GOOD that stands
    quit     'Q' leaves unasked: the foot never asks, nothing is written
______________________________________________________________________________
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
VUT  = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
sys.path.insert(0, os.path.dirname(VUT))

from vut.test_writing_support.python.hwut_vterm import (Terminal,   # noqa: E402
                                                        LibraryMissing)

ROW_N, COLUMN_N = 12, 100


def tree():
    """RETURN: str, a test directory of a fresh tree: 'test-a.sh' was
               accepted printing 'one, two' and prints 'one, TWO, three'
               since -- run, so the difference is on record."""
    root = tempfile.mkdtemp(prefix="hwut-screen-")
    directory = os.path.join(root, "TEST")
    os.mkdir(directory)
    with open(os.path.join(root, "hwut-root.conf"), "w") as fh:
        fh.write('hwut {\n    language-setup { bash { extensions = [".sh"] '
                 'interpreter = "bash" } }\n}\n')
    def page(body):
        path = os.path.join(directory, "test-a.sh")
        with open(path, "w") as fh:
            fh.write('#! /bin/bash\n# @hwut {\n#     title = "a"\n# }\n'
                     '%s\necho "<hwut-end>"\n' % body)
        os.chmod(path, 0o755)
    def face(name, *argument_tuple):
        subprocess.run([os.path.join(VUT, "bin", name)] + list(argument_tuple),
                       cwd=directory, stdin=subprocess.DEVNULL,
                       capture_output=True, env=ENVIRONMENT)
    page("echo one; echo two")
    face("hwut.accept", "--whole")
    page("echo one; echo TWO; echo three")
    face("hwut.run", "--silent")
    return directory


ENVIRONMENT = dict(os.environ, PYTHONPATH=os.path.dirname(VUT),
                   HOME=tempfile.mkdtemp(prefix="hwut-home-"))
ENVIRONMENT.pop("NO_COLOR", None)


def session(key_list, observe=None):
    """RETURN: None. The face run in a terminal on a fresh tree, 'observe'
               called with the terminal before it starts, the keys typed
               one by one; then how it ended and what GOOD holds."""
    directory = tree()
    try:
        with Terminal(ROW_N, COLUMN_N, settle_s=0.3) as terminal:
            if observe is not None: observe(terminal)
            terminal.run([os.path.join(VUT, "bin", "hwut.accept.interactive"),
                          "--all"], cwd=directory, env=ENVIRONMENT,
                         start_s=30)
            terminal.expect("OUTPUT of", 30)
            if observe is None: shown(terminal)
            for key in key_list:
                print("-- key %r" % key)
                terminal.send(key)
            status = terminal.wait(30)
            print("-- the face left: exit status %s" % status)
            for line in terminal.line_list():
                if line.strip() and "===" not in line and "---" not in line:
                    print("    | %s" % line.rstrip())
        with open(os.path.join(directory, "GOOD", "test-a.sh.txt")) as fh:
            print("-- GOOD: %s" % fh.read().split())
    finally:
        shutil.rmtree(os.path.dirname(directory), ignore_errors=True)


def shown(terminal):
    """RETURN: None. The rows that hold something, then the titles'
               weight."""
    for row, line in enumerate(terminal.line_list()):
        if line.strip(): print("    %2d |%s" % (row, line))
    title = terminal.line(0)
    for word in ("OUTPUT", "GOOD"):
        cell = terminal.cell(0, title.index(word))
        print("    title %-6s %s" % (word, "bold" if cell.bold_f else "plain"))


def foot_told(terminal):
    """RETURN: None. The last row is observed; each change is printed."""
    terminal.region("foot", row=-1)
    terminal.on_change(lambda name, line_list:
                       print("    foot: %s" % (line_list[0].strip() or "(blank)")))


CHOICE_DB = {
    "open":   lambda: session(["Q"]),
    "asking": lambda: session(["q", "n", "A", "s", "y"], foot_told),
    "quit":   lambda: session(["A", "Q"], foot_told),
}

if __name__ == "__main__":
    if "--hwut-info" in sys.argv:
        print("The keyed merge screen AS DRAWN.;")
        print("CHOICES: %s;" % ", ".join(sorted(CHOICE_DB)))
        sys.exit(0)
    try:
        CHOICE_DB[sys.argv[1]]()
    except LibraryMissing as error:
        print("NOT PROBED: %s" % error)
    finally:
        shutil.rmtree(ENVIRONMENT["HOME"], ignore_errors=True)
    print("<hwut-end>")
