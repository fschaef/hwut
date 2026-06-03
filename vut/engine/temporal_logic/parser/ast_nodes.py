"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

ABSTRACT SYNTAX TREE NODES

Pure data structures for the rule-file grammar (SYNTAX section A.1). Every node
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
from typing      import List, Optional

from ..luau.luau_fragment import Role


from abc import ABC


class TopLevel(ABC):
    """Abstract base for the constructs that may appear at rule-file top level.

    Namespace, Include, Causality, Mode, ModeGroup, StateMachine, EventDef and
    ClockDef derive from it, so 'RuleFile.items' is typed as list[TopLevel] and
    only these node kinds are admissible there. A Namespace nests further
    TopLevel items (Causality, Mode, ModeGroup, StateMachine, Singleton,
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
    """A cause trigger: an event name or an implicit keyword (ANY/BEGIN/END/
    switched).

    'name' is the identifier or keyword lexeme. 'is_keyword' True marks the
    implicit triggers, distinguishing 'END' the system event from a user event
    that happens to be spelled END elsewhere.
    """
    name:       str
    is_keyword: bool
    begin:      int


@dataclass(frozen=True)
class Cause:
    """A cause: a trigger with an optional guard.

    'guard' is the CONDITION Luau span after '&', or None when absent.
    """
    trigger: Trigger
    guard:   Optional[Luau]
    begin:   int


@dataclass(frozen=True)
class Arg:
    """One argument of an event-spec or mode-arming: optional member, rvalue.

    'member' is the 'name=' target or None for positional. 'value' is the
    rvalue: a NUMBER/STRING lexeme carried as text, or an EXPRESSION Luau span.
    'is_luau' True iff 'value' is a Luau span rather than a literal lexeme.
    """
    member:  Optional[str]
    value:   object          # str (number/string literal) | Luau
    is_luau: bool
    begin:   int


@dataclass(frozen=True)
class EventSpec:
    """An event emission effect: 'name(args)'."""
    name:  str
    args:  List[Arg]
    begin: int


@dataclass(frozen=True)
class ModeArming:
    """A mode-arming effect: '! name(args)'."""
    name:  str
    args:  List[Arg]
    begin: int


@dataclass(frozen=True)
class Spawn:
    """An aggregate-spawning effect: '+! name [ (args) ] [ in {lvalue} ]'.

    Targets a <mode-group> or <state-machine> type. Three shapes, distinguished
    by which fields are set:
      - singleton re-init: 'has_parens' False, 'container' None -- the bare type
        name, admissible only for a 'singleton :'-declared type; re-inits the
        one declared instance with its declaration-fixed arguments.
      - default-container spawn: 'has_parens' True, 'container' None -- offers a
        fresh instance to the per-kind default container.
      - container spawn: 'container' is the opaque Luau lvalue span -- offers a
        fresh instance to that container.
    'args' is empty for the singleton form (parentheses are a syntax error
    there). 'container' is a Luau node (opaque lvalue) or None; the parser does
    not resolve it.
    """
    name:       str
    args:       List[Arg]
    has_parens: bool
    container:  Optional["Luau"]
    begin:      int


@dataclass(frozen=True)
class Unspawn:
    """An existence-ending effect: '-! name'.

    'name' references a spawned aggregate by bare or dotted name. Ending an
    existence runs the instance's 'deinit' and releases it from its container.
    Pass-2 validation enforces that the target resolves to an existing
    instance; the grammar accepts any dotted name.
    """
    name:  str
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
    name:        str
    params:      List[ArgDecl]
    init:        Optional[Luau]
    deinit:      Optional[Luau]
    causalities: List[Causality]
    untils:      List[Cause]
    begin:       int


@dataclass(frozen=True)
class State:
    """A state: a mode living in a state machine, closed by 'until switched'.

    Same body shape as Mode. 'untils' are the optional preceding explicit
    'until' causes (possibly empty); the mandatory 'until switched' closer is
    implied by the node kind and carries no field. Not a TopLevel: a state
    appears only inside a <state-machine>.
    """
    name:        str
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
    name:     str
    params:   List[ArgDecl]
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
    name:     str
    params:   List[ArgDecl]
    modes:    List[Mode]
    has_refs: List[HasRef]
    init:     Optional[Luau]
    deinit:   Optional[Luau]
    begin:    int


@dataclass(frozen=True)
class Singleton(TopLevel):
    """A singleton declaration: 'singleton : name [ (arg-decls-as-args) ]'.

    Declares an aggregate type to have exactly one instance, identified by
    'name', with the argument list fixed here. The type is thereafter spawned
    only by the bracketless '+! name' re-init form. 'args' carries the fixed
    arguments (an empty list when none were given).
    """
    name:  str
    args:  List[Arg]
    begin: int


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
class Include(TopLevel):
    """A file mount: 'include "<file>" as <dotted-name>'.

    'filename' is the included file's name (the string lexeme, quotes stripped).
    'mount' is the dotted path at which the file's namespace is mounted in THIS
    file. The included file is placement-agnostic; the including file chooses
    the mount point. Resolving and mounting the file is a semantic-pass concern;
    the parser only records the request.
    """
    filename: str
    mount:    str
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
    name:  str
    items: "List[TopLevel]"
    begin: int


@dataclass
class RuleFile:
    """The whole parsed rule file: an ordered list of top-level constructs.

    'items' holds Namespace, Include, Causality, Mode, ModeGroup, StateMachine,
    Singleton, EventDef and ClockDef nodes in source order. A mutable container
    so the parser can append as it goes.
    """
    items: "List[TopLevel]" = field(default_factory=list)
