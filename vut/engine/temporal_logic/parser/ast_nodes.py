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


class TopLevel(ABC):
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


@dataclass(frozen=True)
class Trigger:
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

@dataclass(frozen=True)
class EventMember:
    """A reference to a member of the triggering event: '.name'.

    Leading-dot, single-level. The event is implicit -- the one named by the
    trigger this guard gates -- so only the member 'name' is recorded. Binding
    the name to a declared event member is a pass-2 concern.
    """
    name:  str
    begin: int


@dataclass(frozen=True)
class Literal:
    """A number or string literal operand in a comparison.

    'text' is the verbatim lexeme (a number, or a string WITH its quotes); the
    static layer interprets it against the compared member's type.
    """
    text:  str
    begin: int


@dataclass(frozen=True)
class Comparison:
    """A single comparison: '<evt-member> <op> <operand>'.

    'op' is one of '>=', '<=', '==', '!=', '>', '<' (verbatim). 'left' is always
    an EventMember; 'right' is an EventMember or a Literal.
    """
    left:  EventMember
    op:    str
    right: "object"          # EventMember | Literal
    begin: int


@dataclass(frozen=True)
class Not:
    """A negated condition: 'not <cond-atom>'."""
    operand: "object"        # Comparison | Not | BoolOp
    begin:   int


@dataclass(frozen=True)
class BoolOp:
    """An 'and'/'or' chain of two or more operands.

    'op' is 'and' or 'or'. 'operands' are the flattened terms at this precedence
    level (left-associative, but associativity is irrelevant for and/or). A
    single-operand level is collapsed by the builder, so a BoolOp always holds at
    least two operands.
    """
    op:       str            # 'and' | 'or'
    operands: List["object"]
    begin:    int


@dataclass(frozen=True)
class Condition:
    """The root of a bracket guard '[ ... ]'.

    'expr' is the top boolean expression (a BoolOp, Not, or Comparison). Wrapping
    it in a named root keeps a guard's two forms -- Luau span vs. bracket
    condition -- as two distinct, type-distinguishable node kinds on Cause.guard.
    """
    expr:  "object"
    begin: int


@dataclass(frozen=True)
class Cause:
    """A cause: a trigger with an optional guard.

    'guard' is the condition gating the trigger, or None when absent. It is
    either a Luau CONDITION span (the '& { ... }' form) or a Condition tree (the
    '& [ ... ]' bracket form); both express "the event fired AND this holds".
    """
    trigger: Trigger
    guard:   "Optional[object]"   # Luau | Condition | None
    begin:   int


@dataclass(frozen=True)
class ShallowMemberAccess:
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


@dataclass(frozen=True)
class Arg:
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


@dataclass(frozen=True)
class EventSpec:
    """An event emission effect: 'name(args)'."""
    name:  "list[str]"        # dotted-name segments
    args:  List[Arg]
    begin: int


@dataclass(frozen=True)
class ModeArming:
    """A mode-arming effect: '! name(args)'."""
    name:  "list[str]"        # dotted-name segments
    args:  List[Arg]
    begin: int


@dataclass(frozen=True)
class Spawn:
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


@dataclass(frozen=True)
class Unspawn:
    """An existence-ending effect: '-! name'.

    'name' references a spawned aggregate by bare or dotted name. Ending an
    existence runs the instance's 'deinit' and releases it from its container.
    Pass-2 validation enforces that the target resolves to an existing
    instance; the grammar accepts any dotted name.
    """
    name:  "list[str]"        # dotted-name segments
    begin: int


@dataclass(frozen=True)
class ReportString:
    """A report-string effect: an interpolated '\"...\"' line."""
    text:  str
    begin: int


@dataclass(frozen=True)
class Mutation:
    """A mutation effect: a STATEMENT_BLOCK Luau span after '=>'."""
    body:  Luau
    begin: int


@dataclass(frozen=True)
class InitBlock:
    """An 'init { ... }' member: its STATEMENT_BLOCK body.

    A distinct type (vs DeinitBlock) so a mode/state-machine assembler can sort
    interleaved members by kind rather than by source position.
    """
    body:  Luau
    begin: int


@dataclass(frozen=True)
class DeinitBlock:
    """A 'deinit { ... }' member: its STATEMENT_BLOCK body. See InitBlock."""
    body:  Luau
    begin: int


@dataclass(frozen=True)
class Causality(TopLevel):
    """A full rule: 'on <cause> (=> <effect>)+'.

    'effects' holds the ordered effect nodes (EventSpec, ModeArming,
    ReportString, Mutation).
    """
    cause:   Cause
    effects: List[object]
    begin:   int


@dataclass(frozen=True)
class ArgDecl:
    """One parameter declaration: 'member : type'."""
    member: str
    type:   str
    begin:  int


@dataclass(frozen=True)
class Mode(TopLevel):
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


@dataclass(frozen=True)
class State:
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


@dataclass(frozen=True)
class HasRef:
    """A 'has: <member-ref>' element pulling in a member defined elsewhere.

    'aggregate' is the qualifier of 'AGG.member' or None for a bare name.
    'member' is the referenced reactor name ('VOID' with 'is_void' True names
    the implicit void state).
    """
    aggregate: Optional[str]
    member:    str
    is_void:   bool
    begin:     int


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


@dataclass(frozen=True)
class StateMachineModeRef:
    """A reference 'SM.member' or 'SM.VOID' used by 'default ='."""
    sm_name:   str
    mode_name: str          # 'VOID' when the implicit void member is meant
    is_void:   bool
    begin:     int


@dataclass(frozen=True)
class StateMachine(TopLevel):
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


@dataclass(frozen=True)
class ModeGroup(TopLevel):
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


@dataclass(frozen=True)
class EventDef(TopLevel):
    """An event declaration: 'event name(arg-decls)'."""
    name:   str
    params: List[ArgDecl]
    begin:  int


@dataclass(frozen=True)
class ClockDef(TopLevel):
    """A clock declaration: 'clock event-name number'."""
    name:   str
    period: str             # NUMBER lexeme, kept verbatim
    begin:  int


@dataclass(frozen=True)
class CauseDef(TopLevel):
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


@dataclass(frozen=True)
class EffectDef(TopLevel):
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


@dataclass(frozen=True)
class CauseRef:
    """A reference to a defined cause, invoked with arguments: 'NAME(args)'.

    Appears in cause position of a causality rule as an alternative to an inline
    trigger. 'name' is the cause's identifier; 'args' are the actual arguments
    bound to the definition's parameters. Binding the args to a CauseDef and
    checking arity/types is a pass-2 concern.
    """
    name:  str
    args:  List["Arg"]
    begin: int


@dataclass(frozen=True)
class EffectRef:
    """A reference to a defined effect bundle, by bare name: 'NAME'.

    Appears in effect position of a causality rule as an alternative to an inline
    effect. 'name' is the bundle's identifier; expanding it to the defined
    effects is a pass-2 concern. The name is a single identifier, never dotted.
    """
    name:  str
    begin: int


@dataclass(frozen=True)
class Include(TopLevel):
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


@dataclass(frozen=True)
class Namespace(TopLevel):
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


@dataclass
class RuleFile:
    """The whole parsed rule file: an ordered list of top-level constructs.

    'items' holds Namespace, Include, Causality, Mode, ModeGroup, StateMachine,
    ForwardDecl, EventDef and ClockDef nodes in source order. A mutable container
    so the parser can append as it goes.
    """
    items: "List[TopLevel]" = field(default_factory=list)


