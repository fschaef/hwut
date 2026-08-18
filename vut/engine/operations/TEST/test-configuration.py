#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE CONFIGURATION OF ONE TEST APPLICATION.

    UNIT     'TestConfiguration' + 'TestChoiceConfiguration': what a test
             IS, aggregating its sub-components' own structs verbatim.

    CAUSAL CONTRACT
             the derived places follow from the source file's stem and the
             test directory; 'has_choices' follows from the single 'None'
             key; a configuration that cannot serve any goal is REFUSED
             where it is handed in, naming the one first fault.

    CONSISTENCY CONTRACT
             the object is frozen -- read-only after it is handed in, so
             no run can mutate the design it runs under.

    Each choice prints a complete picture, so wrongness is visible rather
    than merely asserted.
______________________________________________________________________________
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from   config import HwutRunner                                  # noqa F401,E402
from   dataclasses import FrozenInstanceError                    # noqa E402

from   vut.engine.procsitter.procsitter import ProcsitterConfig  # noqa E402
from   vut.engine.operations.configuration import (                # noqa E402
                                        TestConfiguration,
                                        TestChoiceConfiguration,
                                        ConfigurationError,
                                        E_SourceKind,
                                        verify)


def _check(pair_list):
    """
    RETURN: True,  every claim held.
            False, at least one did not.

    Prints one line per claim, so a failure names itself.
    """
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def _verdict(ok, sentence):
    """RETURN: None. Prints the one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


def _compiled(**kwargs):
    """RETURN: TestConfiguration, a COMPILED test with one named choice."""
    argument_db = dict(source_file    = "parse.c",
                       source_kind    = E_SourceKind.COMPILED,
                       test_directory = "/tests/parser",
                       caps           = ProcsitterConfig(),
                       build          = object(),
                       choice_db      = {"basic": TestChoiceConfiguration()})
    argument_db.update(kwargs)
    return TestConfiguration(**argument_db)


def test_places():
    """The derived places. One source file and one directory fix all three,
    and the build directory is keyed by the STEM -- which is what lets two
    tests of one source tree build concurrently without a lock."""
    c = _compiled()
    print("INSPECT: source_file = %s" % c.source_file)
    print("         stem        = %s" % c.stem)
    print("         runs in     = %s" % c.test_directory)
    print("         builds in   = %s" % c.build_directory)
    print("         outputs to  = %s" % c.output_directory)
    ok = _check([
        (c.stem == "parse",
         "the stem drops the extension"),
        (str(c.build_directory) == "/tests/parser/BUILD/parse",
         "the build directory is BUILD/<stem> under the test directory"),
        (str(c.output_directory) == "/tests/parser/OUT",
         "outputs go to OUT/ beside BUILD/"),
        (c.build_directory != c.output_directory,
         "a build writes nowhere near the application's output"),
    ])
    _verdict(ok, "three roles, three directories, all derived.")


def test_choices():
    """'None' is the key of a test that mentions no choices: it is called
    once, with no choice argument. It never stands beside named choices."""
    named = _compiled(choice_db={"basic": TestChoiceConfiguration(),
                                 "deep":  TestChoiceConfiguration()})
    plain = _compiled(choice_db={None: TestChoiceConfiguration()})
    verify(named); verify(plain)

    print("INSPECT: named keys = %s -> has_choices = %s"
          % (sorted(named.choice_db), named.has_choices))
    print("         plain keys = [None] -> has_choices = %s" % plain.has_choices)
    ok = _check([
        (named.has_choices is True,
         "a test with named choices HAS choices"),
        (plain.has_choices is False,
         "a test keyed by None alone has NONE"),
        (isinstance(plain.choice_configuration(None), TestChoiceConfiguration),
         "the None entry is reachable like any other"),
    ])
    _verdict(ok, "the single None key answers 'has this test choices'.")


def test_aggregation():
    """The configuration HOLDS its sub-components' structs; it does not
    restate their fields. A cap is read from the ProcsitterConfig itself."""
    caps = ProcsitterConfig(max_wall_clock_sec=12.5, max_output_gap_sec=3.0)
    c    = _compiled(caps=caps)
    print("INSPECT: caps is a %s" % type(c.caps).__name__)
    print("         max_wall_clock_sec = %s" % c.caps.max_wall_clock_sec)
    print("         max_output_gap_sec = %s" % c.caps.max_output_gap_sec)
    ok = _check([
        (c.caps is caps,
         "the ProcsitterConfig is held, not copied"),
        (not any(name.startswith("max_") for name in vars(c)),
         "no cap is restated as a field of the configuration"),
        (c.caps.max_output_gap_sec == 3.0,
         "the silence cap arrives through procsitter's own struct"),
    ])
    _verdict(ok, "sub-component structs held verbatim, never restated.")


def test_frozen():
    """The configuration is the test's DESIGN: written once, read-only
    thereafter, so no run can mutate what it runs under."""
    c      = _compiled()
    caught = []
    for name, value in (("source_file", "other.c"), ("test_directory", "/x")):
        try:
            setattr(c, name, value)
            caught.append((name, None))
        except FrozenInstanceError:
            caught.append((name, "refused"))
    for name, outcome in caught:
        print("INSPECT: assignment to '%s' -> %s" % (name, outcome))
    ok = _check([
        (all(outcome == "refused" for _, outcome in caught),
         "every assignment is refused"),
        (c.source_file == "parse.c",
         "the value is unchanged after the attempt"),
    ])
    _verdict(ok, "one writer, many readers -- enforced by the object.")


def test_refusal():
    """A configuration that cannot serve any goal is refused where it is
    handed in, naming the ONE first fault -- not at step seven."""
    case_list = [
        ("empty choice_db",
         dict(choice_db={})),
        ("None mixed with named choices",
         dict(choice_db={None: TestChoiceConfiguration(),
                         "basic": TestChoiceConfiguration()})),
        ("COMPILED without a build",
         dict(build=None)),
        ("interpreter given, but COMPILED",
         dict(interpreter=["python3"])),
        ("a choice entry of the wrong type",
         dict(choice_db={"basic": {"canonicalisers": {}}})),
        ("a build given where none is read",
         dict(source_kind=E_SourceKind.EXECUTABLE)),
    ]
    outcome_list = []
    for title, override in case_list:
        try:
            verify(_compiled(**override))
            outcome_list.append((title, None))
        except ConfigurationError as error:
            outcome_list.append((title, str(error).split(".")[0]))

    for title, reason in outcome_list:
        print("INSPECT: %-32s -> %s" % (title, reason or "NOT REFUSED"))
    ok = _check([
        (all(reason is not None for _, reason in outcome_list),
         "every unservable configuration is refused"),
        (verify(_compiled()) is None,
         "a servable one passes silently"),
    ])
    _verdict(ok, "unservable configurations refused where they are written.")


def test_interpreted():
    """INTERPRETED needs its argv prefix and no build; the other kinds need
    the opposite. The rule is symmetric, so neither can be forgotten."""
    good = TestConfiguration(source_file="run.lua",
                             source_kind=E_SourceKind.INTERPRETED,
                             test_directory="/tests/lua",
                             caps=ProcsitterConfig(),
                             interpreter=["lua"],
                             choice_db={None: TestChoiceConfiguration()})
    verify(good)
    print("INSPECT: %s + interpreter %s -> accepted"
          % (good.source_kind, list(good.interpreter)))
    missing = refused = None
    try:
        verify(TestConfiguration(source_file="run.lua",
                                 source_kind=E_SourceKind.INTERPRETED,
                                 test_directory="/tests/lua",
                                 caps=ProcsitterConfig(),
                                 choice_db={None: TestChoiceConfiguration()}))
    except ConfigurationError as error:
        missing = str(error)
    try:
        verify(_compiled(source_kind=E_SourceKind.EXECUTABLE, build=None,
                         interpreter=["python3"]))
    except ConfigurationError as error:
        refused = str(error)
    print("INSPECT: INTERPRETED without interpreter -> %s"
          % (missing.split(".")[0] if missing else "NOT REFUSED"))
    print("         EXECUTABLE with interpreter     -> %s"
          % (refused.split("--")[0].strip() if refused else "NOT REFUSED"))
    ok = _check([
        (good.build is None,
         "an interpreted test carries no build configuration"),
        (missing is not None,
         "INTERPRETED without an interpreter is refused"),
        (refused is not None,
         "an interpreter where none is read is refused, not ignored"),
    ])
    _verdict(ok, "the argv prefix is required exactly where it is read.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The configuration of one test application",
        choice_map = {
            "places":      test_places,
            "choices":     test_choices,
            "aggregation": test_aggregation,
            "frozen":      test_frozen,
            "refusal":     test_refusal,
            "interpreted": test_interpreted,
        },
        happy      = "SUCCESS.*",
    ).run()
