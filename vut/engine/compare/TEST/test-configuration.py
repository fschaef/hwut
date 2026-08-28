#! /usr/bin/env python3
#
# @hwut {
#     title      = "Configuration: declarations, slots, constraint relation"
#     choices    = ["constraint_db", "declared", "edges", "namespace",
#                   "slots"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: The configuration's two promises, and the derivation of the
         constraint database from the expressions as written.

CHOICES: declared, slots, constraint_db, namespace, edges;

DESCRIPTION:

declared      every default stands in the declaration and is read
              without constructing anything. A caller learns what
              compare does when nothing is stated, and compare restates
              it nowhere.

slots         assignment works as it always did; a MISSPELT field is
              refused. Before, 'numeric_tolerence_ratio = 0.01' created
              an attribute nothing read, and the author believed a
              tolerance was in force when it was not.

constraint_db the relation runs BOTH WAYS: one expression reaches every
              variable it mentions, and one variable collects every
              expression that mentions it. Deriving it here, from the
              expression itself, is what makes it impossible to relate a
              variable to an expression that does not mention it.

namespace     A TEST RUN HAS ONE NAMESPACE for all its constraints:
              the fixed names -- maths, the builtins, 'glob', the
              constants -- and the variables the run has bound so far.
              The two are composed at evaluation time; the fixed part
              is copied, so one run's bindings never reach another's.
              The same set read the other way is what a variable may
              not be called.

edges         a name that is not a variable -- a sandbox callable, a
              literal, a keyword -- and an expression that does not
              parse. The malformed expression contributes nothing and
              raises nothing: it is refused where it is compiled.
______________________________________________________________________________
"""
import sys

from   config import HwutRunner                                # noqa: F401

from   dataclasses import fields

from   vut.engine.compare.configuration import (
                        Configuration, ConfigurationPatternFinder,
                        related_variable_to_constraint_expression_db)
from   vut.engine.compare.engine.constraint_namespace import (
                        FUNCTION_DB, CONSTANT_DB, STR_METHOD_SET,
                        NOT_A_VARIABLE_SET, fixed_namespace,
                        namespace_of, glob)


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def show_db(expression_list):
    """RETURN: None. Prints the derived relation, variable by variable."""
    db = related_variable_to_constraint_expression_db(expression_list)
    for name in sorted(db):
        print("    %-10s %s" % (name, list(db[name])))
    if not db: print("    (nothing)")


def test_declared():
    """RETURN: None. Defaults read out of the declaration."""
    banner("ConfigurationPatternFinder")
    for f in fields(ConfigurationPatternFinder):
        value = f.default if f.default is not None else None
        if value.__class__.__name__ == "_MISSING_TYPE":
            value = f.default_factory()
        print("    %-30s %r" % (f.name, value))

    banner("Configuration")
    for f in fields(Configuration):
        if f.name in ("pattern_finder", "cross_check_f"): continue
        value = f.default
        if value.__class__.__name__ == "_MISSING_TYPE":
            value = f.default_factory()
        print("    %-30s %r" % (f.name, value))


def test_slots():
    """RETURN: None. Assignment stands; a misspelling is refused."""
    config = Configuration()

    banner("assignment works as it always did")
    config.pattern_finder.numeric_tolerance_ratio = 0.01
    config.pattern_finder.analogy_f               = False
    print("    numeric_tolerance_ratio %r"
          % config.pattern_finder.numeric_tolerance_ratio)
    print("    analogy_f               %r"
          % config.pattern_finder.analogy_f)

    banner("a misspelt field is refused")
    for name in ("numeric_tolerence_ratio", "analogy_marker",
                 "equivalent_patterns"):
        try:
            setattr(config.pattern_finder, name, 1)
            print("    %-24s NOT REFUSED" % name)
        except AttributeError as error:
            print("    %-24s refused: %s" % (name, error))


def test_constraint_db():
    """RETURN: None. The relation, both ways."""
    banner("one expression, two variables")
    show_db(["x < y + 2"])

    banner("one variable, two expressions")
    show_db(["x < 10", "x > 0"])

    banner("both ways at once")
    show_db(["x < y + 2", "abs(z) < epsilon", "y > z"])

    banner("through the configuration: the flag follows the database")
    config = Configuration()
    print("    before: constraint_f %r  db %r"
          % (config.pattern_finder.constraint_f, config.constraint_db))
    config.constraint_expression_list = ["t > 0 and t < 100"]
    config.derive_constraint_db()
    print("    after:  constraint_f %r  db %r"
          % (config.pattern_finder.constraint_f, config.constraint_db))

    config.constraint_expression_list = []
    config.derive_constraint_db()
    print("    empty:  constraint_f %r  db %r"
          % (config.pattern_finder.constraint_f, config.constraint_db))


def test_namespace():
    """RETURN: None. What a constraint may call, and what it may not."""
    banner("the run's namespace: fixed names, and what the run bound")
    space = {}
    for name, value in (("z", 0.0), ("area", 81), ("name", "build-42.log")):
        space[name] = value
        print("    bound %-6s -> namespace carries %d names, %d of them "
              "the run's" % (name, len(namespace_of(space)), len(space)))
    print("    a fresh run starts at %d" % len(fixed_namespace()))

    banner("a constraint evaluates against the namespace")
    for expression, binding in (
            ("abs(sin(z)) < 1e-9",              {"z": 0.0}),
            ("sqrt(area) < 10",                 {"area": 81}),
            ("log10(n) > 2",                    {"n": 1000}),
            ("degrees(angle) == 180.0",         {"angle": 3.141592653589793}),
            ("value < pi",                      {"value": 3.0}),
            ('glob(name, "build-*.log")',       {"name": "build-42.log"}),
            ('glob(name, "build-*.log")',       {"name": "run.log"}),
            ("isclose(ratio, 0.5, abs_tol=1e-9)", {"ratio": 0.5}),
    ):
        verdict = eval(expression, {"__builtins__": {}},
                       namespace_of(binding))
        print("    %-38s %-28s %s"
              % (expression, binding, verdict))

    banner("the namespace reaches nothing else")
    for name in ("open", "__import__", "eval", "exec", "os", "sys"):
        print("    %-12s carried: %s" % (name, name in fixed_namespace()))
    print("    functions %d   constants %d   string methods %d"
          % (len(FUNCTION_DB), len(CONSTANT_DB), len(STR_METHOD_SET)))

    banner("glob is the shell's own form, and case sensitive")
    for value, pattern in (("build-42.log", "build-*.log"),
                           ("build-42.log", "build-?2.log"),
                           ("Build-42.log", "build-*.log"),
                           ("x.log",        "[abx].log"),
                           (4711,           "47*")):
        print("    %-14r %-16r %s" % (value, pattern, glob(value, pattern)))

    banner("what a variable may not be called")
    print("    %d names" % len(NOT_A_VARIABLE_SET))
    for name in ("sin", "min", "glob", "pi", "abs", "x", "epsilon"):
        print("    %-10s %s" % (name, name in NOT_A_VARIABLE_SET))


def test_edges():
    """RETURN: None. What is not a variable, and what does not parse."""
    banner("a name the namespace provides is not a variable")
    show_db(["abs(x) < 1", "len(name) > 3", "max(a, b) < c",
             "abs(sin(z) - x) < epsilon", 'glob(name, "b-*")'])

    banner("a literal is not a variable")
    show_db(["x is not None", "flag == True"])

    banner("an expression that does not parse contributes nothing")
    show_db(["x <", "((("])

    banner("... and does not stop the ones that do")
    show_db(["x <", "y > 0"])


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "Configuration: declarations, slots, constraint relation;", {
        "declared":      test_declared,
        "slots":         test_slots,
        "constraint_db": test_constraint_db,
        "namespace":     test_namespace,
        "edges":         test_edges,
    }).run()
