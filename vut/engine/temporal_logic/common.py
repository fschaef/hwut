"""
COMMON CORE of the build processes -- source to SemanticModule.

make_executable and make_library share one path per source module:

    parse  ->  declare  ->  elaborate

bundled here as `semanticize`. Declaration-first is enforced INSIDE this core:
a module's imported dependencies must each be a DeclaredModule BEFORE elaborate
peeks their export_db.

This module owns no entry-point logic and performs no link. Those are the ends
that distinguish the two build processes (make_executable.py / make_library.py).

Forward-referenced, not yet built:
    parser unit          parse(source_text, oracle, reporter) -> ParsedModule
    semantic unit        declare(ParsedModule)   -> DeclaredModule
                         elaborate(DeclaredModule, foreign_export_dbs)
                                                 -> SemanticModule
"""

from __future__ import annotations
from typing import Iterable


# ---------------------------------------------------------------------------
# TYPE STATES (placeholders -- the real classes live in the semantic unit).
# Named here only so the annotations read; not defined.
# ---------------------------------------------------------------------------
SourceModule   = "SourceModule"      # text (one file)
ParsedModule   = "ParsedModule"      # ast
DeclaredModule = "DeclaredModule"    # ast + export_db
SemanticModule = "SemanticModule"    # decorated_ast + symbol_table  (is-a DeclaredModule)


def parse(source: SourceModule) -> ParsedModule:
    """
    RETURN: a ParsedModule, the source's ast if the text is well-formed
            raises on a fatal infrastructure failure (e.g. oracle down)

    The parser unit. Author errors are recovered into a partial tree and
    reported, not raised. Stub: the real entry is parser.rule_parser.parse.
    """
    raise NotImplementedError


def declare(parsed: ParsedModule) -> DeclaredModule:
    """
    RETURN: a DeclaredModule, the parsed module with its export_db published

    No peek at any other module. Collects every declared name with kind and
    scope into the export_db; references are not touched. The semantic unit's
    first transition.
    """
    raise NotImplementedError


def elaborate(declared: DeclaredModule,
              foreign_export_dbs: "Iterable[DeclaredModule]") -> SemanticModule:
    """
    RETURN: a SemanticModule, `declared` extended with a mutated ast and a
            symbol table whose every Access carries a recipe (access KNOWN)

    Reads the module's own ast and the export_db of each imported module.
    Mutates the ast ('=> name' nodes replaced, kind selected from the foreign
    export_db) and builds the symbol table. Implements nothing; link does.
    The semantic unit's second transition.
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# DEPENDENCY AGGREGATION -- declaration-first precondition.
# ---------------------------------------------------------------------------
def aggregate_dependencies(declared: DeclaredModule) -> "list[DeclaredModule]":
    """
    RETURN: a list of DeclaredModule, the modules `declared` imports, each
            already at (or past) the DeclaredModule state

    The declaration-first obligation made concrete: gather the import targets
    and require each present as a DeclaredModule before elaborate may peek it.
    A target may be a bare DeclaredModule (declared this build) or a loaded
    library member (a SemanticModule, which IS-A DeclaredModule). Resolution
    of WHERE a dependency comes from (this build vs disk) is the caller's; this
    returns the resolved DeclaredModule set.
    """
    raise NotImplementedError


# ---------------------------------------------------------------------------
# THE SHARED CORE.
# ---------------------------------------------------------------------------
def semanticize(source: SourceModule) -> SemanticModule:
    """
    RETURN: a SemanticModule, the source carried through parse -> declare ->
            elaborate with its dependencies' export_dbs in hand

    The unit of work shared by make_executable and make_library. Declaration-
    first is enforced here: dependencies are aggregated as DeclaredModules
    BEFORE elaborate peeks them. No entry-point logic, no link.
    """
    parsed   = parse(source)
    declared = declare(parsed)
    deps     = aggregate_dependencies(declared)     # each a DeclaredModule, before access
    semantic = elaborate(declared, deps)
    return semantic
