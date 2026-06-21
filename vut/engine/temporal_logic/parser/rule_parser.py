#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

RULE-FILE PARSER  --  the facade that binds the reactive-engine rule language
                      (the OUTER layer) to the generic parsing engine (core).

This is the seam between "this specific language" and "the general machinery":

  OUTER (this layer)   grammar.py   GRAMMAR dict + terminal definitions
                       ast_nodes.py AST node shapes the actions build
                       ...

  core/ (general)      a grammar-agnostic LL(2) engine, lexer, node tree,
                       terminal factory, diagnostics -- knows nothing of the
                       rule language; it is parameterised by the grammar.

The facade does three things, once: register the grammar's string keywords with
the core lexer (so its token spec can be generated), compile GRAMMAR/ACTIONS into
a validated Grammar, and expose parse(). A different language would supply its
own grammar/actions/ast_nodes and its own facade, reusing core unchanged.
______________________________________________________________________________
"""
from vut.engine.temporal_logic.core.parser_generator.ll2_engine import Grammar, EngineParser
from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter
from vut.engine.temporal_logic.lexer.lexer import register_grammar

from .grammar import GRAMMAR
from .ast_map import AST_MAP, validate_ast_map, validate_ast_map_shapes
from . import ast_nodes as _ast

# Grammar registration with the core lexer happens once at package import
# (see parser/__init__.py), so any entry path finds it already wired.


_COMPILED = None

def parse(source_text, oracle, reporter: DiagnosticReporter) -> _ast.ModuleRoot:
    """RETURN: Module, the AST for 'source_text' via the table-driven engine.

    Diagnostics accumulate in 'reporter'; the AST may be partial when errors
    were recovered. The observable contract is unchanged from before the
    outer/core split and the Phase-4 CST overlay -- only the wiring moved. The
    engine produces a STAR_Node('<file>') of transformed top-level items (CST
    mode); this wraps them in the outer ast.ModuleRoot so the public return type is
    unchanged.
    """
    file_node = EngineParser(source_text, oracle, reporter,
                             compiled_grammar()).parse()
    return finalize_file(file_node)

def compiled_grammar():
    """RETURN: Grammar, the compiled+validated rule-file grammar (cached).

    Builds once on first use. Registers the grammar with the lexer (so the token
    spec is generated) and compiles it with the CST + AST_MAP overlay (Phase 4):
    the engine builds the canonical CST and AST_MAP transforms each rule's node
    into its typed AST node. Done lazily here -- NOT at package import -- so
    importing the parser package has no side effects and cannot form an import
    cycle (grammar.py imports the Luau Role, whose module imports back into
    parser.core; eager registration in __init__ would close that loop mid-init).
    Raises LL2ConflictError if the grammar block is not LL(2) -- surfaced eagerly
    so a grammar edit that breaks LL(2) fails loud. The grammar is LL(2): most
    rules are LL(1); the second token decides <arg> ('id =' named vs positional
    rvalue) and steers the merged named tails, where an identifier head must be
    told from a dotted continuation ('id .' vs 'id (' vs bare).
    """
    global _COMPILED
    if _COMPILED is None:
        # The engine flattens subspaces internally (D-21); the outer layer just
        # registers the grammar and compiles it. register_grammar and Grammar
        # each flatten what they receive, so GRAMMAR is passed nested.
        register_grammar(GRAMMAR)
        _COMPILED = Grammar(GRAMMAR, transformers=AST_MAP, start="top-level")
        validate_ast_map(_COMPILED.flat)
        validate_ast_map_shapes(_COMPILED)
    return _COMPILED


def finalize_file(file_node) -> _ast.ModuleRoot:
    """RETURN: Module, the outer-layer module node wrapping the CST items.

    The engine (core, AST-free) yields a STAR_Node('<file>') of transformed
    top-level items in CST mode. The outer layer wraps those into ast.ModuleRoot --
    the public module type. Any caller that drives EngineParser.parse() directly
    (e.g. the fuzz harness, which injects its own lexer) finalises through here
    so the file type is consistent everywhere, not just via parse().
    """
    module_node = _ast.ModuleRoot()
    module_node.items.extend(file_node.items)
    return module_node


