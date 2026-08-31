"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: The 'hwut.parse' service (R-29). It checks the syntax, resolves the
         defaults, and prints the complete configuration as a tree.

    hwut.parse <source file>    scan for the trigger, extract, print
    hwut.parse                  act as the explorer: 'hwut.conf' first,
                                then the files of the directory
    --no-default                drop every value nobody stated, leaving
                                what somebody chose
    --provenance                name the place of every stated value --
                                the file and the line it stands on
    --gnu                       name it in the GNU error format,
                                'file:line:column', which an editor
                                jumps to

What it shows is what the framework READ -- not what was written, which the
author can read himself.
______________________________________________________________________________
"""
import os

from .          import finder
from .          import reader
from .explorer  import explore
from .printer   import app_text


def text_of_file(directory, name, no_default_f=False,
                 provenance_f=False, gnu_f=False):
    """
    RETURN: [0] str, the file's specification as a tree; '' where the
                file carries no specification.
            [1] list[Fault], every fault met.
    """
    path = os.path.join(directory, name)
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        content = fh.read()

    spec, fault_list = reader.read_header(content, name)
    #  A specification that carries a fault yields NO tree: exploration
    #  refuses it rather than guessing at it, and the service shows what
    #  exploration will do, not more.
    if spec is None or fault_list: return "", fault_list

    from .explorer import _resolve
    return app_text(_resolve(spec, _inherited_of(directory)),
                    no_default_f, provenance_f, gnu_f), fault_list


def _inherited_of(directory):
    """
    RETURN: DirectorySpec, the root's word folded down to 'directory'
            ('tree_explorer.ascended_spec') -- so that 'language-setup'
            reaches a single-directory reading (R-73).
            None where no 'hwut-root.conf' stands above: 'hwut.show'
            works on a bare directory, and reads it bare.
    """
    from .tree_explorer import ascended_spec, RootConfMissing
    try:                      return ascended_spec(directory)[0]
    except RootConfMissing:   return None


def text_of_directory(directory, interview_runner=None,
                      no_default_f=False, provenance_f=False,
                      gnu_f=False):
    """
    RETURN: [0] str, every test application of the directory as a tree.
            [1] list[Fault], every fault met.

    The order is the explorer's: 'hwut.conf' first, then the files.
    """
    result = explore(directory, interview_runner=interview_runner,
                     inherited=_inherited_of(directory))
    text_list = []

    spec = result.app_set.directory_spec
    stated = [(name, getattr(spec, name))
              for name in ("on_entry", "on_exit", "ignore", "collision",
                           "dependency")
              if getattr(spec, name)]
    if stated:
        text_list.append(finder.CONF_NAME)
        for name, value in stated:
            text_list.append("    %-20s %s" % (name, _printed(value)))
        text_list.append("")

    for app in result.app_set:
        text_list.append(app_text(app, no_default_f,
                                  provenance_f, gnu_f))
        text_list.append("")

    for case in sorted(result.app_set.misdep_set,
                       key=lambda c: (c[0], c[1] or "")):
        text_list.append("%s %s   [MISDEP]"
                         % (case[0], "-" if case[1] is None else case[1]))

    return "\n".join(text_list), list(result.fault_list)


def _printed(value):
    """RETURN: str, a directory key's value, briefly."""
    if isinstance(value, dict):
        return "  ".join("%s <- %s" % (target,
                                       ", ".join(str(x) for x in needed))
                         for target, needed in sorted(value.items(),
                                                      key=str))
    if isinstance(value, tuple):
        return ", ".join(str(item) for item in value)
    return str(value)
