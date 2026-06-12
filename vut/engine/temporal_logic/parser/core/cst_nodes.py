"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

CST NODES  --  the canonical concrete-syntax tree the engine builds by default.

The engine ALWAYS reduces a parse to a tree of these five frozen nodes, one node
per grammar operator, bottom-up. They are the baseline output; a transformer
overlay (the outer layer's AST_MAP) refines selected rules into typed AST nodes,
but where no transformer is registered, the CST node IS the output. This is a
PRUNED CST: silent terminals contribute nothing, so syntax (punctuation
keywords) is discarded while structure -- which operator matched, which OR
branch, how many repetitions -- is preserved.

Five node kinds mirror the five authoring operators (combinators.py):

    OR_Node    an alternation. 'triggered_index' names which branch matched;
               'child' is that branch's reduced value, or ABSENT when the
               matched branch produced no surviving value (an all-silent
               branch).
    OPT_Node   an optional. 'present' is True iff the optional fired; 'child'
               is the body's surviving reduced value, or ABSENT when none
               survived (not fired, or fired over an all-silent body).
               Presence is a STATE of the node, marked on it, never inferred
               from a missing slot downstream.
    SEQ_Node   a sequence: 'children' holds one reduced value per surviving
               grammar position (silent terminals leave no entry; inline
               operators among the positions are themselves CST nodes at their
               stable slot).
    PLUS_Node  one-or-more: 'items' is the reduced repetitions, never empty.
    STAR_Node  zero-or-more: 'items' is the reduced repetitions, possibly empty.

NAME. Every node carries 'name': the producing GRAMMAR rule's name when the node
was built at a rule-reduce site, or None when the node was built from an INLINE
operator inside a rule body (the STAR((",", "<arg>")) inside <arg-list>, the
["&", "<guard>"] inside <cause>). A transformer reaching DOWN into an
untransformed child branches on that child's 'name' to interpret it; an
anonymous (name=None) inline node is interpreted by the enclosing rule's
transformer from its own positional knowledge, so it needs no name of its own.

Leaf values inside children/items/child are Tokens (captured terminals),
SpanResults (opaque spans, span_oracle.py), or the already-reduced CST/AST nodes
of child rules. The nodes are frozen dataclasses, so a consumer may hold and
compare them freely; they hold REFERENCES to already-reduced children (bottom-up
reduction finishes a child before its parent is built), never copies.
______________________________________________________________________________
"""
from dataclasses import dataclass, field

from .operator_interface import (OR_Interface, OPT_Interface, SEQ_Interface,
                                  PLUS_Interface, STAR_Interface)


class _Absent:
    """The sentinel a node's 'child' holds when a position produced no value.

    A single module-global instance, ABSENT, exported below. OPT_Node.child IS
    ABSENT when the optional did not fire OR fired over an all-silent body
    (read 'present' for which); OR_Node.child is ABSENT when the matched
    branch was all-silent. A distinct type (not None) so a genuinely
    None-valued child -- should a transformer ever produce one -- is not
    mistaken for absence. Truthy-falsy: ABSENT is falsey, so 'if node.child:'
    reads as "the position produced a value".
    """
    __slots__ = ()
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self):
        return "ABSENT"

    def __bool__(self):
        return False


ABSENT = _Absent()


@dataclass(frozen=True)
class OR_Node(OR_Interface):
    """An alternation and the branch that matched.

    'triggered_index' is the 0-based index of the matched branch within the
    grammar's alternation; 'child' is that branch's reduced value, or ABSENT
    when the matched branch produced no surviving value (an all-silent branch).
    'name' is the rule name, or None for an inline alternation. 'begin' is the
    construct's start offset (the frame's begin), so a transformer can stamp an
    AST node's begin without a child token.
    """
    triggered_index: int
    child: object
    name: object = None
    begin: int = 0

    @property
    def or_child(self):
        """RETURN: object, the matched branch's reduced value (ABSENT if none)."""
        return self.child


@dataclass(frozen=True)
class OPT_Node(OPT_Interface):
    """An optional position and whether it fired.

    'present' is True iff the optional fired. 'child' is the body's surviving
    reduced value, or ABSENT when none survived -- exactly OR_Node's child
    semantics, so a FIRED optional over an all-silent body is present=True,
    child=ABSENT, distinguishable from absent. Presence is read off 'present',
    never inferred from the parent's child count -- the parent SEQ keeps a
    stable slot either way. 'name' is the rule name, or None for an inline
    optional. 'begin' is the construct's start offset (the frame's begin).
    """
    present: bool
    child: object
    name: object = None
    begin: int = 0


@dataclass(frozen=True)
class SEQ_Node(SEQ_Interface):
    """A sequence; 'children' is the reduced value per surviving grammar position.

    Silent terminals leave no entry, so 'children' is the dense list of values
    the sequence produced -- but each inline operator among the positions is
    itself a CST node held at its stable slot, so presence/absence of an inline
    optional is read OFF that slot's OPT_Node, never inferred from list length.
    'name' is the rule name, or None for an inline sequence.
    """
    children: tuple = field(default_factory=tuple)
    name: object = None
    begin: int = 0

    def seq_children(self):
        """RETURN: tuple, the sequence's matched contents in grammar order."""
        return self.children


@dataclass(frozen=True)
class PLUS_Node(PLUS_Interface):
    """One-or-more: 'items' is the reduced repetitions, guaranteed non-empty.

    'name' is the rule name, or None for an inline PLUS.
    """
    items: tuple = field(default_factory=tuple)
    name: object = None
    begin: int = 0

    def rep_items(self):
        """RETURN: tuple, the matched repetitions (non-empty for PLUS)."""
        return self.items


@dataclass(frozen=True)
class STAR_Node(STAR_Interface):
    """Zero-or-more: 'items' is the reduced repetitions, possibly empty.

    'name' is the rule name, or None for an inline STAR.
    """
    items: tuple = field(default_factory=tuple)
    name: object = None
    begin: int = 0

    def rep_items(self):
        """RETURN: tuple, the matched repetitions (possibly empty for STAR)."""
        return self.items
