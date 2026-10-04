"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.dev.podman.build' -- the development container's image,
         built from 'vut/adm/container/Containerfile'.

    hwut.dev.podman.build [--rebuild] [--directory=<path>]
                                builds the image 'hwut-dev' where none
                                stands; '--rebuild' builds it anew (after
                                an edit of the Containerfile). The build
                                runs at the tree's root -- the directory
                                holding 'vut/', found by ascending from
                                the working directory or '--directory'.
    hwut.dev.podman.build --help
                                this text

The engine is 'podman', or 'docker' where podman does not stand; neither
is a FAULT by name. The engine's call is printed before it runs, and its
exit status is the face's (E-1).
______________________________________________________________________________
"""
import os
import subprocess
import sys

from   vut.services._exit import E_ExitCode
from   vut.services.lib.dev.podman._common import (CONTAINERFILE, IMAGE,
                                                   engine, hand_over,
                                                   root_of)

NAME  = "hwut.dev.podman.build"
USAGE = "usage: %s [--rebuild] [--directory=<path>] | --help" % NAME
HELP  = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip()


def image_stands(tool, run=None):
    """RETURN: True, the image 'hwut-dev' stands in the engine's store."""
    argv = [tool, "image", "inspect", IMAGE]
    if run is not None: return run(argv) == 0
    return subprocess.run(argv, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0


def main(argv=None, write=None, run=None):
    """
    RETURN: E_ExitCode (E-1): OK where the image stands (built now, or
            already), FAULT where no engine or no root stands or the
            build failed, REFUSED where the command line cannot be read.

    'write' takes one line of text; 'run' replaces the engine for a
    test (takes argv, answers the status).
    """
    if write is None: write = print
    if argv is None:  argv = sys.argv[1:]
    if "--help" in argv or "-h" in argv:
        write(HELP)
        return E_ExitCode.OK
    rebuild_f, directory = False, None
    for word in argv:
        if word == "--rebuild":                  rebuild_f = True
        elif word.startswith("--directory="):    directory = word[12:]
        else:
            write("REFUSED: %s does not take: %s" % (NAME, word))
            write(USAGE)
            return E_ExitCode.REFUSED
    tool = engine()
    if tool is None:
        write("FAULT: neither 'podman' nor 'docker' stands on this machine")
        return E_ExitCode.FAULT
    root = root_of(directory)
    if root is None:
        write("FAULT: no directory holding 'vut/%s' above '%s'"
              % (CONTAINERFILE[4:], os.path.abspath(directory or os.getcwd())))
        return E_ExitCode.FAULT
    if not rebuild_f and image_stands(tool, run):
        write("image '%s' stands; '--rebuild' builds it anew" % IMAGE)
        return E_ExitCode.OK
    os.chdir(root)
    status = hand_over([tool, "build", "-t", IMAGE, "-f", CONTAINERFILE, "."],
                       write, run or _run)
    return E_ExitCode.OK if status == 0 else E_ExitCode.FAULT


def _run(argv):
    """RETURN: int, the engine's status, its output passing through."""
    return subprocess.run(argv).returncode


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from vut.services._exit import guarded
    sys.exit(guarded(NAME, main, sys.argv[1:]))
