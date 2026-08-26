#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the pype line-matching language.

CHOICES: patterns, modes, namespace, default_mode, inheritance, multi_inheritance, else_flush, anchors_repeat, boundaries_stack, if_cause, imports, compat, errors, pipe, examples, generate;

DESCRIPTION:

pype triggers Python actions on input lines that match handler patterns.

    patterns    constant strings, <number>, <int>, <"GLOB">,
                named and unnamed; first-match dispatch; non-matching
                lines pass silently.
    modes       <entry>/<exit> handlers; 'goto' switch (arrow form and
                'mode()' call form); 'and:' continuation blocks.
    default_mode  bare 'on:' handlers form the nameless default mode;
                it is the start mode and cannot be re-entered.
    inheritance 'LEFT is: RIGHT' hands RIGHT's handlers to LEFT
                transitively; SHADOWING IS FORBIDDEN -- intersecting
                patterns are an error wherever they come from;
                '=> ignore;' consumes a line without effect; cycles
                and unknown bases are rejected.
    multi_inheritance  'LEFT is: B1, B2' receives handlers of all
                bases; diamond duplicates enter once; ANY two distinct
                pattern handlers of one effective list with
                INTERSECTING languages are a hard error -- no
                settlement, no shadowing.
    else_flush  'MODE/on: <else>'/'else:' fires when every match handler of
                the active mode failed; '=> flush;' emits the line
                unchanged; 'on: <else> => flush;' is the pass-through-filter
                idiom; <else> is the one shadowable handler, own
                before inherited, first of the effective list;
                'FLUSH' is reserved.
    anchors_repeat  '<bol>'/'<eol>' anchors; '+( i : ... )' repeat
                groups (one or more) with counter, indexed dictionary
                bindings and '[i +/- n]' offset expressions; the
                mandatory-else law with its mixin exemption and
                activation-time check.
    boundaries_stack  <bof>/<eof> file boundary handlers; PUSH/POP mode
                stack with return into the default mode; 'line_n' and
                'time_sec'; the --dry-run option.
    namespace   all blocks share one namespace; bindings and 'line'
                are visible across handlers and modes.
    errors      parse errors report file and line; unknown mode names
                are rejected.
    pipe        a she-bang script run as an OS-level pipe filter.
    examples    every script in examples/ run against its matching
                input file; the recorded output doubles as the
                reference output of the manual's example section.
    generate    'hwut.pype --example SCRIPT' generates an example
                input; the generated input is fed back into the
                script (round trip); pure-IGNORE handlers and modes
                reachable only via 'mode()' calls are skipped by the
                static walk.
______________________________________________________________________________
"""
import io
import os
import subprocess
import textwrap
import sys
import config                                                       # noqa: F401

from   vut.language_support.python.hwut_runner  import HwutRunner
from   vut.language_support.python.script_runner import CRunScript
from   vut.engine.hwut_pype.hwut_pype          import parse, Interpreter, PypeError, generate_example_input


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def run_script(script_txt, input_txt):
    """RETURN: None. Parses 'script_txt', feeds 'input_txt' line-wise, and
                     prints script and input beforehand so the GOOD file is
                     self-describing.
    """
    script_txt = textwrap.dedent(script_txt).strip("\n")
    input_txt  = textwrap.dedent(input_txt).strip("\n")
    print("SCRIPT: {")
    for line in script_txt.splitlines(): print("    " + line)
    print("}")
    print("INPUT: {")
    for line in input_txt.splitlines():  print("    " + line)
    print("}")
    print("OUTPUT: {")
    mode_db, first = parse(script_txt, "<test>")
    Interpreter(mode_db, first).run(io.StringIO(input_txt))
    print("}")


def run_patterns():
    """RETURN: None. Every pattern token kind; first-match dispatch."""
    banner("constants, number, int, glob; named and unnamed")
    run_script(
        """
        M/on: "value" <x = number> => {
            print("number ->", repr(x))
        }
        M/on: "count" <k = int> => {
            print("int    ->", repr(k))
        }
        M/on: "file" <f = "*.txt"> => {
            print("glob   ->", repr(f))
        }
        M/on: "flag" <int> => {
            print("unnamed int matched; line:", pype.line())
        }
        M/on: <else> => ignore;
        """,
        """
        value -3.25
        count 42
        file report.txt
        flag 7
        this line matches nothing
        """)

    banner("glob character classes: '[seq]', '[!seq]', ranges")
    run_script(
        """
        on: "f" <name = "log[0-9].txt"> => {
            print("numbered log:", name)
        }
        on: "g" <word = "[!p]*"> => {
            print("not p-initial:", word)
        }
        on: <else> => {
            print("rejected: %r" % pype.line())
        }
        """,
        """
        f log7.txt
        f logX.txt
        g quiet
        g pond
        """)

    banner("class edge law: leading ']' literal; unclosed '[' literal")
    run_script(
        """
        on: <x = "[]]end"> => {
            print("leading ] literal:", x)
        }
        on: <y = "a[b"> => {
            print("unclosed [ literal:", y)
        }
        on: <else> => ignore;
        """,
        """
        ]end
        a[b
        """)

    banner("first-match dispatch: earlier handler wins")
    run_script(
        """
        M/on: "abc" => {
            print("first")
        }
        M/on: "abc" "def" => {
            print("second (never reached for 'abc def')")
        }
        M/on: <else> => ignore;
        """,
        """
        abc def
        """)


def run_modes():
    """RETURN: None. <entry>/<exit>, arrow switch, pype.goto() call, 'and:' chain."""
    banner("arrow switch with <entry>/<exit>")
    run_script(
        """
        A/on: <entry> => {
            print("A begin")
        }
        A/on: "go" => goto B;
        A/on: <exit> => {
            print("A end")
        }
        B/on: <entry> => {
            print("B begin")
        }
        B/on: "back" => {
            print("returning via mode() call")
            pype.goto("A")
        }
        B/on: <exit> => {
            print("B end")
        }
        A/on: <else> => ignore;
        B/on: <else> => ignore;
        """,
        """
        go
        ignored while in B
        back
        """)

    banner("'and:' continuation: block then switch")
    run_script(
        """
        A/on: "x" => {
            print("block one")
        }
        and: {
            print("block two")
        }
        and: goto B;
        B/on: <entry> => {
            print("now in B")
        }
        A/on: <else> => ignore;
        B/on: <else> => ignore;
        """,
        """
        x
        """)


def run_namespace():
    """RETURN: None. One namespace across handlers and modes."""
    banner("counter survives handlers and mode switches")
    run_script(
        """
        A/on: <entry> => {
            n = 0
        }
        A/on: "tick" => {
            n += 1
            print("A tick, n =", n)
        }
        A/on: "over" => goto B;
        B/on: "tick" => {
            n += 1
            print("B tick, n =", n)
        }
        A/on: <else> => ignore;
        B/on: <else> => ignore;
        """,
        """
        tick
        tick
        over
        tick
        """)


def run_default_mode():
    """RETURN: None. Bare 'on:' handlers form the nameless default mode."""
    banner("default mode starts; leaving it is one-way")
    run_script(
        """
        on: <entry> => {
            print("default begin")
        }
        on: "tick" => {
            print("default tick")
        }
        on: "leave" => goto NAMED;
        on: <exit> => {
            print("default end")
        }
        NAMED/on: "tick" => {
            print("NAMED tick")
        }
        on: <else> => ignore;
        NAMED/on: <else> => ignore;
        """,
        """
        tick
        leave
        tick
        """)

    banner("default mode precedes named modes as start mode")
    run_script(
        """
        NAMED/on: "x" => {
            print("NAMED (not active at start)")
        }
        on: "x" => {
            print("default handles it")
        }
        on: <else> => ignore;
        """,
        """
        x
        """)

    banner("no way back: mode('<default>') rejected")
    try:
        mode_db, first = parse(
            'on: "go" => goto NAMED;\n'
            'on: <else> => ignore;\n'
            'NAMED/on: "back" => {\n'
            '    pype.goto("<default>")\n'
            '}\n'
            'NAMED/on: <else> => ignore;\n', "<test>")
        Interpreter(mode_db, first).run(io.StringIO("go\nback\n"))
        print("UNEXPECTED: run returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)


def run_inheritance():
    """RETURN: None. 'LEFT is: RIGHT' hands RIGHT's handlers to LEFT;
                     '=> ignore;' consumes a line without effect.
    """
    banner("inherited match and <entry>/<exit> handlers")
    run_script(
        """
        BASE/on: <entry> => {
            print("BASE begin")
        }
        BASE/on: "common" => {
            print("BASE handles 'common'")
        }
        BASE/on: <exit> => {
            print("BASE end")
        }
        BASE/on: <else> => ignore;
        SUB is: BASE
        SUB/on: "extra" => {
            print("SUB handles 'extra'")
        }
        on: "go" => goto SUB;
        on: <else> => ignore;
        """,
        """
        go
        common
        extra
        """)

    banner("shadowing is forbidden: own against inherited")
    try:
        parse('BASE/on: "x" => ignore;\n'
              'BASE/on: <else> => ignore;\n'
              'SUB is: BASE\n'
              'SUB/on: "x" => flush;\n'
              'on: "go" => goto SUB;\n'
              'on: <else> => ignore;\n', "<test>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)

    banner("shadowing is forbidden: own against own")
    try:
        parse('on: <n = int> => ignore;\n'
              'on: <x = number> => ignore;\n'
              'on: <else> => ignore;\n', "<test>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)

    banner("disjoint vocabularies inherit cleanly; no shadowing needed")
    run_script(
        """
        BASE/on: "data" <n = int> => {
            print("BASE data", n)
        }
        BASE/on: <else> => ignore;
        SUB is: BASE
        SUB/on: "extra" => {
            print("SUB extra")
        }
        on: "go" => goto SUB;
        on: <else> => ignore;
        """,
        """
        go
        data 7
        extra
        """)

    banner("transitive inheritance: C is: B is: A")
    run_script(
        """
        A/on: "a" => {
            print("from A")
        }
        A/on: <else> => ignore;
        B is: A
        B/on: "b" => {
            print("from B")
        }
        C is: B
        on: "go" => goto C;
        on: <else> => ignore;
        """,
        """
        go
        a
        b
        """)

    banner("inheritance cycle rejected")
    try:
        parse("A is: B\nB is: A\nA/on: \"x\" => ignore;\n", "<test>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)

    banner("unknown base rejected")
    try:
        parse("A is: GHOST\nA/on: \"x\" => ignore;\n", "<test>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)

    banner("IGNORE reserved as mode name")
    try:
        parse('IGNORE/on: "x" => { }\n', "<test>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)
    try:
        parse('A is: IGNORE\n', "<test>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)


def run_multi_inheritance():
    """RETURN: None. Comma-separated base lists; diamond deduplication;
                     interference (intersecting inherited patterns) is a
                     hard error.
    """
    banner("two bases: handlers of both received")
    run_script(
        """
        NUM/on: "n" <x = int> => {
            print("NUM:", x)
        }
        TXT/on: "t" <s = "*"> => {
            print("TXT:", s)
        }
        SUB is: NUM, TXT
        SUB/on: <else> => ignore;
        on: "go" => goto SUB;
        on: <else> => ignore;
        """,
        """
        go
        n 5
        t hello
        """)

    banner("diamond: shared root handler enters once, no interference")
    run_script(
        """
        ROOT/on: "r" => {
            print("ROOT handler")
        }
        LEFT is: ROOT
        LEFT/on: "l" => {
            print("LEFT handler")
        }
        RIGHT is: ROOT
        RIGHT/on: "q" => {
            print("RIGHT handler")
        }
        ROOT/on: <else> => ignore;
        SUB is: LEFT, RIGHT
        on: "go" => goto SUB;
        on: <else> => ignore;
        """,
        """
        go
        r
        l
        q
        """)

    banner("interference: equal patterns across two bases (trivial intersection)")
    try:
        parse('B1/on: "x" => {\n'
              '    print("B1")\n'
              '}\n'
              'B2/on: "x" => {\n'
              '    print("B2")\n'
              '}\n'
              'SUB is: B1, B2\n', "<test>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)

    banner("own override does not cure base interference")
    try:
        parse('B1/on: "x" => ignore;\n'
              'B2/on: "x" => ignore;\n'
              'SUB is: B1, B2\n'
              'SUB/on: "x" => ignore;\n', "<test>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)

    banner("interference across depth: base and base-of-base")
    try:
        parse('ROOT/on: "x" => ignore;\n'
              'MID is: ROOT\n'
              'OTHER/on: "x" => ignore;\n'
              'SUB is: MID, OTHER\n', "<test>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)

    banner("intersection, not identity: <int> against <number>")
    try:
        parse('B1/on: "v" <n = int> => ignore;\n'
              'B2/on: "v" <x = number> => ignore;\n'
              'SUB is: B1, B2\n', "<test>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)

    banner("intersection of globs: *.txt against *")
    try:
        parse('B1/on: <f = "*.txt"> => ignore;\n'
              'B2/on: <s = "*"> => ignore;\n'
              'SUB is: B1, B2\n', "<test>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)

    banner("disjoint languages are lawful across bases")
    run_script(
        """
        B1/on: <f = "*.txt"> => {
            print("txt file:", f)
        }
        B2/on: <g = "*.log"> => {
            print("log file:", g)
        }
        B3/on: "abc" "def" => {
            print("two-token constant, disjoint from both globs")
        }
        SUB is: B1, B2, B3
        SUB/on: <else> => ignore;
        on: "go" => goto SUB;
        on: <else> => ignore;
        """,
        """
        go
        report.txt
        trace.log
        abc def
        """)

    banner("interference decides glob classes exactly")
    try:
        parse('B1/on: <"[abc]"> => ignore;\n'
              'B2/on: "b" => ignore;\n'
              'SUB is: B1, B2\n'
              'SUB/on: <else> => ignore;\n', "<test>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)
    mode_db, first = parse(
        'on: "go" => goto SUB;\non: <else> => ignore;\n'
        'B1/on: <"[abc]"> => ignore;\n'
        'B2/on: "d" => ignore;\n'
        'SUB is: B1, B2\n'
        'SUB/on: <else> => ignore;\n', "<test>")
    print("disjoint classes lawful: '[abc]' vs 'd'")

    banner("effect-command words in a base list: plain unknown-mode law")
    try:
        parse('A/on: "x" => ignore;\n'
              'SUB is: A, IGNORE\n', "<test>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)


def _run_pipe_file_inputs():
    """RETURN: None. INPUT-FILE arguments after SCRIPT: files read in
                     order as one stream; trace positions name the file.
    """
    interpreter_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..",
                     "bin", "hwut.pype"))
    work_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "tmp-file-input-work")
    os.makedirs(work_dir, exist_ok=True)
    try:
        script_path = os.path.join(work_dir, "filter.pype")
        with open(script_path, "w") as fh:
            fh.write('on: "x" => flush;\non: <else> => ignore;\n')
        a_path = os.path.join(work_dir, "in-a.txt")
        b_path = os.path.join(work_dir, "in-b.txt")
        with open(a_path, "w") as fh: fh.write("l1 x\nl2\n")
        with open(b_path, "w") as fh: fh.write("l3 x\n")

        banner("two input files read in order as one stream")
        result = subprocess.run(
            ["python3", interpreter_path, script_path, a_path, b_path],
            capture_output=True, text=True)
        print("EXIT:", result.returncode)
        for line in result.stdout.splitlines(): print("    " + line)

        banner("trace positions name the input file, per-file line count")
        result = subprocess.run(
            ["python3", interpreter_path, "--trace",
             script_path, a_path, b_path],
            capture_output=True, text=True)
        for line in result.stderr.splitlines():
            print("    " + line.replace(work_dir + os.sep, ""))
    finally:
        import shutil
        shutil.rmtree(work_dir, ignore_errors=True)


def run_examples():
    """RETURN: None. Runs every script in examples/ against its matching
                     input file through the she-bang interpreter; prints
                     input and output verbatim.
    """
    example_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "examples"))
    interpreter = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..",
                     "bin", "hwut.pype"))
    for stem in ("01-test-report", "02-build-phases", "03-sensor-watch",
                 "04-log-router", "05-service-discovery"):
        banner(stem)
        script_path = os.path.join(example_dir, stem + ".pype")
        input_path  = os.path.join(example_dir, stem + ".txt")
        with open(input_path) as fh:
            input_txt = fh.read()
        print("INPUT: {")
        for line in input_txt.splitlines(): print("    " + line)
        print("}")
        result = subprocess.run(
            ["python3", interpreter, script_path],
            input          = input_txt,
            capture_output = True, text = True)
        print("EXIT:", result.returncode)
        print("OUTPUT: {")
        for line in result.stdout.splitlines(): print("    " + line)
        print("}")
        if result.stderr:
            print("STDERR: {")
            for line in result.stderr.splitlines(): print("    " + line)
            print("}")


def run_generate():
    """RETURN: None. 'hwut.pype --example SCRIPT' prints a generated
                     example input; feeding it back into the script is
                     the round trip.
    """
    example_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "examples"))
    interpreter = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..",
                     "bin", "hwut.pype"))
    for stem in ("01-test-report", "02-build-phases", "03-sensor-watch",
                 "04-log-router", "05-service-discovery"):
        banner(stem)
        script_path = os.path.join(example_dir, stem + ".pype")
        generated = subprocess.run(
            ["python3", interpreter, "--example", script_path],
            capture_output = True, text = True)
        print("GENERATED (exit %d): {" % generated.returncode)
        for line in generated.stdout.splitlines(): print("    " + line)
        print("}")
        round_trip = subprocess.run(
            ["python3", interpreter, script_path],
            input          = generated.stdout,
            capture_output = True, text = True)
        print("ROUND TRIP (exit %d): {" % round_trip.returncode)
        for line in round_trip.stdout.splitlines(): print("    " + line)
        print("}")
        if generated.stderr or round_trip.stderr:
            print("STDERR: {")
            for line in (generated.stderr + round_trip.stderr).splitlines():
                print("    " + line)
            print("}")

    banner("walk skips pure-IGNORE handlers and mode()-only switches")
    mode_db, first = parse(
        'on: "visible" <n = int> => {\n'
        '    print(n)\n'
        '}\n'
        'on: "silent" => ignore;\n'
        'on: "go" => goto NAMED;\n'
        'on: <else> => ignore;\n'
        'NAMED/on: "deep" <f = "*.log"> => {\n'
        '    print(f)\n'
        '}\n'
        'NAMED/on: "hidden" => {\n'
        '    pype.goto("UNSEEN")\n'
        '}\n'
        'NAMED/on: <else> => ignore;\n'
        'UNSEEN/on: "never sampled" => {\n'
        '    print("unreachable to the static walk")\n'
        '}\n', "<test>")
    for line in generate_example_input(mode_db, first):
        print(line)


def run_else_flush():
    """RETURN: None. 'on: <else>' fires when every match handler failed;
                     '=> flush;' emits the line unchanged.
    """
    banner("else fires only on unmatched lines")
    run_script(
        """
        on: "known" <n = int> => {
            print("known:", n)
        }
        on: <else> => {
            print("unmatched: %r" % pype.line())
        }
        """,
        """
        known 7
        something odd
        known 8
        """)

    banner("pass-through filter: transform known lines, FLUSH the rest")
    run_script(
        """
        on: "T =" <t = number> "C" => {
            print("T = %.1f F" % (t * 9 / 5 + 32))
        }
        on: <else> => flush;
        """,
        """
        # header kept verbatim
        T = 100.0 C
        T = 0.0 C
        trailer kept verbatim
        """)

    banner("FLUSH on a match handler, chained after a block")
    run_script(
        """
        on: "ERROR" => {
            error_n = error_n + 1 if 'error_n' in dir() else 1
            print(">> error number %d:" % error_n)
        }
        and: flush;
        on: <else> => ignore;
        """,
        """
        ERROR disk full
        fine line
        ERROR again
        """)

    banner("<else> is the one shadowable handler: own before inherited")
    run_script(
        """
        BASE/on: <else> => {
            print("BASE else: %r" % pype.line())
        }
        BASE/on: "b" => ignore;
        STRICT is: BASE
        STRICT/on: "ok" => {
            print("STRICT ok")
        }
        STRICT/on: <else> => {
            print("STRICT else (shadows BASE): %r" % pype.line())
        }
        on: "go" => goto STRICT;
        on: <else> => ignore;
        """,
        """
        go
        ok
        mystery
        """)

    banner("one inherited <else> serves the whole hierarchy")
    run_script(
        """
        BASE/on: <else> => {
            print("BASE else: %r" % pype.line())
        }
        is: BASE
        on: "go" => goto STRICT;
        STRICT is: BASE
        STRICT/on: "ok" => {
            print("STRICT ok")
        }
        """,
        """
        mystery in default
        go
        ok
        mystery in STRICT
        """)

    banner("two inherited <else>: first base of the list wins")
    run_script(
        """
        B1/on: <else> => {
            print("B1 else fires")
        }
        B2/on: <else> => ignore;
        SUB is: B1, B2
        SUB/on: "x" => ignore;
        on: "go" => goto SUB;
        on: <else> => ignore;
        """,
        """
        go
        mystery
        """)

    banner("first <else> of the effective list fires: MID over ROOT")
    mode_db, first = parse('ROOT/on: <else> => flush;\n'
                           'MID is: ROOT\n'
                           'MID/on: <else> => ignore;\n'
                           'SUB is: MID\n'
                           'SUB/on: "x" => ignore;\n'
                           'on: "go" => goto SUB;\n'
                           'on: <else> => ignore;\n', "<test>")
    print("parse succeeded: SUB's effective <else> is MID's (own before "
          "inherited); ROOT's flush is shadowed")

    banner("effect-command words are lawful mode names; unknown ones err")
    mode_db, first = parse('FLUSH/on: "x" => ignore;\n'
                           'FLUSH/on: <else> => ignore;\n'
                           'on: "go" => goto FLUSH;\n'
                           'on: <else> => ignore;\n', "<test>")
    print("parse succeeded: mode 'FLUSH' defined and targeted via goto")
    try:
        mode_db, first = parse(
            'A/on: "y" => {\n    pype.goto("FLUSH")\n}\n'
            'A/on: <else> => ignore;\n', "<test>")
        Interpreter(mode_db, first).run(io.StringIO("y\n"))
        print("UNEXPECTED: run returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)


def run_anchors_repeat():
    """RETURN: None. '<bol>'/'<eol>' anchors; repeat groups with counter
                     and indexed dictionary bindings; mandatory 'else'.
    """
    banner("bol distinguishes line-start from mid-line")
    run_script(
        """
        M/on: <bol> "#" => {
            print("comment line")
        }
        M/on: <else> => {
            print("no line-start hash: %r" % pype.line())
        }
        """,
        """
        # starts here
        value # trailing
        """)

    banner("anchors are transparent to interference: languages decide")
    try:
        parse('M/on: <bol> "#" => ignore;\n'
              'M/on: "#" => ignore;\n'
              'M/on: <else> => ignore;\n', "<test>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)

    banner("eol demands the pattern reaches line end")
    run_script(
        """
        M/on: "done" <eol> => {
            print("line ends in done")
        }
        M/on: <else> => {
            print("no: %r" % pype.line())
        }
        """,
        """
        all done
        done deal
        """)

    banner("repeat: one or more; counter and indexed dictionary bindings")
    run_script(
        """
        M/on: "sum" +( i : <x[i] = number> ";" ) "end" => {
            print("n =", i, "values =", [x[k] for k in sorted(x)],
                  "sum =", sum(x.values()))
        }
        M/on: <else> => {
            print("rejected: %r" % pype.line())
        }
        """,
        """
        sum 1.5 ; 2.5 ; 3.5 ; end
        sum end
        """)

    banner("offset expressions in the index brackets")
    run_script(
        """
        M/on: "pair" +( i : <a[i + 2] = int> <b[i - 1] = int> ) => {
            print("i =", i, "a =", dict(sorted(a.items())),
                  "b =", dict(sorted(b.items())))
        }
        M/on: <else> => ignore;
        """,
        """
        pair 10 11 20 21
        """)

    banner("mandatory else: activatable mode without else is an error")
    try:
        parse('M/on: "x" => ignore;\n', "<test>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)

    banner("mixin without else is exempt; activation via mode() is checked")
    try:
        mode_db, first = parse(
            'MIXIN/on: "m" => ignore;\n'
            'on: "go" => {\n    pype.goto("MIXIN")\n}\n'
            'on: <else> => ignore;\n', "<test>")
        print("parse succeeded (MIXIN is no static target)")
        Interpreter(mode_db, first).run(io.StringIO("go\n"))
        print("UNEXPECTED: run returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)

    banner("indexed binding outside a repeat group rejected")
    try:
        parse('M/on: <x[i] = number> => ignore;\nM/on: <else> => ignore;\n',
              "<test>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)

    banner("repeat groups do not nest")
    try:
        parse('M/on: +( i : +( j : <x[i] = int> ) ) '
              '=> ignore;\nM/on: <else> => ignore;\n', "<test>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)

    banner("index expressions are offsets only: '+'/'-' integers")
    try:
        parse('M/on: +( i : <x[i * 2] = int> ) => ignore;\n'
              'M/on: <else> => ignore;\n', "<test>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)
    try:
        parse('M/on: +( i : <x[j] = int> ) => ignore;\n'
              'M/on: <else> => ignore;\n', "<test>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)


def run_boundaries_stack():
    """RETURN: None. <bof>/<eof> file boundary handlers; PUSH/POP mode stack;
                     'line_n' and 'time_sec' namespace values; --dry-run.
    """
    banner("<bof> and <eof> fire once at the file boundaries")
    run_script(
        """
        on: <bof> => {
            print("<bof> at line_n", pype.line_n())
        }
        on: "x" => {
            print("x at line_n", pype.line_n())
        }
        on: <else> => ignore;
        on: <eof> => {
            print("<eof> at line_n", pype.line_n(),
                  "; pype.time() >= 0:", pype.time() >= 0.0)
        }
        """,
        """
        x
        noise
        x
        """)

    banner("PUSH suspends, POP returns; <entry>/<exit> fire on both")
    run_script(
        """
        on: <entry> => {
            print("default <entry>")
        }
        on: "dig" => push DETAIL;
        on: "x" => {
            print("default x")
        }
        on: <else> => ignore;
        DETAIL/on: <entry> => {
            print("  DETAIL <entry>")
        }
        DETAIL/on: "up" => pop;
        DETAIL/on: "x" => {
            print("  DETAIL x")
        }
        DETAIL/on: <else> => ignore;
        DETAIL/on: <exit> => {
            print("  DETAIL <exit>")
        }
        """,
        """
        x
        dig
        x
        up
        x
        """)

    banner("POP may return into the nameless default mode")
    run_script(
        """
        on: "call" => push SUB;
        on: "x" => {
            print("default x")
        }
        on: <else> => ignore;
        SUB/on: "ret" => pop;
        SUB/on: <else> => ignore;
        """,
        """
        call
        ret
        x
        """)

    banner("pop with an empty stack is a runtime error")
    try:
        mode_db, first = parse('on: "x" => pop;\non: <else> => ignore;\n', "<test>")
        Interpreter(mode_db, first).run(io.StringIO("x\n"))
        print("UNEXPECTED: run returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)

    banner("no reserved mode names: 'goto NAME;' cannot collide")
    run_script(
        """
        on: "go" => goto IGNORE;
        on: <else> => ignore;
        IGNORE/on: "x" => {
            print("a mode named IGNORE, lawfully addressed by goto")
        }
        IGNORE/on: <else> => ignore;
        """,
        """
        go
        x
        """)

    banner("malformed effects rejected: missing ';', missing argument")
    try:
        parse('on: "x" => goto B\non: <else> => ignore;\n', "<test>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)
    try:
        parse('on: "x" => push;\non: <else> => ignore;\n', "<test>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)

    banner("released: cause words and anything else are lawful mode names")
    run_script(
        """
        on: "go" => goto WHEN_THE_SUN_SHINES;
        on: <else> => ignore;
        WHEN_THE_SUN_SHINES/on: "x" => {
            print("shining")
        }
        WHEN_THE_SUN_SHINES/on: "visit" => goto ENTRY;
        WHEN_THE_SUN_SHINES/on: <else> => ignore;
        ENTRY/on: "x" => {
            print("a mode named ENTRY, lawfully")
        }
        ENTRY/on: <else> => ignore;
        """,
        """
        go
        x
        visit
        x
        """)

    banner("pype.bindings(): the current line's pattern bindings")
    run_script(
        """
        M/on: "p" +( i : <x[i] = int> ) => {
            print("bindings:", dict(sorted(pype.bindings().items())))
        }
        M/on: if ( True ) => {
            print("if fire, bindings:", pype.bindings())
        }
        M/on: <else> => ignore;
        """,
        """
        p 4 5
        anything else
        """)

    banner("--trace: gcc-style 'file:line:' diagnostics on stderr")
    interpreter_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..",
                     "bin", "hwut.pype"))
    with CRunScript(
            file_name       = "tmp-trace.pype",
            shebang         = "#!" + interpreter_path,
            script_txt_list = [
                'on: "x" <n = int> => {',
                '    print("seen", n)',
                '}',
                'and: flush;',
                'on: "go" => push DEEP;',
                'on: <else> => ignore;',
                'DEEP/on: "up" => pop;',
                'DEEP/on: <else> => ignore;',
            ],
            display_f       = False) as script_path:
        for flag, label in (("--trace", "gcc style (default)"),
                            ("--trace-plain", "plain style")):
            result = subprocess.run(
                ["python3", interpreter_path, flag,
                 os.path.abspath(script_path)],
                input          = "x 7\ngo\nmystery\nup\n",
                capture_output = True, text = True)
            print("EXIT:", result.returncode)
            print("STDOUT (the clean filter stream): {")
            for line in result.stdout.splitlines(): print("    " + line)
            print("}")
            print("TRACE, %s (stderr): {" % label)
            for line in result.stderr.splitlines():
                print("    " + line.replace(os.path.abspath(script_path),
                                            "tmp-trace.pype"))
            print("}")

    banner("--trace with mode-name filters traces only those modes")
    with CRunScript(
            file_name       = "tmp-trace-filter.pype",
            shebang         = "#!" + interpreter_path,
            script_txt_list = [
                'on: "go" => push DEEP;',
                'on: "x" => ignore;',
                'on: <else> => ignore;',
                'DEEP/on: "up" => pop;',
                'DEEP/on: <else> => ignore;',
            ],
            display_f       = False) as script_path:
        result = subprocess.run(
            ["python3", interpreter_path, "--trace", "DEEP",
             os.path.abspath(script_path)],
            input          = "x\ngo\nmystery\nup\nx\n",
            capture_output = True, text = True)
        print("TRACE, filtered to DEEP (stderr): {")
        for line in result.stderr.splitlines():
            print("    " + line.replace(os.path.abspath(script_path),
                                        "tmp-trace-filter.pype"))
        print("}")

    banner("--dry-run checks the script and reads no input")
    interpreter = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..",
                     "bin", "hwut.pype"))
    with CRunScript(
            file_name       = "tmp-dry.pype",
            shebang         = "#!" + interpreter,
            script_txt_list = [
                'on: "x" => ignore;',
                'on: <else> => ignore;',
            ],
            display_f       = False) as script_path:
        result = subprocess.run(
            ["python3", interpreter, "--dry-run",
             os.path.abspath(script_path)],
            capture_output = True, text = True)
        print("EXIT:", result.returncode)
        print("STDOUT:", result.stdout.strip())
    with CRunScript(
            file_name       = "tmp-dry-bad.pype",
            shebang         = "#!" + interpreter,
            script_txt_list = [
                'on: "x" => ignore;',
            ],
            display_f       = False) as script_path:
        result = subprocess.run(
            ["python3", interpreter, "--dry-run",
             os.path.abspath(script_path)],
            capture_output = True, text = True)
        print("EXIT:", result.returncode)
        print("STDERR:", result.stderr.strip().replace(
            os.path.abspath(script_path), "tmp-dry-bad.pype"))


def run_if_cause():
    """RETURN: None. 'if(...)' causes: fire on a true condition; ordered
                     among match handlers; opaque to interference.
    """
    banner("if-cause fires on condition; dispatch order holds")
    run_script(
        """
        M/on: "known" => {
            print("pattern first")
        }
        M/on: if ( pype.line_n() >= 3 ) => {
            print("late line %d: %r" % (pype.line_n(), pype.line()))
        }
        M/on: <else> => {
            print("early unmatched: %r" % pype.line())
        }
        """,
        """
        stray
        known
        stray again
        known
        """)

    banner("condition reads the shared namespace")
    run_script(
        """
        M/on: <entry> => {
            budget = 2
        }
        M/on: "spend" => {
            budget -= 1
            print("spent; budget", budget)
        }
        M/on: if ( budget <= 0 ) => {
            print("budget exhausted at %r" % pype.line())
        }
        M/on: <else> => ignore;
        """,
        """
        spend
        idle
        spend
        idle
        """)

    banner("'if' causes are conditions, not patterns: exempt from "
           "disjointness")
    run_script(
        """
        M/on: "known" => {
            print("pattern handler")
        }
        M/on: if ( pype.line_n() % 2 == 0 ) => {
            print("even line condition")
        }
        M/on: if ( True ) => {
            print("catch-any condition, later in order")
        }
        M/on: <else> => ignore;
        """,
        """
        known
        anything
        odd again
        """)

    banner("a mode containing 'if' cannot be inherited from")
    try:
        parse('B/on: if ( True ) => ignore;\n'
              'B/on: <else> => ignore;\n'
              'S is: B\n'
              'S/on: <else> => ignore;\n', "<test>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)

    banner("broken condition rejected at parse")
    try:
        parse('M/on: if ( 1 +++ ) => ignore;\nM/on: <else> => ignore;\n',
              "<test>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % str(e).splitlines()[0])


def run_imports():
    """RETURN: None. 'import: FILE' merges another pype file; '--pype-dir'
                     adds search directories; 'sys.exit(n)' gates the
                     pipeline exit status.
    """
    interpreter_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..",
                     "bin", "hwut.pype"))
    work_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "tmp-import-work")
    lib_dir  = os.path.join(work_dir, "lib")
    os.makedirs(lib_dir, exist_ok=True)
    try:
        with open(os.path.join(lib_dir, "common.pype"), "w") as fh:
            fh.write('COMMON/on: <else> => ignore;\n'
                     'COMMON/on: "shared" => {\n'
                     '    print("shared handler from the library")\n'
                     '}\n')
        main_path = os.path.join(work_dir, "main.pype")
        with open(main_path, "w") as fh:
            fh.write('import: "common.pype"\n'
                     'is: COMMON\n'
                     'on: "own" => {\n'
                     '    print("own handler")\n'
                     '}\n')

        banner("import resolved via --pype-dir; inherited library mode")
        result = subprocess.run(
            ["python3", interpreter_path, "--pype-dir", lib_dir, main_path],
            input="own\nshared\nnoise\n", capture_output=True, text=True)
        print("EXIT:", result.returncode)
        for line in result.stdout.splitlines(): print("    " + line)
        if result.stderr: print("STDERR:", result.stderr.strip())

        banner("environment variables expand inside the quoted path")
        env_main = os.path.join(work_dir, "env-main.pype")
        with open(env_main, "w") as fh:
            fh.write('import: "$PYPE_TEST_LIB/common.pype"\n'
                     'is: COMMON\n'
                     'on: "own" => {\n'
                     '    print("own via env import")\n'
                     '}\n')
        env = dict(os.environ)
        env["PYPE_TEST_LIB"] = lib_dir
        result = subprocess.run(
            ["python3", interpreter_path, env_main],
            input="own\nshared\n", capture_output=True, text=True,
            env=env)
        print("EXIT:", result.returncode)
        for line in result.stdout.splitlines(): print("    " + line)

        banner("unquoted import path rejected")
        try:
            parse('import: bare.pype\non: <else> => ignore;\n',
                  os.path.join(work_dir, "unquoted.pype"))
            print("UNEXPECTED: parse returned")
        except PypeError as e:
            print("PypeError (expected): %s"
                  % str(e).replace(work_dir, "WORK"))

        banner("missing import reported with the searched paths")
        try:
            parse('import: "no-such-file.pype"\non: "x" => ignore;\n'
                  'on: <else> => ignore;\n',
                  os.path.join(work_dir, "broken.pype"))
            print("UNEXPECTED: parse returned")
        except PypeError as e:
            print("PypeError (expected): %s"
                  % str(e).replace(work_dir, "WORK"))

        banner("import cycle rejected")
        a_path = os.path.join(work_dir, "a.pype")
        b_path = os.path.join(work_dir, "b.pype")
        with open(a_path, "w") as fh:
            fh.write('import: "b.pype"\nA/on: <else> => ignore;\n')
        with open(b_path, "w") as fh:
            fh.write('import: "a.pype"\nB/on: <else> => ignore;\n')
        with open(a_path) as fh: a_txt = fh.read()
        try:
            parse(a_txt, a_path)
            print("UNEXPECTED: parse returned")
        except PypeError as e:
            print("PypeError (expected): %s"
                  % str(e).replace(work_dir, "WORK"))

        banner("sys.exit(n) inside a block gates the exit status")
        gate_path = os.path.join(work_dir, "gate.pype")
        with open(gate_path, "w") as fh:
            fh.write('on: <entry> => {\n    fail_n = 0\n}\n'
                     'on: "FAIL" => {\n    fail_n += 1\n}\n'
                     'on: <else> => ignore;\n'
                     'on: <eof> => {\n'
                     '    if fail_n > 0:\n'
                     '        print("gating: %d failure(s)" % fail_n)\n'
                     '        import sys\n'
                     '        sys.exit(3)\n'
                     '}\n')
        for input_txt, label in (("ok\nFAIL x\n", "with a failure"),
                                 ("ok\n", "clean")):
            result = subprocess.run(
                ["python3", interpreter_path, gate_path],
                input=input_txt, capture_output=True, text=True)
            print("%s: exit %d, stdout %r"
                  % (label, result.returncode, result.stdout))
    finally:
        import shutil
        shutil.rmtree(work_dir, ignore_errors=True)


def run_compat():
    """RETURN: None. Static version-independence audit: the interpreter
                     source must avoid syntax that narrows the range of
                     supported Python versions. One interpreter suffices:
                     the check is on the AST, not on runtime behaviour.
    """
    import ast
    source_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "hwut_pype.py"))
    with open(source_path) as fh:
        tree = ast.parse(fh.read())
    finding_list = []
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            finding_list.append(("f-string", node.lineno))
        if isinstance(node, ast.AnnAssign):
            finding_list.append(("annotation", node.lineno))
        if isinstance(node, getattr(ast, "NamedExpr", ())):
            finding_list.append(("walrus", node.lineno))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns or any(a.annotation for a in node.args.args):
                finding_list.append(("annotation", node.lineno))
            if node.args.kwonlyargs:
                finding_list.append(("keyword-only args", node.lineno))
    banner("forbidden constructs in hwut_pype.py")
    if finding_list:
        for kind, line_n in finding_list:
            print("VIOLATION: %s at line %d" % (kind, line_n))
    else:
        print("clean: no f-strings, no annotations, no walrus, "
              "no keyword-only arguments")


def run_errors():
    """RETURN: None. Parse errors carry file:line; unknown modes rejected."""
    banner("missing arrow")
    try:
        parse('M/on: "x"\n', "<err>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)

    banner("unclosed block")
    try:
        parse('M/on: "x" => {\n    print(1)\n', "<err>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)

    banner("'and:' without handler")
    try:
        parse('and: { }\n', "<err>")
        print("UNEXPECTED: parse returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)

    banner("switch to unknown mode")
    try:
        mode_db, first = parse('M/on: "x" => goto GHOST;\n'
                               'M/on: <else> => ignore;\n', "<err>")
        Interpreter(mode_db, first).run(io.StringIO("x\n"))
        print("UNEXPECTED: run returned")
    except PypeError as e:
        print("PypeError (expected): %s" % e)


def run_pipe():
    """RETURN: None. She-bang script used as an OS-level pipe filter;
                     INPUT-FILE arguments as the stream source.
    """
    _run_pipe_file_inputs()
    interpreter = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..",
                     "bin", "hwut.pype"))
    script_txt_list = [
        'SCAN/on: "PASS" <n = int> ":" <f = "*.txt"> => {',
        '    print("ok %d %s" % (n, f))',
        '}',
        'SCAN/on: <exit> => {',
        '    print("done")',
        '}',
        'SCAN/on: <else> => ignore;',
    ]
    print("SCRIPT: 'tmp-filter.pype' (she-bang: hwut.pype) {")
    for line in script_txt_list: print("    " + line)
    print("}")
    with CRunScript(
            file_name       = "tmp-filter.pype",
            shebang         = "#!" + interpreter,
            script_txt_list = script_txt_list,
            display_f       = False) as script_path:
        result = subprocess.run(
            [os.path.abspath(script_path)],
            input          = "PASS 1 : a.txt\nnoise\nPASS 2 : b.txt\n",
            capture_output = True, text = True)
        print("EXIT:", result.returncode)
        print("STDOUT: {")
        for line in result.stdout.splitlines(): print("    " + line)
        print("}")




def run_terminal():
    """RETURN: None. THE TERMINAL TOKEN (R-70, MANUAL 1b): a script
    WITH the '<eof>' emission ends its stream in '<hwut-end>'; a
    script WITHOUT ends bare -- and a bare end on a pype-d stream is
    the SCRIPT's fault, by the law the MANUAL states. The feeding
    application never carries the token."""
    banner("the '<eof>' emission: the stream states its completeness")
    run_script("""
         SCAN/on: <else> => flush;
         SCAN/on: <eof> => {
             print("<hwut-end>")
         }
         """, """
         alpha
         beta
         """)
    banner("no emission: the stream ends BARE -- the script's fault")
    run_script("""
         SCAN/on: <else> => flush;
         """, """
         alpha
         beta
         """)


HwutRunner(
    argv       = sys.argv,
    title      = "pype line-matching language",
    choice_map = {
        "terminal":       run_terminal,
        "patterns":  run_patterns,
        "modes":     run_modes,
        "namespace": run_namespace,
        "default_mode": run_default_mode,
        "inheritance": run_inheritance,
        "multi_inheritance": run_multi_inheritance,
        "else_flush": run_else_flush,
        "anchors_repeat": run_anchors_repeat,
        "boundaries_stack": run_boundaries_stack,
        "if_cause": run_if_cause,
        "imports": run_imports,
        "compat": run_compat,
        "errors":    run_errors,
        "pipe":      run_pipe,
        "examples":  run_examples,
        "generate":  run_generate,
    },
).run()
