"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ONE COMMAND LINE of the converters over an output
         directory -- 'hwut.cov.conv.to_<format> [DIRECTORY] [-o
         TARGET] [<own options>]' -- so seven faces refuse, default and
         fail the same way (coverage D-44).

    DIRECTORY   the '-o' of 'hwut.cov.run'; './hwut.coverage' where none
                is named; refused where it is no directory or carries no
                marker of a coverage run
    -o TARGET   where the result goes; a FILE for the formats that are
                one file (stdout where none is named), a DIRECTORY for
                the ones that are many (a default beside the data)
______________________________________________________________________________
"""
import os
import sys

from   vut.engine.coverage.api      import (DEFAULT_DIRECTORY_NAME,
                                            OutputRefused, root_of)
from   vut.services._exit           import E_ExitCode
from   vut.services.lib.cov.summary import summaries_of


def parse(name, usage, argv, write, option_db=None, flag_set=()):
    """
    RETURN: [0] str, the output directory
            [1] str, the target of '-o', None where none was named
            [2] dict, option -> value for 'option_db' (None where
                absent), flag -> True/False for 'flag_set'
            None, where the command line was refused -- 'write' said
            why, and the usage line.

    'option_db' maps an option word ('--style') to its metavar; a flag
    takes no value.
    """
    option_db = option_db or {}
    directory_list, target, found = [], None, {}
    for flag in flag_set: found[flag] = False
    for option in option_db: found[option] = None
    i = 0
    while i < len(argv):
        word = argv[i]
        if word in ("-o", "--output"):
            if i + 1 >= len(argv) or target is not None:
                write("REFUSED: '%s' takes one target, once" % word)
                write(usage)
                return None
            target = argv[i + 1]; i += 2
        elif word in option_db:
            if i + 1 >= len(argv) or found[word] is not None:
                write("REFUSED: '%s' takes one %s, once"
                      % (word, option_db[word]))
                write(usage)
                return None
            found[word] = argv[i + 1]; i += 2
        elif word in flag_set:
            found[word] = True; i += 1
        elif word.startswith("-"):
            write("REFUSED: unknown option '%s'" % word); write(usage)
            return None
        else:
            directory_list.append(word); i += 1
    if len(directory_list) > 1:
        write("REFUSED: %s takes at most one DIRECTORY" % name)
        write(usage)
        return None
    directory = directory_list[0] if directory_list \
                else os.path.join(os.getcwd(), DEFAULT_DIRECTORY_NAME)
    return directory, target, found


def checked(directory, write):
    """RETURN: True, 'directory' is an output directory of a coverage
    run; False, 'write' said what it is instead."""
    if not os.path.isdir(directory):
        write("FAULT: '%s' is no directory" % directory)
        return False
    if root_of(directory) is None:
        write("FAULT: '%s' carries no marker of a coverage run; name "
              "the '-o' directory of 'hwut.cov.run'" % directory)
        return False
    return True


def one_file_main(name, usage, help_text, build, argv=None, write=None,
                  write_bytes=None, option_db=None, flag_set=()):
    """
    RETURN: E_ExitCode (E-1): OK with the result written, FAULT where
            the output directory cannot be read or the target not
            written, REFUSED where the command line cannot be read.

    For a converter whose result is ONE FILE: 'build(root,
    summary_list, found)' answers its bytes; they go to '-o TARGET' or
    to 'write_bytes' -- stdout's buffer where none is given, so a test
    may capture the face without a process. 'write' takes one line of
    text.
    """
    if write is None:       write = print
    if write_bytes is None: write_bytes = sys.stdout.buffer.write
    if argv is None:        argv = sys.argv[1:]
    if "--help" in argv or "-h" in argv:
        write(help_text)
        return E_ExitCode.OK
    parsed = parse(name, usage, argv, write, option_db, flag_set)
    if parsed is None: return E_ExitCode.REFUSED
    directory, target, found = parsed
    if not checked(directory, write): return E_ExitCode.FAULT
    try:
        root, summary_list = summaries_of(directory)
        data = build(root, summary_list, found, target)
    except OutputRefused as refusal:
        write("FAULT: %s" % refusal)
        return E_ExitCode.FAULT
    except OSError as fault:
        write("FAULT: %s" % fault)
        return E_ExitCode.FAULT
    if target is None:
        write_bytes(data)
        return E_ExitCode.OK
    try:
        with open(target, "wb") as handle: handle.write(data)
    except OSError as fault:
        write("FAULT: %s" % fault)
        return E_ExitCode.FAULT
    return E_ExitCode.OK


def many_files_main(name, usage, help_text, build, default_name, argv=None,
                    write=None, option_db=None, flag_set=()):
    """
    RETURN: E_ExitCode (E-1), as 'one_file_main'.

    For a converter whose result is MANY FILES, or one that must be
    built in a directory of its own: 'build(root, summary_list, found,
    out_dir)' writes them and answers the line 'write' prints -- the
    path of what to open. 'out_dir' is '-o TARGET', else
    'DIRECTORY/<default_name>'.
    """
    if write is None: write = print
    if argv is None:  argv = sys.argv[1:]
    if "--help" in argv or "-h" in argv:
        write(help_text)
        return E_ExitCode.OK
    parsed = parse(name, usage, argv, write, option_db, flag_set)
    if parsed is None: return E_ExitCode.REFUSED
    directory, target, found = parsed
    if not checked(directory, write): return E_ExitCode.FAULT
    if target is None: target = os.path.join(directory, default_name)
    try:
        root, summary_list = summaries_of(directory)
        line = build(root, summary_list, found, target)
    except OutputRefused as refusal:
        write("FAULT: %s" % refusal)
        return E_ExitCode.FAULT
    except OSError as fault:
        write("FAULT: %s" % fault)
        return E_ExitCode.FAULT
    if line is None: return E_ExitCode.FAULT
    write(line)
    return E_ExitCode.OK


def help_of(doc):
    """RETURN: str, a converter's '--help' text: its module docstring
    without the licence line and the closing rule."""
    return doc.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip()
