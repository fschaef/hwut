"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

ResolvedProgram  (pass 2, README H)

The emitter's ENTIRE input: one frozen dataclass. Resolution is a SIDECAR --
the AST is never rewritten to carry resolved symbols; the 'resolutions' map is
the one place a reference's meaning lives, keyed on node IDENTITY (id(node)),
because the frozen AST reference nodes have value equality and two textual twins
would otherwise collide.

The frozen 'ast' in this same artefact keeps every reference node alive, so the
integer id used as a key is stable for the program's lifetime -- no node is
collected and no id reused while the ResolvedProgram exists.
______________________________________________________________________________
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ResolvedProgram:
    """The complete pass-2 result handed to the emitter, frozen.

    'ast' is the untouched root Module. 'scope_tree' is the GROUND scope with
    its symbols. 'resolutions' maps id(reference-node) -> Symbol. 'mounts' are
    the import grafts. 'cascade' is the cycle-free event-kind graph.
    'queried' is the set of event kinds the rules consume (the emitter generates
    tracer registration from it -- no hand-written watch list). 'source_map' is
    the diagnostics seed (offset -> line/column at render time).

    Frozen so no stage past pass 2 mutates the result; the maps it carries are
    built once and read thereafter.
    """
    ast:         object
    scope_tree:  object
    resolutions: dict
    mounts:      dict             = field(default_factory=dict)
    cascade:     object           = None
    queried:     frozenset        = frozenset()
    source_map:  object           = None

    def symbol_of(self, node):
        """RETURN: the Symbol a reference 'node' resolved to, or None if it was
                  never seated.

        The id-keyed lookup, wrapped so callers never key on the node by value.
        Returns None for an unresolved reference (a failed or never-recorded
        one) rather than raising.
        """
        return self.resolutions.get(id(node))
