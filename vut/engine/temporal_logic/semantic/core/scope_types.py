"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

SCOPE TYPES  (semantic/core -- GENERAL mechanism)

The data types of a lexical scope tree: a Symbol (a declared name), a Scope (a
node of the tree holding symbols and child scopes), and E_ScopeKind (what opened
a scope). These types know NOTHING about the rule language -- not events, modes,
causes or clocks. They model names and nesting, and would serve any language
with lexical scope. The BUILDER that fills a tree from the rule-language AST
(build_scopes) is application-specific and lives in semantic/scope_tree.py; it
imports these types.

'kind' on a Symbol is a free string the application assigns (the rule language
puts 'event' / 'mode' / ... here); core does not interpret it. 'kind' on a Scope
is the structural E_ScopeKind. Keeping the string open is what lets core stay
ignorant of the rule vocabulary while the application layers meaning on top.
______________________________________________________________________________
"""
from dataclasses import dataclass, field
from enum        import Enum

from vut.engine.temporal_logic.semantic.diagnostics import (
    SemanticClass, semantic_error)


class E_ScopeKind(Enum):
    """What opened a scope. GROUND is the tree root; the others are the
    structural kinds that bracket nested items.

    GROUND/NAMESPACE are general nesting kinds; MODE_GROUP/STATE_MACHINE name
    the two rule-language aggregates that also open scopes -- retained here as
    structural tags (core does not act on their meaning, only on the fact that
    they bracket a child scope).
    """
    GROUND        = "ground"
    NAMESPACE     = "namespace"
    MODE_GROUP    = "mode-group"
    STATE_MACHINE = "state-machine"


@dataclass(frozen=True)
class Symbol:
    """One declared name in a scope: its kind, its members, and where it sat.

    'kind' is an application-assigned string (the rule language puts 'event' /
    'mode' / 'struct' / ... here); core stores it without interpreting it.
    'params' is the declared-member list as a flat ordered list of
    (member-name, member-type) pairs -- empty for kinds that carry no members.
    It is NOT a list of Symbols and the members are NOT scope entries; the
    TYPE-descent walk reads this list directly. 'offset' is the absolute
    character offset of the declaration head, the position a diagnostic about
    this symbol points at.
    """
    name:   str
    kind:   str
    params: "tuple[tuple[str, str], ...]" = ()
    offset: int = 0


@dataclass
class Scope:
    """One node of the scope tree: the symbols declared directly in it.

    'kind' is what opened it (E_ScopeKind). 'parent' is the enclosing scope, or
    None for GROUND. 'name' is the path segment this scope was opened under, or
    "" for GROUND. 'symbols' maps a spelling to its Symbol. 'children' holds
    nested opened scopes in source order.

    'sealed' is the seal law made concrete: False while the build is still
    inside this scope's items, True once they are exhausted. Nothing adds to a
    sealed scope, and a later mount may not graft onto or through one. A mutable
    dataclass because the build fills 'symbols'/'children' as it sweeps and flips
    'sealed' at the close; once sealed it is treated as final.
    """
    kind:     E_ScopeKind
    parent:   "Scope | None" = None
    name:     str = ""
    symbols:  "dict[str, Symbol]" = field(default_factory=dict)
    children: "list[Scope]"       = field(default_factory=list)
    sealed:   bool = False

    def add_symbol(self, symbol: Symbol, reporter) -> bool:
        """RETURN: True,  if 'symbol' was recorded in this scope.
                  False, if a symbol of the same spelling already sat here
                         (a duplicate; the second is reported, dropped).

        Records the symbol under its spelling. A duplicate is a NAME error at
        the duplicate's offset; the first declaration wins so later resolution
        sees a stable binding.
        """
        if symbol.name in self.symbols:
            reporter.report(semantic_error(
                SemanticClass.NAME, symbol.offset,
                "duplicate declaration of '%s' in this scope" % symbol.name))
            return False
        self.symbols[symbol.name] = symbol
        return True
