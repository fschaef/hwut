"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

CST NODES  --  the canonical concrete-syntax tree the engine builds by default.

The engine ALWAYS reduces a parse to a tree of these four frozen nodes, one node
per grammar operator, bottom-up. They are the baseline output; a transformer
overlay (the outer layer's AST_MAP) refines selected rules into typed AST nodes,
but where no transformer is registered, the CST node IS the output. This is a
PRUNED CST: silent terminals contribute nothing, so syntax (punctuation
keywords) is discarded while structure -- which operator matched, which OR
branch, how many repetitions -- is preserved.

Four node kinds mirror the four authoring operators (combinators.py):

    OR_Node    an alternation OR an optional. 'triggered_index' names which
               branch of the alternation matched; 'child' is that branch's
               reduced value. An OPTIONAL is the degenerate two-branch
               alternation '(body | empty)': when the empty branch matched,
               'child' IS the ABSENT sentinel. There is no separate OPT node --
               absence is a STATE of OR_Node, not a node type.
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


class _Absent:
    """The sentinel value an OR_Node.child holds when the empty branch matched.

    A single module-global instance, ABSENT, exported below. It is the value an
    OPTIONAL contributes when it did not fire: 'OR_Node(child=ABSENT)' is "this
    optional was absent". A distinct type (not None) so a genuinely None-valued
    child -- should a transformer ever produce one -- is not mistaken for
    absence. Truthy-falsy: ABSENT is falsey, so 'if node.child:' reads as "the
    optional fired", though an explicit 'node.child is ABSENT' is clearer.
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
class OR_Node:
    """An alternation (or an absent/present optional) and the branch that matched.

    'triggered_index' is the 0-based index of the matched branch within the
    grammar's alternation; 'child' is that branch's reduced value, or ABSENT when
    the node is an optional whose empty branch matched. 'name' is the rule name,
    or None for an inline alternation/optional.
    """
    triggered_index: int
    child: object
    name: object = None


@dataclass(frozen=True)
class SEQ_Node:
    """A sequence; 'children' is the reduced value per surviving grammar position.

    Silent terminals leave no entry, so 'children' is the dense list of values
    the sequence produced -- but each inline operator among the positions is
    itself a CST node held at its stable slot, so presence/absence of an inline
    optional is read OFF that slot's OR_Node, never inferred from list length.
    'name' is the rule name, or None for an inline sequence.
    """
    children: tuple = field(default_factory=tuple)
    name: object = None


@dataclass(frozen=True)
class PLUS_Node:
    """One-or-more: 'items' is the reduced repetitions, guaranteed non-empty.

    'name' is the rule name, or None for an inline PLUS.
    """
    items: tuple = field(default_factory=tuple)
    name: object = None


@dataclass(frozen=True)
class STAR_Node:
    """Zero-or-more: 'items' is the reduced repetitions, possibly empty.

    'name' is the rule name, or None for an inline STAR.
    """
    items: tuple = field(default_factory=tuple)
    name: object = None
