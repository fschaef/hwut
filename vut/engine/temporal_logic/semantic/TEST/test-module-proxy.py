"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

TEST: ModuleProxy mounted view + chaining lookup (pass 2, disc-4 SETTLED 6)

The cross-file lookup in isolation, against a HAND-BUILT module table mounted
under a prefix -- the proxy is a VIEW of that table, not a copy. The printed
report IS the assertion.

What is proven:
    proxy_present   a PRESENT proxy answers a mount-prefixed name from the
                    viewed table; a covered-but-undeclared name returns None
                    ('absent name'); an uncovered head returns None (not ours).
    proxy_lazy      an ABSENT proxy is made PRESENT by a loader on first lookup
                    (lazy load), then answers; unmanifest reverts it and a
                    reload re-runs the loader.
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

from vut.engine.temporal_logic.semantic.core.module_proxy import ModuleProxy, E_Presence
from vut.engine.temporal_logic.semantic.core.scope_types import Scope, Symbol, E_ScopeKind
from vut.engine.temporal_logic.semantic.resolver     import (
    Reference, ResolutionState, resolve_with_chain)


class _Node:
    """A stand-in for an AST reference node, identity-keyed (README H)."""
    def __init__(self, label):
        self.label = label


def _sym(name, kind="event"):
    """RETURN: a leaf Symbol with no members, for use as a donor declaration."""
    return Symbol(name=name, kind=kind, params=(), offset=0)


def run_proxy_present():
    """RETURN: None. Prints that a PRESENT proxy mounted at 'lib' answers a
              mount-prefixed name, returns None for a covered-undeclared name,
              and None for an uncovered head."""
    proxy = ModuleProxy(path="leaf.rule", mount=("lib",),
                        presence=E_Presence.PRESENT,
                        table={"tick": _sym("tick")})
    print("presence:    %s" % proxy.presence.name)
    print("declared:    %s" % proxy.lookup(["lib", "tick"]))
    print("undeclared:  %s" % proxy.lookup(["lib", "nope"]))
    print("uncovered:   %s" % proxy.lookup(["other", "tick"]))

    assert proxy.lookup(["lib", "tick"]).name == "tick"
    assert proxy.lookup(["lib", "nope"]) is None
    assert proxy.lookup(["other", "tick"]) is None


def run_proxy_lazy():
    """RETURN: None. Prints the lazy-load lifecycle: an ABSENT proxy loads on
              first lookup, reverts on unmanifest, and reloads on the next ask."""
    loads = {"count": 0}

    def loader(path):
        """RETURN: the table for 'path', counting each real load."""
        loads["count"] += 1
        return {"beat": _sym("beat")}

    proxy = ModuleProxy(path="clock.rule", mount=("clk",))
    print("before:      %s loads=%d" % (proxy.presence.name, loads["count"]))
    got = proxy.lookup(["clk", "beat"], loader)
    print("after load:  %s loads=%d sym=%s" % (proxy.presence.name,
                                               loads["count"],
                                               got.name if got else None))
    proxy.unmanifest()
    print("unmanifest:  %s loads=%d" % (proxy.presence.name, loads["count"]))
    proxy.lookup(["clk", "beat"], loader)
    print("reload:      %s loads=%d" % (proxy.presence.name, loads["count"]))

    assert loads["count"] == 2               # loaded, dropped, loaded again
    assert proxy.presence is E_Presence.PRESENT


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
    ref   = Reference(segments=("here",), offset=3, node=node)
    state = ResolutionState()

    ok = resolve_with_chain(ref, scope, proxies=(), state=state)
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
                        presence=E_Presence.PRESENT,
                        table={"shared": _sym("shared")})
    node  = _Node("lib.shared")
    ref   = Reference(segments=("lib", "shared"), offset=11, node=node)
    state = ResolutionState()

    ok = resolve_with_chain(ref, scope, proxies=(proxy,), state=state)
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
    proxy = ModuleProxy(path="lib.rule", mount=("lib",),
                        presence=E_Presence.PRESENT, table={})
    node  = _Node("lib.ghost")
    ref   = Reference(segments=("lib", "ghost"), offset=13, node=node)
    state = ResolutionState()

    ok = resolve_with_chain(ref, scope, proxies=(proxy,), state=state)
    print("seated:      %s" % ok)
    print("symbol:      %s" % (state.resolutions.get(id(node)).name
                               if id(node) in state.resolutions else None))

    assert ok is False
    assert id(node) not in state.resolutions


HwutRunner(
    argv       = sys.argv,
    title      = "Semantic Layer -- ModuleProxy / chaining lookup",
    choice_map = {
        "proxy_present": run_proxy_present,
        "proxy_lazy":    run_proxy_lazy,
        "chain_local":   run_chain_local,
        "chain_remote":  run_chain_remote,
        "chain_absent":  run_chain_absent,
    },
).run()
