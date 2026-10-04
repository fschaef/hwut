"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHAT 'hwut.dev.podman.build' AND 'hwut.dev.podman.enter' SHARE --
         the engine, the image's name, the tree's root, and the one way
         a face hands over to the engine.

    THE ENGINE is 'podman'; 'docker' where podman does not stand (the
    words below are the same for both, but for the user mapping).
    THE ROOT is the directory that holds 'vut/', found by ascending from
    the working directory: the tree is mounted THERE, at its own
    absolute path, so a path printed inside the container is the same
    path outside.
    THE IMAGE is 'hwut-dev', built from 'vut/adm/container/Containerfile'.
______________________________________________________________________________
"""
import os
import shutil

IMAGE      = "hwut-dev"
CONTAINERFILE = os.path.join("vut", "adm", "container", "Containerfile")


def engine():
    """RETURN: str, 'podman' or 'docker', whichever stands first on PATH.
    None, where neither does."""
    for name in ("podman", "docker"):
        if shutil.which(name): return name
    return None


def root_of(directory=None):
    """
    RETURN: str, the absolute path of the directory holding 'vut/', found
            by ascending from 'directory' (the working directory where
            none is given).
            None, where no ancestor holds one.
    """
    here = os.path.abspath(directory or os.getcwd())
    while True:
        if os.path.isdir(os.path.join(here, "vut")) \
           and os.path.isfile(os.path.join(here, CONTAINERFILE)):
            return here
        parent = os.path.dirname(here)
        if parent == here: return None
        here = parent


def hand_over(argv, write, run=None):
    """
    RETURN: int, the engine's exit status. The call is printed first,
            as a person would type it, so what the face did is never a
            guess. 'run' replaces the engine for a test (takes argv,
            answers the status); where none is given the engine REPLACES
            this process ('execvp'), so a shell entered is the shell
            itself, not a child of python.
    """
    write("$ " + " ".join(_quoted(word) for word in argv))
    if run is not None: return run(argv)
    os.execvp(argv[0], argv)


def _quoted(word):
    """RETURN: str, 'word' as a shell shows it: quoted where it holds a
    blank or a shell character."""
    if word and all(ch.isalnum() or ch in "-_./=:,+@" for ch in word):
        return word
    return "'" + word.replace("'", "'\\''") + "'"
