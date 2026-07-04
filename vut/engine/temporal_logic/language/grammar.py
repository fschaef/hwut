"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer

RULE-FILE GRAMMAR -- formal spec of the settled language.

Authority: LANGUAGE.txt (mechanics) and RATIONALE.txt (R-1..R-22, the why).
This file is the formal grammar. Regions below carry ONE-LINE remarks naming the
language element; full prose lives in LANGUAGE.txt, rationale in RATIONALE.txt.

______________________________________________________________________________
DELTA LEDGER -- revisions against the DESIGN-chat grammar.py (ratification
pending, REACTIVE-ENGINE-REBUILD pass 1). The DESIGN grammar had never been
compiled; on the extracted core engine it raised 178 LL(2) conflicts and its
reference forms could not parse a single LANGUAGE.txt entity name. Each delta
preserves the documented source language; where the parser now accepts a WIDER
surface, the narrowing is a pass-2 check already anticipated by SEMANTICS.txt
("The parser accepts a wider language").

D-1  name-ref replaces <name-bound> in reference positions.
     DESIGN's "signature"/"call" were built on <name-bound>, which REQUIRES an
     e./b./a./c./s. head (R-9) -- so no bare entity name ("Polling",
     "OPERATION_IMPOSSIBLE") could parse. Per LANGUAGE §8 the dotted NAMESPACE
     path and the binding-qualified MEMBER access are two distinct notions;
     references need both: "name-ref" := <name-dotted> OR <name-bound>.
     "signature" declares a BARE id (definition under the current scope).

D-2  ONE expression grammar ("expr"); condition/algebr become sort VIEWS.
     <algebr> OR <condition> at a consumption site is not LL(k) for any k
     ("c.x + 1" vs "c.x + 1 < 2" differ arbitrarily far right): 151 of the 178
     conflicts. The parse is now one layered grammar (or > and > not >
     comparison > add > mul > unary > atom, ternary as TOP tail); the SORT
     (truth vs number, R-4's two worlds) is a semantic property of the parsed
     tree, checked in pass 2. "condition" and "algebr" survive as view rules
     over <expr> so every reference site and role reads unchanged.

D-3  Unified cause: (<name-ref> [args] | ~ENTRY | ~EXIT) [when: <condition>].
     DESIGN's cause = <cause-explicit> OR <call> shared arbitrary-length
     prefixes (both admit the same name tokens). One form now parses every
     cause; event-vs-cause-ref kind and the no-guard-on-a-cause-ref rule are
     pass-2 (SEMANTICS 2, 5).  <cause-explicit> remains for the def-cause
     body and the groove arm, where no <call> competes.

D-4  data-access base left-factored: <name-ref> [<parens-arg>].
     DESIGN's <name-bound> OR <call> made a bare bound name match both
     branches identically (call's parens are optional). Presence of the parens
     is the discriminator; no second branch.

D-5  Top-level "declaration" drops its [<parens-decl>].
     With D-1, a causality's cause-ref and a parameterised declaration both
     start (id, "(") -- irreducibly conflicting at LL(2) without a merged
     opaque-parens head. No LANGUAGE.txt example exercises a parameterised
     declaration; the surface is REMOVED rather than factored around. If the
     construct is ever wanted, it returns via an A-12 kind-opaque head.
     Declarations inside has: blocks are unaffected in every exemplified use.

D-6  ROLES keyed per pattern, as the engine contract requires.
     DESIGN grouped routing roles under a "<ROUTING>" pseudo-key the
     vocabulary validator cannot resolve (it keys by terminal object or by
     the referenced rule's "<name>"). Same vocabulary, engine-conformant keys.

D-7  "file" rule added: a rule-file is STAR(<top-level>); parse starts there.
     DESIGN carried no file-level rule; the engine needs a start symbol that
     covers the whole input.
D-10 The global ROLES vocabulary dict is DROPPED (rule-scoped roles).
D-11 decl-arg gains a Python-style VALUE DEFAULT: name [: type] [= algebr].
     Arity law (SEMANTICS 20): required-exact, defaulted-optional; bare use
     is a reference, not a call.
D-12 Terminator law: ';' terminates a statement/effect; '}' terminates
     itself -- never '};'. The effect chain is right-recursive ("effects"):
     block-final causalities end at '}', spawn-final take ';'. The 'effect'
     rule is retired.
D-13 emit-step takes ';' (a clockwork statement among ';'-terminated
     statements) -- resolves the pass-1 doc mismatch in the DOCUMENT'S
     favour.
     Role meaning is scoped to the rule that applies it; per-SEQ uniqueness is
     the engine's compile-time law, and factory role access is STRICT (a role
     the rule does not carry raises at the read). A misspelled role therefore
     surfaces on the first parse of its rule -- closer to use than the old
     load-time vocabulary gate, which is retired for this grammar (the core
     capability remains, unused).
______________________________________________________________________________

Authoring surface (combinators):
    (a, b, ...)      sequence (a bare tuple)
    [a, b, ...]      optional (a bare list; single element = that element optional)
    (a, OR, b, ...)  alternation (OR sentinel placed BETWEEN branches)
    PLUS(x) STAR(x)  one-/zero-or-more
    "<name>"         reference to grammar rule 'name'
    "<name(role)>"   reference carrying an advisory role hint (R-8)
    "literal"        a silent keyword spelled as written (colon-terminated, R-11)
    t_...            a terminal object (preamble below)
    { TOP: ..., m: ...}  a SUBSPACE: TOP holds the rule's pattern, other keys are
                         member rules named by path ('expr/add'); see R-8.
"""

from ..core.parser_generator.combinators import OR, PLUS, STAR, TOP
from ..core.parser_generator.ll2_grammar_spec import T


# == terminals ================================================================
# Numeric literals: float BEFORE int (maximal munch, R-13/R-4).
t_re_float   = T.regex(r'\d+\.\d+')
t_re_int     = T.regex(r'\d+')
t_re_string  = T.regex(r'"[^"]*"')
t_re_id      = T.regex(r'[a-zA-Z_]\w*')

# == reserved events (R-10: lifecycle; non-external) ==========================
t_kw_entry   = T.captured("~ENTRY")
t_kw_exit    = T.captured("~EXIT")

# == operator terminals =======================================================
# LEXING ORDER LAW: captured terminals lex in DECLARATION order (the lexer's
# tier-4 scan). Every MULTI-character operator is therefore declared BEFORE any
# single-character operator that is its prefix ("=x=>", "=>", "==" before "=";
# "+=" before "+"; ".." before the "." symbol keyword) -- maximal munch by
# construction, verified by the acceptance smoke.

# -- multi-character operators, longest first ---------------------------------
# effect markers (R-1, §2.2): captured so they precede "=" in the scan order
t_op_cancel  = T.captured("=x=>")
t_op_spawn   = T.captured("=>")
# bridge B1 (comparison: algebraic -> condition, R-4)
t_op_eq      = T.captured("==")
t_op_ne      = T.captured("!=")
t_op_le      = T.captured("<=")
t_op_ge      = T.captured(">=")
# mutation compounds (R-13: statement world, leaf)
t_op_addeq   = T.captured("+=")
t_op_subeq   = T.captured("-=")
t_op_muleq   = T.captured("*=")
t_op_diveq   = T.captured("/=")
# range operator (R-13: count loop bounds "a .. b"); two dots, distinct from "."
t_op_range   = T.captured("..")
# count-loop counter-type keywords (R-13): colon-terminated (R-11), role-bearing
# so the semantic unit routes the counter type. Declared HERE, before the bare
# type names "int"/"float" and before ":", so "int:" lexes as one token.
t_kw_int_loop   = T.captured("int:")
t_kw_float_loop = T.captured("float:")

# -- single-character operators ------------------------------------------------
t_op_lt      = T.captured("<")
t_op_gt      = T.captured(">")
# algebraic world: arithmetic operators (R-4)
t_op_add     = T.captured("+")
t_op_sub     = T.captured("-")
t_op_mul     = T.captured("*")
t_op_div     = T.captured("/")
# plain assignment (R-13); also the "=" of the count loop and the named arg
t_op_assign  = T.captured("=")
# bridge B2 (ternary: condition -> algebraic, R-4)
t_op_quest   = T.captured("?")
# bracket index (R-16: data-access)
t_br_open    = T.captured("[")
t_br_close   = T.captured("]")
# bare colon (declaration "name: type", decl-arg, the ternary's ":"). REGEX,
# not captured/string: a ":" string keyword lands in the lexer's leading-colon
# tier, whose pattern (":word\b") demands a word char after the colon and so
# never matches a lone ":". A regex terminal uses its pattern verbatim in the
# final tier -- after every colon-terminated keyword (has:/is:/int:) -- so a
# bare ":" is lexed only where no keyword claimed it.
t_op_colon   = T.regex(r':')

# -- condition world: boolean operators (R-4; identifier keywords, no munch
#    interaction with the symbol operators above) ------------------------------
t_kw_and     = T.captured("and")
t_kw_or      = T.captured("or")
t_kw_not     = T.captured("not")
# clockwork reserved-event cause (R-20, R-22): named like ~ENTRY/~EXIT (R-10).
# ~ELSE = the DEFAULT/fallthrough arm: fires when NO other arm matched (like
# "case: _"), so it does not shadow specific arms. (No ~TICK: the groove is
# already tick-paced, so a condition-only arm "when: <cond>" waking on the tick
# is the tick-default; naming ~TICK was redundant.)
t_kw_else    = T.captured("~ELSE")
# null emit target (R-20): "=> ~NONE" emits nothing, passes one tick. ~NONE is
# an emit TARGET only, never a trigger. Named like the ~ reserved-event family.
t_kw_none    = T.captured("~NONE")

# == built-in type keywords (declarations, has:) ==============================
t_kw_int     = T.captured("int")
t_kw_float   = T.captured("float")
t_kw_string  = T.captured("string")
t_kw_bool    = T.captured("bool")
t_kw_true    = T.captured("true")
t_kw_false   = T.captured("false")
# aggregate type keywords (R-19: plain aggregation, no member functions)
t_kw_list    = T.captured("list")
t_kw_dict    = T.captured("dict")
t_kw_struct  = T.captured("struct")
# == match patterns (R-13) ====================================================
t_kw_wild    = T.captured("_")           # default arm: case: _ { ... }
t_re_glob    = T.regex(r'"[^"]*"')       # string-wildcard pattern (glob)


GRAMMAR = {

    # == file (D-7): a rule-file is a sequence of top-level items =============
    "file":       (STAR("<top-level>"),),

    # == top level ============================================================
    # A rule-file is a sequence of definitions, causalities, scopes, and imports.
    "top-level":  ("<character(character)>", OR, "<aspect(aspect)>", OR, "<behavior(behavior)>",
                   OR, "<causality(causality)>", OR, "<causality/def-cause(cause-def)>",
                   OR, "<declaration(declaration)>",
                   OR, "<namespace(namespace)>", OR, "<import(import)>"),

    # == namespace (R-18, §8): a named scope; nests unrestricted ==============
    # open: <dotted> { ... }  -- brace-delimited (R-12; replaces the prior :close).
    # Re-openable and nestable; names are scoped to it. Semantics: SEMANTICS.txt.
    "namespace":  ("open:", "<name-dotted(namespace)>", "{", STAR("<top-level>"), "}"),

    # == import (R-18, §8): mount a file/url under a namespace ================
    # import: "<quoted-path>" as: <dotted>  -- recorded by the parser, mounted by
    # the semantic pass. (Prior spelling was "into:"; now "as:".)
    "import":     ("import:", t_re_string("path"), "as:", "<name-dotted(namespace)>"),

    # -- dotted namespace path: a plain dotted name, NOT a binding-qualified
    #    member access (R-9). It has no e./b./a./c./s. head.
    "name-dotted": (t_re_id("name"), STAR((".", t_re_id("name")))),

    # == character (R-7, R-10, §7): aggregates concurrent aspects in has: =====
    "character":  (["~"], "character:", "<signature(signature)>",
                   ["is:", "<call(character)>", STAR((",", "<call(character)>"))],
                   ["has:", "<decl-block>"]),

    # == aspect (R-7→R-16amend, R-10, R-20, §6): governs the one active behavior
    # No does:: the brace already delimits the body (R-12). An aspect body is
    # EITHER the mutually-exclusive behaviour set OR a clockwork (R-20).
    "aspect":     (["~"], "aspect:", "<signature(signature)>",
                   ["is:", "<call(aspect)>", STAR((",", "<call(aspect)>"))],
                   ["has:", "<decl-block>"],
                   "{", "<aspect-body(body)>", "}"),
    # aspect-body: behaviours (XOR set) OR a clockwork (paced coroutine, R-20).
    "aspect-body": ("<behavior-list(behaviors)>", OR, "<clockwork(clockwork)>"),
    "behavior-list": (PLUS("<behavior>"),),

    # == behavior (R-7→R-16amend, R-10, §3): aggregates causalities ===========
    # No does:: the brace already delimits the body (R-12).
    "behavior":   (["~"], "behavior:", "<signature(signature)>",
                   ["is:", "<call(behavior)>", STAR((",", "<call(behavior)>"))],
                   ["has:", "<decl-block>"],
                   "{", PLUS("<causality>"), "}"),

    # == causality (R-1, R-5, R-6, R-15, §2): cause --> one-or-more effects ===
    # Subspace: the cause/effect family. TOP is the causality; members carry the
    # cause forms, the named-cause definition, and the effect forms.
    "causality": {
        TOP:            ("<cause(cause)>", "<effects>"),

        # -- cause (R-5, D-3): ONE parse shape -- a name (bare / dotted /
        #    bound / lifecycle), optional arguments, optional guard. Kind
        #    (raw event vs cause-ref) and the no-guard-on-a-cause-ref rule
        #    are pass-2 (SEMANTICS 2, 5).
        "cause":        (("<name-ref>", ["<parens-arg>"],
                          OR, t_kw_entry, OR, t_kw_exit),
                         ["when:", "<condition>"]),
        "cause-explicit": ("<event>", ["when:", "<condition>"]),
        # event (R-21): an event TYPE is a bare name (a global signal name), OR a
        # binding-qualified member for character-scoped events, OR a lifecycle
        # event. Bare-name is the common form; the bound form (c.tick) names an
        # event carried on an entity.
        "event":        ("<name-dotted(event)>", OR, t_kw_entry, OR, t_kw_exit),

        # -- named cause definition (R-5): carries its own guard -------------
        "def-cause":    ("cause:", "<signature>", "<cause-explicit>", ";"),

        # -- effect (R-1, R-6, R-15): marker + (spawn | command-block) -------
        # call and code are disjoint (R-6 D1); periodic modifiers ride a spawn.
        # D-12 terminator law: ';' terminates a statement/effect; '}'
        # terminates itself -- never '};'. The chain is right-recursive so the
        # FINAL effect decides: block-final ends at '}', spawn-final takes ';'.
        "effects":      ("<effect-marker>",
                         (("<code(causality)>", ["<effects>"]),
                          OR,
                          ("<spawn(spawn)>", (";", OR, "<effects>")))),
        "effect-marker": (t_op_spawn, OR, t_op_cancel),

        # -- spawn (R-15): an entity/event call, optionally recurring + named -
        "spawn":        ("<call>", ["every:", "<numeric>", ["as:", t_re_id("name")]]),
    },

    # == values (R-4, D-2): ONE parse grammar; sorts are pass-2 views =========
    # R-4's two worlds and two bridges are unchanged as SORTS: comparison lifts
    # number -> truth (bridge B1); the ternary tail selects a number by a truth
    # (bridge B2). The alternation <algebr> OR <condition> is not LL(k) (the
    # deciding comparison operator sits arbitrarily far right), so the PARSE is
    # one layered grammar and world-membership is a property of the parsed tree,
    # enforced where each site's sort demands it (guard/if/match: truth;
    # args/bounds/index: number).
    "expr": {
        TOP:        ("<or>", [t_op_quest, "<expr>", t_op_colon, "<expr>"]),  # bridge B2 tail
        "or":       ("<and>", STAR((t_kw_or,  "<and>"))),
        "and":      ("<not>", STAR((t_kw_and, "<not>"))),
        "not":      ([t_kw_not], "<cmp>"),
        # bridge B1: zero comparisons -> number-sorted; one or more -> truth
        # (chaining allowed: a < b < c == a < b and b < c).
        "cmp":      ("<add>", STAR(("<op-cmp>", "<add>"))),
        "op-cmp":   (t_op_eq, OR, t_op_ne, OR, t_op_le,
                     OR, t_op_ge, OR, t_op_lt, OR, t_op_gt),
        "add":      ("<mul>", STAR(("<op-add>", "<mul>"))),
        "mul":      ("<un>",  STAR(("<op-mul>", "<un>"))),
        "un":       ([t_op_sub], "<atom>"),
        "atom":     ("<group(group)>", OR, "<number(literal)>",
                     OR, t_kw_true, OR, t_kw_false,
                     OR, "<data-access(operand)>"),
        "group":    ("(", "<expr>", ")"),
        "op-add":   (t_op_add, OR, t_op_sub),
        "op-mul":   (t_op_mul, OR, t_op_div),
    },

    # -- sort views (D-2): the truth view and the number view over <expr>.
    #    Reference sites keep their sorted name; pass-2 enforces the sort.
    "condition":  ("<expr>",),
    "algebr":     ("<expr>",),

    "numeric":    ("<algebr>",),
    "number":     (t_re_float, OR, t_re_int),

    # == data-access (R-16, D-4): the place layer below the value worlds ======
    # Reaches a value out of a structure: a name (bare / dotted / bound), an
    # optional call-argument list, then chained index steps. Consumed by the
    # value world, by the mutation lvalue, by the foreach: source, and by the
    # comprehension from:. An lvalue IS a data-access; pass-2 restricts the
    # lvalue head to a binding (SEMANTICS 9).
    "data-access": {
        TOP:        ("<base>", STAR("<step>")),
        "base":     ("<name-ref>", ["<parens-arg>"]),
        "step":     (t_br_open, "<algebr>", t_br_close),   # single index; chains
    },

    # == collection (R-17): a third value SORT -- construct & consume only =====
    # No operators, no bridges (R-4 unchanged). Constructed by a comprehension
    # (or a literal); consumed by foreach:/index-base/from:/argument/RHS.
    "collection": {
        TOP:            ("<comprehension>",),
        # [ element  with: vars from: src [if: cond]  ... ]   (chained generators)
        "comprehension": (t_br_open, "<element>", PLUS("<generator>"), t_br_close),
        "generator":    ("with:", "<var-list>", "from:", "<source>", ["if:", "<condition>"]),
        "var-list":     (t_re_id("var"), STAR((",", t_re_id("var")))),
        # source / element are any value sort; a collection element nests.
        "source":       ("<data-access(access)>", OR, "<collection(comprehension)>"),
        "element":      ("<expr>", OR, "<collection(comprehension)>"),
    },

    # == command-block (R-6, R-13, R-14): imperative body; no event emission ==
    # Subspace: the statement world. TOP is the command-block. ONE statement
    # tier: every loop is bounded by definition (foreach:, from:/to:) -- there is
    # no unbounded while: -- and exit: is forward-only (targets a LATER label),
    # so no statement can diverge or form a back-edge. The command-block admits
    # statements and closes in an optional tail ladder of EXIT-LABELS.
    # Exit-region model (R-14, kernel goto-label idiom; "goto considered harmful"
    # made safe): "exit: label" DEFINES a bare drop-through label (no body, C-label
    # semantics -- control falls through it to what follows). "dropto: label" is
    # the forward-only JUMP to such an exit.
    # Pass-2 checks (see SEMANTICS.txt): exit-labels may be defined ONLY at the
    # outermost function body (not inside loops, if/elif/else, match, or any
    # nested block); "dropto: L" targets an exit defined LATER (forward-only);
    # the label exists.
    "code": {
        TOP:            ("{", STAR("<statement>"), "}"),

        "statement":    ("<mutation(mutation)>", OR, "<if(if)>", OR, "<match(match)>",
                         OR, "<foreach(foreach)>", OR, "<count(count)>",
                         OR, "<break(break)>", OR, "<continue(continue)>", OR, "<dropto(dropto)>",
                         OR, "<exit-label>"),

        # -- the brace body (R-12: every block is "{ }") --------------------
        # Nested bodies admit no exit-label (outermost-only, pass-2).
        "block":        ("{", STAR("<statement>"), "}"),

        # -- mutation (R-13 leaf): lvalue OP value; lvalue is a data-access ---
        # RHS is any value sort (number / truth via <expr>, or a collection --
        # disjoint at "[", R-16/R-17).
        "mutation":     ("<lvalue>", "<op-mut>", "<rhs>", ";"),
        "lvalue":       ("<data-access(operand)>",),
        "rhs":          ("<expr>", OR, "<collection(comprehension)>"),
        "op-mut":       (t_op_assign, OR, t_op_addeq, OR, t_op_subeq,
                         OR, t_op_muleq, OR, t_op_diveq),

        # -- if/elif/else (R-13): brancher (not the ternary) ----------------
        "if":           ("if:", "<condition>", "<block>",
                         STAR(("elif:", "<condition>", "<block>")),
                         ["else:", "<block>"]),

        # -- match/case (R-13): scrutinee vs literal|range|glob; opt default -
        "match":        ("match:", "<algebr>", "{", PLUS("<case>"), "}"),
        "case":         ("case:", "<pattern>", "<block>"),
        "pattern":      ("<number(literal)>", OR, "<range(range)>", OR, t_re_glob("glob"), OR, t_kw_wild),
        "range":        ("<number>", "to:", "<number>"),

        # -- foreach (R-13, bounded): iterate a collection; var is a local --
        "foreach":      ("foreach:", t_re_id("var"), "in:", "<coll-source>", "<block>"),
        "coll-source":  ("<data-access(access)>", OR, "<collection(comprehension)>"),

        # -- counting loop (R-13, bounded): a TYPED counter declared inline.
        #    <count-type>: <id> = <begin> .. <end> [step: <step>] { ... }
        #    The counter is a typed bare local; bounds/step are algebraic;
        #    inclusive; default step +1 (negative step counts down).
        "count":        ("<count-type>", t_re_id("var"), t_op_assign,
                         "<algebr>", t_op_range, "<algebr>",
                         ["step:", "<algebr>"], "<block>"),
        # -- count-type: the counter's type. Role-bearing so the semantic unit
        #    routes the counter type; extensible (more numeric types later).
        #    "int:"/"float:" (colon, R-11) are distinct from the bare type names
        #    "int"/"float" used in declarations.
        "count-type":   (t_kw_int_loop("int"), OR, t_kw_float_loop("float")),

        # -- loop control (R-14): break:/continue: are unlabelled -----------
        "break":        ("break:", ";"),
        "continue":     ("continue:", ";"),

        # -- dropto (R-14): forward-only jump to a later exit-label ----------
        "dropto":       ("dropto:", t_re_id("label"), ";"),
        # -- exit-label (R-14): a bare drop-through label (no body, C-label);
        #    definable only at the outermost body (pass-2).
        "exit-label":   ("exit:", t_re_id("label"), ";"),
    },

    # == clockwork (R-20, §11): an aspect body run as a paced coroutine ========
    # Mental model: asyncio. A clockwork is a coroutine on the engine's event
    # loop; its suspension points are "await on a resource available":
    #   => <emit>   emit, then AWAIT the tick        (await queue.put; await tick)
    #   => ~NONE    emit nothing, pass one tick      (await sleep(0) / yield)
    #   groove:{..} AWAIT-and-repeat over causes      (async for / looping select)
    #   beat: n     an arm that fires every n TICKS    (a recurring pulse)
    # Arm causes: a named event (gated by its own when:), ~ELSE (default: fires
    # when no other arm matched), or a
    # tick-default arm "when: <cond>" (the groove is tick-paced, so a condition-
    # only arm wakes on the tick). Statements run IN SEQUENCE; where a step both
    # acts and suspends, the EFFECT happens first, then the wait ("=> x" emits,
    # THEN awaits the tick; a groove arm runs its body, THEN the groove resumes).
    # A borrowed <statement> (R-13) runs WITHIN a step and is EMISSION-IMPOTENT
    # (R-6 ban untouched); emission lives ONLY in the "=>" step.
    "clockwork": {
        TOP:            ("clockwork:", "<causality/cause(tick)>",
                         "{", PLUS("<clockwork-statement>"), "}"),

        "clockwork-statement": ("<code/statement(statement)>",   # R-13, emission-impotent
                         OR, "<emit-step(emit)>",
                         OR, "<groove(groove)>"),

        # -- emit-step: "=> <call>" emit + await tick; "=> ~NONE" pass a tick --
        "emit-step":    (t_op_spawn, ("<call(emission)>", OR, t_kw_none),
                         ";"),                     # D-13; ~NONE = emit nothing

        # -- groove: a repeating blocking select over cause-arms (implicitly
        #    or-ed): keep reacting to whichever cause fires, again and again.
        #    Exited by break:/dropto:/exit: from within an arm. A one-shot wait
        #    is "groove: { ... break: }" (an arm that breaks).
        #    asyncio analogue: async-for / looping select() over channels.
        "groove":       ("groove:", "{", PLUS("<clock-arm>"), "}"),

        # -- clock-arm: a cause (R-5, carries when:), the ~ELSE default arm, a
        #    tick-default "when: <cond>", or "beat: n" (every n ticks). Arms are
        #    or-ed; each has a clockwork-code body. --------------------------
        "clock-arm":    ("<clock-cause>", "{", STAR("<clockwork-statement>"), "}",
                         OR, "beat:", t_re_int("beat"), "{", STAR("<clockwork-statement>"), "}"),
        "clock-cause":  ("<causality/cause-explicit(cause)>",       # a named event, gated
                         OR, (t_kw_else, ["when:", "<condition>"]),   # ~ELSE = default/fallthrough
                         OR, ("when:", "<condition>")),               # tick-default: on the
                                                                      # tick, gated by <cond>
    },

    # == declarations (has:) ==================================================
    "decl-block": ("{", PLUS("<declaration>"), "}"),
    # D-5: no [<parens-decl>] on a declaration (see the delta ledger).
    "declaration": (t_re_id("name"), t_op_colon, "<type>", ";"),

    # -- type (R-19): a built-in, a named type, or a plain aggregate ----------
    "type":       ("<type-built-in(type-builtin)>", OR, "<type-list(list)>",
                   OR, "<type-dict(dict)>", OR, "<type-struct(struct)>",
                   OR, t_re_id("type")),
    "type-built-in": (t_kw_int, OR, t_kw_float, OR, t_kw_string, OR, t_kw_bool),

    # -- aggregation types (R-19): plain VARIABLE-TYPED containers, NO type
    #    parameters and NO member functions. Element/key/value/field types are
    #    dynamic; constraints are a deliberate future addition.
    "type-list":   (t_kw_list,),                            # list  (of anything)
    "type-dict":   (t_kw_dict,),                            # dict  (anything -> anything)
    "type-struct": (t_kw_struct, "{", PLUS("<field>"), "}"), # struct { x; y; ... }
    "field":       (t_re_id("name"), ";"),                  # a named slot, untyped

    # == reference and definition (R-8, D-1): shared signature / call pair ====
    # A SIGNATURE declares a BARE name under the current scope (namespacing is
    # the open: block's job, R-18). A CALL references a name: bare, dotted
    # (namespace path), or binding-qualified (member), with optional arguments.
    "signature":  (t_re_id("name"), ["<parens-decl>"]),
    "call":       ("<name-ref>", ["<parens-arg>"]),

    # -- name-ref (D-1, D-8): every reference parses as ONE dotted-name shape.
    #    Whether the head is a binding (e./b./a./c./s., R-9), a namespace path,
    #    or a bare entity name is a SEMANTIC property of the resolved head, not
    #    a lexical class: reserving e/b/a/c/s as keywords would forbid any
    #    member or entity named "a" or "s". Pass-2 reads the head (SEMANTICS 4,
    #    9, 12).
    "name-ref":   ("<name-dotted(name)>",),

    "parens-arg":  ("(", ["<list-arg>"], ")"),
    "list-arg":    ("<arg>", STAR((",", "<arg>"))),
    "arg":         ("<algebr>", OR, (t_re_id("arg-name"), t_op_assign, "<algebr>")),

    "parens-decl": ("(", ["<list-decl>"], ")"),
    "list-decl":   ("<decl-arg>", STAR((",", "<decl-arg>"))),
    "decl-arg":    (t_re_id("arg-name"), [t_op_colon, "<type>"],
                    [t_op_assign, "<algebr>"]),  # D-11; default type float (§2.1)

}
# R-9 (no leading-dot form; every member access names its binding) is enforced
# in pass-2 over the dotted head (D-8): the grammar carries no binding keywords.
