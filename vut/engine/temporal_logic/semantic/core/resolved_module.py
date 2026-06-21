"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

ResolvedModule  (pass 2; RATIONALE D-33)

A module is, structurally, just two things plus the decoration that joins them:

    ast                 the parser's frozen tree -- a PURE value, never touched
    symbol_table        declared names + scopes (the former scope_tree)
    ast_decoration_db   id(node) -> resolved Symbol -- the DECORATION, a SEPARATE
                        identity-keyed unit beside the AST, not inside it

The AST is NEVER mutated by resolution. The decoration references the AST by node
IDENTITY; the parser layer knows nothing of it (one-way dependency, semantic ->
ast). Every resolution question reduces to these: 'did this reference resolve?'
-> query ast_decoration_db at the node; 'what does this module export / contain?'
-> the symbol_table; 'can X see Y's name?' -> Y's symbol_table addressed under a
mount (ModuleProxy).

LIFETIME (load-bearing, D-33): ast_decoration_db is keyed by id() and is valid
ONLY while the exact 'ast' instance it was built against is alive. It is BOUND to
that one AST -- never portable to a reparse or a replacement's fresh tree. On
replacement (D-31) the old db is discarded and rebuilt against the new ast, not
migrated.

cascade_part / header / provenance are secondary products carried alongside the
core triple: cascade_part is this module's local event-kind edge contribution
(folded with the others at link); header is the identity a pre-built (shipped)
form carries, or None for a module resolved in-process; provenance is the import
that introduced it.

This type is FROZEN in its structural fields. 'ast_decoration_db' is written at
resolve/link and then read; it is a plain dict the stages own.
______________________________________________________________________________
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ResolvedModule:
    """One module: ast + symbol_table + ast_decoration_db (D-33).

    'key' is the import path. 'ast' is the parser's frozen tree (pure; the
    decoration keys into it by identity). 'symbol_table' is the sealed GROUND
    Scope holding the module's Symbols. 'ast_decoration_db' maps
    id(reference-node) -> Symbol for every seated reference (intra-module and
    cross-file alike; static, D-31). 'cascade_part' is the local event-kind edge
    contribution. 'header' is a shipped form's identity or None. 'provenance' is
    the introducing import.

    Frozen so the resolved facts do not drift; the decoration dict is written by
    the resolve/link stages, not by reassigning the field.
    """
    key:               str
    ast:               object              = None
    symbol_table:      object              = None
    cascade_part:      object              = None
    header:            "UnitHeader | None"  = None
    provenance:        object              = None
    ast_decoration_db:  dict = field(default_factory=dict)

    def symbol_of(self, node):
        """RETURN: the Symbol a reference 'node' resolved to, or None if it is
                  not seated.

        The id-keyed decoration lookup, wrapped so callers never key on the node
        by value. Returns None for an unseated reference rather than raising;
        under static resolution (D-31) an unseated reference is a resolve/link-
        time error, not a deferred miss. Valid only for a 'node' belonging to
        this module's own 'ast' (the db is bound to that instance, D-33).
        """
        return self.ast_decoration_db.get(id(node))
