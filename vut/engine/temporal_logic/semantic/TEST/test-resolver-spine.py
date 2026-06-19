"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

TEST: resolver -- the three spine fixtures (pass 2, README C / D / H / J)

These three prove the resolution core BEFORE any F-check, exactly as README J
prescribes. They build scopes and reference nodes directly (the resolver
consumes a neutral Reference, so a hand-built scope plus distinct node objects
is the cleanest exercise of the (B) drain and the id-keying). The printed
report IS the assertion.

Choices:
    drain_unmet   a (B) forward reference whose body NEVER arrives -> error at
                  the scope close, the diagnostic carrying the REFERENCE offset.
    drain_late    a (B) forward reference whose body arrives LATE but valid ->
                  passes (the drain finds the now-defined target).
    twin_ids      two textually identical references resolving to DIFFERENT
                  symbols -> both present in resolutions, each correct
                  (the id(node)-keying proof, README H).
______________________________________________________________________________
"""
import sys
from config import HwutRunner

from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter
from vut.engine.temporal_logic.semantic.scope_tree import (
    Scope, Symbol, E_ScopeKind)
from vut.engine.temporal_logic.semantic.resolver import (
    Reference, ResolutionState, resolve_reference, drain_scope)


class _Node:
    """A stand-in reference node, distinct by identity even when two carry the
    same spelling -- exactly the twin case id-keying must keep apart."""
    def __init__(self, tag):
        self.tag = tag


def _ground():
    """RETURN: a fresh empty GROUND scope."""
    return Scope(kind=E_ScopeKind.GROUND, parent=None, name="")


def run_drain_unmet():
    """RETURN: None. (B) forward ref, body never arrives -> one [NAME] at close."""
    scope = _ground()
    state, rep = ResolutionState(), DiagnosticReporter()
    node = _Node("Watcher")
    ref  = Reference(segments=("Watcher",), offset=42, node=node)

    seated = resolve_reference(ref, scope, state, rep)
    print("seated at use: %s" % seated)
    print("errors before close: %d" % len(rep.errors))
    drain_scope(scope, state, rep)
    print("errors after close: %d" % len(rep.errors))
    for d in rep.errors:
        print("  tag=%s %s @%d" % (d.tag, d.message, d.source_offset))
    assert len(rep.errors) == 1 and rep.errors[0].source_offset == 42


def run_drain_late():
    """RETURN: None. (B) forward ref, body arrives late -> passes, resolves."""
    scope = _ground()
    state, rep = ResolutionState(), DiagnosticReporter()
    node = _Node("Patrol")
    ref  = Reference(segments=("Patrol",), offset=10, node=node)

    resolve_reference(ref, scope, state, rep)              # queued (forward)
    scope.symbols["Patrol"] = Symbol(name="Patrol", kind="mode",
                                     params=(), offset=99)  # body arrives later
    drain_scope(scope, state, rep)
    seated = state.resolutions.get(id(node))
    print("errors: %d" % len(rep.errors))
    print("Patrol resolved to: %s" % (seated.kind if seated else None))
    assert not rep.errors and seated is not None and seated.kind == "mode"


def run_twin_ids():
    """RETURN: None. Two identical-spelling refs -> distinct symbols, id-keyed."""
    outer = _ground()
    outer.symbols["temp"] = Symbol(name="temp", kind="event", params=(), offset=1)
    inner = Scope(kind=E_ScopeKind.NAMESPACE, parent=outer, name="ns")
    inner.symbols["temp"] = Symbol(name="temp", kind="clock", params=(), offset=2)

    state, rep = ResolutionState(), DiagnosticReporter()
    node_a, node_b = _Node("A"), _Node("B")
    ref_a = Reference(segments=("temp",), offset=5, node=node_a)  # from outer
    ref_b = Reference(segments=("temp",), offset=6, node=node_b)  # from inner

    resolve_reference(ref_a, outer, state, rep)
    resolve_reference(ref_b, inner, state, rep)
    sym_a = state.resolutions.get(id(node_a))
    sym_b = state.resolutions.get(id(node_b))
    print("ref A (outer) -> %s" % sym_a.kind)
    print("ref B (inner) -> %s" % sym_b.kind)
    print("both present: %s" % (id(node_a) in state.resolutions
                                and id(node_b) in state.resolutions))
    print("distinct kinds: %s" % (sym_a.kind != sym_b.kind))
    assert sym_a.kind == "event" and sym_b.kind == "clock"


HwutRunner(
    argv       = sys.argv,
    title      = "Semantic Layer -- Resolver Spine",
    choice_map = {
        "drain_unmet": run_drain_unmet,
        "drain_late":  run_drain_late,
        "twin_ids":    run_twin_ids,
    },
).run()
