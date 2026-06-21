"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

TEST: the reference-resolution report (pass 2 -- the S3 safety net; disc-5)

Observes WHICH reference sites seat and from WHICH enclosing scope, over real
source. For every candidate reference site in the fixture (a fixed taxonomy, not
the admitted _REF_SITES set) the report prints the dotted name, the enclosing
scope kind, and the seated symbol -- or UNSEATED if the resolver does not yet
admit that site. The row SET is stable; widening _REF_SITES flips a single row
from UNSEATED to a seated symbol, a reviewable diff. The printed report IS the
assertion (HWUT discipline): each S3 site addition must MOVE this GOOD.

Choices:
    clean    the nested-state-machine fixture: a ground-scope Trigger, a
             DefaultRef inside the SM, until-causes in states, an effect.
______________________________________________________________________________
"""
import sys
from config import HwutRunner

from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter
from vut.engine.temporal_logic.parser.ast_nodes import Import  # noqa: F401
from fake_luau_oracle import FakeLuauOracle

from vut.engine.temporal_logic.semantic.modules    import load_import_closure
from vut.engine.temporal_logic.semantic.scope_tree import build_scopes
from vut.engine.temporal_logic.semantic.resolver   import ResolutionState
from vut.engine.temporal_logic.semantic.resolve    import (
    _resolve_module, _drain_all, reference_report)


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


def _loader(key):
    """RETURN: never; raises -- the fixture has no imports."""
    raise FileNotFoundError(key)


def _resolve_and_observe(src):
    """RETURN: (module-ast, root-scope, state) after the real LOCAL resolve pass.

    Drives parse -> build_scopes -> _resolve_module -> _drain_all exactly as
    resolve() does, but keeps the ResolutionState so the report can read what
    seated. Reaching the private walk is deliberate: this is an in-layer
    observation test, not a public-seam test.
    """
    rep = DiagnosticReporter()
    load_table = load_import_closure(src, "root.rule", FakeLuauOracle(),
                                     _loader, rep)
    parsed = load_table.modules[load_table.root_key]
    scope  = build_scopes(parsed.ast, rep)
    state  = ResolutionState()
    _resolve_module(parsed.ast, scope, state, rep, proxies=())
    _drain_all(scope, state, rep)
    return parsed.ast, scope, state, rep


def run_clean():
    """RETURN: None. Prints the reference-resolution report for the clean
              fixture: every candidate site, its enclosing scope, its seat."""
    ast, scope, state, rep = _resolve_and_observe(_CLEAN_SRC)

    print("errors: %d" % len(rep.errors))
    for d in rep.errors:
        print("  tag=%s %s @%d" % (d.tag, d.message, d.source_offset))

    print("references (name | enclosing-scope | seated):")
    for name, scope_kind, seated in reference_report(ast, scope, state):
        print("  %-18s %-14s %s" % (name, scope_kind, seated))


HwutRunner(
    argv       = sys.argv,
    title      = "Semantic Layer -- reference-resolution report (S3 net)",
    choice_map = {
        "clean": run_clean,
    },
).run()
