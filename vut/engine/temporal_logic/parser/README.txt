===============================================================================
REACTIVE RULE ENGINE  --  HWUT 2.0
PARSER ARCHITECTURE
===============================================================================

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
MODULES AND RESPONSIBILITIES
-------------------------------------------------------------------------------

    lexer.py
        Regex tokenizer. One compiled alternation of named patterns yields
        tokens on demand. Holds the oracle boundary: on a Luau open brace it
        hands off to the fragment oracle to slice out an opaque '{ ... }' block
        and resumes past the closing brace. Illegal characters are reported
        non-fatally and returned as MISMATCH so the parser can resync.

    grammar.py
        The language as data. GRAMMAR maps each non-terminal to a pattern built
        from the combinators SEQ, ALT, OPT, STAR, PLUS, plus terminal literals
        and the '{luau:ROLE}' fragment marker. CAPTURED_LITERALS lists the
        keyword literals whose token value is kept (ANY, BEGIN, END, VOID). For
        each rule a reduce action ('_build_*') turns the matched frame into an
        AST node; a 'None' action passes the child value through unchanged.

    parser_engine.py
        The engine. 'Grammar' compiles the pattern table: it resolves literals
        against the lexer (via the literal table), computes FIRST sets, and
        rejects any ALT whose branches share a FIRST token (LL1ConflictError),
        so ambiguity is caught at compile time, not at parse time.
        'EngineParser' walks the compiled patterns with one token of lookahead,
        building a 'Frame' of child values per rule and calling the rule's
        reduce action. 'compiled_grammar()' memoizes the compiled grammar;
        'parse()' is the entry point returning a RuleFile plus diagnostics.

    ast_nodes.py
        Frozen dataclasses for the tree. Every node stores 'begin' (a source
        offset) for provenance and error reporting. TopLevel is the abstract
        base for the items a rule-file may contain: Causality, Mode, ModeGroup,
        StateMachine, EventDef, ClockDef.

    diagnostic.py
        Phase-tagged diagnostics (LEXER, PARSER, ...) collected by a
        DiagnosticReporter. Non-fatal diagnostics accumulate so one run can
        report several problems; FatalDiagnostics stops the pass.

-------------------------------------------------------------------------------
(A) THE LEXER AND THE ORACLE HANDOFF
-------------------------------------------------------------------------------

The lexer matches a single compiled regular expression of named patterns; the
C regex backend finds token boundaries quickly. Keyword patterns are ordered so
longer keywords win where prefixes overlap ('mode_group' before 'mode',
'state_machine' before 'state', '+!'/'-!' before '!').

When the lexer yields a Luau open brace it pauses and the fragment oracle finds
the matching close for the current role (e.g. a guard CONDITION, a mutation
STATEMENT_BLOCK, an rvalue EXPRESSION). The raw span becomes one LUAU_BLOCK
token and the lexer cursor is advanced past the close. An unbalanced fragment
is recovered: the error flag is set and a block token is still produced so
parsing can continue.

-------------------------------------------------------------------------------
(B) THE GRAMMAR TABLE AND LL(1) GUARANTEE
-------------------------------------------------------------------------------

A pattern is a nested tuple of combinators. For example a causality:

    "<causality>": (SEQ, "on", "<cause>", (PLUS, (SEQ, "=>", "<effect>")))

At compile time 'Grammar' computes FIRST(rule) for every rule and, for each ALT
and each repetition, checks that the continuation is decidable from one
lookahead token. If two ALT branches can start with the same token the grammar
is rejected with a located LL1ConflictError. This is why the test-engine
'll1_ok' choice can assert the real grammar is conflict-free, and 'll1_conflict'
can show a toy grammar being rejected.

DELIMITER DESIGN (so every rule is decidable with one token):

    'on' block        no terminator. Each effect is led by '=>', so the effect
                      loop ends at the first token that is not '=>'. The
                      follower of a rule -- a top-level keyword, a member
                      keyword, 'until', 'end', or EOF -- is never '=>'.
    <mode>            closed by ( 'until' <cause> )+.
    <state>           closed by 'until switched'. Modeled as <state-untils>, a
                      right-recursive tail left-factored on 'until': after
                      'until', one token chooses 'switched' (terminate) or a
                      <cause> (continue). This stops the run exactly at
                      'until switched' and never swallows the enclosing
                      machine's tokens.
    <mode-group>      closed by 'end'.
    <state-machine>   closed by 'end'.

The 'end' closer on the two aggregates is what makes an inline member
parseable: a member mode carries its own ( 'until' <cause> )+, and because the
aggregate ends with 'end' rather than its own 'until', the boundary between the
last member's untils and the aggregate's close is decidable with one token.
'switched' is parsed only as the state closer; it is not a general <trigger>.

-------------------------------------------------------------------------------
(C) THE ENGINE (DRIVER) AND REDUCE ACTIONS
-------------------------------------------------------------------------------

'EngineParser._match' drives one element to completion on two explicit stacks,
never recursing into itself:

    work    -- instructions still to perform (LIFO). An instruction is one of:
               ELEM(element)  expand element, appending values to the top frame
               REDUCE(nt)     finish a NonTerminal: pop its frame, run its
                              action, append the result to the new top frame
               LOOP(body)     a PLUS/STAR iteration point
    frames  -- one 'Frame' (collected child values + start offset) per
               NonTerminal currently being assembled; child values append to
               frames[-1].

Expansion is direct: a SEQ pushes its parts in reverse (so they run left to
right); an ALT chooses its branch from one-token lookahead and pushes it; an
OPT pushes its body iff the lookahead starts it; a PLUS pushes one mandatory
body plus a LOOP; a STAR pushes a LOOP. Each time a LOOP surfaces it re-checks
the lookahead and, while the body still starts, pushes the body and another
LOOP beneath it -- turning repetition into stack iteration. A terminal matches
and advances; a captured literal or Luau block appends its value. When a
NonTerminal's pattern is fully consumed its REDUCE fires: the frame's values go
to the rule's action, which returns one AST node appended to the parent frame.
A 'None' action forwards the single child unchanged (pure alternations like
'<effect>' and '<rvalue>'). Because the recursion lives on the heap stacks, not
the C stack, nesting depth is bounded only by memory.

ERROR RECOVERY:

    On a token that no alternative accepts, the engine emits a PARSER
    diagnostic and resyncs: it skips to the next safe boundary -- it stops AT a
    top-level keyword (a new item starts there) or CONSUMES an aggregate 'end'
    and stops after it. Because causalities have no terminator, a top-level
    keyword is the boundary for a malformed rule; 'end' is the boundary inside
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
    State          causalities, init, deinit, untils  (closed by 'until switched')
    ModeGroup      modes, has_refs, init, deinit       (closed by 'end')
    StateMachine   states, has_refs, default, init, deinit  (closed by 'end')
    HasRef         a 'has:' member pulled in by bare or qualified name
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
    2. State machine: at most one 'default'; every member state's until-run
       ends with 'until switched'; 'default' references a defined member or
       VOID.
    3. Reference checks: every '! MODE()' / '+! AGG()' arming, every '-! name'
       unspawn, and every 'has:' and 'default' target resolves to a defined
       entity (an unspawn target must be a named, spawned instance). Modes and
       state machines share one namespace; no mode may share a state machine's
       name.
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
                         (ll1_conflict), and the literal table.

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
