#! /usr/bin/env python3
#
# @hwut {
#     title      = "Defaults: declared by the owner, related by us"
#     choices    = ["declared", "instantiate", "merge", "refused",
#                   "table"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: DEFAULT PROVISION IS CONTRACT. A configuration is a frozen
         dataclass; its default stands in its declaration. The relation
         table names, per parameter, the class and the member that carry
         it, and serves both directions -- write the stated values, read
         the declared defaults.

CHOICES: table, declared, refused, instantiate, merge;

DESCRIPTION:

table       the relation table covers the parameter vocabulary
            EXACTLY. A parameter added without a relation, or a
            relation left behind by a struck parameter, shows here.
            The scopes of the grammar ('caps', 'build') relate leaf by
            leaf, so their leaves are what is compared.

declared    the import-time check standing, and every default printed.
            An ADAPTED entry names several members of the component's
            own configuration, and its default is DERIVED from their
            declarations through the adapter's 'backward' -- compare's
            three analogy fields become the marker pair our vocabulary
            speaks in, and no default is restated here -- a default that changes is a contract change and
            must be seen. A member renamed or a default forgotten in a
            component fails at the IMPORT of 'relation.py', naming
            parameter, class and member; the choice shows that it does.

            A declared 'None' is the value and documents that the thing
            is absent: no build framework, no canonicalisation. Nothing
            substitutes for it.

refused     a name outside the vocabulary is refused -- KeyError, not
            a guess.

instantiate what a case yields: one COMPLETE configuration per owning
            class, stated values written, everything else at the
            declared default. No member comes out 'None' unless its
            owner declared 'None'.

merge       the record keeps its 'None's -- the store records what was
            CHOSEN -- while the configuration has none. A value stated
            OFF ('()') is a statement and no default replaces it.
______________________________________________________________________________
"""
import sys
from config import HwutRunner                                # noqa: F401

from vut.engine.orchestrator.exploration.configuration_tree import (TestParameters, Caps, Tolerance,
                                                     KEY_TO_FIELD)
from vut.engine.orchestrator.exploration.relation         import (RELATION, default_of,
                                                     effective, value_db_of,
                                                     _member_list)
from vut.engine.orchestrator.exploration.instantiate      import configurations_of


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def leaf_name_list():
    """
    RETURN: list[str], the vocabulary as the relation table names it:
            a scalar parameter by its name, a scope leaf by leaf.
    """
    result = []
    for name in KEY_TO_FIELD:
        related = [n for n in RELATION
                   if n == name or n.startswith("%s." % name)]
        result.extend(related if related else [name])
    return sorted(set(result))


def test_table():
    """RETURN: None. Vocabulary and relation cover each other."""
    banner("vocabulary without a relation")
    orphan_list = sorted(set(leaf_name_list()) - set(RELATION))
    print(orphan_list if orphan_list else "none")

    banner("relation without a parameter")
    root_set   = set(KEY_TO_FIELD)
    stale_list = sorted(n for n in RELATION
                        if n.split(".", 1)[0] not in root_set)
    print(stale_list if stale_list else "none")


def test_declared():
    """RETURN: None. Every related member exists and declares."""
    banner("the table imported: every member exists and declares")
    print("import check passed")

    banner("parameter, owning class, member(s), derived default")
    for name in sorted(RELATION):
        entry  = RELATION[name]
        member = ", ".join(_member_list(entry))
        mark   = "  <adapted>" if len(entry) == 3 else ""
        print("%-18s %-19s %-46s %s%s"
              % (name, entry[0].__name__, member,
                 repr(default_of(name)), mark))

    banner("a member renamed behind our back")
    from dataclasses import dataclass
    from vut.engine.orchestrator.exploration.relation import _assert_relation

    @dataclass(frozen=True, slots=True)
    class Renamed:
        tolerance_ratio: float = 0.0

    @dataclass(frozen=True, slots=True)
    class Silent:
        numeric_tolerance_ratio: float

    #  THE TABLE IS MODULE STATE and this process may run the next
    #  choice too (the interactive runner keeps the interpreter): put
    #  the entry back, or 'instantiate' meets a class of this test's.
    standing = RELATION["tolerance.numeric_ratio"]
    try:
        for cls in (Renamed, Silent):
            RELATION["tolerance.numeric_ratio"] = (cls, "numeric_tolerance_ratio")
            try:
                _assert_relation()
                print("%s: NOT CAUGHT" % cls.__name__)
            except ImportError as error:
                print("%s -> %s" % (cls.__name__,
                                    str(error).splitlines()[-1].strip()))
    finally:
        RELATION["tolerance.numeric_ratio"] = standing


def test_refused():
    """RETURN: None. An unknown name is refused, never defaulted."""
    banner("a name the vocabulary does not carry")
    for name in ("timeout", "app", "constraint", "caps", "invented"):
        try:
            print("%-12s answered %r -- NOT REFUSED"
                  % (name, default_of(name)))
        except KeyError:
            print("%-12s refused" % name)


def test_instantiate():
    """RETURN: None. Complete configurations out of one record."""
    banner("a case stating two things, and what it yields")
    parameters = TestParameters(tolerance=Tolerance(numeric_ratio=0.05), caps=Caps(network=False))
    print("record: tolerance %r  caps %r"
          % (parameters.tolerance, parameters.caps))
    print()
    for cls, instance in configurations_of(parameters):
        print("%s:" % cls.__name__)
        for member in instance.__dataclass_fields__:
            print("    %-30s %r" % (member, getattr(instance, member)))


def test_merge():
    """RETURN: None. Stated wins, unstated defaults, OFF is a
    statement."""
    banner("stated, unstated, and stated OFF")
    parameters = TestParameters(tolerance=Tolerance(numeric_ratio=0.25, analogy=()),
                                caps=Caps(timeout_sec=5))
    value_db   = value_db_of(parameters)
    for name in ("tolerance.numeric_ratio", "tolerance.analogy",
                 "tolerance.comment",
                 "caps.timeout_sec", "caps.network"):
        print("%-18s record %-14r effective %r"
              % (name, value_db[name], effective(parameters, name)))


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "Defaults: declared by the owner, related by us;", {
        "table":       test_table,
        "declared":    test_declared,
        "refused":     test_refused,
        "instantiate": test_instantiate,
        "merge":       test_merge,
    }).run()
