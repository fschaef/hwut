"""Explanation Suite (the fourth documentation bin, R-35)

Verifies every file of language/EXPLANATION/: an explanation that stops
compiling fails here -- teaching text may not drift from the language.
Each choice takes one file through the full front half (parse -> declare ->
elaborate; asserted fatal-free), then, where the file carries a Demo
behaviour, drives its SHOW event through the interpreter and prints the
trace -- the explanation's claims, executed.

CHOICES: construct, destruct, lifecycle, take_give_know,
ephemerals, destruction_cannot_fail.
"""
import os
import sys

import config                                                   # noqa: F401

from vut.engine.temporal_logic.language.rule_parser import parse_module
from vut.engine.temporal_logic.language.declare import declare_module
from vut.engine.temporal_logic.language.elaborate import elaborate_module
from vut.engine.temporal_logic.language.interpret import Machine
from vut.engine.temporal_logic.language.module_states import SourceModule
from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter
from vut.language_support.python.hwut_runner import HwutRunner

EXPLANATION = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "EXPLANATION")


def check(basename):
    """RETURN: None, always. Takes one explanation file through the full
              front half (asserted fatal-free -- a drifted explanation
              fails loudly) and runs its PLANT (pipe ruling: a script
              feeder wired to the Demo reactor replays SHOW); the trace
              prints, locking the explanation's claims.
    """
    print("\n--- %s ---" % basename)
    reporter = DiagnosticReporter()
    parsed = parse_module(
        SourceModule(path=os.path.join(EXPLANATION, basename)), reporter)
    semantic = elaborate_module(declare_module(parsed, reporter), {},
                                reporter)
    assert not any(d.fatal for d in reporter.errors), \
        [d.message for d in reporter.errors]
    print("front half: clean")
    machine = Machine([semantic])
    machine.run("plant")
    machine.play()
    for line in machine.lines:
        print(line)


HwutRunner(
    argv       = sys.argv,
    title      = "Explanations (checked teaching, R-35)",
    choice_map = {
        "construct": lambda: check("explain-construct.vut"),
        "destruct":  lambda: check("explain-destruct.vut"),
        "lifecycle": lambda: check("explain-lifecycle.vut"),
        "take_give_know": lambda: check("explain-take-give-know.vut"),
        "ephemerals": lambda: check("explain-ephemerals.vut"),
        "destruction_cannot_fail":
            lambda: check("explain-destruction-cannot-fail.vut"),
    },
).run()
