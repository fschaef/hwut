SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
===============================================================================
core  --  grammar-agnostic engine machinery, parameterised by a grammar the
          outer layer supplies at run time.
===============================================================================

TOPOLOGY
-------------------------------------------------------------------------------

    diagnostic.py            symbol/ast.py
         ^                        ^
         |                        |
    lexer/lexer.py <------ parser_generator/
         (register_grammar,      (LL(2) engine, grammar spec, combinators,
          Token stream)           CST nodes, AST-map family, subspaces)

    Arrows point from user to used. parser_generator drives the lexer and
    reports through diagnostic; the lexer builds its token spec from
    parser_generator's terminal database; ast_map_family produces
    symbol/ast.NodeList. No module in core imports from language/.

THE PARTS
-------------------------------------------------------------------------------

    diagnostic.py     Phase (LEXER/PARSER/ANALYZER/SEMANTIC), Diagnostic
                      (phase, message, source_offset, fatal, tag),
                      DiagnosticReporter (report / has_fatal /
                      abort_if_fatal), FatalDiagnostics. report() always
                      appends; abort_if_fatal() is the one place a phase
                      boundary raises.
    lexer/            Pull-driven regex tokenizer; token spec generated
                      from the terminal database and the registered
                      grammar's string keywords. See lexer/README.txt.
    parser_generator/ Authoring combinators, the compiled grammar spec,
                      the LL(2) parse engine, the five CST node kinds,
                      the AST-map router family, grammar subspaces.
                      See parser_generator/README.txt (the manual).
    symbol/           The general AST vocabulary the semantic unit walks:
                      Node, NodeList, the Leaf kinds, the recipe slot.
                      See symbol/README.txt.

DATA FLOW
-------------------------------------------------------------------------------

    GRAMMAR (outer) --register_grammar--> lexer token spec
    GRAMMAR (outer) --Grammar(...)------> compiled Spec tree, LL(2) analysed

    source text --Lexer.next()--> Token stream --EngineParser--> CST
                                       (five node kinds, pruned)
    CST --transformer seam (Grammar._reduce)--> typed products
                                       (symbol/ast Node derivations)

    Every phase reports into one injected DiagnosticReporter; the caller
    invokes abort_if_fatal() at each phase boundary.

HOW TO RUN / TEST
-------------------------------------------------------------------------------

Two HWUT TEST directories under core:

    lexer/TEST/                python3 test-lexer.py --hwut-info
    parser_generator/TEST/     python3 test-engine.py --hwut-info
                               python3 test-cst.py --hwut-info
                               python3 test-ast-map-router.py --hwut-info
                               python3 test-role-hint.py --hwut-info

    Then per choice:  python3 test-X.py <choice>
    Output diffs byte-exact against GOOD/test-X.py--<choice>.txt.

POINTERS
-------------------------------------------------------------------------------

    ../README.txt                        the tree
    lexer/README.txt                     token spec, tiers, registration
    parser_generator/README.txt          THE PARSER CORE MANUAL
    parser_generator/RATIONALE.txt       core decisions (C-numbered)
    symbol/README.txt                    AST vocabulary
