#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE TRANSLATION -- every parameter an author STATES reaches
         the component that OWNS it, or is refused by name.

Exploration resolves what an author wrote into 'TestParameters'.
Nothing judges a test by that: the RUN needs operations'
TestConfiguration, compare needs its own Configuration, procsitter its
caps, the bookkeeper its naming law. 'adapter.py' is the one crossing,
and a parameter it drops is worse than one it refuses: the test then
runs under a setup nobody chose, and its verdict means something other
than what its author asked for.

CHOICES: sweep, compare, caps, naming, refused;

DESCRIPTION:

sweep    EVERY member of 'TestParameters', stated, and where it
         arrives. A member that reaches nothing is named -- the sweep
         reads the DECLARATION, so a parameter exploration gains later
         is swept the day it exists.

compare  the TOLERANCES, member by member, into compare's own
         Configuration: the ratio, the pattern lists, the marker
         PAIRS, and the stated OFF (the empty tuple).

caps     the CAPS into procsitter's configuration; an unstated cap
         keeps procsitter's own default, never a zero.

naming   'same' into the bookkeeper's naming law: one nominal for
         every choice, candidates still per choice.

refused  a language no interpreter is declared for, and a marker pair
         that is not a pair -- refused BY NAME at the door, never
         guessed into a default.
______________________________________________________________________________
"""
import dataclasses
import sys
from config import HwutRunner                                # noqa: F401

from vut.engine.orchestrator.exploration.specification import (
                                                  Build, Caps,
                                                  CTestApp, E_Origin,
                                                  Position,
                                                  TestParameters)
from vut.engine.orchestrator.run.adapter import (naming_of,
                                                 test_configuration_of,
                                                 _compare_of)
from vut.engine.operations.configuration import E_SourceKind


def _check(result_list):
    """RETURN: bool, all (bool, label) pairs hold; prints OK/FAIL."""
    ok = True
    for holds, label in result_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", label))
        ok = ok and bool(holds)
    return ok


def _verdict(ok, sentence):
    """RETURN: None. The suite's closing line."""
    print("%s: %s%s" % ("SUCCESS" if ok else "FAIL", sentence,
                        "" if ok else " (see above)"))


def _app(parameters=None, language="bash", choice_db=None):
    """RETURN: CTestApp over the given parameters, one root choice."""
    if choice_db is None:
        choice_db = {None: parameters if parameters is not None
                           else TestParameters()}
    return CTestApp(source_file = "test-demo.sh",
                    title       = "Demo",
                    language    = language,
                    choice_db   = choice_db,
                    origin      = E_Origin.HEADER,
                    position    = Position(1, 1))


def _configuration(parameters, language="bash"):
    """RETURN: TestConfiguration of an application stating that."""
    return test_configuration_of(_app(parameters, language), "/tmp")


def _stated_value(member):
    """
    RETURN: a value a member of 'TestParameters' can be STATED as --
            chosen to be visibly not a default.

    Raises AssertionError for a member the sweep has not met: a new
    parameter must be PLACED here, never silently skipped.
    """
    match member.name:
        case "build":       return Build(framework="make",
                                         executable="app")
        case "caps":        return Caps(timeout_sec=11)
        case "pype":        return "python3 filter.py"
        case "numeric":     return 0.25
        case "eq_pattern":  return ("alpha|beta",)
        case "nothing":     return ("~",)
        case "analogy":     return ("<<", ">>")
        case "constraints": return ("x < y",)
        case "comment":     return ("/*", "*/")
        case "slash_eqv":   return False
        case "whitespace_eqv": return False
        case "same":        return True
        case "interactive": return True
        case "execute":     return "./run-me --now"
        case _:
            assert False, ("the sweep does not know how to state '%s'"
                           % member.name)


def _arrivals(parameters):
    """
    RETURN: list[str], the names of the places a stated parameter
            REACHED -- 'compare', 'caps', 'naming', or the
            TestConfiguration member it became.

    The comparison is against an application stating NOTHING: what
    differs, arrived.
    """
    plain    = _configuration(TestParameters())
    carried  = _configuration(parameters)
    arrival  = []

    for member in dataclasses.fields(type(plain)):
        name = member.name
        if name == "choice_db": continue
        if getattr(plain, name) != getattr(carried, name):
            arrival.append(name)

    plain_choice   = plain.choice_db[None]
    carried_choice = carried.choice_db[None]
    if plain_choice.canonicalisers != carried_choice.canonicalisers:
        arrival.append("canonicalisers")
    if carried_choice.compare is not None:
        arrival.append("compare")
    if naming_of(_app(parameters)) != naming_of(_app(TestParameters())):
        arrival.append("naming")
    return arrival


def test_sweep():
    """RETURN: None. Every declared parameter, stated, and where it
    arrives."""
    print("INSPECT: every member of 'TestParameters', stated alone")
    print("         %-16s %s" % ("stated", "arrives at"))
    unreached = []
    for member in dataclasses.fields(TestParameters):
        parameters = TestParameters(
                        **{member.name: _stated_value(member)})
        arrival    = _arrivals(parameters)
        if not arrival: unreached.append(member.name)
        print("         %-16s %s"
              % (member.name,
                 ", ".join(arrival) if arrival else "NOTHING -- DROPPED"))
    ok = _check([
        (not unreached,
         "every stated parameter reaches a component -- none is "
         "silently dropped"),
    ])
    _verdict(ok, "what an author states, a component receives.")


def test_compare():
    """RETURN: None. The tolerances into compare's Configuration."""
    print("INSPECT: nothing stated -> %s"
          % _compare_of(TestParameters()))

    options = _compare_of(TestParameters(numeric        = 0.01,
                                         eq_pattern     = ("a|b",),
                                         nothing        = ("~",),
                                         analogy        = ("<<", ">>"),
                                         comment        = ("/*", "*/"),
                                         constraints    = ("x < y",),
                                         slash_eqv      = False,
                                         whitespace_eqv = False))
    finder = options.pattern_finder
    print("         numeric        -> %s" % finder.numeric_tolerance_ratio)
    print("         eq_pattern     -> %s" % finder.equivalent_pattern_list)
    print("         nothing        -> %s"
          % finder.visible_nothing_pattern_list)
    print("         analogy pair   -> %s %s (on: %s)"
          % (finder.analogy_begin_marker, finder.analogy_end_marker,
             finder.analogy_f))
    print("         comment pair   -> %s %s (on: %s)"
          % (finder.ignored_line_begin_marker,
             finder.ignored_line_end_marker, finder.ignored_line_f))
    print("         constraints    -> %s" % options.constraint_expression_list)
    print("         slash_eqv      -> backslash_f %s" % finder.backslash_f)
    print("         whitespace_eqv -> whitespace_f %s" % finder.whitespace_f)

    off = _compare_of(TestParameters(analogy=(), comment=()))
    print("         stated OFF: analogy_f %s, ignored_line_f %s"
          % (off.pattern_finder.analogy_f,
             off.pattern_finder.ignored_line_f))
    ok = _check([
        (_compare_of(TestParameters()) is None,
         "an unstated tolerance is compare's OWN default -- no "
         "configuration is invented"),
        (finder.numeric_tolerance_ratio == 0.01
         and finder.equivalent_pattern_list == ["a|b"]
         and finder.visible_nothing_pattern_list == ["~"],
         "the ratio and the pattern lists arrive"),
        (finder.analogy_begin_marker == "<<"
         and finder.analogy_end_marker == ">>",
         "a marker PAIR arrives as begin and end"),
        (finder.backslash_f is False and finder.whitespace_f is False,
         "the equivalence flags arrive under compare's own names"),
        (options.constraint_expression_list == ["x < y"],
         "the constraint expressions arrive"),
        (off.pattern_finder.analogy_f is False
         and off.pattern_finder.ignored_line_f is False,
         "the empty tuple is the stated OFF, and switches the "
         "handling off"),
    ])
    _verdict(ok, "every stated tolerance reaches compare, by its own "
                 "name.")


def test_caps():
    """RETURN: None. The caps into procsitter's configuration."""
    default = _configuration(TestParameters()).caps
    carried = _configuration(TestParameters(
                    caps=Caps(timeout_sec=11, memory_mb=64))).caps
    print("INSPECT: unstated -> wall clock %s, memory %s"
          % (default.max_wall_clock_sec, default.max_memory_mb))
    print("         stated   -> wall clock %s, memory %s"
          % (carried.max_wall_clock_sec, carried.max_memory_mb))
    print("         a cap NOT stated keeps procsitter's own: cpu %s"
          % carried.max_cpu_time_sec)
    ok = _check([
        (carried.max_wall_clock_sec == 11
         and carried.max_memory_mb == 64,
         "a stated cap arrives under procsitter's name"),
        (carried.max_cpu_time_sec == default.max_cpu_time_sec,
         "an unstated cap keeps procsitter's default -- never a zero"),
    ])
    _verdict(ok, "caps arrive; silence keeps the owner's default.")


def test_naming():
    """RETURN: None. 'same' into the bookkeeper's naming law."""
    plain = naming_of(_app(TestParameters()))
    same  = naming_of(_app(TestParameters(same=True)))
    print("INSPECT: unstated -> same_nominal_f %s" % plain.same_nominal_f)
    print("         same=yes -> same_nominal_f %s" % same.same_nominal_f)
    ok = _check([
        (plain.same_nominal_f is False,
         "unstated: a nominal per choice"),
        (same.same_nominal_f is True,
         "'same' reaches the bookkeeper's naming law"),
    ])
    _verdict(ok, "'same' is a NAMING law, and arrives as one.")


def test_refused():
    """RETURN: None. Refusal by name, at the door."""
    refusal = []
    try:
        _configuration(TestParameters(), language="klingon")
        refusal.append("(none)")
    except AssertionError as error:
        refusal.append(str(error))
    try:
        _compare_of(TestParameters(analogy=("<<",)))
        refusal.append("(none)")
    except AssertionError as error:
        refusal.append(str(error))

    print("INSPECT: an unknown language -> %s" % refusal[0])
    print("         a marker pair of one -> %s" % refusal[1])
    ok = _check([
        ("klingon" in refusal[0],
         "the unknown language is named in its refusal"),
        ("analogy" in refusal[1],
         "the malformed pair is named in its refusal"),
    ])
    _verdict(ok, "what cannot be translated is refused, by name.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The translation: stated parameters reach their owners",
        choice_map = {
            "sweep":   test_sweep,
            "compare": test_compare,
            "caps":    test_caps,
            "naming":  test_naming,
            "refused": test_refused,
        }).run()
