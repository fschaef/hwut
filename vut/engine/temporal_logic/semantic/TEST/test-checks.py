"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

TEST: consistency checks -- the decided F-checks (pass 2, README E / J)

Parses real source, builds scopes, runs run_checks, prints the diagnostics.
Covers the two checks that are decided and need no open table:
kind-vs-shape [KIND] and is-base category [KIND]. The open-table checks
(calls, sweeps) are no-ops until their tables land (todo-1, todo-2) and are not
exercised here.

Choices:
    kind_shape   a struct without a signature, and a bare mode WITH one ->
                 two [KIND].
    is_base      a state machine deriving from a mode group -> [KIND]
                 category mismatch.
    clean        a well-formed state machine -> no diagnostics.
______________________________________________________________________________
"""
import sys
from config import HwutRunner

from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter
from vut.engine.temporal_logic.parser.rule_parser import parse
from vut.engine.temporal_logic.semantic.scope_tree import build_scopes
from vut.engine.temporal_logic.semantic.resolver import ResolutionState
from vut.engine.temporal_logic.semantic.checks import run_checks
from fake_luau_oracle import FakeLuauOracle


def _check(src):
    """RETURN: (DiagnosticReporter) holding the check diagnostics for 'src'.

    Parses (errors printed so a broken fixture is visible), builds scopes, runs
    the decided checks. Build and check diagnostics share one reporter so the
    printed list is the whole pass-2 verdict for the fixture.
    """
    prep = DiagnosticReporter()
    rf   = parse(src, FakeLuauOracle(), prep)
    if prep.errors:
        print("PARSE ERRORS (%d):" % len(prep.errors))
        for d in prep.errors:
            print("  %s @%d" % (d.message, d.source_offset))
    rep    = DiagnosticReporter()
    ground = build_scopes(rf, rep)
    state  = ResolutionState()
    run_checks(rf, ground, state, rep)
    return rep


def _report(rep):
    """RETURN: None. Prints the check diagnostics, tag and offset, in order."""
    print("DIAGNOSTICS (%d):" % len(rep.errors))
    for d in rep.errors:
        print("  tag=%s %s @%d" % (d.tag, d.message, d.source_offset))


_KIND_SHAPE_SRC = """\
Foo is: struct
"""

_IS_BASE_SRC = """\
mode_group: Grp(scale: int)
    has: Grp.x

    mode: A
        init: { x = 1 }
        until: tick
:end

state_machine: SM(rate: string) is: Grp
    default: SM.Idle

    state: Idle
        init: { y = 2 }
        until: tick
:end
"""

_CLEAN_SRC = """\
state_machine: SM(rate: string)
    default: SM.Idle

    state: Idle
        init: { y = 2 }
        until: tick
:end
"""


def run_kind_shape():
    """RETURN: None. Struct without a signature -> [KIND] mandatory-missing."""
    _report(_check(_KIND_SHAPE_SRC))


def run_is_base():
    """RETURN: None. State machine deriving a mode group -> [KIND] mismatch."""
    _report(_check(_IS_BASE_SRC))


def run_clean():
    """RETURN: None. Well-formed state machine -> no diagnostics."""
    rep = _check(_CLEAN_SRC)
    _report(rep)
    assert not rep.errors


HwutRunner(
    argv       = sys.argv,
    title      = "Semantic Layer -- Consistency Checks",
    choice_map = {
        "kind_shape": run_kind_shape,
        "is_base":    run_is_base,
        "clean":      run_clean,
    },
).run()
