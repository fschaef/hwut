"""
MODULE TYPE STATES -- the spine of the build, expressed as types.

    SourceModule  --parse-->  ParsedModule  --declare-->  DeclaredModule
                  --elaborate-->  SemanticModule  --(pack)-->  Library
                                                  --(link, +entry)-->  Executable

Each state is a distinct type; each transition is a total function producing the
next. The types are thin -- some hold almost nothing -- but each names a stage
the build passes through, so the chain is visible in the type system.

INHERITANCE: SemanticModule IS-A DeclaredModule. A SemanticModule provides
everything a DeclaredModule does (its export_db stays present and peekable) plus
the symbol table and mutated ast. Wherever an export_db is peeked, a
SemanticModule stands in for a DeclaredModule.

PROVENANCE is a load-stage concept (which file, from where). It enters at
SourceModule and is carried forward by reference. It is NOT a parser concept:
the parser is single-file and import-chain-unaware (parser todo-4).

The transition FUNCTIONS (parse, declare, elaborate, link, pack) live in the
units that own them (common.py, the semantic unit, the link unit); this module
defines only the STATES they move between.
"""

from __future__ import annotations
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Forward-referenced contents -- defined by the units that fill them.
#   ast.ModuleRoot   the parser's root node (was RuleFile)
#   ExportDB         name -> (kind, scope)            (declare fills it)
#   SymbolTable      Access (each with recipe), ModuleRefs   (elaborate fills it)
#   EntryPoint       a runnable root (BEGIN/END frame)
# ---------------------------------------------------------------------------
ModuleRoot  = "ast.ModuleRoot"
ExportDB    = "ExportDB"
SymbolTable = "SymbolTable"
EntryPoint  = "EntryPoint"


# ---------------------------------------------------------------------------
# PER-MODULE STATES (one file, carried through the front of the pipeline).
# ---------------------------------------------------------------------------
@dataclass
class SourceModule:
    """
    RETURN: a SourceModule, the first state -- a module identified by its path,
            before any text is read

    The text is NOT held. It is ephemeral: the parser iterates over it through
    `path` and discards it. SourceModule carries only what identifies the module
    and lets the parser reach its bytes.
    """
    path: object                       # file reference: identity + iteration handle


@dataclass
class ParsedModule:
    """
    RETURN: a ParsedModule, the state after parse -- an ast plus the provenance
            it came from

    Wraps the parser's root node. The text is gone; what remains is the tree and
    a traceable reference back to the source path (diagnostics point at
    file:offset). Provenance lives here, at the load stage, never in the parser.
    """
    origin: object                     # provenance: the SourceModule path
    ast: ModuleRoot                    # ast.ModuleRoot, the parser's root node


@dataclass
class DeclaredModule:
    """
    RETURN: a DeclaredModule, the state after declare -- the ast with its
            export_db published

    Carries references not yet given an access recipe. Its export_db announces
    the kinds it declares; that surface is what another module peeks during its
    own elaborate. References are untouched at this state.
    """
    origin: object                     # provenance, carried from ParsedModule
    ast: ModuleRoot                    # the parser's root node (not yet mutated)
    export_db: ExportDB                # name -> (kind, scope); export names only


@dataclass
class SemanticModule(DeclaredModule):
    """
    RETURN: a SemanticModule, the state after elaborate -- a DeclaredModule
            extended with a mutated ast and a symbol table

    IS-A DeclaredModule: inherits origin, ast, export_db; export_db stays
    peekable. elaborate mutates the inherited `ast` in place ('=> name' nodes
    replaced, kind selected from a peeked export_db) and fills `symbol_table`,
    where every Access carries its recipe -- access KNOWN, not implemented.
    link implements it.
    """
    symbol_table: SymbolTable = None   # Access (each with recipe), ModuleRefs


# ---------------------------------------------------------------------------
# WHOLE-PROGRAM STATES (the fold over a set of SemanticModules).
# ---------------------------------------------------------------------------
@dataclass
class Library:
    """
    RETURN: a Library, a packed set of SemanticModules with no entry point

    Rootless by construction -- consumed, never launched. NOT linked: members
    stay SemanticModules (access known, not implemented), so re-entry into a
    later build is free. A Library acts as a set of SemanticModules in a later
    make_executable, peeked for their export_db and linked then.
    """
    members: "list[SemanticModule]" = field(default_factory=list)


@dataclass
class Executable:
    """
    RETURN: an Executable, a LinkedModule bound to an entry point

    Single-rooted and runnable. Produced by folding a SemanticModule with its
    dependency set (link implements every reference) and binding the entry
    point. The seam to the emitter: emit(Executable) -> Luau application.
    """
    linked: object                     # LinkedModule: references IMPLEMENTED
    entry_point: EntryPoint            # the runnable root bound after link
