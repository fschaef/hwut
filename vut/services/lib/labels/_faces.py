"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHAT THE FIVE LABEL FACES SHARE -- the '--directory' option,
         the selection over the tree, the glob warnings, the report
         lines. One place, so five faces cannot drift apart.

THE SELECTION IS THE WISH, the same wish every face takes, evaluated
by the same 'CTestTaskListQuery' -- with the label view handed down,
so '--label' works HERE already, and the standard label's silence
holds here as everywhere: a wish that asks no label does not want what
'meta' labels. The report makes it visible -- expansion is stated RUN
BY RUN, which is what makes write-time expansion honest rather than
merely convenient.
______________________________________________________________________________
"""
import os
from dataclasses import dataclass, field
from vut.engine.orchestrator.plan.wish import Wish
import sys

from   vut.engine.orchestrator.exploration          import selection
from   vut.engine.orchestrator.plan.wish             import (WishError,
                                                             parse_wish)
from   vut.services._exit                            import E_ExitCode


class Refused(Exception):
    """THE PROLOGUE REFUSED, and what it wrote is already written. The
    face catches this and returns the carried code -- nothing more to
    say, since 'opened()' has said it."""

    def __init__(self, exit_code):
        Exception.__init__(self, str(exit_code))
        self.exit_code = exit_code


def opened(argv, write, help_text, usage_text):
    """
    RETURN: [0] callable, the 'write' to use -- the caller's, or
                'print' where none was given.
            [1] CWish, the wish parsed from the arguments.
            [2] str, the '--directory=<path>' value, '.' where none.
            [3] list[str], the arguments left after the wish and the
                directory are taken out.

    Raises 'Refused' where the face must stop AND THE REASON IS
    ALREADY WRITTEN: '--help' (code OK, the help stands), or a wish
    that does not parse (code REFUSED, the error and the usage stand).

    WHAT EVERY LABEL FACE DOES BEFORE IT DOES ITS OWN WORK -- default
    the writer, answer '--help', parse the wish, split the directory
    off. Five faces wrote it out; one drifting from the others would
    be a face that answers '--help' differently from its siblings for
    no reason a reader could find.
    """
    if write is None: write = print
    if argv is None:  argv  = sys.argv[1:]
    if "--help" in argv:
        write(help_text)
        raise Refused(E_ExitCode.OK)

    try:
        wish, rest_list = parse_wish(argv)
    except WishError as error:
        write("REFUSED: %s" % error)
        write(usage_text)
        raise Refused(E_ExitCode.REFUSED)
    directory, rest_list = split_directory(rest_list)
    return write, wish, directory, rest_list


def split_directory(argument_list):
    """
    RETURN: [0] str, the '--directory=<path>' value; '.' where none
                stands.
            [1] list[str], the arguments that are not it, in order.
    """
    directory = "."
    rest_list = []
    for argument in argument_list:
        if argument.startswith("--directory="):
            directory = argument[len("--directory="):]
        else:
            rest_list.append(argument)
    return directory, rest_list


def selected_key_tuple(directory, wish, view):
    """
    RETURN: [0] tuple[(str, str | None)], every run the wish selects,
                as entry keys of the labels file -- the file RELATIVE
                TO THE BOUNDARY, and the choice -- in walk order.
            [1] tuple[str], the findings: a glob that met NOTHING, and
                one wholly swallowed by the standard label's silence.
                Neither is a refusal.
            [2] tuple[Fault], the walk's own faults.

    Raises SelectionError out of the query, unchanged, and
    RootConfMissing out of the walk.

    THE SELECTION IS THE BRICK'S ('exploration/selection.py'). What is
    left here is the only labels-specific part: REKEYING a case to the
    form the labels file writes, and speaking a glob in the file's own
    tongue rather than as an absolute path.
    """
    root   = os.path.abspath(directory)
    prefix = os.path.relpath(root, view.boundary)
    found  = selection.of_tree(root, wish, view)

    key_list = [(_boundary_relative(prefix, entry.directory,
                                    entry.case.source_file),
                 entry.case.choice)
                for entry in found.case_list]

    #  THE WARNINGS SPEAK IN THE FILE'S TONGUE: an absolute path is a
    #  machine's word, not the author's.
    warning_list = [text.replace(text.split("'")[1],
                                 _spoken(text.split("'")[1],
                                         view.boundary))
                    for text in found.warning_tuple]
    for glob_text in wish.glob_tuple:
        if glob_text in found.met_set: continue
        warning_list.append("WARNING: the glob '%s' met nothing"
                            % _spoken(glob_text, view.boundary))
    return (tuple(key_list), tuple(sorted(warning_list)),
            found.fault_tuple)


def _spoken(glob_text, boundary):
    """
    RETURN: str, the glob as a warning may speak it: as given -- or,
            where a wishlist's './' resolution made it ABSOLUTE, in
            './'-form against 'boundary', which is the file's own
            tongue. An absolute path is a machine's word, not the
            author's, and no report echoes one where a stable form
            exists.
    """
    file_part, _, choice_part = glob_text.partition(" ")
    if not os.path.isabs(file_part): return glob_text
    relative = os.path.relpath(file_part, boundary).replace(os.sep, "/")
    if relative.startswith("../"):   return glob_text
    spoken = "./%s" % relative
    return "%s %s" % (spoken, choice_part) if choice_part else spoken


def _boundary_relative(prefix, where, source_file):
    """
    RETURN: str, the source file as the labels file keys it: relative
            to the BOUNDARY, '/'-separated -- the walk's root-relative
            place rebased by 'prefix', the root's own place under the
            boundary.
    """
    joined = os.path.normpath(os.path.join(prefix, where, source_file))
    return joined.replace(os.sep, "/")


#  ------------------------------------------------------------------
#  THE FAMILY'S RECORDS (services E-106). Five faces, one door
#  ('opened') and one editing layer ('_editing'): so one Request and
#  one Result serve them all, and what each face DID is data before it
#  is a page.
@dataclass(frozen=True)
class Request:
    """WHAT WAS ASKED of a label face: the label, where the tree
    stands, and the wish that names the members -- ONE nested record,
    not its keywords spelled out again. 'Wish' is frozen and holds
    nothing but plain fields, so the Request stays plain."""
    label:     str  = ""
    directory: str  = "."
    wish:      Wish = field(default_factory=Wish)


@dataclass(frozen=True)
class Result:
    """WHAT THE FACE DID: the label it touched, the members that
    entered or left, and whether the label itself stands afterwards."""
    label:         str = ""
    added_tuple:   tuple = ()      # target texts
    removed_tuple: tuple = ()      # target texts
    untouched_n:   int = 0
    stands_f:      bool = True
    member_n:      int = 0


def request_of(label, wish, directory):
    """RETURN: Request, a label, a Wish and a directory, as asked."""
    return Request(label=label, directory=directory, wish=wish)


def wish_of(request):
    """RETURN: Wish, the one the request carries."""
    return request.wish


@dataclass(frozen=True)
class Standing:
    """WHAT STANDS in the tree's labels file (E-106): one row per
    label, its members counted -- what 'hwut.labels.list' answers."""
    row_tuple: tuple = ()          # of (label, member_n)

    @property
    def label_tuple(self):
        """RETURN: tuple[str], the labels, sorted as the page says
                   them."""
        return tuple(label for label, _ in self.row_tuple)


def standing_of(entry_db):
    """RETURN: Standing, the labels of 'entry_db' with their member
               counts, sorted by name."""
    count_db = {}
    for label_set in entry_db.values():
        for label in label_set:
            count_db[label] = count_db.get(label, 0) + 1
    return Standing(tuple((label, count_db[label])
                          for label in sorted(count_db)))


@dataclass(frozen=True)
class Answer:
    """WHAT A QUESTION ABOUT LABELS ANSWERS (E-106): the targets the
    expression names, each with the labels it carries, and whatever
    reading the tree faulted on -- plain fields, three ways of saying
    them (the elided page, the expanded one, the labelled one)."""
    target_tuple:  tuple = ()      # of (target text, labels text)
    elided_tuple:  tuple = ()      # the same targets, elided
    fault_tuple:   tuple = ()

    @property
    def empty_f(self):
        """RETURN: bool, True where the expression named nothing."""
        return not self.target_tuple
