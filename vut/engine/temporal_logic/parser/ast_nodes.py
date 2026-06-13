"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

ABSTRACT SYNTAX TREE NODES

Pure data structures for the rule-file grammar (see GRAMMAR in grammar.py). Every node
carries 'begin', the absolute source offset where the construct starts, so a
SourceMap can resolve a 1-based (line, column) for error reporting and for the
Source2TargetLocationMapper during code generation. Nodes hold no behaviour;
the parser builds them and the validator/transpiler consume them.

Opaque code spans are stored verbatim (braces included) together with the
span MODE under which the parser handed them to the oracle (OpaqueCode), so
the code generator can re-frame each correctly. The parser names no embedded
language: everything span-related speaks 'oracle' (core.span_oracle).
______________________________________________________________________________
"""
from dataclasses import dataclass, field
from enum        import Enum
from typing      import List, Optional

from .core.span_oracle        import Reference
from .core.operator_interface import (OR_Interface, SEQ_Interface,
                                      PLUS_Interface, STAR_Interface)


from abc import ABC


class E_ArgKind(Enum):
    """The value shape of an Arg (see Arg.kind).

    LITERAL  a NUMBER/STRING/true/false lexeme carried as text.
    LUAU     an opaque EXPRESSION span (an OpaqueCode node).
    NAME     a <name-dotted> reference carried as its segment list -- a bare
             word ('dict'), a variable, a struct member ('tracker.pos.x'), or
             a self-binding member ('e.target'); resolved in pass 2 (D-24).
    """
    LITERAL = 0
    LUAU    = 1
    NAME    = 2


class TopLevel(OR_Interface):
    """Abstract base for the constructs that may appear at rule-file top level.

    Namespace, Import, Causality, Mode, ModeGroup, StateMachine, Agent, the
    four declaration nodes (ReactorDecl, StructDecl, ContainerDecl, VariableDef),
    EventDef, ClockDef, CauseDef and EffectDef derive from it, so
    'RuleFile.items' is typed as list[TopLevel] and only these node kinds are
    admissible there. A Namespace nests further TopLevel items. Carries no
    fields; the concrete nodes hold their own.
    """
    pass

@dataclass(frozen=True)
class OpaqueCode:
    """One opaque code span: its verbatim text, mode, and source offset.

    'text' is the lexeme including the enclosing braces. 'mode' is the span
    mode the grammar attached to the opaque terminal (a core SpanMode --
    CONDITION, EXPRESSION, LVALUE, STATEMENT_BLOCK); the concrete oracle is
    the only party that interprets it. The node names no embedded language.
    """
    text:  str
    mode:  object             # core.span_oracle.SpanMode
    begin: int
    _references: "tuple|None" = field(default=None, compare=False, repr=False)

    @classmethod
    def from_span(cls, span):
        """RETURN: OpaqueCode, wrapping an engine SpanResult.

        The engine yields a neutral core.span_oracle.SpanResult at an
        opaque-span position (it knows no language); this is the single seam
        where the rule language turns it into its own node. SpanResult.mode is
        carried straight onto 'mode'. For the <guard-luau> rule (a
        single-terminal rule) the factory receives the raw SpanResult itself
        -- there is no operator node to unwrap.
        """
        return cls(text=span.text, mode=span.mode, begin=span.begin)

    def get_references(self, oracle):
        """RETURN: tuple[Reference], the names referenced inside this span;
        begins ABSOLUTE (rebased onto this node's source position).

        Raises SpanSyntaxError / SpanOracleError from the oracle.

        LAZY: computed on the first call via the oracle, then cached. The
        oracle is an ARGUMENT per call -- the node never holds an oracle
        handle (no live subprocess reference inside pure data). The cache is
        one compare=False, repr=False slot written once through
        object.__setattr__: the node stays pure data in identity and print;
        this method is a memoised accessor, not behaviour.
        """
        if self._references is None:
            raw = oracle.collect_references(
                    self.text, 0, len(self.text) - 1, self.mode)
            rebased = tuple(Reference(segments=r.segments,
                                      begin=r.begin + self.begin)
                            for r in raw)
            object.__setattr__(self, "_references", rebased)
        return self._references


@dataclass(frozen=True)
class Trigger:
    """A cause trigger: an event name or a system keyword (ANY/BEGIN/END/CHANGE).

    'name' is the <name-dotted> segment list of the triggering event; for a
    system trigger it is the single keyword segment. 'is_keyword' True marks
    the system triggers, distinguishing 'END' the system event from a user
    event that happens to be spelled END elsewhere. Constructed by the
    cause-system / cause-named builders (ast_map), not by a rule of its own.
    """
    name:       "list[str]"   # name-dotted segments; [keyword] for system
    is_keyword: bool
    begin:      int


# --- Bracket-condition algebra ('& [ ... ]') ---------------------------------
# A transparent, engine-inspectable alternative to an opaque CONDITION guard: a
# boolean combination ('and'/'or'/'not', parenthesisable) of comparisons over
# the triggering event's members. Members are leading-dot, single-level
# ('.ip_adr' == the 'ip_adr' member of the event that fired). The tree is built
# directly by the parser, so the static layer can validate member references and
# comparisons instead of treating the guard as opaque text.

@dataclass(frozen=True)
class BoolRef:
    """A bare boolean reference standing as a condition: '[ GHOSTS_AT_HOME ]'.

    A <cond-term> WITHOUT a comparison tail: 'name' is the <name-dotted>
    segment list, equivalent to a '== true' comparison. That the reference
    resolves to kind bool is a pass-2 check (F-5). Constructed by the
    cond-term builder (ast_map).
    """
    name:  "list[str]"        # name-dotted segments
    begin: int


@dataclass(frozen=True)
class Literal:
    """A number or string literal operand in a comparison.

    'text' is the verbatim lexeme (a number, a string WITH its quotes, or
    'true'/'false'); the static layer interprets it against the compared
    side's kind.
    """
    text:  str
    begin: int

    @classmethod
    def from_token(cls, tok):
        """RETURN: Literal, wrapping a number/string/true/false token."""
        return cls(text=tok.text, begin=tok.begin)


@dataclass(frozen=True)
class Comparison:
    """A single comparison: '<name-dotted> <op-cmp> <operand-cond>'.

    'op' is one of '>=', '<=', '==', '!=', '>', '<' (verbatim). 'left' is a
    <name-dotted> segment list; 'right' is a segment list or a Literal -- both
    sides admit names symmetrically, literals stand only on the right. That a
    side resolves to a built-in scalar is a pass-2 check (F-5). Constructed by
    the cond-term builder (ast_map).
    """
    left:  "list[str]"       # name-dotted segments
    op:    str
    right: "object"          # list[str] | Literal
    begin: int


@dataclass(frozen=True)
class Not(SEQ_Interface):
    """A negated condition: 'not <cond-atom>'."""
    operand: "object"        # Comparison | Not | BoolOp
    begin:   int

    @classmethod
    def from_seq(cls, node):
        """RETURN: Not | <cond-atom>, from the <not-cond> SEQ_Node.

        children = (opt_not, atom): the inline optional 'not' is an OPT_Node at
        a STABLE slot -- 'present' True means 'not' was written. No counting.
        A plain (un-negated) atom is forwarded unchanged.
        """
        opt_not, atom = node.children
        if opt_not.present:
            return cls(operand=atom, begin=node.begin)
        return atom


@dataclass(frozen=True)
class BoolOp(SEQ_Interface):
    """An 'and'/'or' chain of two or more operands.

    'op' is 'and' or 'or'. 'operands' are the flattened terms at this precedence
    level (left-associative, but associativity is irrelevant for and/or). A
    single-operand level is collapsed by the builder, so a BoolOp always holds at
    least two operands.
    """
    op:       str            # 'and' | 'or'
    operands: List["object"]
    begin:    int

    @classmethod
    def _from_level(cls, node, op):
        """RETURN: BoolOp | operand, one precedence level, collapsed when trivial.

        children = (first, STAR(('kw', operand))): the head operand, then the
        repetition -- each item an anonymous SEQ whose single survivor is the
        next operand (the 'and'/'or' keyword is silent). One operand forwards
        unchanged; two-or-more become one BoolOp carrying 'op'.
        """
        first    = node.children[0]
        rest     = [s.children[0] for s in node.children[1].items]
        operands = [first] + rest
        if len(operands) == 1:
            return first
        return cls(op=op, operands=operands, begin=first.begin)

    @classmethod
    def from_cond_and(cls, node):
        """RETURN: BoolOp('and') | operand, the <cond-and> precedence level."""
        return cls._from_level(node, "and")

    @classmethod
    def from_cond(cls, node):
        """RETURN: BoolOp('or') | operand, the <cond> level ('or', lowest)."""
        return cls._from_level(node, "or")


@dataclass(frozen=True)
class Condition(SEQ_Interface):
    """The root of a bracket guard '[ ... ]'.

    'expr' is the top boolean expression (a BoolOp, Not, or Comparison). Wrapping
    it in a named root keeps a guard's two forms -- opaque span vs. bracket
    condition -- as two distinct, type-distinguishable node kinds on Cause.guard.
    """
    expr:  "object"
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: Condition, the root of a '[ ... ]' bracket guard.

        children = (expr,): the single top boolean expression ('[' / ']' are
        silent). The wrapper keeps the two guard forms (opaque span vs bracket
        condition) type-distinguishable on Cause.guard.
        """
        return cls(expr=node.children[0], begin=node.begin)


@dataclass(frozen=True)
class Cause(OR_Interface):
    """A cause: a trigger with an optional guard.

    'guard' is the condition gating the trigger, or None when absent. It is
    either an opaque CONDITION span (the '& { ... }' form) or a Condition tree (the
    '& [ ... ]' bracket form); both express "the event fired AND this holds".
    Built by the cause-system builder (system keyword trigger) and by the
    cause-named builder for the paren-less branch (inline named trigger); the
    paren branch builds a CauseRef instead -- the parens decide (D-26).
    """
    trigger: Trigger
    guard:   "Optional[object]"   # OpaqueCode | Condition | None
    begin:   int


@dataclass(frozen=True)
class Arg(OR_Interface):
    """One argument of an event-spec, mode-arming, or spawn: optional name, value.

    'name' is the keyword-argument name when written 'name = value', else None
    (a positional argument). Named arguments may follow positional ones; whether
    a given site accepts a name, and binding correctness, are a semantic-layer
    concern, not a parse error.

    'value' is the rvalue, one of three shapes discriminated by 'kind':
      - E_ArgKind.LITERAL  : a NUMBER/STRING/true/false lexeme as text (str).
      - E_ArgKind.LUAU     : an opaque EXPRESSION span (an OpaqueCode node).
      - E_ArgKind.NAME     : a <name-dotted> segment list (list[str]) the
                             static layer resolves without opening the span --
                             'e.target', 'TIMEOUT', 'dict', 'tracker.pos.x'.
    """
    name:  Optional[str]
    value: object            # str (literal) | OpaqueCode | list[str]
    kind:  "E_ArgKind"
    begin: int

    @classmethod
    def _classify(cls, value, name, begin):
        """RETURN: Arg, classifying 'value' into its E_ArgKind.

        A segment list is a NAME; an opaque SpanResult becomes an OpaqueCode node
        (LUAU); a value-bearing Token (or bare str) is carried as text
        (LITERAL).
        """
        from .core.span_oracle import SpanResult
        if isinstance(value, list):
            return cls(name=name, value=value, kind=E_ArgKind.NAME, begin=begin)
        if isinstance(value, SpanResult):
            return cls(name=name, value=OpaqueCode.from_span(value),
                       kind=E_ArgKind.LUAU, begin=begin)
        text = value if isinstance(value, str) else value.text
        return cls(name=name, value=text, kind=E_ArgKind.LITERAL, begin=begin)

    @classmethod
    def from_or(cls, node):
        """RETURN: Arg, from the <arg> OR_Node (the canonical LL(2) construct).

        Branch 0: positional -- the child is the rvalue, name None. Branch 1:
        named -- the child is the anonymous SEQ (id_tok, rvalue), '=' silent.
        Dispatch by triggered_index, never by shape.
        """
        if node.triggered_index == 1:
            id_tok, rvalue = node.child.children
            return cls._classify(rvalue, name=id_tok.text, begin=node.begin)
        return cls._classify(node.child, name=None, begin=node.begin)


@dataclass(frozen=True)
class EventSpec:
    """An event emission effect: 'name(args)'.

    Built by the effect-named builder (ast_map) when the parens are present;
    a bare name builds an EffectRef instead -- the parens decide (D-26).
    """
    name:  "list[str]"        # name-dotted segments
    args:  List[Arg]
    begin: int


@dataclass(frozen=True)
class ModeArming(SEQ_Interface):
    """A mode-arming effect: 'arm: name(args)'."""
    name:  "list[str]"        # dotted-name segments
    args:  List[Arg]
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: ModeArming -- children = (dotted_name, args_list); 'arm:' silent."""
        name, args = node.children
        return cls(name=name, args=args, begin=node.begin)


@dataclass(frozen=True)
class Spawn(SEQ_Interface):
    """An aggregate-spawning effect: 'spawn: name (args) [ in: C [ via: <rvalue> ] ]'.

    Targets a <mode-group> or <state-machine> type. One shape with one nested
    optional modifier chain:
      - 'args' is the instantiation argument list; the parentheses are MANDATORY
        (a bare 'spawn: name' is rejected by the grammar). 'args' is empty when the
        type takes none ('spawn: name()').
      - 'in_container' names a declared container ('+! x in: C') the fresh
        instance is caught by, or None for the per-kind default container;
        resolved in pass 2 to an 'is: container' declaration.
      - 'via' is the optional key the container holds the instance under (a
        dict container's key): an rvalue normalised to a positional Arg
        (LITERAL / NAME / LUAU), or None. Legal only inside 'in:' -- the
        grammar nests it so (D-25).
    'has_parens' is now always True for a parsed node (the parens are mandatory);
    it is retained for the builder and downstream and no longer discriminates a
    shape.
    """
    name:        "list[str]"  # name-dotted segments
    args:        List[Arg]
    has_parens:  bool
    in_container: "Optional[list[str]]"  # name-dotted segments, or None
    via:         Optional["Arg"]
    begin:       int

    @classmethod
    def from_seq(cls, node):
        """RETURN: Spawn, 'spawn: name (args) [ in: C [ via: <rvalue> ] ]'.

        children = (name, args, opt_in): the trailing options are NESTED stable
        OPT_Node slots mirroring the grammar's nested optionals -- opt_in
        present yields the anonymous SEQ (container_name, opt_via); opt_via
        present yields the anonymous one-survivor SEQ around the rvalue,
        normalised to an Arg through the one classifier (Arg._classify).
        """
        name, args, opt_in = node.children
        in_container = None
        via          = None
        if opt_in.present:
            seq          = opt_in.child
            in_container = seq.children[0]
            opt_via      = seq.children[1]
            if opt_via.present:
                rvalue = opt_via.child.children[0]
                via    = Arg._classify(rvalue, name=None, begin=node.begin)
        return cls(name=name, args=args, has_parens=True,
                   in_container=in_container, via=via,
                   begin=node.begin)


@dataclass(frozen=True)
class Unspawn(SEQ_Interface):
    """An existence-ending effect: 'unspawn: name'.

    'name' references a spawned aggregate by bare or dotted name. Ending an
    existence runs the instance's 'deinit' and releases it from its container.
    Pass-2 validation enforces that the target resolves to an existing
    instance; the grammar accepts any dotted name.
    """
    name:  "list[str]"        # dotted-name segments
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: Unspawn, 'unspawn: name' -- children = (dotted_name,)."""
        return cls(name=node.children[0], begin=node.begin)


@dataclass(frozen=True)
class ReportString:
    """A report-string effect: an interpolated '\"...\"' line."""
    text:  str
    begin: int

    @classmethod
    def from_token(cls, tok):
        """RETURN: ReportString, from the matched STRING token (single-terminal
        rule: the factory receives the raw Token, no operator node)."""
        return cls(text=tok.text, begin=tok.begin)


@dataclass(frozen=True)
class Mutation:
    """A mutation effect: a STATEMENT_BLOCK opaque span after '=>'."""
    body:  OpaqueCode
    begin: int

    @classmethod
    def from_span(cls, span):
        """RETURN: Mutation, wrapping the STATEMENT_BLOCK span (single-terminal
        rule: the factory receives the raw SpanResult)."""
        body = OpaqueCode.from_span(span)
        return cls(body=body, begin=body.begin)


@dataclass(frozen=True)
class InitBlock(SEQ_Interface):
    """An 'init { ... }' member: its STATEMENT_BLOCK body.

    A distinct type (vs DeinitBlock) so a mode/state-machine assembler can sort
    interleaved members by kind rather than by source position.
    """
    body:  OpaqueCode
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: InitBlock -- children = (span,), the STATEMENT_BLOCK body
        wrapped into the rule language's own OpaqueCode node."""
        body = OpaqueCode.from_span(node.children[0])
        return cls(body=body, begin=body.begin)


@dataclass(frozen=True)
class DeinitBlock(SEQ_Interface):
    """A 'deinit { ... }' member: its STATEMENT_BLOCK body. See InitBlock."""
    body:  OpaqueCode
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: DeinitBlock -- children = (span,), the STATEMENT_BLOCK body
        wrapped into the rule language's own OpaqueCode node."""
        body = OpaqueCode.from_span(node.children[0])
        return cls(body=body, begin=body.begin)


@dataclass(frozen=True)
class Causality(SEQ_Interface, TopLevel):
    """A full rule: 'on <cause> (=> <effect>)+'.

    'effects' holds the ordered effect nodes (EventSpec, EffectRef, ModeArming,
    Spawn, Unspawn, ReportString, Mutation).
    """
    cause:   Cause
    effects: List[object]
    begin:   int

    @classmethod
    def from_seq(cls, node):
        """RETURN: Causality -- children = (Cause, PLUS(('=>', effect)))."""
        cause   = node.children[0]
        effects = [s.children[0] for s in node.children[1].items]
        return cls(cause=cause, effects=effects, begin=node.begin)


@dataclass(frozen=True)
class ArgDecl(SEQ_Interface):
    """One parameter declaration: 'member : type'.

    'type' is the verbatim type word -- a built-in keyword ('int', 'float',
    'string', 'bool'), a struct name, or a class name; which it is, is a pass-2
    resolution.
    """
    member: str
    type:   str
    begin:  int

    @classmethod
    def from_seq(cls, node):
        """RETURN: ArgDecl, one 'member: type' -- children = (name_colon, type_or).

        The member name carries a glued trailing ':' (NAME_COLON), stripped
        here. The type slot is the inline OR (bare id | built-in keyword); its
        child is the token either way.
        """
        member_tok, type_or = node.children
        return cls(member=member_tok.text[:-1], type=type_or.child.text,
                   begin=member_tok.begin)


@dataclass(frozen=True)
class Mode(SEQ_Interface, TopLevel):
    """A mode definition with its members and mandatory 'until' causes.

    'init'/'deinit' are STATEMENT_BLOCK OpaqueCode spans or None. 'causalities' are
    the member rules. 'untils' are the closing causes (one or more).
    """
    name:        "list[str]"  # dotted-name segments
    params:      List[ArgDecl]
    init:        Optional[OpaqueCode]
    deinit:      Optional[OpaqueCode]
    causalities: List[Causality]
    untils:      List[Cause]
    begin:       int

    @classmethod
    def from_seq(cls, node):
        """RETURN: Mode -- children = (signature, PLUS(members), PLUS(untils)).

        Members come off their PLUS slot directly; each until item is the
        anonymous one-survivor SEQ around its Cause ('until:' is silent). The
        old trailing-run split is gone: the grammar slots are explicit.
        """
        name, params = node.children[0]
        members      = node.children[1].items
        untils       = [s.children[0] for s in node.children[2].items]
        init = deinit = None
        causalities = []
        for m in members:
            match m:
                case InitBlock():   init = m.body
                case DeinitBlock(): deinit = m.body
                case Causality():   causalities.append(m)
        return cls(name=name, params=params, init=init, deinit=deinit,
                   causalities=causalities, untils=untils, begin=node.begin)


@dataclass(frozen=True)
class State(SEQ_Interface):
    """A state: a mode living in a state machine.

    Same body shape as Mode. 'untils' are the trailing 'until' causes (now
    optional -- possibly empty); the block is terminated structurally by the
    next state-machine element or 'end', not by a closer keyword. Not a
    TopLevel: a state appears only inside a state-machine.
    """
    name:        "list[str]"  # dotted-name segments
    params:      List[ArgDecl]
    init:        Optional[OpaqueCode]
    deinit:      Optional[OpaqueCode]
    causalities: List[Causality]
    untils:      List[Cause]
    begin:       int

    @classmethod
    def from_seq(cls, node):
        """RETURN: State -- children = (signature, STAR(members), STAR(untils)).

        Same shape as Mode.from_seq with zero-or-more slots.
        """
        name, params = node.children[0]
        members      = node.children[1].items
        untils       = [s.children[0] for s in node.children[2].items]
        init = deinit = None
        causalities = []
        for m in members:
            match m:
                case InitBlock():   init = m.body
                case DeinitBlock(): deinit = m.body
                case Causality():   causalities.append(m)
        return cls(name=name, params=params, init=init, deinit=deinit,
                   causalities=causalities, untils=untils, begin=node.begin)


@dataclass(frozen=True)
class HasRef(SEQ_Interface):
    """A 'has: <ref-member>' element pulling in a member defined elsewhere.

    'name' is the <ref-member> head as a segment list -- bare ('GLOW'),
    qualified ('SM.Idle'), or crossing namespaces and mounts ('NS.Other.Idle').
    'is_void' True marks a trailing '.VOID', naming the implicit void member.
    Splitting the head into aggregate and member is resolution's business
    (F-8); the parser records the segments.
    """
    name:    "list[str]"      # name-dotted segments (without the VOID tail)
    is_void: bool
    begin:   int

    @classmethod
    def from_seq(cls, node):
        """RETURN: HasRef -- children = (ref_member,): the (segments, is_void)
        pair from the <ref-member> rule, rebased to the 'has:' offset."""
        segments, is_void = node.children[0]
        return cls(name=segments, is_void=is_void, begin=node.begin)


@dataclass(frozen=True)
class ReactorDecl(TopLevel):
    """A reactor-kind forward declaration: '<name> [signature] is: <kind>'.

    Satisfies the (B.1) declare-by-name-and-kind gate of the (A)/(B) forward-
    reference rule; the matching definition follows later in the same scope
    (B.2). 'kind' is one of 'mode', 'state', 'mode_group', 'state_machine'
    (the verbatim kind keyword). 'params' is the ROUND-bracket instantiation
    signature, a list of ArgDecl -- how a later 'spawn:' instantiates the type.
    MANDATORY on the spawnable kinds (mode_group, state_machine), forbidden on
    'mode'/'state' (armed, not instantiated) -- the kind-vs-shape rule checked
    in pass 2 (F-2); the parser records what was written. Empty when the head
    carried no parentheses.
    """
    kind:   str
    name:   str
    params: List["ArgDecl"]
    begin:  int


@dataclass(frozen=True)
class StructDecl(TopLevel):
    """A struct definition: '<name>( member: type; ... ) is: struct'.

    An aggregate VALUE type (D-23). 'members' is the head signature -- the SAME
    round-bracket form a reactor declaration carries, here it IS the member
    list and the declaration IS the definition: structs are (A)-strict, no
    forward declaration exists, so the signature is mandatory (F-2) and member
    cycles are impossible by construction. Members may be built-in- or
    struct-typed (ArgDecl.type, resolved pass 2).
    """
    name:    str
    members: List["ArgDecl"]
    begin:   int


@dataclass(frozen=True)
class ContainerDecl(TopLevel):
    """A container declaration: '<name> is: container<...> [by: {lvalue}]'.

    'cargs' are the ANGLE-bracket TYPE PARAMETERS, a list of Arg (shape, size,
    access words -- opaque to the static layer, read by the resolver); empty
    when the angle brackets are absent (per-kind defaults). A container has no
    constructor signature -- round = how to instantiate, angle = what kind --
    yet the grammar admits a head signature on the shared declaration head, so
    'head_params' records what was written for the pass-2 kind-vs-shape check
    (F-2). 'by' is the optional script binding: an LVALUE opaque span giving the
    engine-owned container an EXISTING opaque-code reference, or None.
    """
    name:        str
    cargs:       List["Arg"]
    by:          Optional["OpaqueCode"]
    head_params: List["ArgDecl"]
    begin:       int


@dataclass(frozen=True)
class VariableDef(TopLevel):
    """A variable definition: '<name> is: <type>(args) [by: {lvalue}]'.

    'type_name' is the verbatim type word -- a built-in keyword ('int',
    'float', 'string', 'bool') or a struct name; which it is, is a pass-2
    resolution. 'args' is the MANDATORY round-bracket initialiser: one
    positional value for a built-in, member bindings for a struct, checked in
    pass 2 (F-4); evaluation is declaration-ordered at bootstrap. 'by' is the
    optional script binding (as on ContainerDecl). 'head_params' records a
    head signature should one be written (illegal, pass-2 F-2).
    """
    name:        str
    type_name:   str
    args:        List["Arg"]
    by:          Optional["OpaqueCode"]
    head_params: List["ArgDecl"]
    begin:       int


@dataclass(frozen=True)
class DefaultRef(SEQ_Interface):
    """A 'default: <ref-member>' element naming the fallback member state.

    Same shape as HasRef -- the two share the <ref-member> production -- as a
    DISTINCT class so the aggregate builder tells them apart by type, never by
    provenance sniffing. That the target is a member state of the enclosing
    machine is a pass-2 check (F-8).
    """
    name:    "list[str]"      # name-dotted segments (without the VOID tail)
    is_void: bool
    begin:   int

    @classmethod
    def from_seq(cls, node):
        """RETURN: DefaultRef -- children = (ref_member,): the (segments,
        is_void) pair from the <ref-member> rule, rebased to 'default:'."""
        segments, is_void = node.children[0]
        return cls(name=segments, is_void=is_void, begin=node.begin)


@dataclass(frozen=True)
class StateMachine(SEQ_Interface, TopLevel):
    """A state-machine definition: members and one 'default', closed by 'end'.

    'states' are the inline member states; 'has_refs' are members pulled in
    with 'has:'. 'default' is the single DefaultRef ('default:' target) or
    None if the author omitted it (a validator-pass concern, not a parser
    error). The block is closed by the 'end' keyword; a state machine has no
    closing 'until' causes of its own.
    """
    name:     "list[str]"     # dotted-name segments
    params:   List[ArgDecl]
    bases:    List["list[str]"]   # 'is:' base names (dotted), in source order
    states:   List[State]
    has_refs: List[HasRef]
    default:  Optional["DefaultRef"]
    init:     Optional[OpaqueCode]
    deinit:   Optional[OpaqueCode]
    begin:    int

    @classmethod
    def from_seq(cls, node):
        """RETURN: StateMachine -- children = (signature, STAR(is-bases),
        PLUS(members)); ':end' silent.

        Each base item is the anonymous one-survivor SEQ around its dotted-name
        ('is:' is silent); members come off their PLUS slot directly. The old
        list-vs-node type-spotting boundary scan is gone: bases and members have
        their own grammar slots.
        """
        name, params = node.children[0]
        bases        = [s.children[0] for s in node.children[1].items]
        members      = node.children[2].items
        init = deinit = default = None
        states, has_refs = [], []
        for m in members:
            match m:
                case InitBlock():           init = m.body
                case DeinitBlock():         deinit = m.body
                case DefaultRef():          default = m
                case State():               states.append(m)
                case HasRef():              has_refs.append(m)
        return cls(name=name, params=params, bases=bases, states=states,
                   has_refs=has_refs, default=default, init=init,
                   deinit=deinit, begin=node.begin)


@dataclass(frozen=True)
class ModeGroup(SEQ_Interface, TopLevel):
    """A mode-group definition: an aggregate of modes, closed by 'end'.

    'modes' are the inline member modes; 'has_refs' are members pulled in with
    'has:'. Has 'init'/'deinit' like a state machine, but no 'default'
    (overlapping members have no single fallback) and, like a state machine, no
    closing 'until' causes of its own -- the block is closed by 'end'.
    """
    name:     "list[str]"     # dotted-name segments
    params:   List[ArgDecl]
    bases:    List["list[str]"]   # 'is:' base names (dotted), in source order
    modes:    List[Mode]
    has_refs: List[HasRef]
    init:     Optional[OpaqueCode]
    deinit:   Optional[OpaqueCode]
    begin:    int

    @classmethod
    def from_seq(cls, node):
        """RETURN: ModeGroup -- children = (signature, STAR(is-bases),
        PLUS(members)); ':end' silent. Same slot shape as StateMachine."""
        name, params = node.children[0]
        bases        = [s.children[0] for s in node.children[1].items]
        members      = node.children[2].items
        init = deinit = None
        modes, has_refs = [], []
        for m in members:
            match m:
                case InitBlock():   init = m.body
                case DeinitBlock(): deinit = m.body
                case Mode():        modes.append(m)
                case HasRef():      has_refs.append(m)
        return cls(name=name, params=params, bases=bases, modes=modes,
                   has_refs=has_refs, init=init, deinit=deinit,
                   begin=node.begin)


@dataclass(frozen=True)
class EventDef(SEQ_Interface, TopLevel):
    """An event declaration: 'event name(arg-decls)'."""
    name:   str
    params: List[ArgDecl]
    begin:  int

    @classmethod
    def from_seq(cls, node):
        """RETURN: EventDef -- children = (name_tok, params_list)."""
        name_tok, params = node.children
        return cls(name=name_tok.text, params=params, begin=node.begin)


@dataclass(frozen=True)
class ClockDef(SEQ_Interface, TopLevel):
    """A clock declaration: 'clock event-name number'."""
    name:   str
    period: str             # NUMBER lexeme, kept verbatim
    begin:  int

    @classmethod
    def from_seq(cls, node):
        """RETURN: ClockDef -- children = (name_tok, period_tok)."""
        name_tok, period_tok = node.children
        return cls(name=name_tok.text, period=period_tok.text, begin=node.begin)


@dataclass(frozen=True)
class CauseDef(SEQ_Interface, TopLevel):
    """A named, parameterised cause:
    'cause: NAME(params) for: <event> & <guard>'.

    Defines a reusable cause so a causality rule can fire it by reference (see
    CauseRef) instead of respelling the trigger and guard. 'name'/'params' come
    from the signature; 'for_event' is the bound event's <name-dotted> segment
    list -- the event the definition's 'e.member' references are checked
    against, once, at the definition (D-8). 'guard' is MANDATORY and CONCRETE
    (an opaque span or a Condition tree), never another cause reference: no alias
    chains. Resolution of references against this definition is a pass-2
    concern; the parser only records it.
    """
    name:      "list[str]"     # name-dotted segments from the signature
    params:    List[ArgDecl]
    for_event: "list[str]"     # name-dotted segments of the bound event
    guard:     "object"        # OpaqueCode | Condition
    begin:     int

    @classmethod
    def from_seq(cls, node):
        """RETURN: CauseDef -- children = (signature, for_event, guard);
        'cause:', 'for:', '&' silent."""
        sig, for_event, guard = node.children
        name, params = sig
        return cls(name=name, params=params, for_event=for_event,
                   guard=guard, begin=node.begin)


@dataclass(frozen=True)
class EffectDef(SEQ_Interface, TopLevel):
    """A named effect bundle: 'effect: NAME(params) => <effect> [=> <effect>]*'.

    Defines a reusable, ordered list of effects so a causality rule can invoke
    the whole bundle by reference. '=>' is a signal even here -- it introduces
    each effect exactly as in an inline causality rule. 'name'/'params' come from
    the signature, parallel to CauseDef; binding a reference's arguments to these
    params is a pass-2 concern.
    """
    name:    "list[str]"     # dotted-name segments from the signature
    params:  List[ArgDecl]
    effects: List[object]
    begin:   int

    @classmethod
    def from_seq(cls, node):
        """RETURN: EffectDef -- children = (signature, PLUS(('=>', effect))).

        Each repetition item is an anonymous one-survivor SEQ around its effect
        ('=>' is silent), so the effects are read off the PLUS slot directly.
        """
        sig          = node.children[0]
        name, params = sig
        effects      = [s.children[0] for s in node.children[1].items]
        return cls(name=name, params=params, effects=effects, begin=node.begin)


@dataclass(frozen=True)
class CauseRef:
    """A reference to a defined cause, invoked with arguments: 'NAME(args)'.

    Appears in cause position of a causality rule as an alternative to an
    inline trigger; built by the cause-named builder when the parens are
    present -- the parens decide (D-26). 'name' is the cause's <name-dotted>
    segment list (definitions reached through namespaces and imports are
    referenceable); 'args' are the actual arguments bound to the definition's
    parameters. 'guard' records a trailing '& <guard>' should one be written:
    it PARSES, and its legality is a pass-2 decision (F-7, fatal until
    decided). Binding the args to a CauseDef and checking arity/kinds is a
    pass-2 concern.
    """
    name:  "list[str]"        # name-dotted segments
    args:  List["Arg"]
    guard: "Optional[object]" # OpaqueCode | Condition | None -- parsed, pass-2 F-7
    begin: int


@dataclass(frozen=True)
class EffectRef:
    """A reference to a defined effect bundle, by bare name: 'NAME'.

    Appears in effect position of a causality rule as an alternative to an
    inline effect; built by the effect-named builder when the parens are
    ABSENT -- the parens decide (D-26). 'name' is the bundle's <name-dotted>
    segment list (definitions reached through namespaces and imports are
    referenceable); expanding it to the defined effects is a pass-2 concern.
    """
    name:  "list[str]"        # name-dotted segments
    begin: int


@dataclass(frozen=True)
class Import(SEQ_Interface, TopLevel):
    """A file mount: 'import: "<file>" into: <name-dotted>'.

    'filename' is the imported file's name (the string lexeme, quotes
    stripped). 'mount' is the dotted path at which the file's namespace is
    mounted in THIS file. The imported file is placement-agnostic; the
    importing file chooses the mount point. Resolving and mounting the file is
    a semantic-pass concern; the parser only records the request.
    """
    filename: str
    mount:    "list[str]"     # name-dotted segments
    begin:    int

    @classmethod
    def from_seq(cls, node):
        """RETURN: Import -- children = (string_tok, name_dotted); quotes
        stripped from the filename lexeme."""
        string_tok, mount = node.children
        filename = string_tok.text
        if len(filename) >= 2 and filename[0] in "\"'" and filename[-1] == filename[0]:
            filename = filename[1:-1]
        return cls(filename=filename, mount=mount, begin=node.begin)


@dataclass(frozen=True)
class Namespace(SEQ_Interface, TopLevel):
    """A named scope: 'open <dotted-name> ... close' bracketing nested items.

    'name' is the dotted path opened ('world.europe.berlin'), nesting several
    levels at once. 'items' are the TopLevel constructs declared inside, in
    source order, and may themselves include further Namespace nodes. Names
    declared inside resolve within this scope; there is no restriction on
    nesting depth.
    """
    name:  "list[str]"        # dotted-name segments
    items: "List[TopLevel]"
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: Namespace -- children = (dotted_name, PLUS(items)).

        The PLUS body is a single rule reference, so its items are the finished
        top-level nodes directly (no anonymous wrap).
        """
        name  = node.children[0]
        items = list(node.children[1].items)
        return cls(name=name, items=items, begin=node.begin)


@dataclass(frozen=True)
class Instant(SEQ_Interface):
    """An immediate-injection step: 'instant: name(args)'.

    A tick-free agent stimulus -- the named event with its mandatory argument
    list is injected into the CURRENT event queue at the present instant, off
    the agent's clock beat (D-11). The paced counterpart is a bare EventSpec
    (no keyword), which consumes a tick.
    """
    name:  "list[str]"        # name-dotted segments
    args:  List[Arg]
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: Instant -- children = (name, args); 'instant:' silent."""
        name, args = node.children
        return cls(name=name, args=args, begin=node.begin)


@dataclass(frozen=True)
class WaitLine(SEQ_Interface):
    """A wait step: 'wait: <cause> (=> <effect>)*'.

    Suspends the agent script until 'cause' fires. 'effects' is the optional
    co-temporal tail (possibly empty), run with 'e' bound to the firing event
    -- 'e' does not flow into subsequent steps. A tail-less wait is a pure
    progression gate. Resumption is at the agent's next own-clock tick (D-11).
    """
    cause:   Cause
    effects: List[object]     # EventSpec/EffectRef/ModeArming/Spawn/Unspawn/...
    begin:   int

    @classmethod
    def from_seq(cls, node):
        """RETURN: WaitLine -- children = (cause, STAR(('=>', effect))).

        Each repetition item is the anonymous one-survivor SEQ around its
        effect ('=>' silent); the tail may be empty.
        """
        cause   = node.children[0]
        effects = [s.children[0] for s in node.children[1].items]
        return cls(cause=cause, effects=effects, begin=node.begin)


@dataclass(frozen=True)
class SelectFrame(SEQ_Interface):
    """A select step: 'select: <wait-line>+ :end'.

    Suspends on several waits at once; the first cause to fire selects its
    branch, the others are abandoned (D-11). 'branches' are the member
    WaitLines, each with its own optional co-temporal effect tail.
    """
    branches: List["WaitLine"]
    begin:    int

    @classmethod
    def from_seq(cls, node):
        """RETURN: SelectFrame -- children = (PLUS(wait-line),); ':end' silent."""
        return cls(branches=list(node.children[0].items), begin=node.begin)


@dataclass(frozen=True)
class IfFrame(SEQ_Interface):
    """An if step: 'if: <guard> <steps> (elif: <guard> <steps>)* [else: <steps>] :end'.

    A tick-free control frame fencing step sequences inside an agent body. 'arms'
    is the list of (guard, body) pairs -- the leading 'if:' and each 'elif:', in
    source order; 'else_body' is the trailing 'else:' steps or None. The whole
    if/elif/else chain is closed by ONE ':end'. Conditions reuse <guard> (an
    OpaqueCode CONDITION span or a Condition tree); 'e' is not in scope (D-11).
    """
    arms:      List["tuple"]   # [(guard, [step, ...]), ...]
    else_body: "Optional[list]"
    begin:     int

    @classmethod
    def from_seq(cls, node):
        """RETURN: IfFrame, 'if:/elif:/else: ... :end'.

        children = (guard, PLUS(steps), STAR(('elif:', guard, PLUS(steps))),
        opt_else): the head arm, then the elif repetition (each item the
        anonymous SEQ (guard, PLUS) -- 'elif:' silent), then the optional else
        (present yields the anonymous one-survivor SEQ around its PLUS, 'else:'
        silent). ':end' silent.
        """
        head_guard  = node.children[0]
        head_body   = list(node.children[1].items)
        arms        = [(head_guard, head_body)]
        for s in node.children[2].items:
            g, plus = s.children
            arms.append((g, list(plus.items)))
        opt_else  = node.children[3]
        else_body = list(opt_else.child.children[0].items) if opt_else.present \
                    else None
        return cls(arms=arms, else_body=else_body, begin=node.begin)


@dataclass(frozen=True)
class WhileFrame(SEQ_Interface):
    """A while step: 'while: <guard> <steps> :end'.

    A tick-free control frame: the step body repeats while 'guard' holds. The
    block takes its OWN ':end' (D-11). Condition reuses <guard>; 'e' is not in
    scope.
    """
    guard: "object"           # OpaqueCode | Condition
    body:  List[object]       # agent steps
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: WhileFrame -- children = (guard, PLUS(steps)); ':end' silent."""
        guard = node.children[0]
        body  = list(node.children[1].items)
        return cls(guard=guard, body=body, begin=node.begin)


@dataclass(frozen=True)
class Agent(SEQ_Interface, TopLevel):
    """An agent definition: a tick-scripted stimulus actor, closed by ':end'.

    'name'/'params' come from the signature; the params ARE the instance
    members, read through the 'ag' self-binding (D-11). 'clock' is the 'on:'
    <cause> -- a trigger (resolved to a clock in pass 2) with an optional guard,
    the heartbeat shape. 'init'/'deinit' are STATEMENT_BLOCK OpaqueCode spans or
    None. 'steps' are the ordered body steps: EventSpec (paced emission),
    Instant, WaitLine, SelectFrame, IfFrame, WhileFrame, and the bare commands
    (Spawn, Unspawn, ModeArming, Mutation). No inheritance: an agent carries no
    'is:' bases.
    """
    name:   "list[str]"       # dotted-name segments
    params: List[ArgDecl]
    clock:  Cause
    init:   Optional[OpaqueCode]
    deinit: Optional[OpaqueCode]
    steps:  List[object]
    begin:  int

    @classmethod
    def from_seq(cls, node):
        """RETURN: Agent -- children = (signature, cause, PLUS(elements)).

        'agent:', 'on:', ':end' silent. The signature is the (name, params)
        pair; the cause is the 'on:' clock binding. Each element is a step or an
        InitBlock/DeinitBlock; init/deinit are sorted out by type, the rest keep
        source order as the script.
        """
        name, params = node.children[0]
        clock        = node.children[1]
        elements     = node.children[2].items
        init = deinit = None
        steps = []
        for elm in elements:
            match elm:
                case InitBlock():   init = elm.body
                case DeinitBlock(): deinit = elm.body
                case _:             steps.append(elm)
        return cls(name=name, params=params, clock=clock, init=init,
                   deinit=deinit, steps=steps, begin=node.begin)


@dataclass
class RuleFile:
    """The whole parsed rule file: an ordered list of top-level constructs.

    'items' holds Namespace, Import, Causality, Mode, ModeGroup, StateMachine,
    Agent, declaration (ReactorDecl/StructDecl/ContainerDecl/VariableDef),
    EventDef, ClockDef, CauseDef and EffectDef nodes in source order. A mutable
    container so the parser can append as it goes.
    """
    items: "List[TopLevel]" = field(default_factory=list)

