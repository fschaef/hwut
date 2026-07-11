#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the rule-file GRAMMAR and its binding to the core engine (the
         OUTER language layer). Three properties, each a HWUT choice:

           compile     GRAMMAR compiles under the core engine with NO LL(2)
                       conflict and NO role-vocabulary violation -- the two
                       load-time gates the facade relies on -- and yields the
                       expected rule inventory and start symbol.
           constructs  Every LANGUAGE.txt construct parses to a clean CST: one
                       representative snippet per construct is parsed and its
                       fault count reported. A regression that breaks a
                       construct's grammar surfaces here as that snippet's line
                       flipping OK -> ERR with the diagnostics shown.
           ast_shape   The typed AST of two canonical snippets is rendered
                       structurally, locking the actual tree the engine builds
                       (node kinds, rule names, surviving tokens) -- not merely
                       that parsing succeeded.

         The grammar-agnostic machinery (lexer tiers, LL(2) engine, CST reduce)
         is tested in core/*/TEST; this file asserts only what the LANGUAGE
         layer adds on top of that machinery.

CHOICES: compile, constructs, ast_shape.
______________________________________________________________________________
"""
import sys

import config                                                   # noqa: F401
from config import HwutRunner

from vut.engine.temporal_logic.language.rule_parser import parse, compiled_grammar
from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter


# One representative snippet per LANGUAGE.txt construct. Each MUST parse with
# zero diagnostics. Snippets are spelled to the grammar (ground truth): a
# causality ends in ';'.
# Ordered so the printed report is stable regardless of dict iteration.
SNIPPETS = [
 ("causality",     "button_pressed => light_on;"),
 ("guarded",       "MOTOR_ON when: c.fuel == 0 => lighten_fuel_missing;"),
 ("def_cause",     "OPERATION_IMPOSSIBLE : cause(fuel_limit, battery_limit)\n"
                   "    MOTOR_ON when: c.fuel <= fuel_limit or c.battery < battery_limit;"),
 ("cause_ref",     "OPERATION_IMPOSSIBLE(0.1, 2) => SIGNAL_REFUSE_OPERATION;"),
 ("behavior",      "ClimateControlWhenActivated : behavior {\n"
                   "    ac_button_pushed => toggle_compressor;\n"
                   "    temp_dial_turned => set_target_temperature;\n"
                   "    fan_dial_turned  => adjust_fan_speed;\n}"),
 ("recurring",     "Polling : behavior {\n"
                   "    ~ENTRY       => poll_sensors() every: 0.5 as: poller;\n"
                   "    stop_pressed =x=> poller;\n}"),
 ("aspect",        "MotorActivity : aspect {\n"
                   "    GENERAL : ~behavior {\n"
                   "         gas_pedal_release => close_throttle;\n"
                   "         battery_empty     => close_throttle;\n    }\n"
                   "    ON : behavior is: GENERAL {\n"
                   "         gas_pedal_push     => open_throttle;\n"
                   "         on_off_button_push => OFF;\n    }\n"
                   "    OFF : behavior is: GENERAL {\n"
                   "         gas_pedal_push     => tone_notify_engine_off;\n"
                   "         on_off_button_push => ON;\n    }\n}"),
 ("character",     "sprite : ~character has: {\n"
                   "    position:  vec2;\n    speed:     vec2;\n"
                   "    resources: AspectResources;\n}"),
 ("namespace",     "open: graphics.sprites {\n"
                   "    sprite : ~character has: { position: vec2; }\n}"),
 ("import",        'import: "lib/physics.vut" as: physics'),
 ("command_block", "TRAVELLED_100KM => {\n"
                   "    c.fuel -= 8.31;\n"
                   "    if: c.fuel < 5.0   { c.warn = true; }\n"
                   "    elif: c.fuel < 20.0 { c.warn = false; }\n"
                   "    else:               { c.reserve = false; }\n"
                   "    int: i = 1 .. c.cylinders { c.checks += i; }\n}"),
 ("match",         "X => {\n    match: c.state {\n"
                   "        case: 3 { c.a = 1; }\n"
                   "        case: 1 to: 5 { c.b = 2; }\n"
                   '        case: "ab*" { c.g = 3; }\n'
                   "        case: _ { c.d = 4; }\n    }\n}"),
 ("for_loop",      "X => { for: v in: c.items { c.sum += v; } }"),
 ("enumeration",   "X => { int: i with: x from: c.items start: 2 { c.sum += i * x; } }"),
 ("exit_region",   "SOMETHING => {\n"
                   "    c.h = acquire_a();\n"
                   "    if: not c.h.ok  { dropto: fail; }\n"
                   "    c.g = acquire_b();\n"
                   "    if: not c.g.ok  { dropto: free_a; }\n"
                   "    dropto: done;\n"
                   "  :free_a:   c.released_a = release_a(c.h);\n"
                   "  :fail:     c.status = FAILED;\n"
                   "  :done:\n}"),
 ("comprehension", "X => { c.pp = [ x*y   with: x, y from: pairs ];\n"
                   "        c.pos = [ x with: x from: xs if: x > 0 ];\n"
                   "        c.mix = [ x + y with: x from: xs if: x > 0\n"
                   "                        with: y from: ys ];\n"
                   "        c.nest = [ [ a*b with: b from: row ] with: row from: matrix ]; }"),
 ("data_access",   "X => { c.buf[i] = v; c.f = grid[i][j]; c.z = f(x)[0]; }"),
 ("ternary_chain", "X when: 1 < c.a < 9 => { c.v = c.cond ? c.x + 1 : c.y * 2; }"),
 ("aggregates",    "X => { c.q = 1; }\nB : behavior has: {\n"
                   "    buffer: list;\n    scores: dict;\n"
                   "    point: struct { x; y; };\n} { E => F; }"),
 ("documented",    '"""Watches the motor and shuts down on overheat."""\n'
                   'guard : behavior(threshold = 90.0) { hot => shutdown; }'),
 ("strings_in",   'X when: e.tag == "sensor_7" => { c.hit = 1.0; }\n'
                   'Y when: e.v in c.items => f;\n'
                   'Z when: e.v not in c.items and "ens" in c.tag => g;'),
 ("work_def",     "divide : work(knows: x, y\n"
                   "               gives: q\n"
                   "               signals: by_zero)\n"
                   "{ q = x / y else: { div_by_zero => exit: by_zero; } give: }"),
 ("work_spec",    "on_event : work(knows: ev gives: consumed signals: failed(m))"),
 ("clockwork_def", "line_reader : clockwork(takes: f\n"
                   "                        ticks: line\n"
                   "                        signals: io_error(code))\n"
                   "{ tick: give: }"),
 ("class_def",    "sprite : class is: entity\n"
                   "  has:   { pos: vec2; tex: gpu_texture; }\n"
                   "  knows: { atlas: texture_atlas; }\n"
                   "{\n"
                   "  make : work(knows: skin gives: s : sprite signals: no_texture(path))\n"
                   "  { s = 1; give: }\n"
                   "  free : work(takes: s : sprite signals: free_failed(code))\n"
                   "  { give: }\n"
                   "}"),
 ("aware_forms",  "E => { b.x = f(1) else: { bad(r) => { b.x = r; } => ; }\n"
                   "       for: v from: give src(3) { b.y = v; } else: { worn => ; } }"),
 ("label_two_accounts",
                   "w : work(knows: v gives: r signals: snag) {\n"
                   "    dropto: done;\n"
                   "    :cleanup:\n"
                   "    r = 0;\n"
                   "    :done:\n"
                   "    give:\n"
                   "    :failures: => {\n"
                   "        exit: snag;\n"
                   "    }\n"
                   "}"),
 ("explicit_destruct",
                   "tunnel : class has: { fd: float; } { from : work }\n"
                   "+tunnel.from : work(knows: host gives: t : tunnel signals: refused)\n"
                   "{ t = host; give: }\n"
                   "-tunnel() : work(takes: t : tunnel signals: busy(when))\n"
                   "{ give: }\n"
                   "shutdown : work(knows: t gives: done) {\n"
                   "    destruct: t else: { busy(when) => ; }\n"
                   "    done = 1;\n"
                   "    give:\n"
                   "}"),
 ("semi_and_completions",
                   "pair : class has: { lo: float; } {\n"
                   "    make #{a, b -> the ordered pair} : work\n"
                   "}\n"
                   "+pair.make : work(knows: a, b gives: p : pair signals: disorder)\n"
                   "{ p = a; give: }\n"
                   "-pair : work(takes: p : pair signals: never_fails)\n"
                   "{ exit: never_fails; give: }"),
 ("aspect_panel",  "Poller : aspect(knows: rate, retries = 3\n"
                   "                signals: overrun, sensor_lost(port))\n"
                   "{\n"
                   "    IDLE : behavior { go => RUN; }\n"
                   "    RUN  : behavior { stop => IDLE; }\n"
                   "}"),
 ("namespaced_ref", "physics.tick_event => physics.apply_gravity;"),
]


def banner(label):
    """RETURN: None, always. Prints a section heading for the label 'label'."""
    print()
    print("--- %s ---" % label)


def render(node, indent=0):
    """RETURN: None, always. Prints a deterministic structural dump of the
              TYPED AST rooted at 'node', one line per product, indented by
              depth.

    Product lines carry the node's class name and its scalar fields inline
    (op texts, kinds, names as segments); child products recurse beneath.
    Leaves print their class, segments/text, and constant kind; NodeAbsent
    prints as-is (the typed absence, A-13); a NodeList shows its length. What
    this locks is the PRODUCT shape the factories build -- a factory reading
    the wrong slot, dropping a guard, or mis-routing an OR branch changes
    these lines even when parsing still "succeeds".
    """
    from dataclasses import fields, is_dataclass
    from vut.engine.temporal_logic.core.symbol.ast import (
            NodeList, Leaf, ConstantLeaf, ReferenceLeaf, DeclarationLeaf)
    from vut.engine.temporal_logic.core.parser_generator.cst_nodes import (
            NodeAbsent)
    pad = "  " * indent
    if node is NodeAbsent:
        print("%sNodeAbsent" % pad)
    elif isinstance(node, NodeList):
        print("%sNodeList [%d]" % (pad, len(node)))
        for it in node:
            render(it, indent + 1)
    elif isinstance(node, ConstantLeaf):
        print("%sConstantLeaf %s %r" % (pad, node.kind, node.text))
    elif isinstance(node, (ReferenceLeaf, DeclarationLeaf)):
        print("%s%s %s" % (pad, type(node).__name__, ".".join(node.segments)))
    elif is_dataclass(node) and not isinstance(node, Leaf):
        scalars, children = [], []
        for f in fields(node):
            v = getattr(node, f.name)
            if isinstance(v, (str, int, bool)):
                scalars.append("%s=%r" % (f.name, v))
            else:
                children.append((f.name, v))
        print("%s%s%s" % (pad, type(node).__name__,
                          " " + " ".join(scalars) if scalars else ""))
        for name, v in children:
            print("%s  .%s:" % (pad, name))
            render(v, indent + 2)
    else:
        print("%s%r" % (pad, node))


def run_compile():
    """RETURN: None, always. Shows the grammar compiles clean and its inventory.

    Reaching this line at all means neither load-time gate raised: an LL(2)
    conflict or a role-vocabulary violation would have aborted compiled_grammar()
    before any output. The rule count, start symbol, and sorted rule names are
    printed so a rule added or dropped is a visible diff.
    """
    g = compiled_grammar()
    banner("load-time gates")
    print("compiled: no LL(2) conflict; role uniqueness, AST-map coverage "
          "and AST-map kind gates passed (D-10)")
    print("start symbol:", g.start)
    print("rule count:", len(g.rules))
    banner("rule inventory (flattened, sorted)")
    for name in sorted(g.rules):
        print("  ", name)


def run_constructs():
    """RETURN: None, always. Parses one snippet per construct; reports each.

    A construct's line reads OK when its snippet parsed with zero diagnostics;
    otherwise ERR with the recorded diagnostics beneath it. The whole language
    surface is covered, so a grammar edit that breaks any single construct is
    localised to its line.
    """
    banner("construct parse coverage")
    for name, src in SNIPPETS:
        reporter = DiagnosticReporter()
        node = parse(src, reporter)
        ok = (node is not None and len(reporter.errors) == 0)
        print("%-16s %s" % (name, "OK" if ok else "ERR"))
        if not ok:
            for d in reporter.errors:
                print("      ", d.message)


def run_ast_shape():
    """RETURN: None, always. Renders the typed AST of two canonical snippets.

    Locks the ACTUAL product tree the factories build for a minimal causality
    and a guarded causality -- product classes, scalar fields, leaf segments,
    typed absences -- so a silent change in factory wiring (a wrong slot, a
    dropped guard, a mis-routed branch) is caught even when parsing still
    "succeeds".
    """
    for label, src in [("minimal causality", "button_pressed => light_on;"),
                       ("guarded causality",
                        "MOTOR_ON when: c.fuel == 0 => stop;")]:
        banner(label)
        print("source:", repr(src))
        reporter = DiagnosticReporter()
        node = parse(src, reporter)
        render(node)
        if reporter.errors:
            for d in reporter.errors:
                print("  DIAG:", d.message)


HwutRunner(
    argv       = sys.argv,
    title      = "Reactive-Engine Rule Language",
    choice_map = {
        "compile":    run_compile,
        "constructs": run_constructs,
        "ast_shape":  run_ast_shape,
    },
).run()
