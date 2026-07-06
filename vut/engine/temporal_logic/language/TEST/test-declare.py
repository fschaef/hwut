"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the DECLARE unit -- the ParsedModule -> DeclaredModule
         transition: the strict F-6 gate, the export surface, namespace
         re-opening, and SEMANTICS-18 duplicate rejection. Fixture rule-files
         live in fixtures/; paths print as basenames so the dump is
         byte-stable across checkouts.

CHOICES: gate, exports, reopen, duplicates, docstrings.

           gate        A parsed module carrying parser diagnostics is REFUSED:
                       declare_module raises (F-6 strict, ratified (a));
                       declare only ever sees a clean tree.
           exports     The full export surface of a rich module: definition
                       kinds, cause, declaration, import ALIAS (recorded, not
                       mounted -- F-1), namespace links, nested qualification;
                       anonymous causalities publish nothing; definition
                       internals stay private to their owner.
           reopen      Re-opening a namespace path EXTENDS it -- one link per
                       segment, no collision, later items joining the same
                       scope.
           duplicates  The same name declared twice in one scope is rejected
                       (SEMANTICS 18, fatal, tag NAME); the FIRST declaration
                       stays authoritative; a namespace link colliding with a
                       non-namespace name is the same rejection.
______________________________________________________________________________
"""
import os
import sys

import config                                                   # noqa: F401

from vut.engine.temporal_logic.language.rule_parser import parse_module
from vut.engine.temporal_logic.language.declare import declare_module
from vut.engine.temporal_logic.language.module_states import SourceModule
from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter
from vut.language_support.python.hwut_runner import HwutRunner

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "fixtures")


def banner(title):
    """RETURN: None, always. Prints the section banner for 'title'."""
    print("\n--- %s ---" % title)


def declare_fixture(basename):
    """RETURN: (DeclaredModule, DiagnosticReporter), the fixture parsed and
              declared with one shared reporter -- the caller reads exports
              off the module and rejections off the reporter.
    """
    reporter = DiagnosticReporter()
    parsed = parse_module(
        SourceModule(path=os.path.join(FIXTURES, basename)), reporter)
    return declare_module(parsed, reporter), reporter


def dump(declared, reporter):
    """RETURN: None, always. Prints the export_db (sorted, qualified name /
              kind / scope) and every diagnostic (tag and message) -- the
              byte-stable summary each choice locks.
    """
    print("exports: %d" % len(declared.export_db))
    for qualified, entry in declared.export_db:
        print("  %-30s %-12s scope=%s"
              % (".".join(qualified), entry.kind,
                 ".".join(entry.scope) or "-"))
    print("diagnostics: %d  (has_fatal: %s)"
          % (len(reporter.errors), reporter.has_fatal()))
    for d in reporter.errors:
        print("  [%s] %s" % (d.tag, d.message))


def run_gate():
    """RETURN: None, always. Pins the strict F-6 gate: a module whose parse
              produced diagnostics is refused by raising, with the count in
              the message -- no DeclaredModule, no partial export_db.
    """
    banner("F-6 strict gate: parser diagnostics block declare")
    reporter = DiagnosticReporter()
    parsed = parse_module(
        SourceModule(path=os.path.join(FIXTURES, "faulty.vut")), reporter)
    print("parse diagnostics:", len(reporter.errors))
    try:
        declare_module(parsed, reporter)
        print("UNEXPECTED: declare accepted a dirty tree")
    except ValueError as e:
        print("refused:", e)


def run_exports():
    """RETURN: None, always. Locks the export surface of the rich fixture:
              what is published, its kind, its scope -- and what deliberately
              is not (the causality, the behaviours inside the aspect body).
    """
    banner("export surface (declare-rich.vut)")
    dump(*declare_fixture("declare-rich.vut"))


def run_reopen():
    """RETURN: None, always. Pins namespace re-opening: the same dotted path
              opened twice publishes each link ONCE and both bodies' names
              land in the same scope -- extension, never collision.
    """
    banner("namespace re-opening extends the scope (declare-reopen.vut)")
    dump(*declare_fixture("declare-reopen.vut"))


def run_duplicates():
    """RETURN: None, always. Pins SEMANTICS-18: a repeated name in one scope
              is rejected (fatal, tag NAME), the first declaration stays
              authoritative; 'open:' on a name already declared non-namespace
              is the same rejection.
    """
    banner("duplicate declarations rejected, first wins (declare-dup.vut)")
    dump(*declare_fixture("declare-dup.vut"))


def run_docstrings():
    """RETURN: None, always. Locks D-18/SEMANTICS 22 over declare-doc.vut:
              the module docstring seats on the root, a documented
              behaviour exports exactly as an undocumented one (docstrings
              never enter the surface), and the one MISPLACED docstring --
              preceding no definition, not first in the file -- draws the
              rejection while declaration continues.
    """
    banner("docstrings (declare-doc.vut)")
    reporter = DiagnosticReporter()
    parsed = parse_module(
        SourceModule(path=os.path.join(FIXTURES, "declare-doc.vut")),
        reporter)
    declared = declare_module(parsed, reporter)
    print("module doc: %r" % parsed.file_node.doc.text)
    for qualified, entry in declared.export_db:
        print("  %-20s %s" % (".".join(qualified), entry.kind))
    print("diagnostics: %d" % len(reporter.errors))
    for d in reporter.errors:
        print("  %s [%s] %s" % ("REJECT" if d.fatal else "WARN  ",
                                d.tag, d.message))


HwutRunner(
    argv       = sys.argv,
    title      = "Declare Unit (export_db, F-6 gate, SEMANTICS 18)",
    choice_map = {
        "gate":       run_gate,
        "exports":    run_exports,
        "reopen":     run_reopen,
        "duplicates": run_duplicates,
        "docstrings": run_docstrings,
    },
).run()
