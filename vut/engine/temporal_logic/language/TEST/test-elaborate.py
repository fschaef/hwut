"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the ELABORATE unit -- the DeclaredModule -> SemanticModule
         transition: import mounting (F-1 step 0), recipe seating on every
         ReferenceLeaf (binding heads, local frames, scope-aware table hits
         with residue, free), and the settled checks the walk carries
         (SEMANTICS 2, 5, 7, 17, 19; the sm/mg binding law). Fixtures live in
         fixtures/; peer modules are declared inside the test through the
         same front half, so mounting reads a REAL export_db.

CHOICES: gate, mount_recipes, rejects, warn17, work_rejects.

           gate           A reporter already carrying diagnostics makes
                          elaborate_module refuse by raising -- the F-6
                          discipline extended to this boundary.
           mount_recipes  The two-module case: the peer's exports mounted
                          under the alias, and every reference of the main
                          module dumped with its seated recipe -- kinds,
                          targets, residues, origins; free raw events seat
                          'free' with NO diagnostic.
           rejects        One fixture, every REJECT of the pass in source
                          order: a guarded lifecycle (5), a guarded use of a
                          named cause (2), sm/mg outside a definition body
                          (BINDING), a nested exit-label (7b), a backward
                          dropto (7c), an unresolved is:-target and named
                          type (19).
           warn17         An effect targeting a locally ABSTRACT entity draws
                          the WARN remark; elaboration proceeds (fatal False).
______________________________________________________________________________
"""
import dataclasses
import os
import sys

import config                                                   # noqa: F401

from vut.engine.temporal_logic.language.rule_parser import parse_module
from vut.engine.temporal_logic.language.declare import declare_module
from vut.engine.temporal_logic.language.elaborate import elaborate_module
from vut.engine.temporal_logic.language.module_states import SourceModule
from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter
from vut.engine.temporal_logic.core.symbol.ast import ReferenceLeaf
from vut.language_support.python.hwut_runner import HwutRunner

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "fixtures")


def banner(title):
    """RETURN: None, always. Prints the section banner for 'title'."""
    print("\n--- %s ---" % title)


def front_half(basename, peers={}):
    """RETURN: (SemanticModule, DiagnosticReporter), the fixture taken through
              parse, declare and elaborate on one shared reporter -- exactly
              the spine a build driver would run.
    """
    reporter = DiagnosticReporter()
    parsed = parse_module(
        SourceModule(path=os.path.join(FIXTURES, basename)), reporter)
    declared = declare_module(parsed, reporter)
    return elaborate_module(declared, peers, reporter), reporter


def declared_only(basename):
    """RETURN: DeclaredModule, the fixture parsed and declared -- a peer for
              mounting; its reporter must stay clean (asserted, so a broken
              peer fixture fails loudly instead of skewing the choice).
    """
    reporter = DiagnosticReporter()
    parsed = parse_module(
        SourceModule(path=os.path.join(FIXTURES, basename)), reporter)
    declared = declare_module(parsed, reporter)
    assert not reporter.errors, "peer fixture must be clean"
    return declared


def all_references(node, out=None):
    """RETURN: list, every ReferenceLeaf of the typed tree in walk order --
              tuples recurse, dataclass fields recurse, scalars end the
              descent.
    """
    if out is None:
        out = []
    if isinstance(node, ReferenceLeaf):
        out.append(node)
    elif isinstance(node, tuple):
        for item in node:
            all_references(item, out)
    elif dataclasses.is_dataclass(node):
        for f in dataclasses.fields(node):
            all_references(getattr(node, f.name), out)
    return out


def dump_recipes(semantic):
    """RETURN: None, always. Prints one line per reference: the written name
              and its seated recipe (kind, target, residue, origin) -- an
              UNSEATED leaf would print as such, so the dump doubles as the
              totality guard of the walk.
    """
    for leaf in all_references(semantic.file_node):
        access = leaf.access
        line = "  %-18s -> " % ".".join(leaf.segments)
        if access is None:
            line += "UNSEATED"
        else:
            line += "%s:%s" % (access.kind, ".".join(access.target))
            if access.residue:
                line += "  residue=" + ".".join(access.residue)
            if access.origin:
                line += "  origin=" + access.origin
        print(line)


def dump_diagnostics(reporter):
    """RETURN: None, always. Prints the diagnostic count and each entry's
              severity, tag and message -- the reject/warn summary each
              choice locks.
    """
    print("diagnostics: %d  (has_fatal: %s)"
          % (len(reporter.errors), reporter.has_fatal()))
    for d in reporter.errors:
        print("  %s [%s] %s"
              % ("REJECT" if d.fatal else "WARN  ", d.tag, d.message))


def run_gate():
    """RETURN: None, always. Pins the boundary gate: elaborate refuses a
              dirty reporter by raising, never producing a partial
              SemanticModule.
    """
    banner("boundary gate: prior diagnostics block elaborate")
    reporter = DiagnosticReporter()
    parsed = parse_module(
        SourceModule(path=os.path.join(FIXTURES, "faulty.vut")), reporter)
    print("parse diagnostics:", len(reporter.errors))
    try:
        declared = declare_module(parsed, reporter)
        print("UNEXPECTED: declare accepted a dirty tree", declared)
    except ValueError as e:
        print("declare refused:", e)
    try:
        elaborate_module(None, {}, reporter)
        print("UNEXPECTED: elaborate accepted a dirty reporter")
    except ValueError as e:
        print("elaborate refused:", e)


def run_mount_recipes():
    """RETURN: None, always. Locks the two-module surface: the peer's exports
              under the alias in the symbol table, and every recipe of the
              main module -- mounted hits with origin and residue, binding
              heads, locals, table hits, free raw events (no diagnostic).
    """
    peer = declared_only("elab-peer.vut")
    semantic, reporter = front_half(
        "elab-main.vut", peers={"lib/base.vut": peer})
    banner("symbol table (own + mounted)")
    for qualified, (entry, origin) in semantic.symbol_table:
        surface = ",".join(
            m.name + ("=" if m.has_default else "") for m in entry.members)
        print("  %-24s %-12s%s%s%s"
              % (".".join(qualified), entry.kind,
                 " ~" if entry.abstract else "",
                 "  (" + surface + ")" if surface else "",
                 "  <- " + origin if origin else ""))
    banner("recipes")
    dump_recipes(semantic)
    banner("diagnostics")
    dump_diagnostics(reporter)


def run_rejects():
    """RETURN: None, always. Locks every REJECT of the pass over one fixture,
              in source order -- guard laws, the sm/mg binding law, the
              exit-region discipline, unresolved required references -- plus
              the missing-peer mount rejection.
    """
    banner("all rejections (elab-rejects.vut; import peer NOT supplied)")
    semantic, reporter = front_half("elab-rejects.vut", peers={})
    dump_diagnostics(reporter)
    print("elaboration stayed total: %d recipes seated"
          % len([leaf for leaf in all_references(semantic.file_node)
                 if leaf.access is not None]))


def run_work_rejects():
    """RETURN: None, always. Locks the work-body REJECTs of SEMANTICS 23
              over one fixture: an exit: naming an undeclared signal
              (LANGUAGE 12.4, first direction), a declared signal no
              reachable exit: emits (second direction), and a tick:
              outside a clockwork's ticks: hosting (LANGUAGE 13.3).
    """
    banner("work rejections (elab-work-rejects.vut)")
    semantic, reporter = front_half("elab-work-rejects.vut", peers={})
    dump_diagnostics(reporter)


def run_warn17():
    """RETURN: None, always. Pins SEMANTICS 17: an effect targeting a locally
              defined ABSTRACT entity draws the remark (fatal False) and
              nothing else; elaboration proceeds.
    """
    banner("abstract-target remark (elab-warn17.vut)")
    semantic, reporter = front_half("elab-warn17.vut")
    dump_diagnostics(reporter)
    print("fatal-free:", not reporter.has_fatal())


HwutRunner(
    argv       = sys.argv,
    title      = "Elaborate Unit (mount, recipes, settled checks)",
    choice_map = {
        "gate":          run_gate,
        "mount_recipes": run_mount_recipes,
        "rejects":       run_rejects,
        "warn17":        run_warn17,
        "work_rejects": run_work_rejects,
    },
).run()
