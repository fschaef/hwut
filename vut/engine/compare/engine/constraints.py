"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: STATEFUL CONSTRAINTS -- a constraint space fed by binding elements.

An element matching

    (( <variable-name> : <number>|<quoted-string> ))

in the SEQUENTIAL outer text is a CONSTRAINT BINDING: the variable enters
the run's CONSTRAINT SPACE with the given value. The moment it enters, ALL
constraints defined for that variable are checked. Constraints live in the
configuration as a plain dictionary

    Configuration.constraint_db = {
        "y": "y >= x",
        "t": "t > 0 and t < 100",
    }

mapping variable name -> constraint expression (or a list of expressions).

VERDICT SEMANTICS (the user's ruling, DOC/SEMANTICS.txt sec. 10):

  -- A SUBJECT-side violation -- constraint false, referenced variable not
     (yet) in the space, division by zero, ANY evaluation failure -- makes
     the test FAIL with the binding's cell a MISMATCH (red). Never loud.
  -- A NOMINAL-side violation is a BROKEN SPECIFICATION: the GOOD file's
     own data breaks its own law -> LOUD 'ConstraintSpecError' (the
     malformed-data asymmetry, D-14/D-23).
  -- Constraint bindings are allowed ONLY where line sequentiality is
     maintained: the outer text. In order-free scopes (potpourri, unordered
     or keyed tables) a NOMINAL binding is a loud 'RegionSyntaxError'.
  -- A basic CIRCULARITY test over the constraint dependency graph PRECEDES
     the run: a dependency cycle between DIFFERENT variables is a broken
     specification (loud, at ConstraintDb build time). Self-reference
     ("y >= x" for 'y' referencing 'y') is natural, not a cycle.

EXECUTION: constraints are inspected as AST elements against a strict
whitelist (arithmetic, comparisons, boolean logic, math functions, Python
string methods) and executed by Python with empty builtins -- the same
safety envelope as 'region/point_cloud/expression.py' (D-22).

THE LAW: both faces process bindings in the SAME line order and STOP at the
first non-equivalent pair (the Judge aborts; the Lawyer kills the space via
'ConstraintContext.kill()'). Hence a loud nominal violation is raised by
both faces or by neither -- reachability is mirrored.

Context threading uses a ContextVar (like 'frozen_analogy_db'): local to
the thread / asyncio task, set by 'main.py' only when 'constraint_db' is
non-empty -- otherwise the feature costs nothing.
________________________________________________________________________________
"""
import ast
import contextvars
import math


class ConstraintSpecError(Exception):
    """A BROKEN CONSTRAINT SPECIFICATION -- always LOUD, never a verdict:
    unparseable/unsafe expression, unknown name, dependency cycle, or the
    NOMINAL's own data violating the nominal's own constraint (asymmetry
    rule: the GOOD file is the law giver; a law giver breaking his own law
    is a defect of the specification, not of the subject).
    """
    def __init__(self, msg, line_n=None):
        self.line_n = line_n
        if line_n is not None:
            msg = "line %s: %s" % (line_n, msg)
        super().__init__(msg)


# ------------------------------------------------------------------------------
# SAFE EVALUATION (AST whitelist; strings included)
# ------------------------------------------------------------------------------

SAFE_FUNCTION_DB = {
    "abs":   abs,       "min":   min,       "max":   max,
    "sqrt":  math.sqrt, "exp":   math.exp,  "log":   math.log,
    "sin":   math.sin,  "cos":   math.cos,  "tan":   math.tan,
    "asin":  math.asin, "acos":  math.acos, "atan":  math.atan,
    "atan2": math.atan2,"floor": math.floor,"ceil":  math.ceil,
    "round": round,     "hypot": math.hypot,
    # string-capable additions:
    "len":   len,       "str":   str,       "int":   int,
    "float": float,
}

SAFE_CONSTANT_DB = {
    "pi": math.pi, "e": math.e, "inf": math.inf,
}

# Python string methods callable on values in a constraint ("s.lower()"):
SAFE_STR_METHOD_SET = frozenset((
    "startswith", "endswith", "lower", "upper", "strip", "lstrip", "rstrip",
    "replace", "find", "rfind", "count", "split",
    "isdigit", "isalpha", "isalnum", "isspace", "islower", "isupper",
))

_SAFE_NODE_TYPES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
    ast.IfExp, ast.Call, ast.Name, ast.Load, ast.Constant, ast.Subscript,
    ast.Tuple, ast.Attribute,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
)


class ConstraintExpression:
    """A validated, compiled constraint expression over the constraint
    variables. Whitelisted at PARSE time (see module purpose); evaluation
    happens against the current constraint space values.
    """
    __slots__ = ("text", "variable", "depend_set", "_code")

    def __init__(self, variable, text):
        """RETURNS: (constructor) -- raises ConstraintSpecError if 'text' is
        not a pure whitelisted expression.
        """
        self.text     = text
        self.variable = variable
        try:
            tree = ast.parse(text, mode="eval")
        except SyntaxError as e:
            raise ConstraintSpecError(
                "constraint for '%s': %r is not parseable (%s)"
                % (variable, text, e.msg))
        self.depend_set = self._validate(tree)
        self._code      = compile(tree, "<constraint>", "eval")

    def _validate(self, tree):
        """RETURNS: frozenset of variable names the expression refers to
                    (the dependency set) -- raises ConstraintSpecError on
                    any construct outside the whitelist.
        """
        depend_set = set()
        for node in ast.walk(tree):
            if not isinstance(node, _SAFE_NODE_TYPES):
                raise ConstraintSpecError(
                    "constraint for '%s': %r: '%s' is not allowed"
                    % (self.variable, self.text, type(node).__name__))
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    if func.id not in SAFE_FUNCTION_DB or node.keywords:
                        raise ConstraintSpecError(
                            "constraint for '%s': %r: only calls to %s "
                            "or string methods are allowed"
                            % (self.variable, self.text,
                               ", ".join(sorted(SAFE_FUNCTION_DB))))
                elif isinstance(func, ast.Attribute):
                    pass  # checked as ast.Attribute below
                else:
                    raise ConstraintSpecError(
                        "constraint for '%s': %r: computed calls are "
                        "not allowed" % (self.variable, self.text))
            elif isinstance(node, ast.Attribute):
                if node.attr not in SAFE_STR_METHOD_SET:
                    raise ConstraintSpecError(
                        "constraint for '%s': %r: attribute '%s' is not "
                        "allowed (string methods: %s)"
                        % (self.variable, self.text, node.attr,
                           ", ".join(sorted(SAFE_STR_METHOD_SET))))
            elif isinstance(node, ast.Name):
                if (node.id not in SAFE_FUNCTION_DB
                        and node.id not in SAFE_CONSTANT_DB):
                    # ANY other name is a VARIABLE of the constraint space
                    # -- possibly one without constraints of its own (an
                    # input, e.g. 'x' in "y >= x"). Whether it EXISTS is a
                    # RUNTIME question: missing at check time -> red cell
                    # (the ruling), never a static error.
                    depend_set.add(node.id)
            elif isinstance(node, ast.Constant):
                if not isinstance(node.value, (int, float, bool, str)):
                    raise ConstraintSpecError(
                        "constraint for '%s': %r: only numeric and string "
                        "constants are allowed" % (self.variable, self.text))
        return frozenset(depend_set)

    def __call__(self, value_db):
        """RETURNS: the expression's truth value under 'value_db' (variable
                    name -> current value). Raises whatever the evaluation
                    raises (NameError on a missing variable, ZeroDivisionError,
                    TypeError, ...) -- the CALLER maps failure to a verdict.

        Only PRESENT variables are bound: a missing one raises NameError
        exactly when the evaluation actually needs it -- short-circuit logic
        ('y == 2 or y >= x') may pass without 'x' ever having entered.
        """
        scope = dict(SAFE_FUNCTION_DB)
        scope.update(SAFE_CONSTANT_DB)
        for name in self.depend_set:
            if name in value_db:
                scope[name] = value_db[name]
        return eval(self._code, {"__builtins__": {}}, scope)  # noqa: S307
        # 'eval' runs a WHITELIST-VALIDATED, freshly compiled expression
        # with empty builtins -- see module purpose.


# ------------------------------------------------------------------------------
# CONSTRAINT DATABASE (from the configuration; static checks are LOUD)
# ------------------------------------------------------------------------------

class ConstraintDb:
    """The compiled constraint dictionary: variable name -> tuple of
    'ConstraintExpression'. Construction performs ALL static checks LOUDLY:
    expression whitelisting, name resolution, and the circularity pre-check
    over the dependency graph.
    """
    __slots__ = ("db",)

    def __init__(self, spec_db):
        """RETURNS: (constructor) -- raises ConstraintSpecError on any
        malformed constraint or a dependency cycle.

        'spec_db': dict variable name -> expression string, or list/tuple of
        expression strings (e.g. Configuration.constraint_db).
        """
        self.db = {}
        for variable, spec in spec_db.items():
            if isinstance(spec, str): spec_list = (spec,)
            else:                     spec_list = tuple(spec)
            self.db[variable] = tuple(
                ConstraintExpression(variable, text)
                for text in spec_list)
        self._check_circularity()

    def _check_circularity(self):
        """RETURNS: None -- raises ConstraintSpecError if the dependency
        graph 'variable -> variables its constraints refer to' contains a
        cycle between DIFFERENT variables (self-reference is natural).
        """
        edge_db = {
            variable: set().union(*(e.depend_set for e in expression_list))
                      - {variable}
            for variable, expression_list in self.db.items()
        }
        DONE, IN_PROGRESS = 1, 2
        state_db = {}

        def visit(variable, path):
            state_db[variable] = IN_PROGRESS
            for dep in sorted(edge_db.get(variable, ())):
                if state_db.get(dep) is IN_PROGRESS:
                    cycle = path[path.index(dep):] + [dep] \
                            if dep in path else [variable, dep]
                    raise ConstraintSpecError(
                        "constraint dependency cycle: %s"
                        % " -> ".join(cycle))
                elif state_db.get(dep) is not DONE:
                    visit(dep, path + [dep])
            state_db[variable] = DONE

        for variable in sorted(self.db):
            if state_db.get(variable) is not DONE:
                visit(variable, [variable])

    def get(self, variable):
        """RETURNS: tuple of ConstraintExpression for 'variable';
                    (), if no constraint is defined for it.
        """
        return self.db.get(variable, ())


# ------------------------------------------------------------------------------
# CONSTRAINT SPACE (per input side; check-on-entry)
# ------------------------------------------------------------------------------

class ConstraintSpace:
    """The evolving variable space of ONE input side. '.enter()' implements
    the ruling's core: the moment a variable enters, all constraints defined
    for it are checked against the CURRENT space.
    """
    __slots__ = ("constraint_db", "value_db")

    def __init__(self, constraint_db):
        self.constraint_db = constraint_db
        self.value_db      = {}

    def enter(self, name, value):
        """RETURNS: None,                  if all constraints of 'name' hold
                    ConstraintExpression,  the FIRST failing constraint --
                                           false, missing dependency, or ANY
                                           evaluation failure (div by zero,
                                           type clash, ...).
        The value is stored either way; later entries may refer to it.
        """
        self.value_db[name] = value
        for expression in self.constraint_db.get(name):
            try:
                ok = expression(self.value_db)
            except Exception:
                return expression   # missing dep / div-zero / any failure
            if not ok:
                return expression
        return None


class ConstraintContext:
    """The per-run pair of constraint spaces (subject side, nominal side)
    plus the shared liveness flag. 'alive == False' mirrors the Judge's
    abort: after the first non-equivalent pair NO further binding is
    processed on either face -- reachability of loud nominal violations
    stays identical between Judge and Lawyer (THE LAW).
    """
    __slots__ = ("subject_space", "nominal_space", "alive")

    def __init__(self, constraint_db):
        self.subject_space = ConstraintSpace(constraint_db)
        self.nominal_space = ConstraintSpace(constraint_db)
        self.alive         = True

    def kill(self):
        """RETURNS: None -- freezes both spaces: no further '.enter()' calls
        are made by the faces (they check '.alive' first).
        """
        self.alive = False


# Context variable, local to thread / asyncio task -- like the frozen
# analogy registry. 'None' == no constraints configured: zero overhead.
context_constraint_context = contextvars.ContextVar(
    "context_constraint_context", default=None)


def context_new(config):
    """RETURNS: token to reset 'context_constraint_context' with -- sets a
                fresh ConstraintContext if 'config.constraint_db' is
                non-empty, else sets None.
    Raises ConstraintSpecError on a malformed constraint dictionary
    (static checks happen HERE, before any line is read).
    """
    spec_db = getattr(config, "constraint_db", None)
    if not spec_db:
        return context_constraint_context.set(None)
    return context_constraint_context.set(
        ConstraintContext(ConstraintDb(spec_db)))


def context_get():
    """RETURNS: the current ConstraintContext,
                None, if no constraints are configured.
    """
    return context_constraint_context.get()


# ------------------------------------------------------------------------------
# BINDING EXTRACTION AND FACE HELPERS
# ------------------------------------------------------------------------------

def iter_bindings(line):
    """RETURNS: iterator over (name, value) of the CONSTRAINT_BINDING
                elements of 'line', in element order;
                empty, if the line has none (or is None).
    """
    if line is None:
        return
    from vut.engine.compare.engine.enums import E_ToleranceId
    for element in line.sequence:
        if element.tolerance_id is E_ToleranceId.CONSTRAINT_BINDING:
            yield element.name, element.value


def enter_line(context, subject_line, nominal_line):
    """RETURNS: True,  if every binding of both lines entered its space
                       with all its constraints holding;
                False, if a SUBJECT-side binding failed -> the pair is a
                       MISMATCH (red cell) for the caller to enact.
    Raises ConstraintSpecError if a NOMINAL-side binding fails: the GOOD
    file violating its own constraints is a broken specification (LOUD;
    checked FIRST -- specification validation precedes judgment).

    INSIGNIFICANT lines (blank / ignored-marker) never feed the space: the
    Judge's pipe drops them before it ever sees them, so the Lawyer must
    skip them too -- or THE LAW breaks on a binding inside an ignored line.
    """
    if nominal_line is not None and nominal_line.is_insignificant():
        nominal_line = None
    if subject_line is not None and subject_line.is_insignificant():
        subject_line = None
    for name, value in iter_bindings(nominal_line):
        failed = context.nominal_space.enter(name, value)
        if failed is not None:
            raise ConstraintSpecError(
                "nominal binding '((%s: %s))' violates the nominal's own "
                "constraint %r -- broken specification"
                % (name, value, failed.text), nominal_line.line_n)
    for name, value in iter_bindings(subject_line):
        failed = context.subject_space.enter(name, value)
        if failed is not None:
            context.kill()
            return False
    return True


def check_no_bindings_nominal(line_list, scope_name):
    """RETURNS: None -- raises RegionSyntaxError if any NOMINAL line of an
    order-free scope contains a constraint binding. Constraint bindings are
    only allowed where line sequentiality is maintained (the ruling); in an
    order-free scope 'the value before' is undefined by construction.
    """
    from vut.engine.compare.region.registry import RegionSyntaxError
    for line in line_list:
        for name, value in iter_bindings(line):
            raise RegionSyntaxError(line.line_n,
                "constraint binding '((%s: %s))' in an order-free scope "
                "(%s) -- constraints require line sequentiality"
                % (name, value, scope_name))
