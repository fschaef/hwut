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

from   vut.engine.bookkeeper.bookkeeper              import Bookkeeper
from   vut.engine.orchestrator.exploration.task_list_query \
                                                     import CTestTaskListQuery
from   vut.engine.orchestrator.exploration.tree_explorer \
                                                     import explore_tree
from   vut.engine.orchestrator.plan.label            import swallowed_warning_tuple


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
            [1] tuple[str], one warning per '--glob' that MET NOTHING,
                the glob named. Not a refusal: the pattern is well
                formed, and today's tree simply holds no such run.
            [2] tuple[Fault], the walk's own faults.

    Raises SelectionError out of the query, unchanged, and
    RootConfMissing out of the walk.
    """
    root        = os.path.abspath(directory)
    exploration = explore_tree(root)
    prefix      = os.path.relpath(root, view.boundary)
    result_list = list(exploration)

    key_list = []
    for where, result in result_list:
        bookkeeper = Bookkeeper(os.path.join(root, where)) \
                     if wish.asks_base_f() else None
        query = CTestTaskListQuery(wish, bookkeeper,
                                   directory=where, root=root,
                                   label_view=view)
        for case in query.get_test_cases(result.app_set):
            key_list.append((_boundary_relative(prefix, where,
                                                case.source_file),
                             case.choice))

    #  ONE WARNING FUNCTION for the whole framework
    #  ('plan/label.py'): a glob wholly swallowed by the silence
    #  speaks alike in every face. A LITERAL target never appears
    #  here -- it overrides the silence (disc-8).
    met_set     = set()
    visible_set = set()
    for where, result in result_list:
        met, visible = CTestTaskListQuery(
                           wish, directory=where, root=root,
                           label_view=view).glob_reach(result.app_set)
        met_set.update(met)
        visible_set.update(visible)

    warning_list = [text.replace(text.split("'")[1],
                                 _spoken(text.split("'")[1],
                                         view.boundary))
                    for text in swallowed_warning_tuple(met_set,
                                                        visible_set)]
    for glob_text in wish.glob_tuple:
        if glob_text in met_set: continue
        warning_list.append("WARNING: the glob '%s' met nothing"
                            % _spoken(glob_text, view.boundary))
    return (tuple(key_list), tuple(sorted(warning_list)),
            exploration.fault_tuple)


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
