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

from . import actions as _actions

# Grammar registration with the core lexer happens once at package import
# (see parser/__init__.py), so any entry path finds it already wired.


_COMPILED = None


def compiled_grammar():
    """RETURN: Grammar, the compiled+validated rule-file grammar (cached).

    Builds once on first use. Registers the grammar with the lexer (so the token
    spec is generated) and compiles it. Done lazily here -- NOT at package import
    -- so importing the parser package has no side effects and cannot form an
    import cycle (grammar.py imports the Luau Role, whose module imports back into
    parser.core; eager registration in __init__ would close that loop mid-init).
    Raises LL2ConflictError if the grammar block is not LL(2) -- surfaced eagerly
    so a grammar edit that breaks LL(2) fails loud. The grammar is LL(2): all but
    one rule are LL(1), and <arg> needs the second token ('id =' is a named
    argument, 'id' alone a positional rvalue).
    """
    global _COMPILED
    if _COMPILED is None:
        register_grammar(_actions.GRAMMAR)
        _COMPILED = Grammar(_actions.GRAMMAR, _actions.ACTIONS, start="top-level")
    return _COMPILED


def parse(source_text, oracle, reporter: DiagnosticReporter):
    """RETURN: RuleFile, the AST for 'source_text' via the table-driven engine.

    Diagnostics accumulate in 'reporter'; the AST may be partial when errors
    were recovered. The observable contract is unchanged from before the
    outer/core split -- only the wiring moved here from the engine module.
    """
    return EngineParser(source_text, oracle, reporter, compiled_grammar()).parse()


