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

  -- A CONSTRAINT FIRES ONCE ALL ITS VARIABLES ARE IN THE SPACE (C-19).
     Until then it does not fire: a variable not (yet) bound is no
     violation. It fires again whenever one of its variables is bound anew.
  -- A SUBJECT-side violation -- constraint false, division by zero, ANY
     evaluation failure -- makes the test FAIL with the binding's cell a
     MISMATCH (red). Never loud.
  -- A NOMINAL-side violation is a BROKEN SPECIFICATION: the GOOD file's
     own data breaks its own law. It is a FINDING, never an exception
     (C-20): the pair is non-equivalent, and the caller is told which
     side broke which law ('ConstraintFinding').
  -- EVERY VARIABLE A CONSTRAINT NAMES MUST BE BOUND (C-20). A stream that
     ends equivalent with a named variable never bound on a side is NOT
     equivalent: the constraint definition and the stream disagree.
  -- Constraint bindings are allowed ONLY where line sequentiality is
     maintained: the outer text. In order-free scopes (potpourri, unordered
     or keyed tables) a NOMINAL binding is a loud 'RegionSyntaxError'.
  -- An expression belongs to EVERY variable it names (C-19): "y >= x"
     is checked when 'y' is bound and when 'x' is -- once both are there.
     There is no circularity: an expression over two variables relates
     them, it does not order them.

EXECUTION: constraints are inspected as AST elements against a strict
whitelist (arithmetic, comparisons, boolean logic, math functions, Python
string methods) and executed by Python with empty builtins -- the same
safety envelope as 'region/point_cloud/expression.py' (D-22).

THE LAW: both faces process bindings in the SAME line order and STOP at the
first non-equivalent pair (the Judge aborts; the Lawyer kills the space via
'ConstraintContext.kill()'). Hence a finding -- a violation on either side,
a named variable never bound -- is found by both faces or by neither:
reachability is mirrored.

Context threading uses a ContextVar (like 'frozen_analogy_db'): local to
the thread / asyncio task, set by 'main.py' only when 'constraint_db' is
non-empty -- otherwise the feature costs nothing.
________________________________________________________________________________
"""
import ast
import contextvars
import math


class ConstraintSpecError(Exception):
    """A BROKEN CONSTRAINT DEFINITION -- LOUD, before any line is read: an
    unparseable or unsafe expression. A GOOD file breaking its own
    constraint is a FINDING since C-20, not this.
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
                % (variable, text, e.msg)) from None
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
                    # ANY other name is a VARIABLE of the constraint space.
                    # Whether it is BOUND is a RUNTIME question: until it
                    # is, the expression does not fire (C-19) -- never a
                    # static error.
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

        Called only once every variable of 'depend_set' is in 'value_db'
        (C-19: 'ConstraintSpace.enter' decides).
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
    expression whitelisting and name resolution.

    AN EXPRESSION BELONGS TO EVERY VARIABLE IT NAMES (C-19), whichever
    variable the dictionary filed it under -- so binding any one of them
    brings it up, and it fires once all are bound. Filed twice (the page's
    list gives it to each of its variables), it is held once per variable.
    """
    __slots__ = ("db",)

    def __init__(self, spec_db):
        """RETURNS: (constructor) -- raises ConstraintSpecError on any
        malformed constraint.

        'spec_db': dict variable name -> expression string, or list/tuple of
        expression strings (e.g. Configuration.constraint_db).
        """
        text_db = {}                  # variable -> {text: expression}
        for variable, spec in spec_db.items():
            if isinstance(spec, str): spec_list = (spec,)
            else:                     spec_list = tuple(spec)
            for text in spec_list:
                expression = ConstraintExpression(variable, text)
                for name in sorted(expression.depend_set | {variable}):
                    text_db.setdefault(name, {}).setdefault(text, expression)
        self.db = {variable: tuple(by_text.values())
                   for variable, by_text in text_db.items()}

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
        """RETURNS: None,                  if every constraint of 'name' that
                                           FIRES holds
                    ConstraintExpression,  the FIRST failing constraint --
                                           false, or ANY evaluation failure
                                           (div by zero, type clash, ...).
        A constraint fires only once ALL its variables are in the space
        (C-19); before that it is passed over, never failed.
        The value is stored either way; later entries may refer to it.
        """
        self.value_db[name] = value
        for expression in self.constraint_db.get(name):
            if not expression.depend_set <= self.value_db.keys():
                continue            # not all bound yet: does not fire
            try:
                ok = expression(self.value_db)
            except Exception:
                return expression   # div-zero / type clash / any failure
            if not ok:
                return expression
        return None


class ConstraintFinding:
    """WHAT A CONSTRAINT FOUND (C-20): on which side, of which kind, under
    which expression -- told to the caller, never raised.

        side        "OUTPUT" (the subject) or "GOOD" (the nominal)
        kind        "violated" -- a binding broke the expression (or its
                                  evaluation failed)
                    "unbound"  -- the stream ended with 'variable' never
                                  bound
        expression  the expression as written
        variable    the variable concerned
        value       the bound value ("violated"); None else
        line_n      the line of the binding ("violated"); None else
        value_db    every variable the expression names -> its value when
                    the finding was made; one never bound is absent
    """
    __slots__ = ("side", "kind", "expression", "variable", "value",
                 "line_n", "value_db")

    def __init__(self, side, kind, expression, variable, value=None,
                 line_n=None, value_db=None):
        self.side = side;             self.kind = kind
        self.expression = expression; self.variable = variable
        self.value = value;           self.line_n = line_n
        self.value_db = dict(value_db or {})

    def text(self):
        """RETURN: str, the finding as one sentence, naming the side."""
        if self.kind == "unbound":
            return "%s: constraint \"%s\": '%s' never bound" \
                   % (self.side, self.expression, self.variable)
        value = '"%s"' % self.value if isinstance(self.value, str) \
                else self.value
        return "%s: constraint \"%s\": broken by ((%s: %s))%s" \
               % (self.side, self.expression, self.variable, value,
                  "" if self.line_n is None else ", line %s" % self.line_n)

    def remark(self):
        """
        RETURN: str, what is written into the text where the finding was
                made (services E-123):

                    error: "<expression>" with: <variable>=<value> ...

                every variable the expression names, in name order, with
                the value it held; one never bound as '(never bound)'.
                No side and no line: the file and the place say both.
        """
        pair_list = []
        for name in sorted(set(self.value_db) | {self.variable}):
            if name in self.value_db:
                value = self.value_db[name]
                text  = '"%s"' % value if isinstance(value, str) else value
            else:
                text  = "(never bound)"
            pair_list.append("%s=%s" % (name, text))
        return 'error: "%s" with: %s' % (self.expression, " ".join(pair_list))

    def __repr__(self):
        """RETURN: str, the sentence."""
        return self.text()


class ConstraintContext:
    """The per-run pair of constraint spaces (subject side, nominal side)
    plus the shared liveness flag. 'alive == False' mirrors the Judge's
    abort: after the first non-equivalent pair NO further binding is
    processed on either face -- reachability of every finding stays
    identical between Judge and Lawyer (THE LAW).
    """
    __slots__ = ("subject_space", "nominal_space", "alive", "finding_list")

    def __init__(self, constraint_db, finding_list=None):
        self.subject_space = ConstraintSpace(constraint_db)
        self.nominal_space = ConstraintSpace(constraint_db)
        self.alive         = True
        #  THE CALLER'S LIST, where one was handed in: findings leave
        #  compare here (C-20).
        self.finding_list  = finding_list if finding_list is not None \
                             else []

    def unbound_found(self):
        """
        RETURN: bool, a variable some constraint names was never bound on
                a side -- one 'unbound' finding per side, expression and
                variable is added to 'finding_list' (C-20).

        Asked at the END of an equivalent stream only, and only while the
        space is alive -- where both faces reach it (THE LAW).
        """
        found_f = False
        for side, space in (("GOOD", self.nominal_space),
                            ("OUTPUT", self.subject_space)):
            for variable in sorted(space.constraint_db.db):
                if variable in space.value_db: continue
                for expression in space.constraint_db.get(variable):
                    self.finding_list.append(ConstraintFinding(
                        side, "unbound", expression.text, variable,
                        value_db={n: space.value_db[n]
                                  for n in expression.depend_set
                                  if n in space.value_db}))
                    found_f = True
        return found_f

    def kill(self):
        """RETURNS: None -- freezes both spaces: no further '.enter()' calls
        are made by the faces (they check '.alive' first).
        """
        self.alive = False


# Context variable, local to thread / asyncio task -- like the frozen
# analogy registry. 'None' == no constraints configured: zero overhead.
context_constraint_context = contextvars.ContextVar(
    "context_constraint_context", default=None)


def context_new(config, finding_list=None):
    """RETURNS: token to reset 'context_constraint_context' with -- sets a
                fresh ConstraintContext if 'config.constraint_db' is
                non-empty, else sets None. Its findings go to
                'finding_list' where one is given (C-20).
    Raises ConstraintSpecError on a malformed constraint dictionary
    (static checks happen HERE, before any line is read).
    """
    spec_db = getattr(config, "constraint_db", None)
    if not spec_db:
        return context_constraint_context.set(None)
    return context_constraint_context.set(
        ConstraintContext(ConstraintDb(spec_db), finding_list))


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
    from vut.engine.compare.contract.enums import E_ToleranceId
    for element in line.sequence:
        if element.tolerance_id is E_ToleranceId.CONSTRAINT_BINDING:
            yield element.name, element.value


def enter_line(context, subject_line, nominal_line):
    """RETURNS: True,  if every binding of both lines entered its space
                       with all its constraints holding;
                False, if a binding failed on either side -> the pair is a
                       MISMATCH (red cell) for the caller to enact; the
                       space is killed and a 'violated' finding names the
                       side (C-20). The NOMINAL is checked FIRST: the GOOD
                       file violating its own constraints is a broken
                       specification, and specification precedes judgment.

    INSIGNIFICANT lines (blank / ignored-marker) never feed the space: the
    Judge's pipe drops them before it ever sees them, so the Lawyer must
    skip them too -- or THE LAW breaks on a binding inside an ignored line.
    """
    if nominal_line is not None and nominal_line.is_insignificant():
        nominal_line = None
    if subject_line is not None and subject_line.is_insignificant():
        subject_line = None
    for side, space, line in (("GOOD",   context.nominal_space, nominal_line),
                              ("OUTPUT", context.subject_space, subject_line)):
        for name, value in iter_bindings(line):
            failed = space.enter(name, value)
            if failed is None: continue
            context.finding_list.append(ConstraintFinding(
                side, "violated", failed.text, name, value, line.line_n,
                value_db={n: space.value_db[n] for n in failed.depend_set
                          if n in space.value_db}))
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
