"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE PERSON'S PREFERENCES -- how hwut SHOWS things, never what it
         does (services E-78). THE ONE READER of '~/.hwut.conf'; colours
         today, and whatever preference comes next -- read here, handed
         down: the engine's ink takes a 'color_of' function and never
         imports this module (services E-82).

DESCRIPTION
       TWO FILES, ONE LANGUAGE (our HOCON dialect), key by key:

           ~/.hwut.conf              the person's own; DOMINATES
           <root>/bin/.hwut.conf     the installation's default, beside
                                     the 'hwut.*' apps; states EVERY key,
                                     and its comments list the words a
                                     colour may be written with

       A key the person states wins; every other key comes from the
       default. A project's 'hwut.conf' never holds a preference, and
       this file never holds an operational key: a project reigns over
       what is run and compared, not over how a person's terminal looks.

       A COLOUR is a quoted string of words, applied left to right:

           red green yellow blue magenta cyan white black
                                     the foreground; 'bright-' before any
           bg-<name>                 the background; 'bg-bright-<name>'
           c256:N  bg256:N           a 256-colour palette entry
           #rrggbb bg#rrggbb         a true colour
           bold dim italic underline reverse
           none                      nothing at all (also: an empty string)

       Each reader asks for a ROLE -- 'element.numeric', 'verdict.subject',
       'keyed.spent', ... -- and receives it in its own form: an ANSI SGR
       parameter string for a stream, a 'prompt_toolkit' style for the
       keyed screen.

       A FAULTY PREFERENCE NEVER STOPS A RUN. An unknown key, an unknown
       colour word, a file that does not parse: the default stands for
       that key, and ONE line on stderr names what was ignored and where.
______________________________________________________________________________
"""
import os
import sys

from vut.test_writing_support.python import hwut_hocon
from vut.engine.display.colour import (word_list_valid, sgr, paint,   # noqa: F401
                                       toolkit_style, ELEMENT_ROLE_DB)

USER_PATH    = os.path.join("~", ".hwut.conf")
DEFAULT_NAME = ".hwut.conf"


def default_path():
    """RETURN: str, the installation's preference file -- '.hwut.conf' in
               the 'bin' directory beside the 'hwut.*' apps."""
    vut_dir = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))                 # services/lib -> vut
    return os.path.join(vut_dir, "bin", DEFAULT_NAME)


class Preferences:
    """The merged preferences: the default's every key, the person's
    stated keys over them."""

    def __init__(self, color_db, note_list):
        """RETURN: Preferences, holding 'color_db' (role -> colour) and
                   the notes on what was ignored."""
        self.color_db  = color_db
        self.note_list = note_list

    def color(self, role):
        """RETURN: str, the colour of 'role' (e.g. 'element.numeric') as
                   written in the files.
                   '', where no file names the role."""
        return self.color_db.get(role) or ""


_LOADED = None


def load(user_path=None, default=None, err=None):
    """RETURN: Preferences, the default file's keys overlaid by the
               person's -- read ONCE per process; later calls return
               the same object. Notes go to 'err' (stderr) once."""
    global _LOADED
    if _LOADED is not None and user_path is None and default is None:
        return _LOADED
    default_db, note_list = _read(default or default_path(), None)
    user_db,    more      = _read(os.path.expanduser(user_path or USER_PATH),
                                  set(default_db))
    note_list.extend(more)
    color_db = dict(default_db)
    color_db.update(user_db)
    result = Preferences(color_db, note_list)
    write = err or (lambda line: sys.stderr.write(line + "\n"))
    for note in note_list: write(note)
    if user_path is None and default is None: _LOADED = result
    return result


def _read(path, known_set):
    """RETURN: [0] dict, role -> colour, every well-formed key of the
                   file at 'path'; empty where the file does not exist.
               [1] list[str], one NOTE per thing ignored.

    'known_set' is the set of roles a key may name; None admits every
    role -- the default file is what DEFINES them."""
    if not os.path.isfile(path): return {}, []
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    from vut.engine.orchestrator.exploration import unwrapper
    document, fault_list = hwut_hocon.parse(unwrapper.plain_lines(text), path)
    if fault_list:
        fault = fault_list[0]
        return {}, ["NOTE: %s:%i: preferences ignored -- %s"
                    % (path, fault.position.line, fault.message)]
    result, note_list = {}, []
    for entry in document.entry_list:
        if entry.key != "hwut" or not hasattr(entry.node, "entry_list"):
            note_list.append("NOTE: %s:%i: '%s' ignored -- a preference "
                             "file holds one 'hwut' block"
                             % (path, entry.key_position.line, entry.key))
            continue
        for inner in entry.node.entry_list:
            if inner.key != "colors" or not hasattr(inner.node, "entry_list"):
                note_list.append("NOTE: %s:%i: '%s' ignored -- not a "
                                 "preference ('colors' is)"
                                 % (path, inner.key_position.line, inner.key))
                continue
            _collect(inner.node, "", path, known_set, result, note_list)
    return result, note_list


def _collect(node, prefix, path, known_set, result, note_list):
    """RETURN: None. Every leaf below 'node' entered into 'result' as
               'prefix.key' -> colour; what is ill-formed, noted."""
    for entry in node.entry_list:
        role = prefix + entry.key
        if hasattr(entry.node, "entry_list"):
            _collect(entry.node, role + ".", path, known_set, result, note_list)
            continue
        where = "NOTE: %s:%i: colour '%s'" % (path, entry.key_position.line, role)
        if known_set is not None and role not in known_set:
            note_list.append("%s ignored -- no such role" % where)
            continue
        value = entry.node.value if hasattr(entry.node, "value") else None
        if value is None: value = ""
        if not isinstance(value, str):
            note_list.append("%s ignored -- a colour is a quoted string" % where)
            continue
        bad = word_list_valid(value)
        if bad is not None:
            note_list.append("%s ignored -- unknown word '%s'" % (where, bad))
            continue
        result[role] = value


