"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

TEST: resolve_program end to end (pass 2 driver, README THE PIPELINE / J)

Runs the public seam over real source: load -> build -> resolve+drain ->
checks -> cascade, producing a frozen ResolvedProgram or gating to None. The
printed program summary / gate verdict IS the assertion.

Choices:
    clean    events + a nested state machine + a clean cascade -> a
             ResolvedProgram (sealed scopes, queried set, cascade edges).
    gate     a cascade cycle -> the pipeline gates at stage 4, returns None,
             one [CASCADE].
______________________________________________________________________________
"""
import sys
from config import HwutRunner

from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter
from vut.engine.temporal_logic.semantic.resolve import resolve_program
from fake_luau_oracle import FakeLuauOracle


def _loader(key):
    """RETURN: never; raises -- these fixtures have no imports, so a load
              attempt is a fixture bug surfaced as a loader failure."""
    raise FileNotFoundError(key)


_CLEAN_SRC = """\
event: A(n: int)
event: B(n: int)
clock: heartbeat 100

open: monitor

    state_machine: crossing(rate: string)
        default: crossing.Idle

        state: Idle
            init: { y = 2 }
            until: A

        state: Active
            init: { y = 3 }
            until: B
    :end

:close

on: A => B(n = 1)
"""

_GATE_SRC = """\
event: A(n: int)
event: B(n: int)
on: A => B(n = 1)
on: B => A(n = 1)
"""


def run_clean():
    """RETURN: None. Resolves the clean fixture; prints the program summary."""
    rep  = DiagnosticReporter()
    prog = resolve_program(_CLEAN_SRC, "root.rule", FakeLuauOracle(),
                           _loader, rep)
    print("program: %s" % ("ResolvedProgram" if prog else None))
    print("errors: %d" % len(rep.errors))
    for d in rep.errors:
        print("  tag=%s %s @%d" % (d.tag, d.message, d.source_offset))
    if prog:
        print("root sealed: %s" % prog.module.scope_tree.sealed)
        print("top symbols: %s" % sorted(prog.module.scope_tree.symbols))
        print("queried: %s" % sorted(prog.module.cascade_part.queried))
        print("cascade edges: %s"
              % {k: sorted(v)
                 for k, v in sorted(prog.module.cascade_part.edges.items())})
    assert prog is not None and not rep.errors


def run_gate():
    """RETURN: None. Cascade cycle gates the pipeline at stage 4 -> None."""
    rep  = DiagnosticReporter()
    prog = resolve_program(_GATE_SRC, "root.rule", FakeLuauOracle(),
                           _loader, rep)
    print("program: %s" % prog)
    print("errors: %d" % len(rep.errors))
    for d in rep.errors:
        print("  tag=%s %s" % (d.tag, d.message))
    assert prog is None and len(rep.errors) >= 1


HwutRunner(
    argv       = sys.argv,
    title      = "Semantic Layer -- resolve_program (end to end)",
    choice_map = {
        "clean": run_clean,
        "gate":  run_gate,
    },
).run()
