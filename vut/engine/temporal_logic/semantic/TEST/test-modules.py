"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

TEST: module manager (pass 2, README A / J)

The load walk over a dict-backed loader (a deterministic in-memory file set --
no real filesystem, so the fixture is hermetic). Each choice parses real source
through the parser and the neutral test oracle. The printed report IS the
assertion.

Choices:
    clean       root imports one leaf -> both PARSED, the import edge captured.
    cycle       a -> b -> a -> the ordered chain, [STRUCTURE], fatal-stop.
    missing     an import naming an absent module -> an infrastructure fatal
                with NO author class tag (a machine fault, not one of the seven
                author classes).
______________________________________________________________________________
"""
import sys
from config import HwutRunner

from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter
from vut.engine.temporal_logic.semantic.modules import load_import_closure
from fake_luau_oracle import FakeLuauOracle


def _loader_over(files):
    """RETURN: loader(key) -> source str; raises FileNotFoundError for an
              absent key (the loader contract: it raises on absence)."""
    def loader(key):
        if key not in files:
            raise FileNotFoundError("no such module")
        return files[key]
    return loader


def _run(root_source, files):
    """RETURN: (LoadTable, DiagnosticReporter) for a load walk from the root
              over the in-memory 'files'."""
    rep = DiagnosticReporter()
    ms  = load_import_closure(root_source, "root.rule", FakeLuauOracle(),
                              _loader_over(files), rep)
    return ms, rep


_CLEAN_FILES = {"leaf.rule": "event: ping(amount: int)\n"}
_CLEAN_ROOT  = 'import: "leaf.rule" into: lib\nevent: tick(amount: int)\n'

_CYCLE_FILES = {
    "a.rule": 'import: "b.rule" into: bb\nevent: ea(amount: int)\n',
    "b.rule": 'import: "a.rule" into: aa\nevent: eb(amount: int)\n',
}
_CYCLE_ROOT  = 'import: "a.rule" into: aa\nevent: root_ev(amount: int)\n'

_MISSING_ROOT = 'import: "ghost.rule" into: g\nevent: tick(amount: int)\n'


def run_clean():
    """RETURN: None. Prints the loaded modules of the clean fixture, each with
              its provenance (importer@offset) and derived imports."""
    ms, rep = _run(_CLEAN_ROOT, _CLEAN_FILES)
    print("ok=%s root=%s" % (ms.ok, ms.root_key))
    for key in sorted(ms.modules):
        m     = ms.modules[key]
        pv    = m.provenance
        by    = "%s@%d" % (pv.importer_key, pv.import_offset) if pv.importer_key else "ROOT"
        edges = ", ".join("%s->%s" % (p, ".".join(mt)) for p, mt, _ in m.imports)
        print("  %-10s by=%-12s imports=[%s]" % (key, by, edges))
    print("diagnostics=%d" % len(rep.errors))
    assert ms.ok and not rep.errors


def run_cycle():
    """RETURN: None. Prints the import-cycle chain of the cycle fixture."""
    ms, rep = _run(_CYCLE_ROOT, _CYCLE_FILES)
    print("ok=%s" % ms.ok)
    for d in rep.errors:
        print("  tag=%s %s @%d" % (d.tag, d.message, d.source_offset))
    assert not ms.ok


def run_missing():
    """RETURN: None. Prints the infrastructure fatal of the missing fixture."""
    ms, rep = _run(_MISSING_ROOT, {})
    print("ok=%s has_fatal=%s" % (ms.ok, rep.has_fatal()))
    for d in rep.errors:
        print("  tag=%s %s" % (d.tag, d.message))
    assert not ms.ok and rep.has_fatal()


HwutRunner(
    argv       = sys.argv,
    title      = "Semantic Layer -- Module Manager",
    choice_map = {
        "clean":   run_clean,
        "cycle":   run_cycle,
        "missing": run_missing,
    },
).run()
