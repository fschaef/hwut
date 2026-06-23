"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

GENERAL AST VOCABULARY  --  the shapes the semantic unit treats generically.

An AST DESCRIBES; it is not the thing it describes. Nodes come from rule
productions; leaves come from terminals. A terminal, in the tree, is therefore
not an object -- it is a description of HOW the object it stands for is
accessed. The way of access varies, and that variation is the only thing the
leaf kinds encode:

    ConstantLeaf    the object is inline here          -> const-fold license
    ReferenceLeaf   reach it by key / navigation       -> symbol-table resolve
    DeclarationLeaf introduces a name                  -> registered, resolved against
    AnonymousLeaf   the object is built in place        -> no lookup
    OpaqueLeaf      embedded-language content           -> oracle, on demand

Beyond leaves, general OPERATOR-SEQUENCE nodes carry associativity as identity:

    LeftFolding     head + mounted STAR of (op, operand) -> left grouping
    RightFolding    same shape                           -> right grouping

A specific grammar (the application, parser/) derives its named constructs and
terminals from these. The semantic unit walks Root and resolves every
ReferenceLeaf against the symbol table WITHOUT knowing the application's
vocabulary -- that is what 'general' buys: one resolution mechanism over all
trees.

The set of leaf kinds is not closed by decree; Leaf is a base and a new access
kind is a new derivation when a terminal needs one.
______________________________________________________________________________
"""
from dataclasses import dataclass, field
from abc         import ABC
from enum        import Enum
from typing      import List


@dataclass(frozen=True)
class Leaf(ABC):
    """A terminal's place in the tree: a DESCRIPTION of how to access the one
    object the terminal stands for.

    'begin' is the absolute source offset of the terminal, so a SourceMap can
    resolve a (line, column) for diagnostics. Subclasses add the access-kind
    specifics; the base fixes only that every leaf has a source position and is
    a description, never the object itself.
    """
    begin: int


class E_ConstantKind(Enum):
    """The lexical kind of a ConstantLeaf, riding from the terminal it was born
    from -- NOT re-derived from the text. The grammar already separates these
    into distinct terminals; this records which one matched.

    INT     an integer literal      (t_re_int:    \\d+)
    FLOAT   a float literal         (t_re_float:  \\d+\\.\\d+)
    STRING  a string literal        (t_re_string, quotes included)
    BOOL    true / false
    """
    INT    = "int"
    FLOAT  = "float"
    STRING = "string"
    BOOL   = "bool"


@dataclass(frozen=True)
class ConstantLeaf(Leaf):
    """A leaf whose object is INLINE: the value is present in the source, no
    lookup needed. Marks the site as eligible for constant reduction.

    'text' is the verbatim lexeme (a number, a string WITH its quotes, or
    'true'/'false'). 'kind' is the lexical kind it was born from
    (E_ConstantKind), carried from the terminal -- not re-classified from text.

    Interpretation (text -> a machine value: int, float, the unescaped string,
    a bool) is DEFERRED to the static layer, which decides against the compared
    side's kind -- common compiler practice (lex records kind + spelling,
    semantic analysis evaluates). 'kind' is what makes the const-fold license
    real: a folding pass knows the lexical class without committing the value.
    """
    text: str
    kind: E_ConstantKind

    @classmethod
    def from_text(cls, text, kind, begin):
        """RETURN: ConstantLeaf, a constant of lexical 'kind' carrying verbatim
                  'text' at source offset 'begin'.

        Pure primitives -- no CST/token type. The caller (the application's
        reduce action) does the CST-shape dispatch (which terminal/arm matched)
        and passes the resolved kind; this factory stays general. Interpretation
        of text to a machine value remains the static layer's job.
        """
        return cls(text=text, kind=kind, begin=begin)


@dataclass(frozen=True)
class ReferenceLeaf(Leaf):
    """A leaf reached BY KEY: a name that requires access to a declared object
    via the symbol table. The unit of resolution.

    'segments' is the dotted name AS WRITTEN, head first
    (('NS','Other','Idle')) -- raw navigation input, immutable so the table may
    key on it. Splitting head into aggregate vs member, and turning the written
    path into a seated access, is resolution's business and lands in the
    resolution slot, NOT here.

    '_access' is that slot: empty at construction (the parser, or the oracle,
    seats only the written name), written ONCE by the semantic pass via
    object.__setattr__. compare=False, repr=False -- the leaf stays pure data
    in identity and print; the slot is a resolution result cached on the
    description, not a field of what was written. The same one-slot,
    written-once pattern carries OpaqueLeaf's lazy reference cache below.
    """
    segments: "tuple[str, ...]"
    _access:  "object|None" = field(default=None, compare=False, repr=False)

    def resolve(self, access):
        """RETURN: None; seats the resolved access onto this leaf.

        Raises nothing. Written once by the semantic pass; a second call
        overwrites silently (re-link replaces wholesale, see RATIONALE).
        """
        object.__setattr__(self, "_access", access)

    @property
    def access(self):
        """RETURN: the seated access object if resolved,
                   None                   else.

        A None return means this leaf has not been through resolution yet; the
        caller distinguishes 'unresolved' from any resolved value.
        """
        return self._access


@dataclass(frozen=True)
class DeclarationLeaf(Leaf):
    """A leaf that INTRODUCES a name: the dual of ReferenceLeaf. Where a
    reference requires access to something declared elsewhere, a declaration is
    the site where that something is declared -- the name the symbol table
    registers and resolves references against.

    'segments' is the introduced dotted name AS WRITTEN, head first, immutable
    so the table may key on it. No resolution slot: a declaration does not
    resolve, it is resolved AGAINST. (Scope/registration data the semantic pass
    needs lives in the symbol table beside the AST, per the AST-never-mutated
    discipline, not on this leaf -- added there when the table is built.)

    Covers both definition names (Mode, State, StateMachine, ModeGroup,
    Namespace, CauseDef, EffectDef, Clockwork) and the import mount point, which
    introduces a binding name rather than referencing one.
    """
    segments: "tuple[str, ...]"


@dataclass(frozen=True)
class AnonymousLeaf(Leaf):
    """A leaf whose object is BUILT IN PLACE: a fresh, unnamed object with no
    lookup and no name to resolve (an inline structure / literal aggregate).

    'value' is the constructed description the application attaches. Carried so
    the semantic unit can walk it without a special case; it is not resolved
    against the symbol table because it names nothing outside itself.
    """
    value: object


@dataclass(frozen=True)
class OpaqueLeaf(Leaf):
    """A leaf standing for OPAQUE CONTENT in an embedded language: the rule
    language does not parse it; an oracle does, on demand.

    'text' is the verbatim span (delimiters included). 'mode' is the span mode
    the grammar attached (an oracle concept, world.span_oracle.SpanMode); only
    the concrete oracle interprets it.

    REFERENCE KIND -- OPEN. The content is referenced BY INLINE TEXT for now.
    This is deliberately one of several possible reference kinds (offset+extent
    into the source, a url, an external handle, ...); a second kind is added as
    a field or derivation when it appears, with no change to the engine, which
    yields a neutral (text, mode, begin) triple regardless. Inline text is NOT
    a closed decision.

    PRODUCTION: the engine yields the neutral triple at a T.opaque position; the
    concrete parser's reduce action builds this leaf. The engine never names
    this type.

    '_references' is the lazy cache: names found inside the opaque text, each a
    ReferenceLeaf (the SAME resolvable leaf the bracket grammar produces, born
    lazily). One compare=False, repr=False slot, written once via
    object.__setattr__; the leaf stays pure data in identity and print.
    """
    text:        str
    mode:        object
    _references: "tuple|None" = field(default=None, compare=False, repr=False)

    @classmethod
    def from_span(cls, span):
        """RETURN: OpaqueLeaf, lifting the engine's neutral span triple.

        The engine yields a neutral (text, mode, begin) span value at an
        opaque-terminal position (it names no language); this is the single
        seam where the concrete parser turns it into this general leaf. 'mode'
        is carried straight across. For a single-terminal rule the factory
        receives the raw span value itself -- there is no operator node to
        unwrap.
        """
        return cls(text=span.text, mode=span.mode, begin=span.begin)

    def get_references(self, oracle):
        """RETURN: tuple[ReferenceLeaf], the names referenced inside this opaque
                   span, begins ABSOLUTE (rebased onto this leaf's position).

        Raises whatever the oracle raises on malformed opaque content or
        infrastructure failure.

        LAZY: computed on the first call via the oracle, then cached. The oracle
        is an ARGUMENT per call -- the leaf never holds a live oracle handle. A
        memoised accessor, not behaviour.
        """
        if self._references is None:
            raw = oracle.collect_references(
                    self.text, 0, len(self.text) - 1, self.mode)
            rebased = tuple(ReferenceLeaf(segments=tuple(r.segments),
                                          begin=r.begin + self.begin)
                            for r in raw)
            object.__setattr__(self, "_references", rebased)
        return self._references


@dataclass(frozen=True)
class LeftFolding(Leaf):
    """A same-precedence operator SEQUENCE that associates LEFT: a head operand
    followed by a mounted repetition of (operator, operand) steps, meaning
    ((head op1 a) op2 b) op3 c ...

    The associativity is the NODE'S IDENTITY, not a downstream convention: a
    LeftFolding means left-grouping by its type, so a consumer cannot mistake
    the grouping of a non-associative operator ('-', '/'). The dual RightFolding
    states right-grouping; a grammar with mixed associativity produces one node
    type per tier.

    'head' is the first operand (a Leaf or node). 'star' is the engine's
    STAR_Node, MOUNTED not copied -- each item an (op_token, operand) pair, in
    source order; the fold character is meaningful only with this foldable
    structure present. Mounting a STAR_Node (a core/parser_generator type)
    depends DOWN the pipeline (core/symbol -> core/parser_generator), the
    permitted direction; it carries no application vocabulary.

    Precedence is carried by the grammar's rule nesting, not here: every step in
    one LeftFolding is the same precedence tier, so the flat mount loses no
    precedence. 'begin' is provenance.
    """
    head:  object
    star:  object             # the mounted STAR_Node; items are (op_tok, operand)
    begin: int


@dataclass(frozen=True)
class RightFolding(Leaf):
    """A same-precedence operator SEQUENCE that associates RIGHT: the dual of
    LeftFolding, meaning head op1 (a op2 (b op3 c ...)). Same shape (head +
    mounted STAR_Node); the type states right-grouping. Not produced by the
    current ladders (all left), provided so a right-associative tier has a home
    without a fold convention.
    """
    head:  object
    star:  object
    begin: int


@dataclass
class Root:
    """The root of an AST tree the semantic unit can walk GENERICALLY: an
    ordered list of top-level items.

    'items' holds the application's top-level constructs in source order. The
    base names no construct kind -- the application (parser/) derives a Root
    (e.g. parser's ModuleRoot) whose items are its own named nodes. A mutable
    container so a parser may append as it goes; the semantic unit only reads.
    """
    items: List = field(default_factory=list)


@dataclass
class MutableBranch:
    """PLACEHOLDER -- not yet designed.

    A general branch base whose role is to be SWITCHED (replaced) during
    semantic analysis: where the AST is otherwise never mutated (decoration
    lives beside it), a MutableBranch is the controlled exception a semantic
    pass may swap out for a refined node. One such base may sit under each CST
    branch kind.

    Intentionally empty for now: noted, not built. Design deferred.
    """
    pass

