SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
===============================================================================
core/parser_generator  --  THE PARSER CORE MANUAL: authoring combinators,
                           compiled grammar spec, LL(2) engine, CST nodes,
                           AST-map family, transformer seam, diagnostics.
===============================================================================

TOPOLOGY
-------------------------------------------------------------------------------

    combinators.py          subspace.py
    (authoring forms)       (flatten / resolve)
          |                       |
          | compile_element       | flat rule map, flattened names
          v                       v
    ll2_grammar_spec.py ----> ll2_engine.py <---- ../lexer/lexer.py
    (Spec tree, FIRST_2,      (Grammar, EngineParser)   (Token stream)
     terminal factory T)          |
                                  | builds, bottom-up
                                  v
    operator_interface.py --> cst_nodes.py --> ast_map_family.py
    (shape identity)          (five node kinds,  (SeqMap/OrMap/OptMap/
                               NodeAbsent)        StarMap/PlusMap, PASS)

THE PARTS
-------------------------------------------------------------------------------

combinators.py -- the authoring vocabulary a GRAMMAR dict is written in:

    (a, b, ...)       a sequence (SEQ); a bare tuple
    [a, b, ...]       an optional (OPT); a bare list
    (a, OR, b, ...)   an alternation; OR is a sentinel between branches,
                      a branch that is itself a sequence is a nested tuple
    PLUS(x)           x one or more times
    STAR(x)           x zero or more times
    t_...             a terminal object (T.string / T.regex / T.captured)
    "<name>"          a reference to another rule
    "literal"         a bare-string keyword: a silent terminal
    TOP               the key of a subspace's own pattern (see subspace.py)

    compile_element(element, ctx) lowers an authored body to the Spec
    tree; leaf resolution (terminal, reference, keyword) is delegated to
    ctx, the engine, which owns the terminal database and the rule map.

ll2_grammar_spec.py -- the compiled grammar as a uniform SpecNode tree:

    Rule_Spec          one per rule (flattened name)
    Terminal_Spec      one per terminal leaf
    SEQ_Spec / OR_Spec / OPT_Spec / STAR_Spec / PLUS_Spec
                       one per operator; each carries first2_set,
                       nullable, the conflict scan, and expand
    Tagged_Spec        a transparent wrapper holding one body element plus
                       an advisory role string; FIRST_2, nullable, the
                       conflict scan, and expand all delegate to the body.
                       Authoring forms: a terminal call t("role") and a
                       reference suffix '<name(role)>'.
    TerminalFactory T  T.string / T.regex / T.captured / T.framing mint
                       Terminal objects into TERMINAL_DB; the framing four
                       are t_fr_comment, t_fr_ws, t_fr_mismatch, t_fr_eof.
    rule_shape(rule)   SEQ / OR / OPT / STAR / PLUS / TERMINAL / FORWARD:
                       the shape of a rule's top operator.

    A Spec describes; it never holds a parse result. One Spec yields many
    CST nodes across parses.

subspace.py -- grammar subspaces and path namespaces:

    A grammar value is a pattern, or a subspace: a dict whose TOP key
    holds the rule's own pattern and whose other keys are member rules.
    Every rule has a flattened name, its path joined by '/' ('algebr/
    shift'); a root rule keeps its bare name. flatten() lowers a nested
    grammar to the flat rule map keyed by flattened name, plus a scope
    map; a
    duplicate flattened name is a load error. resolve() binds a reference:
    a path-spelled name resolves from any scope; a bare name resolves
    against the writing rule's subspace first, then the enclosing
    subspaces, then the root. Subspaces nest to arbitrary depth.

ll2_engine.py -- the table-driven LL(2) engine:

    Grammar(grammar_dict, actions=None, start=None, cst=False,
            transformers=None, roles=None)
        Flattens subspaces, compiles every rule body via combinators,
        runs the FIRST_2 fixpoint (_analyse), seals the memo, then
        validates role uniqueness and, when 'roles' is given, the role
        vocabulary. Compile-time errors, each collecting every
        violation before raising:
            LL2ConflictError        the grammar is not LL(2)
            RoleUniquenessError     one SEQ gives two positions the same
                                    advisory role (D-18)
            RoleVocabularyError     a role hint is outside the declared
                                    ROLES vocabulary (D-10)
        Three reduction modes, mutually exclusive:
            actions        legacy per-rule hand-builders
            cst=True       the canonical CST and nothing else
            transformers   a PARTIAL dict rule-name -> callable; implies
                           CST mode. Each rule with an entry has fn(node)
                           called on its finished CST node and the result
                           forwarded; a rule with no entry passes its CST
                           node through untouched. There is no
                           completeness check.
        Grammar._reduce is THE TRANSFORMER SEAM: the single call site
        'fn(node)' where a typed product replaces a CST node.

    EngineParser(source_text, reporter, grammar)
        Drives the Lexer pull-wise with two tokens of lookahead. Branch
        choice consults the alternation's first2_set (choose_alt);
        presence tests consult starts(). parse() runs the start rule to
        end-of-file.

    Frame  the engine's reduction stack record: collected values, their
           roles, and the construct's begin offset.

cst_nodes.py -- the canonical pruned CST, five frozen node kinds:

    OR_Node    triggered_index (0-based fired branch), child (the
               branch's reduced value, NodeAbsent for an all-silent
               branch), role (the fired branch's advisory role or None).
               route_key(address) answers int-against-triggered_index or
               str-against-role.
    OPT_Node   present (True iff the optional fired), child (the body's
               surviving value, NodeAbsent when none survived). Presence
               is a state on the node; a fired optional over an
               all-silent body is present=True, child=NodeAbsent.
               or_else(default) reads child-if-present, else default.
    SEQ_Node   children: one reduced value per surviving grammar
               position; roles rides parallel, one advisory role or None
               per entry. node[i] is positional; node["role"] is STRICT
               role access -- a role the sequence does not carry raises
               AssertionError naming the carried roles. An absent
               optional survives at its slot as OPT_Node(present=False).
    PLUS_Node  items: the reduced repetitions, never empty.
    STAR_Node  items: the reduced repetitions, possibly empty.

    Every node carries 'name': the producing rule's name at a
    rule-reduce site, None for an inline operator inside a rule body;
    and 'begin': the construct's start offset. Silent terminals leave no
    entry (the pruning); captured and regex terminals survive as Tokens.
    NodeAbsent is a single falsey sentinel instance, a distinct type.

operator_interface.py -- shape identity over the CST:

    Operator_Interface and its five derivations OR_/OPT_/SEQ_/PLUS_/
    STAR_Interface signal WHICH grammar operator built a node. The
    generic CST nodes are the interface bearers; a typed AST product
    carries no operator accessors. The interface asserts structural
    identity, not a callable accessor contract.

ast_map_family.py -- the typed map-entry wrappers (D-19), one per shape:

    SeqMap(fn)               SEQ: one constructor receiving the finished
                             SEQ_Node
    OrMap({address: leaf})   OR: a route table, branch address (role,
                             index, or tuple of either) -> leaf; the
                             fired branch picks the leaf
    OptMap(fn)               OPT: transform the child when present;
                             NodeAbsent otherwise, fixed by the machinery
    StarMap(item_fn)         STAR: an applier -- one item constructor
                             applied uniformly; product NodeList, empty
                             when nothing matched
    PlusMap(item_fn)         PLUS: as StarMap; the NodeList is never
                             empty
    PASS                     a route leaf forwarding the routed value
                             unchanged

    A map value is callable and applied as fn(node) at the transformer
    seam, exactly like a plain factory. Its '.shape' names the rule
    shape it belongs on; the load-time shape gate lives in the outer
    layer (language/ast_map.load_ast_map).

DATA FLOW
-------------------------------------------------------------------------------

Compile (once):

    GRAMMAR dict --flatten--> flat rule map --compile_element--> Spec tree
        --_analyse (FIRST_2 fixpoint)--> sealed Grammar
        --role uniqueness / role vocabulary checks--> ready

Parse (per source text):

    Token stream --EngineParser (LL(2) branch choice, bottom-up reduce)-->
    per rule: finished CST node --Grammar._reduce: transformer fn(node)-->
    typed product (or the CST node itself where no transformer is
    registered)

Diagnostics:

    lexer mismatch          non-fatal Diagnostic + mismatch Token
    parse fault             fatal Diagnostic; _resync skips at least one
                            token, then advances to the next top-level
                            anchor, a consumed ':end', or end-of-file;
                            parsing continues with the recovered items
    phase boundary          the caller invokes reporter.abort_if_fatal()

HOW TO RUN / TEST
-------------------------------------------------------------------------------

    cd TEST
    python3 test-engine.py --hwut-info          engine: FIRST_2, LL(2)
                                                conflicts, parse drive
    python3 test-cst.py --hwut-info             CST shapes, strict roles,
                                                overlay, signals
    python3 test-ast-map-router.py --hwut-info  the map family per shape
    python3 test-role-hint.py --hwut-info       Tagged_Spec transparency,
                                                vocabulary check
    python3 test-X.py <choice>                  diffs byte-exact against
                                                GOOD/test-X.py--<choice>.txt

POINTERS
-------------------------------------------------------------------------------

    RATIONALE.txt                        core decisions (C-numbered)
    ../README.txt                        core overview
    ../lexer/README.txt                  the token stream feeding parse()
    ../symbol/README.txt                 the Node/NodeList vocabulary the
                                         appliers produce into
    ../../language/README.txt            the outer layer supplying GRAMMAR,
                                         AST_MAP, and ROLES
