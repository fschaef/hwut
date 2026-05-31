#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the rule-file Parser: AST construction and error recovery.

CHOICES: causality, effects, mode, state_machine, definitions, roles,
         resync, missing_off;

DESCRIPTION:

The Parser drives the pull-Lexer, builds the AST (ast_nodes), and assigns each
Luau span its grammar role. It resyncs at 'off' / top-level keywords on error,
running to end-of-file so every construct is attempted.

    causality      'on <cause> => <effect> off' with and without a guard;
                   trigger keywords (ANY/BEGIN/END) are recognised.
    effects        The four effect kinds -- event-spec, '+' mode-arming,
                   report string, '{ }' mutation -- each parse to their node.
    mode           A mode parses its members (causalities, init, deinit) and
                   the mandatory 'until' list; nested causalities keep 'off'.
    state_machine  A state machine parses 'default =', init/deinit, and its
                   'until' list; 'default = SM.VOID' resolves to the void ref.
    definitions    'event name(decls)' and 'clock name number' parse to
                   EventDef / ClockDef with their parameters.
    roles          Each Luau span carries the role the parser chose: guard ->
                   CONDITION, rvalue -> EXPRESSION, body -> STATEMENT_BLOCK.
    resync         A malformed rule between two good ones is reported once and
                   skipped; both good rules still appear in the AST.
    missing_off    A causality lacking its closing 'off' is reported; the
                   parser recovers at the next top-level keyword.
______________________________________________________________________________
"""
import sys
import config                                                       # noqa: F401

from   vut.language_support.python.hwut_runner         import HwutRunner
from   vut.engine.temporal_logic.parser.diagnostic     import DiagnosticReporter
from   vut.engine.temporal_logic.parser.parser         import parse
import vut.engine.temporal_logic.parser.ast_nodes      as ast
from   vut.engine.temporal_logic.parser.TEST.fake_luau_oracle import FakeLuauOracle


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def parse_text(src):
    """RETURN: (RuleFile, reporter), the AST and collected diagnostics for src."""
    reporter = DiagnosticReporter()
    tree     = parse(src, FakeLuauOracle(), reporter)
    return tree, reporter


def show_diagnostics(reporter):
    """RETURN: None. Prints collected diagnostics, or a 'none' line."""
    if not reporter.errors:
        print("diagnostics: (none)")
        return
    print("diagnostics:")
    for d in reporter.errors:
        print("  %-8s fatal=%-5s off=%-3d %s"
              % (d.phase.name, str(d.fatal), d.source_offset, d.message))


def show_effect(effect, indent):
    """RETURN: None. Prints one effect node compactly."""
    pad = "  " * indent
    if isinstance(effect, ast.EventSpec):
        print("%sEventSpec %s(%d arg)" % (pad, effect.name, len(effect.args)))
    elif isinstance(effect, ast.ModeArming):
        print("%sModeArming +%s(%d arg)" % (pad, effect.name, len(effect.args)))
    elif isinstance(effect, ast.ReportString):
        print("%sReportString %r" % (pad, effect.text))
    elif isinstance(effect, ast.Mutation):
        print("%sMutation role=%s %r"
              % (pad, effect.body.role.name, effect.body.text))


def show_cause(cause, indent):
    """RETURN: None. Prints a cause: trigger, keyword flag, guard presence."""
    pad = "  " * indent
    kw  = "keyword" if cause.trigger.is_keyword else "event"
    g   = "guard(%s)" % cause.guard.role.name if cause.guard else "no-guard"
    print("%sCause %s=%s %s" % (pad, kw, cause.trigger.name, g))


def show_item(item, indent=0):
    """RETURN: None. Prints one top-level construct and its children."""
    pad = "  " * indent
    if isinstance(item, ast.Causality):
        print("%sCausality" % pad)
        show_cause(item.cause, indent + 1)
        for e in item.effects:
            show_effect(e, indent + 1)
    elif isinstance(item, ast.Mode):
        print("%sMode %s params=%d init=%s deinit=%s causalities=%d untils=%d"
              % (pad, item.name, len(item.params),
                 "Y" if item.init else "N", "Y" if item.deinit else "N",
                 len(item.causalities), len(item.untils)))
        for c in item.causalities:
            show_item(c, indent + 1)
        for u in item.untils:
            show_cause(u, indent + 1)
    elif isinstance(item, ast.StateMachine):
        dflt = "%s.%s" % (item.default.sm_name, item.default.mode_name) \
               if item.default else "(none)"
        print("%sStateMachine %s default=%s init=%s deinit=%s untils=%d"
              % (pad, item.name, dflt,
                 "Y" if item.init else "N", "Y" if item.deinit else "N",
                 len(item.untils)))
        for u in item.untils:
            show_cause(u, indent + 1)
    elif isinstance(item, ast.EventDef):
        decls = ", ".join("%s:%s" % (p.member, p.type) for p in item.params)
        print("%sEventDef %s(%s)" % (pad, item.name, decls))
    elif isinstance(item, ast.ClockDef):
        print("%sClockDef %s period=%s" % (pad, item.name, item.period))


def show_tree(tree):
    """RETURN: None. Prints all top-level items of a RuleFile."""
    for item in tree.items:
        show_item(item)


def run_causality():
    """RETURN: None. Causalities with/without guard and with keyword triggers."""
    banner("guarded event trigger")
    tree, rep = parse_text("on Tick & { event.n > 0 } => Beep() off")
    show_tree(tree)
    show_diagnostics(rep)

    banner("keyword triggers ANY / BEGIN / END")
    tree, rep = parse_text("on ANY => Log() off\n"
                           "on BEGIN => Start() off\n"
                           "on END => Stop() off")
    show_tree(tree)
    show_diagnostics(rep)


def run_effects():
    """RETURN: None. The four effect kinds each parse to the right node."""
    banner("all four effect kinds in one rule")
    src = ('on Tick => Beep(volume = 3) => + Blink() '
           '=> "tick {event.n}" => { sm.n = sm.n + 1 } off')
    tree, rep = parse_text(src)
    show_tree(tree)
    show_diagnostics(rep)


def run_mode():
    """RETURN: None. A mode with init, a member causality, and 'until'."""
    banner("mode with init, member rule, and until")
    src = ("mode Blink :\n"
           "    on Tick => Toggle() off\n"
           "    init { sm.x = 0 }\n"
           "    deinit { sm.x = nil }\n"
           "    until ANY\n")
    tree, rep = parse_text(src)
    show_tree(tree)
    show_diagnostics(rep)


def run_state_machine():
    """RETURN: None. A state machine with default, init, and until list."""
    banner("state machine with default member")
    src = ("state_machine Traffic :\n"
           "    default = Traffic.RED\n"
           "    init { sm.phase = 0 }\n"
           "    until END\n")
    tree, rep = parse_text(src)
    show_tree(tree)
    show_diagnostics(rep)

    banner("default to implicit VOID")
    src = ("state_machine Idle :\n"
           "    default = Idle.VOID\n"
           "    until ANY\n")
    tree, rep = parse_text(src)
    show_tree(tree)
    print("default is_void:", tree.items[0].default.is_void)
    show_diagnostics(rep)


def run_definitions():
    """RETURN: None. event and clock declarations parse with parameters."""
    banner("event declaration with two parameters")
    tree, rep = parse_text("event Move(dx : int ; dy : int)")
    show_tree(tree)
    show_diagnostics(rep)

    banner("clock declaration")
    tree, rep = parse_text("clock Tick 100")
    show_tree(tree)
    show_diagnostics(rep)


def run_roles():
    """RETURN: None. Each Luau span carries the role its context dictates."""
    banner("guard=CONDITION, rvalue=EXPRESSION, body=STATEMENT_BLOCK")
    src = 'on Tick & { event.ok } => Beep(n = { 1 + 2 }) => { sm.x = 1 } off'
    tree, rep = parse_text(src)
    rule = tree.items[0]
    print("guard role:   ", rule.cause.guard.role.name)
    arg = rule.effects[0].args[0]
    print("rvalue is_luau:", arg.is_luau, "role:", arg.value.role.name)
    print("mutation role:", rule.effects[1].body.role.name)
    show_diagnostics(rep)


def run_resync():
    """RETURN: None. A bad middle rule is reported once; neighbours survive."""
    banner("malformed middle rule recovered at 'off'")
    src = ("on A => Beep() off\n"
           "on B => => off\n"
           "on C => Honk() off\n")
    tree, rep = parse_text(src)
    print("recovered rules:")
    for it in tree.items:
        print("  on", it.cause.trigger.name)
    show_diagnostics(rep)


def run_missing_off():
    """RETURN: None. A causality without 'off' recovers at next construct."""
    banner("missing 'off' before next top-level keyword")
    src = ("on A => Beep()\n"
           "event Tick(n : int)\n")
    tree, rep = parse_text(src)
    print("items recovered:")
    for it in tree.items:
        print("  ", type(it).__name__)
    show_diagnostics(rep)


HwutRunner(
    argv       = sys.argv,
    title      = "Rule-file Parser",
    choice_map = {
        "causality":     run_causality,
        "effects":       run_effects,
        "mode":          run_mode,
        "state_machine": run_state_machine,
        "definitions":   run_definitions,
        "roles":         run_roles,
        "resync":        run_resync,
        "missing_off":   run_missing_off,
    },
).run()
