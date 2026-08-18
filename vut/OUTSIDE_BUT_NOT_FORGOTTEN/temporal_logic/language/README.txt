SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
===============================================================================
language  --  the rule-file language layer: the three-file contract, the
              parser facade, and the module-spine units declare / elaborate.
===============================================================================

TOPOLOGY
-------------------------------------------------------------------------------

The three-file contract:

    grammar.py          ast_nodes.py         ast_map.py
    (the data:           (the products:       (the wiring: one raw
     GRAMMAR dict,        typed Node           entry per rule; the
     terminal              derivations)         load_ast_map gate)
     bindings)
         \                    |                    /
          \                   |                   /
           +-------------- rule_parser.py --------+
                           (the facade)
                                |
    module_states.py            |            declare.py    elaborate.py
    (the spine types) <---------+---------------+---------------+

Document set:

    LANGUAGE.txt        the language, element by element, mechanics only
    SEMANTICS.txt       pass-2 checks (1)-(20), each with an explicit
                        severity: [REJECT] or [WARN]
    RATIONALE.txt       settled rule-file decisions (D-/A-/G- entries)

THE PARTS
-------------------------------------------------------------------------------

    grammar.py       The GRAMMAR dict: every rule of the rule-file
                     language in the authoring combinators, with
                     terminal bindings and advisory role hints. Regions
                     carry one-line remarks; full prose is LANGUAGE.txt.
                     A delta ledger at the head records each revision
                     against the DESIGN-chat grammar (D-1..).
    ast_nodes.py     The typed products. Every product IS-A core Node;
                     leaf classification leans on the core kinds
                     (DeclarationLeaf / ReferenceLeaf / ConstantLeaf).
                     Siting rule: a one-rule product carries a from_cst
                     classmethod; a shared product is built by a
                     function in ast_map.py; OR routing is an OrMap;
                     passthrough is PASS.
    ast_map.py       AST_MAP: one raw entry per rule, keyed by flattened
                     name. A callable entry is a SEQ factory; a dict
                     entry is an OR route table. load_ast_map(grammar)
                     runs three checks in one pass -- coverage in both
                     directions (LookupError), entry kind against the
                     rule's compiled shape (TypeError), normalisation
                     into the core family (dict -> OrMap, callable ->
                     SeqMap) -- and returns the engine-ready transformer
                     map. A factory's product shape is asserted by the
                     ast_shape GOOD suite at first parse.
    rule_parser.py   The facade. compiled_grammar() builds once, on
                     first call: register_grammar(GRAMMAR) seeds the
                     lexer's token spec, Grammar(GRAMMAR, cst=True,
                     start="top-level") compiles and analyses, then
                     load_ast_map supplies the transformers. parse()
                     returns the typed tree for a source text;
                     parse_module() wraps it as the spine transition
                     SourceModule -> ParsedModule; finalize_file() is
                     the single exit producing the typed ModuleRoot.
                     Importing the facade has no side effects.
    module_states.py The spine types: SourceModule, ParsedModule,
                     DeclaredModule, SemanticModule. SemanticModule IS-A
                     DeclaredModule; wherever an export_db is peeked, a
                     SemanticModule stands in. SemanticModule is the
                     disk serialisation boundary; link / pack / emit are
                     outside this component.
    declare.py       declare_module: ParsedModule -> DeclaredModule.
                     Publishes the export_db -- the declared surface:
                     name, kind, scope, abstractness, members -- and
                     touches no reference. Imports are recorded under
                     their alias, not mounted. The F-6 gate: any parser
                     diagnostic in the reporter makes declare_module
                     raise (a software violation raises; a content
                     fault diagnoses). Duplicates in one scope are
                     REJECTed via the reporter; the first publication
                     stays authoritative. ExportDB / ExportEntry /
                     Member are the surface types.
    elaborate.py     elaborate_module: DeclaredModule -> SemanticModule.
                     Step 0 mounts every recorded import: the peer's
                     export_db is read into the symbol table under the
                     alias; a missing peer is a REJECT. Step 1 resolves
                     every ReferenceLeaf to ONE recipe (an Access seated
                     into '_access'), first hit wins: (1) binding head
                     e/b/a/c/s -- every level has a default instance in
                     the open scope; (2) local frames, innermost
                     outward; (3) the table, scope-aware outward,
                     longest declared prefix wins, remaining segments
                     become the residue, verified as far as the
                     declared surface reaches; (4) raw event, only at a
                     cause target or an emission target. Anywhere else
                     an unresolved name is a REJECT. The same walk
                     carries the settled SEMANTICS checks (2, 5, 7, 9,
                     17, 19); 17 is the WARN. Access and SymbolTable
                     are the carrier types.

DATA FLOW  (the module spine, front half)
-------------------------------------------------------------------------------

    rule-file text
        |  parse_module            (rule_parser.py; typed tree out,
        v                           faults recorded, F-6 input state)
    ParsedModule
        |  declare_module          (declare.py; export_db published)
        v
    DeclaredModule ----peeked by peers' elaborate (declared surface only)
        |  elaborate_module        (elaborate.py; step 0 mount,
        v                           step 1 resolve + settled checks)
    SemanticModule                 (serialisation boundary)

    Ordering law: every module of a build declares before any module
    elaborates.

HOW TO RUN / TEST
-------------------------------------------------------------------------------

    cd TEST
    python3 test-grammar.py --hwut-info        compile, constructs,
                                               ast_shape
    python3 test-module-spine.py --hwut-info   states, parse_module,
                                               parse_faulty
    python3 test-declare.py --hwut-info        exports, reopen,
                                               duplicates, gate
    python3 test-elaborate.py --hwut-info      mount_recipes, rejects,
                                               warn17, gate
    python3 test-X.py <choice>                 diffs byte-exact against
                                               GOOD/test-X.py--<choice>.txt
    Fixture rule files live in TEST/fixtures/.

POINTERS
-------------------------------------------------------------------------------

    ../README.txt                        the tree
    ../core/README.txt                   the machinery this layer
                                         parameterises
    ../core/parser_generator/README.txt  THE PARSER CORE MANUAL
    RATIONALE.txt                        rule-file decisions (D-/A-/G-)
    LANGUAGE.txt                         the language, mechanics
    SEMANTICS.txt                        pass-2 checks and severities
