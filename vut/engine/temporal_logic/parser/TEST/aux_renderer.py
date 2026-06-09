#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

Shared rendering for the parser test suite: turn a token list into a readable
input fragment, and an AST node into a stable indented dump. Pure presentation,
no grammar walking -- the GOOD file's human-readability lives here.
______________________________________________________________________________
"""
from dataclasses import is_dataclass, fields

from vut.engine.temporal_logic.parser.core.terminals import t_fr_span_open


def fragment(tokens):
    """RETURN: str, the token list rendered as a readable code fragment.

    Lexemes joined with single spaces -- enough to show WHAT input produced a
    case, not to reproduce source layout. A LUAU_OPEN ('{') is shown as the
    synthetic block '{ luau }' the fake lexer serves, matching what the engine
    consumed. An empty list renders as '(empty)'.
    """
    if not tokens:
        return "(empty)"
    out = []
    for t in tokens:
        out.append("{ luau }" if t.kind is t_fr_span_open else t.text)
    return " ".join(out)


def fmt(node, indent=0):
    """RETURN: str, a stable indented rendering of an AST node / list / leaf.

    A dataclass prints its type name then one line per field; nested dataclasses
    and lists recurse indented; leaves print with repr. Deterministic given the
    node, so the rendering is safe as a GOOD-file oracle.
    """
    pad = "  " * indent
    if isinstance(node, list):
        if not node:
            return pad + "[]"
        return "\n".join(fmt(x, indent) for x in node)
    if is_dataclass(node):
        lines = [pad + type(node).__name__]
        for f in fields(node):
            val = getattr(node, f.name)
            if is_dataclass(val) or isinstance(val, list):
                lines.append("%s  %s:" % (pad, f.name))
                lines.append(fmt(val, indent + 2))
            else:
                lines.append("%s  %s = %r" % (pad, f.name, val))
        return "\n".join(lines)
    return pad + repr(node)


