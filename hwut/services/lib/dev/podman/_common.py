"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHAT 'hwut.dev.podman.build' AND 'hwut.dev.podman.enter' SHARE --
         the engine, the image's name, the tree's root, and the one way
         a face hands over to the engine.

    THE ENGINE is 'podman'; 'docker' where podman does not stand (the
    words below are the same for both, but for the user mapping).
    THE ROOT is the directory that holds 'hwut/', found by ascending from
    the working directory: the tree is mounted THERE, at its own
    absolute path, so a path printed inside the container is the same
    path outside.
    THE IMAGE is 'hwut-dev', built from 'hwut/adm/container/Containerfile'.
______________________________________________________________________________
"""
import os

#  THE ENGINE AND THE ROOT ARE THE ENGINE'S (spec/42 section 4): a
#  platform of kind 'container' finds them the same way, and the engine
#  imports nothing of the faces.
from .....engine.platforms.container import (CONTAINERFILE,      # noqa F401
                                            engine, root_of)

IMAGE = "hwut-dev"


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
