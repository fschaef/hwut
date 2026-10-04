"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.dev.podman.enter' -- a shell, or one command, inside the
         development container, over the tree ON THE HOST'S DISK.

    hwut.dev.podman.enter [--directory=<path>] [-- <command>...]
                                enters the container 'hwut-dev' with the
                                tree's root -- the directory holding
                                'vut/', found by ascending from the
                                working directory or '--directory' --
                                mounted READ-WRITE at its own absolute
                                path, the working directory the same
                                inside as outside, as the user you are.
                                Without a command: an interactive shell.
                                With one: that command, its exit status
                                the face's.
    hwut.dev.podman.enter --help
                                this text

    hwut.dev.podman.enter                              a shell
    hwut.dev.podman.enter bin/hwut.run --plain         the census
    hwut.dev.podman.enter -- sh -c 'cd vut/services/TEST && ../../bin/hwut.run'

THE TREE IS THE HOST'S, NOT A COPY: an edit, an accepted GOOD, a book
entry made inside stands outside the moment it is made, under your own
user id ('--userns=keep-id' with podman; '--user' with docker). The
container holds the requirements and nothing of the tree; it is thrown
away on exit ('--rm').

Where the image does not stand, the face says so and names
'hwut.dev.podman.build'; it does not build unasked. Where no engine
stands, FAULT by name.
______________________________________________________________________________
"""
import os
import sys

from   vut.services._exit import E_ExitCode
from   vut.services.lib.dev.podman._common import (IMAGE, engine, hand_over,
                                                   root_of)
from   vut.services.lib.dev.podman.build   import image_stands

NAME  = "hwut.dev.podman.enter"
USAGE = "usage: %s [--directory=<path>] [-- <command>...] | --help" % NAME
HELP  = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip()


def run_argv(tool, root, cwd, command, uid, gid, tty_f):
    """
    RETURN: list of str, the engine's call: the root mounted at its own
            path, read-write; the working directory kept; the user kept;
            a terminal where one stands; the command, or a shell.
    """
    argv = [tool, "run", "--rm"]
    if tty_f: argv.append("-it")
    if tool == "podman": argv.append("--userns=keep-id")
    else:                argv.append("--user=%i:%i" % (uid, gid))
    argv += ["-v", "%s:%s" % (root, root), "-w", cwd,
             "-e", "HOME=/tmp", IMAGE]
    argv += list(command) if command else ["bash"]
    return argv


def main(argv=None, write=None, run=None, tty_f=None):
    """
    RETURN: E_ExitCode (E-1): the command's status as OK/FAULT, FAULT
            where no engine, no root or no image stands, REFUSED where
            the command line cannot be read.

    'write' takes one line of text; 'run' replaces the engine for a
    test (takes argv, answers the status); 'tty_f' says whether a
    terminal stands (asked of stdin where None).
    """
    if write is None: write = print
    if argv is None:  argv = sys.argv[1:]
    if argv and argv[0] in ("--help", "-h"):
        write(HELP)
        return E_ExitCode.OK
    directory, command = None, []
    i = 0
    while i < len(argv):
        word = argv[i]
        if word == "--":
            command = argv[i + 1:]; break
        elif word.startswith("--directory="):
            directory = word[12:]; i += 1
        elif word.startswith("-") and not command:
            write("REFUSED: %s does not take: %s (a command's own options "
                  "follow '--')" % (NAME, word))
            write(USAGE)
            return E_ExitCode.REFUSED
        else:
            command = argv[i:]; break
    tool = engine()
    if tool is None:
        write("FAULT: neither 'podman' nor 'docker' stands on this machine")
        return E_ExitCode.FAULT
    root = root_of(directory)
    if root is None:
        write("FAULT: no directory holding 'vut/' above '%s'"
              % os.path.abspath(directory or os.getcwd()))
        return E_ExitCode.FAULT
    if not image_stands(tool, run):
        write("FAULT: the image '%s' does not stand; 'hwut.dev.podman.build' "
              "builds it" % IMAGE)
        return E_ExitCode.FAULT
    if tty_f is None: tty_f = sys.stdin.isatty()
    cwd = os.path.abspath(directory or os.getcwd())
    status = hand_over(run_argv(tool, root, cwd, command, os.getuid(),
                                os.getgid(), tty_f), write, run)
    return E_ExitCode.OK if status == 0 else E_ExitCode.FAULT


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from vut.services._exit import guarded
    sys.exit(guarded(NAME, main, sys.argv[1:]))
