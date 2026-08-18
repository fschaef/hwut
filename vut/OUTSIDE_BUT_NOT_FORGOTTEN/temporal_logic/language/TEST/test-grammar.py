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
 ("causality",     "R : reactor { B : behavior { button_pressed => light_on; } }"),
 ("guarded",       "R : reactor { fuel: float; B : behavior {\n"
                   "    MOTOR_ON when: .fuel == 0 => lighten_fuel_missing;\n} }"),
 ("def_cause",     "OPERATION_IMPOSSIBLE : cause(fuel_limit, battery_limit)\n"
                   "    MOTOR_ON when: .fuel <= fuel_limit or .battery < battery_limit;"),
 ("cause_ref",     "R : reactor { B : behavior {\n"
                   "    OPERATION_IMPOSSIBLE(0.1, 2) => SIGNAL_REFUSE_OPERATION;\n} }"),
 ("reactor_single", "ClimateControl : reactor {\n"
                   "    target: float;\n"
                   "    control : behavior {\n"
                   "        ac_button_pushed => toggle_compressor;\n"
                   "        temp_dial_turned => set_target_temperature;\n"
                   "        fan_dial_turned  => adjust_fan_speed;\n    }\n}"),
 ("shrug_effect",  "Station : reactor {\n"
                   "  Polling : behavior {\n"
                   "    ~ENTRY       => poll_sensors();\n"
                   "    stop_pressed => ;\n  }\n}"),
 ("state_machine", "MotorActivity : reactor {\n"
                   "    ON : behavior {\n"
                   "         gas_pedal_push     => open_throttle;\n"
                   "         on_off_button_push =!=> OFF;\n    }\n"
                   "    OFF : behavior {\n"
                   "         gas_pedal_push     => tone_notify_engine_off;\n"
                   "         on_off_button_push =!=> ON;\n    }\n}"),
 ("mode_group",    "sprite : reactor++ {\n"
                   "    position:  vec2;\n    speed:     vec2;\n"
                   "    move : behavior { tickle => wiggle; }\n"
                   "    draw : behavior { frame => blit; }\n}"),
 ("namespace",     "open: graphics.sprites {\n"
                   "    sprite : reactor { position: vec2;\n"
                   "        idle : behavior { poke => wake; } }\n}"),
 ("import",        'import: "lib/physics.vut" as: physics'),
 ("command_block", "Car : reactor { fuel: float; warn: bool; reserve: bool;\n"
                   "  cylinders: float; checks: float;\n"
                   "  drive : behavior { TRAVELLED_100KM => {\n"
                   "    .fuel -= 8.31;\n"
                   "    if: .fuel < 5.0   { .warn = true; }\n"
                   "    elif: .fuel < 20.0 { .warn = false; }\n"
                   "    else:               { .reserve = false; }\n"
                   "    int: i = 1 .. .cylinders { .checks += i; }\n} } }"),
 ("match",         "R : reactor { state: float; a: float; b: float; g: float; d: float;\n"
                   "  B : behavior { X => {\n    match: .state {\n"
                   "        case: 3 { .a = 1; }\n"
                   "        case: 1 to: 5 { .b = 2; }\n"
                   '        case: "ab*" { .g = 3; }\n'
                   "        case: _ { .d = 4; }\n    }\n} } }"),
 ("for_loop",      "R : reactor { items: list; sum: float;\n"
                   "  B : behavior { X => { for: v in: .items { .sum += v; } } } }"),
 ("enumeration",   "R : reactor { items: list; sum: float;\n"
                   "  B : behavior { X => { int: i with: x from: .items start: 2"
                   " { .sum += i * x; } } } }"),
 ("exit_region",   "R : reactor { h: float; g: float; released_a: float; status: float;\n"
                   "  B : behavior { SOMETHING => {\n"
                   "    .h = acquire_a();\n"
                   "    if: not .h.ok  { dropto fail; }\n"
                   "    .g = acquire_b();\n"
                   "    if: not .g.ok  { dropto free_a; }\n"
                   "    dropto done;\n"
                   "  :free_a:   .released_a = release_a(.h);\n"
                   "  :fail:     .status = FAILED;\n"
                   "  :done:\n} } }"),
 ("comprehension", "R : reactor { pp: list; pos: list; mix: list; nest: list;\n"
                   "  B : behavior { X => { .pp = [ x*y   with: x, y from: pairs ];\n"
                   "        .pos = [ x with: x from: xs if: x > 0 ];\n"
                   "        .mix = [ x + y with: x from: xs if: x > 0\n"
                   "                        with: y from: ys ];\n"
                   "        .nest = [ [ a*b with: b from: row ] with: row from: matrix ]; } } }"),
 ("data_access",   "R : reactor { buf: list; f: float; z: float;\n"
                   "  B : behavior { X => { .buf[i] = v; .f = grid[i][j]; .z = f(x)[0]; } } }"),
 ("ternary_chain", "R : reactor { a: float; v: float; cond: bool; x: float; y: float;\n"
                   "  B : behavior { X when: 1 < .a < 9 => { .v = .cond ? .x + 1 : .y * 2; } } }"),
 ("aggregates",    "R : reactor {\n"
                   "    buffer: list;\n    scores: dict;\n"
                   "    point: struct { x; y; };\n    q: float;\n"
                   "    B : behavior { X => { .q = 1; }\n    E => F;\n}\n}"),
 ("documented",    '"""Watches the motor and shuts down on overheat."""\n'
                   'guard : reactor { threshold: float;\n'
                   '  watch : behavior { hot => shutdown; } }'),
 ("strings_in",   'R : reactor { hit: float; items: list; tag: string;\n'
                   '  B : behavior {\n'
                   '    X when: e.tag == "sensor_7" => { .hit = 1.0; }\n'
                   "    Y when: e.v in .items => f;\n"
                   '    Z when: e.v not in .items and "ens" in .tag => g;\n} }'),
 ("work_def",     "divide : work(in: x, y\n"
                   "               out: q\n"
                   "               signals: by_zero)\n"
                   "{ q = x / y else: { div_by_zero => signal by_zero; } give q; }"),
 ("work_spec",    "on_event : work(in: known: ev out: consumed signals: failed(m))"),
 ("clockwork_def", "line_reader : clockwork(in: f\n"
                   "                        out: line\n"
                   "                        signals: io_error(code))\n"
                   "{ tick; signal; }"),
 ("physical",      "speed : physical[m/s];\n"
                   "force : physical[kg*m/s^2];\n"
                   "dens  : physical[kg m^-3];\n"
                   "area  : physical[m\u00b2];\n"
                   "root  : physical[m^(1/2)];\n"
                   "power_use : work(in: t out: p : physical[W]) {\n"
                   "    p = 3.14 [kg*m\u00b2/s\u00b3];\n"
                   "    q = 9.81 [m/s^2];\n"
                   "    give p;\n}"),
 ("three_arrows",  "lamp : reactor(in: cmd out: note) {\n"
                   "  RED   : behavior { cmd: { go => blink to note =!=> GREEN;\n"
                   "                            hush => ; } }\n"
                   "  GREEN : behavior { cmd: { go =!=> RED; } }\n}"),
 ("event_def",     "blink : event(v, kind);\n"
                   "heartbeat : event();"),
 ("signal_routed", "R : reactor(in: cmd out: note) { n: float;\n"
                   "  B : behavior { go => { .n += 1; signal blink(v = .n) to note;\n"
                   "                         signal fanned; } } }"),
 ("panel_flat",   "bundle : work(in: raw : cloud, known: eps : float = 0.5\n"
                   "              out: center : point2d, known: rotation : mat2\n"
                   "              signals: no_convergence(residual: float))\n"
                   "{ center = raw; rotation = eps; give center, rotation; }"),
 ("class_def",    "sprite : class is: entity\n"
                   "{\n"
                   "  pos: vec2;\n"
                   "  known: atlas: texture_atlas;\n"
                   "  make : work(in: skin out: s : sprite signals: no_texture(path))\n"
                   "  { s = 1; give s; }\n"
                   "  had: tex: gpu_texture;\n"
                   "  free : work(in: s : sprite signals: free_failed(code))\n"
                   "  { give; }\n"
                   "}"),
 ("param_marking", "hot : cause(known: threshold) t_high when: e.v > threshold;"),
 ("self_binding",  "counter : reactor { n: float;\n"
                   "  step : work(in: d out: done) { .n = .n + d; done = 1; give done; }\n"
                   "  tick_b : behavior { bump => { .n = .n + 1; } }\n}"),
 ("float_exponent", "w : work(in: a, known: eps = 1e-6 out: q)\n"
                   "{ q = a * 2.5e3 + 1E+10; give q; }"),
 ("site_marking", "W : work(in: a out: m) {\n"
                   "    known: entry = db.get(1);\n"
                   "    known: m = a.b.c;\n"
                   "    x, known: r = bundle(1, 2);\n"
                   "    give m;\n}"),
 ("aware_forms",  "R : reactor { x: float; y: float;\n"
                   "  B : behavior { E => { .x = f(1) else: { bad when: e.r > 0 => { .x = e.r; } ~ANY => ; }\n"
                   "       for: v from: src(3) { .y = v; } else: { worn => ; } } } }"),
 ("label_two_accounts",
                   "w : work(in: v out: r signals: snag) {\n"
                   "    dropto done;\n"
                   "    :cleanup:\n"
                   "    r = 0;\n"
                   "    :done:\n"
                   "    give r;\n"
                   "    :failures: => {\n"
                   "        signal snag;\n"
                   "    }\n"
                   "}"),
 ("explicit_destruct",
                   "tunnel : class { fd: float; from : work }\n"
                   "+tunnel.from : work(in: host out: t : tunnel signals: refused)\n"
                   "{ t = host; give t; }\n"
                   "-tunnel() : work(in: t : tunnel signals: busy(when))\n"
                   "{ give; }\n"
                   "shutdown : work(in: t out: done) {\n"
                   "    destruct t else: { busy => ; }\n"
                   "    done = 1;\n"
                   "    give done;\n"
                   "}"),
 ("semi_and_completions",
                   "pair : class { lo: float;\n"
                   "    make #{a, b -> the ordered pair} : work\n"
                   "}\n"
                   "+pair.make : work(in: a, b out: p : pair signals: disorder)\n"
                   "{ p = a; give p; }\n"
                   "-pair : work(in: p : pair signals: never_fails)\n"
                   "{ signal never_fails; give; }"),
 ("reactor_inherit", "Base : reactor { speed: float;\n"
                   "    idle : behavior { go => run; } }\n"
                   "Rover : reactor is: Base { gain: float;\n"
                   "    drive : behavior { MOTOR_ON => go_fast; } }"),
 ("namespaced_ref", "R : reactor { v: float;\n"
                   "  B : behavior { E => { .v = physics.motors.rpm_limit; } } }"),
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
