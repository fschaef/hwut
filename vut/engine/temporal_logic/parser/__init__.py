"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer

Rule-file parser package. Importing it wires the reactive-engine rule grammar
(the OUTER layer) into the grammar-agnostic core: the core lexer is told which
grammar's string keywords seed its token spec. This single registration keeps
core independent of the rule language while guaranteeing that ANY entry into the
package -- the facade, a direct core.lexer import in a test, anything -- finds
the grammar already registered.
"""
from . import actions as _actions
from .core import lexer as _lexer

_lexer.register_grammar(_actions.GRAMMAR)
