===============================================================================
REACTIVE RULE ENGINE  --  HWUT 2.0
PARSER ARCHITECTURE
===============================================================================
                               
                               .--------.
      rule file source code -->| Parser |---> AST (abstract syntax tree)
                               '--------'

The parser turns a rule-file into an Abstract Syntax Tree. It is a table-driven
LL(1) engine: the grammar is declared once as data, compiled into FIRST sets,
and executed by a single generic driver. There is no hand-written descent
function per construct; adding or changing a rule is an edit to the grammar
data, not to the driver.

The driver is STACKLESS: it walks the grammar on an explicit heap work-stack
rather than the Python call stack, so parse depth is bounded by memory, not by
the interpreter's recursion limit. This matters because namespaces nest to
unrestricted depth ('open ... open ... close ... close'); a recursive walker
would overflow after a few dozen levels, whereas the engine parses tens of
thousands of levels (see the monkey 'depth_bomb' acceptance test).

-------------------------------------------------------------------------------
RUNNING A PARSE
-------------------------------------------------------------------------------

One call turns rule-file source into an AST:

    from vut.engine.temporal_logic.parser.parser_engine import parse
    from vut.engine.temporal_logic.parser.diagnostic    import DiagnosticReporter

    reporter = DiagnosticReporter()
    rule_file = parse(source_text, oracle, reporter)

The three arguments:

    source_text   the rule-file text, one str.
    oracle        the Luau fragment oracle: any object with
                  'parse(text) -> result'. The lexer hands it each '{ ... }'
                  span to find the matching brace under the role the grammar
                  context demands. It is the ONE external dependency; a source
                  with no Luau spans never calls it.
    reporter      a DiagnosticReporter. Diagnostics (lexer and parser phases)
                  accumulate here; 'parse' does not raise on an author error.

What comes back:

    rule_file     a RuleFile whose '.items' are the top-level constructs
                  (Namespace, Causality, Mode, ModeGroup, StateMachine,
                  EventDef, ClockDef, ForwardDecl, Include). On a recovered
                  error the tree is PARTIAL -- the offending item is dropped,
                  the rest are present -- so always consult the reporter:

    if reporter.has_fatal():
        ...                         # infrastructure failure (e.g. oracle down)
    for d in reporter.errors:
        ...                         # d.phase, d.message, d.source_offset

'parse' is the public seam. Under it, 'compiled_grammar()' compiles and
memoizes GRAMMAR/ACTIONS once (raising LL1ConflictError if a grammar edit
breaks LL(1)); 'EngineParser(source, oracle, reporter, grammar).parse()' is the
loop that drives the 'top-level' start rule to EOF, recovering past each error.
Call 'parse' unless you are testing the engine itself.

-------------------------------------------------------------------------------
MODULES AND RESPONSIBILITIES
-------------------------------------------------------------------------------

    terminals.py
        The named-terminal authoring surface. The 'T' factory mints Terminal
        objects (T.regex character classes, T.string keywords, T.captured
        keywords kept for the builder, T.opaque Luau spans carrying a Role) and
        records each into TERMINAL_DB in declaration order. A terminal's
        IDENTITY is its _name(); the engine compares terminals by object
        identity, never by a hand-written id. 'R(name)' wraps a reference to
        another grammar rule. The framing terminals (Luau open/block, comment,
        whitespace, mismatch, EOF) live here too.

    syntax.py
        The language as data, and its prose spec in one place. A preamble binds
        the regex/opaque/captured terminals to 't_re_'/'t_opq_'/'t_kw_'
        variables; GRAMMAR then maps each non-terminal to a pattern built from
        the combinators OR/OPT/PLUS/STAR (syntax_support), plain tuples for
        sequence, bare strings for silent keywords, terminal objects, and R()
        references. SYNTAX_DOC, the module docstring, is the DOMINATING prose
        reference for the concrete syntax; this README cites it and defers to it
        on any discrepancy.

    syntax_support.py
        The combinator classes (Seq/Alt/Opt/Plus/Star) the grammar author
        writes, and 'compile_element', which turns an authored pattern into the
        parser_nodes tree. The only authoring-time dependency the grammar data
        needs; it knows nothing of the engine.

    grammar.py
        The reduce actions. ACTIONS maps each GRAMMAR rule name to a builder
        '_build_*(frame) -> node' that turns a matched frame into an AST node,
        or 'None' for a pass-through rule that forwards its single child value
        (the OR dispatch rules). It imports GRAMMAR from syntax.py and supplies
        the actions; the engine zips the two by key.

    parser_nodes.py
        The compiled grammar as a uniform polymorphic node tree -- combinators
        (Seq/Alt/Opt/Plus/Star) and leaves (TerminalNode/LuauNode/
        NonTerminalNode) alike. Every node answers first_set / nullable /
        check_alts / expand, so the engine never switches on a node kind: it
        calls a method and the node does the right thing. The work-instruction
        tags (ELEM/REDUCE/LOOP) are defined here and shared with the engine.

    lexer.py
        Regex tokenizer. It GENERATES its scanner spec lazily from TERMINAL_DB
        plus the bare-string keywords walked out of GRAMMAR -- no hand-kept
        token table. One compiled alternation of named patterns yields tokens
        on demand. Holds the oracle boundary: on a Luau open brace it hands off
        to the fragment oracle to slice out an opaque '{ ... }' block under the
        role the parser supplies, and resumes past the closing brace. Illegal
        characters are reported non-fatally and returned as MISMATCH so the
        parser can resync.

    parser_engine.py
        The engine. 'Grammar' compiles GRAMMAR/ACTIONS into the parser_nodes
        tree (resolving each leaf to its Terminal/Luau/NonTerminal node),
        computes FIRST sets, and rejects any OR whose branches share a FIRST
        token (LL1ConflictError), so ambiguity is caught at compile time, not at
        parse time. 'EngineParser' walks the compiled patterns with one token of
        lookahead on the explicit work/frame stacks, building a 'Frame' of child
        values per rule and calling the rule's reduce action.
        'compiled_grammar()' memoizes the compiled grammar; 'parse()' is the
        entry point returning a RuleFile.

    ast_nodes.py
        Frozen dataclasses for the tree. Every node stores 'begin' (a source
        offset) for provenance and error reporting. TopLevel is the abstract
        base for the items a rule-file may contain: Namespace, Include,
        Causality, Mode, ModeGroup, StateMachine, ForwardDecl, EventDef,
        ClockDef.

    diagnostic.py
        Phase-tagged diagnostics (LEXER, PARSER, ...) collected by a
        DiagnosticReporter. Non-fatal diagnostics accumulate so one run can
        report several problems; a fatal diagnostic stops the pass.

-------------------------------------------------------------------------------
(A) THE LEXER AND THE ORACLE HANDOFF
-------------------------------------------------------------------------------

The lexer matches a single compiled regular expression of named patterns; the
C regex backend finds token boundaries quickly. Keyword patterns are ordered so
longer keywords win where prefixes overlap ('mode_group:' before 'mode:',
'state_machine:' before 'state:', '+!'/'-!' before '!'). Keywords are colon-
glued (the colon abuts its filler: 'mode:' opens, ':end' closes); leading-colon
terminators (':end', ':close') are matched before the trailing-colon keywords,
and a NAME_COLON ('n:') is matched after all fixed keyword-colons but before
the bare identifier class. There is no free-standing colon and no '='.

When the lexer yields a Luau open brace it pauses and the fragment oracle finds
the matching close for the current role (e.g. a guard CONDITION, a mutation
STATEMENT_BLOCK, an rvalue EXPRESSION). The raw span becomes one LUAU_BLOCK
token and the lexer cursor is advanced past the close. An unbalanced fragment
is recovered: the error flag is set and a block token is still produced so
parsing can continue.

-------------------------------------------------------------------------------
(B) THE GRAMMAR TABLE AND LL(1) GUARANTEE
-------------------------------------------------------------------------------

A pattern is a plain tuple for sequence, with the combinator classes OR / OPT
/ PLUS / STAR for the rest. For example a causality:

    "causality": ("on:", R("cause"), PLUS(("=>", R("effect"))))

A bare string ('on:', '=>') is a silent keyword terminal; R("name") references
another rule; a 't_opq_...' terminal marks an opaque Luau span under its Role.

At compile time 'Grammar' computes FIRST(rule) for every rule and, for each OR
and each repetition, checks that the continuation is decidable from one
lookahead token. If two OR branches can start with the same token the grammar
is rejected with a located LL1ConflictError. This is why the test-engine
'll1_ok' choice can assert the real grammar is conflict-free, and 'll1_conflict'
can show a toy grammar being rejected.

DELIMITER DESIGN (so every rule is decidable with one token):

    'on:' block       no terminator. Each effect is led by '=>', so the effect
                      loop ends at the first token that is not '=>'. The
                      follower of a rule -- a top-level keyword, a member
                      keyword, 'until:', ':end', or EOF -- is never '=>'.
    <mode>            closed by ( 'until:' <cause> )+.
    <state>           has an optional body and optional 'until:' causes; both
                      may be empty. It is terminated STRUCTURALLY -- by the next
                      state-machine element ('state:', 'has:', 'default:',
                      'init:', 'deinit:') or by the aggregate's ':end'. A state
                      carries no closing keyword of its own.
    <mode-group>      closed by ':end'.
    <state-machine>   closed by ':end'.

The ':end' closer on the two aggregates is what makes an inline member
parseable: a member mode carries its own ( 'until:' <cause> )+, and because the
aggregate ends with ':end' rather than its own 'until:', the boundary between the
last member's untils and the aggregate's close is decidable with one token. A
state's untils are a STAR, so a member state runs up to the first token that
neither continues an until nor starts a new member -- which is exactly the next
member keyword or ':end'.

-------------------------------------------------------------------------------
(C) THE ENGINE (DRIVER) AND REDUCE ACTIONS
-------------------------------------------------------------------------------

'EngineParser._match' drives one element to completion on two explicit stacks:

    work    -- instructions still to perform (LIFO). An instruction is one of:
               ELEM(element)  expand element, appending values to the top frame
               REDUCE(nt)     finish a NonTerminal: pop its frame, run its
                              action, append the result to the new top frame
               LOOP(body)     a PLUS/STAR iteration point
    frames  -- one 'Frame' (collected child values + start offset) per
               NonTerminal currently being assembled; child values append to
               frames[-1].

Expansion is direct: a Seq pushes its parts in reverse (so they run left to
right); an Alt chooses its branch from one-token lookahead and pushes it; an
Opt pushes its body iff the lookahead starts it; a Plus pushes one mandatory
body plus a LOOP; a Star pushes a LOOP. Each time a LOOP surfaces it re-checks
the lookahead and, while the body still starts, pushes the body and another
LOOP beneath it -- turning repetition into stack iteration. A terminal matches
and advances; a captured literal or Luau block appends its value. When a
NonTerminal's pattern is fully consumed its REDUCE fires: the frame's values go
to the rule's action, which returns one AST node appended to the parent frame.
A 'None' action forwards the single child unchanged (pure alternations like
'<effect>' and '<rvalue>'). Because the walk runs on the heap work and frame
stacks, not the C stack, nesting depth is bounded only by memory.

ERROR RECOVERY:

    On a token that no alternative accepts, the engine emits a PARSER
    diagnostic and resyncs: it skips to the next safe boundary -- it stops AT a
    top-level keyword (a new item starts there) or CONSUMES an aggregate ':end'
    and stops after it. Because causalities have no terminator, a top-level
    keyword is the boundary for a malformed rule; ':end' is the boundary inside
    an aggregate. A mismatch raises _ResyncError, which unwinds the work and
    frame stacks back to 'parse', which resyncs and continues; recovery is
    non-fatal, so one run can surface several errors.

-------------------------------------------------------------------------------
(D) THE ABSTRACT SYNTAX TREE
-------------------------------------------------------------------------------

Nodes are frozen dataclasses; the tree is immutable once built. Each carries
'begin' for provenance, feeding error reporting and the source-to-target
location mapper during code generation. The aggregate nodes hold their members
by kind:

    Mode           causalities, init, deinit, untils
    State          causalities, init, deinit, untils  (body and untils optional;
                                                        terminated structurally)
    ModeGroup      modes, has_refs, init, deinit       (closed by ':end')
    StateMachine   states, has_refs, default, init, deinit  (closed by ':end')
    HasRef         a 'has:' member pulled in by bare or qualified name
    ForwardDecl    a '<name> is: <kind>' scope-level forward declaration; for
                   kind 'container' carries config args + an optional Luau
                   'as:' lvalue handle
                   (name + kind, no body; definition follows in the scope)
    Spawn          a '+! name(args) [as inst]' aggregate spawn
    Unspawn        a '-! name' removal of a named aggregate
    Namespace      an 'open <dotted-name> ... close' scope of nested items
    Include        an 'include "<file>" as <dotted-name>' file mount (recorded;
                   resolved and mounted by the semantic pass)

-------------------------------------------------------------------------------
(E) SEMANTIC VALIDATION (PASS 2)
-------------------------------------------------------------------------------

The parser accepts the LL(1) surface syntax; constraints that are not
context-free are deferred to a validation pass over the finished AST, kept
separate so the parser stays a pure recognizer:

    1. At most one 'init' and one 'deinit' per reactor or aggregate.
    2. State machine: at most one 'default'; 'default:' references a defined
       member or VOID. A state needs no closing 'until'; its untils are
       optional and it terminates structurally.
    3. Reference checks: every '! MODE()' / '+! AGG()' arming, every '-! name'
       unspawn, every '+! ... in: C' container reference (C resolves to an
       'is: container' declaration), and every 'has:' and 'default:' target
       resolves to a defined
       entity (an unspawn target must be a named, spawned instance). Modes and
       state machines share one namespace; no mode may share a state machine's
       name. Every '<name> is: <kind>' forward declaration is matched by a
       definition of <name> of that kind later in the same scope; a declaration
       with no following definition, or a kind mismatch, is a validation error.
       A <trigger> names an event: because events are STRICT define-before-use
       (no forward referencing -- an event is a leaf that references nothing),
       an event name is resolvable the moment it is used, so an unknown trigger
       is a "no such event" diagnostic. The check is cheap for that reason, but
       it is still a SEMANTIC-pass concern -- the parser stays a pure recognizer
       and does not track a declared-event set; one resolver, parameterized by
       the kind expected at each site, owns all name resolution.
    4. Include resolution: each 'include "<file>" as <path>' resolves the file,
       parses it once, and mounts its namespace at <path>; the included file is
       lexically self-contained (its names do not see the mounting scope).

-------------------------------------------------------------------------------
(F) THE TEST SUITE (TEST/)
-------------------------------------------------------------------------------

Each test is an HWUT driver: '--hwut-info' lists its choices, and running a
choice prints to stdout, compared byte-for-byte against a GOOD/ recording. All
four derive their choices from the compiled grammar, so a new rule is exercised
automatically with no test edit.

    test-lexer.py        Tokenizer coverage: keywords, operators, comments,
                         dotted names, the Luau oracle handoff, and lexer error
                         cases (mismatch, malformed fragment, source mapping).

    test-engine.py       Grammar-level properties: FIRST sets, the real grammar
                         is LL(1) (ll1_ok), a toy grammar is rejected
                         (ll1_conflict), and the token inventory derived from
                         the terminal database covers every fixed-spelling
                         terminal the grammar refers to.

    cover-syntax-tree.py POSITIVE coverage: one choice per rule, synthesizing a
                         minimal valid input for each shape (PLUS -> 1,2;
                         STAR -> 0,1,2; OPT -> absent,present; one variadic
                         point varied at a time, no cross-product) and printing
                         the resulting AST with the input fragment that produced
                         it. 'node_coverage' asserts every AST node type is built
                         by some rule.

    cover-negative.py    NEGATIVE coverage: one choice per rule, feeding
                         mechanically malformed inputs (truncation, required-
                         element omission, junk head) to the rule in isolation
                         and recording the diagnostics and recovery, so error
                         behaviour is pinned, not just the accepted language.

    monkey-fuzz.py       Deterministic grammar-walk fuzzing. Profiles (deep,
                         wide, luau, balanced, states) each pair a seed with
                         weights (recursion bias, repetition cap, OPT chance,
                         Luau nesting, item count); the walk is depth-budgeted
                         so it always terminates and the printed AST stays
                         reviewable. Because the walk is deterministic the AST
                         is stable and its recording is the assertion.
                         'depth_bomb' nests namespaces to 2000 levels as the
                         stackless-engine acceptance test (all PASS only with
                         the heap-stack driver; a recursive walker fails past a
                         few dozen). 'coverage' unions the rules entered and AST
                         node types produced across all profiles and asserts the
                         suite collectively reaches every rule (38/38) and every
                         tree node type (22/22; the transient InitBlock/
                         DeinitBlock are excluded, as they never persist).

                         Passing '--debug' after a profile name additionally
                         renders the SAME synthesized walk as real source text,
                         re-parses it through the REAL lexer, and confirms the
                         AST matches structurally -- a lightweight round-trip
                         that also prints the source for eyeballing text vs.
                         tree, plus the per-profile rule/node gaps. '--debug'
                         output is never recorded.
