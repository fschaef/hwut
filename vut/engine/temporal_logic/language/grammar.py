"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer

RULE-FILE GRAMMAR -- formal spec of the settled language.

Authority: LANGUAGE.txt (mechanics) and RATIONALE.txt (R-1..R-40, the why).
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
     pass-2 (SEMANTICS 2, 5).  <cause-explicit> remains for the named-cause
     tail (cause-tail, D-19), where no <call> competes.

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
D-14 String literals enter the expression grammar (an atom branch): guards
     and mutations compare and carry strings.
D-15 The membership operator: 'x in c' and 'x not in c' join the comparison
     tier (op-cmp). Bare 'in' becomes a captured keyword string; 'not'
     stays silent everywhere. Equality over containers is structural
     (semantics side; the grammar was already sufficient).
D-16 'foreach:' is renamed 'for:' (rule 'code/for', node For) -- one
     iteration verb.
D-17 The count loop gains the ENUMERATION arm:
     '<type>: i with: x from: <iterable> [start: i0]' -- i counts in the
     counter's type from i0 (default 0), x walks the iterable; the '='
     range arm and the 'with:' arm split LL(2)-clean on the token after
     the counter name.
D-18 DOCSTRINGS: a triple-quoted string (three double-quotes on each
     side, multi-line) PRECEDES the definition it documents (character,
     aspect, behavior, named cause); a docstring followed by no definition
     is the MODULE docstring, lawful only as the file's first item
     (SEMANTICS 22). The terminal is declared before the plain string so a
     triple quote lexes as one docstring token.
D-19 NAME-FIRST definitions (F-4, ratified): '<name> : <kind-tail>' is the
     ONE definition form -- 'ON : behavior { ... }', 'hot : cause(threshold)
     ...', 'Rover : character(speed) is: ...'. The kind words character/
     aspect/behavior/cause become BARE reserved words (the colon moved to the
     head); the parameter list follows the kind word, so no name-led item
     carries '(' before its ':' and the top level splits LL(2)-clean on token
     two: ':' opens a named item (definition or declaration -- ONE factored
     head, <named-item>, decided at the token after ':'), anything else is a
     causality. '~' qualifies the kind word ('GENERAL : ~behavior'). The AST
     is UNCHANGED: the factories reunite head name and tail parameters into
     the same Signature product.
D-20 A docstring before a top-level DECLARATION is parseable (a consequence
     of D-19's factored head: the parser cannot split definition from
     declaration at the docstring's optional). LANGUAGE 1.2 admits no such
     subject; the semantic layer rejects it (SEMANTICS 22).
D-21 The exit-label is spelled ':name:' (F-5 ruling, R-24): colon, name,
     colon -- self-terminating (the second colon delimits, like '}'; no ';').
     'dropto:' is unchanged; the keyword 'exit:' leaves the label duty and is
     reserved for the work construct's fault egress. No lexer change: an
     undeclared trailing-colon word falls apart into ID + bare ':', and the
     bare ':' is the final-tier regex terminal.
D-22 The tick-paced clockwork left the grammar (R-25): the aspect body is
     behaviours-only again; the clockwork subspace (emit-step, groove,
     clock-arm, beat:) and the reserved events ~ELSE/~NONE are removed.
     'groove:' SURVIVES as a construct by ruling -- waiting is an essential
     element of the forthcoming pull-driven clockwork -- and is reserved
     (LANGUAGE 1.1) until that construct lands with the work integration.
D-23 The aspect gains a PANEL (clockwork-style signature) in the kind
     parens: '(knows: <decl-args> signals: <signal-decls>)' -- knows: are
     the parameters (the former plain parens-decl), signals: the declared
     fault set (recorded; checks land with the work construct).
D-24 The named-argument binder is '=>' (C-1 ruling: 'port => value'), the
     ONE direction-neutral port binder of the work construct's port-map
     form -- '=' remains the declaration DEFAULT marker ('boost = 1' in a
     parameter list). Supersedes D-11's call-site '='.
D-25 The work-construct slice enters the grammar (LANGUAGE 11/12/13):
     named-item gains the class/work/clockwork branches; the panel grows to
     its five sections (knows/takes/gives/ticks/signals); class bodies hold
     member works; work and clockwork bodies are code-statement sequences;
     finish:/exit:/tick: are code STATEMENTS at any nesting depth, lawful
     only inside work/clockwork bodies (SEMANTICS 23).
D-26 The AWARE surface: a mutation's targets may be a comma list and its
     terminator may be replaced by the handler "else: { arms }" (block-
     final); an arm is '[variant[(fields)]] => (block | exit: | ;)'; the
     for:-loop gains the consumption arm 'from: [give] <source>' with a
     trailing handler (LANGUAGE 12.6/13.5).
D-27 Semi-declaration and completion (LANGUAGE 11.3): the work-tail's
     panel is OPTIONAL -- 'name : work' alone inside a class body is the
     brief listing; the top level gains '+class.ext : work ...' and
     '-class : work ...' completion heads (captured '+'/'-' operators,
     LL(2)-clean beside expressions: statement position never opens with
     an operator... at top level nothing else opens with one either). The
     lexer's block-comment opener admits '#{' directly (whitespace now
     optional), so a semi-declaration may carry '#{...}' where the panel
     will be. Reverses the pinned lexer choice "'#{' without whitespace is
     a line comment".
D-31 The catch-region form ':label: => { ... }' (B-1, R-39): the elseto:
     target's own syntax, distinct from the bare drop-through label --
     the two accounts of labels read differently at the definition site.
D-30 'Nothing' enters as an expression atom (R-38): assignable to KNOWN
     holders only -- the had world is Nothing-free by construction; the
     narrowing law is SEMANTICS 28. The relation words prefix containers:
     'have list'/'know list' (custody / views; bare = value container).
D-29 The success terminal is 'give:' (R-37, renaming finish: -- the
     keyword names the act: the gives-bundle leaves). 'destruct:' is a
     statement ending a having explicitly: 'destruct: <object>()' calls
     the object's disposal work, ';'-closed or with an else:-handler. A
     dtor-def head may carry '()' after the class name: the EXPLICIT flag
     (SEMANTICS 27).
D-28 Named arguments are 'name = value' again (FR ruling, R-34): D-24's
     '=>' binder is REVERTED. '=>' keeps the effect marker and the handler
     arm; '=' serves both the declaration default and the call-site named
     argument, distinguished by position (panel vs parens-arg). The
     port-map's OUTPUT association is an OPEN question again (disc-9 C-1
     residual) -- it does not pre-decide here.
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
t_re_doc     = T.regex(r'"""(?:[^"]|"(?!""))*"""')  # D-18: BEFORE t_re_string
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
t_kw_in      = T.captured("in")       # D-15: the membership operator

# == built-in type keywords (declarations, has:) ==============================
t_kw_int     = T.captured("int")
t_kw_float   = T.captured("float")
t_kw_string  = T.captured("string")
t_kw_bool    = T.captured("bool")
# D-30 (R-38): 'Nothing' -- the one noun for non-existence. Assignable to
# KNOWN holders only; the had world is Nothing-free by construction (0.5).
t_kw_nothing = T.captured("Nothing")
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
    # D-19: every name-led ':' item (definition or declaration) parses through
    # ONE factored rule, <named-item>; a top-level causality never carries ':'
    # after its head name, so the two branches split LL(2)-clean on token two.
    "top-level":  ("<named-item(named)>",
                   OR, "<ctor-def(ctor)>", OR, "<dtor-def(dtor)>",
                   OR, "<causality(causality)>",
                   OR, "<namespace(namespace)>", OR, "<import(import)>",
                   OR, "<documented(documented)>"),                    # D-18

    # == named item (D-19, F-4): ONE definition form, name first =============
    # <name> ':' <kind-tail>  -- "name is a <kind> about ...". The kind word is
    # BARE (the colon moved to the head); parameters follow the kind word
    # ('hot : cause(threshold) ...'), mirroring the has:-declaration
    # 'name: type;', whose type-tail is the fifth branch: definition and
    # top-level declaration are ONE head, decided at the token after ':'.
    # '~' (abstract, R-10) qualifies the kind word; a named cause admits none.
    "named-item": (t_re_id("name"), t_op_colon,
                   ((["~"], "character", "<character-tail(character)>"),
                    OR,
                    (["~"], "aspect", "<aspect-tail(aspect)>"),
                    OR,
                    (["~"], "behavior", "<behavior-tail(behavior)>"),
                    OR,
                    ("cause", "<cause-tail(cause-def)>"),
                    OR,
                    ("class", "<class-tail(class)>"),
                    OR,
                    ("work", "<work-tail(work)>"),
                    OR,
                    ("clockwork", "<clockwork-tail(clockwork)>"),
                    OR,
                    ("<type(declaration)>", ";"))),

    # == completion definitions (D-27, LANGUAGE 11.3): the marker asserts the
    # role R-30 reads off the panel -- '+class.ext' a CONSTRUCTION WORK
    # (several, hence the extension), '-class' THE disposal work (one, no
    # extension); marker and panel must agree (SEMANTICS 25).
    "ctor-def":   (t_op_add, t_re_id("class"), ".", t_re_id("ext"),
                   t_op_colon, "work", "<work-tail(work)>"),
    # D-29: '()' after the class name is the EXPLICIT flag (R-37): the
    # class's destruction is WRITTEN at every site ('destruct:'), so the
    # disposal work MAY declare signals -- every site answers them.
    "dtor-def":   (t_op_sub, t_re_id("class"), ["(", ")"],
                   t_op_colon, "work", "<work-tail(work)>"),

    # == class (R-29, LANGUAGE 11; D-25) ======================================
    # is: inheritance; has: custody members; knows: view members; the body
    # holds MEMBER WORKS -- role by panel: a member work giving the class is
    # its CONSTRUCTION WORK, one taking it its DISPOSAL WORK (R-30).
    "class-tail": (["is:", "<call(class)>", STAR((",", "<call(class)>"))],
                   ["has:", "<decl-block>"],
                   ["knows:", "<decl-block>"],
                   ["{", PLUS("<member-work>"), "}"]),
    "member-work": (t_re_id("name"), t_op_colon, "work", "<work-tail(work)>"),

    # == work (LANGUAGE 12; D-25) =============================================
    # Panel, then the body: statements of the code subspace plus the work
    # terminals. finish: and exit: are STATEMENTS of the work body only; the
    # semantic layer holds their laws (SEMANTICS 23).
    # D-27: the panel is OPTIONAL -- 'name : work' alone is a class body's
    # SEMI-DECLARATION (brief listing; the complete definition must follow,
    # SEMANTICS 25); panel without body remains the SPEC (12.1).
    "work-tail":  (["<panel>"], ["{", STAR("<code/statement>"), "}"]),

    # == handler (LANGUAGE 12.6; D-26): the else:-block is a match ===========
    # Arms: '<variant>[(fields)] => <action>'; a bare '=>' is the default arm
    # (at most one, last -- pass-2). Actions: a block, an exit:, or ';' (the
    # arm-level shrug). Exhaustiveness/dead-arm are semantic (SEMANTICS 24).
    "handler":    ("{", STAR("<arm>"), "}"),
    # An arm's head is OPTIONAL: absent = the bare '=>' default arm.
    "arm":        ([(t_re_id("variant"), ["<arm-fields>"])],
                   t_op_spawn, "<arm-action(action)>"),
    "arm-fields": ("(", [t_re_id("field"), STAR((",", t_re_id("field")))], ")"),
    "arm-action": ("<code/block(block)>", OR, "<code/exit-stmt(exit)>",
                   OR, "<arm-shrug(shrug)>"),
    "arm-shrug":  (";",),

    # == clockwork (LANGUAGE 13; D-25) ========================================
    # A work body extended by tick: (deliver the ticks: bundle, suspend until
    # the next pull). groove: awaits its host's rebuild (R-25(3)).
    "clockwork-tail": ("<panel(panel)>", ["{", STAR("<code/statement>"), "}"]),

    # == documented definition (D-18, D-20): a docstring PRECEDES its subject =
    # """...""" <named-item> -- the docstring rides the subject's product
    # ('doc' field). A docstring whose next token opens no named item is the
    # MODULE docstring (first item of the file, by law SEMANTICS 22 -- the
    # parser admits it anywhere top-level, the semantic layer holds the
    # first-position law). D-20: the factored head makes a docstring before a
    # top-level DECLARATION parseable; LANGUAGE 1.2 admits no such subject, so
    # the semantic layer rejects it (SEMANTICS 22).
    "documented": (t_re_doc("doc"), ["<named-item(named)>"]),

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

    # == kind tails (D-19): what follows the kind word of a definition ========
    # Each tail is the definition MINUS its head name: '(params)?' first (the
    # parameter list rides the kind word: 'drive : behavior(gain) ...'), then
    # the kind's own sections. The head name and '~' live in <named-item> /
    # <behavior-def>; the factories reunite them into ONE Signature product
    # (AST unchanged, D-19).

    # == character (R-7, R-10, §7): aggregates concurrent aspects in has: =====
    "character-tail": (["<parens-decl>"],
                   ["is:", "<call(character)>", STAR((",", "<call(character)>"))],
                   ["has:", "<decl-block>"]),

    # == aspect (R-7→R-16amend, R-10, R-25, §6): governs the one active behavior
    # No does:: the brace already delimits the body (R-12). An aspect body is
    # the mutually-exclusive behaviour set (the tick-paced clockwork left the
    # language, R-25/D-22; its successor rides the work construct). The panel
    # (D-23) is the clockwork-style signature: "knows:" declares the
    # parameters, "signals:" the declared fault set -- signals are RECORDED;
    # their checks land with the work construct.
    "aspect-tail": (["<panel>"],
                   ["is:", "<call(aspect)>", STAR((",", "<call(aspect)>"))],
                   ["has:", "<decl-block>"],
                   "{", PLUS("<behavior-def>"), "}"),
    # panel (D-23): sectioned signature -- both sections optional, order fixed.
    # panel (D-23, D-25): the five sections in fixed order, each optional.
    # knows/takes are inputs (acquaintance / custody), gives the outputs,
    # ticks the per-tick outputs (clockworks), signals the fault set.
    "panel":       ("(", ["knows:",   "<decl-arg>", STAR((",", "<decl-arg>"))],
                         ["takes:",   "<decl-arg>", STAR((",", "<decl-arg>"))],
                         ["gives:",   "<decl-arg>", STAR((",", "<decl-arg>"))],
                         ["ticks:",   "<decl-arg>", STAR((",", "<decl-arg>"))],
                         ["signals:", "<signal-decl>", STAR((",", "<signal-decl>"))],
                    ")"),
    "signal-decl": (t_re_id("name"), ["<parens-decl>"]),

    # == behavior (R-7→R-16amend, R-10, §3): aggregates causalities ===========
    # No does:: the brace already delimits the body (R-12). <behavior-def> is
    # the full name-first form (D-19), the shape an aspect body repeats.
    "behavior-def": (t_re_id("name"), t_op_colon, ["~"],
                     "behavior", "<behavior-tail(behavior)>"),
    "behavior-tail": (["<parens-decl>"],
                   ["is:", "<call(behavior)>", STAR((",", "<call(behavior)>"))],
                   ["has:", "<decl-block>"],
                   "{", PLUS("<causality>"), "}"),

    # == named cause (R-5, D-19): carries its own guard =======================
    "cause-tail": (["<parens-decl>"], "<causality/cause-explicit>", ";"),

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
                     OR, t_op_ge, OR, t_op_lt, OR, t_op_gt,
                     OR, t_kw_in, OR, (t_kw_not, t_kw_in)),  # D-15
        "add":      ("<mul>", STAR(("<op-add>", "<mul>"))),
        "mul":      ("<un>",  STAR(("<op-mul>", "<un>"))),
        "un":       ([t_op_sub], "<atom>"),
        "atom":     ("<group(group)>", OR, "<number(literal)>",
                     OR, t_re_string("literal-string"),    # D-14
                     OR, t_kw_true, OR, t_kw_false, OR, t_kw_nothing,
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
    # value world, by the mutation lvalue, by the for: source, and by the
    # comprehension from:. An lvalue IS a data-access; pass-2 restricts the
    # lvalue head to a binding (SEMANTICS 9).
    "data-access": {
        TOP:        ("<base>", STAR("<step>")),
        "base":     ("<name-ref>", ["<parens-arg>"]),
        "step":     (t_br_open, "<algebr>", t_br_close),   # single index; chains
    },

    # == collection (R-17): a third value SORT -- construct & consume only =====
    # No operators, no bridges (R-4 unchanged). Constructed by a comprehension
    # (or a literal); consumed by for:/index-base/from:/argument/RHS.
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
    # tier: every loop is bounded by definition (for:, from:/to:) -- there is
    # no unbounded while: -- and a drop is forward-only (targets a LATER
    # label), so no statement can diverge or form a back-edge. The command-block
    # admits statements and closes in an optional tail ladder of LABELS.
    # Exit-region model (R-14, R-24, kernel goto-label idiom; "goto considered
    # harmful" made safe): ":name:" DEFINES a bare drop-through label (no body,
    # C-label semantics -- control falls through it to what follows;
    # self-terminating: the second colon delimits, D-21). "dropto: label" is
    # the forward-only JUMP to such a label. The keyword "exit:" is retired
    # from this duty and reserved for the work construct's fault egress (F-5).
    # Pass-2 checks (see SEMANTICS.txt): exit-labels may be defined ONLY at the
    # outermost function body (not inside loops, if/elif/else, match, or any
    # nested block); "dropto: L" targets an exit defined LATER (forward-only);
    # the label exists.
    "code": {
        TOP:            ("{", STAR("<statement>"), "}"),

        # D-25/D-29: the work terminals give:/exit:/tick: and the explicit
        # destruct: are STATEMENTS here (any nesting depth inside a work
        # body); unlawful outside work and clockwork bodies -- the semantic
        # layer rejects (SEMANTICS 23, 27).
        "statement":    ("<mutation(mutation)>", OR, "<if(if)>", OR, "<match(match)>",
                         OR, "<for(for)>", OR, "<count(count)>",
                         OR, "<break(break)>", OR, "<continue(continue)>", OR, "<dropto(dropto)>",
                         OR, "<exit-label>",
                         OR, "<give-stmt(give)>", OR, "<exit-stmt(exit)>",
                         OR, "<tick-stmt(tick)>", OR, "<destruct-stmt(destruct)>"),

        # -- the brace body (R-12: every block is "{ }") --------------------
        # Nested bodies admit no exit-label (outermost-only, pass-2).
        "block":        ("{", STAR("<statement>"), "}"),

        # -- mutation (R-13 leaf): lvalue OP value; lvalue is a data-access ---
        # RHS is any value sort (number / truth via <expr>, or a collection --
        # disjoint at "[", R-16/R-17).
        # D-26 (LANGUAGE 12.5/12.6): targets may be a comma list (assignment
        # form of a multi-output work call; single elsewhere, pass-2) and the
        # terminator may be replaced by the AWARE handler "else: { arms }" --
        # block-final, ends at '}' (the earlier canary, verified LL(2)-clean).
        "mutation":     ("<lvalue>", STAR((",", "<lvalue>")), "<op-mut>", "<rhs>",
                         (";", OR, ("else:", "<handler(handler)>"))),
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

        # -- for (R-13, bounded, D-16): iterate a collection; var is a local --
        "for":          ("for:", t_re_id("var"),
                         (("in:", "<coll-source>"),
                          OR,                                          # D-26
                          ("from:", ["give"], "<data-access(source)>")),
                         "<block>",
                         ["else:", "<handler(handler)>"]),   # D-16, D-26
        "coll-source":  ("<data-access(access)>", OR, "<collection(comprehension)>"),

        # -- counting loop (R-13, bounded): a TYPED counter declared inline.
        #    <count-type>: <id> = <begin> .. <end> [step: <step>] { ... }
        #    The counter is a typed bare local; bounds/step are algebraic;
        #    inclusive; default step +1 (negative step counts down).
        "count":        ("<count-type>", t_re_id("var"),
                         ((t_op_assign, "<algebr>", t_op_range, "<algebr>",
                           ["step:", "<algebr>"]),
                          OR,                                          # D-17
                          ("with:", t_re_id("item"), "from:",
                           "<coll-source>", ["start:", "<algebr>"])),
                         "<block>"),
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

        # -- work terminals (D-25, D-29, LANGUAGE 12.4/13.3; SEMANTICS 23) ---
        # 'give:' names the act: the gives-bundle leaves implicitly (R-37,
        # renaming finish:). 'destruct:' ends a having explicitly by calling
        # the object's disposal work (R-37, SEMANTICS 27).
        "give-stmt":    ("give:",),
        "exit-stmt":    ("exit:", t_re_id("variant"), ["<parens-arg>"], ";"),
        "tick-stmt":    ("tick:",),
        "destruct-stmt": ("destruct:", "<data-access(object)>",
                          (";", OR, ("else:", "<handler(handler)>"))),
        # -- exit-label (R-14): a bare drop-through label (no body, C-label);
        #    definable only at the outermost body (pass-2).
        # D-21/D-31 (B-1, R-39): labels operate on TWO ACCOUNTS. Bare
        # ':name:' is the DEAD ADDRESS -- dropto:'s target, drop-throughable
        # like a kernel-driver goto label. ':name: => { ... }' is the CATCH
        # REGION -- the elseto: target that catches routed signals; normal
        # flow SKIPS it (nobody falls into a handler).
        "exit-label":   (t_op_colon, t_re_id("label"), t_op_colon,
                         [t_op_spawn, "<block(region)>"]),
    },

    # == declarations (has:) ==================================================
    "decl-block": ("{", PLUS("<declaration>"), "}"),
    # D-5: no [<parens-decl>] on a declaration (see the delta ledger).
    "declaration": (t_re_id("name"), t_op_colon, "<type>", ";"),

    # -- type (R-19): a built-in, a named type, or a plain aggregate ----------
    # D-30 (R-38): the relation words prefix a container -- 'have list' HAS
    # its elements (collective debt), 'know list' knows them (views). The
    # bare container stays the VALUE container (10). Custody checks bind
    # the type document (SEMANTICS 28, deferred).
    "type":       ("<type-built-in(type-builtin)>", OR, "<type-list(list)>",
                   OR, "<type-dict(dict)>", OR, "<type-struct(struct)>",
                   OR, "<type-have(have)>", OR, "<type-know(know)>",
                   OR, t_re_id("type")),
    "type-have":  ("have", ("<type-list(list)>", OR, "<type-dict(dict)>")),
    "type-know":  ("know", ("<type-list(list)>", OR, "<type-dict(dict)>")),
    "type-built-in": (t_kw_int, OR, t_kw_float, OR, t_kw_string, OR, t_kw_bool),

    # -- aggregation types (R-19): plain VARIABLE-TYPED containers, NO type
    #    parameters and NO member functions. Element/key/value/field types are
    #    dynamic; constraints are a deliberate future addition.
    "type-list":   (t_kw_list,),                            # list  (of anything)
    "type-dict":   (t_kw_dict,),                            # dict  (anything -> anything)
    "type-struct": (t_kw_struct, "{", PLUS("<field>"), "}"), # struct { x; y; ... }
    "field":       (t_re_id("name"), ";"),                  # a named slot, untyped

    # == reference (R-8, D-1, D-19): the call form ============================
    # A definition head declares a BARE name under the current scope
    # (namespacing is the open: block's job, R-18); since D-19 the head lives
    # in <named-item>/<behavior-def> and the Signature product is assembled
    # there. A CALL references a name: bare, dotted (namespace path), or
    # binding-qualified (member), with optional arguments.
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
    "arg":         ("<algebr>", OR, (t_re_id("arg-name"), t_op_assign, "<algebr>")),  # D-28

    "parens-decl": ("(", ["<list-decl>"], ")"),
    "list-decl":   ("<decl-arg>", STAR((",", "<decl-arg>"))),
    "decl-arg":    (t_re_id("arg-name"), [t_op_colon, "<type>"],
                    [t_op_assign, "<algebr>"]),  # D-11; default type float (§2.1)

}
# R-9 (no leading-dot form; every member access names its binding) is enforced
# in pass-2 over the dotted head (D-8): the grammar carries no binding keywords.
