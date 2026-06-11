"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

ABSTRACT SYNTAX TREE NODES

Pure data structures for the rule-file grammar (see GRAMMAR in grammar.py). Every node
carries 'begin', the absolute source offset where the construct starts, so a
SourceMap can resolve a 1-based (line, column) for error reporting and for the
Source2TargetLocationMapper during code generation. Nodes hold no behaviour;
the parser builds them and the validator/transpiler consume them.

Opaque Luau spans are stored verbatim as the LUAU_BLOCK lexeme text (braces
included) together with the Role under which the parser handed them to the
oracle, so the transpiler can re-frame each correctly.
______________________________________________________________________________
"""
from dataclasses import dataclass, field
from enum        import Enum
from typing      import List, Optional

from ..luau.luau_fragment import Role
from .core.operator_interface import (OR_Interface, SEQ_Interface,
                                      PLUS_Interface, STAR_Interface)


from abc import ABC


class E_ArgKind(Enum):
    """The value shape of an Arg (see Arg.kind).

    LITERAL  a NUMBER/STRING/bare-identifier lexeme carried as text.
    LUAU     an opaque EXPRESSION Luau span (a Luau node).
    MEMBER   a shallow 'binding.member' reference (a ShallowMemberAccess node).
    """
    LITERAL = 0
    LUAU    = 1
    MEMBER  = 2


class TopLevel(OR_Interface):
    """Abstract base for the constructs that may appear at rule-file top level.

    Namespace, Include, Causality, Mode, ModeGroup, StateMachine, ForwardDecl,
    EventDef and ClockDef derive from it, so 'RuleFile.items' is typed as list[TopLevel] and
    only these node kinds are admissible there. A Namespace nests further
    TopLevel items (Causality, Mode, ModeGroup, StateMachine, ForwardDecl,
    EventDef, ClockDef, Include, Namespace). Carries no fields; the concrete
    nodes hold their own.
    """
    pass

@dataclass(frozen=True)
class Luau:
    """One opaque Luau span: its verbatim text, role, and source offset.

    'text' is the lexeme including the enclosing braces. 'role' is the context
    the parser supplied to the oracle (CONDITION, EXPRESSION, STATEMENT_BLOCK).
    """
    text:  str
    role:  Role
    begin: int

    @classmethod
    def from_span(cls, span):
        """RETURN: Luau, wrapping an engine SpanResult.

        The engine yields a neutral core.span_oracle.SpanResult at an opaque-span
        position (it knows no language); this is the single seam where the rule
        language turns it into its own Luau node. SpanResult.mode is the Role the
        grammar attached to the opaque terminal, mapped straight onto 'role'.
        For the <luau-guard> rule (a single-terminal rule) the factory receives
        the raw SpanResult itself -- there is no operator node to unwrap.
        """
        return cls(text=span.text, role=span.mode, begin=span.begin)


@dataclass(frozen=True)
class Trigger(OR_Interface):
    """A cause trigger: an event name or an implicit keyword (ANY/BEGIN/END).

    'name' is the identifier or keyword lexeme. 'is_keyword' True marks the
    implicit triggers, distinguishing 'END' the system event from a user event
    that happens to be spelled END elsewhere.
    """
    name:       str
    is_keyword: bool
    begin:      int


# --- Bracket-condition algebra ('& [ ... ]') ---------------------------------
# A transparent, engine-inspectable alternative to a Luau CONDITION guard: a
# boolean combination ('and'/'or'/'not', parenthesisable) of comparisons over
# the triggering event's members. Members are leading-dot, single-level
# ('.ip_adr' == the 'ip_adr' member of the event that fired). The tree is built
# directly by the parser, so the static layer can validate member references and
# comparisons instead of treating the guard as opaque text.

    @classmethod
    def from_or(cls, node):
        """RETURN: Trigger, from the <trigger> OR_Node.

        Branch 0 is the bare identifier; branches 1..3 the captured keywords
        (ANY / END / BEGIN), so 'is_keyword' is exactly 'a non-zero branch fired'
        -- read off triggered_index, no token-kind comparison needed.
        """
        tok = node.child
        return cls(name=tok.text, is_keyword=(node.triggered_index != 0),
                   begin=tok.begin)


@dataclass(frozen=True)
class EventMember(SEQ_Interface):
    """A reference to a member of the triggering event: '.name'.

    Leading-dot, single-level. The event is implicit -- the one named by the
    trigger this guard gates -- so only the member 'name' is recorded. Binding
    the name to a declared event member is a pass-2 concern.
    """
    name:  str
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: EventMember, from the <evt-member> SEQ_Node ('.' is silent)."""
        tok = node.children[0]
        return cls(name=tok.text, begin=tok.begin)


@dataclass(frozen=True)
class Literal:
    """A number or string literal operand in a comparison.

    'text' is the verbatim lexeme (a number, or a string WITH its quotes); the
    static layer interprets it against the compared member's type.
    """
    text:  str
    begin: int

    @classmethod
    def from_or(cls, node):
        """RETURN: EventMember | Literal, from the <cond-operand> OR_Node.

        Branch 0 is an already-built EventMember (children-transformed-first),
        forwarded unchanged; branches 1..2 are number/string tokens wrapped here.
        """
        value = node.child
        if node.triggered_index == 0:
            return value
        return cls(text=value.text, begin=value.begin)


@dataclass(frozen=True)
class Comparison(SEQ_Interface):
    """A single comparison: '<evt-member> <op> <operand>'.

    'op' is one of '>=', '<=', '==', '!=', '>', '<' (verbatim). 'left' is always
    an EventMember; 'right' is an EventMember or a Literal.
    """
    left:  EventMember
    op:    str
    right: "object"          # EventMember | Literal
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: Comparison, from the <comparison> SEQ_Node.

        children = (EventMember, op_token, operand): left member, the comparison
        operator token (its '.text' is the verbatim op), right operand.
        """
        left, op_tok, right = node.children
        return cls(left=left, op=op_tok.text, right=right, begin=left.begin)


@dataclass(frozen=True)
class Not(SEQ_Interface):
    """A negated condition: 'not <cond-atom>'."""
    operand: "object"        # Comparison | Not | BoolOp
    begin:   int

    @classmethod
    def from_seq(cls, node):
        """RETURN: Not | <cond-atom>, from the <not-cond> SEQ_Node.

        children = (opt_not, atom): the inline optional 'not' is an OR_Node at a
        STABLE slot -- triggered_index 0 means 'not' was present. No counting.
        A plain (un-negated) atom is forwarded unchanged.
        """
        opt_not, atom = node.children
        if opt_not.triggered_index == 0:
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
    def from_and_cond(cls, node):
        """RETURN: BoolOp('and') | operand, the 'and' precedence level."""
        return cls._from_level(node, "and")

    @classmethod
    def from_or_cond(cls, node):
        """RETURN: BoolOp('or') | operand, the 'or' precedence level (lowest)."""
        return cls._from_level(node, "or")


@dataclass(frozen=True)
class Condition(SEQ_Interface):
    """The root of a bracket guard '[ ... ]'.

    'expr' is the top boolean expression (a BoolOp, Not, or Comparison). Wrapping
    it in a named root keeps a guard's two forms -- Luau span vs. bracket
    condition -- as two distinct, type-distinguishable node kinds on Cause.guard.
    """
    expr:  "object"
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: Condition, the root of a '[ ... ]' bracket guard.

        children = (expr,): the single top boolean expression ('[' / ']' are
        silent). The wrapper keeps the two guard forms (Luau span vs bracket
        condition) type-distinguishable on Cause.guard.
        """
        return cls(expr=node.children[0], begin=node.begin)


@dataclass(frozen=True)
class Cause(OR_Interface):
    """A cause: a trigger with an optional guard.

    'guard' is the condition gating the trigger, or None when absent. It is
    either a Luau CONDITION span (the '& { ... }' form) or a Condition tree (the
    '& [ ... ]' bracket form); both express "the event fired AND this holds".
    """
    trigger: Trigger
    guard:   "Optional[object]"   # Luau | Condition | None
    begin:   int

    @classmethod
    def from_or(cls, node):
        """RETURN: Cause | CauseRef, from the <cause> OR_Node.

        Branch 0 is an already-built CauseRef, forwarded unchanged. Branch 1 is
        the anonymous SEQ (Trigger, opt_guard): the inline optional ["&" <guard>]
        is an OR_Node at a stable slot whose present child is the anonymous
        one-survivor SEQ around the guard ('&' is silent). No counting.
        """
        if node.triggered_index == 0:
            return node.child
        seq       = node.child
        trigger   = seq.children[0]
        opt_guard = seq.children[1]
        guard     = (opt_guard.child.children[0]
                     if opt_guard.triggered_index == 0 else None)
        return cls(trigger=trigger, guard=guard, begin=trigger.begin)


@dataclass(frozen=True)
class ShallowMemberAccess(SEQ_Interface):
    """A first-class member reference 'binding.member' on the rule-file plane.

    The rule-file plane can name a member of one of the four runtime self-
    bindings -- 'event' (the triggering event), 'sm' / 'mg' (the enclosing state
    machine / mode group), 'mode' (the enclosing mode) -- WITHOUT descending into
    opaque Luau. 'binding' is the keyword lexeme ('event'/'sm'/'mg'/'mode');
    'member' is the bare member name after the '.'. The access is SHALLOW by
    design: exactly one '.', no deeper dive and no expression -- a pure
    reference, legible to the static layer, which checks the member against the
    binding's declared members (an EventDef, or a mode/aggregate's declared
    members). A deeper navigation or any computation still belongs behind '{ }'.
    """
    binding: str
    member:  str
    begin:   int

    @classmethod
    def from_seq(cls, node):
        """RETURN: ShallowMemberAccess -- children = (binding_tok, member_tok)."""
        binding_tok, member_tok = node.children
        return cls(binding=binding_tok.text, member=member_tok.text,
                   begin=node.begin)


@dataclass(frozen=True)
class Arg(OR_Interface):
    """One argument of an event-spec, mode-arming, or spawn: optional name, value.

    'name' is the keyword-argument name when written 'name = value', else None
    (a positional argument). Named arguments may follow positional ones; whether
    a given site accepts a name, and binding correctness, are a semantic-layer
    concern, not a parse error.

    'value' is the rvalue, one of three shapes discriminated by 'kind':
      - E_ArgKind.LITERAL  : a NUMBER/STRING/bare-identifier lexeme as text (str).
      - E_ArgKind.LUAU     : an opaque EXPRESSION Luau span (a Luau node).
      - E_ArgKind.MEMBER   : a ShallowMemberAccess node ('event.x' etc.) the
                             static layer can read without parsing Luau.
    A bare identifier (e.g. a container type-parameter 'dict') is a LITERAL
    carried as text; its meaning is a pass-2 concern.
    """
    name:  Optional[str]
    value: object            # str (literal) | Luau | ShallowMemberAccess
    kind:  "E_ArgKind"
    begin: int

    @classmethod
    def _classify(cls, value, name, begin):
        """RETURN: Arg, classifying 'value' into its E_ArgKind.

        A ShallowMemberAccess is a MEMBER; an opaque SpanResult becomes a Luau
        node (LUAU); a value-bearing Token (or bare str) is carried as text
        (LITERAL).
        """
        from .core.span_oracle import SpanResult
        if isinstance(value, ShallowMemberAccess):
            return cls(name=name, value=value, kind=E_ArgKind.MEMBER, begin=begin)
        if isinstance(value, SpanResult):
            return cls(name=name, value=Luau.from_span(value),
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
class EventSpec(SEQ_Interface):
    """An event emission effect: 'name(args)'."""
    name:  "list[str]"        # dotted-name segments
    args:  List[Arg]
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: EventSpec -- children = (dotted_name, args_list)."""
        name, args = node.children
        return cls(name=name, args=args, begin=node.begin)


@dataclass(frozen=True)
class ModeArming(SEQ_Interface):
    """A mode-arming effect: '! name(args)'."""
    name:  "list[str]"        # dotted-name segments
    args:  List[Arg]
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: ModeArming -- children = (dotted_name, args_list); '!' silent."""
        name, args = node.children
        return cls(name=name, args=args, begin=node.begin)


@dataclass(frozen=True)
class Spawn(SEQ_Interface):
    """An aggregate-spawning effect: '+! name (args) [ in: C ] [ as: {lvalue} ]'.

    Targets a <mode-group> or <state-machine> type. One shape with two
    independent optional modifiers:
      - 'args' is the instantiation argument list; the parentheses are MANDATORY
        (a bare '+! name' is rejected by the grammar). 'args' is empty when the
        type takes none ('+! name()').
      - 'in_container' names a declared container ('+! x in: C') the fresh
        instance is caught by, or None for the per-kind default container;
        resolved in pass 2 to an 'is: container' declaration.
      - 'luau_handle' is the optional 'as: { ... }' lvalue span (a Luau node):
        the key/handle the container holds the instance under (a dict
        container's key), or None.
    'has_parens' is now always True for a parsed node (the parens are mandatory);
    it is retained for the builder and downstream and no longer discriminates a
    shape.
    """
    name:        "list[str]"  # dotted-name segments
    args:        List[Arg]
    has_parens:  bool
    in_container: "Optional[list[str]]"  # dotted-name segments, or None
    luau_handle: Optional["Luau"]
    begin:       int

    @classmethod
    def from_seq(cls, node):
        """RETURN: Spawn, '+! name (args) [ in: C [ as: {lv} ] ]'.

        children = (name, args, opt_in): the trailing options are NESTED stable
        OR_Node slots mirroring the grammar's nested optionals -- opt_in present
        yields the anonymous SEQ (container_name, opt_as); opt_as present yields
        the anonymous one-survivor SEQ around the LVALUE span. The old last-
        value-is-a-span type-spotting is gone: each option has its slot.
        """
        name, args, opt_in = node.children
        in_container = None
        luau_handle  = None
        if opt_in.triggered_index == 0:
            seq          = opt_in.child
            in_container = seq.children[0]
            opt_as       = seq.children[1]
            if opt_as.triggered_index == 0:
                span        = opt_as.child.children[0]
                luau_handle = Luau.from_span(span)
        return cls(name=name, args=args, has_parens=True,
                   in_container=in_container, luau_handle=luau_handle,
                   begin=node.begin)


@dataclass(frozen=True)
class Unspawn(SEQ_Interface):
    """An existence-ending effect: '-! name'.

    'name' references a spawned aggregate by bare or dotted name. Ending an
    existence runs the instance's 'deinit' and releases it from its container.
    Pass-2 validation enforces that the target resolves to an existing
    instance; the grammar accepts any dotted name.
    """
    name:  "list[str]"        # dotted-name segments
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: Unspawn, '-! name' -- children = (dotted_name,)."""
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
    """A mutation effect: a STATEMENT_BLOCK Luau span after '=>'."""
    body:  Luau
    begin: int

    @classmethod
    def from_span(cls, span):
        """RETURN: Mutation, wrapping the STATEMENT_BLOCK span (single-terminal
        rule: the factory receives the raw SpanResult)."""
        body = Luau.from_span(span)
        return cls(body=body, begin=body.begin)


@dataclass(frozen=True)
class InitBlock(SEQ_Interface):
    """An 'init { ... }' member: its STATEMENT_BLOCK body.

    A distinct type (vs DeinitBlock) so a mode/state-machine assembler can sort
    interleaved members by kind rather than by source position.
    """
    body:  Luau
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: InitBlock -- children = (span,), the STATEMENT_BLOCK body."""
        body = node.children[0]
        return cls(body=body, begin=body.begin)


@dataclass(frozen=True)
class DeinitBlock(SEQ_Interface):
    """A 'deinit { ... }' member: its STATEMENT_BLOCK body. See InitBlock."""
    body:  Luau
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: DeinitBlock -- children = (span,), the STATEMENT_BLOCK body."""
        body = node.children[0]
        return cls(body=body, begin=body.begin)


@dataclass(frozen=True)
class Causality(SEQ_Interface, TopLevel):
    """A full rule: 'on <cause> (=> <effect>)+'.

    'effects' holds the ordered effect nodes (EventSpec, ModeArming,
    ReportString, Mutation).
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
    """One parameter declaration: 'member : type'."""
    member: str
    type:   str
    begin:  int

    @classmethod
    def from_seq(cls, node):
        """RETURN: ArgDecl, one 'member: type' -- children = (name_colon, type).

        The member name carries a glued trailing ':' (NAME_COLON), stripped here.
        """
        member_tok, type_tok = node.children
        return cls(member=member_tok.text[:-1], type=type_tok.text,
                   begin=member_tok.begin)


@dataclass(frozen=True)
class Mode(SEQ_Interface, TopLevel):
    """A mode definition with its members and mandatory 'until' causes.

    'init'/'deinit' are STATEMENT_BLOCK Luau spans or None. 'causalities' are
    the member rules. 'untils' are the closing causes (one or more).
    """
    name:        "list[str]"  # dotted-name segments
    params:      List[ArgDecl]
    init:        Optional[Luau]
    deinit:      Optional[Luau]
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
    init:        Optional[Luau]
    deinit:      Optional[Luau]
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
    """A 'has: <member-ref>' element pulling in a member defined elsewhere.

    'aggregate' is the qualifier of 'AGG.member' or None for a bare name.
    'member' is the referenced reactor name ('VOID' with 'is_void' True names
    the implicit void state).
    """
    aggregate: Optional[str]
    member:    str
    is_void:   bool
    begin:     int

    @classmethod
    def from_member_ref(cls, node):
        """RETURN: HasRef, a bare or qualified member reference.

        children = (name_tok, opt): the inline optional ('.', VOID|id) is an
        OR_Node at a stable slot. Absent -> bare name (the bare token is always a
        plain identifier, never VOID, so is_void is False). Present -> the
        optional's child is the anonymous one-survivor SEQ around the inner
        member OR_Node ('.' is silent); is_void IS that inner branch index.
        """
        name_tok, opt = node.children
        if opt.triggered_index != 0:
            return cls(aggregate=None, member=name_tok.text, is_void=False,
                       begin=name_tok.begin)
        member_or  = opt.child.children[0]
        member_tok = member_or.child
        return cls(aggregate=name_tok.text, member=member_tok.text,
                   is_void=(member_or.triggered_index == 0),
                   begin=name_tok.begin)

    @classmethod
    def from_has_kw(cls, node):
        """RETURN: HasRef, the 'has:' member rebased to the keyword offset."""
        ref = node.children[0]
        return cls(aggregate=ref.aggregate, member=ref.member,
                   is_void=ref.is_void, begin=node.begin)


@dataclass(frozen=True)
class ForwardDecl(TopLevel):
    """A '<name> [signature] is: <kind>' forward declaration: name, kind, body.

    Satisfies the (B.1) declare-by-name-and-type gate of the (A)/(B) forward-
    reference rule; the matching definition follows later in the same scope
    (B.2). 'kind' is one of 'mode', 'mode_group', 'state_machine', 'container'.

    Two bracket shapes are kept strictly apart, by type and by meaning:

      'signature' -- the ROUND-bracket instantiation signature, a list of
        ArgDecl (the same 'member : type ; ...' an aggregate definition
        declares). It says HOW a later '+!' instantiates the type, and is what
        the engine needs to instantiate when only the declaration is in scope.
        MANDATORY on the spawnable kinds (mode_group, state_machine), absent on
        'mode' (armed, not instantiated) and 'container' (parameterised, not
        instantiated) -- a kind-vs-signature rule checked in pass 2. Empty list
        when the name carried no parentheses.

      'cargs' -- the ANGLE-bracket TYPE PARAMETERS of a 'container' kind, a list
        of Arg (shape/size/access words, opaque to the static layer). It says
        WHAT KIND of container, never how to instantiate one; a container has no
        constructor signature. Empty for the static kinds.

    Round = how to instantiate; angle = what kind. 'luau_handle' is the optional
    'as: { ... }' lvalue span naming where a container lives in the script world
    (a Luau node, or None). The scope-level counterpart of HasRef ('has:'),
    which declares an aggregate member and lets the enclosing aggregate imply
    the kind.
    """
    kind:        str
    name:        str
    signature:   List["ArgDecl"]
    cargs:       List["Arg"]
    luau_handle: Optional["Luau"]
    begin:       int

    @classmethod
    def from_seq(cls, node):
        """RETURN: ForwardDecl, '<name> [signature] is: <kind>'.

        children = (name_tok, opt_sig, kind_dict): the optional round-bracket
        signature is an OR_Node at a stable slot (its present child is the
        already-reduced ArgDecl list); 'kind_dict' from <type-ref> carries keys
        'kind' / 'cargs' / 'luau_handle'. 'is:' is silent.
        """
        name_tok, opt_sig, kind = node.children
        signature = opt_sig.child if opt_sig.triggered_index == 0 else []
        return cls(kind=kind["kind"], name=name_tok.text, signature=signature,
                   cargs=kind["cargs"], luau_handle=kind["luau_handle"],
                   begin=name_tok.begin)


@dataclass(frozen=True)
class StateMachineModeRef(SEQ_Interface):
    """A reference 'SM.member' or 'SM.VOID' used by 'default ='."""
    sm_name:   str
    mode_name: str          # 'VOID' when the implicit void member is meant
    is_void:   bool
    begin:     int

    @classmethod
    def from_sm_mode_ref(cls, node):
        """RETURN: StateMachineModeRef, 'SM.member' or 'SM.VOID'.

        children = (sm_tok, member_or): the member is an inline OR_Node whose
        branch 0 is the captured VOID keyword -- is_void IS the branch index.
        """
        sm_tok, member_or = node.children
        member_tok = member_or.child
        return cls(sm_name=sm_tok.text, mode_name=member_tok.text,
                   is_void=(member_or.triggered_index == 0), begin=sm_tok.begin)

    @classmethod
    def from_default(cls, node):
        """RETURN: StateMachineModeRef, the 'default:' target, rebased to the
        construct start ('default:' is the connective)."""
        ref = node.children[0]
        return cls(sm_name=ref.sm_name, mode_name=ref.mode_name,
                   is_void=ref.is_void, begin=node.begin)


@dataclass(frozen=True)
class StateMachine(SEQ_Interface, TopLevel):
    """A state-machine definition: members and one 'default', closed by 'end'.

    'states' are the inline member states; 'has_refs' are members pulled in
    with 'has:'. 'default' is the single StateMachineModeRef ('default ='
    target) or None if the author omitted it (a validator-pass concern, not a
    parser error). The block is closed by the 'end' keyword; a state machine
    has no closing 'until' causes of its own.
    """
    name:     "list[str]"     # dotted-name segments
    params:   List[ArgDecl]
    bases:    List["list[str]"]   # 'is:' base names (dotted), in source order
    states:   List[State]
    has_refs: List[HasRef]
    default:  Optional[StateMachineModeRef]
    init:     Optional[Luau]
    deinit:   Optional[Luau]
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
                case StateMachineModeRef(): default = m
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
    init:     Optional[Luau]
    deinit:   Optional[Luau]
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
    """A named, parameterised cause: 'cause: NAME(params) on: <cause>'.

    Defines a reusable cause so a causality rule can fire it by reference (see
    CauseRef) instead of respelling the trigger and guard. 'name'/'params' come
    from the signature; 'body' is the Cause (trigger + optional guard) after the
    'on:' signal. 'on:' is a signal even here -- it marks the cause body just as
    it does in an inline causality rule. Resolution of the reference against this
    definition is a pass-2 concern; the parser only records the definition.
    """
    name:   "list[str]"     # dotted-name segments from the signature
    params: List[ArgDecl]
    body:   Cause
    begin:  int

    @classmethod
    def from_seq(cls, node):
        """RETURN: CauseDef -- children = (signature, Cause); keywords silent."""
        sig, body    = node.children
        name, params = sig
        return cls(name=name, params=params, body=body, begin=node.begin)


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
class CauseRef(SEQ_Interface):
    """A reference to a defined cause, invoked with arguments: 'NAME(args)'.

    Appears in cause position of a causality rule as an alternative to an inline
    trigger. 'name' is the cause's identifier; 'args' are the actual arguments
    bound to the definition's parameters. Binding the args to a CauseDef and
    checking arity/types is a pass-2 concern.
    """
    name:  str
    args:  List["Arg"]
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: CauseRef, 'NAME(args)' -- children = (name_tok, args_list)."""
        name_tok, args = node.children
        return cls(name=name_tok.text, args=args, begin=name_tok.begin)


@dataclass(frozen=True)
class EffectRef(SEQ_Interface):
    """A reference to a defined effect bundle, by bare name: 'NAME'.

    Appears in effect position of a causality rule as an alternative to an inline
    effect. 'name' is the bundle's identifier; expanding it to the defined
    effects is a pass-2 concern. The name is a single identifier, never dotted.
    """
    name:  str
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: EffectRef, a bare effect-bundle name -- children = (name_tok,)."""
        tok = node.children[0]
        return cls(name=tok.text, begin=tok.begin)


@dataclass(frozen=True)
class Include(SEQ_Interface, TopLevel):
    """A file mount: 'include "<file>" as <dotted-name>'.

    'filename' is the included file's name (the string lexeme, quotes stripped).
    'mount' is the dotted path at which the file's namespace is mounted in THIS
    file. The included file is placement-agnostic; the including file chooses
    the mount point. Resolving and mounting the file is a semantic-pass concern;
    the parser only records the request.
    """
    filename: str
    mount:    "list[str]"     # dotted-name segments
    begin:    int

    @classmethod
    def from_seq(cls, node):
        """RETURN: Include -- children = (string_tok, dotted_name); quotes
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


@dataclass
class RuleFile:
    """The whole parsed rule file: an ordered list of top-level constructs.

    'items' holds Namespace, Include, Causality, Mode, ModeGroup, StateMachine,
    ForwardDecl, EventDef and ClockDef nodes in source order. A mutable container
    so the parser can append as it goes.
    """
    items: "List[TopLevel]" = field(default_factory=list)
