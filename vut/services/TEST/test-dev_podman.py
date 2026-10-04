#! /usr/bin/env python3
#
# @hwut {
#     title      = "hwut.dev.podman.build / enter: the development container"
#     choices    = ["build", "enter", "help", "refused"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE TWO FACES OF THE DEVELOPMENT CONTAINER (adm/DEVELOPMENT.txt,
         services E-134): what they hand the engine, stated verbatim.
         No engine runs here: a stand-in takes the call and answers the
         status the choice decides, so the page is the CALL -- the root
         mounted at its own path, the working directory kept, the user
         kept, the command or the shell -- and not a machine's podman.

CHOICES: build, enter, refused, help;

build     the image stands: nothing is built, said; '--rebuild' and a
          missing image: 'podman build -t hwut-dev -f ... .' at the root;
          a failing build is a FAULT.
enter     no command: 'bash', at the working directory, the root mounted
          read-write at its own path, '--userns=keep-id'; a command, with
          and without '--'; a terminal or none; the image missing names
          the build face; docker's user mapping.
refused   an option neither face takes; no root above the directory.
help      the two texts.
______________________________________________________________________________
"""
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from   vut.services.lib.dev.podman import build as build_module  # noqa E402
from   vut.services.lib.dev.podman import enter as enter_module  # noqa E402
build_main, enter_main = build_module.main, enter_module.main


def check(pair_list):
    """RETURN: True, every claim held; False, at least one did not."""
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def verdict(ok, sentence):
    """RETURN: None. The one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


class Engine:
    """The stand-in: records every call, answers as told."""

    def __init__(self, image_f=True, build_status=0, run_status=0):
        self.image_f, self.build_status, self.run_status = \
            image_f, build_status, run_status
        self.call_list = []

    def __call__(self, argv):
        """RETURN: int, the status of 'argv' as this stand-in decides."""
        self.call_list.append(argv)
        if argv[1:3] == ["image", "inspect"]: return 0 if self.image_f else 1
        if argv[1] == "build":               return self.build_status
        return self.run_status


def fixture():
    """RETURN: (root, a directory below it) -- a tree with the
    Containerfile where the faces look for it."""
    root = tempfile.mkdtemp(prefix="vut_dev_")
    os.makedirs(os.path.join(root, "vut", "adm", "container"))
    with open(os.path.join(root, "vut", "adm", "container", "Containerfile"),
              "w") as fh:
        fh.write("FROM scratch\n")
    below = os.path.join(root, "vut", "services", "TEST")
    os.makedirs(below)
    return root, below


def call(face, argument_list, engine, root, **kw):
    """RETURN: int, the status; the face's lines shown, the root as
    '<root>', the engine's calls as the face printed them."""
    main = {"build": build_main, "enter": enter_main}[face]
    print("$ hwut.dev.podman.%s %s"
          % (face, " ".join(a.replace(root, "<root>") if root else a
                            for a in argument_list)))
    line_list = []
    status = main(argument_list, line_list.append, run=engine, **kw)
    for line in line_list:
        line = re.sub(r"--user=\d+:\d+", "--user=<uid>:<gid>", line)
        print("    %s" % (line.replace(root, "<root>") if root else line))
    print("    [status %d]" % status)
    return status


def _with_engine(name):
    """RETURN: None. The faces' 'engine()' answers 'name' for this test
    -- the machine's own podman or docker is never asked."""
    build_module.engine = lambda: name
    enter_module.engine = lambda: name


def test_build():
    """The build face."""
    root, below = fixture()
    _with_engine("podman")
    here = os.getcwd()
    os.chdir(below)
    try:
        standing = Engine(image_f=True)
        s1 = call("build", [], standing, root)
        asked_n = len(standing.call_list)
        s2 = call("build", ["--rebuild"], standing, root)
        absent = Engine(image_f=False)
        s3 = call("build", [], absent, root)
        failing = Engine(image_f=False, build_status=1)
        s4 = call("build", [], failing, root)
    finally:
        os.chdir(here)
    shutil.rmtree(root)
    ok = check([
        (s1 == 0 and asked_n == 1,
         "an image that stands is not rebuilt unasked"),
        (s2 == 0 and standing.call_list[-1][:5]
         == ["podman", "build", "-t", "hwut-dev", "-f"],
         "'--rebuild' builds it anew, at the root"),
        (s3 == 0 and absent.call_list[-1][1] == "build",
         "an image that does not stand is built"),
        (s4 != 0, "a build that fails is a FAULT"),
    ])
    verdict(ok, "the image, built where none stands.")


def test_enter():
    """The enter face."""
    root, below = fixture()
    _with_engine("podman")
    here = os.getcwd()
    os.chdir(below)
    try:
        e = Engine()
        call("enter", [], e, root, tty_f=True)
        call("enter", ["bin/hwut.run", "--plain"], e, root, tty_f=False)
        call("enter", ["--", "sh", "-c", "cd vut && ls"], e, root, tty_f=False)
        call("enter", ["--directory=%s" % root], e, root, tty_f=True)
        missing = Engine(image_f=False)
        call("enter", [], missing, root, tty_f=True)
        _with_engine("docker")
        d = Engine()
        call("enter", [], d, root, tty_f=False)
    finally:
        os.chdir(here)
    shutil.rmtree(root)
    shell, census, dashed, at_root = e.call_list[1], e.call_list[3], \
                                     e.call_list[5], e.call_list[7]
    ok = check([
        (shell[-1] == "bash" and "-it" in shell and "--userns=keep-id" in shell
         and "%s:%s" % (root, root) in shell and below in shell,
         "no command: an interactive shell, the root at its own path, "
         "the working directory kept, the user kept"),
        (census[-2:] == ["bin/hwut.run", "--plain"] and "-it" not in census,
         "a command runs as given; no terminal, no '-it'"),
        (dashed[-3:] == ["sh", "-c", "cd vut && ls"],
         "'--' passes a command with options of its own"),
        (at_root[at_root.index("-w") + 1] == root,
         "'--directory' is the working directory inside"),
        (len(missing.call_list) == 1,
         "an image that does not stand is named, not built"),
        (any(w.startswith("--user=") for w in d.call_list[1])
         and "--userns=keep-id" not in d.call_list[1],
         "docker keeps the user by '--user'"),
    ])
    verdict(ok, "the host's tree, inside.")


def test_refused():
    """Refusals by name."""
    root, below = fixture()
    _with_engine("podman")
    here = os.getcwd()
    os.chdir(below)
    try:
        call("build", ["--sideways"], Engine(), root)
        call("enter", ["--sideways"], Engine(), root, tty_f=False)
        _with_engine(None)
        call("build", [], Engine(), root)
        call("enter", [], Engine(), root, tty_f=False)
    finally:
        os.chdir(here)
    elsewhere = tempfile.mkdtemp(prefix="vut_dev_nowhere_")
    _with_engine("podman")
    os.chdir(elsewhere)
    try:
        call("build", [], Engine(), elsewhere)
        call("enter", [], Engine(), elsewhere, tty_f=False)
    finally:
        os.chdir(here)
    shutil.rmtree(root); shutil.rmtree(elsewhere)
    verdict(True, "refused by name: the word, the engine, the root.")


def test_help():
    """The two texts."""
    for face in ("build", "enter"):
        call(face, ["--help"], Engine(), "")
    verdict(True, "help on request.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "hwut.dev.podman.build / enter",
        choice_map = {
            "build":   test_build,
            "enter":   test_enter,
            "refused": test_refused,
            "help":    test_help,
        },
        happy      = "SUCCESS.*",
    ).run()
