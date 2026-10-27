"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: STATEFUL CONSTRAINTS -- a constraint space fed by binding elements.

An element matching

    (( <variable-name> : <number> [<unit>]|<quoted-string> ))

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

THE LAW: both faces process bindings in the SAME line order. The Judge
STOPS at the first non-equivalent pair and at the first broken law -- the
verdict is decided there. THE ASSOCIATION IS FREE (C-22): once the Judge
has bailed out it has no judgement to agree with, so the Lawyer's context
('free_f') keeps the space alive past every difference and judges every
law at every binding -- what 'hwut.diff', 'hwut.merge' and 'hwut.accept'
show. Where nothing differs and nothing breaks, both find the same: none,
and a named variable never bound is asked by both at the same point.

Context threading uses a ContextVar (like 'frozen_analogy_db'): local to
the thread / asyncio task, set by 'main.py' only when 'constraint_db' is
non-empty -- otherwise the feature costs nothing.
________________________________________________________________________________
"""
import ast
import contextvars
import keyword
import re

from .constraint_namespace import (CONSTANT_DB, FUNCTION_DB,
                                   STR_METHOD_SET, namespace_of)


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

#  THE TABLES ARE THE NAMESPACE'S (exploration R-66), NOT A SECOND COPY.
#  MEASURED (audit r10, G-3): this module kept tables of its own, and
#  its door read those -- 'glob(...)' passed the validator, which reads
#  'constraint_namespace', and ended the run here in a traceback; 26
#  functions and 2 constants of the ruled namespace were refused, 3
#  string methods allowed that it does not hold. One list, three names.
SAFE_FUNCTION_DB    = FUNCTION_DB
SAFE_CONSTANT_DB    = CONSTANT_DB

#  HOW A CONSTANT IS SAID where a binding carries its name (E-193).
_CONSTANT_SAID_DB = {"pi": "the circle's ratio", "e": "Euler's number",
                     "tau": "two pi", "inf": "infinity",
                     "nan": "not a number"}
SAFE_STR_METHOD_SET = STR_METHOD_SET

_SAFE_NODE_TYPES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
    ast.IfExp, ast.Call, ast.Name, ast.Load, ast.Constant, ast.Subscript,
    ast.Tuple, ast.Attribute,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
)


#  A NUMERAL WITH A UNIT IN A CONSTRAINT (RQ-7): 't < 50 ms', 't < 2.5kN'.
#  Python reads a numeral followed by a word as an error, so the reading
#  takes nothing Python would read otherwise -- except a keyword after
#  the numeral ('5 if', '5 in') and the glued forms Python owns ('0x1f',
#  '0o7', '0b1', '5j'). Strings are passed over whole.
_STRING_SRC  = r"\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'"
#  THE NUMERAL IS THE LONGEST NUMERAL (RQ-6, R1 of 2026-10-24): it never
#  stops where an exponent continues it. Without the look-ahead '1e-9'
#  with no unit after it was re-read as '1' and the unit 'e' -- pint's
#  elementary charge -- and 'x <= 1e-9' compared x with a charge.
_NUMERAL_SRC = (r"(?<![\w.])(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
                r"(?![eE][-+]?\d)")


def _unit_literal_re():
    """RETURN: compiled regex, a string literal (group 'string') or a
               numeral (group 'numeral'), its gap (group 'gap') and its
               unit (group 'unit')."""
    from ....auxiliary.units import UNIT_WORD_SRC
    return re.compile("(?P<string>%s)|(?P<numeral>%s)(?P<gap>[ \t]*)"
                      "(?P<unit>%s)" % (_STRING_SRC, _NUMERAL_SRC,
                                        UNIT_WORD_SRC))


def with_quantity_literals(text, glued_list=None):
    """
    RETURN: str, 'text' with every numeral-and-unit written as the call
            'quantity("<numeral> <unit>")' -- 't < 50 ms' becomes
            't < quantity("50 ms")' -- if success; 'text' itself where
            it holds none;
            raises ConstraintSpecError naming the unit, else: a unit pint
            does not know, or pint absent.
    """
    def replaced(match):
        if match.group("string") is not None: return match.group(0)
        numeral, gap, unit = (match.group("numeral"), match.group("gap"),
                              match.group("unit"))
        head = re.match(r"[A-Za-z_]\w*", unit)
        if head is not None and keyword.iskeyword(head.group(0)):
            return match.group(0)
        if not gap and (unit[0] in "jJ" and len(unit) == 1
                        or (set(numeral) == {"0"} and unit[0] in "xXoObB")):
            return match.group(0)
        #  A GLUED PRODUCT ('10 m*force', services E-193): the longest
        #  unit pint knows, the rest of the word stays the law's.
        rest = ""
        while True:
            literal = "%s %s" % (numeral, unit)
            try:
                from ....auxiliary.units import quantity_of
                quantity_of(literal)
                break
            except ModuleNotFoundError as error:
                raise ConstraintSpecError(
                    "%r: a quantity needs the Python module 'pint' (%s) -- "
                    "'hwut.help' says how to install it" % (text, error)) \
                    from None
            except Exception:                         # noqa: BLE001
                cut = max(unit.rfind("*"), unit.rfind("/"))
                if cut <= 0:
                    raise ConstraintSpecError(
                        "%r: '%s' is no unit ('hwut.pype --units' lists "
                        "them)" % (text, unit + rest)) from None
                unit, rest = unit[:cut], unit[cut:] + rest
        #  WHAT THE UNIT WORD SWALLOWED past its first unit ('kg*a'):
        #  names a binding may also carry (services E-193).
        if glued_list is not None:
            glued_list.extend(
                (literal, part) for part in
                (re.sub(r"(\*\*|\^)-?\d+$", "", piece)
                 for piece in re.split(r"[*/]", unit)[1:]) if part)
        return 'quantity("%s")%s' % (literal, rest)
    return _unit_literal_re().sub(replaced, text)


class ConstraintExpression:
    """A validated, compiled constraint expression over the constraint
    variables. Whitelisted at PARSE time (see module purpose); evaluation
    happens against the current constraint space values.
    """
    __slots__ = ("text", "variable", "depend_set", "_code", "_quantity_f",
                 "_code_q", "glued_tuple")

    def __init__(self, variable, text):
        """RETURNS: (constructor) -- raises ConstraintSpecError if 'text' is
        not a pure whitelisted expression.
        """
        self.text     = text
        self.variable = variable
        glued_list = []
        try:
            source = with_quantity_literals(text, glued_list)
        except ConstraintSpecError as error:
            raise ConstraintSpecError("constraint for '%s': %s"
                                      % (variable, error)) from None
        try:
            tree = ast.parse(source, mode="eval")
        except SyntaxError as e:
            raise ConstraintSpecError(
                "constraint for '%s': %r is not parseable (%s)"
                % (variable, text, e.msg)) from None
        self.depend_set  = self._validate(tree)
        #  (literal, unit part) of every glued unit word -- 'kg*a' in
        #  '2 kg*a': where a binding is called 'a', the law is ambiguous.
        self.glued_tuple = tuple(glued_list)
        self._code       = compile(tree, "<constraint>", "eval")
        #  THE SAME LAW, ITS NUMBERS DIMENSIONLESS (ND12, E-191): evaluated
        #  where quantities take part, so a unit-less number meeting a
        #  quantity fails ('t > 0' over -5 degC) as a unit-less value does
        #  (ND13) -- and '2 * y' stays a factor.
        self._code_q     = compile(_with_dimensionless_numbers(
                                       ast.parse(source, mode="eval")),
                                   "<constraint>", "eval")
        #  A LAW THAT WRITES A QUANTITY ('x == 0 s', or 'quantity(...)'
        #  by hand) -- see '_bare_numbers_dimensionless'.
        self._quantity_f = any(isinstance(node, ast.Call)
                               and isinstance(node.func, ast.Name)
                               and node.func.id == "quantity"
                               for node in ast.walk(tree))

    def _validate(self, tree):
        """RETURNS: frozenset of variable names the expression refers to
                    (the dependency set) -- raises ConstraintSpecError on
                    any construct outside the whitelist.
        """
        depend_set = set()
        #  A FUNCTION'S NAME STANDS ONLY WHERE IT IS CALLED. Anywhere
        #  else it is meant as a VARIABLE, and a variable may not carry a
        #  name of the namespace ('README-constraint_namespace.txt', 4).
        #  MEASURED: "min > 5" named no variable, was filed under none,
        #  and was never checked -- '((min: 1))' passed.
        called_set = {id(node.func) for node in ast.walk(tree)
                      if isinstance(node, ast.Call)}
        for node in ast.walk(tree):
            #  AN EXPONENT IS A SMALL NUMBER (services E-193): units need
            #  'm**2', 's**-1'; '10 ** 10 ** 10' held the run for good.
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow) \
               and not _small_exponent_f(node.right):
                raise ConstraintSpecError(
                    "constraint for '%s': %r: an exponent must be a number "
                    "of magnitude at most %d ('x ** 2', 's ** -1'), not '%s'"
                    % (self.variable, self.text, EXPONENT_MAX,
                       ast.unparse(node.right)))
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
                if (node.id in SAFE_FUNCTION_DB
                        and id(node) not in called_set):
                    raise ConstraintSpecError(
                        "constraint for '%s': %r: '%s' is a function of "
                        "the constraint namespace -- a variable cannot "
                        "carry that name"
                        % (self.variable, self.text, node.id))
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
        if not depend_set:
            #  ONLY CONSTANTS NAMED (book D-72): 'e > 1 J' meant a binding
            #  'e', which a law reads as Euler's number -- say the name and
            #  the remedy, as E-193 does where the binding is read.
            constant_list = sorted({node.id for node in ast.walk(tree)
                                    if isinstance(node, ast.Name)
                                    and node.id in SAFE_CONSTANT_DB})
            if constant_list:
                raise ConstraintSpecError(
                    "constraint for '%s': %r names no variable: %s -- a "
                    "binding cannot carry that name; rename it, in the "
                    "binding and in the law"
                    % (self.variable, self.text,
                       "; ".join("'%s' is a constant of the constraint "
                                 "namespace (%s)"
                                 % (name, _CONSTANT_SAID_DB.get(name, name))
                                 for name in constant_list)))
            raise ConstraintSpecError(
                "constraint for '%s': %r names no variable -- it "
                "constrains nothing" % (self.variable, self.text))
        return frozenset(depend_set)

    def __call__(self, value_db):
        """RETURNS: the expression's truth value under 'value_db' (variable
                    name -> current value). Raises whatever the evaluation
                    raises (NameError on a missing variable, ZeroDivisionError,
                    TypeError, ...) -- the CALLER maps failure to a verdict.

        Called only once every variable of 'depend_set' is in 'value_db'
        (C-19: 'ConstraintSpace.enter' decides).
        """
        value_db = {name: value_db[name]
                    for name in self.depend_set if name in value_db}
        quantity_f = self._quantity_f \
                     or any(hasattr(v, "units") for v in value_db.values())
        value_db = _bare_numbers_dimensionless(value_db, self._quantity_f)
        scope = namespace_of(value_db)
        if not quantity_f:
            return eval(self._code, {"__builtins__": {}}, scope)  # noqa: S307
        from ....auxiliary.units import registry
        ureg = registry()

        def dimensionless(number):
            """RETURN: pint.Quantity, 'number' without unit -- an operand
                       of a law where quantities take part (E-191)."""
            return ureg.Quantity(number, "")
        scope[_DIMENSIONLESS_NAME] = dimensionless
        return eval(self._code_q, {"__builtins__": {}}, scope)  # noqa: S307
        # 'eval' runs a WHITELIST-VALIDATED, freshly compiled expression
        # with empty builtins -- see module purpose.


#  THE LARGEST EXPONENT A LAW MAY WRITE (services E-193).
EXPONENT_MAX = 64


def _small_exponent_f(node):
    """
    RETURN: bool, True if 'node' -- the right side of a '**' -- is a
            number, signed or not, of magnitude at most EXPONENT_MAX;
            False, else: a variable, an expression, a larger number.
    """
    if isinstance(node, ast.UnaryOp) and isinstance(node.op,
                                                    (ast.USub, ast.UAdd)):
        node = node.operand
    return isinstance(node, ast.Constant) \
           and isinstance(node.value, (int, float)) \
           and not isinstance(node.value, bool) \
           and abs(node.value) <= EXPONENT_MAX


#  THE NAME the dimensionless wrapper carries in a law's scope -- one no
#  constraint can write ('_' opens no name of the grammar's variables).
_DIMENSIONLESS_NAME = "_hwut_dimensionless"


def _with_dimensionless_numbers(tree):
    """
    RETURN: ast.Expression, 'tree' with every number that is an OPERAND --
            of arithmetic or of a comparison -- wrapped as
            '_hwut_dimensionless(<number>)'; an exponent, a function's
            argument and a boolean stay as written ('x ** 2',
            'round(x, 2)').
    """
    class Wrap(ast.NodeTransformer):
        """Wraps the operand numbers; leaves exponents and call arguments."""
        def _wrapped(self, node):
            if isinstance(node, ast.Constant) \
               and isinstance(node.value, (int, float)) \
               and not isinstance(node.value, bool):
                return ast.copy_location(ast.Call(
                    func=ast.Name(id=_DIMENSIONLESS_NAME, ctx=ast.Load()),
                    args=[node], keywords=[]), node)
            return self.visit(node)

        def visit_BinOp(self, node):
            node.left = self._wrapped(node.left)
            node.right = self.visit(node.right) if isinstance(node.op, ast.Pow) \
                         else self._wrapped(node.right)
            return node

        def visit_Compare(self, node):
            node.left = self._wrapped(node.left)
            node.comparators = [self._wrapped(c) for c in node.comparators]
            return node

        def visit_UnaryOp(self, node):
            node.operand = self._wrapped(node.operand)
            return node

        def visit_Call(self, node):
            #  A FUNCTION'S ARGUMENTS ARE ITS OWN: 'round(x, 2)' takes digits.
            #  Only their inner arithmetic is visited.
            node.args = [self.visit(arg) for arg in node.args]
            return node

    return ast.fix_missing_locations(Wrap().visit(tree))


def failure_reason(error):
    """
    RETURN: str, why a law over quantities could not be judged, said in a
            reader's words -- a number without unit against a quantity, an
            offset temperature in arithmetic, two units that do not
            compare -- if 'error' is pint's;
            None, else (a division by zero, a type clash: said as before).
    """
    name = type(error).__name__
    text = str(error)
    if name == "OffsetUnitCalculusError":
        return ("an absolute temperature in arithmetic -- write the "
                "difference in delta_degC or K")
    if name == "DimensionalityError":
        if "'dimensionless'" in text:
            return "a number without unit against a quantity -- write its unit"
        #  IN THE SPELLING A PAGE WRITES ('kg', 'ms'), not pint's long form.
        #  AND THEIR DIMENSIONS (services E-193): 'm * N / kg' says less
        #  than '[length] ** 2 / [time] ** 2' does.
        unit_list = [getattr(error, attribute, None)
                     for attribute in ("units1", "units2")]
        dimension_list = [getattr(error, attribute, None)
                          for attribute in ("dim1", "dim2")]
        if all(u is not None for u in unit_list):
            from ....auxiliary.units import registry
            ureg = registry()
            try:
                said = ["%s" % format(ureg.Unit(u), "~") for u in unit_list]
            except Exception:                          # noqa: BLE001
                return "the units do not compare"      # a unit pint cannot say
            if all(d for d in dimension_list):
                said = ["%s (%s)" % (u, d) for u, d in zip(said,
                                                          dimension_list)]
            return "the units do not compare: %s against %s" % tuple(said)
        return "the units do not compare"
    return None


def _bare_numbers_dimensionless(value_db, quantity_f):
    """
    RETURN: dict, 'value_db' with every bare number (int or float, not
            bool) made a DIMENSIONLESS quantity, where the law involves
            quantities -- 'quantity_f' (it writes one) or a value of
            'value_db' that carries a unit;
            'value_db' itself, else.

    PINT'S ZERO EXCEPTION (ND13, services E-182): pint compares a plain
    0 with ANY unit ('0 == 0 s' is True), while every other bare number
    raises. E-175 ruled that a bare number fails a law with a unit; a
    dimensionless 0 is refused like 7, so the law holds for every
    number alike. Laws over plain numbers meet plain numbers, unchanged.
    """
    if not quantity_f and not any(hasattr(value, "units")
                                  for value in value_db.values()):
        return value_db
    from ....auxiliary.units import registry
    ureg = registry()
    return {name: (ureg.Quantity(value, "")
                   if isinstance(value, (int, float))
                   and not isinstance(value, bool) else value)
            for name, value in value_db.items()}


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
    __slots__ = ("constraint_db", "value_db", "reason_db", "glued_failed_db")

    def __init__(self, constraint_db):
        self.constraint_db = constraint_db
        self.value_db      = {}
        self.reason_db     = {}     # expression text -> why it failed, or None
        self.glued_failed_db = {}   # failed expression text -> glued_tuple

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
        failing_tuple = self.failing_tuple(name, value)
        return failing_tuple[0] if failing_tuple else None

    def failing_tuple(self, name, value):
        """
        RETURN: tuple[ConstraintExpression], EVERY constraint of 'name'
                that fires and fails -- false, or any evaluation failure
                -- in definition order; empty where every one that fires
                holds. The value is stored either way.
        """
        self.value_db[name] = value
        found = []
        for expression in self.constraint_db.get(name):
            if not expression.depend_set <= self.value_db.keys():
                continue            # not all bound yet: does not fire
            #  A UNIT WORD THAT SWALLOWED A BINDING'S NAME (E-193): '2 kg*a'
            #  reads kilogram-annum where a binding 'a' stands -- said, never
            #  judged either way.
            clash_list = [(literal, part)
                          for literal, part in expression.glued_tuple
                          if part in self.value_db]
            if clash_list:
                literal, part = clash_list[0]
                self.reason_db[expression.text] = (
                    "'%s' reads '%s' as a unit, and a binding is called "
                    "'%s' -- write '* %s' apart" % (literal, part, part, part))
                found.append(expression)
                continue
            try:
                ok = expression(self.value_db)
            except Exception as error:
                ok = False          # div-zero / type clash / any failure
                #  WHY, WHERE A READER CAN ACT ON IT (ND12, E-191).
                self.reason_db[expression.text] = failure_reason(error)
            if not ok:
                #  A GLUED UNIT WORD WHOSE BINDING MAY STILL COME (E-193):
                #  remembered, said only where that binding does come
                #  ('glued_reason').
                if expression.glued_tuple:
                    self.glued_failed_db[expression.text] = \
                        expression.glued_tuple
                found.append(expression)
        return tuple(found)

    def glued_reason(self, expression_text, name):
        """
        RETURN: str, why the failed law 'expression_text' may have meant
                otherwise -- its glued unit word swallowed 'name', which a
                binding now carries ('2 kg*a', then '((a: 3 m/s**2))') --
                if that is so;
                None, else.
        """
        for literal, part in self.glued_failed_db.get(expression_text, ()):
            if part == name:
                return ("'%s' reads '%s' as a unit, and a binding is called "
                        "'%s' -- write '* %s' apart"
                        % (literal, part, part, part))
        return None


def quoted_expression(expression):
    """
    RETURN: str, 'expression' between double quotes, as every constraint
            is said -- between single quotes where it holds a double quote
            itself, so 'm == "run"' is said as written (the book's D-59b:
            it was echoed '"m == "run""').
    """
    if '"' in expression and "'" not in expression:
        return "'%s'" % expression
    return '"%s"' % expression


def _value_said(value):
    """RETURN: str, a bound value as a page says it: a string quoted, a
               quantity in short form ('2.5 ms', RQ-7), a number as is."""
    if isinstance(value, str): return '"%s"' % value
    from ....auxiliary.units import shown
    return shown(value)


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
        reason      why the law could not be judged, where pint said so
                    (ND12): a number without unit, an offset temperature
                    in arithmetic; None else
    """
    __slots__ = ("side", "kind", "expression", "variable", "value",
                 "line_n", "value_db", "reason")

    def __init__(self, side, kind, expression, variable, value=None,
                 line_n=None, value_db=None, reason=None):
        self.side = side;             self.kind = kind
        self.expression = expression; self.variable = variable
        self.value = value;           self.line_n = line_n
        self.value_db = dict(value_db or {})
        self.reason = reason

    def text(self):
        """RETURN: str, the finding as one sentence, naming the side."""
        if self.kind == "unbound":
            return "%s: constraint %s: '%s' never bound" \
                   % (self.side, quoted_expression(self.expression), self.variable)
        if self.kind == "misnamed":
            return "%s: binding ((%s: %s))%s -- %s" \
                   % (self.side, self.variable, _value_said(self.value),
                      "" if self.line_n is None else ", line %s" % self.line_n,
                      self.reason)
        value = _value_said(self.value)
        return "%s: constraint %s: broken by ((%s: %s))%s%s" \
               % (self.side, quoted_expression(self.expression), self.variable, value,
                  "" if self.line_n is None else ", line %s" % self.line_n,
                  "" if self.reason is None else " -- %s" % self.reason)

    def remark(self):
        """
        RETURN: str, what is written into the text where the finding was
                made (services E-123):

                    error: "<expression>" with: <variable>=<value> ...

                every variable the expression names, in name order, with
                the value it held; one never bound as '(never bound)'.
                No side and no line: the file and the place say both.
                A binding named like a constant: 'error: binding "<name>"
                -- <reason>'.
        """
        if self.kind == "misnamed":
            return 'error: binding "%s" -- %s' % (self.variable, self.reason)
        pair_list = []
        for name in sorted(set(self.value_db) | {self.variable}):
            if name in self.value_db:
                text  = _value_said(self.value_db[name])
            else:
                text  = "(never bound)"
            pair_list.append("%s=%s" % (name, text))
        return 'error: %s with: %s' % (quoted_expression(self.expression),
                                        " ".join(pair_list))

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
    __slots__ = ("subject_space", "nominal_space", "alive", "finding_list",
                 "free_f", "differed_f")

    def __init__(self, constraint_db, finding_list=None, free_f=False):
        self.subject_space = ConstraintSpace(constraint_db)
        self.nominal_space = ConstraintSpace(constraint_db)
        self.alive         = True
        #  THE ASSOCIATION IS FREE (C-22): 'kill' marks a difference and
        #  stops nothing; every law is judged at every binding.
        self.free_f        = free_f
        self.differed_f    = False
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
        """RETURNS: None -- a difference or a broken law was met. The Judge's
        context freezes both spaces: no further '.enter()' calls are made
        by the faces (they check '.alive' first). A FREE context (the
        association, C-22) only remembers it -- 'differed_f' -- and stays
        alive.
        """
        self.differed_f = True
        if not self.free_f:
            self.alive = False

    def whole_f(self):
        """RETURNS: bool, True if the space is alive and nothing differed --
        where the Judge asks whether every named variable was bound, and
        the association asks it too.
        """
        return self.alive and not self.differed_f


# Context variable, local to thread / asyncio task -- like the frozen
# analogy registry. 'None' == no constraints configured: zero overhead.
context_constraint_context = contextvars.ContextVar(
    "context_constraint_context", default=None)


def context_new(config, finding_list=None, free_f=False):
    """RETURNS: token to reset 'context_constraint_context' with -- sets a
                fresh ConstraintContext if 'config.constraint_db' is
                non-empty, else sets None. Its findings go to
                'finding_list' where one is given (C-20); 'free_f' makes
                it the association's, which stops at nothing (C-22).
    Raises ConstraintSpecError on a malformed constraint dictionary
    (static checks happen HERE, before any line is read).
    """
    spec_db = getattr(config, "constraint_db", None)
    if not spec_db:
        return context_constraint_context.set(None)
    return context_constraint_context.set(
        ConstraintContext(ConstraintDb(spec_db), finding_list, free_f))


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
    from ..contract.enums import E_ToleranceId
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
    held_f = True
    for side, space, line in (("GOOD",   context.nominal_space, nominal_line),
                              ("OUTPUT", context.subject_space, subject_line)):
        for name, value in iter_bindings(line):
            #  A BINDING NAMED LIKE A CONSTANT OF THE NAMESPACE (services
            #  E-193): a law reads 'e' as Euler's number, never as this
            #  binding -- refused where the binding is read, by name.
            if name in CONSTANT_DB:
                context.finding_list.append(ConstraintFinding(
                    side, "misnamed", "", name, value, line.line_n,
                    reason="'%s' is a constant of the constraint namespace "
                           "(%s) -- rename the binding"
                           % (name, _CONSTANT_SAID_DB.get(name, name))))
                context.kill()
                held_f = False
                if not context.free_f: return False
                continue
            #  A LAW THAT FAILED BEFORE THIS BINDING CAME, its glued unit
            #  word having swallowed this name (E-193): its finding says so.
            for finding in context.finding_list:
                if finding.side == side and finding.kind == "violated" \
                   and finding.reason is None:
                    finding.reason = space.glued_reason(finding.expression,
                                                        name)
            for failed in space.failing_tuple(name, value):
                context.finding_list.append(ConstraintFinding(
                    side, "violated", failed.text, name, value, line.line_n,
                    value_db={n: space.value_db[n] for n in failed.depend_set
                              if n in space.value_db},
                    reason=space.reason_db.pop(failed.text, None)))
                context.kill()
                held_f = False
                #  THE JUDGE STOPS AT THE FIRST (THE LAW); the association
                #  goes on to every law of every binding (C-22).
                if not context.free_f: return False
    return held_f


def check_no_bindings_nominal(line_list, scope_name):
    """RETURNS: None -- raises RegionSyntaxError if any NOMINAL line of an
    order-free scope contains a constraint binding. Constraint bindings are
    only allowed where line sequentiality is maintained (the ruling); in an
    order-free scope 'the value before' is undefined by construction.
    """
    from ..region.registry import RegionSyntaxError
    for line in line_list:
        for name, value in iter_bindings(line):
            raise RegionSyntaxError(line.line_n,
                "constraint binding '((%s: %s))' in an order-free scope "
                "(%s) -- constraints require line sequentiality"
                % (name, value, scope_name))


def spec_fault_of(expression):
    """
    RETURN: str, why 'expression' cannot stand as a constraint -- it
                 does not parse, or reaches outside the namespace;
            None, where it can.

    THE DOOR'S OWN JUDGEMENT, ASKED BEFORE A RUN (G-3): whoever reads a
    constraint out of a specification asks here, so that what the
    validator admits is what the run can compile.
    """
    try:
        ConstraintExpression("?", expression)
    except ConstraintSpecError as error:
        text = str(error)
        prefix = "constraint for '?': "
        return text[len(prefix):] if text.startswith(prefix) else text
    return None
