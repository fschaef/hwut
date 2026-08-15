"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: THE CONSTRAINT NAMESPACE -- the names a constraint expression may
         use, in ONE place.

    "x < y + 2"                     no call
    "abs(sin(z) - x) < epsilon"     'abs' and 'sin' are calls
    'glob(name, "build-*.log")'     a text match, the shell's own form

A TEST RUN HAS ONE. The fixed part -- functions, constants, string methods
-- is the same for every run and stands here. The variable part is the run's
CONSTRAINT SPACE ('ConstraintSpace' in 'constraints.py'): a binding element
'(( name: value ))' in the sequential outer text enters a name into it, and
every constraint over that name is checked the moment it does. The two are
composed at evaluation time; neither is a copy of the other.

    namespace of a run  =  this module's fixed names
                        +  the run's bound variables

THREE READERS, ONE SET. They must not disagree:

    the AST CHECK        admits a call only to a name in 'FUNCTION_DB' and
                         a bare name only where it is a function, a
                         constant, or a bound variable.
    the EVALUATION       runs with an empty '__builtins__' and this
                         mapping beside the bound variables; nothing else
                         is reachable.
    the VARIABLE FINDER  relates a variable to the constraints that
                         mention it, and must not read a call as a
                         variable: 'abs(x) < 1' constrains 'x' and
                         constrains nothing called 'abs'.

Every name here is therefore a name A VARIABLE MAY NOT CARRY. A constraint
over a variable called 'min' or 'sin' cannot be written.

NOTHING WITH A SIDE EFFECT. No name here reaches the file system, the
network, or the interpreter's own state; 'glob' matches text and does not
look at a disk.
________________________________________________________________________________
"""
import math

from fnmatch import fnmatchcase


def glob(value, pattern):
    """
    RETURN: True,  'value' matches the shell pattern 'pattern'.
            False, it does not.

    The match is CASE SENSITIVE and touches no file system: '*' spans any
    run, '?' one character, '[abc]' a set. A value that is no string is
    made one first, so 'glob(count, "47*")' says what it looks like it
    says.
    """
    return fnmatchcase(str(value), str(pattern))


#  The maths taken from the standard library BY NAME: a name 'math' gains
#  does not silently enter the namespace.
_MATH_NAME_LIST = (
    "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    "sinh", "cosh", "tanh",
    "exp", "log", "log2", "log10", "sqrt", "pow",
    "floor", "ceil", "trunc", "fabs", "fmod", "copysign",
    "degrees", "radians", "hypot", "gcd", "factorial",
    "isfinite", "isinf", "isnan", "isclose",
)

#  WHAT A CONSTRAINT MAY CALL.
FUNCTION_DB = {
    **{name: getattr(math, name) for name in _MATH_NAME_LIST},
    "len": len, "abs": abs, "min": min, "max": max, "sum": sum,
    "int": int, "float": float, "str": str, "bool": bool,
    "round": round, "ord": ord, "chr": chr,
    "all": all, "any": any, "sorted": sorted,
    "glob": glob,
}

#  WHAT A CONSTRAINT MAY NAME without calling it.
CONSTANT_DB = {
    "pi": math.pi, "e": math.e, "tau": math.tau,
    "inf": math.inf, "nan": math.nan,
}

#  The string methods a constraint may reach through a value.
STR_METHOD_SET = frozenset((
    "startswith", "endswith", "lower", "upper", "strip", "lstrip",
    "rstrip", "count", "find", "replace", "split", "isdigit", "isalpha",
    "isalnum", "isspace",
))

#  WHAT A VARIABLE MAY NOT BE CALLED. One set, read by the variable finder
#  and by the AST check alike, so the two cannot drift apart.
NOT_A_VARIABLE_SET = frozenset(FUNCTION_DB) | frozenset(CONSTANT_DB) \
                     | frozenset(("True", "False", "None"))


def fixed_namespace():
    """
    RETURN: dict, the names every constraint of every run may use --
            functions and constants, freshly copied.

    The run's own bindings are laid over this; the copy is what keeps one
    run's bindings out of the next one's namespace.
    """
    return {**FUNCTION_DB, **CONSTANT_DB}


def namespace_of(binding_db):
    """
    RETURN: dict, the namespace ONE evaluation sees: the fixed names, and
            the variables the run has bound so far.

    'binding_db' is the constraint space's current bindings. A binding
    NEVER shadows a fixed name -- a variable cannot be called 'sin' -- so
    the order of composition decides nothing, and the refusal happens
    where a constraint is built, not here.
    """
    return {**FUNCTION_DB, **CONSTANT_DB, **binding_db}
