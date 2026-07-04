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
OpaqueTerminals (opaque spans), or the already-reduced CST/AST nodes
of child rules. The nodes are frozen dataclasses, so a consumer may hold and
compare them freely; they hold REFERENCES to already-reduced children (bottom-up
reduction finishes a child before its parent is built), never copies.
______________________________________________________________________________
"""
from dataclasses import dataclass, field

from .operator_interface import (OR_Interface, OPT_Interface, SEQ_Interface,
                                  PLUS_Interface, STAR_Interface)


@dataclass(frozen=True)
class OpaqueTerminal:
    """A captured OPAQUE terminal: the engine's result of absorbing a '{ ... }'
    span. The opaque counterpart to a Token -- where a Token captures an
    ordinary terminal, this captures one the rule language does not parse.

    'text' is the span content the finder reported (delimiters included). The
    finder API is minimalist: it reports raw content -- text now, possibly an
    offset+length or a url later -- and this terminal carries whatever it
    reported, opening OpaqueLeaf's reference-kind openness at the finder
    boundary without coupling the engine to any one form.

    'begin' is provenance: the absolute source offset, as Token.begin is.

    'mode' is the terminal's span-mode ROLE: which way the oracle parses the
    content (e.g. EXPRESSION vs STATEMENT_BLOCK). It rides on the terminal
    DEFINITION (T.opaque(mode)), distinct from the positional role hint (D-18)
    that the reduce-time router reads -- different attachment point, different
    consumer. Kept language-neutral: any object exposing qualified_name()/name.

    The engine builds THIS (its own type); the reduce action makes ast.OpaqueLeaf
    from it. No world type is named by the engine.
    """
    text:  str
    begin: int
    mode:  object


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
    'role' is the advisory role string the matched branch carried (D-19), or
    None for an untagged branch -- the role-keyed routing address parallel to
    SEQ_Node's per-position roles. 'name' is the rule name, or None for an
    inline alternation. 'begin' is the construct's start offset (the frame's
    begin), so a transformer can stamp an AST node's begin without a child token.
    """
    triggered_index: int
    child: object
    role: object = None
    name: object = None
    begin: int = 0

    @property
    def or_child(self):
        """RETURN: object, the matched branch's reduced value (ABSENT if none)."""
        return self.child

    def route_key(self, address):
        """RETURN: bool, whether this OR_Node's fired branch matches 'address'.

        An int 'address' matches the fired branch's 'triggered_index'; a str
        'address' matches its 'role'. The routing primitive an OrMap uses to
        pick the factory for the branch that actually fired (D-19).
        """
        if isinstance(address, int):
            return address == self.triggered_index
        return address == self.role


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

    def or_else(self, default):
        """RETURN: object, the body's value if the optional fired, else 'default'.

        The present->child / absent->default read a SEQ factory does on a child
        optional slot, named so the call site states intent ('params =
        node[1].or_else([])') instead of re-deriving 'present'/'child' (D-19).
        An optional that FIRED over an all-silent body is present with
        child=ABSENT; callers wanting that distinction read '.present' directly.
        """
        return self.child if self.present else default


@dataclass(frozen=True)
class SEQ_Node(SEQ_Interface):
    """A sequence; 'children' is the reduced value per surviving grammar position.

    Silent terminals leave no entry, so 'children' is the dense list of values
    the sequence produced -- but each inline operator among the positions is
    itself a CST node held at its stable slot, so presence/absence of an inline
    optional is read OFF that slot's OPT_Node, never inferred from list length.
    'name' is the rule name, or None for an inline sequence.

    'roles' (D-18) rides PARALLEL to 'children': one entry per surviving value,
    the advisory role string a position carried ('<type(key)>' -> "key") or
    None for an untagged position (including every captured discriminant like
    '<', '>', 'dict'). Positional access 'children[i]' is unchanged; role access
    'node["key"]' is a SECOND index over the same tuple, immune to captured-
    terminal index drift -- a factory reads the slot it means by name, and an
    inserted or removed silent/captured terminal no longer shifts it.
    """
    children: tuple = field(default_factory=tuple)
    roles:    tuple = field(default_factory=tuple)
    name: object = None
    begin: int = 0

    def seq_children(self):
        """RETURN: tuple, the sequence's matched contents in grammar order."""
        return self.children

    def __getitem__(self, address):
        """RETURN: object, the child at 'address' -- positional, role-asserted, or role-searched.

        Three address forms, ONE operator:
          int i            POSITIONAL. 'self.children[i]', raising IndexError out
                           of range as the tuple does; a missing slot is a
                           structural bug worth surfacing. The default address:
                           position is the natural identity of a sequence, and
                           captured-terminal index drift is cured at source by
                           SILENCING non-value tokens, not by routing around them.
          (int i, str r)   POSITIONAL with a ROLE ASSERTION. Returns children[i]
                           and ASSERTS slot i carried role r in the grammar; on
                           mismatch raises AssertionError naming expected vs found,
                           at the read, in grammar vocabulary. A drift smoke-
                           detector: an inserted/removed token that shoves a
                           different-role node into slot i fails LOUDLY here rather
                           than silently corrupting the AST downstream. It catches
                           the common, coarse drift (role-at-slot changed) and the
                           same-TYPE transposition a type check misses, since
                           distinct positions carry distinct roles even when their
                           node classes coincide. It does NOT catch slots sharing a
                           role, untagged slots (role None), or drift one level
                           inside an OPT_Node -- 'sometimes', by design; the GOOD
                           suite stays the total guard. Position still addresses;
                           the role only VERIFIES -- so a role may repeat across
                           slots (uniqueness is irrelevant to an assertion that
                           names its own index).
          str r            ROLE SEARCH. The single surviving child whose position
                           carried role r, or None if none does (a wrong/absent
                           role reads None, never raises -- D-19). Retained ONLY
                           for the forced case where a value-bearing terminal
                           cannot be silenced because its spelling is shared with a
                           rule that reads its text (the container-type angle
                           bracket '<'/'>', shared with the comparison operators):
                           there the scaffolding stays captured and DictType/
                           ListType locate key/value/element by role. Lenient on
                           miss (None), OPPOSITE the assertion form's strict raise
                           -- a search finding nothing is a legitimate absence; an
                           assertion failing is a structural lie.
        An ABSENT OPTIONAL is NOT a None return -- the optional position survives
        as an OPT_Node(present=False) at its slot, returned normally; its absence
        is read off '.present', never conflated with a missing-role None.
        """
        if isinstance(address, int):
            return self.children[address]
        if isinstance(address, tuple):
            index, role = address
            child = self.children[index]
            found = self.roles[index]
            if found != role:
                raise AssertionError(
                    "role assertion failed at slot %d: expected %r, found %r"
                    % (index, role, found))
            return child
        if not isinstance(address, str):
            raise TypeError("SEQ_Node index must be int (positional), "
                            "(int, str) (positional + role assertion), or str "
                            "(role search); got %r" % type(address).__name__)
        hits = [v for v, r in zip(self.children, self.roles) if r == address]
        if not hits:
            return None
        if len(hits) > 1:
            raise ValueError("role %r is ambiguous: %d positions carry it"
                             % (address, len(hits)))
        return hits[0]


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
