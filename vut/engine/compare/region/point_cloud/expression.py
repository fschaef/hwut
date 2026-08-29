"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: SAFE evaluation of user expressions from region parameters.

Region parameters like

    constraint={abs(y - sin(x)/x) < 0.01}
    dist={max(abs(x[0]-y[0]), abs(x[1]-y[1]))}

arrive in INPUT STREAMS. They are never handed to 'eval': the expression is
parsed with 'ast' and validated against a strict whitelist BEFORE anything
runs -- literals, the declared vector names (with indexing), the aliases
x, y, z, w for p[0..3] where applicable, arithmetic, comparisons, boolean
operators, conditional expressions, and a fixed set of math functions.
Anything else (names, calls, attributes, comprehensions, ...) is rejected
loudly at PARSE time.

(Defense in depth: the registry additionally rules that only the NOMINAL
side's expressions are ever evaluated -- see 'region/registry.py'.)
________________________________________________________________________________
"""
import ast
import math

from vut.engine.compare.region.registry import RegionSyntaxError


SAFE_FUNCTION_DB = {
    "abs":   abs,       "min":   min,       "max":   max,
    "sqrt":  math.sqrt, "exp":   math.exp,  "log":   math.log,
    "sin":   math.sin,  "cos":   math.cos,  "tan":   math.tan,
    "asin":  math.asin, "acos":  math.acos, "atan":  math.atan,
    "atan2": math.atan2,"floor": math.floor,"ceil":  math.ceil,
    "round": round,     "hypot": math.hypot,
}

SAFE_CONSTANT_DB = {
    "pi": math.pi, "e": math.e, "inf": math.inf,
}

_SAFE_NODE_TYPES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
    ast.IfExp, ast.Call, ast.Name, ast.Load, ast.Constant, ast.Subscript,
    ast.Tuple,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
)

# Aliases for the first components of the single-vector name (constraint):
ALIAS_DB = {"x": 0, "y": 1, "z": 2, "w": 3}


class SafeExpression:
    """A validated, compiled expression over declared vector names.

    'vector_names': the names visible as indexable vectors, e.g. ("p",) for
    a constraint, ("x", "y") for a distance function. With the single
    vector "p", the aliases x, y, z, w address p[0..3].
    """
    def __init__(self, text, vector_names, line_n):
        """RETURNS: (constructor) -- raises RegionSyntaxError if 'text' is
        not a pure whitelisted expression.
        """
        self.text         = text
        self.vector_names = tuple(vector_names)
        self.alias_f      = (self.vector_names == ("p",))
        try:
            tree = ast.parse(text, mode="eval")
        except SyntaxError as e:
            raise RegionSyntaxError(line_n,
                "expression %r: not parseable (%s)" % (text, e.msg)) from None
        self._validate(tree, line_n)
        self._code = compile(tree, "<region-parameter>", "eval")

    def _validate(self, tree, line_n):
        for node in ast.walk(tree):
            if not isinstance(node, _SAFE_NODE_TYPES):
                raise RegionSyntaxError(line_n,
                    "expression %r: '%s' is not allowed"
                    % (self.text, type(node).__name__))
            elif isinstance(node, ast.Call):
                if (not isinstance(node.func, ast.Name)
                        or node.func.id not in SAFE_FUNCTION_DB
                        or node.keywords):
                    raise RegionSyntaxError(line_n,
                        "expression %r: only calls to %s are allowed"
                        % (self.text, ", ".join(sorted(SAFE_FUNCTION_DB))))
            elif isinstance(node, ast.Name):
                allowed = (set(self.vector_names)
                           | set(SAFE_FUNCTION_DB) | set(SAFE_CONSTANT_DB)
                           | (set(ALIAS_DB) if self.alias_f else set()))
                if node.id not in allowed:
                    raise RegionSyntaxError(line_n,
                        "expression %r: unknown name '%s' (allowed: %s)"
                        % (self.text, node.id, ", ".join(sorted(allowed))))
            elif isinstance(node, ast.Constant):
                if not isinstance(node.value, (int, float, bool)):
                    raise RegionSyntaxError(line_n,
                        "expression %r: only numeric constants are allowed"
                        % (self.text,))

    def __call__(self, *vectors):
        """RETURNS: the expression's value for the given vectors (bound to
        'vector_names' in order).
        """
        scope = dict(SAFE_FUNCTION_DB)
        scope.update(SAFE_CONSTANT_DB)
        for name, vec in zip(self.vector_names, vectors, strict=False):
            scope[name] = vec
        if self.alias_f:
            p = vectors[0]
            for alias, i in ALIAS_DB.items():
                if i < len(p):
                    scope[alias] = p[i]
        return eval(self._code, {"__builtins__": {}}, scope)  # noqa: S307
        # 'eval' runs a WHITELIST-VALIDATED, freshly compiled expression
        # with empty builtins -- see module purpose.


# ------------------------------------------------------------------------------
# BUILT-IN DISTANCE FUNCTIONS
# ------------------------------------------------------------------------------

def _euclidean(x, y):
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(x, y, strict=False)))

def _l1(x, y):
    return sum(abs(a - b) for a, b in zip(x, y, strict=False))

def _linf(x, y):
    return max(abs(a - b) for a, b in zip(x, y, strict=False))

BUILTIN_DIST_DB = {
    "euclidean": _euclidean,
    "L1":        _l1,
    "L2":        _euclidean,
    "Linf":      _linf,
}


def make_dist(spec, line_n):
    """RETURNS: callable(x, y) -> float, the distance function for 'spec':
                a built-in name (euclidean, L1, L2, Linf) or a whitelisted
                expression over the vectors 'x' and 'y'.
    """
    if spec in BUILTIN_DIST_DB:
        return BUILTIN_DIST_DB[spec]
    return SafeExpression(spec, ("x", "y"), line_n)


def make_constraint(spec, line_n):
    """RETURNS: callable(p) -> bool, the constraint predicate for 'spec':
                a whitelisted expression over the vector 'p' (aliases
                x, y, z, w for p[0..3]).
    """
    return SafeExpression(spec, ("p",), line_n)
