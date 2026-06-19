"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

TEST: scope tree (pass 2, README B / J)

Parses real rule-file source with the parser and the neutral test oracle, then
builds the scope tree and prints a census. The printed census IS the assertion
(byte-exact against the GOOD recording); 'assert' is a hard-stop safety net
only. No AST is fabricated -- every tree printed here came through the real
parser.

Choices:
    census      a nested file (events, clock, namespace, state machine) ->
                the full scope tree, sealed flags, symbols, params.
    duplicate   two events of one spelling in one scope -> one [NAME].
    collision   a signature parameter spelling a state of its aggregate ->
                one [NAME] (D-4 spelling check).
______________________________________________________________________________
"""
import sys
from config import HwutRunner

from vut.engine.temporal_logic.core.diagnostic    import DiagnosticReporter
from vut.engine.temporal_logic.parser.rule_parser import parse
from vut.engine.temporal_logic.semantic.scope_tree import build_scopes
from fake_luau_oracle import FakeLuauOracle


def _parse(src):
    """RETURN: (Module, DiagnosticReporter) for 'src' via the real parser.

    A non-empty parser-error list is printed so a fixture that stops parsing
    is visible in the census rather than silently yielding a partial tree.
    """
    rep = DiagnosticReporter()
    rf  = parse(src, FakeLuauOracle(), rep)
    if rep.errors:
        print("PARSE ERRORS (%d):" % len(rep.errors))
        for d in rep.errors:
            print("  %s @%d" % (d.message, d.source_offset))
    return rf, rep


def _dump(scope, indent=0):
    """RETURN: None. Prints 'scope' and its children depth-first, deterministic.

    Symbols print in insertion order (dict preserves it); a scope's sealed flag
    and kind head each block so the seal law is observable in the recording.
    """
    pad = "  " * indent
    print("%sSCOPE[%s] '%s' sealed=%s"
          % (pad, scope.kind.value, scope.name, scope.sealed))
    for name, sym in scope.symbols.items():
        params = "".join(" %s:%s" % (n, t) for n, t in sym.params)
        print("%s  %-13s %s%s" % (pad, sym.kind, name,
                                  (" [" + params.strip() + "]") if params else ""))
    for child in scope.children:
        _dump(child, indent + 1)


def _report(reporter):
    """RETURN: None. Prints the scope-build diagnostics, tag and offset, in
              recorded order -- the negative-fixture assertion."""
    print("DIAGNOSTICS (%d):" % len(reporter.errors))
    for d in reporter.errors:
        print("  tag=%s %s @%d" % (d.tag, d.message, d.source_offset))


_CENSUS_SRC = """\
event: tick(amount: int)
clock: heartbeat 100

open: monitor.north

    event: arrived(depth: int)

    state_machine: crossing(rate: string)
        default: crossing.Idle

        state: Idle
            until: tick

        state: Active
            until: tick
    :end

:close
"""

_DUPLICATE_SRC = """\
event: tick(amount: int)
event: tick(depth: int)
"""

_COLLISION_SRC = """\
state_machine: crossing(Idle: string)
    default: crossing.Idle

    state: Idle
        until: tick
:end
"""


def run_census():
    """RETURN: None. Builds and prints the scope tree of the census fixture."""
    rf, _ = _parse(_CENSUS_SRC)
    rep = DiagnosticReporter()
    ground = build_scopes(rf, rep)
    _dump(ground)
    assert not rep.errors, "census fixture must build cleanly"
    print("clean build")


def run_duplicate():
    """RETURN: None. Builds the duplicate fixture; prints the one [NAME]."""
    rf, _ = _parse(_DUPLICATE_SRC)
    rep = DiagnosticReporter()
    build_scopes(rf, rep)
    _report(rep)
    assert len(rep.errors) == 1


def run_collision():
    """RETURN: None. Builds the collision fixture; prints the one [NAME]."""
    rf, _ = _parse(_COLLISION_SRC)
    rep = DiagnosticReporter()
    build_scopes(rf, rep)
    _report(rep)
    assert len(rep.errors) == 1


HwutRunner(
    argv       = sys.argv,
    title      = "Semantic Layer -- Scope Tree",
    choice_map = {
        "census":    run_census,
        "duplicate": run_duplicate,
        "collision": run_collision,
    },
).run()
