===============================================================================
REACTIVE RULE ENGINE  --  HWUT 2.0
PARSER ARCHITECTURE
===============================================================================

MODULES AND RESPONSIBILITIES:

    parser.py
        Entry point. Orchestrates file reading, AST construction, and triggers 
        the semantic validation pass.

    lexer.py
        The Regex-based tokenizer. Yields standard tokens on demand and handles 
        the oracle boundary to extract opaque Luau blocks.

    ast_nodes.py
        Pure data structures defining the Abstract Syntax Tree. Every node 
        stores source file coordinates for provenance.

    state_machine.py
        The stackless, iterative descent logic. Consumes the token stream 
        from the lexer and constructs the AST nodes based on current state.

    validator.py
        Pass 2 semantic validation. Enforces domain logic constraints (e.g. 
        single init/deinit, state machine invariants) before transpilation.

-------------------------------------------------------------------------------
(A) ARCHITECTURAL OVERVIEW
-------------------------------------------------------------------------------

OBJECTIVE:
    Parse the rule-file language into an Abstract Syntax Tree (AST) while 
    seamlessly handling opaque Luau code blocks ('{ ... }') via the 'luau-ast' 
    oracle.

The parser is a single-pass, stackless state machine. It does not use 
recursive function calls (e.g., 'parse_mode()' calling 'parse_causality()'), 
eliminating Python call stack limits. Instead, it relies on a 
heap-allocated 'state_stack' and an on-demand Regex Lexer. 

The architecture consists of three distinct layers:

    1. The Lexer (Regex Generator): Tokenizes the input string on demand.
    2. The Oracle Boundary: Halts lexing to allow the external 
       'luau_fragment.py' module to extract verbatim Luau code blocks.
    3. The Iterative State Machine: Consumes tokens, validates grammar 
       sequences, and builds the AST nodes.

-------------------------------------------------------------------------------
(B) THE LEXER (TOKENIZER)
-------------------------------------------------------------------------------

The lexer uses a single compiled regular expression with named capture groups
('(?P<NAME>pattern)'). This allows Python's C-backend to rapidly 
identify token boundaries.

THE ORACLE HANDOFF:

    When the Lexer yields a 'LUAU_OPEN' token, the parser pauses the token 
    stream. It invokes 'find_matching_brace(source_text, offset, 
    role, oracle)'. The returned 'closing_idx' is used to slice 
    the raw Luau string, create a 'LUAU_BLOCK' token, and forcefully advance 
    the Lexer's internal cursor past the closing brace.

-------------------------------------------------------------------------------
(C) THE ABSTRACT SYNTAX TREE (AST) NODES
-------------------------------------------------------------------------------

The AST is built using Python dataclasses. Every node must store 
its 'source_line' and 'source_column' to enable accurate error reporting and 
feed the 'Source2TargetLocationMapper' during code generation.

-------------------------------------------------------------------------------
(D) THE ITERATIVE STATE MACHINE (THE PARSER)
-------------------------------------------------------------------------------

The parser loops over the token stream, applying logic based on the top value
of the 'state_stack'.

STATE STACK DYNAMICS:

    'EXPECT_TOP_LEVEL'
        Routes to 'IN_MODE', 'IN_STATE_MACHINE', 'IN_CAUSALITY', 
        'IN_EVENT_DEF', or 'IN_CLOCK_DEF' based on the starting keyword.

    'IN_CAUSALITY'
        Expects a trigger ID. If '&' is encountered, pushes 
        'EXPECT_GUARD'. If '=>' is encountered, pushes 
        'EXPECT_EFFECT'. If 'off' is encountered, pops back to 
        the previous state.

    'EXPECT_GUARD'
        Sets the Oracle role to 'Role.CONDITION'. Expects a 
        'LUAU_BLOCK'. Pops upon receipt.

    'EXPECT_EFFECT'
        Reads the token following '=>'. Determines if it is an 
        event emit, mode arm (prefixed by '+'), report string, or a 
        'LUAU_BLOCK' (mutation).

    'IN_MODE'
        Parses the signature. Loops over elements (causalities, 
        'init', 'deinit'). When 'until' is encountered, parses the 
        cause and appends to the 'untils' list. Pops when the mode 
        block ends (which is implicitly when a new top-level keyword is 
        encountered).

-------------------------------------------------------------------------------
(E) SEMANTIC VALIDATION (PASS 2)
-------------------------------------------------------------------------------

After the AST is constructed, a validation pass ensures domain logic
constraints are met before Code Generation begins:

    1. Mode Validation: Ensure a Mode contains no more than one 'init' and 
       one 'deinit'.
       
    2. State Machine Validation:
       - Ensure exactly one 'default' assignment exists.
       - Ensure all member-modes (Modes prefixed with 'SM_NAME.') terminate 
         their 'untils' list strictly with 'until switched'.
         
    3. Reference Checks: Verify that every '+ MODE()' arming effect 
       references a Mode that is actually defined in the AST.
