===============================================================================
REACTIVE RULE ENGINE  --  HWUT 2.0
PARSER CORE  --  the grammar-agnostic LL(2) machinery
===============================================================================

   authoring          compile               analyse (load-time gates)
   combinators  ----> *_Spec tree  ------->  FIRST_2  ->  LL(2) check
   (a,OR,b) [x]       (Grammar.rules)                     ROLES check
   PLUS STAR                                                  |
        |                                                     v
        |                                              .--------------.
   tokens <--- Lexer <--- source                       | EngineParser |
                 |                                      |  (stackless) |
                 v  '{...}' spans                       '--------------'
            SpanOracle                                         |
           (E_SpanMode)                                        v
                                                          CST node tree

The core owns everything that does not depend on a particular grammar: the
terminal and operator vocabulary, the compiler from authored rules to a uniform
spec tree, the FIRST_2 / LL(2) analysis, the lexer, the span-oracle boundary,
the stackless parse driver, and the canonical CST it builds. A grammar (the
rule-file GRAMMAR dict, one level up) is data fed to this machinery; the core
names no rule and no keyword of its own.

-------------------------------------------------------------------------------
DIAGNOSTICS  (diagnostic.py)
-------------------------------------------------------------------------------
A DiagnosticReporter collects every lexer and parser Diagnostic of a run, each
tagged with a Phase and a source offset. It is the one sink threaded through the
lexer and the engine; nothing else carries error state.

-------------------------------------------------------------------------------
SPAN ORACLE  (span_oracle.py)
-------------------------------------------------------------------------------
SpanOracle is the abstract boundary for OPAQUE SPANS -- the '{ ... }' text the
control plane does not parse. The lexer hands the oracle each span with the
E_SpanMode the grammar position demands (CONDITION / EXPRESSION / LVALUE /
STATEMENT_BLOCK); the oracle returns the matching-brace extent. E_SpanMode is a
core-owned enum, so the core hard-codes no embedded language. A source with no
spans never calls the oracle.

-------------------------------------------------------------------------------
TERMINALS AND THE SPEC TREE  (ll2_grammar_spec.py)
-------------------------------------------------------------------------------
The compiled grammar is a uniform tree of frozen-in-practice '*_Spec' nodes.
The leaves:

  Terminal_Spec   a terminal: its lexeme specification AND its seat in the tree.
                  IDENTITY is _name() -- shape plus every distinguishing field
                  -- and the object is INTERNED on it (one Terminal_Spec per
                  _name()), so the engine compares terminals by object identity
                  and the lexer stamps the same object on Token.kind. The object
                  is immutable after construction and content-hashed on _name(),
                  so it serves as a value key (see the ROLES vocabulary below).
                  Built through the T factory: T.regex / T.string / T.captured /
                  T.opaque.
  Rule_Spec       a non-terminal: its name, its compiled pattern, and (after
                  analysis) its FIRST_2 set.

The operators (one per authoring combinator):

  SEQ_Spec   a sequence of children.        OR_Spec   an alternation of branches.
  OPT_Spec   zero-or-one body.              PLUS_Spec one-or-more body.
  STAR_Spec  zero-or-more body.

  Tagged_Spec  a TRANSPARENT wrapper carrying one body plus an advisory role
               string (the role-hint facility). Its nullable / FIRST_2 / expand
               delegate straight to the body, so it adds nothing to lexing, the
               LL(2) analysis, or the value stream; the role is metadata read
               off the spec by position. See "ROLE HINTS" below.

FIRST_2 sets are computed by an iterative fixpoint over the tree (no recursion
on grammar depth); merge_first2 combines a prefix set with a follower set under
the two-token bound.

-------------------------------------------------------------------------------
OPERATOR INTERFACES  (operator_interface.py)
-------------------------------------------------------------------------------
Shape-identity signals (OR_Interface, SEQ_Interface, PLUS_Interface,
STAR_Interface, OPT_Interface) shared by the generic CST nodes and the typed
AST nodes one level up. A consumer asks "what shape is this node" by interface,
independent of which hierarchy minted it.

-------------------------------------------------------------------------------
AUTHORING COMBINATORS  (combinators.py)
-------------------------------------------------------------------------------
The surface a grammar is written in: a bare tuple is a SEQUENCE, a bare list is
an OPTIONAL, the OR sentinel between tuple elements is an ALTERNATION, PLUS(x)
and STAR(x) are the repetitions, a terminal object is a leaf, and a bare
'<name>' string is a rule reference. compile_element lowers an authored rule
into the '*_Spec' tree, deferring leaf resolution (terminal object / '<name>'
reference / '<name(role)>' tagged reference / bare-string keyword) to the
engine, which owns the terminal table and the rule map.

-------------------------------------------------------------------------------
CST NODES  (cst_nodes.py)
-------------------------------------------------------------------------------
Five frozen nodes -- OR_Node, OPT_Node, SEQ_Node, PLUS_Node, STAR_Node -- one
per operator. The engine reduces every parse to a tree of these by default; this
is a PRUNED CST (silent terminals contribute nothing). Each carries the
producing rule's name, or None for an inline operator. The ABSENT sentinel marks
a position that produced no surviving value.

-------------------------------------------------------------------------------
LEXER  (lexer.py)
-------------------------------------------------------------------------------
A single compiled regular expression, assembled from the terminal table in
declaration-tier order, tokenizes the control plane. On reaching a span opener
the lexer hands control to the SpanOracle, splices the returned span as one
token, and resumes. Output is a token stream; each Token carries its Terminal
kind (by identity) and source offsets.

-------------------------------------------------------------------------------
ENGINE  (ll2_engine.py)
-------------------------------------------------------------------------------
Grammar compiles the authored grammar dict into the Rule_Spec map, analyses it,
and runs the load-time gates. Construction modes: 'actions' (legacy hand-builder
reduce), 'cst=True' (canonical CST only), or 'transformers' (CST plus a partial
rule-name -> callable overlay). Three gates run at compile time:

    FIRST_2 / LL(2)   merge the sets, scan every alternation for a two-token
                      collision; a clash raises LL2ConflictError, located by
                      rule.
    ROLES (optional)  validate every role hint against the supplied vocabulary
                      (see below); a violation raises RoleVocabularyError.

EngineParser is the driver: a STACKLESS interpreter over an explicit heap
work-stack (ELEM / REDUCE / CST_REDUCE / LOOP items), so parse depth is bounded
by memory, not the interpreter recursion limit. It primes a two-token lookahead
window, expands each spec node into work items, consumes terminals and spans,
and reduces finished frames into CST nodes (then through the transformer overlay
where one is registered).

-------------------------------------------------------------------------------
ROLE HINTS AND THE ROLES VOCABULARY  (ll2_grammar_spec.py + ll2_engine.py)
-------------------------------------------------------------------------------
A grammar position may carry an advisory ROLE: a plain string naming the kind a
reference or terminal is expected to denote. Two authoring forms lower to a
Tagged_Spec: a terminal CALL, t_re_id("event"), and a reference SUFFIX,
'<name-dotted(event)>'. The tag is recorded on the spec and walked by position;
it is OUTSIDE terminal identity and the value stream -- lexing, interning, the
FIRST_2 analysis, and every reduced CST value are identical to the bare form.

The allowed roles are declared once, in a ROLES vocabulary the grammar supplies
to Grammar(roles=...): a dict mapping each role-bearing pattern -- a terminal
object, or a '<name>' reference string -- to the tuple of roles it may carry.
Terminals serve as keys directly (interned, immutable, content-hashed).
_validate_roles walks the compiled grammar, resolves each Tagged_Spec to its key
(the wrapped terminal, or '<rule-name>'), and checks the carried role against
the declared tuple. An undeclared pattern or an unlisted role raises
RoleVocabularyError at load time. The check is opt-in: with no roles dict, hints
are not validated.
