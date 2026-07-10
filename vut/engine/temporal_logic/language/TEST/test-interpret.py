"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the INTERPRETER -- direct execution of the decorated AST over
         SemanticModules. Each choice drives one Machine through a scripted
         scenario and prints the full event TRACE; the GOOD locks the
         language's OPERATIONAL behaviour byte-exactly, making this suite
         the semantics ORACLE every future emitter must match.

CHOICES: dispatch, lifecycle, blocks, membership.

           dispatch   The synchronous-instant law (P-1/P-1b): FIFO queue,
                      guards fixed at event arrival (a toggle alternates,
                      never double-fires), 'e.' payload reads, named-cause
                      matching with use-site arguments (P-6), emission
                      cascade in breadth order.
           lifecycle  Activation and deactivation (P-2): '=> behaviour'
                      enters (running ~ENTRY), '=x=>' exits (running ~EXIT);
                      a recurring 'every:' emission fires on virtual time
                      (P-3), cancels by handle, and auto-cancels at ~EXIT
                      (R-15).
           blocks     The command-block set: mutations with all operators,
                      if/elif/else, match over literal/range/glob/wildcard,
                      a filtered comprehension driving for:, count with
                      step, the D-17 enumeration arm (index alongside item,
                      start offset), indexed list writes, and dropto landing
                      on its forward exit-label.
           membership The D-14/D-15 surface at run time: string-literal
                      guards, 'in' over lists (elements), dicts (keys) and
                      strings (substrings), 'not in' as its negation, and
                      STRUCTURAL container equality.
______________________________________________________________________________
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

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "fixtures")


def banner(title):
    """RETURN: None, always. Prints the section banner for 'title'."""
    print("\n--- %s ---" % title)


def machine(basename):
    """RETURN: Machine, the fixture taken through the full front half
              (asserted fatal-free -- a broken fixture fails loudly) and
              loaded into a fresh executable world.
    """
    reporter = DiagnosticReporter()
    parsed = parse_module(
        SourceModule(path=os.path.join(FIXTURES, basename)), reporter)
    semantic = elaborate_module(declare_module(parsed, reporter), {},
                                reporter)
    assert not any(d.fatal for d in reporter.errors), \
        [d.message for d in reporter.errors]
    return Machine([semantic])


def run_dispatch():
    """RETURN: None, always. Locks the dispatch laws over run-toggle.vut:
              the toggle alternates across three presses (P-1b), payload
              guards select (P-4), the named cause matches with its
              use-site threshold (P-6), and the emitted alarm cascades in
              breadth order (P-1).
    """
    banner("dispatch (run-toggle.vut)")
    m = machine("run-toggle.vut")
    m.post("ac_button")
    m.post("ac_button")
    m.post("ac_button")
    m.post("dial_turned", delta=2.5)
    m.post("temp_high", value=95.0)
    m.post("temp_high", value=50.0)
    print(m.trace())


def run_lifecycle():
    """RETURN: None, always. Locks activation over run-lifecycle.vut:
              polling auto-activates at load (~ENTRY spawning the
              recurring poll; P-2 top-level),
              virtual time fires it at its multiples, the handle cancels
              it, a second start restarts it, and stop's ~EXIT
              auto-cancels (R-15).
    """
    banner("lifecycle (run-lifecycle.vut)")
    m = machine("run-lifecycle.vut")
    m.post("start")
    m.advance(1.2)
    m.post("mute")
    m.advance(1.0)
    m.post("start")
    m.advance(0.6)
    m.post("stop")
    m.advance(1.0)
    print(m.trace())


def run_blocks():
    """RETURN: None, always. Locks the command-block set over
              run-blocks.vut: one event drives mutations, branching,
              matching, both loops, the forward dropto, and a
              comprehension; the final member states are visible in the
              set-lines.
    """
    banner("blocks (run-blocks.vut)")
    m = machine("run-blocks.vut")
    m.post("go", n=3.0)
    m.post("classify", code=42.0)
    m.post("classify", code=7.0)
    m.post("classify", code=500.0)
    print(m.trace())


def run_membership():
    """RETURN: None, always. Locks D-14/D-15 over run-membership.vut: the
              string-equality guard holds, 'x in list' fires exactly on a
              held element and 'not in' exactly on a missing one, a
              substring 'in' over a string member holds, and two
              element-equal lists compare equal structurally.
    """
    banner("membership and strings (run-membership.vut)")
    m = machine("run-membership.vut")
    m.post("setup")
    m.post("q1", x=7.0)
    m.post("q1", x=9.0)
    m.post("q2", x=9.0)
    m.post("q2", x=7.0)
    m.post("q3")
    m.post("q4")
    m.post("q5")
    print(m.trace())


HwutRunner(
    argv       = sys.argv,
    title      = "Interpreter (the semantics oracle)",
    choice_map = {
        "dispatch":  run_dispatch,
        "lifecycle": run_lifecycle,
        "blocks":    run_blocks,
        "membership": run_membership,
    },
).run()
