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
language: everything span-related speaks 'oracle' (world.span_oracle).
______________________________________________________________________________
"""
from dataclasses import dataclass, field
from enum        import Enum
from typing      import List, Optional

from vut.engine.temporal_logic.world.span_oracle import Reference
from vut.engine.temporal_logic.core.parser_generator.operator_interface import (OR_Interface, SEQ_Interface,
                                      PLUS_Interface, STAR_Interface)


from abc import ABC


class E_ArgKind(Enum):
    """The value shape of an Arg (see Arg.kind).

    LITERAL  a NUMBER/STRING/true/false lexeme carried as text.
    LUAU     an opaque EXPRESSION span (an OpaqueCode node).
    NAME     a <name-dotted> reference carried as its segment list -- a bare
             word ('dict'), a variable, a struct member ('tracker.pos.x'), or
             a self-binding member ('e.target'); resolved in pass 2 (D-24).
    EXPR     a compound algebraic expression (BinOp/UnOp/Bridge/Comparison),
             carried as the expression node -- 'base + 1', '? c then: a else: b'
             (D-13). The simple atoms above remain their own kinds so a plain
             arg renders unchanged.
    """
    LITERAL = 0
    LUAU    = 1
    NAME    = 2
    EXPR    = 3


class TopLevel(OR_Interface):
    """Abstract base for the constructs that may appear at rule-file top level.

    Namespace, Import, Causality, Mode, ModeGroup, StateMachine, Clockwork, the
    four declaration nodes (ReactorDecl, StructDecl, ContainerDecl, VariableDef),
    EventDef, ClockDef, CauseDef and EffectDef derive from it, so
    'ModuleRoot.items' is typed as list[TopLevel] and only these node kinds are
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
    mode:  object             # world.span_oracle.SpanMode
    begin: int
    _references: "tuple|None" = field(default=None, compare=False, repr=False)

    @classmethod
    def from_span(cls, span):
        """RETURN: OpaqueCode, wrapping an engine SpanResult.

        The engine yields a neutral world.span_oracle.SpanResult at an
        opaque-span position (it knows no language); this is the single seam
        where the rule language turns it into its own node. SpanResult.mode is
        carried straight onto 'mode'. For the <mutation> rule (a
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
# The guard form: a transparent, engine-inspectable boolean combination
# ('and'/'or'/'not', parenthesisable) of comparisons over the triggering event's
# members. Members are leading-dot, single-level ('.ip_adr' == the 'ip_adr'
# member of the event that fired). The tree is built directly by the parser, so
# the static layer can validate member references and comparisons; a guard is
# never opaque text.

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
class MethodCall:
    """A postfix on an operand: a method call '.method(args)' or, after a call,
    a member read '.field'.

    'method' is the verbatim postfix name ('glob', 'len', 'has', 'keys', or a
    field). 'args' is the already-reduced argument list when this is a CALL
    (possibly empty for '()'), or None when it is a bare member read on a call
    result ('d.first().name'). 'receiver' is what the postfix applies to -- a
    name-dotted segment list, or another MethodCall when chaining
    ('d.keys().len()' nests the inner call as the outer postfix's receiver).
    Whether 'method' is a real member function/field of the receiver's type, and
    the arg arity/kinds, is a pass-2 catalogue check; the grammar admits any
    '.id' or '.id(args)'. An operand with NO call collapses to its name-dotted
    segment list, so a bare reference stays list[str] and the BoolRef path is
    preserved.
    """
    receiver: object         # list[str] | MethodCall
    method:   str
    args:     "object"       # list[Arg] (call) | None (member read on a result)
    begin:    int


@dataclass(frozen=True)
class Comparison:
    """A comparison: '<algebr> <op-cmp> <algebr>' -- the num->bool crossing (D-13).

    'op' is one of '>=', '<=', '==', '!=', '>', '<' (verbatim). 'left'/'right'
    are algebraic expressions (a BinOp, UnOp, Bridge, Literal, OpaqueCode, or a
    bare <name-dotted> segment list). That the two sides resolve to comparable
    scalars is a pass-2 check (F-5).
    """
    left:  "object"          # algebraic expression
    op:    str
    right: "object"          # algebraic expression
    begin: int


@dataclass(frozen=True)
class UnOp(SEQ_Interface):
    """A unary operation: 'not <cond-atom>' or '- <alg-atom>' (D-13).

    'op' is 'not' (boolean negation) or '-' (arithmetic negation), verbatim.
    'operand' is the negated expression. Built by the cond-not / alg-un folds,
    which forward a plain (un-prefixed) operand unchanged, so a UnOp always
    carries a real prefix.
    """
    op:      str             # 'not' | '-'
    operand: "object"
    begin:   int


@dataclass(frozen=True)
class BinOp(SEQ_Interface):
    """A binary operation, left-associative (D-13).

    One node for every infix operator in both ladders: boolean
    'or'/'nor'/'xor'/'nxor'/'and'/'nand', arithmetic '+'/'-'/'*', and the shifts
    'shl:'/'shr:'. 'op' is the verbatim operator; 'left'/'right' are the operands
    (each a BinOp, UnOp, Bridge, Comparison, Literal, BoolRef, OpaqueCode, or a
    bare <name-dotted> segment list). The left-fold builder collapses a level
    with no operator to its bare head, so a BinOp always carries a real operator.
    Operator kind and operand kinds are pass-2 concerns (F-5).
    """
    op:    str
    left:  "object"
    right: "object"
    begin: int


@dataclass(frozen=True)
class Expr(SEQ_Interface):
    """An algebraic expression carrying an explicit division-fallback (D-23).

    'body undef: fallback' -- the optional 'undef:' supplies the value the
    expression takes when a math operation inside 'body' is undefined (divide by
    zero, a domain error on a math function). 'undef:' is DISTINCT from the
    conditional 'else:' (the bridge's false-branch, recip's zero-guard body), so
    a math fallback never collides with a structural 'else:'.
    The PARSER accepts 'undef:' on any expression; the SEMANTIC layer REQUIRES it
    when (and only when) a math exception can arise in 'body' -- in practice when
    a '/' is present -- and rejects it as dead otherwise. This node exists only
    when the 'undef:' fired -- a fallback-free expression is its bare 'body'
    value (the factory passes it through), so adding the clause never reshapes
    existing trees.
    """
    body:     "object"
    fallback: "object"
    begin:    int

    @classmethod
    def from_seq(cls, node):
        """RETURN: Expr if an 'undef:' fallback is present, else the bare body.

        children = (shift-body, opt_undef): 'undef:' is silent, so the optional's
        child (when present) is the one-survivor SEQ around the fallback <shift>.
        Absent -> the body value is forwarded unchanged, keeping a fallback-free
        expression identical to its pre-D-23 shape.
        """
        body    = node.children[0]
        opt_undef = node.children[1]
        if not opt_undef.present:
            return body
        fallback = opt_undef.child.children[0]
        begin = getattr(body, "begin", node.begin)
        return cls(body=body, fallback=fallback, begin=begin)


@dataclass(frozen=True)
class Bridge(SEQ_Interface):
    """The '?' bridge: the only bool->num crossing (D-13).

    '? <cond> then: <algebr> else: <algebr>' -- evaluates 'cond' and yields
    'then_' or 'else_' accordingly, the single explicit way a condition feeds an
    algebraic expression. 'cond' is a boolean expression; 'then_'/'else_' are
    algebraic expressions.
    """
    cond:  "object"
    then_: "object"
    else_: "object"
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: Bridge -- children = (?, cond, then-algebr, else-algebr).

        'then:'/'else:' are silent; the leading '?' is captured (its position
        anchors the node) and otherwise unused.
        """
        q, cond, then_, else_ = node.children
        return cls(cond=cond, then_=then_, else_=else_, begin=q.begin)


@dataclass(frozen=True)
class Condition(SEQ_Interface):
    """The root of a bracket guard '[ ... ]' -- the sole guard form.

    'expr' is the top boolean expression (a BinOp, UnOp, Comparison, BoolRef, or
    Literal). Wrapping it in a named root gives Cause.guard a single concrete
    node kind; a guard never carries an opaque Luau span (values cross from Luau
    only via 'is:').
    """
    expr:  "object"
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: Condition, the root of a '[ ... ]' bracket guard.

        children = (expr,): the single top boolean expression ('[' / ']' are
        silent). The bracket condition is the only guard form Cause.guard ever
        holds.
        """
        return cls(expr=node.children[0], begin=node.begin)


@dataclass(frozen=True)
class Cause(OR_Interface):
    """A cause: a trigger with an optional guard.

    'guard' is the Condition gating the trigger ('& [ ... ]'), or None when
    absent; it expresses "the event fired AND this holds". Built by the
    cause-system builder (system keyword trigger) and by the cause-named builder
    for the paren-less branch (inline named trigger); the paren branch builds a
    CauseRef instead -- the parens decide (D-26).
    """
    trigger: Trigger
    guard:   "Optional[Condition]"   # Condition | None
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
    value: object            # str (literal) | OpaqueCode | list[str] | expr node
    kind:  "E_ArgKind"
    begin: int

    @classmethod
    def _classify(cls, value, name, begin):
        """RETURN: Arg, classifying an <algebr> 'value' into its E_ArgKind (D-13).

        A segment list is a NAME; an OpaqueCode (or raw opaque span) is LUAU; a
        Literal node (or value-bearing token / bare str) carries its text as a
        LITERAL; any other expression node -- BinOp, UnOp, Bridge, Comparison --
        is a compound EXPR carried whole.
        """
        from vut.engine.temporal_logic.world.span_oracle import SpanResult
        if isinstance(value, list):
            return cls(name=name, value=value, kind=E_ArgKind.NAME, begin=begin)
        if isinstance(value, OpaqueCode):
            return cls(name=name, value=value, kind=E_ArgKind.LUAU, begin=begin)
        if isinstance(value, SpanResult):
            return cls(name=name, value=OpaqueCode.from_span(value),
                       kind=E_ArgKind.LUAU, begin=begin)
        if isinstance(value, Literal):
            return cls(name=name, value=value.text, kind=E_ArgKind.LITERAL,
                       begin=begin)
        if isinstance(value, str) or hasattr(value, "text"):
            text = value if isinstance(value, str) else value.text
            return cls(name=name, value=text, kind=E_ArgKind.LITERAL, begin=begin)
        return cls(name=name, value=value, kind=E_ArgKind.EXPR, begin=begin)

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
    """A mode-arming effect: 'arm: name(args)'.

    DORMANT (grammar collapse, disc-7 / D-36): the parser NO LONGER produces this
    node. Since '=> arm: Mode' collapsed to a bare '=> Mode', an arm-target now
    parses as EventSpec/EffectRef (or a clockwork name-step), and PASS 2 finalizes
    it into a ModeArming once the target resolves to kind mode/state -- a shallow
    interface-preserving substitution. Kept as that finalization target; not
    constructed at parse time. 'from_seq' is retained for pass 2 to build one.
    """
    name:  "list[str]"        # dotted-name segments
    args:  List[Arg]
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: ModeArming -- children = (dotted_name, args_list); 'arm:' silent.

        Retained for PASS 2 finalization (D-36), not parse-time construction."""
        name, args = node.children
        return cls(name=name, args=args, begin=node.begin)


@dataclass(frozen=True)
class Spawn(SEQ_Interface):
    """An aggregate-spawning effect: 'spawn: name (args) [ into: target ]'.

    Targets a <mode-group> or <state-machine> type. One shape with one optional
    'into:' clause:
      - 'args' is the instantiation argument list; the parentheses are MANDATORY
        (a bare 'spawn: name' is rejected by the grammar). 'args' is empty when the
        type takes none ('spawn: name()').
      - 'into_container' names the declared container that catches the fresh
        instance ('into: roster' / 'into: roster[e.id]'), or None for the
        per-kind default container; resolved in pass 2 to a dict/list
        declaration.
      - 'key' is the dict key the instance is held under, a name-dotted segment
        list ('into: roster[e.id]'), or None. None with a container means a LIST
        target -- the instance APPENDS. A key on a list, or its absence on a
        dict, is a pass-2 error (the container's declared kind decides).
    'has_parens' is always True for a parsed node (the parens are mandatory);
    retained for the builder and downstream, no longer a shape discriminant.
    """
    name:           "list[str]"  # name-dotted segments
    args:           List[Arg]
    has_parens:     bool
    into_container: "Optional[list[str]]"  # name-dotted segments, or None
    key:            "Optional[list[str]]"  # dict key segments; None = list append
    begin:          int

    @classmethod
    def from_seq(cls, node):
        """RETURN: Spawn, 'spawn: name (args) [ into: C [ "[" key "]" ] ]'.

        ROLE-KEYED at the FLAT level only (D-18, B2): 'name' is read by its
        '<name-dotted(aggregate)>' role, immune to the silent 'spawn:' and any
        future discriminant on this sequence. The args and the optional 'into:'
        clause stay POSITIONAL: 'children' here is (aggregate, parens-arg,
        opt_into) -- 'spawn:' silent, the parens-arg an unroled SEQ at slot 1,
        the optional an OPT_Node at slot 2. The 'into:' target ('container',
        'key') is tagged one rule DOWN, inside <spawn-into>, reached through this
        OPT_Node and an anonymous inline SEQ; the container now reads by ROLE off
        the 'step/spawn/into' member node (D-22), and only the key keeps a single
        optional unwrap -- the residual boundary is one hop, not the former two.
        """
        name = node["aggregate"]
        # Positional below: parens-arg at slot 1, the into-optional at slot 2.
        args    = node.children[1]
        opt_into = node.children[2]
        into_container = None
        key            = None
        if opt_into.present:
            # opt_into wraps the one-survivor SEQ around <into> ('into:' silent);
            # its first child is the 'step/spawn/into' SEQ_Node, which tags its
            # container slot (D-22 made <into> a roled subspace member), so the
            # container reads by ROLE -- drift-proof. The optional key sits one
            # level down inside <into>'s own '[' ... ']' optional, whose role tag
            # does not surface at this SEQ level, so the key keeps a one-level
            # optional unwrap (the residual B2 boundary, now just one hop).
            into           = opt_into.child.children[0]
            into_container = into["container"]
            opt_key        = into.children[1]
            if opt_key.present:
                key = opt_key.child.children[0]
        return cls(name=name, args=args, has_parens=True,
                   into_container=into_container, key=key,
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
    """A mutation effect: a statement-block CODE BLOCK after '=>'.

    'body' is the code block -- an OpaqueCode (opaque Luau '{ ... }') or a
    DoSweep ('do: <step>+ :end'); the sweep is the rule-plane alternative to a
    Luau statement block. A DoSweep body carries its one-sweep restriction via a
    role hint read in pass-2.
    """
    body:  object            # OpaqueCode | DoSweep
    begin: int

    @classmethod
    def from_block(cls, block):
        """RETURN: Mutation, wrapping a code-block value.

        The <mutation> rule is the single reference '<code-block>', so its value
        is the already-built block (an OpaqueCode | DoSweep), passed straight in.
        """
        return cls(body=block, begin=block.begin)


@dataclass(frozen=True)
class InitBlock(SEQ_Interface):
    """An 'init: <code-block>' member: its statement-block body.

    'body' is the code block (OpaqueCode | DoSweep), as for a mutation. A
    distinct type (vs DeinitBlock) so a mode/state-machine assembler can sort
    interleaved members by kind rather than by source position.
    """
    body:  object            # OpaqueCode | DoSweep
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: InitBlock -- children = (code-block,), an OpaqueCode | DoSweep."""
        body = node.children[0]
        return cls(body=body, begin=body.begin)


@dataclass(frozen=True)
class DeinitBlock(SEQ_Interface):
    """A 'deinit: <code-block>' member: its statement-block body. See InitBlock."""
    body:  object            # OpaqueCode | DoSweep
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: DeinitBlock -- children = (code-block,), an OpaqueCode | DoSweep."""
        body = node.children[0]
        return cls(body=body, begin=body.begin)


@dataclass(frozen=True)
class Causality(SEQ_Interface, TopLevel):
    """A full rule: 'on: <cause> (=> <effect>)+'.

    'effects' holds the ordered effect nodes (EventSpec, EffectRef, ModeArming,
    Unspawn, ReportString, Mutation). A Mutation's body may itself be a 'do:'
    sweep (a DoSweep) rather than opaque Luau -- the sweep is an alternative to
    a Luau code block at every statement-block site. Spawn and container writes
    are NOT effects: they appear only inside a clockwork or sweep body (D-16).
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
class DictType(SEQ_Interface):
    """A 'dict<K,V>' type: a map from one key type to one value type.

    'key'/'value' are each a <type>: a built-in scalar word (str), a named user
    type (str), or a nested DictType/ListType. The type words' resolution is a
    pass-2 concern. Used both as a declaration kind (DictDecl.dtype) and as a
    nested type parameter inside another container type.
    """
    key:   object            # str | DictType | ListType
    value: object            # str | DictType | ListType
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: DictType, 'dict < <type> , <type> >'.

        Reads the key/value type slots by ROLE (D-18): the grammar tags them
        '<type(key)>' / '<type(value)>', so 'dict' and the '<'/'>' captured
        discriminants -- present in 'children' but unroled -- are never named
        and their slots cannot drift the read. ',' is silent.
        """
        return cls(key=node["key"], value=node["value"],
                   begin=node.begin)


@dataclass(frozen=True)
class ListType(SEQ_Interface):
    """A 'list<V>' type: an ordered sequence of one element type.

    'element' is a <type> (built-in scalar word, named type, or nested
    DictType/ListType), resolved in pass 2. Used as a declaration kind
    (ListDecl.dtype) and as a nested type parameter.
    """
    element: object          # str | DictType | ListType
    begin:   int

    @classmethod
    def from_seq(cls, node):
        """RETURN: ListType, 'list < <type> >'.

        Reads the element type by ROLE (D-18): the grammar tags it
        '<type(element)>', so 'list' and the captured '<'/'>' -- unroled slots
        in 'children' -- cannot drift the read.
        """
        return cls(element=node["element"], begin=node.begin)


@dataclass(frozen=True)
class DictDecl(TopLevel):
    """A dict declaration: '<name> is: dict<K,V> [by: {lvalue}]'.

    'dtype' is the DictType (key and value types). A container has no
    constructor signature -- the angle brackets say what it holds -- yet the
    grammar admits a head signature on the shared declaration head, so
    'head_params' records what was written for the pass-2 kind-vs-shape check
    (F-2). 'by' is the optional script binding: an LVALUE opaque span giving the
    engine-owned container an EXISTING opaque-code reference, or None.
    """
    name:        str
    dtype:       "DictType"
    by:          Optional["OpaqueCode"]
    head_params: List["ArgDecl"]
    begin:       int


@dataclass(frozen=True)
class ListDecl(TopLevel):
    """A list declaration: '<name> is: list<V> [by: {lvalue}]'.

    'dtype' is the ListType (element type). 'head_params'/'by' as on DictDecl.
    """
    name:        str
    dtype:       "ListType"
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
    (a Condition tree), never another cause reference: no alias chains.
    Resolution of references against this definition is a pass-2
    concern; the parser only records it.
    """
    name:      "list[str]"     # name-dotted segments from the signature
    params:    List[ArgDecl]
    for_event: "list[str]"     # name-dotted segments of the bound event
    guard:     "Condition"
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
    guard: "Optional[Condition]" # Condition | None -- parsed, pass-2 F-7
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
class Assign(SEQ_Interface):
    """An assignment statement: '<lvalue> gets: <algebr>' (D-13).

    A clockwork-fenced mutation -- the analysable counterpart of an opaque
    '{ ... }' block. 'lvalue' is the target <name-dotted> segment list; 'rhs' is
    the assigned algebraic expression. State mutates only here (and via incr/
    decr/recip), inside a clockwork body, so every write has a tick to anchor it.
    """
    lvalue: "list[str]"
    rhs:    "object"
    begin:  int


@dataclass(frozen=True)
class Recip(SEQ_Interface):
    """A guarded reciprocal: '<lvalue> recip: <algebr> else: <body> :end' (D-13).

    Sets 'lvalue' to 1/(operand) when the operand is non-zero, else runs
    'else_body'. The only division path in the language, total by construction:
    the zero case is never silent -- it is the mandatory 'else_body'. The operand
    is promoted to float (the one implicit-promotion site). 'else_body' is the
    ordered clockwork steps run on zero.
    """
    lvalue:    "list[str]"
    operand:   "object"
    else_body: List["object"]
    begin:     int


@dataclass(frozen=True)
class Incr(SEQ_Interface):
    """A saturating increment: 'incr: <lvalue> [by: <algebr>] [to: <algebr>]' (D-13).

    Increases 'lvalue' by 'amount' (None -> the default step, pass 2), optionally
    clamped at the ceiling 'limit' (None -> unbounded). Clockwork-fenced. The
    saturate-vs-guard reading of 'limit' is a pass-2 semantic (F-15).
    """
    lvalue: "list[str]"
    amount: "object"         # algebr | None
    limit:  "object"         # algebr | None
    begin:  int

    @classmethod
    def from_seq(cls, node):
        """RETURN: Incr -- children = (lvalue, opt_by, opt_to); keywords silent.

        Each optional is an OPT_Node at a stable slot; present yields the
        anonymous one-survivor SEQ around its <algebr> ('by:'/'to:' silent).
        """
        lvalue, opt_by, opt_to = node.children
        amount = opt_by.child.children[0] if opt_by.present else None
        limit  = opt_to.child.children[0] if opt_to.present else None
        return cls(lvalue=lvalue, amount=amount, limit=limit, begin=node.begin)


@dataclass(frozen=True)
class Decr(SEQ_Interface):
    """A saturating decrement: 'decr: <lvalue> [by: <algebr>] [to: <algebr>]' (D-13).

    Decreases 'lvalue' by 'amount' (None -> default step), optionally clamped at
    the floor 'limit'. The decrement twin of Incr; see it for the slot layout
    and the pass-2 notes.
    """
    lvalue: "list[str]"
    amount: "object"
    limit:  "object"
    begin:  int

    @classmethod
    def from_seq(cls, node):
        """RETURN: Decr -- children = (lvalue, opt_by, opt_to); keywords silent."""
        lvalue, opt_by, opt_to = node.children
        amount = opt_by.child.children[0] if opt_by.present else None
        limit  = opt_to.child.children[0] if opt_to.present else None
        return cls(lvalue=lvalue, amount=amount, limit=limit, begin=node.begin)


@dataclass(frozen=True)
class Instant(SEQ_Interface):
    """An immediate-injection step: 'instant: name(args)'.

    A tick-free clockwork stimulus -- the named event with its mandatory argument
    list is injected into the CURRENT event queue at the present instant, off
    the clockwork's clock beat (D-11). The paced counterpart is a bare EventSpec
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

    Suspends the clockwork script until 'cause' fires. 'effects' is the optional
    co-temporal tail (possibly empty), run with 'e' bound to the firing event
    -- 'e' does not flow into subsequent steps. A tail-less wait is a pure
    progression gate. Resumption is at the clockwork's next own-clock tick (D-11).
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

    A tick-free control frame fencing step sequences inside an clockwork body. 'arms'
    is the list of (guard, body) pairs -- the leading 'if:' and each 'elif:', in
    source order; 'else_body' is the trailing 'else:' steps or None. The whole
    if/elif/else chain is closed by ONE ':end'. Conditions reuse <guard> (a
    Condition tree); 'e' is not in scope (D-11).
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
    guard: "Condition"        # bracket condition '[ ... ]'
    body:  List[object]       # clockwork steps
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: WhileFrame -- children = (guard, PLUS(steps)); ':end' silent."""
        guard = node.children[0]
        body  = list(node.children[1].items)
        return cls(guard=guard, body=body, begin=node.begin)


@dataclass(frozen=True)
class Clockwork(SEQ_Interface, TopLevel):
    """An clockwork definition: a tick-scripted stimulus actor, closed by ':end'.

    'name'/'params' come from the signature; the params ARE the instance
    members, read through the 'cw' self-binding (D-11). 'clock' is the 'on:'
    <cause> -- a trigger (resolved to a clock in pass 2) with an optional guard,
    the heartbeat shape. 'init'/'deinit' are STATEMENT_BLOCK OpaqueCode spans or
    None. 'steps' are the ordered body steps: EventSpec (paced emission),
    Instant, WaitLine, SelectFrame, IfFrame, WhileFrame, and the bare commands
    (Spawn, Unspawn, ModeArming, Mutation). No inheritance: an clockwork carries no
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
        """RETURN: Clockwork -- children = (signature, cause, PLUS(elements)).

        'clockwork:', 'on:', ':end' silent. The signature is the (name, params)
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


@dataclass(frozen=True)
class DoSweep(SEQ_Interface):
    """A one-sweep clockwork body as a causality reaction: 'do: <step>+ :end'.

    The heartbeat-free alternative to an effect list: the causality's cause
    triggers this body, which runs to completion in a SINGLE sweep. It is where
    container writes and other clockwork-only statements (spawn, gets:, incr:,
    instant:, ...) run from a causality, mixed freely with '{ luau }' segments.
    No signature, no inner 'on:', no init/deinit -- just 'steps'. The grammar
    admits the full step vocabulary; the one-sweep restrictions (no heartbeat,
    so 'while:', the heartbeat-shaped 'wait:'/'select:', and bare events are
    flagged) are pass-2 checks, not parse errors.
    """
    steps: List[object]
    begin: int

    @classmethod
    def from_seq(cls, node):
        """RETURN: DoSweep -- children = (PLUS(step-clockwork),).

        'do:'/':end' silent. Body steps keep source order; no init/deinit (those
        are lifecycle hooks of a named actor, absent here).
        """
        return cls(steps=list(node.children[0].items), begin=node.begin)


@dataclass
class ModuleRoot:
    """The whole parsed module: an ordered list of top-level constructs.

    'items' holds Namespace, Import, Causality, Mode, ModeGroup, StateMachine,
    Clockwork, declaration (ReactorDecl/StructDecl/ContainerDecl/VariableDef),
    EventDef, ClockDef, CauseDef and EffectDef nodes in source order. A mutable
    container so the parser can append as it goes.
    """
    items: "List[TopLevel]" = field(default_factory=list)
