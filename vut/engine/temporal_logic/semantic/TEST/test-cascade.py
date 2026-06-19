"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

TEST: cascade graph (pass 2, README F / J)

Parses real source, builds the event-kind graph, prints the edges, runs the
coloured-DFS cycle check. The printed edges + diagnostics ARE the assertion.

Choices:
    clean       A -> B -> C, acyclic -> no diagnostics.
    cycle       A -> B -> A -> one [CASCADE] cycle chain.
    any_fanout  'on: ANY => A' fans inbound from every node; combined with
                A -> B this closes cycles A->A and A->B->A -> two [CASCADE]
                (accumulate-and-continue, and the over-approximation of ANY).

Note: emitting a system kind (END/CHANGE/...) is rejected at PARSE time for
every surface form, so the [CASCADE] system-emission guard in cascade.py is
defensive (reachable only via an aliased/imported system kind) and is not
exercised by a parseable fixture here.
______________________________________________________________________________
"""
import sys
from config import HwutRunner

from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter
from vut.engine.temporal_logic.parser.rule_parser import parse
from vut.engine.temporal_logic.semantic.cascade import build_cascade, find_cycles
from fake_luau_oracle import FakeLuauOracle


def _run(src):
    """RETURN: (Cascade, DiagnosticReporter) after build + cycle check on 'src'.

    Parse errors are printed so a broken fixture is visible; the cascade is then
    built and its cycles found, both into one reporter.
    """
    prep = DiagnosticReporter()
    rf   = parse(src, FakeLuauOracle(), prep)
    if prep.errors:
        print("PARSE ERRORS (%d):" % len(prep.errors))
        for d in prep.errors:
            print("  %s @%d" % (d.message, d.source_offset))
    rep  = DiagnosticReporter()
    casc = build_cascade(rf, rep)
    find_cycles(casc, rep)
    return casc, rep


def _report(casc, rep):
    """RETURN: None. Prints the sorted edge set then the diagnostics in order."""
    edges = {k: sorted(v) for k, v in sorted(casc.edges.items())}
    print("EDGES: %s" % edges)
    print("DIAGNOSTICS (%d):" % len(rep.errors))
    for d in rep.errors:
        print("  tag=%s %s @%d" % (d.tag, d.message, d.source_offset))


_CLEAN_SRC = """\
event: A(n: int)
event: B(n: int)
event: C(n: int)
on: A => B(n = 1)
on: B => C(n = 1)
"""

_CYCLE_SRC = """\
event: A(n: int)
event: B(n: int)
on: A => B(n = 1)
on: B => A(n = 1)
"""

_ANY_SRC = """\
event: A(n: int)
event: B(n: int)
on: A => B(n = 1)
on: ANY => A(n = 1)
"""


def run_clean():
    """RETURN: None. Acyclic chain -> no diagnostics."""
    casc, rep = _run(_CLEAN_SRC)
    _report(casc, rep)
    assert not rep.errors


def run_cycle():
    """RETURN: None. A -> B -> A -> one cascade-cycle diagnostic."""
    casc, rep = _run(_CYCLE_SRC)
    _report(casc, rep)
    assert len(rep.errors) >= 1


def run_any_fanout():
    """RETURN: None. ANY fan-in closing cycles -> accumulate-and-continue."""
    casc, rep = _run(_ANY_SRC)
    _report(casc, rep)
    assert len(rep.errors) >= 1


HwutRunner(
    argv       = sys.argv,
    title      = "Semantic Layer -- Cascade Graph",
    choice_map = {
        "clean":      run_clean,
        "cycle":      run_cycle,
        "any_fanout": run_any_fanout,
    },
).run()
