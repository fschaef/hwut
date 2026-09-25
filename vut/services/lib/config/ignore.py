"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.config.ignore' COMMAND LINE -- the answer to the run's
         closing NOTE (X-SILENT). A file carrying no 'hwut { }' and named
         under no 'apps' is no test application; where it is a HELPER,
         this face says so once and for good, by writing the file's name
         into its directory's 'hwut.conf' under 'ignore'.

    hwut.config.ignore <path>...   whitespace separated, as the NOTE prints
                                   them: relative to where you stand
    --dont-ask                     write without showing and asking
    --help                         this text

THE AUTHOR'S FILE STAYS THE AUTHOR'S (E-48). Only the 'ignore' key is
touched: every other key, every comment and the whole layout are left as
they stand. Paths are grouped by directory, one 'hwut.conf' written per
directory, and a name already ignored is not written twice. Where no
'hwut.conf' stands, one is written holding the block and nothing else.

A path naming a directory, or naming a file that does not exist, is
REFUSED by name and nothing is written for that directory: an ignore
entry for a file nobody can see would be a lie that never expires.
______________________________________________________________________________
"""
import os
import sys

from   ..._exit  import E_ExitCode, guarded


USAGE = ("usage: hwut.config.ignore <path>... [--dont-ask]\n"
         "                          [--help]")


def _entry_text(name_list):
    """RETURN: str, the 'ignore' block as it is written into a
              'hwut.conf' that holds none -- the names in the order
              given, one statement, nothing else.
    """
    return ("hwut {\n    ignore = [%s]\n}\n"
            % ", ".join('"%s"' % name for name in name_list))


def _ignored_set_of(text):
    """RETURN: set, the names an existing 'ignore = [...]' already holds;
              empty where the file states none.

    Read as text, not as a parse tree: this face must put a name back
    where the author wrote his, and a re-rendered file would lose his
    comments and his layout.
    """
    start = text.find("ignore")
    if start < 0: return set()
    open_i = text.find("[", start)
    close_i = text.find("]", open_i)
    if open_i < 0 or close_i < 0: return set()
    return {word.strip().strip('",\' ')
            for word in text[open_i + 1:close_i].split(",")
            if word.strip()}


def _amended(text, name_list):
    """RETURN: str,  'text' with 'name_list' added to its 'ignore' key --
                     the key extended where it stands, a new key beside
                     the other directory keys where it does not.
              None, where the file holds no 'hwut { ... }' block to
                     extend, so the caller may refuse rather than guess.
    """
    ignored = _ignored_set_of(text)
    fresh   = [name for name in name_list if name not in ignored]
    if not fresh: return text
    start = text.find("ignore")
    if start >= 0:
        close_i = text.find("]", text.find("[", start))
        addition = "".join(', "%s"' % name for name in fresh)
        return text[:close_i] + addition + text[close_i:]
    open_i = text.find("{", text.find("hwut"))
    if open_i < 0: return None
    block = "\n    ignore = [%s]" % ", ".join('"%s"' % n for n in fresh)
    return text[:open_i + 1] + block + text[open_i + 1:]


def do(path_list, ask_f=True, write=print, ask=input):
    """
    RETURN: E_ExitCode.OK,      every named file is ignored by its
                                directory now -- written, or standing
                                there already.
            E_ExitCode.REFUSED, a path names no file that stands, or a
                                'hwut.conf' holds no block to extend, or
                                the answer to the question was no.

    'path_list' as the run's NOTE prints them: relative to where the
    caller stands. Grouped by directory, one file written per directory.
    """
    if not path_list:
        write("REFUSED: 'hwut.config.ignore' names no path")
        write(USAGE)
        return E_ExitCode.REFUSED
    group_db = {}
    for path in path_list:
        if not os.path.isfile(path):
            write("REFUSED: '%s' is no file that stands" % path)
            return E_ExitCode.REFUSED
        directory, name = os.path.split(path)
        group_db.setdefault(directory or ".", []).append(name)

    plan_list = []
    for directory in sorted(group_db):
        conf_path = os.path.join(directory, "hwut.conf")
        name_list = sorted(set(group_db[directory]))
        if os.path.exists(conf_path):
            text = open(conf_path, encoding="utf-8").read()
            amended = _amended(text, name_list)
            if amended is None:
                write("REFUSED: '%s' holds no 'hwut { ... }' block to "
                      "extend" % conf_path)
                return E_ExitCode.REFUSED
        else:
            amended = _entry_text(name_list)
        if not os.path.exists(conf_path) or amended != text:
            plan_list.append((conf_path, amended, name_list))

    if not plan_list:
        write("Nothing to do: every name stands under 'ignore' already.")
        return E_ExitCode.OK
    for conf_path, _, name_list in plan_list:
        write("%s:  ignore %s" % (conf_path, " ".join(name_list)))
    if ask_f:
        answer = ask("write? [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            write("Nothing written.")
            return E_ExitCode.REFUSED
    for conf_path, amended, _ in plan_list:
        with open(conf_path, "w", encoding="utf-8") as fh:
            fh.write(amended)
    return E_ExitCode.OK


def main(argv):
    """RETURN: E_ExitCode, as 'do' gives it; REFUSED where the command
               line itself is not understood.
    """
    if "--help" in argv:
        write = print
        write(__doc__.split("PURPOSE:", 1)[1].rstrip())
        return E_ExitCode.OK
    ask_f     = "--dont-ask" not in argv
    path_list = [word for word in argv[1:] if not word.startswith("-")]
    unknown   = [word for word in argv[1:]
                 if word.startswith("-") and word != "--dont-ask"]
    if unknown:
        print("REFUSED: '%s' is no option of 'hwut.config.ignore'"
              % unknown[0])
        print(USAGE)
        return E_ExitCode.REFUSED
    return do(path_list, ask_f=ask_f)


if __name__ == "__main__":
    sys.exit(guarded("hwut.config.ignore", main, sys.argv))
