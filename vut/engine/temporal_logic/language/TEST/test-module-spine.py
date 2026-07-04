#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the module-spine STATES (module_states.py) and the one transition
         this layer owns: parse_module (rule_parser). Three properties, each a
         HWUT choice:

           states        The four front-half states exist with exactly their
                         declared fields, and SemanticModule IS-A DeclaredModule
                         (the substitution the cross-module walk depends on).
           parse_module  SourceModule -> ParsedModule over a fixture file:
                         provenance is carried by reference, the file_node is
                         the finalised "<file>" CST, no diagnostics.
           parse_faulty  A malformed fixture parses collect-and-continue: the
                         recovered items are present, every fault is recorded
                         in the reporter, nothing raises.

         declare/elaborate transitions belong to the semantic unit (later
         passes); their states are covered here, their behaviour is not.

CHOICES: states, parse_module, parse_faulty.
______________________________________________________________________________
"""
import os
import sys
import dataclasses

import config                                                   # noqa: F401
from config import HwutRunner

from vut.engine.temporal_logic.language.module_states import (
    SourceModule, ParsedModule, DeclaredModule, SemanticModule)
from vut.engine.temporal_logic.language.rule_parser import parse_module
from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter

_HERE = os.path.abspath(os.path.dirname(__file__))


def banner(label):
    """RETURN: None, always. Prints a section heading for the label 'label'."""
    print()
    print("--- %s ---" % label)


def fixture(name):
    """RETURN: str, the absolute path of fixture 'name' under TEST/fixtures."""
    return os.path.join(_HERE, "fixtures", name)


def show_module(parsed):
    """RETURN: None, always. Prints the provenance and CST summary of 'parsed'.

    Provenance is shown as the BASENAME of the origin path (absolute prefixes
    differ per checkout and would break the byte-exact diff); the AST summary
    is the typed root's class, its item count, and each item's product class
    (the top-level OR routes each item to its construct's typed product).
    """
    print("state:", type(parsed).__name__)
    print("origin:", os.path.basename(parsed.origin.path))
    node = parsed.file_node
    print("file_node:", type(node).__name__, "[%d items]" % len(node.items))
    for i, item in enumerate(node.items):
        # each item is the fired top-level construct's typed product
        print("  item %d: %s" % (i, type(item).__name__))


def run_states():
    """RETURN: None, always. Shows the state types, their fields, and the IS-A.

    Field inventories come from the dataclass machinery, so a field added or
    dropped on any state is a visible diff; the IS-A block asserts the
    substitution property (a SemanticModule passes wherever a DeclaredModule is
    peeked) directly with isinstance.
    """
    banner("state field inventory")
    for cls in (SourceModule, ParsedModule, DeclaredModule, SemanticModule):
        names = [f.name for f in dataclasses.fields(cls)]
        print("%-16s %s" % (cls.__name__, ", ".join(names)))

    banner("IS-A: SemanticModule substitutes for DeclaredModule")
    sem = SemanticModule(origin=SourceModule(path="p"), file_node=None,
                         export_db={}, symbol_table=None)
    print("isinstance(sem, DeclaredModule):", isinstance(sem, DeclaredModule))
    print("isinstance(sem, ParsedModule):  ", isinstance(sem, ParsedModule))
    print("export_db peekable on the SemanticModule:", sem.export_db == {})

    banner("transition ownership (documented, not imported)")
    print("parse     -> rule_parser.parse_module (this layer; tested here)")
    print("declare   -> semantic unit (later pass)")
    print("elaborate -> semantic unit (later pass)")


def run_parse_module():
    """RETURN: None, always. Drives SourceModule -> ParsedModule over a fixture.

    Shows the produced state, that provenance is the SAME SourceModule object
    (carried by reference, not copied), and that a clean fixture yields zero
    diagnostics.
    """
    src = SourceModule(path=fixture("minimal.vut"))
    reporter = DiagnosticReporter()
    parsed = parse_module(src, reporter)

    banner("SourceModule -> ParsedModule")
    show_module(parsed)
    print("origin is the given SourceModule object:", parsed.origin is src)
    print("diagnostics:", len(reporter.errors))
    print("has_fatal:", reporter.has_fatal())


def run_parse_faulty():
    """RETURN: None, always. Parses a malformed fixture; shows collect-and-continue.

    The first causality lacks its ';'. The parse must not raise: the reporter
    records the fault(s), and the recovered items still appear in the file node
    so a later phase can decide via has_fatal() whether to proceed.
    """
    src = SourceModule(path=fixture("faulty.vut"))
    reporter = DiagnosticReporter()
    parsed = parse_module(src, reporter)

    banner("faulty input: collect-and-continue")
    show_module(parsed)
    print("diagnostics:", len(reporter.errors))
    for d in reporter.errors:
        print("  ", d.message)
    print("has_fatal:", reporter.has_fatal())


HwutRunner(
    argv       = sys.argv,
    title      = "Module Spine (front half)",
    choice_map = {
        "states":       run_states,
        "parse_module": run_parse_module,
        "parse_faulty": run_parse_faulty,
    },
).run()
