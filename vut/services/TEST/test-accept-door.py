#! /usr/bin/env python3
#
# @hwut {
#     title      = "'hwut.accept' at a terminal: the merge door (E-88)"
#     choices    = ["cancel", "done", "realign", "unbuilt"]
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

WHERE A NOMINAL STANDS AND THE CANDIDATE DIFFERS, 'hwut.accept' at a
terminal hands the key to the shared merge engine. MEASURED (E-88): the
call passed 'write' where the adapter belongs -- every merge through the
door died in a TypeError, and no suite reached the door.

The terminal is stood in for: the face's 'adapter_for' returns the keyed
display with its keys scripted, and the face is told it sits at a
terminal. Everything else is the real face on a real tree.

    done     'A' takes the whole subject, 'q' is done: GOOD is written,
             the report says 'blessed' (E-89: no separate commit)
    cancel   'A', then Ctrl-C: NOTHING is written, and the report says
             the screen was left -- not that there was none
    realign  a take, 'g' (realign), then 'q': a SECOND round of the
             session -- MEASURED (E-90) to die in 'hwut.accept' comparing
             the round against a bound it never stated
    unbuilt  no session can be built at all: 'merge required', and the
             way out, as before
______________________________________________________________________________
"""
import io
import os
import sys
import shutil
import tempfile
import subprocess
import contextlib

from   config import HwutRunner                                  # noqa F401,E402
from   vut.services import accept                                # noqa: E402
from   vut.services.lib.accept import engine                     # noqa: E402
from   vut.services.lib.viewers.keyed.driver import KeyedDisplay  # noqa: E402
from   vut.services.lib.viewers.keyed.act import E_Act           # noqa: E402

os.environ["HOME"] = tempfile.mkdtemp(prefix="hwut-home-")


def tree():
    """RETURN: str, a tree whose one test has a nominal ('value old')
               and a differing candidate ('value new')."""
    root = tempfile.mkdtemp(prefix="hwut-door-")
    directory = os.path.join(root, "suite", "TEST")
    os.makedirs(directory)
    with open(os.path.join(root, "hwut-root.conf"), "w") as fh:
        fh.write("hwut {\n}\n")
    app = os.path.join(directory, "test-v.sh")
    def write_app(word):
        with open(app, "w") as fh:
            fh.write('#!/bin/bash\n# @hwut { title = "V" }\n'
                     'echo "value %s"\necho "<hwut-end>"\n' % word)
        os.chmod(app, 0o755)
    face = lambda *a: subprocess.run([sys.executable, "-m"] + list(a),
                                     cwd=root, capture_output=True, text=True)
    write_app("old")
    face("vut.services.run", "--directory=suite", "--silent")
    face("vut.services.accept", "--directory=suite/TEST", "--force")
    write_app("new")
    face("vut.services.run", "--directory=suite", "--silent")
    return root


class _Tty:
    """A stream that answers 'isatty' with True, and is the stream it
    wraps in every other respect."""
    def __init__(self, stream): self._stream = stream
    def isatty(self):           return True
    def __getattr__(self, name): return getattr(self._stream, name)


def door(act_list):
    """RETURN: None. 'hwut.accept' on the tree, at a stood-in terminal
               answering with 'act_list' (None: no session can be built)."""
    root  = tree()
    good  = os.path.join(root, "suite", "TEST", "GOOD", "test-v.sh.txt")
    print("  GOOD before : %s" % open(good).read().splitlines()[0])
    real_adapter_for = engine.adapter_for
    real_stdin, real_stderr = sys.stdin, sys.stderr
    def scripted(**_):
        if act_list is None: raise RuntimeError("no terminal to stand in for")
        return KeyedDisplay(act_script=list(act_list), color_f=False)
    engine.adapter_for = scripted
    line_list = []
    here = os.getcwd()
    try:
        os.chdir(root)
        sys.stdin, sys.stderr = _Tty(real_stdin), _Tty(real_stderr)
        code = accept.main(["--directory=suite/TEST"],
                           write=line_list.append, read_line=lambda: "")
    finally:
        os.chdir(here)
        engine.adapter_for = real_adapter_for
        sys.stdin, sys.stderr = real_stdin, real_stderr
    print("  exit        : %s" % code.name)
    print("  GOOD after  : %s" % open(good).read().splitlines()[0])
    for line in line_list:
        if line.startswith(("    ", "The screen", "'<enter>'", "A nominal")):
            print("  | %s" % line)
    shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    try:
        HwutRunner(
            argv       = sys.argv,
            title      = "'hwut.accept' at a terminal: the merge door (E-88)",
            choice_map = {
                "done":    lambda: door([E_Act.TAKE_ALL, E_Act.DONE]),
                "cancel":  lambda: door([E_Act.TAKE_ALL, E_Act.CANCEL]),
                "realign": lambda: door([E_Act.TAKE_ALL, E_Act.REALIGN,
                                         E_Act.DONE]),
                "unbuilt": lambda: door(None),
            }).run()
    finally:
        shutil.rmtree(os.environ["HOME"], ignore_errors=True)
