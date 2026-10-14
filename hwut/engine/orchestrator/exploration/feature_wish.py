"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FEATURE WISH -- which test runs '-F/--feature' and
         '-k/--keys' want (exploration R-95).

    -F <id-glob>   over FULL ids, matched by KEY NAMES
                       '*'      one key (or part of one: 'scr*')
                       '**'     any number of keys, none included
                       '{a,b}'  alternatives
                       a bare key is '**.key'
                   A COMPONENT BRINGS ITS SUBTREE: the glob names a
                   claim and every feature below it is wanted.
                   An id the feature map publishes is resolved through
                   it first: it means the full id the map binds it to,
                   exactly. A RETIRED id is refused by name.
    -k <expr>      the grammar of '-l' over the EFFECTIVE keys of a
                   feature. A key no feature carries is refused by name.

A RUN IS WANTED where ONE feature it is linked to is named by an '-F'
glob (where any stands) AND satisfies the '-k' expression (where one
stands). A run linked to no feature is wanted by neither: both ask for
features.

THE VIEW is computed once per tree and process (reading the relation
costs a walk of the whole tree, and a query stands in every TEST
directory); 'forget_views' drops it, for a test that rebuilds a tree
under one path.

THIS MODULE REUSES: 'feature_relation' for the ids, the keys and the map,
'plan/label' for the expression's grammar and its evaluation. It adds
only the id glob.
______________________________________________________________________________
"""
import os
import re

from ..plan.label        import (evaluate_f, label_name_tuple,
                                 parse_expression)
from .feature_relation   import relation_of_tree
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


def _level_regex(level):
    """RETURN: re.Pattern, the key-level glob 'level' ('*' any run of
    characters, '?' one) as a regular expression over ONE key."""
    text = "".join("[^.]*" if char == "*" else "[^.]" if char == "?"
                   else re.escape(char) for char in level)
    return re.compile(text + r"\Z")


def _chain_hit_f(level_tuple, key_tuple):
    """
    RETURN: bool, True where the glob levels 'level_tuple' match the keys
            'key_tuple' in whole: '**' takes any number of keys, none
            included, every other level one key.
    """
    if not level_tuple: return not key_tuple
    head, rest = level_tuple[0], level_tuple[1:]
    if head == "**":
        return any(_chain_hit_f(rest, key_tuple[i:])
                   for i in range(len(key_tuple) + 1))
    if not key_tuple: return False
    return _level_regex(head).match(key_tuple[0]) is not None \
           and _chain_hit_f(rest, key_tuple[1:])


def glob_hit_f(glob, key_tuple):
    """
    RETURN: bool, True where the id glob 'glob' names the claim at
            'key_tuple' -- or any claim ABOVE the end of it, which brings
            its subtree: a feature is wanted where its own id or any
            proper prefix of it is named.

    A glob without '.', '*', '?', '[' or '{' is a bare key: '**.key'.
    """
    if not _GLOB_CHARS.search(glob) and "." not in glob:
        glob = "**." + glob
    for alternative in brace_alternative_tuple(glob):
        level_tuple = tuple(alternative.split("."))
        for end in range(1, len(key_tuple) + 1):
            if _chain_hit_f(level_tuple, key_tuple[:end]):
                return True
    return False


def full_id_tuple_wanted(relation, glob_tuple):
    """
    RETURN: [0] dict, full id -> True for the glob-free texts of
                'glob_tuple' the feature map resolves: the exact
                features they mean
            [1] tuple of str, the globs that remain
    Raises SelectionError, naming the id, for a published id the map
    retired.
    """
    exact_set, remaining = set(), []
    map_db = {} if relation.feature_map is None else {
        each: target for each, target, _
        in relation.feature_map.entry_tuple}
    for glob in glob_tuple:
        if glob in map_db:
            target = map_db[glob]
            if target is None:
                raise SelectionError(
                    "'--feature %s' names a RETIRED id: the map binds it "
                    "to none, no feature means it any more" % glob)
            exact_set.add(target)
        else:
            remaining.append(glob)
    return exact_set, tuple(remaining)


def _case_set_of(relation, root, wish):
    """
    RETURN: [0] frozenset of (absolute test file, choice), the runs the
                wish's features and keys want
            [1] frozenset of str, every key a feature of the tree carries
    """
    exact_set, glob_tuple = full_id_tuple_wanted(relation, wish.feature_tuple)
    key_tree = None if wish.keys_spec is None \
               else parse_expression(wish.keys_spec)
    case_set, known_set = set(), set()
    for path, each in relation.test_directory_db.items():
        for state in each.state_tuple:
            chain    = relation.chain_tuple(path) + (state.feature.name,)
            full_id  = ".".join(chain)
            key_set  = set(relation.effective_key_tuple(path, state.feature))
            known_set |= key_set
            if wish.feature_tuple:
                named = full_id in exact_set \
                        or any(glob_hit_f(glob, chain)
                               for glob in glob_tuple)
                if not named: continue
            if key_tree is not None and not evaluate_f(key_tree, key_set):
                continue
            for run in state.run_tuple:
                case_set.add((os.path.normpath(
                    os.path.join(root, path, run.test)), run.choice))
    return frozenset(case_set), frozenset(known_set)


def case_set_of(root, wish):
    """
    RETURN: frozenset of (absolute test file, choice), the runs of the
            tree below 'root' that the wish's '-F' and '-k' want --
            empty where none does.

    Raises SelectionError for a retired id, for a key no feature of the
    tree carries (a misspelt key silently selecting nothing is how an
    author comes to believe a set is empty), and for a glob that cannot
    be read.
    """
    root = os.path.abspath(root)
    mark = (root, wish.feature_tuple, wish.keys_spec)
    if mark in _view_db: return _view_db[mark]
    relation = relation_of_tree(root)
    # the globs are read once, so a broken one is refused at the door
    for glob in wish.feature_tuple:
        brace_alternative_tuple(glob)
    case_set, known_set = _case_set_of(relation, root, wish)
    if wish.keys_spec is not None:
        unknown = [name for name in label_name_tuple(
                       parse_expression(wish.keys_spec))
                   if name not in known_set]
        if unknown:
            raise SelectionError(
                "no feature carries the key '%s'; keys that stand: %s"
                % ("', '".join(unknown),
                   ", ".join(sorted(known_set)) or "(none)"))
    _view_db[mark] = case_set
    return case_set
