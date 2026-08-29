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

from   vut.engine.orchestrator.exploration          import selection


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
