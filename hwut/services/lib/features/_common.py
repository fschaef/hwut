"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHAT THE FEATURE FACES SHARE -- '--help', '--directory=<path>',
         the root of the tree, the directory asked below it, and the way a
         finding of the detector is printed. One place, so the faces cannot
         drift apart.
______________________________________________________________________________
"""
import os
import sys

from hwut.engine.orchestrator.exploration.tree_explorer \
                                     import RootConfMissing, root_conf_directory
from hwut.engine.orchestrator.exploration.finder import REGISTRY_FILE_NAME
from ..._exit                        import E_ExitCode


class Refused(Exception):
    """The face must stop; what it wrote is written. 'exit_code' is the
    status to return."""

    def __init__(self, exit_code):
        Exception.__init__(self, str(exit_code))
        self.exit_code = exit_code


def opened(name, argv, write, help_text):
    """
    RETURN: [0] callable, the 'write' to use (the caller's, or 'print')
            [1] str, the '--directory=<path>' value, '.' where none
            [2] list of str, the arguments left
    Raises Refused (OK) where '--help' was asked: the page is written.
    """
    if write is None: write = print
    if argv is None:  argv  = sys.argv[1:]
    if "--help" in argv:
        from ..._core import man_page
        write(man_page(name, help_text))
        raise Refused(E_ExitCode.OK)
    directory, rest = ".", []
    for argument in argv:
        if argument.startswith("--directory="):
            directory = argument.split("=", 1)[1] or "."
        else:
            rest.append(argument)
    return write, directory, rest


def root_of(directory, write):
    """RETURN: str, the absolute directory holding 'hwut-root.conf' above
    'directory'. Raises Refused (REFUSED) where none stands; the reason is
    written."""
    try:
        return root_conf_directory(directory)
    except RootConfMissing as error:
        write("REFUSED: %s" % error)
        raise Refused(E_ExitCode.REFUSED) from None


def below_of(root, directory, path, write):
    """RETURN: str, the path of 'path' (taken from 'directory'; 'directory'
    itself where 'path' is None) relative to 'root', '/'-separated, '.' for
    the root. Raises Refused (REFUSED) where it does not stand below the
    root, or is no directory."""
    target = os.path.abspath(os.path.join(directory, path or "."))
    relative = os.path.relpath(target, root)
    if relative == ".." or relative.startswith(".." + os.sep):
        write("REFUSED: '%s' does not stand below the root '%s'"
              % (path or directory, root))
        raise Refused(E_ExitCode.REFUSED)
    if not os.path.isdir(target):
        write("REFUSED: '%s' is no directory" % (path or directory))
        raise Refused(E_ExitCode.REFUSED)
    return relative.replace(os.sep, "/")


def registry_path(root):
    """RETURN: str, the path of the central file of the tree at 'root'."""
    return os.path.join(root, REGISTRY_FILE_NAME)


def finding_lines(found):
    """RETURN: list of str, the detector's findings as printed: one line per
    finding, its kind first, '(hint)' behind a hint, each proposal below it
    after '=>'."""
    width = max((len(each.kind) for each in found), default=0)
    result = []
    for each in found:
        result.append("    %-*s  %s%s" % (width, each.kind, each.text,
                                          "   (hint)" if each.hint_f else ""))
        for line in each.proposal:
            result.append("    %-*s      => %s" % (width, "", line))
    return result


def path_below(root, directory, path, write):
    """RETURN: str, 'path' (taken from 'directory') relative to 'root',
    '/'-separated; it need not stand. Raises Refused (REFUSED) where it
    lies outside the root."""
    target = os.path.abspath(os.path.join(directory, path))
    relative = os.path.relpath(target, root)
    if relative == ".." or relative.startswith(".." + os.sep):
        write("REFUSED: '%s' does not stand below the root '%s'"
              % (path, root))
        raise Refused(E_ExitCode.REFUSED)
    return relative.replace(os.sep, "/")


def act_main(name, help_text, usage, argv, write, arity, act):
    """
    RETURN: E_ExitCode, the status of a face that takes exactly 'arity'
            words and hands them to 'act(root, directory, write, *words)',
            which returns the lines to print: OK where it acted; REFUSED
            where the command line cannot be read, no root stands, or the
            act was refused (ActRefused; the reason is printed).
    """
    from hwut.engine.orchestrator.exploration.feature_registry_act \
        import ActRefused
    try:
        write, directory, rest = opened(name, argv, write, help_text)
        option_list = [each for each in rest if each.startswith("-")]
        if option_list or len(rest) != arity:
            write("REFUSED: '%s' %s" % (
                name, "does not take: %s" % ", ".join(option_list)
                if option_list else "takes %d word(s): %s"
                % (arity, ", ".join(rest) or "none given")))
            write(usage)
            return E_ExitCode.REFUSED
        root = root_of(directory, write)
        line_list = act(root, directory, write, *rest)
    except Refused as refusal:
        return refusal.exit_code
    except ActRefused as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    for line in line_list:
        write(line)
    return E_ExitCode.OK
