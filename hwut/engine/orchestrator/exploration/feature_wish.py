"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FEATURE WISH -- which test runs '-F/--feature',
         '-e/--feature-ext' and '-k/--keys' want, read from the view of
         'hwut-root-features.conf' ('feature_view.view_of'; spec 23
         VERSION 10 section 11, R-96):

    -F <path-glob>   over TREE PATHS: the aggregate keys from the top, '/'
                     between, the leaf's EXTERNAL id last; an unplaced leaf
                     is its external id alone. '*' any part of ONE level,
                     '**' any number of levels, '{a,b}' alternatives; a bare
                     word is '**/word'. An aggregate brings its subtree. A
                     word with ':' is an INTERNAL id '<directory id>:<name>'
                     ('*' allowed). A retired internal id is refused.
    -e <id>          over EXTERNAL ids, whole; '*' any characters. An id
                     that names no feature, or a retired one, is refused by
                     name -- a customer's id that selects nothing silently
                     is the failure this wish exists to prevent.
    -k <expr>        the grammar of '-l' over the EFFECTIVE keys of a leaf
                     (its own, its TEST file's, the aggregates' above it).
                     A key no leaf carries is refused by name.

'-F' and '-e' are ONE union; '-k' narrows it. A run is wanted where ONE
leaf it is linked to is selected. A run linked to no feature is wanted by
none of them: all ask for features. Where no readable central file stands
the wish is refused => hwut.features.init.

THE VIEW is computed once per tree and process (reading the relation
costs a walk of the whole tree, and a query stands in every TEST
directory); 'forget_views' drops it, for a test that rebuilds a tree
under one path.

THIS MODULE REUSES: 'feature_view' for the leaves, their runs and keys,
'plan/label' for the expression's grammar and its evaluation. It adds
only the path glob.
______________________________________________________________________________
"""
import os
import re

from ..plan.label        import (evaluate_f, label_name_tuple,
                                 parse_expression)
from .task_list          import SelectionError


_GLOB_CHARS = re.compile(r"[*?\[{]")

_view_db = {}


def forget_views():
    """RETURN: None. Drops every view computed so far."""
    _view_db.clear()


def brace_alternative_tuple(pattern):
    """
    RETURN: tuple of str, 'pattern' with every '{a,b}' expanded into its
            alternatives (nested braces and several groups included),
            in order, each once; the pattern itself where no brace
            stands.

    Raises SelectionError for a brace that is not closed.
    """
    open_i = pattern.find("{")
    if open_i < 0:
        if "}" in pattern:
            raise SelectionError("'%s': a '}' without its '{'" % pattern)
        return (pattern,)
    depth, part_list, start = 0, [], open_i + 1
    for i in range(open_i, len(pattern)):
        char = pattern[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                part_list.append(pattern[start:i])
                close_i = i
                break
        elif char == "," and depth == 1:
            part_list.append(pattern[start:i])
            start = i + 1
    else:
        raise SelectionError("'%s': a '{' is not closed" % pattern)
    head, tail = pattern[:open_i], pattern[close_i + 1:]
    result = []
    for part in part_list:
        for inner in brace_alternative_tuple(part):
            for rest in brace_alternative_tuple(tail):
                text = head + inner + rest
                if text not in result: result.append(text)
    return tuple(result)


def _path_level_regex(level):
    """RETURN: re.Pattern, one level of a tree-path glob ('*' any run of
    characters, '?' one) over ONE level -- a level may hold dots (an
    external id)."""
    text = "".join(".*" if char == "*" else "." if char == "?"
                   else re.escape(char) for char in level)
    return re.compile(text + r"\Z")


def _path_chain_hit_f(level_tuple, part_tuple):
    """RETURN: bool, True where the glob levels match the path parts in
    whole: '**' any number of parts, none included, every other level one
    part."""
    if not level_tuple: return not part_tuple
    head, rest = level_tuple[0], level_tuple[1:]
    if head == "**":
        return any(_path_chain_hit_f(rest, part_tuple[i:])
                   for i in range(len(part_tuple) + 1))
    if not part_tuple: return False
    return _path_level_regex(head).match(part_tuple[0]) is not None \
           and _path_chain_hit_f(rest, part_tuple[1:])


def path_glob_hit_f(glob, part_tuple):
    """
    RETURN: bool, True where the tree-path glob 'glob' names the leaf at
            'part_tuple' (aggregate keys, then its external id) or a claim
            above it -- an aggregate brings its subtree. A glob without '/'
            and without '*', '?', '[' or '{' is a bare word: '**/word'.
    """
    if not _GLOB_CHARS.search(glob) and "/" not in glob:
        glob = "**/" + glob
    for alternative in brace_alternative_tuple(glob):
        level_tuple = tuple(alternative.strip("/").split("/"))
        for end in range(1, len(part_tuple) + 1):
            if _path_chain_hit_f(level_tuple, part_tuple[:end]):
                return True
    return False


def _whole_hit_f(glob, text):
    """RETURN: bool, True where 'glob' ('*' any characters, '{a,b}') matches
    'text' in whole."""
    return any(_path_level_regex(each).match(text) is not None
               for each in brace_alternative_tuple(glob))


def selected_leaf_list(view, wish):
    """
    RETURN: list of CLeafView, the leaves of 'view' the wish's '-F', '-e'
            and '-k' select, in the view's order -- THE ONE READING of the
            feature wish: the runs a face selects are these leaves' runs
            ('case_set_of'), the page 'hwut.report.features' prints is
            the view kept to them ('view_cut').
    Raises SelectionError for an external id that names no feature, for a
    retired id named by '-e' or '-F', and for a key no leaf carries.
    """
    leaf_list, known_set = _selected_and_known(view, wish)
    if wish.keys_spec is not None:
        unknown = [name for name in label_name_tuple(
                       parse_expression(wish.keys_spec))
                   if name not in known_set]
        if unknown:
            raise SelectionError(
                "no feature carries the key '%s'; keys that stand: %s"
                % ("', '".join(unknown),
                   ", ".join(sorted(known_set)) or "(none)"))
    return leaf_list


def view_cut(view, wish):
    """
    RETURN: CView, 'view' kept to the leaves the wish selects
            ('selected_leaf_list'), the aggregates above them as headers,
            folded and counted over what is kept.
    Raises SelectionError as 'selected_leaf_list' does.
    """
    from .feature_view import view_kept
    for glob in wish.feature_tuple + wish.feature_ext_tuple:
        brace_alternative_tuple(glob)
    chosen = {id(each) for each in selected_leaf_list(view, wish)}
    return view_kept(view, lambda each: id(each) in chosen)


def _selected_and_known(view, wish):
    """
    RETURN: [0] list of CLeafView, the leaves the wish's '-F', '-e' and
                '-k' select
            [1] frozenset of str, every key a leaf of the view carries
    Raises SelectionError for an external id that names no feature, and
    for a retired id named by '-e' or '-F'.
    """
    from .feature_registry import name_set, retired_internal_set
    leaf_list = view.leaf_list()
    retired_internal = retired_internal_set(view.registry)
    live_external = {each.leaf.external for each in leaf_list}
    retired_name = name_set(view.registry) - live_external - {
        each.aggregate.key for each in _aggregate_list(view)}
    for text in wish.feature_ext_tuple:
        if _GLOB_CHARS.search(text): continue
        if text in retired_name:
            raise SelectionError(
                "'--feature-ext %s' names a RETIRED feature: no longer "
                "claimed, no run proves it any more" % text)
        if text not in live_external:
            raise SelectionError(
                "'--feature-ext %s' names no feature: no line of "
                "'hwut-root-features.conf' has that external id => "
                "hwut.features.tree -e" % text)
    for text in wish.feature_tuple:
        if ":" in text and not _GLOB_CHARS.search(text) \
           and text in retired_internal:
            raise SelectionError(
                "'--feature %s' names a RETIRED feature: no longer "
                "claimed" % text)
    key_tree = None if wish.keys_spec is None \
               else parse_expression(wish.keys_spec)
    named_f  = bool(wish.feature_tuple or wish.feature_ext_tuple)
    selected_list, known_set = [], set()
    for each in leaf_list:
        known_set |= set(each.key_tuple)
        if named_f:
            part_tuple = tuple(each.tree_path.split("/")
                               if each.tree_path else ()) \
                         + (each.leaf.external,)
            hit = any(_whole_hit_f(text, each.leaf.internal)
                      if ":" in text else path_glob_hit_f(text, part_tuple)
                      for text in wish.feature_tuple) \
                  or any(_whole_hit_f(text, each.leaf.external)
                         for text in wish.feature_ext_tuple)
            if not hit: continue
        if key_tree is not None and not evaluate_f(key_tree,
                                                   set(each.key_tuple)):
            continue
        selected_list.append(each)
    return selected_list, frozenset(known_set)


def _aggregate_list(view):
    """RETURN: list of CAggregateView, every aggregate of the view."""
    result = []

    def walk(child_tuple):
        for each in child_tuple:
            if hasattr(each, "aggregate"):
                result.append(each)
                walk(each.child_tuple)

    walk(view.top_tuple)
    return result


def _asked_text(wish):
    """RETURN: str, the first feature option the wish states, as typed."""
    if wish.feature_tuple:     return "--feature"
    if wish.feature_ext_tuple: return "--feature-ext"
    return "--keys"


def case_set_of(root, wish):
    """
    RETURN: frozenset of (absolute test file, choice), the runs of the
            tree below 'root' that the wish's '-F', '-e' and '-k' want --
            empty where none does.

    Raises SelectionError where no readable central file stands, for a
    retired id, for an external id naming no feature, for a key no leaf
    carries (a misspelt key silently selecting nothing is how an
    author comes to believe a set is empty), and for a glob that cannot
    be read.
    """
    root = os.path.abspath(root)
    mark = (root, wish.feature_tuple, wish.keys_spec,
            wish.feature_ext_tuple)
    if mark in _view_db: return _view_db[mark]
    # the globs are read once, so a broken one is refused at the door
    for glob in wish.feature_tuple + wish.feature_ext_tuple:
        brace_alternative_tuple(glob)
    from .tree_explorer import inner_root_tuple
    #  EVERY BUBBLE ANSWERS FOR ITS OWN RUNS (RQ-9, services E-200): a
    #  bubble's feature file names its runs, as when hwut is called inside
    #  it. A refusal stands where EVERY bubble refuses -- an id no bubble
    #  knows; a bubble that does not know it simply offers none.
    top_tuple  = (root,) + inner_root_tuple(root)
    case_set   = frozenset()
    error_list = []
    for top in top_tuple:
        try:
            case_set |= _bubble_case_set(top, wish)
        except SelectionError as error:
            error_list.append(error)
    if error_list and len(error_list) == len(top_tuple):
        raise error_list[0]
    _view_db[mark] = case_set
    return case_set


def _bubble_case_set(top, wish):
    """
    RETURN: frozenset of (absolute test file, choice), the runs of the
            ONE bubble 'top' stands in (no walk below an inner root)
            that the wish's '-F', '-e' and '-k' want, by that bubble's
            own central file;
            raises SelectionError, as 'case_set_of' says, else.
    """
    from .feature_view  import view_of, ViewRefused
    from .tree_explorer import RootConfMissing
    try:
        view = view_of(top)
    except (ViewRefused, RootConfMissing) as error:
        raise SelectionError("'%s' asks for features: %s"
                             % (_asked_text(wish), error)) from error
    return frozenset(
        (os.path.normpath(os.path.join(view.asked,
                                       run.path or each.test_path,
                                       run.test)), run.choice)
        for each in selected_leaf_list(view, wish)
        if each.feature_state is not None
        for run in each.feature_state.run_tuple)
