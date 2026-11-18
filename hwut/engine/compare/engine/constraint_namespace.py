"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
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

THE AUTHOR'S OWN NAMES (ruled 2026-11-18): a tolerance may name ONE
Python file,

    tolerance { constraint_module = "laws.py" }

read from the directory of the file that says it. EVERY PUBLIC NAME of
it enters the namespace flat -- '__all__' where the file states one, else
every top-level name without a leading '_' -- a callable as a function,
anything else as a constant; a module the file imported ('numpy') is no
name of the namespace, what the file takes from it is ('from statistics
import fmean'). Anything a law calls beyond the fixed names comes from
that file. A name of the file that is a fixed name REPLACES it, said once
on stderr where the file is loaded. A file that cannot be loaded --
missing, not Python, raising on import -- is a fault of the specification,
said before any line is read.

The file's code is the AUTHOR'S, as a pype script is: it runs in the
comparing process, unfenced. 'Nothing with a side effect' is a law over
the fixed names; over the file's it is the author's.
________________________________________________________________________________
"""
import math
import os
import sys

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


def quantity(text):
    """
    RETURN: pint.Quantity, the quantity 'text' spells ('50 ms'), if
            success; raises else -- a word pint does not know, or pint
            absent. A literal '50 ms' in a constraint is read as
            'quantity("50 ms")' (the book's RQ-7); bound quantities and
            these compare through pint, converting units, and a
            comparison across dimensions FAILS the constraint.
    """
    from ....auxiliary.units import quantity_of
    return quantity_of(text)


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

# ------------------------------------------------------------------------------
# UNITS IN THE MATHS (book D-92, compare C-25)
# ------------------------------------------------------------------------------
#  'math' sees a magnitude: 'hypot(30 m, 40 ft)' raised "meter to
#  dimensionless", said as "a number without unit -- write its unit" over
#  a law whose every unit was written. Each maths name is ONE of four
#  kinds; over plain numbers every one is 'math''s own, unchanged.
#
#    keeps the unit   hypot sqrt pow floor ceil trunc fabs fmod copysign
#                     -- pint's arithmetic, units converted to the first
#    compares         isclose isfinite isinf isnan -- units converted
#    angle or plain   sin cos tan sinh cosh tanh exp log log2 log10
#                     degrees radians -- an angle is taken in radian
#    plain            asin acos atan atan2 gcd factorial -- a ratio of
#                     one dimension ('atan2(north, east)') is plain
#
#  Anything else is REFUSED, naming the function, what it needs, and the
#  argument's dimension ('ArgumentUnitError').

class ArgumentUnitError(Exception):
    """A MATHS FUNCTION GIVEN A QUANTITY IT CANNOT TAKE (D-92).

        function    its name, 'sin'
        need        what it takes, 'an angle or a plain number'
        pair_list   [(argument index, value)] -- those it refuses
    """
    def __init__(self, function, need, pair_list):
        self.function, self.need, self.pair_list = function, need, pair_list
        super().__init__("%s needs %s" % (function, need))


def _quantity_f(value):
    """RETURN: bool, True if 'value' carries a unit (a pint Quantity)."""
    return hasattr(value, "units") and hasattr(value, "magnitude")


def _plain_of(name, need, value, index, angle_f=False):
    """
    RETURN: float or int, 'value' as a plain number -- itself where it
            carries no unit; a dimensionless quantity's number ('m/m');
            an angle in radian where 'angle_f' admits one;
            raises ArgumentUnitError naming 'name' and 'need', else -- a
            dimension, or an angle where none is admitted.
    """
    if not _quantity_f(value): return value
    if not value.dimensionless:
        raise ArgumentUnitError(name, need, [(index, value)])
    #  pint holds an angle dimensionless; its base unit tells it apart.
    base = value.to_base_units()
    if "radian" in str(base.units):
        if not angle_f: raise ArgumentUnitError(name, need, [(index, value)])
        return value.to("radian").magnitude
    return base.magnitude


def _angle_or_plain(name):
    """RETURN: callable, math's 'name' over a plain number or an angle."""
    function = getattr(math, name)
    need = "an angle or a plain number"

    def call(x, *rest):
        """RETURN: float, math's function of 'x', an angle in radian; a
                   further argument ('log(x, 2)''s base) plain."""
        return function(_plain_of(name, need, x, 0, angle_f=True),
                        *[_plain_of(name, need, y, i + 1)
                          for i, y in enumerate(rest)])
    call.__name__ = name
    return call


def _plain(name):
    """RETURN: callable, math's 'name' over plain numbers -- a
               dimensionless quantity counts as one."""
    function = getattr(math, name)
    need = "plain numbers"

    def call(*argument_list):
        """RETURN: math's function of the arguments, made plain."""
        return function(*[_plain_of(name, need, x, i)
                          for i, x in enumerate(argument_list)])
    call.__name__ = name
    return call


def _same_unit_list(name, argument_list):
    """
    RETURN: list, the arguments, each a quantity in the unit of the first
            that carries one -- a plain number taken as dimensionless
            where that unit is; the arguments as they are where none
            carries a unit;
            raises ArgumentUnitError naming the first and the one that
            does not compare with it.
    """
    index_first = next((i for i, x in enumerate(argument_list)
                        if _quantity_f(x)), None)
    if index_first is None: return list(argument_list)
    first  = argument_list[index_first]
    result = []
    for i, x in enumerate(argument_list):
        if not _quantity_f(x):
            if not first.dimensionless:
                raise ArgumentUnitError(name, "values of one dimension",
                                        [(index_first, first), (i, x)])
            x = first.__class__(x, "dimensionless")
        if x.dimensionality != first.dimensionality:
            raise ArgumentUnitError(name, "values of one dimension",
                                    [(index_first, first), (i, x)])
        result.append(x.to(first.units))
    return result


def _with_unit(value, magnitude):
    """RETURN: 'magnitude' in the unit of 'value' where it carries one;
               'magnitude' itself else."""
    if not _quantity_f(value): return magnitude
    return value.__class__(magnitude, value.units)


def hypot(*argument_list):
    """
    RETURN: the Euclidean norm of the arguments -- in the unit of the
            first, the others converted ('hypot(30 m, 40 ft)' is 32.38 m);
            a plain number where none carries a unit.
    """
    if not any(_quantity_f(x) for x in argument_list):
        return math.hypot(*argument_list)
    q_list = _same_unit_list("hypot", argument_list)
    return sum(x ** 2 for x in q_list) ** 0.5


def sqrt(x):
    """RETURN: the square root of 'x' -- of its unit too ('144 m**2' gives
               12 m); math's where 'x' is plain."""
    if not _quantity_f(x): return math.sqrt(x)
    if x.magnitude < 0: return math.sqrt(x.magnitude)   # math's ValueError
    return x ** 0.5


def pow(x, y):                                          # noqa: A001
    """RETURN: 'x' to the power 'y' -- its unit too ('pow(3 m, 2)' is
               9 m**2); 'y' a plain number. math's where both are plain."""
    y = _plain_of("pow", "a plain number as its exponent", y, 1)
    if not _quantity_f(x): return math.pow(x, y)
    return x ** y


def _keeping(name):
    """RETURN: callable, math's one-argument 'name' over the magnitude,
               the unit kept ('floor(3.7 m)' is 3 m)."""
    function = getattr(math, name)

    def call(x):
        """RETURN: math's function of 'x''s magnitude, in 'x''s unit."""
        if not _quantity_f(x): return function(x)
        return _with_unit(x, function(x.magnitude))
    call.__name__ = name
    return call


def _keeping_two(name):
    """RETURN: callable, math's two-argument 'name' over magnitudes in the
               first's unit, that unit kept ('fmod(7 m, 300 cm)' is 1 m)."""
    function = getattr(math, name)

    def call(x, y):
        """RETURN: math's function of the two, in 'x''s unit."""
        if not (_quantity_f(x) or _quantity_f(y)): return function(x, y)
        x, y = _same_unit_list(name, [x, y])
        return _with_unit(x, function(x.magnitude, y.magnitude))
    call.__name__ = name
    return call


def _comparing(name):
    """RETURN: callable, math's 'name' over magnitudes in one unit
               ('isclose(1 m, 100 cm)' is True)."""
    function = getattr(math, name)

    def call(*argument_list, **keyword_db):
        """RETURN: math's function of the magnitudes, units converted; a
                   keyword with a unit ('abs_tol') read in the first's."""
        if not any(_quantity_f(x) for x in argument_list):
            return function(*argument_list, **keyword_db)
        q_list = _same_unit_list(name, argument_list)
        unit   = next(x for x in q_list if _quantity_f(x)).units
        keyword_db = {k: v.to(unit).magnitude if _quantity_f(v) else v
                      for k, v in keyword_db.items()}
        return function(*[getattr(x, "magnitude", x) for x in q_list],
                        **keyword_db)
    call.__name__ = name
    return call


def atan2(y, x):
    """RETURN: float, the angle in radian of the point ('x', 'y') -- two
               values of one dimension, or two plain numbers."""
    if not (_quantity_f(x) or _quantity_f(y)): return math.atan2(y, x)
    y, x = _same_unit_list("atan2", [y, x])
    return math.atan2(getattr(y, "magnitude", y), getattr(x, "magnitude", x))


def degrees(x):
    """RETURN: float, 'x' in degrees -- an angle as it stands ('degrees(
               30 deg)' is 30), a plain number read as radian."""
    if not _quantity_f(x): return math.degrees(x)
    _plain_of("degrees", "an angle or a plain number", x, 0, angle_f=True)
    return x.to("degree").magnitude


def radians(x):
    """RETURN: float, 'x' in radian -- an angle as it stands, a plain
               number read as degrees."""
    if not _quantity_f(x): return math.radians(x)
    return _plain_of("radians", "an angle or a plain number", x, 0,
                     angle_f=True)


_UNIT_MATH_DB = {
    "hypot": hypot, "sqrt": sqrt, "pow": pow, "atan2": atan2,
    "degrees": degrees, "radians": radians,
    **{n: _keeping(n)     for n in ("floor", "ceil", "trunc", "fabs")},
    **{n: _keeping_two(n) for n in ("fmod", "copysign")},
    **{n: _comparing(n)   for n in ("isclose", "isfinite", "isinf",
                                    "isnan")},
    **{n: _angle_or_plain(n) for n in ("sin", "cos", "tan", "sinh",
                                       "cosh", "tanh", "exp", "log",
                                       "log2", "log10")},
    **{n: _plain(n)       for n in ("asin", "acos", "atan", "gcd",
                                    "factorial")},
}
assert set(_UNIT_MATH_DB) == set(_MATH_NAME_LIST)

#  WHAT A CONSTRAINT MAY CALL.
FUNCTION_DB = {
    **_UNIT_MATH_DB,
    "len": len, "abs": abs, "min": min, "max": max, "sum": sum,
    "int": int, "float": float, "str": str, "bool": bool,
    "round": round, "ord": ord, "chr": chr,
    "all": all, "any": any, "sorted": sorted,
    "glob": glob, "quantity": quantity,
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


class ConstraintModuleError(Exception):
    """A CONSTRAINT MODULE THAT CANNOT BE LOADED -- missing, not Python, or
    raising on import. Its text names the file and Python's reason."""


class ConstraintNamespace:
    """THE NAMES THE LAWS OF ONE CONFIGURATION MAY USE: the fixed ones, and
    the public names of its 'constraint_module', where it names one.

        function_db         name -> callable a law may call
        constant_db         name -> value a law may name
        not_a_variable_set  every name a binding may not carry
        module_path         the file's absolute path; None: fixed names only
        replaced_tuple      the fixed names the file replaces, sorted
    """
    __slots__ = ("function_db", "constant_db", "not_a_variable_set",
                 "module_path", "replaced_tuple")

    def __init__(self, module_path=None, name_db=None):
        """
        RETURN: (constructor) -- the fixed names, each 'name_db' entry laid
                over them: a callable as a function, anything else as a
                constant.
        """
        self.module_path = module_path
        self.function_db = dict(FUNCTION_DB)
        self.constant_db = dict(CONSTANT_DB)
        fixed_set = set(FUNCTION_DB) | set(CONSTANT_DB)
        for name, value in (name_db or {}).items():
            self.function_db.pop(name, None)
            self.constant_db.pop(name, None)
            if callable(value): self.function_db[name] = value
            else:               self.constant_db[name] = value
        self.replaced_tuple = tuple(sorted(set(name_db or ()) & fixed_set))
        self.not_a_variable_set = frozenset(self.function_db) \
                                  | frozenset(self.constant_db) \
                                  | frozenset(("True", "False", "None"))

    def scope(self, binding_db):
        """
        RETURN: dict, the namespace ONE evaluation sees: the names of this
                namespace, and the variables bound so far ('binding_db').
                A binding never shadows a name here -- the refusal happens
                where a constraint is built.
        """
        return {**self.function_db, **self.constant_db, **binding_db}


FIXED_NAMESPACE = ConstraintNamespace()


def module_path_of(text, directory=None):
    """
    RETURN: str, the absolute path of the constraint module 'text' names
            (ruled 2026-11-18): as written where absolute, else read from
            'directory' -- the test directory -- or, where None, from
            where the face stands.
    """
    path = os.path.expanduser(text)
    if not os.path.isabs(path):
        path = os.path.join(directory or os.getcwd(), path)
    return os.path.abspath(path)

#  ONE LOAD PER FILE AND STATE: path -> (mtime_ns, size, namespace).
_LOADED_DB = {}


def _shown(module_path):
    """RETURN: str, 'module_path' as a reader finds it: from where the face
               stands where it lies below, else absolute."""
    relative = os.path.relpath(module_path)
    return module_path if relative.startswith("..") else relative


def namespace_for(module_path):
    """
    RETURN: ConstraintNamespace, the names of a configuration whose
            'constraint_module' is 'module_path' (an absolute path) --
            the fixed names alone where it is None;
            raises ConstraintModuleError naming the file and the reason,
            where the file cannot be loaded.

    A file is loaded once while it stands unchanged; the first load says
    on stderr which fixed names it replaces.
    """
    if module_path is None: return FIXED_NAMESPACE
    try:
        stat = os.stat(module_path)
    except OSError as error:
        raise ConstraintModuleError(
            "constraint_module '%s': no such file (%s)"
            % (_shown(module_path), error.strerror)) from None
    key = (stat.st_mtime_ns, stat.st_size)
    entry = _LOADED_DB.get(module_path)
    if entry is not None and entry[0] == key: return entry[1]
    namespace = ConstraintNamespace(module_path, _public_name_db(module_path))
    _LOADED_DB[module_path] = (key, namespace)
    if namespace.replaced_tuple:
        sys.stderr.write(
            "NOTE constraint_module '%s' replaces the constraint "
            "namespace's %s\n"
            % (_shown(module_path),
               ", ".join("'%s'" % n for n in namespace.replaced_tuple)))
    return namespace


def _public_name_db(module_path):
    """
    RETURN: dict, name -> value, every public name of the Python file
            'module_path': those of its '__all__' where it states one,
            else every top-level name without a leading '_'; a module
            object is none (a law cannot reach into it);
            raises ConstraintModuleError, the file does not load.

    The file's own directory stands first on the import path while it
    loads, so a helper beside it is found as Python would find it.
    """
    import importlib.util
    import types
    name = "hwut_constraint_module_%x" % (hash(module_path) & 0xFFFFFFFF)
    spec = importlib.util.spec_from_file_location(name, module_path)
    if spec is None or spec.loader is None:
        raise ConstraintModuleError(
            "constraint_module '%s': not a Python file" % _shown(module_path))
    module = importlib.util.module_from_spec(spec)
    directory = os.path.dirname(module_path)
    sys.path.insert(0, directory)
    try:
        spec.loader.exec_module(module)
    except BaseException as error:                    # noqa: BLE001
        if isinstance(error, KeyboardInterrupt): raise
        raise ConstraintModuleError(
            "constraint_module '%s' does not load: %s: %s"
            % (_shown(module_path), type(error).__name__, error)) from None
    finally:
        try:              sys.path.remove(directory)
        except ValueError: pass
    all_list = getattr(module, "__all__", None)
    if all_list is not None:
        missing = [n for n in all_list if not hasattr(module, n)]
        if missing:
            raise ConstraintModuleError(
                "constraint_module '%s': '__all__' names what it does not "
                "define: %s" % (_shown(module_path),
                                ", ".join("'%s'" % n for n in missing)))
        name_list = list(all_list)
    else:
        name_list = [n for n in vars(module) if not n.startswith("_")]
    return {n: getattr(module, n) for n in name_list
            if not isinstance(getattr(module, n), types.ModuleType)}
