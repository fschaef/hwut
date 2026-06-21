"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

SCOPE TREE  (pass 2, README B)

The TYPE plane: a tree of Scopes, each holding the Symbols declared directly in
it. Four kinds open a scope -- GROUND (file root), NAMESPACE, MODE GROUP, STATE
MACHINE; everything else (modes, states, events, clocks, variables, structs,
cause/effect defs, containers) is a Symbol in its containing scope and opens no
scope of its own.

The build is STACKLESS over Module.items: a single forward sweep carrying an
explicit work-list of (item, target-scope) frames, never interpreter recursion,
so a deep namespace nest is bounded by memory not the call stack (the house
rule, README VOCABULARY). A scope SEALS the moment its items are exhausted; a
sealed scope is final and is never reopened (the seal law). Sealing is what a
later mount must respect (D-3) and what 'closed scopes are complete' means.

Parameters are NOT scope symbols. A declaration's signature/member list rides
on its Symbol as a flat ordered list of (member-name, member-type) pairs (D-4);
'Traffic.threshold' therefore finds nothing in the scope tree, which is exactly
why a SCOPE-descent of it fails -- only an object has a threshold.

This module builds the tree and records the symbols; it does not RESOLVE
references (resolver.py) and does not run the consistency checks (checks.py). It
reports exactly two things itself, both at record time: a duplicate symbol
spelling in one scope, and a parameter spelling colliding with a mode/state of
the same aggregate (D-4 spelling check).
______________________________________________________________________________
"""
from dataclasses import dataclass, field
from enum        import Enum

from vut.engine.temporal_logic.semantic.diagnostics import (
    SemanticClass, semantic_error)
from vut.engine.temporal_logic.parser.ast_nodes import (
    Namespace, StateMachine, ModeGroup, Mode, State, StructDecl, EventDef,
    ClockDef, ReactorDecl, VariableDef, DictDecl, ListDecl, CauseDef, EffectDef,
    Import)


from vut.engine.temporal_logic.semantic.core.scope_types import (
    E_ScopeKind, Symbol, Scope)


# --- helpers reading the AST -------------------------------------------------

def _dotted(name) -> "list[str]":
    """RETURN: list[str], the dotted-name segments of 'name'.

    A declaration's 'name' field is either a plain str (event, clock, struct,
    container, variable) or a list[str] of dotted segments (namespace, mode,
    aggregate). Normalises both to a segment list so the build treats them
    uniformly.
    """
    if isinstance(name, str):
        return [name]
    return list(name)


def _params_of(item) -> "tuple[tuple[str, str], ...]":
    """RETURN: tuple of (member-name, member-type) pairs for 'item'.

    Reads the declaration's member list -- 'members' on a struct, 'params' on
    an aggregate/mode/event -- as ArgDecl(member, type, begin) nodes, and
    flattens each to a (member, type) pair (D-4 shape). An item with neither
    field yields the empty tuple.
    """
    decls = getattr(item, "members", None)
    if decls is None:
        decls = getattr(item, "params", None)
    if not decls:
        return ()
    return tuple((d.member, d.type) for d in decls)


def _aggregate_member_names(item) -> "list[str]":
    """RETURN: list[str], the spellings of the modes/states declared inside
              the aggregate 'item' (a StateMachine's states, a ModeGroup's
              modes), or [] for a non-aggregate.

    Used for the D-4 spelling check: a parameter may not share its spelling
    with a mode/state of the same aggregate.
    """
    members = getattr(item, "states", None)
    if members is None:
        members = getattr(item, "modes", None)
    if not members:
        return []
    out = []
    for m in members:
        out.extend(_dotted(m.name))
    return out


_KIND_OF_NODE = {
    "Mode":        "mode",
    "State":       "state",
    "StructDecl":  "struct",
    "EventDef":    "event",
    "ClockDef":    "clock",
    "VariableDef": "variable",
    "DictDecl":    "container",
    "ListDecl":    "container",
    "CauseDef":    "cause-def",
    "EffectDef":   "effect-def",
}


# --- the stackless build -----------------------------------------------------

def build_scopes(module, reporter) -> Scope:
    """RETURN: Scope, the sealed GROUND scope of this module's scope tree.

    A single stackless forward sweep over Module.items. Each opened scope is
    pushed with the count of items it must consume; when consumed, it seals.
    Namespace, StateMachine and ModeGroup open a child scope; every other
    declaration records a Symbol in the current scope. Modes/states are
    recorded as symbols of their aggregate's scope but open no scope of their
    own (their bodies define no names, D-4).

    Reports duplicate spellings and the D-4 parameter/state spelling collision
    as it goes; resolution of references is a later pass.
    """
    ground = Scope(kind=E_ScopeKind.GROUND, parent=None, name="")

    # Work-list of frames: (scope, iterator-over-its-items). Explicit, so
    # arbitrarily deep nesting never touches the interpreter call stack.
    work = [(ground, iter(module.items))]

    while work:
        scope, items = work[-1]
        nxt = next(items, _DONE)
        if nxt is _DONE:
            scope.sealed = True            # seal law: items exhausted -> final
            work.pop()
            continue

        opened = _open_scope_for(nxt, scope, reporter)
        if opened is not None:
            scope.children.append(opened)
            work.append((opened, iter(_nested_items(nxt))))
        else:
            _record_symbol(nxt, scope, reporter)

    return ground


_DONE = object()   # sentinel distinct from any AST item / None


def _open_scope_for(item, parent: Scope, reporter):
    """RETURN: Scope, a fresh child scope if 'item' opens one (Namespace,
              StateMachine, ModeGroup); None if 'item' is symbol-only.

    A Namespace opens one scope per declaration; its dotted name may nest
    several levels ('open a.b') -- modelled as one scope named by the full
    path, sealed as a unit (the seal law seals 'a' with 'b', README B). An
    aggregate (StateMachine/ModeGroup) opens its own scope AND is itself a
    symbol in the parent; the symbol is recorded here, the scope returned.
    """
    if isinstance(item, Namespace):
        return Scope(kind=E_ScopeKind.NAMESPACE, parent=parent,
                     name=".".join(_dotted(item.name)))

    if isinstance(item, (StateMachine, ModeGroup)):
        kind   = ("state-machine" if isinstance(item, StateMachine)
                  else "mode-group")
        s_kind = (E_ScopeKind.STATE_MACHINE if isinstance(item, StateMachine)
                  else E_ScopeKind.MODE_GROUP)
        params = _params_of(item)
        name   = ".".join(_dotted(item.name))
        parent.add_symbol(
            Symbol(name=name, kind=kind, params=params, offset=item.begin),
            reporter)
        _check_param_state_collision(item, params, reporter)
        return Scope(kind=s_kind, parent=parent, name=name)

    return None


def _nested_items(item) -> "list":
    """RETURN: list, the TopLevel items nested inside a scope-opening 'item'.

    A Namespace nests 'items'. An aggregate's modes/states are recorded as
    symbols of the aggregate scope (they open no scope themselves), so the
    aggregate contributes its modes/states here as the items its scope holds.
    """
    if isinstance(item, Namespace):
        return list(item.items)
    if isinstance(item, StateMachine):
        return list(item.states)
    if isinstance(item, ModeGroup):
        return list(item.modes)
    return []


def _record_symbol(item, scope: Scope, reporter):
    """RETURN: None. Records 'item' as a Symbol in 'scope' (or skips a node
              that contributes no scope symbol, e.g. an Import handled by the
              module manager).

    Reads the kind from the node type (or, for a ReactorDecl forward
    declaration, from its own 'kind' field), the name (normalised), the member
    list as (name, type) pairs, and the declaration offset. A Mode/State is
    recorded here too -- it is a symbol of its aggregate's scope but opens no
    scope. A forward declaration ('X is: mode') records the name and kind now;
    its body, if any, follows under the (B) regime (resolver.py).
    """
    if isinstance(item, Import):
        return                              # mounts are the module manager's job

    if isinstance(item, ReactorDecl):
        for seg_name in _dotted(item.name):
            scope.add_symbol(
                Symbol(name=seg_name, kind=item.kind,
                       params=_params_of(item), offset=item.begin),
                reporter)
        return

    kind = _KIND_OF_NODE.get(type(item).__name__)
    if kind is None:
        return                              # not a scope-symbol-bearing node

    for seg_name in _dotted(item.name):
        scope.add_symbol(
            Symbol(name=seg_name, kind=kind,
                   params=_params_of(item), offset=item.begin),
            reporter)


def _check_param_state_collision(item, params, reporter):
    """RETURN: None. Reports [NAME] if a signature parameter shares its
              spelling with a mode/state of the same aggregate (D-4).

    A name meaning instance data in one breath and a state in the next is a
    confusion; one cheap check at record time. The diagnostic points at the
    aggregate declaration head.
    """
    member_names = set(_aggregate_member_names(item))
    for pname, _ in params:
        if pname in member_names:
            reporter.report(semantic_error(
                SemanticClass.NAME, item.begin,
                "parameter '%s' collides with a mode/state of the same "
                "aggregate" % pname))
