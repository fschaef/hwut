"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE SELECTION -- given a wish, WHICH RUNS? One action, one
         place.

Six faces wrote these four lines apiece:

    explore / explore_tree      what the directory offers
    Bookkeeper(...)             where the wish asks the base
    CTestTaskListQuery(...)     the selection
    .get_test_cases(app_set)    the runs

'plan', 'wishlist', 'accept', 'report', 'play' and the label faces
each assembled them, differing only in whether they walk ONE DIRECTORY
or A TREE. That is not six faces using a component -- it is ONE ACTION
IMPLEMENTED SIX TIMES, and the sixth copy is where they start to
disagree.

TWO DOORS, because there are two shapes and no more:

    of_directory(directory, wish, ...)   one directory, its own root
    of_tree(root, wish, ...)             the walk, directory by
                                         directory

THE BOOKKEEPER IS MADE HERE, above the query, exactly as the hand-down
law requires -- and in ONE agreed place rather than six copied ones.
The law is unchanged; only the number of implementations is.

    A FACE WHOSE SUBJECT IS STORAGE still makes its own and should:
    'hwut.rename' and 'hwut.remove' re-key and forget records, and
    that is not a selection. This module serves the faces that SELECT.

THE GLOB REACH TRAVELS WITH THE SELECTION. A glob that met only runs
the standard label silences must speak (disc-8), and the accumulation
runs over the WHOLE walk -- a glob silenced in one directory may stand
plainly in the next, and a warning about it there would be a lie. The
faces used to accumulate that by hand too.
______________________________________________________________________________
"""
import os
from   dataclasses import dataclass

from   .explorer         import explore
from   .tree_explorer    import (explore_tree, explore_tree_stream,
                                 ascended_spec)
from   .task_list       import CTestTaskListAll
from   .task_list_query  import CTestTaskListQuery
from   ..plan.label      import swallowed_warning_tuple
from   ...bookkeeper.api import Bookkeeper


@dataclass(frozen=True, slots=True)
class CSelection:
    """What a wish selected, and what the selecting found on the way.

    'case_list'      the runs, in walk order. For a tree walk each
                     entry carries the DIRECTORY it was found in,
                     relative to the root -- the very form a wishlist
                     line takes.
    'fault_tuple'    what the exploration could not read. A tree that
                     cannot be fully read cannot say what it offers,
                     and a face decides for itself whether to proceed.
    'warning_tuple'  findings that decide nothing: a glob wholly
                     swallowed by the standard label's silence.
    'result_db'      directory -> ExplorationResult, for a face that
                     needs the shape as well as the selection.
    'bookkeeper_db'  directory -> the Bookkeeper made for it, or None
                     where the wish did not ask the base. A FACE THAT
                     READS THE BOOK gets the one already made rather
                     than making a second: 'hwut.report' needs the
                     selection AND the record behind it, and two
                     Bookkeepers over one directory is two answers to
                     one question.
    'query_db'       directory -> the CTestTaskListQuery. A FACE THAT
                     PLANS takes the query itself: 'determine' reads a
                     task list, not a list of cases.
    'met_set'        every glob of the wish that met at least one run
                     ANYWHERE in the walk. A caller wanting 'which
                     globs met nothing' subtracts this from the wish's
                     own globs -- it must not re-derive the answer,
                     because deriving it needs the root and the
                     queries THIS module built."""
    case_list:     list
    fault_tuple:   tuple = ()
    warning_tuple: tuple = ()
    result_db:     dict  = None
    bookkeeper_db: dict  = None
    query_db:      dict  = None
    met_set:       frozenset = frozenset()


@dataclass(frozen=True, slots=True)
class CSelectedCase:
    """One selected run, and where it was found.

    'directory' is relative to the root the selection walked; '.' for
    a single-directory selection, which is its own root."""
    directory: str
    case:      object


def of_directory(directory, wish, label_view=None, inherited=None,
                 base_f=None):
    """
    RETURN: CSelection over ONE directory, which is its own root.

    A PATH-BEARING GLOB IS MATCHED AGAINST '.', so './test-x.py' names
    a test here and 'other/test-x.py' names nothing -- which is true.

    Raises SelectionError out of the query, unchanged: a wish that
    names a label no view can answer is refused, never guessed at.
    """
    #  THE ROOT'S WORD REACHES A SINGLE DIRECTORY TOO (R-73): a face
    #  that has not ascended itself gets the climb here, so
    #  'language-setup' governs 'hwut.play' as it governs 'hwut.run'.
    if inherited is None:
        inherited, _ascent_fault_list = ascended_spec(directory)
    result     = explore(directory, inherited=inherited)
    #  'base_f' OVERRIDES THE WISH'S OWN ANSWER, for the face that
    #  needs the book whatever the wish asked: 'hwut.accept' reads
    #  candidates, and a bare wish asks no base.
    want_f     = wish.asks_base_f() if base_f is None else base_f
    bookkeeper = Bookkeeper(directory) if want_f else None
    query      = CTestTaskListQuery(wish, bookkeeper, directory=".",
                                    root=os.path.abspath(directory),
                                    label_view=label_view)
    case_list  = [CSelectedCase(".", case)
                  for case in query.get_test_cases(result.app_set)]
    return CSelection(case_list     = case_list,
                      fault_tuple   = tuple(result.fault_list),
                      warning_tuple = _warning_tuple(query, wish,
                                                     result.app_set),
                      result_db     = {".": result},
                      bookkeeper_db = {".": bookkeeper},
                      query_db      = {".": query},
                      met_set       = _met_set(query, wish,
                                               result.app_set))


def of_tree(root, wish, label_view=None, base_f=None):
    """
    RETURN: CSelection over the whole tree below 'root', directory by
            directory in WALK ORDER.

    THE WALK'S DIRECTORY IS RELATIVE to the root -- the very form a
    wishlist line carries, so a face need not rebase what it is given.

    Raises SelectionError and RootConfMissing out of the walk,
    unchanged.
    """
    exploration = explore_tree(root)
    case_list     = []
    result_db     = {}
    bookkeeper_db = {}
    query_db      = {}
    met_set       = set()
    visible_set   = set()
    want_f        = wish.asks_base_f() if base_f is None else base_f
    for directory, result in exploration:
        result_db[directory] = result
        bookkeeper = Bookkeeper(os.path.join(root, directory)) \
                     if want_f else None
        bookkeeper_db[directory] = bookkeeper
        query = CTestTaskListQuery(wish, bookkeeper,
                                   directory=directory, root=root,
                                   label_view=label_view)
        query_db[directory] = query
        if wish.glob_tuple:
            met, visible = query.glob_reach(result.app_set)
            met_set.update(met)
            #  THE SILENCE CAN ONLY SWALLOW where a view reaches: with
            #  none, everything met is visible.
            visible_set.update(met if label_view is None else visible)
        for case in query.get_test_cases(result.app_set):
            case_list.append(CSelectedCase(directory, case))
    return CSelection(
        case_list     = case_list,
        fault_tuple   = tuple(exploration.fault_tuple),
        warning_tuple = swallowed_warning_tuple(met_set, visible_set),
        result_db     = result_db,
        bookkeeper_db = bookkeeper_db,
        query_db      = query_db,
        met_set       = frozenset(met_set))


def of_tree_stream(root, wish, label_view=None, base_f=None,
                   fault_list=None):
    """
    YIELD: [0] str            one directory, RELATIVE to 'root', walk
                              order.
           [1] ExplorationResult   what it offers.
           [2] Bookkeeper | None   its book, where the wish asks for one.
           [3] list[CSelectedCase] the cases the wish selected there.

    ONE DIRECTORY AT A TIME, so a face can show a directory the moment
    it is known instead of after the whole tree has been walked
    ('explore_tree_stream'). The per-directory work is identical to
    'of_tree's loop body -- this is that loop, opened up.

    WHAT CANNOT STREAM IS NOT HERE. The swallowed-label warnings are a
    fact about the WHOLE selection (a label met in one directory can be
    invisible because of another), and so are the walk's faults; a face
    that needs either asks 'of_tree'. 'fault_list' is the caller's
    accumulator and is complete only when this generator is exhausted.
    """
    want_f = wish.asks_base_f() if base_f is None else base_f
    for directory, result in explore_tree_stream(root,
                                                 fault_list=fault_list):
        bookkeeper = Bookkeeper(os.path.join(root, directory)) \
                     if want_f else None
        query = CTestTaskListQuery(wish, bookkeeper,
                                   directory=directory, root=root,
                                   label_view=label_view)
        if wish.glob_tuple: query.glob_reach(result.app_set)
        case_list = [CSelectedCase(directory, case)
                     for case in query.get_test_cases(result.app_set)]
        yield directory, result, bookkeeper, case_list


def directory_tuple(root, wish):
    """
    RETURN: tuple[str], the DIRECTORIES a wish names, relative to
            'root', in walk order.

    THE OTHER VIEW OF ONE SELECTION (disc-10). A face whose subject is
    directories -- 'hwut.target' cleaning in each, 'hwut.sanitize'
    clearing wreckage -- asks this instead of asking for cases, and
    the wish it hands in is the very wish every other face uses.

    WHICH DIRECTORIES, and the rule reads both ways:

        the wish names DIRECTORIES     those, matched as
                                       '--exclude-dir' matches
        the wish names RUNS            the directories those runs
                                       STAND IN -- a run names its
                                       directory, so a wish of any
                                       shape answers this question
        the wish names NOTHING         every directory the tree offers

    THAT LAST TWO ARE WHAT MAKES THIS ONE VOCABULARY rather than two:
    a face asks for the view it needs, and the wish need not know
    which face asked.
    """
    if wish.states_nothing_f():
        return tuple(directory for directory, _ in explore_tree(root))
    found = of_tree(root, wish)
    seen  = []
    for entry in found.case_list:
        if entry.directory not in seen: seen.append(entry.directory)
    return tuple(seen)


def all_of_tree(root):
    """
    RETURN: CSelection over EVERY run the tree offers, no wish
            applied -- 'case_list' in walk order, each entry carrying
            its directory relative to 'root'.

    THE DOMAIN IS WHAT THE TREE OFFERS. A face asking 'which runs does
    NOT concern name' cannot ask a wish, because the answer includes
    the runs no label mentions at all -- and only the walk knows them.
    No Bookkeeper is made: nothing here asks the base.
    """
    exploration = explore_tree(root)
    case_list   = []
    result_db   = {}
    for directory, result in exploration:
        result_db[directory] = result
        for case in CTestTaskListAll().get_test_cases(result.app_set):
            case_list.append(CSelectedCase(directory, case))
    return CSelection(case_list   = case_list,
                      fault_tuple = tuple(exploration.fault_tuple),
                      result_db   = result_db)


def _met_set(query, wish, app_set):
    """
    RETURN: frozenset[str], the globs that met at least one run here.
    """
    if not wish.glob_tuple: return frozenset()
    met, _ = query.glob_reach(app_set)
    return frozenset(met)


def _warning_tuple(query, wish, app_set):
    """
    RETURN: tuple[str], the findings of ONE directory's selection --
            empty where no glob stands, or where no label view reaches
            it and the silence therefore cannot swallow anything.
    """
    if not wish.glob_tuple or query.label_view is None: return ()
    met, visible = query.glob_reach(app_set)
    return swallowed_warning_tuple(met, visible)
