"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE: THE FILES A 'pype' VALUE READS -- so that no script a test names
is a wallflower (ruled 2026-11-22: "ein script das in 'pype=' irgendwo
erwaehnt ist soll automatisch ignoriert werden").

    pype = "cheers.pype"                         cheers.pype
    pype = "kitchen.pypes"                       kitchen.pypes, its scripts
    pype = "python3.11 /x/pype.py c.pype"        c.pype
           and every 'import: "FILE"' of a script read, transitively.

EVERY WORD of the value that names a file is read (the command form names
the script anywhere in the line). Of a '.pype' file its 'import:' lines
are followed -- against the importer's directory, then each '--pype-dir'
of the value; of a '.pypes' system the scripts of its edges, against the
system's directory. What cannot be read or resolved is passed over: the
run says why, not the exploration.

THE GRAMMAR IS pype's ('services/lib/pype': 'RE_IMPORT_HEAD',
'RE_IMPORT_PATH', 'pype_system.RE_EDGE'); the engine may not import the
services (adm/LAYERING.txt), so the two lines are written here again and
'TEST/test-pype-reference.py' holds them equal to pype's own parse.
______________________________________________________________________________
"""
import os
import re
import shlex

RE_IMPORT_HEAD = re.compile(r"^import\s*(<ticks>)?\s*:\s*(.*)$")
RE_IMPORT_PATH = re.compile(r'^"((?:[^"\\]|\\.)*)"$')
RE_EDGE        = re.compile(r"^(\S*)\s*-->\s*(\S+)\s*$")


def file_set(pype_value, directory):
    """
    RETURN: set[str], the absolute path of every file the canonicaliser
            'pype_value' (a test's 'pype' key) reads when it runs in
            'directory': the words of the value that name a file, the
            scripts of a '.pypes' system, and every 'import:' of a
            '.pype' script, transitively.
            An empty set, where the value names no file.
    """
    try:
        word_list = shlex.split(pype_value)
    except ValueError:
        return set()
    search_dir_list = [os.path.join(directory, word_list[k + 1])
                       for k, word in enumerate(word_list[:-1])
                       if word == "--pype-dir"]
    done = set()
    todo = [os.path.abspath(os.path.join(directory, word))
            for word in word_list]
    while todo:
        path = todo.pop()
        if path in done or not os.path.isfile(path): continue
        done.add(path)
        if path.endswith(".pypes"):
            todo.extend(_system_script_list(path))
        elif path.endswith(".pype"):
            todo.extend(_import_list(path, search_dir_list))
    return done


def _lines(path):
    """
    RETURN: list[str], the stripped lines of 'path'.
            An empty list, where it cannot be read.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return [line.strip() for line in fh.read().splitlines()]
    except OSError:
        return []


def _system_script_list(path):
    """
    RETURN: list[str], the absolute path of every script an edge of the
            '.pypes' system 'path' names (source or target), against the
            system's directory.
    """
    base = os.path.dirname(path)
    result = []
    for text in _lines(path):
        match = RE_EDGE.match(text.split("#", 1)[0].strip())
        if match is None: continue
        result.extend(os.path.abspath(os.path.join(base, word))
                      for word in match.groups() if word not in ("", ":"))
    return result


def _import_list(path, search_dir_list):
    """
    RETURN: list[str], the absolute path of every file an 'import:' line
            of the '.pype' script 'path' names: its first candidate that
            stands -- the importer's directory, then 'search_dir_list'.
    """
    result = []
    for text in _lines(path):
        head = RE_IMPORT_HEAD.match(text)
        if head is None: continue
        quoted = RE_IMPORT_PATH.match(head.group(2).strip())
        if quoted is None: continue
        path_txt = os.path.expandvars(quoted.group(1))
        if os.path.isabs(path_txt):
            candidate_list = [path_txt]
        else:
            candidate_list = [os.path.join(d, path_txt)
                              for d in [os.path.dirname(path)]
                                       + search_dir_list]
        for candidate in candidate_list:
            if os.path.isfile(candidate):
                result.append(os.path.abspath(candidate))
                break
    return result
