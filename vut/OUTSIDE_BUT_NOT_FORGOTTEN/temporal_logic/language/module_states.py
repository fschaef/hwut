"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

MODULE TYPE STATES -- the front half of the build spine, expressed as types.

    SourceModule --parse--> ParsedModule --declare--> DeclaredModule
                                         --elaborate--> SemanticModule

Each state is a distinct type; each named transition produces the next state
from the previous one. The types are thin -- some hold almost nothing -- but
each names a stage the build passes through, so the chain is visible in the
type system rather than implied by which fields happen to be filled.

INHERITANCE. SemanticModule IS-A DeclaredModule: it provides everything a
DeclaredModule does (its export_db stays present and peekable) plus what
elaborate adds. Wherever an export_db is peeked, a SemanticModule stands in
for a DeclaredModule -- the substitution the cross-module walk depends on.

OWNERSHIP OF TRANSITIONS. This module defines only the STATES. The transition
functions live in the units that own them:

    parse        rule_parser.parse_module (the parser facade)
    declare      the semantic unit          -- publishes the export_db; never
                                              touches a reference
    elaborate    the semantic unit          -- mounts imports (step 0), then
                                              resolves every reference to a
                                              RECIPE (access KNOWN); peeks peer
                                              export_dbs (existence+kind only)

ORDERING LAW (declaration-first). Every module of a build declares before any
module elaborates: elaborate peeks PEER export_dbs, so the full declared
surface must exist first. The walk that enforces this is the semantic unit's
worklist loop; the states here are what it moves between.

PROVENANCE is a load-stage concept (which file, from where). It enters at
SourceModule and is carried forward by reference; it is NOT a parser concept
-- the parser is single-file and import-chain-unaware.

BACK HALF. Library/Executable and the link/pack/emit transitions are OUT OF
SCOPE for this component (held for a separate dispatch); no speculative types
for them live here. SemanticModule is the disk serialisation boundary: what a
later build loads instead of re-running the front half.
______________________________________________________________________________
"""
from __future__ import annotations
from dataclasses import dataclass, field


# -----------------------------------------------------------------------------
# Forward-referenced contents -- defined by the units that fill them.
#   file_node   the canonical CST: STAR_Node("<file>") from rule_parser (A-1:
#               one tree; the typed overlay annotates it, never duplicates it)
#   ExportDB    name -> (kind, scope); published by declare (its pass defines it)
#   SymbolTable recipes per access + module refs; filled by elaborate (its pass)
# -----------------------------------------------------------------------------


@dataclass
class SourceModule:
    """
    RETURN: SourceModule, the first state -- a module identified by its path,
            before any text is read.

    The text is NOT held: it is ephemeral, read by the parse transition through
    'path' and discarded. A SourceModule carries only what identifies the module
    and lets the parser reach its bytes.
    """
    path: object                       # file reference: identity + read handle


@dataclass
class ParsedModule:
    """
    RETURN: ParsedModule, the state after parse -- the canonical CST plus the
            provenance it came from.

    The text is gone; what remains is the tree and a traceable reference back to
    the source (diagnostics point at file:offset through it). 'file_node' is the
    finalised "<file>" CST from rule_parser.finalize_file -- the ONE tree of the
    build (A-1): later stages annotate or substitute within it, they never build
    a second tree beside it.
    """
    origin: SourceModule               # provenance: where these bytes came from
    file_node: object                  # canonical CST: STAR_Node("<file>")


@dataclass
class DeclaredModule:
    """
    RETURN: DeclaredModule, the state after declare -- the parsed tree with its
            export_db published.

    The export_db announces every name this module declares and its kind; that
    surface is what a PEER module peeks during its own elaborate (existence and
    kind only, never contents). References are untouched at this state -- declare
    publishes, it never resolves. A DeclaredModule is immutable by discipline:
    elaborate reads it and produces the next state, it does not grow this one
    (the fact that forced import mounting into elaborate step 0, ruling F-1).
    """
    origin: SourceModule               # provenance, carried from ParsedModule
    file_node: object                  # the canonical CST, not yet annotated
    export_db: object                  # ExportDB: name -> (kind, scope)


@dataclass
class SemanticModule(DeclaredModule):
    """
    RETURN: SemanticModule, the state after elaborate -- a DeclaredModule
            extended with the symbol table elaborate filled.

    IS-A DeclaredModule: origin, file_node and export_db are inherited and the
    export_db stays peekable, so a SemanticModule stands in wherever a
    DeclaredModule is expected. elaborate mounts imports (step 0), resolves
    every reference scope-aware, and records one RECIPE per access in
    'symbol_table' -- access KNOWN, never implemented (implementation is link's,
    out of scope here). This state is the disk serialisation boundary: a later
    build loads a SemanticModule instead of re-running parse/declare/elaborate.
    """
    symbol_table: object = None        # SymbolTable: recipes per access, refs
