==============================================================================
THE CONSTRAINT NAMESPACE
==============================================================================

A constraint is an expression over variables that a test run BINDS as it
reads. This file states what such an expression may contain: the names it
may use, where those names come from, and what refuses it.


1  A NAMESPACE PER TEST RUN
______________________________________________________________________________

    namespace of a run  =  the fixed names          (this module)
                        +  the run's bound variables (ConstraintSpace)

The FIXED part is the same for every run: functions, constants, string
methods. It stands in 'engine/constraint_namespace.py'.

The VARIABLE part is the run's CONSTRAINT SPACE. A binding element in the
sequential outer text

    (( <variable-name> : <number>|<quoted-string> ))

enters a name into the space, and the moment it does, every constraint over
that name is checked ('engine/constraints.py').

The two are composed at evaluation time by 'namespace_of(binding_db)'.
Neither is a copy of the other, and one run's bindings never reach another:
the fixed part is copied, the space belongs to the run.


2  WHAT A CONSTRAINT MAY CONTAIN
______________________________________________________________________________

    arithmetic          + - * / // % **
    comparison          < <= > >= == !=
    boolean             and or not
    calls               the functions below, by bare name
    constants           pi  e  tau  inf  nan  True  False  None
    string methods      on a bound value: startswith, endswith, lower,
                        upper, strip, lstrip, rstrip, count, find,
                        replace, split, isdigit, isalpha, isalnum,
                        isspace

FUNCTIONS

    maths       sin cos tan asin acos atan atan2 sinh cosh tanh
                exp log log2 log10 sqrt pow
                floor ceil trunc fabs fmod copysign
                degrees radians hypot gcd factorial
                isfinite isinf isnan isclose

    general     len abs min max sum int float str bool
                round ord chr all any sorted

    text        glob(value, pattern)

'glob' matches the way a shell does -- '*' any run, '?' one character,
'[abc]' a set -- and is CASE SENSITIVE. It touches no file system. A value
that is no string is made one first.

    (( name: "build-42.log" ))      glob(name, "build-*.log")
    (( count: 4711 ))               glob(count, "47*")


3  WHAT REFUSES AN EXPRESSION
______________________________________________________________________________

An expression is inspected as an AST against a whitelist before it is ever
run, and it is run with an empty '__builtins__' beside the namespace.
Nothing outside section 2 is reachable: no import, no attribute reaching
into an object's own machinery, no name the namespace does not carry.

A constraint that does not parse, calls a name that is not a function, or
names something the namespace does not carry is a BROKEN SPECIFICATION and
is loud ('ConstraintSpecError'). It is not a verdict about the subject.


4  A VARIABLE MAY NOT BE CALLED LIKE A NAME OF THE NAMESPACE
______________________________________________________________________________

Every name of section 2 is a name a variable may not carry: a constraint
over a variable called 'min', 'sin' or 'glob' cannot be written.

This is not only a rule about writing. The same set is read by the VARIABLE
FINDER, which relates a variable to the constraints that mention it:

    "abs(sin(z) - x) < epsilon"     constrains  x, z, epsilon
                                    and nothing called 'abs' or 'sin'

    "glob(name, 'b-*')"             constrains  name

One set -- 'NOT_A_VARIABLE_SET' -- read by the AST check, by the evaluation
and by the finder, so the three cannot drift apart.


5  WHERE THE CONSTRAINTS COME FROM
______________________________________________________________________________

A test specification states them as a list of expressions, written as they
stand:

    constraints = ["x < y + 2", "abs(sin(z) - x) < epsilon"]

Compare relates each expression to the variables it mentions
('related_variable_to_constraint_expression_db' in 'configuration.py'). The
relation runs BOTH WAYS: one expression may constrain several variables, and
one variable may carry several expressions. Every variable an expression
mentions receives it, so a binding of any one of them brings the whole
expression up for checking.

Deriving that relation inside compare is what makes it impossible to relate
a variable to an expression that does not mention it.
