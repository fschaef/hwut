"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

ResolvedModule  (pass 2, disc-4 SETTLED 1 / SETTLED 5)

A single module resolved AGAINST ITSELF -- the per-module resolved typestate
D-29 lacked. The local axis of resolution: a sealed scope tree, the module's own
symbols, and every intra-module reference seated concretely. Cross-file
references are NOT seated here; they are recorded as RELOCATIONS (relocation.py),
the module's public import surface, for the linker to seat at load-and-link.

THE RESOLUTIONS SPLIT (loadability is totally dynamic -- disc-4 SETTLED 3):
  - local_resolutions    intra-module concrete seatings. PERMANENT: a local
                         reference's meaning never changes once seated.
  - seated_relocations   the result of seat()ing a relocation. EVICTABLE: an
                         unseat() (lazy unload) clears these and leaves
                         local_resolutions untouched, so the binding drops back
                         to its relocation recipe without losing local meaning.
Both are id(node)->Symbol sidecars (the identity-key trick, README H): frozen
AST reference nodes have value equality, so two textual twins must key on
identity, and the live 'ast' keeps every node alive so the id stays stable.

A ResolvedModule a loader returns pre-built (the pre-resolved-library case)
carries a UnitHeader; link verifies it (id_hash vs the expecting relocation's
expected_hash, built_from vs the upstream present) before seating its
relocations. 'cascade_part' is this module's local event-kind edge contribution,
folded with the others into the whole-program graph at link.

This type is FROZEN in its structural fields (key, scope_tree, relocations,
cascade_part, header, provenance) -- the resolved facts about the module. The two
resolution sidecars are the dynamic surface: local_resolutions is written once at
resolve and then read; seated_relocations is written and cleared across the
unit's life by seat/unseat. They are therefore plain (mutable) dicts the resolve
and link stages own, not frozen fields.
______________________________________________________________________________
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ResolvedModule:
    """One module resolved against itself; cross-file refs left as relocations.

    'key' is the import path. 'scope_tree' is the sealed GROUND scope with the
    module's Symbols. 'local_resolutions' maps id(reference-node) -> Symbol for
    intra-module references (PERMANENT). 'seated_relocations' maps id(reference-
    node) -> Symbol for references seated from a relocation (EVICTABLE by
    unseat). 'relocations' is the module's cross-file import surface (frozen
    recipes, kept permanently). 'cascade_part' is this module's local event-kind
    edge contribution. 'header' is the identity a pre-built (shipped) form
    carries, or None for a module just resolved in-process. 'provenance' is the
    import that introduced it.

    Frozen so the resolved facts do not drift; the two resolution dicts are the
    dynamic surface (see module docstring) and are mutated through seat/unseat,
    not by reassigning the field.
    """
    key:               str
    scope_tree:        object
    relocations:       "tuple"
    cascade_part:      object              = None
    header:            "UnitHeader | None"  = None
    provenance:        object              = None
    local_resolutions:  dict = field(default_factory=dict)
    seated_relocations: dict = field(default_factory=dict)

    def symbol_of(self, node):
        """RETURN: the Symbol a reference 'node' resolved to, or None if it is
                  not seated (locally or via a seated relocation).

        Checks the permanent local sidecar first, then the evictable relocation
        sidecar. Returns None for an unseated reference (an unmet local name, or
        a relocation not yet seated under lazy loading) rather than raising; the
        id-keyed lookup is wrapped so callers never key on the node by value.
        """
        seated = self.local_resolutions.get(id(node))
        if seated is not None:
            return seated
        return self.seated_relocations.get(id(node))

    def seat_relocation(self, node, symbol):
        """RETURN: None. Records that reference 'node' is now bound to 'symbol'
                  via load-and-link (an EVICTABLE seating).

        The seat() primitive's record step: eager link calls it in a startup
        loop, lazy link on first miss. Writes the EVICTABLE sidecar so a later
        unseat can drop the binding back to its relocation recipe.
        """
        self.seated_relocations[id(node)] = symbol

    def unseat_all(self):
        """RETURN: None. Clears every relocation seating, dropping each cross-
                  file binding back to its (kept) relocation recipe.

        The lazy-unload step: empties the EVICTABLE sidecar only;
        local_resolutions (the permanent intra-module meanings) is untouched, and
        the relocations themselves are kept so a later reseat re-runs them.
        """
        self.seated_relocations.clear()
