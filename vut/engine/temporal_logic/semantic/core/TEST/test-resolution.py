"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

TEST: the GENERAL join + ModuleProxy mounted view (semantic/core; D-32 / D-31)

The core resolution mechanism IN ISOLATION, against HAND-BUILT tables -- no rule
language, no parser, no application policy beyond an injected ResolutionPolicy.
This test imports ONLY semantic/core/, which is the seam: core is the schema +
query engine, and it must be exercisable without the VUT filler. The printed
report IS the assertion.

What is proven:
    proxy_present   a proxy answers a mount-prefixed name from the viewed table;
                    a covered-but-undeclared name returns None ('absent name');
                    an uncovered head returns None (not ours).
    chain_local     resolve_with_chain seats a head found in the LOCAL scope
                    chain (no proxy consulted -- the local hop).
    chain_remote    a head under a proxy's mount prefix CHAINS into the viewed
                    table and seats the donor symbol (the cross-file hop).
    chain_absent    a head covered by a proxy but absent from its table fails to
                    seat (the caller's missing-export link error).
______________________________________________________________________________
"""
import sys
from config import HwutRunner

from vut.engine.temporal_logic.semantic.core.module_proxy import ModuleProxy
from vut.engine.temporal_logic.semantic.core.scope_types  import (
    Scope, Symbol, E_ScopeKind)
from vut.engine.temporal_logic.semantic.core.resolution   import (
    Reference, ResolutionState, ResolutionPolicy, resolve_with_chain)


# A minimal policy for the join: no kind opens a scope and no head is pseudo,
# so the hand-built single-segment names resolve purely by the local/proxy hop.
_POLICY = ResolutionPolicy(scope_head_kinds=frozenset(), pseudo_symbols=frozenset())


class _Reporter:
    """A reporter stub: records diagnostics so a miss is observable, not fatal."""
    def __init__(self):
        self.errors = []

    def report(self, diagnostic):
        """RETURN: None. Appends 'diagnostic' to the recorded list."""
        self.errors.append(diagnostic)


class _Node:
    """A stand-in for an AST reference node, identity-keyed (README H)."""
    def __init__(self, label):
        self.label = label


def _sym(name, kind="event"):
    """RETURN: a leaf Symbol with no members, for use as a donor declaration."""
    return Symbol(name=name, kind=kind, params=(), offset=0)


def run_proxy_present():
    """RETURN: None. Prints that a proxy mounted at 'lib' answers a mount-
              prefixed name, returns None for a covered-undeclared name, and
              None for an uncovered head."""
    proxy = ModuleProxy(path="leaf.rule", mount=("lib",),
                        table={"tick": _sym("tick")})
    print("declared:    %s" % proxy.lookup(["lib", "tick"]))
    print("undeclared:  %s" % proxy.lookup(["lib", "nope"]))
    print("uncovered:   %s" % proxy.lookup(["other", "tick"]))

    assert proxy.lookup(["lib", "tick"]).name == "tick"
    assert proxy.lookup(["lib", "nope"]) is None
    assert proxy.lookup(["other", "tick"]) is None


def _ground_with(name):
    """RETURN: a sealed ground Scope holding one Symbol named 'name'."""
    g = Scope(kind=E_ScopeKind.GROUND, name="", parent=None)
    g.symbols[name] = _sym(name)
    g.sealed = True
    return g


def run_chain_local():
    """RETURN: None. Prints that a head found locally seats without consulting
              any proxy (the local hop of the one lookup mechanism)."""
    scope = _ground_with("here")
    node  = _Node("here")
    ref   = Reference(segments=("here",), offset=3, node=node, scope=scope)
    state = ResolutionState()

    ok = resolve_with_chain(ref, scope, (), state, _POLICY, _Reporter())
    print("seated:      %s" % ok)
    print("symbol:      %s" % (state.resolutions.get(id(node)).name
                               if id(node) in state.resolutions else None))

    assert ok is True
    assert state.resolutions[id(node)].name == "here"


def run_chain_remote():
    """RETURN: None. Prints that a head under a proxy's mount CHAINS into the
              viewed table and seats the donor symbol (the cross-file hop)."""
    scope = _ground_with("local_only")
    proxy = ModuleProxy(path="lib.rule", mount=("lib",),
                        table={"shared": _sym("shared")})
    node  = _Node("lib.shared")
    ref   = Reference(segments=("lib", "shared"), offset=11, node=node, scope=scope)
    state = ResolutionState()

    ok = resolve_with_chain(ref, scope, (proxy,), state, _POLICY, _Reporter())
    print("seated:      %s" % ok)
    print("donor:       %s" % (state.resolutions.get(id(node)).name
                               if id(node) in state.resolutions else None))
    print("origin:      %s" % proxy.path)

    assert ok is True
    assert state.resolutions[id(node)].name == "shared"


def run_chain_absent():
    """RETURN: None. Prints that a head covered by a proxy but absent from its
              table fails to seat (caller's missing-export link error)."""
    scope = _ground_with("local_only")
    proxy = ModuleProxy(path="lib.rule", mount=("lib",), table={})
    node  = _Node("lib.ghost")
    ref   = Reference(segments=("lib", "ghost"), offset=13, node=node, scope=scope)
    state = ResolutionState()

    ok = resolve_with_chain(ref, scope, (proxy,), state, _POLICY, _Reporter())
    print("seated:      %s" % ok)
    print("symbol:      %s" % (state.resolutions.get(id(node)).name
                               if id(node) in state.resolutions else None))

    assert ok is False
    assert id(node) not in state.resolutions


HwutRunner(
    argv       = sys.argv,
    title      = "Core -- general join / ModuleProxy chaining lookup",
    choice_map = {
        "proxy_present": run_proxy_present,
        "chain_local":   run_chain_local,
        "chain_remote":  run_chain_remote,
        "chain_absent":  run_chain_absent,
    },
).run()
