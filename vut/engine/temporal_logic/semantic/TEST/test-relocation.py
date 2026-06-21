"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

TEST: relocation + ResolvedModule (pass 2, disc-4 SETTLED 3 / 5)

The dynamic load-and-link surface, in isolation: the seat / unseat / reseat
lifecycle of a cross-file reference, and the resolutions SPLIT (permanent local
vs evictable relocation). No real loader -- a bare reference node stands in for
an AST node; the printed report IS the assertion.

Choices:
    lifecycle   seat a relocation, read it back, unseat (drop to recipe),
                reseat -- proving the relocation is kept and the binding is
                evictable.
    split       a permanent local seating and an evictable relocation seating
                coexist; unseat clears ONLY the relocation one, the local
                meaning survives.
______________________________________________________________________________
"""
import sys
from config import HwutRunner

from vut.engine.temporal_logic.semantic.core.relocation     import UnitHeader, Relocation
from vut.engine.temporal_logic.semantic.core.resolved_module import ResolvedModule


class _Node:
    """A stand-in for an AST reference node: identity-keyed, value-equal twins
    would collide, which is exactly why the sidecars key on id()."""
    def __init__(self, label):
        self.label = label


def _module(relocations=()):
    """RETURN: a ResolvedModule with no scope tree, carrying 'relocations'."""
    return ResolvedModule(key="root", scope_tree=None, relocations=tuple(relocations))


def run_lifecycle():
    """RETURN: None. Prints the seat / unseat / reseat lifecycle of one
              relocation, proving the recipe is kept across an unseat."""
    reloc = Relocation(path="leaf.rule", into_scope=None, expected_hash="h1", site=7)
    m = _module([reloc])
    ref = _Node("leaf.tick")

    print("before seat:   %s" % m.symbol_of(ref))
    m.seat_relocation(ref, "SYM(tick)")
    print("after seat:    %s" % m.symbol_of(ref))
    m.unseat_all()
    print("after unseat:  %s" % m.symbol_of(ref))
    print("recipe kept:   path=%s expected=%s" % (m.relocations[0].path,
                                                  m.relocations[0].expected_hash))
    m.seat_relocation(ref, "SYM(tick)#2")
    print("after reseat:  %s" % m.symbol_of(ref))

    assert m.symbol_of(ref) == "SYM(tick)#2"
    assert len(m.relocations) == 1


def run_split():
    """RETURN: None. Prints that an unseat clears the evictable relocation
              seating only; the permanent local seating survives."""
    m = _module([Relocation(path="leaf.rule", into_scope=["NS"],
                            expected_hash="h2", site=9)])
    local_ref = _Node("self.count")
    reloc_ref = _Node("NS.tick")

    m.local_resolutions[id(local_ref)] = "SYM(count)"   # permanent
    m.seat_relocation(reloc_ref, "SYM(NS.tick)")        # evictable

    print("local  before: %s" % m.symbol_of(local_ref))
    print("reloc  before: %s" % m.symbol_of(reloc_ref))
    m.unseat_all()
    print("local  after:  %s" % m.symbol_of(local_ref))
    print("reloc  after:  %s" % m.symbol_of(reloc_ref))

    assert m.symbol_of(local_ref) == "SYM(count)"       # local survives
    assert m.symbol_of(reloc_ref) is None               # relocation evicted


def run_header():
    """RETURN: None. Prints the UnitHeader a pre-built form carries (the
              identity link verifies before seating)."""
    h = UnitHeader(id_hash="lib-abc123", built_from="parsed-def456")
    m = ResolvedModule(key="lib", scope_tree=None, relocations=(), header=h)
    print("id_hash:    %s" % m.header.id_hash)
    print("built_from: %s" % m.header.built_from)
    assert m.header.id_hash == "lib-abc123"


HwutRunner(
    argv       = sys.argv,
    title      = "Semantic Layer -- Relocation / ResolvedModule",
    choice_map = {
        "lifecycle": run_lifecycle,
        "split":     run_split,
        "header":    run_header,
    },
).run()
