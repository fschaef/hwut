TITLE: pype -- line-matching language triggering Python actions

PURPOSE:

    Deterministicalize timing-dependent test output for byte-exact
    comparison: the script records what arrives, may hold wait guards,
    and prints only order-independent results (counts, settled sorted
    summaries) -- 'my-test | ./report.pype'.
______________________________________________________________________________

FILES:

    hwut_pype.py    parser and interpreter.
    hwut.pype       executable she-bang entry point.
    manual.txt      user manual with grammar, semantics, idioms.
    examples/       five runnable scripts, each with a matching input
                    file: 'hwut.pype examples/NN-name.pype
                    < examples/NN-name.txt'. Reference outputs are
                    recorded in TEST/GOOD/test-pype.py--examples.txt.
    TEST/           HWUT test suite (16 choices, GOOD baselined).

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
                                        modes ('default' names the
                                        default mode).
    hwut.pype --pype-dir DIR ... SCRIPT add 'import:' search
                                        directories (repeatable).
    hwut.pype --dry-run SCRIPT          parse and check only (syntax,
                                        inheritance, interference,
                                        mandatory else); read no input.
    hwut.pype --example SCRIPT          print a generated example input
                                        for SCRIPT on stdout: one sample
                                        line per match handler, modes
                                        walked along static 'goto'/
                                        'push' effects; pure-ignore
                                        handlers
                                        produce no line; 'mode()' calls
                                        are not followed.

SCRIPT GRAMMAR (line-oriented; '#' starts a comment line):

    HANDLER  :=  [ MODE "/" ] "on:" CAUSE "=>" EFFECT { "and:" EFFECT }
    INHERIT  :=  [ MODE ] "is:" BASE { "," BASE }
    IMPORT   :=  "import:" FILE-PATH

    CAUSE    :=  PATTERN | "if" "(" python-condition ")" | "<else>"
              |  "<entry>" | "<exit>" | "<bof>" | "<eof>"
    EFFECT   :=  "{" python block "}" | "goto" OTHERMODE ";"
              |  "push" OTHERMODE ";" | "pop" ";" | "ignore" ";"
              |  "flush" ";"

    A missing MODE addresses the DEFAULT MODE. 'on: <else>' fires when
    every match handler of the active mode failed. 'and:' appends one
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

    The handlers of the active mode are tried in definition order; the
    first whose pattern matches fires. The pattern matches anywhere in
    the line; there is no anchoring to line start. If every match
    handler fails, the first 'else' handler of the effective list
    fires. One handler fires per line; its blocks run in definition
    order. Every ACTIVATABLE mode (start mode, switch and push targets)
    must carry an 'else' in its effective list -- parse error otherwise;
    activation through 'mode()'/'push()' is checked at run time; pure
    mixins are exempt. Runtime information lives in the 'pype' object:
    pype.time(), pype.file_name(), pype.line(), pype.line_n(),
    pype.mode_name(), pype.stack_depth(), pype.bindings(); actions:
    pype.goto(NAME), pype.push(NAME), pype.pop(). 'sys.exit(n)' in a
    block terminates immediately with exit status n. An 'if(...)'
    cause fires when its condition evaluates true; conditions are not
    patterns -- exempt from disjointness, definition-ordered, and a
    mode containing one cannot be inherited from.

MODES:

    Exactly one mode is active. Bare 'on:' handlers form the DEFAULT MODE.
    '<bof>'/'<eof>' handlers of the boundary-active mode fire once each; the
    run nests as <entry>, <bof>, lines, <eof>, <exit>. '=> push M;'/'push()'
    stacks the active mode and switches; '=> pop;'/'pop()' returns
    (<entry>/<exit> fire as on a plain switch; POP may re-enter the default
    mode; POP on an empty stack is an error).
    The default mode, when present, is the start mode; otherwise the first
    mode defined in the script is. '<entry>' handlers fire on activation,
    '<exit>' handlers on deactivation. At end of input the active mode's
    '<exit>' fires. A switch to the already-active mode is a no-operation.
    The default mode has no name; once left, it cannot be entered again.

    '=> OTHERMODE' and the namespace function 'mode("OTHERMODE")' both
    request a switch; the request is applied after the current handler's
    blocks have completed. The last request wins.

INHERITANCE:

    'LEFT is: BASE1, BASE2, ...' gives LEFT all handlers (<entry>,
    <exit>, <bof>, <eof>, match, <else>) of every named base,
    transitively. A handler arriving twice over a diamond is entered
    once.

    SHADOWING IS FORBIDDEN. Any two distinct pattern handlers of one
    effective list whose languages INTERSECT -- some line matches both
    -- are a hard error, wherever the pair comes from. Pattern
    dispatch is therefore order-free. Intersection is decided exactly
    on the pattern automata (e.g. '<n = int>' intersects
    '<x = number>'; '"abc"' does not intersect '"abc" "def"').
    <else> is THE ONE EXCEPTION: it can and must be shadowed; the
    first <else> of the effective list fires, own before inherited.
    'if(...)' causes are conditions, not patterns: exempt,
    definition-ordered; a mode containing one cannot be inherited
    from. The error names the mode, both defining modes, and both
    script locations. Bases hold the shared vocabulary; deriving
    modes add disjoint vocabularies.

    Inheritance cycles and unknown bases are parse errors. The default
    mode may inherit ('is: BASE1, BASE2'); it cannot be inherited from.

KEYWORDS:

    No word is reserved as a mode name: commands are lowercase and
    ';'-terminated, a mode name occurs only as the second argument of
    'goto'/'push', so mode names and commands cannot collide.
    '=> ignore;' is the no-op action: the matched line is consumed and
    nothing happens. '=> flush;' emits the input line unchanged on
    stdout; it combines with blocks and switches via 'and:'.
    'on: <else> => flush;' turns a script into a pass-through filter
    that transforms known lines and forwards the rest.

NAMESPACE:

    All Python blocks share one single namespace. It provides 'mode(name)'
    and, during a match, 'line' (the current input line, newline stripped)
    and the pattern's named bindings. Bindings and assignments persist
    across handlers and modes.

ERRORS:

    Parse errors and unknown mode names raise PypeError with 'file:line'
    prefix; the interpreter exits with status 1. Tracebacks from Python
    blocks point into the pype script file.
______________________________________________________________________________
