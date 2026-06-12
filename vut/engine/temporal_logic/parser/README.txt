===============================================================================
REACTIVE RULE ENGINE  --  HWUT 2.0
PARSER ARCHITECTURE
===============================================================================

                 .-------.   tokens    .-------------.   CST    .---------.
  rule file  --->| Lexer |------------>| LL(2) Engine|--------->| AST_MAP |---> AST
   source        '-------'             '-------------'          | overlay |  (RuleFile)
                     |                                           '---------'
                     v
               .-----------.
               | SpanOracle|   '{ ... }' opaque Luau spans
               '-----------'

Table-driven LL(2) parsing: the grammar is declared once as data (grammar.py),
compiled into FIRST_2 sets, and executed by one generic, STACKLESS driver
(explicit heap work-stack; depth bounded by memory, not the interpreter --
see the monkey 'depth_bomb' acceptance test). The engine builds a canonical
CST of generic nodes; a partial overlay (ast_map.py) transforms each rule's
finished node into its typed AST value, bottom-up.

-------------------------------------------------------------------------------
RUNNING A PARSE
-------------------------------------------------------------------------------

    from vut.engine.temporal_logic.parser.rule_parser     import parse
    from vut.engine.temporal_logic.parser.core.diagnostic import DiagnosticReporter

    reporter  = DiagnosticReporter()
    rule_file = parse(source_text, oracle, reporter)

Arguments:

    source_text   the rule-file text, one str.
    oracle        the opaque-span oracle: any core.span_oracle.SpanOracle.
                  The lexer hands it each '{ ... }' span to find the matching
                  brace under the Role the grammar position demands. The ONE
                  external dependency; a source with no spans never calls it.
    reporter      a DiagnosticReporter. Lexer and parser diagnostics
                  accumulate here; 'parse' does not raise on an author error.

Returns:

    rule_file     a RuleFile whose '.items' are the top-level constructs in
                  source order. On a recovered error the tree is PARTIAL --
                  the offending item is dropped, the rest are present -- so
                  always consult the reporter:

    if reporter.has_fatal():
        ...                         # infrastructure failure (e.g. oracle down)
    for d in reporter.errors:
        ...                         # d.phase, d.message, d.source_offset

'parse' is the public seam. Under it, 'compiled_grammar()' registers GRAMMAR
with the lexer, validates AST_MAP coverage, compiles FIRST_2 and the LL(2)
check ONCE (LL2ConflictError on a conflicting edit), and memoizes.

-------------------------------------------------------------------------------
FILES
-------------------------------------------------------------------------------

    grammar.txt
        SYNTAX_DOC -- the prose specification of the rule-file language. It
        defers every production to the GRAMMAR dict and dominates all other
        prose.

    grammar.py
        The grammar: a terminal preamble (T.regex / T.captured / T.opaque
        objects, recorded in declaration order) and the GRAMMAR dict, one
        entry per rule. Element vocabulary: tuple = sequence, list =
        optional, OR sentinel between tuple elements = alternation, PLUS /
        STAR combinators, "<name>" rule reference, "literal" silent keyword.
        Rule names carry a functionality prefix (def-event, kind-container,
        cond-term, ref-has, elm-mode, list-arg, parens-decl, name-dotted).

    core/   grammar-agnostic machinery (no rule-language knowledge):

        combinators.py        OR sentinel, PLUS, STAR.
        ll2_grammar_spec.py   T terminal factories, the terminal database,
                              the compiled Rule/Branch/Operator specs.
        lexer.py              generated token spec: terminal database + the
                              silent keywords walked out of GRAMMAR, emitted
                              in tiers (framing; ':word'; 'word:'
                              longest-first; bare keywords; symbols; regex
                              classes). Pull-driven; hands '{' to the oracle.
        ll2_engine.py         FIRST_2 computation, LL(2) validation,
                              EngineParser -- the stackless driver. Builds
                              the canonical CST; applies transformers on
                              reduce.
        cst_nodes.py          OR_Node / SEQ_Node / PLUS_Node / STAR_Node --
                              the canonical CST. Optionals are OR_Nodes at
                              stable slots; silent terminals are dropped.
        operator_interface.py OR/SEQ/PLUS/STAR_Interface -- the operator
                              signal an AST node class derives from.
        span_oracle.py        SpanOracle ABC + SpanResult (neutral span
                              value: text, mode, begin) + Reference (segments,
                              begin) and the abstract collect_references --
                              the neutral vocabulary pass 2 resolves.
        diagnostic.py         Phase-tagged Diagnostic + DiagnosticReporter.

    ast_map.py
        The overlay: rule name -> constructor. Classmethods on the node
        classes for 1:1 rules; plain-value factories here (name-dotted
        segment lists, signatures, arg lists, parens, ref-member pairs, the
        kind dicts); dispatch functions here where the input decides the
        class -- the merged named tails (cause-named -> Cause | CauseRef,
        effect-named -> EventSpec | EffectRef, cond-term -> Comparison |
        BoolRef: the parens / the comparison tail decide) and the
        declaration family (the kind keyword decides: ReactorDecl /
        StructDecl / ContainerDecl / VariableDef); _passthrough for OR
        dispatch rules. validate_ast_map() guards full rule coverage at
        load time.

    ast_nodes.py
        Frozen dataclasses; every node stores 'begin' (source offset).
        TopLevel is the abstract base for RuleFile items: Namespace, Import,
        Causality, Mode, ModeGroup, StateMachine, ReactorDecl, StructDecl,
        ContainerDecl, VariableDef, EventDef, ClockDef, CauseDef, EffectDef.

    rule_parser.py
        compiled_grammar() / parse() / finalize_file(). finalize_file wraps
        the engine's top-level STAR node into the public RuleFile; any
        caller driving EngineParser directly finalises through it.

-------------------------------------------------------------------------------
(A) LEXER AND ORACLE HANDOFF
-------------------------------------------------------------------------------

The token spec is GENERATED: the terminal database plus the silent keywords
extracted from GRAMMAR. Trailing-colon keywords ('mode:') outrank the bare
captured keywords ('mode'), which outrank the identifier class. At each '{'
the lexer asks the oracle for the matching span under the Role the grammar
position carries (CONDITION / EXPRESSION / LVALUE / STATEMENT_BLOCK); a
malformed fragment is recovered -- error flagged, block token still produced.

-------------------------------------------------------------------------------
(B) GRAMMAR TABLE AND LL(2) GUARANTEE
-------------------------------------------------------------------------------

    "causality": ("on:", "<cause>", PLUS(("=>", "<effect>")))

At compile time FIRST_2 is computed for every rule; every OR and every
repetition continuation must be decidable from two lookahead tokens, else a
located LL2ConflictError. Most rules are LL(1); the second token decides
<arg> ('id =' named vs positional rvalue) and steers the merged named tails
('id .' continuation vs 'id (' parens vs bare).

DELIMITER DESIGN:

    'on:' block       no terminator; the effect loop ends at the first
                      non-'=>' token.
    <mode>            closed by ( 'until:' <cause> )+.
    <state>           body and untils optional; terminated STRUCTURALLY by
                      the next state-machine element or ':end'.
    <mode-group>      closed by ':end'.
    <state-machine>   closed by ':end'.
    <namespace>       'open:' ... ':close', nesting unrestricted.

-------------------------------------------------------------------------------
(C) CST AND THE AST OVERLAY
-------------------------------------------------------------------------------

The engine knows no AST: it builds OR/SEQ/PLUS/STAR nodes, children already
transformed (bottom-up). The overlay reads structure DIRECTLY: SEQ children
by stable slot, OR branches by triggered_index, repetitions off items,
optionals as OR_Nodes whose presence is a state. Single-terminal rules
(<guard-luau>, <mutation>, <report-string>) hand the raw leaf (SpanResult /
Token) to their factory.

-------------------------------------------------------------------------------
(D) AST SUMMARY
-------------------------------------------------------------------------------

    Causality      cause + ordered effects
    Cause          Trigger (name segments | system keyword) + optional guard
    CauseRef       'NAME(args)' reference to a CauseDef; trailing guard
                   recorded (legality pass 2)
    Condition      bracket-guard root; BoolOp / Not / Comparison / BoolRef
                   tree; OpaqueCode is the opaque-guard alternative
    EventSpec      'name(args)' emission     EffectRef  bare-name reference
    Spawn          '+! name(args) [in: C [via: <rvalue>]]'
    Unspawn        '-! name'                 ModeArming '! name(args)'
    Mutation / ReportString / InitBlock / DeinitBlock
    Mode / State   causalities, init, deinit, untils
    ModeGroup      modes, has_refs, init, deinit          (':end')
    StateMachine   states, has_refs, default, init, deinit (':end')
    HasRef         'has: <ref-member>'        DefaultRef 'default: <ref-member>'
                   (name segments + is_void; the two share <ref-member>)
    ReactorDecl    '<name> [sig] is: mode|state|mode_group|state_machine'
    StructDecl     '<name>(members) is: struct'
    ContainerDecl  '<name> is: container<cargs> [by: {lvalue}]'
    VariableDef    '<name> is: <type>(args) [by: {lvalue}]'
    EventDef / ClockDef / CauseDef / EffectDef
    Namespace      'open: <name-dotted> ... :close'
    Import         'import: "<file>" into: <name-dotted>' (recorded; mounted
                   by the semantic pass)
    Arg            optional name + value; kind LITERAL | LUAU | NAME
                   (NAME = a name-dotted segment list, resolved pass 2)
    OpaqueCode     one opaque span: text, mode, begin; get_references(oracle)
                   yields the span's Reference pairs lazily, cached

-------------------------------------------------------------------------------
(E) THE TEST SUITE (TEST/)
-------------------------------------------------------------------------------

Each test is an HWUT driver: '--hwut-info' lists choices; a choice's stdout is
compared byte-for-byte against its GOOD/ recording. The coverage and monkey
drivers derive their cases from the compiled grammar, so a new rule is
exercised with no test edit.

    test-lexer.py        tokens, dotted_names.
    test-engine.py       first_sets, ll2_ok, token_inventory,
                         name_dotted_args, cause_effect,
                         guards_and_inheritance.
    test-ast-signals.py  operator_table, signal_match, exemptions -- the
                         rule-operator / node-interface correspondence.
    cover-syntax-tree.py positive -- per rule, minimal valid variants, AST
                         printed with the producing input.
    cover-negative.py    negative -- per rule, mechanical malformations
                         (junk head, truncation, required-element omission);
                         diagnostics and recovery pinned.
    monkey-fuzz.py       deterministic grammar-walk fuzzing: deep, wide,
                         luau, balanced, states, spread, members profiles
                         (fixtures in monkey_data/, regenerated by
                         monkey-file-creator.py); depth_bomb (stackless
                         acceptance, 20000 levels); sprites (the generated
                         menagerie source, AST census).

    core/TEST/           grammar-agnostic machinery tests: test-lexer.py,
                         test-engine.py, test-cst.py (toy grammars only).
