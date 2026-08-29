"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE LABEL EXPRESSION -- what '--label' and 'hwut.labels.query'
         state about the sets a run belongs to (disc-8).

    expr := term (('AND' | 'OR') term)*
    term := 'NOT' term | '(' expr ')' | 'all' | <label>

'AND' binds tighter than 'OR'. A ',' is sugar for 'OR', so the short
form '--label mine,yours' and the spoken form '--label "mine OR
yours"' are ONE grammar, parsed in one place. Keywords are UPPER CASE
and RESERVED; 'all' denotes the UNIVERSE of runs and is a keyword,
never an assigned label; 'meta' is the STANDARD label that a bare wish
silences.

No globs on label names, no counts, no arithmetic. A grammar that
grows is a language nobody documents.

THIS MODULE PARSES AND EVALUATES; it does not read the labels file.
The file is 'hwut-root.labels' and its reader and writer are the label
faces' ('services/labels/_file.py'). What the engine needs of the
file's CONTENT arrives as a 'CLabelView', built there, handed down
here -- data flows into the engine, the engine imports nothing back.
______________________________________________________________________________
"""
import os
import re
from dataclasses import dataclass


#  THE RESERVED WORDS. 'AND', 'OR', 'NOT' are the grammar's; 'all' is
#  the universe and never stands on a line; 'meta' is the standard
#  label -- assignable, never 'create'd, silenced by a bare wish.
KEYWORD_TUPLE  = ("AND", "OR", "NOT")
UNIVERSE_NAME  = "all"
STANDARD_LABEL = "meta"

#  What a customer label may look like. Case-sensitive throughout, so
#  'and' in lower case is a legal label without ambiguity.
LABEL_NAME_REGEX = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.\-]*\Z")


class LabelExprError(Exception):
    """An expression the grammar cannot mean: an unclosed bracket, a
    keyword where a label must stand, a word no label may be."""


def reserved_reason(name):
    """
    RETURN: str, why 'name' may not be a customer label, if it may
            not -- a sentence naming the remedy.
            None, where the name is free to be one.
    """
    if name in KEYWORD_TUPLE:
        return "'%s' is the grammar's own word" % name
    if name == UNIVERSE_NAME:
        return "'%s' is the universe of runs -- a keyword, never " \
               "assigned" % UNIVERSE_NAME
    if name == STANDARD_LABEL:
        return "'%s' is the standard label; it always stands and " \
               "'hwut.labels.add' grows it" % STANDARD_LABEL
    if LABEL_NAME_REGEX.match(name) is None:
        return "a label is letters, digits, '_', '-', '.' -- '%s' " \
               "is not" % name
    return None


def parse_expression(text):
    """
    RETURN: tuple, the expression as a tree of nested tuples --
            ('label', <n>), ('all',), ('not', t), ('and', t, t),
            ('or', t, t).

    Raises LabelExprError, naming the place, where the text cannot be
    meant: an unclosed bracket, a keyword where a term must stand, a
    dangling operator, a word no label may be. A ',' reads as 'OR'.
    """
    token_list = _token_list(text)
    if not token_list:
        raise LabelExprError("the expression is empty")
    tree, index = _parse_or(token_list, 0)
    if index != len(token_list):
        raise LabelExprError("'%s' stands after a complete expression"
                             % token_list[index])
    return tree


def label_name_tuple(tree):
    """
    RETURN: tuple[str], every label the tree names, sorted, each once
            -- 'all' excluded, being a keyword, 'meta' included, being
            a label.
    """
    found = set()
    _collect(tree, found)
    return tuple(sorted(found))


def evaluate_f(tree, label_set):
    """
    RETURN: bool, True where a run carrying exactly 'label_set'
            answers the expression.
    """
    kind = tree[0]
    if kind == "all":   return True
    if kind == "label": return tree[1] in label_set
    if kind == "not":   return not evaluate_f(tree[1], label_set)
    if kind == "and":   return evaluate_f(tree[1], label_set) \
                               and evaluate_f(tree[2], label_set)
    if kind == "or":    return evaluate_f(tree[1], label_set) \
                               or evaluate_f(tree[2], label_set)
    raise AssertionError("an expression tree holds no '%s'" % kind)


@dataclass(frozen=True, slots=True)
class CLabelView:
    """What the engine sees of 'hwut-root.labels': WHERE the file's
    ground is, WHAT it assigns, and WHICH labels stand. Built by the
    file's reader ('services/labels/_file.py'), handed down, read
    only.

    'entry_db' maps '(<file>, <choice>)' -- the file path RELATIVE to
    'boundary', '/'-separated, no './' -- to a frozenset of labels.
    The choice-less entry '(<file>, None)' labels EVERY choice of the
    application; a choice's own entry ADDS to it (labels accumulate).
    'defined' holds every label that stands, the standard one always
    among them."""
    boundary: str            # absolute, the directory of the file
    entry_db: dict           # (file, choice|None) -> frozenset
    defined:  frozenset      # every label that stands, 'meta' included

    def silences_f(self):
        """
        RETURN: bool, True where any entry carries the STANDARD label
                -- the one condition under which a wish that asks no
                label does not simply take everything. A tree that
                labels nothing, or labels only its own concerns,
                imposes no silence, and a selection over it must
                behave byte for byte as one with no view at all.
        """
        return any(STANDARD_LABEL in label_set
                   for label_set in self.entry_db.values())

    def label_set_of(self, absolute_path, choice):
        """
        RETURN: frozenset[str], the labels the file assigns to the run
                -- the application's own united with the choice's,
                empty where it assigns none or where the path lies
                outside the boundary.
        """
        relative = os.path.relpath(absolute_path, self.boundary)
        relative = relative.replace(os.sep, "/")
        if relative.startswith("../"): return frozenset()
        found = self.entry_db.get((relative, None), frozenset())
        if choice is not None:
            found = found | self.entry_db.get((relative, choice),
                                              frozenset())
        return found


GLOB_MARK_TUPLE = ("*", "?", "[")


def literal_target_f(text):
    """
    RETURN: bool, True where the target names a run EXACTLY -- no
            glob mark in either member.

    THE LINE THE FRAMEWORK DRAWS TWICE: 'hwut-root.labels' holds
    literal targets only for the same reason a literal target lifts
    the standard label's silence (disc-8). A literal names ONE run
    and is spent as certainty; a glob names a set nobody has seen
    yet, and 'test-*.sh' is how a person writes 'this directory',
    not 'I have considered each of these runs'.
    """
    return not any(mark in text for mark in GLOB_MARK_TUPLE)


def swallowed_warning_tuple(met_set, visible_set):
    """
    RETURN: tuple[str], one warning per glob that MET runs and had
            every one of them silenced -- sorted, the glob named, the
            remedy named.

    A selection may never QUIETLY answer nothing where a person
    stated a target: either it takes what was named, or it says why
    not and how ('--label meta'). The status does not move -- a glob
    is a fact about the tree this morning, and a wish is allowed to
    select nothing (P-9).
    """
    return tuple("WARNING: the glob '%s' met only runs the standard "
                 "label silences -- name a label ('--label %s') to "
                 "reach them" % (text, STANDARD_LABEL)
                 for text in sorted(met_set - visible_set))


def empty_view(boundary):
    """
    RETURN: CLabelView assigning nothing -- what an ABSENT
            'hwut-root.labels' means: no label exists, no silence
            imposed, the tree behaves as one that labels nothing.
    """
    return CLabelView(boundary = boundary,
                      entry_db = {},
                      defined  = frozenset((STANDARD_LABEL,)))


def _token_list(text):
    """
    RETURN: list[str], the expression's tokens -- brackets and commas
            split off, the rest split on blanks.
    """
    spaced = text.replace("(", " ( ").replace(")", " ) ") \
                 .replace(",", " , ")
    return spaced.split()


def _parse_or(token_list, index):
    """
    RETURN: [0] tuple, the 'or'-level tree read from 'index' on.
            [1] int, where the reading stopped.
    """
    tree, index = _parse_and(token_list, index)
    while index < len(token_list) \
          and token_list[index] in ("OR", ","):
        right, index = _parse_and(token_list, index + 1)
        tree = ("or", tree, right)
    return tree, index


def _parse_and(token_list, index):
    """
    RETURN: [0] tuple, the 'and'-level tree read from 'index' on.
            [1] int, where the reading stopped.
    """
    tree, index = _parse_term(token_list, index)
    while index < len(token_list) and token_list[index] == "AND":
        right, index = _parse_term(token_list, index + 1)
        tree = ("and", tree, right)
    return tree, index


def _parse_term(token_list, index):
    """
    RETURN: [0] tuple, one term read from 'index' on -- a negation, a
            bracketed expression, the universe, or a label.
            [1] int, where the reading stopped.

    Raises LabelExprError where no term stands: the text ended, a
    keyword or a stray bracket holds the place, or the word is no
    label.
    """
    if index >= len(token_list):
        raise LabelExprError("the expression ends where a label "
                             "must stand")
    token = token_list[index]
    if token == "NOT":
        tree, index = _parse_term(token_list, index + 1)
        return ("not", tree), index
    if token == "(":
        tree, index = _parse_or(token_list, index + 1)
        if index >= len(token_list) or token_list[index] != ")":
            raise LabelExprError("a '(' stands without its ')'")
        return tree, index + 1
    if token in ("AND", "OR", ")", ","):
        raise LabelExprError("'%s' stands where a label must stand"
                             % token)
    if token == UNIVERSE_NAME:
        return ("all",), index + 1
    if LABEL_NAME_REGEX.match(token) is None:
        raise LabelExprError("a label is letters, digits, '_', '-', "
                             "'.' -- '%s' is not" % token)
    return ("label", token), index + 1


def _collect(tree, found):
    """
    RETURN: None. Gathers the tree's label names into 'found'.
    """
    kind = tree[0]
    if   kind == "label":         found.add(tree[1])
    elif kind == "not":           _collect(tree[1], found)
    elif kind in ("and", "or"):
        _collect(tree[1], found)
        _collect(tree[2], found)
