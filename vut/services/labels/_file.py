"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut-root.labels' -- reading it, writing it (disc-8).

The file stands BESIDE 'hwut-root.conf', at the tree's boundary, the
very boundary the configuration climb ends at
('tree_explorer.root_conf_directory'). Absent means no label exists,
which is not an error.

    #  hwut-root.labels -- the sets of this tree.
    ./engine/bookkeeper/TEST/test-group_table.py : concern
    :/: groups                                   : meta
    :/test-stream_store.py                       : meta

    <target> : <label> [<label>...]

ONE MARK, TWO POSITIONS: a LEADING ':' is a ditto for one path
component (':/' the previous entry's directory, ':/:' its directory
and file, a choice following); an INTERIOR ' : ' -- one colon, a blank
either side -- separates the target from its labels.

LITERAL TARGETS ONLY. Globbing is for what a PERSON writes -- the
command line and a wishlist; THIS FILE IS THE FRAMEWORK'S, the faces
expand at write time, and a glob found here is refused by name.

SORTED on '(directory, file, choice)', the choice-less entry of an
application first; the writer rewrites the file WHOLE, sorted and
elided, so the ditto chain is always canonical and a hand edit that
broke it is repaired by the next write. A hand comment does not
survive a rewrite; the header says whose file this is.

ONE LINE PER RUN. A run named twice is a fault, named by line: two
answers to one question is not a merge, it is a mistake.
______________________________________________________________________________
"""
import io
import os

from   vut.engine.orchestrator.plan.label import (KEYWORD_TUPLE,
                                                  LABEL_NAME_REGEX,
                                                  STANDARD_LABEL,
                                                  UNIVERSE_NAME,
                                                  CLabelView)
from   vut.engine.orchestrator.plan.wish  import (ElisionError,
                                                  expanded_target)
from   vut.engine.orchestrator.exploration.tree_explorer \
                                          import root_conf_directory

LABELS_FILE_NAME = "hwut-root.labels"

GLOB_MARK_TUPLE  = ("*", "?", "[")

HEADER = ("#  %s -- the sets of this tree (disc-8)." % LABELS_FILE_NAME,
          "#  Written whole, sorted, by 'hwut.labels.*'; a hand edit",
          "#  holds, a hand comment does not survive the next write.")


class LabelFileError(Exception):
    """A labels file that cannot be meant: a missing separator, a
    glob, a ditto with no predecessor, a run named twice, a word no
    label may be. The message names file and line."""


def file_path(boundary):
    """
    RETURN: str, where the labels file of the tree bounded at
            'boundary' stands -- beside 'hwut-root.conf'.
    """
    return os.path.join(boundary, LABELS_FILE_NAME)


def boundary_of(directory):
    """
    RETURN: str, the absolute directory holding the 'hwut-root.conf'
            that bounds the tree 'directory' stands in.

    Raises RootConfMissing (tree_explorer) where none stands: the
    labels file anchors where the configuration climb ends, or two
    climbs could name two trees.
    """
    return root_conf_directory(directory)


def read_entry_db(boundary):
    """
    RETURN: dict, '(<file>, <choice> | None)' -> frozenset[str] -- what
            'hwut-root.labels' assigns; the file path RELATIVE to
            'boundary', '/'-separated, no './'. Empty where the file
            is absent, which means: no label exists.

    Raises LabelFileError, naming file and line, where a line cannot
    be meant (see the module purpose).
    """
    path = file_path(boundary)
    if not os.path.isfile(path): return {}
    with io.open(path, "r", encoding="utf-8") as file_handle:
        line_list = file_handle.read().splitlines()

    entry_db = {}
    previous = None                        # last EXPANDED target text
    for number, line in enumerate(line_list, start=1):
        text = line.strip()
        if not text or text.startswith("#"): continue
        target_part, label_part = _split(path, number, text)
        if target_part.startswith(":"):
            try:
                target_part = expanded_target(target_part, previous)
            except ElisionError as error:
                raise LabelFileError("%s:%d: %s"
                                     % (path, number, error))
        previous = target_part
        key = _key(path, number, target_part)
        if key in entry_db:
            raise LabelFileError(
                "%s:%d: the run '%s' is named twice -- two answers "
                "to one question is not a merge, it is a mistake"
                % (path, number, target_text(key)))
        entry_db[key] = frozenset(_label_tuple(path, number,
                                               label_part))
    return entry_db


def write_entry_db(boundary, entry_db):
    """
    RETURN: None. Rewrites 'hwut-root.labels' WHOLE: header, then the
            entries sorted and elided. An 'entry_db' holding nothing
            REMOVES the file -- absent and empty mean the same, 'no
            label exists', and only one of the two spellings can be
            canonical.
    """
    path = file_path(boundary)
    if not entry_db:
        if os.path.isfile(path): os.remove(path)
        return
    line_list = _elided_line_list(entry_db)
    width     = max(len(target) for target, _ in line_list)
    with io.open(path, "w", encoding="utf-8", newline="\n") \
         as file_handle:
        for line in HEADER:
            file_handle.write(line + "\n")
        for target, label_tuple in line_list:
            file_handle.write("%-*s : %s\n"
                              % (width, target,
                                 " ".join(label_tuple)))


def defined_label_set(entry_db):
    """
    RETURN: frozenset[str], every label that stands -- the assigned
            ones, and the standard label always: 'meta' needs no
            'create' and is never undefined.
    """
    found = set((STANDARD_LABEL,))
    for label_set in entry_db.values():
        found.update(label_set)
    return frozenset(found)


def view_of(boundary, entry_db):
    """
    RETURN: CLabelView over 'entry_db' -- the shape the engine's
            selection reads (plan/label.py).
    """
    return CLabelView(boundary = os.path.abspath(boundary),
                      entry_db = dict(entry_db),
                      defined  = defined_label_set(entry_db))


def sort_key(key):
    """
    RETURN: tuple, the file's sort order for an entry key: directory
            COMPONENT-WISE, then file, then the choice -- the
            choice-less entry of an application FIRST, because the
            ditto chain hangs on the order.
    """
    file, choice = key
    directory, _, name = file.rpartition("/")
    part_tuple = tuple(directory.split("/")) if directory else ()
    return (part_tuple, name,
            (0, "") if choice is None else (1, choice))


def target_text(key):
    """
    RETURN: str, the entry as a full target line: './<file>', a choice
            after one blank where the key holds one.
    """
    file, choice = key
    return "./%s" % file if choice is None \
           else "./%s %s" % (file, choice)


def elided_target_tuple(key_list):
    """
    RETURN: tuple[str], the keys as WRITTEN targets, in the order
            given -- full ('./<file> [<choice>]'), ':/<file>
            [<choice>]' where the directory repeats, ':/: <choice>'
            where the file does. The caller sorts ('sort_key'); the
            elision only pays, and only holds, over a sorted run.
    """
    target_list   = []
    previous_file = None
    previous_dir  = None
    for key in key_list:
        file, choice = key
        full      = "./%s" % file
        directory = full.rsplit("/", 1)[0]
        if full == previous_file:
            assert choice is not None, \
                   "one file twice without a choice is a duplicate " \
                   "key, refused at reading"
            target = ":/: %s" % choice
        elif directory == previous_dir:
            target = ":/%s" % full.rsplit("/", 1)[1]
            if choice is not None: target += " %s" % choice
        else:
            target = target_text(key)
        previous_file = full
        previous_dir  = directory
        target_list.append(target)
    return tuple(target_list)


def _elided_line_list(entry_db):
    """
    RETURN: list[(str, tuple[str])], the entries sorted, each as its
            WRITTEN target with its labels sorted beside it.
    """
    key_list = sorted(entry_db, key=sort_key)
    return [(target, tuple(sorted(entry_db[key])))
            for key, target
            in zip(key_list, elided_target_tuple(key_list))]


def _split(path, number, text):
    """
    RETURN: [0] str, the target half of the line.
            [1] str, the label half.

    Raises LabelFileError where no ' : ' separator stands -- one
    colon, a blank either side. A leading ditto's colons carry no
    blank before them, so position alone tells the two apart.
    """
    target_part, separator, label_part = text.partition(" : ")
    if not separator:
        raise LabelFileError(
            "%s:%d: no ' : ' separates the target from its labels"
            % (path, number))
    return target_part.rstrip(), label_part.strip()


def _key(path, number, target_text):
    """
    RETURN: (str, str | None), the entry key of the EXPANDED target:
            the file relative to the boundary, and the choice.

    Raises LabelFileError where the target does not start './' -- the
    file's own ground, stated, not guessed -- or where it carries a
    glob: LITERAL TARGETS ONLY, this file is the framework's, and a
    stored pattern would hold two truths at once.
    """
    if not target_text.startswith("./"):
        raise LabelFileError(
            "%s:%d: a target starts './' -- the file's own ground -- "
            "and '%s' does not" % (path, number, target_text))
    if any(mark in target_text for mark in GLOB_MARK_TUPLE):
        raise LabelFileError(
            "%s:%d: '%s' carries a glob; this file holds LITERAL "
            "targets only -- globs are spent by the faces at write "
            "time, never stored" % (path, number, target_text))
    body = target_text[2:]
    file, _, choice = body.partition(" ")
    choice = choice.strip()
    return (file, choice if choice else None)


def _label_tuple(path, number, label_part):
    """
    RETURN: tuple[str], the labels of one line, each a word a label
            may be.

    Raises LabelFileError for an empty label half, a keyword, the
    universe, or a word outside the label alphabet. The STANDARD label
    is a label and passes.
    """
    word_tuple = tuple(label_part.split())
    if not word_tuple:
        raise LabelFileError("%s:%d: the line names no label"
                             % (path, number))
    for word in word_tuple:
        if word in KEYWORD_TUPLE or word == UNIVERSE_NAME:
            raise LabelFileError(
                "%s:%d: '%s' is reserved and never assigned"
                % (path, number, word))
        if LABEL_NAME_REGEX.match(word) is None:
            raise LabelFileError(
                "%s:%d: a label is letters, digits, '_', '-', '.' -- "
                "'%s' is not" % (path, number, word))
    return word_tuple
