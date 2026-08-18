SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
===============================================================================
temporal_logic  --  the rule-file transpiler front half: a grammar-agnostic
                    parser core plus the rule-file language bound onto it.
===============================================================================

TOPOLOGY
-------------------------------------------------------------------------------

    temporal_logic/
        core/                    grammar-agnostic machinery
            diagnostic.py        Diagnostic / DiagnosticReporter / Phase
            lexer/               pull-driven tokenizer, generated token spec
            parser_generator/    LL(2) engine, grammar spec, CST nodes,
                                 AST-map family (the parser core manual
                                 lives in its README)
            symbol/              general AST vocabulary (Node / NodeList /
                                 the Leaf kinds)
        language/                the rule-file language: grammar, typed
                                 products, AST map, parser facade, the
                                 module-spine units declare and elaborate

    core/ names no rule of the rule-file language; language/ parameterises
    it with GRAMMAR, AST_MAP, and the role vocabulary.

THE PARTS
-------------------------------------------------------------------------------

    core/        The engine machinery: lexer, LL(2) parse engine, CST node
                 tree, AST-map family, diagnostics, general AST vocabulary.
                 Every piece is driven by data handed in from outside.
    language/    The rule-file language layer: the three-file contract
                 (grammar.py / ast_nodes.py / ast_map.py), the rule_parser
                 facade, the module-spine units, and the document set
                 (LANGUAGE.txt, SEMANTICS.txt, RATIONALE.txt).

DATA FLOW  (the module spine, front half)
-------------------------------------------------------------------------------

    SourceModule --parse--> ParsedModule --declare--> DeclaredModule
                                                          |
                                                      elaborate
                                                          v
                                                    SemanticModule

    parse       language/rule_parser.py   runs the core engine over the
                                          rule-file text; typed AST out
    declare     language/declare.py       publishes the module's export_db
    elaborate   language/elaborate.py     mounts imports, resolves every
                                          reference to a recipe (Access)

    SemanticModule is the disk serialisation boundary. The back half
    (link / pack / emit) is outside this component.

HOW TO RUN / TEST
-------------------------------------------------------------------------------

Three HWUT TEST directories, one per tested unit:

    core/lexer/TEST/
    core/parser_generator/TEST/
    language/TEST/

Per TEST directory, per test file:

    python3 test-X.py --hwut-info        lists the choices
    python3 test-X.py <choice>           output diffs byte-exact against
                                         GOOD/test-X.py--<choice>.txt

POINTERS
-------------------------------------------------------------------------------

    core/README.txt                      core overview
    core/parser_generator/README.txt     THE PARSER CORE MANUAL
    core/parser_generator/RATIONALE.txt  core decisions (C-numbered)
    language/README.txt                  language-layer overview
    language/RATIONALE.txt               rule-file decisions (D-/A-/G-)
    language/LANGUAGE.txt                the language, element by element
    language/SEMANTICS.txt               pass-2 checks (1)-(20), severity
                                         REJECT / WARN per entry
