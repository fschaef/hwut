TITLE: pype -- line-matching language triggering Python actions

PURPOSE:

    Deterministicalize timing-dependent test output for byte-exact
    comparison: the script records what arrives, may hold wait guards,
    and prints only order-independent results (counts, settled sorted
    summaries) -- 'my-test | ./report.pype'.
______________________________________________________________________________

FILES:

    pype.py         parser and interpreter.
    pype_system.py  systems of scripts ('.pypes'): reading, running,
                    drawing (RQ-2).
    manual.txt      user manual with grammar, semantics, idioms.
    examples/       five runnable scripts, each with a matching input
                    file: 'hwut.pype examples/NN-name.pype
                    < examples/NN-name.txt'. Reference outputs are
                    recorded in TEST/GOOD/test-pype.py--examples.txt.
    TEST/           HWUT test suite (17 choices, GOOD baselined).

    The executable she-bang entry point is 'bin/hwut.pype' under the
    package root, with every other launcher of the tool.

INVOCATION:

    hwut.pype SCRIPT < input            direct.
    producer | ./script.pype            she-bang: script begins with
                                        '#! /usr/bin/env hwut.pype' and is
                                        executable; hwut.pype is on PATH.
    hwut.pype --trace SCRIPT            run with a dispatch trace on
                                        stderr: input lines against the
                                        handlers they trigger, effects,
                                        and the executed lines inside
                                        python blocks, in gcc-style
                                        'file:line:' format; stdout
                                        stays the clean filter stream.
    hwut.pype --trace-plain SCRIPT      the same trace with a plain
                                        'TRACE|' line starter.
    hwut.pype --trace M1 M2 SCRIPT      restrict the trace to the named
                                        scopes ('default' names the
                                        default scope).
    hwut.pype --pype-dir DIR ... SCRIPT add 'import:' search
                                        directories (repeatable).
    hwut.pype --dry-run SCRIPT          parse and check only (syntax,
                                        inheritance, mandatory else and
                                        <eof>, a NOTE on a handler that
                                        never fires); read no input.
    hwut.pype --example SCRIPT          print a generated example input
                                        for SCRIPT on stdout: one sample
                                        line per match handler, scopes
                                        walked along static 'goto'/
                                        'push' effects; pure-ignore
                                        handlers
                                        produce no line; 'pype.goto()'
                                        calls are not followed.
    hwut.pype SYSTEM.pypes < input      run a SYSTEM of scripts wired
                                        by '-->' lines (MANUAL 14).
    hwut.pype --draw [--svg] SYSTEM.pypes
                                        draw the system: ASCII; SVG.
    hwut.pype --unit-types              the unit types and the units
    hwut.pype --units [<type>]          '<x = quantity(X)>' admits
                                        (MANUAL 12).

SCRIPT GRAMMAR (line-oriented; '#' starts a comment line):

    HANDLER  :=  [ SCOPE "/" ] "on:" CAUSE "=>" EFFECT { "and:" EFFECT }
    INHERIT  :=  [ SCOPE ] "is:" BASE { "," BASE }
    TICK     :=  "tick:" SECONDS "=>" '"' FORMAT '"'   time as input
                                        ('{time_sec}', MANUAL 13)
    IMPORT   :=  "import:" FILE-PATH

    CAUSE    :=  PATTERN | "<else>"
              |  "<entry>" | "<exit>" | "<bof>" | "<eof>"
    EFFECT   :=  "{" python block "}" | "goto" OTHERSCOPE ";"
              |  "push" OTHERSCOPE ";" | "pop" ";" | "ignore" ";"
              |  "flush" ";"

    A missing SCOPE addresses the DEFAULT SCOPE. 'on: <else>' fires when
    every match handler of the active scope failed. 'and:' appends one
    further EFFECT to the preceding handler. 'import: "PATH"' merges another
    pype file (quoted path, environment variables expanded, resolved
    relative to the importer, then --pype-dir directories; idempotent;
    cycles rejected).

A block closes with '}' alone on a line. Blocks are dedented before
compilation.

PATTERN TOKENS (whitespace-separated; joined by '\s*'; the whole pattern
is searched anywhere in the input line):

    "text"                      constant string.
    <name = number>             floating point number, bound as float.
    <name = int>                integer, bound as int.
    <name = "GLOB">     glob over one token ('*' -> '\S*',
                                '?' -> '\S'), bound as str.
    <number> <int> <"GLOB">     unnamed variants; match without binding.
    <bol> <eol>                 demand line start / line end here.
    +( i : ... )                repeat group, ONE OR MORE times; 'i'
                                counts repetitions; '<x[i] = ...>'
                                collects a dictionary; the bracket
                                admits offset expressions '[i +/- n]'.
                                Greedy, no backtracking, no nesting.

DISPATCH:

    The handlers of the active scope are tried in definition order; the
    first whose pattern matches fires. The pattern matches anywhere in
    the line unless '<bol>' / '<eol>' anchor it. If every match
    handler fails, the first 'else' handler of the effective list
    fires. One handler fires per line; its blocks run in definition
    order. Every ACTIVATABLE scope (start scope, switch and push targets)
    must carry an 'else' in its effective list -- parse error otherwise;
    activation through 'pype.goto()'/'pype.push()' is checked at run time; pure
    mixins are exempt. Runtime information lives in the 'pype' object:
    pype.time(), pype.file_name(), pype.line(), pype.line_n(),
    pype.scope_name(), pype.stack_depth(), pype.bindings(); actions:
    pype.goto(NAME), pype.push(NAME), pype.pop(). 'sys.exit(n)' in a
    block terminates immediately with exit status n. A condition is
    tested in a block ('if(...)' is no cause, 2026-11-22). EVERY scope
    carries an '<eof>' handler, own or inherited (D-39). An effect may stand on the handler's line:
    '=> { pass }' (D-46).

SCOPES:

    Exactly one scope is active. Bare 'on:' handlers form the DEFAULT SCOPE.
    '<bof>'/'<eof>' handlers of the boundary-active scope fire once each; the
    run nests as <entry>, <bof>, lines, <eof>, <exit>. '=> push M;'/'push()'
    stacks the active scope and switches; '=> pop;'/'pop()' returns
    (<entry>/<exit> fire as on a plain switch; POP may re-enter the default
    scope; POP on an empty stack is an error).
    The default scope, when present, is the start scope; otherwise the first
    scope defined in the script is. '<entry>' handlers fire on activation,
    '<exit>' handlers on deactivation. At end of input the active scope's
    '<exit>' fires. A switch to the already-active scope is a no-operation.
    The default scope has no name; once left, it cannot be entered again.

    '=> goto OTHERSCOPE;' and 'pype.goto("OTHERSCOPE")' in a block both
    request a switch; the request is applied after the current handler's
    blocks have completed. The last request wins. A request raised by
    the '<entry>' or '<exit>' handlers of that switch is applied in the
    same step, before the next input line (MANUAL 7).

INHERITANCE:

    'LEFT is: BASE1, BASE2, ...' gives LEFT all handlers (<entry>,
    <exit>, <bof>, <eof>, match, <else>) of every named base,
    transitively. A handler arriving twice over a diamond is entered
    once.

    THE FIRST MATCH FIRES (D-47): where two pattern handlers of one
    effective list match a line, the first of the effective list
    triggers -- own before inherited, bases in declaration order; the
    same order picks the <else>. '--dry-run' NOTEs a handler that can
    never fire ('"abc" "def"' after '"abc"'), superficially: an
    earlier handler's tokens contiguous among its own. Bases hold the
    shared vocabulary; a deriving scope's own handler overrides.

    Inheritance cycles and unknown bases are parse errors. The default
    scope may inherit ('is: BASE1, BASE2'); it cannot be inherited from.

KEYWORDS:

    No word is reserved as a scope name: commands are lowercase and
    ';'-terminated, a scope name occurs only as the second argument of
    'goto'/'push', so scope names and commands cannot collide.
    '=> ignore;' is the no-op action: the matched line is consumed and
    nothing happens. '=> flush;' emits the input line unchanged on
    stdout; it combines with blocks and switches via 'and:'.
    'on: <else> => flush;' turns a script into a pass-through filter
    that transforms known lines and forwards the rest.

NAMESPACE:

    All Python blocks share one single namespace. It holds the 'pype'
    object ('pype.line()' is the current input line, newline stripped;
    'pype.goto(name)' requests a switch) and, during a match, the
    pattern's named bindings. Bindings and assignments persist across
    handlers and scopes.

ERRORS:

    Parse errors and unknown scope names raise PypeError with 'file:line'
    prefix; the interpreter exits with status 1. Tracebacks from Python
    blocks point into the pype script file.
______________________________________________________________________________
