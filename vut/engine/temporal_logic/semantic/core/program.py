"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

ResolvedProgram  (pass 2, disc-4 SETTLED 4(3))

The emitter's ENTIRE input: one frozen dataclass. At the RESOLVED maturity the
program's module SET has been FUSED by link into ONE ResolvedModule -- the
symbol tables stay separate-but-mutually-addressable inside it (binding is a
LINK across tables, not a copied entry; object-file linking), but the container
the emitter reads is a single module. ResolvedProgram therefore carries that one
fused module plus the two program-level facts a module cannot hold:

  - 'main'  the entry-point Symbol, or None. PRESENT = program, ABSENT =
            library. This is the ONLY program/library discriminator (disc-4
            SETTLED 3); both are otherwise fully resolved.
  - 'source_map'  the diagnostics seed (offset -> line/column at render time).

The whole-program cascade graph (folded from every module's cascade_part) and
the queried set live on 'module.cascade_part' -- the fused module owns the
program's edges, so there is no separate cascade field here. The cascade fold is
a LINK PRODUCT: a relink (after a lazy unload/reload) refolds it; it is not
incrementally invalidated (disc-4, stance (a)).
______________________________________________________________________________
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ResolvedProgram:
    """The complete pass-2 result handed to the emitter, frozen.

    'module' is the ONE fused ResolvedModule: its frozen 'ast' is the parser's
    tree, its sealed symbol_table carries the ground symbols, its cascade_part
    carries the folded whole-program cascade (edges + queried), its
    ast_decoration_db carries the seated references (intra-module and cross-file
    alike; static, D-31). 'main' is the entry-point Symbol, or None for a library (the sole program/library discriminator).
    'source_map' is the diagnostics seed (offset -> line/column at render time).

    Frozen so no stage past pass 2 mutates the result; resolution is static, so
    there is no dynamic seat/unseat surface to guard against.
    """
    module:     object
    main:       object           = None
    source_map: object           = None

    def symbol_of(self, node):
        """RETURN: the Symbol a reference 'node' resolved to, or None if it was
                  never seated (locally or via a seated relocation).

        Delegates to the fused module's id-keyed lookup, wrapped so callers
        never key on the node by value. Returns None for an unresolved reference
        rather than raising.
        """
        return self.module.symbol_of(node)
