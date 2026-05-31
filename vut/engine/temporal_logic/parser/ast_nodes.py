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

from vut.engine.temporal_logic.luau.luau_fragment import Role


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
    """A mode-arming effect: '+ name(args)'."""
    name:  str
    args:  List[Arg]
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
class Causality:
    """A full rule: 'on <cause> (=> <effect>)+ off'.

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
class Mode:
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
class StateMachineModeRef:
    """A reference 'SM.member' or 'SM.VOID' used by 'default ='."""
    sm_name:   str
    mode_name: str          # 'VOID' when the implicit void member is meant
    is_void:   bool
    begin:     int


@dataclass(frozen=True)
class StateMachine:
    """A state-machine definition: members, one 'default', mandatory 'until's.

    'default' is the single StateMachineModeRef ('default =' target) or None if
    the author omitted it (a validator-pass error, not a parser error).
    """
    name:    str
    params:  List[ArgDecl]
    default: Optional[StateMachineModeRef]
    init:    Optional[Luau]
    deinit:  Optional[Luau]
    untils:  List[Cause]
    begin:   int


@dataclass(frozen=True)
class EventDef:
    """An event declaration: 'event name(arg-decls)'."""
    name:   str
    params: List[ArgDecl]
    begin:  int


@dataclass(frozen=True)
class ClockDef:
    """A clock declaration: 'clock event-name number'."""
    name:   str
    period: str             # NUMBER lexeme, kept verbatim
    begin:  int


@dataclass
class RuleFile:
    """The whole parsed rule file: an ordered list of top-level constructs.

    'items' holds Causality, Mode, StateMachine, EventDef and ClockDef nodes in
    source order. A mutable container so the parser can append as it goes.
    """
    items: List[object] = field(default_factory=list)
