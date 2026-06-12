#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

RULE-FILE PARSER  --  the facade that binds the reactive-engine rule language
                      (the OUTER layer) to the generic parsing engine (core).

This is the seam between "this specific language" and "the general machinery":

  OUTER (this layer)   grammar.py   the GRAMMAR dict + terminal definitions
                       actions.py   the _build_* reduce builders (ACTIONS)
                       ast_nodes.py the AST node shapes the actions build

  core/ (general)      a grammar-agnostic LL(2) engine, lexer, node tree,
                       terminal factory, diagnostics -- knows nothing of the
                       rule language; it is parameterised by the grammar.

The facade does three things, once: register the grammar's string keywords with
the core lexer (so its token spec can be generated), compile GRAMMAR/ACTIONS into
a validated Grammar, and expose parse(). A different language would supply its
own grammar/actions/ast_nodes and its own facade, reusing core unchanged.
______________________________________________________________________________
"""
from .core.ll2_engine import Grammar, EngineParser
from .core.diagnostic import DiagnosticReporter
from .core.lexer import register_grammar

from .grammar import GRAMMAR
from .ast_map import AST_MAP, validate_ast_map
from . import ast_nodes as _ast

# Grammar registration with the core lexer happens once at package import
# (see parser/__init__.py), so any entry path finds it already wired.


_COMPILED = None


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
        register_grammar(GRAMMAR)
        validate_ast_map(GRAMMAR)
        _COMPILED = Grammar(GRAMMAR, transformers=AST_MAP,
                            start="top-level")
    return _COMPILED


def finalize_file(file_node):
    """RETURN: RuleFile, the outer-layer file node wrapping the CST items.

    The engine (core, AST-free) yields a STAR_Node('<file>') of transformed
    top-level items in CST mode. The outer layer wraps those into ast.RuleFile --
    the public file type. Any caller that drives EngineParser.parse() directly
    (e.g. the fuzz harness, which injects its own lexer) finalises through here
    so the file type is consistent everywhere, not just via parse().
    """
    rule_file = _ast.RuleFile()
    rule_file.items.extend(file_node.items)
    return rule_file


def parse(source_text, oracle, reporter: DiagnosticReporter):
    """RETURN: RuleFile, the AST for 'source_text' via the table-driven engine.

    Diagnostics accumulate in 'reporter'; the AST may be partial when errors
    were recovered. The observable contract is unchanged from before the
    outer/core split and the Phase-4 CST overlay -- only the wiring moved. The
    engine produces a STAR_Node('<file>') of transformed top-level items (CST
    mode); this wraps them in the outer ast.RuleFile so the public return type is
    unchanged.
    """
    file_node = EngineParser(source_text, oracle, reporter,
                             compiled_grammar()).parse()
    return finalize_file(file_node)

