"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE BOUNDARY, OR AN OFFER TO PLACE ONE.

Every face of this framework works inside a TREE, and a tree is what
'hwut-root.conf' bounds. Without it there is no root to make a path
relative to, no place for 'hwut-root.labels', and no answer to 'which
directories are mine'. A face that proceeds without one is guessing.

WHAT A MISSING BOUNDARY USED TO GET: a refusal naming the file. True,
and useless to somebody who has just arrived in a tree they did not
build -- they now know a file is missing and not WHERE IT GOES.

WHAT IT GETS NOW: the refusal, the reason, and AN OFFER. The
candidates are the directory and its parents, up to the home
directory or the file system's root, LETTERED:

    no 'hwut-root.conf' stands in or above 'engine/compare/TEST'.
    A tree needs a boundary: it is the root every path is relative
    to, and the place 'hwut-root.labels' and the register stand.

    Where shall it go?
        A   engine/compare/TEST
        B   engine/compare
        C   engine
        D   .                        <- usually this one
        anything else  --  nothing is written

    choice:

THE LETTERS ADAPT. Eight is the ceiling, not the shape: a directory
three deep offers three. THE COUNT IS WHAT STANDS, never padded to a
number.

ANY OTHER KEY ABORTS, and abort means NOTHING IS WRITTEN. A person who
typed by accident, or who meant a directory not on the list, must be
able to leave without having changed the tree -- and a bare RETURN is
the commonest accident there is.

NOT ASKED WHERE NOBODY CAN ANSWER. Where the input is not a terminal
-- a script, a pipe, a suite -- the offer is not made: a question
nobody can hear is a hang, not a courtesy. The face refuses as before
and says what would have been offered.
______________________________________________________________________________
"""
import os
import sys

LETTER_TUPLE = ("A", "B", "C", "D", "E", "F", "G", "H")

ROOT_CONF_NAME = "hwut-root.conf"

EMPTY_TEXT = "hwut {\n}\n"


def candidate_tuple(directory):
    """
    RETURN: tuple[str], the directories a boundary could be placed in
            -- this one and its parents, NEAREST FIRST, stopping at
            the home directory or the file system's root, and at
            'LETTER_TUPLE' many.

    EVERY DIRECTORY OF THE CLIMB IS OFFERED, '/' and '/tmp' included:
    what is unusual is not what is forbidden, and a person who means
    to root a tree at '/tmp' knows better than this code does.

    A DIRECTORY THE PERSON CANNOT WRITE IS STILL OFFERED, and SAID TO
    BE UNWRITEABLE. Leaving it out would make the letters skip, and a
    person counting down the list would wonder what they had missed;
    naming the reason answers that before it is asked.

    THE CLIMB STOPS AT A PROJECT'S TOP where it meets one -- a
    directory holding '.git', 'setup.py', 'pyproject.toml' or
    'Makefile'. That is where a boundary usually belongs, and past it
    lies somebody else's tree.
    """
    TOP_MARK = (".git", "setup.py", "pyproject.toml", "Makefile")
    here     = os.path.abspath(directory)
    found    = []
    while len(found) < len(LETTER_TUPLE):
        found.append(here)
        if any(os.path.exists(os.path.join(here, mark))
               for mark in TOP_MARK):     break
        parent = os.path.dirname(here)
        if parent == here:                break
        here = parent
    return tuple(found)


def writeable_f(path):
    """
    RETURN: bool, True where the person running this may create a file
            in the directory.
    """
    return os.access(path, os.W_OK | os.X_OK)


def shown(path, start):
    """
    RETURN: str, the candidate as a person reads it: relative to
            'start' where that is shorter, '.' for 'start' itself, the
            absolute path where relative would climb further than it
            explains.
    """
    relative = os.path.relpath(path, os.path.abspath(start))
    if relative == ".":                    return "."
    if not relative.startswith(".."):      return relative
    #  A CLIMB READS BADLY as '../../..': the absolute path says more,
    #  and a person choosing a directory must SEE which one.
    return path


def _top_f(path):
    """
    RETURN: bool, True where the directory looks like a project's top
            -- it holds '.git', 'setup.py', 'pyproject.toml' or
            'Makefile'. That is where a boundary usually belongs, and
            saying so saves a person from counting letters.
    """
    return any(os.path.exists(os.path.join(path, mark))
               for mark in (".git", "setup.py", "pyproject.toml",
                            "Makefile"))


def offer_text_tuple(directory):
    """
    RETURN: tuple[str], the lines of the offer -- the problem, the
            reason, and the lettered candidates.

    THE REASON IS GIVEN, not merely the fact: a person who has just
    arrived needs to know what a boundary IS before choosing where to
    put one.
    """
    candidate = candidate_tuple(directory)
    line_list = [
        "REFUSED: no '%s' stands in or above '%s'."
        % (ROOT_CONF_NAME, shown(os.path.abspath(directory), ".")),
        "    A tree needs a boundary: it is the root every path is",
        "    relative to, and the place 'hwut-root.labels' and the",
        "    register stand.",
        ""]
    line_list.append("Where shall it go?")
    for letter, path in zip(LETTER_TUPLE, candidate):
        if not writeable_f(path):
            mark = "   (no write access by user)"
        elif _top_f(path):
            mark = "   <- the project's top"
        else:
            mark = ""
        line_list.append("    %s   %-28s%s"
                         % (letter, shown(path, directory), mark))
    line_list.append("    anything else  --  nothing is written")
    return tuple(line_list)


def placed(directory, write, ask=None):
    """
    RETURN: str, the directory a boundary was written into.
            None where none was -- because nobody could be asked,
            because the answer named no candidate, or because the
            write failed. THE REASON IS ALREADY WRITTEN.

    'ask' takes a prompt and answers a line; 'input' where None, and
    NOT CALLED AT ALL where the input is no terminal.

    NOTHING IS WRITTEN ON ANY ANSWER BUT A LETTER THAT STANDS. A bare
    RETURN is the commonest accident there is, and it must leave the
    tree as it was.
    """
    for text in offer_text_tuple(directory): write(text)

    if ask is None:
        if not sys.stdin.isatty():
            #  A QUESTION NOBODY CAN HEAR IS A HANG, not a courtesy.
            write("")
            write("    (no terminal: nothing is written. Place the "
                  "file yourself,")
            write("     or run this again where a person can answer.)")
            return None
        ask = input

    try:    answer = ask("choice: ").strip().upper()
    except (EOFError, KeyboardInterrupt):
        write("")
        return None

    candidate = candidate_tuple(directory)
    if len(answer) != 1 or answer not in LETTER_TUPLE[:len(candidate)]:
        write("nothing written.")
        return None

    where = candidate[LETTER_TUPLE.index(answer)]
    if not writeable_f(where):
        #  THE OFFER SAID SO, and the person chose it anyway. Refuse
        #  by name rather than letting the write fail with an errno.
        write("REFUSED: '%s' cannot be written in -- the offer said "
              "so, and nothing is written." % shown(where, directory))
        return None
    path  = os.path.join(where, ROOT_CONF_NAME)
    try:
        with open(path, "w", encoding="utf-8") as file_handle:
            file_handle.write(EMPTY_TEXT)
    except OSError as error:
        write("FAULT: '%s' cannot be written -- %s" % (path, error))
        return None
    write("written: %s" % path)
    return where
