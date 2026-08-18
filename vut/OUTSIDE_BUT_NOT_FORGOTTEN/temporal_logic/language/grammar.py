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
D-37 The physical unit type enters (R-50): 'physical[<unit>]' the
     type, '<number> [<unit>]' the literal; <unit> a product/quotient
     of unit names ('*' AND whitespace multiply; '/' left-assoc);
     exponents '^<int>', '^(<int>/<int>)', or Unicode superscripts.
     The full unit ALGEBRA (Q3 = B) is semantic/runtime; names
     validate against UNITS.txt.
D-36 The recurrence tail dies (R-49): 'every:'/'as:' leave the spawn;
     the handle namespace and '=x=> <handle>' with them -- lack of
     orthogonality; the timer concern moves to a plant-side feeder
     (held discussion). 'as:' survives only on import:.
D-35 Three arrows (R-46): the activation arrow '=!=>' enters the
     effect markers ('=>' spawn event/work code, '=!=>' activate
     behavior, '=x=>' deactivate); the causality gains the SHRUG
     ('<cause> => ;' -- reckoned, ignored; chain-final). Mode laws
     ('=!=>' the transition in a state machine; '=x=>' on a behavior
     a semantic error there) are pass-2 (SEMANTICS 1/2, R-46).
D-34 The event definition enters (R-45): named-item gains the branch
     'name : event(<decl-args>);' -- the freestanding form of a
     signals: entry (signals ARE events, one ephemeral creature,
     LANGUAGE 14.1). Structure checks and the inline entry type of
     14.2 stay with the F-9 passes.
D-33 The arm IS a causality (R-44): the handler arm becomes
     '(<variant> | ~ANY) [when: <condition>] => <action>' -- the
     parens-binding head ('bad(m)') and the bare '=>' default arm are
     REMOVED; payload reads 'e.<field>' (semantic binding from the
     callee's declaration); '~ANY' is a new captured keyword, also
     admitted as a CAUSE form (the catch-all in a behavior's group).
     Dispatch (first-match, uniform) and coverage-by-testimony are
     pass-2 (SEMANTICS 24, R-44).
D-32 The fault egress speaks 'signal' (R-43): 'exit-stmt' becomes
     'signal-stmt' -- 'signal [<variant>[(<args>)] [to <channel>]];'. The
     'to' suffix is admitted by GRAMMAR everywhere (one statement world);
     the position law is semantic (behavior work code only, SEMANTICS
     23/31). The word 'exit' leaves the keyword set; the exit-label rule
     (':name:', D-21) is untouched -- its surface never spoke 'exit'.
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
# float (Q9 ruling: the EXPONENT MARKS FLOAT, like the dot does): a
# fraction, an exponent, or both -- '1e-6', '2.5e3', '1E+10' are floats;
# a bare '\d+' stays the int. Python and Luau both read the lexeme
# natively.
t_re_float   = T.regex(r'\d+\.\d+(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+')
t_re_int     = T.regex(r'\d+')
t_re_doc     = T.regex(r'"""(?:[^"]|"(?!""))*"""')  # D-18: BEFORE t_re_string
t_re_string  = T.regex(r'"[^"]*"')
t_re_id      = T.regex(r'[a-zA-Z_]\w*')

# == reserved events (R-10: lifecycle; non-external) ==========================
t_kw_entry   = T.captured("~ENTRY")
t_kw_exit    = T.captured("~EXIT")
t_kw_any     = T.captured("~ANY")     # R-44: the catch-all pattern -- any
                                      # event/fault that comes, in the scope
                                      # it sits in; e is Nothing under it

# == operator terminals =======================================================
# LEXING ORDER LAW: captured terminals lex in DECLARATION order (the lexer's
# tier-4 scan). Every MULTI-character operator is therefore declared BEFORE any
# single-character operator that is its prefix ("=x=>", "=>", "==" before "=";
# "+=" before "+"; ".." before the "." symbol keyword) -- maximal munch by
# construction, verified by the acceptance smoke.

# -- multi-character operators, longest first ---------------------------------
# effect markers (R-1, §2.2): captured so they precede "=" in the scan order
t_op_cancel  = T.captured("=x=>")
t_op_activate = T.captured("=!=>")    # R-46: activates a behavior
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
# relation markers (R-41.1/2): the STATE NOUNS spoken at panel entries,
# member declarations, and binding sites -- captured (which marker was
# written matters); colon-terminated (R-11), so they lex in the
# leading-colon tier before any bare id.
t_kw_known   = T.captured("known:")
t_kw_had     = T.captured("had:")
# reactor kind words (reactor ruling): 'reactor++' MUST lex before the
# bare 'reactor' (longest first -- the '++' is part of the kind word,
# not an operator), so it is declared as an explicit captured terminal.
t_kw_reactor_multi = T.captured("reactor++")
# wire arrows (pipe ruling): dash law >= 2 BY REGEX -- 'a --> b' and
# 'a ----> b' are the same arrow, 'a-> b' is not one. EARLY tier: the
# dashes are themselves the '-' terminal, so these classes must be
# tried before the bare keywords and symbols (lexer tier 3b).
t_op_wire_arrow = T.regex(r'--+>',  early=True)
t_op_wire_open  = T.regex(r'--+\[', early=True)

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
# R-50 (the physical unit type): the caret exponent and the Unicode
# lifted-number run (signed superscript integers: m², s⁻²)
t_op_caret   = T.captured("^")
t_re_super   = T.regex(r'[\u207b\u207a\u2070\u00b9\u00b2\u00b3\u2074-\u2079]+')
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
    # A rule-file is a sequence of definitions, scopes, and imports.
    # REACTOR RULING (i): causalities appear ONLY inside behaviors inside
    # reactors -- the top-level causality died with the free-standing
    # behavior. D-19: every name-led ':' item (definition or declaration)
    # parses through ONE factored rule, <named-item>.
    "top-level":  ("<named-item(named)>",
                   OR, "<ctor-def(ctor)>", OR, "<dtor-def(dtor)>",
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
                   ((t_kw_reactor_multi, "<reactor-tail(reactor_multi)>"),
                    OR,
                    ("reactor", "<reactor-tail(reactor_single)>"),
                    OR,
                    ("cause", "<cause-tail(cause-def)>"),
                    OR,
                    ("event", "<event-tail(event-def)>"),
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
    # class's destruction is WRITTEN at every site ('destruct'), so the
    # disposal work MAY declare signals -- every site answers them.
    "dtor-def":   (t_op_sub, t_re_id("class"), ["(", ")"],
                   t_op_colon, "work", "<work-tail(work)>"),

    # == class (R-29, LANGUAGE 11; R-41.3) ====================================
    # is: inheritance; then ONE body brace whose items are member
    # declarations ('[known:|had:] name : type;', having implicit) and
    # member works, INTERLEAVING FREELY (R-41.3, interleave (A)). Role by
    # panel: a member work whose out: names the class is its CONSTRUCTION
    # WORK, one whose in: names it its DISPOSAL WORK (R-30/R-41.1).
    "class-tail": (["is:", "<call(class)>", STAR((",", "<call(class)>"))],
                   ["{", PLUS("<class-item>"), "}"]),
    # -- class-shaped body items (R-41.3, factored head per the D-20
    #    precedent): a marker-led item is a DECLARATION by construction; a
    #    name-led item consumes 'name :' and decides on the token after --
    #    'work' opens a member work, anything else is the declared type.
    "class-item":    ("<marked-member(marked)>", OR, "<plain-member(plain)>"),
    "marked-member": ((t_kw_known, OR, t_kw_had),
                      t_re_id("name"), t_op_colon, "<type>", ";"),
    "plain-member":  (t_re_id("name"), t_op_colon,
                      (("work", "<work-tail(work)>"),
                       OR,
                       ("<type>", ";"))),

    # == work (LANGUAGE 12; D-25) =============================================
    # Panel, then the body: statements of the code subspace plus the work
    # terminals. give and signal are STATEMENTS of the work body only; the
    # semantic layer holds their laws (SEMANTICS 23).
    # D-27: the panel is OPTIONAL -- 'name : work' alone is a class body's
    # SEMI-DECLARATION (brief listing; the complete definition must follow,
    # SEMANTICS 25); panel without body remains the SPEC (12.1).
    "work-tail":  (["<panel>"], ["{", STAR("<code/statement>"), "}"]),

    # == handler (LANGUAGE 12.6; D-26, D-33/R-44): the else:-block is a =====
    # first-match switch whose ARM IS A CAUSALITY in form:
    # '(<variant> | ~ANY) [when: <condition>] => <action>'. Payload reads
    # 'e.<field>' (names from the callee's signal declaration); the old
    # parens-binding form and the bare '=>' default arm RETIRED (the
    # catch-all is the explicit ~ANY, e is Nothing under it). Actions: a
    # block, a signal, or ';' (the arm-level shrug). Coverage-by-testimony
    # and dead-arm are semantic (SEMANTICS 24, R-44).
    "handler":    ("{", STAR("<arm>"), "}"),
    "arm":        ((t_re_id("variant"), OR, t_kw_any),
                   ["when:", "<condition>"],
                   t_op_spawn, "<arm-action(action)>"),
    "arm-action": ("<code/block(block)>", OR, "<code/signal-stmt(signal)>",
                   OR, "<arm-shrug(shrug)>"),
    "arm-shrug":  (";",),

    # == clockwork (LANGUAGE 13; D-25, R-41.1) ================================
    # A work body extended by tick: (deliver the per-tick out: bundle, suspend
    # until the next pull); ended only through signal (bare = nothing-more,
    # R-41.7). groove: awaits its host's rebuild (R-25(3)).
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
    # SELF BINDING (reactor ruling): a LEADING bare dot roots the access
    # at the instance itself -- '.x' is this-instance's member x, for
    # classes and reactors alike; the factory records it as an EMPTY
    # first segment (prints naturally as '.x'). Where self is senseless
    # (imports, is:-targets, namespace heads) the semantic unit rejects.
    "name-dotted": (["."], t_re_id("name"), STAR((".", t_re_id("name")))),

    # == kind tails (D-19): what follows the kind word of a definition ========
    # Each tail is the definition MINUS its head name: '(params)?' first (the
    # parameter list rides the kind word: 'drive : behavior(gain) ...'), then
    # the kind's own sections. The head name and '~' live in <named-item> /
    # <behavior-def>; the factories reunite them into ONE Signature product
    # (AST unchanged, D-19).

    # == reactor (REACTOR RULING): a CLASS with behavior content ==============
    # 'reactor' acts as a STATE MACHINE (single active behavior),
    # 'reactor++' as a MODE GROUP (several active at once). The body is
    # class-shaped -- member declarations and member works -- plus
    # BEHAVIOR MEMBERS; a behavior holds ONLY causalities, has no members,
    # no works, no instances, and exists nowhere else. The factored head
    # (D-20 precedent): a marker-led item declares; after 'name :' the
    # token decides -- 'work' a member work, 'behavior' a behavior member,
    # anything else the declared type.
    "reactor-tail": (["<reactor-panel(panel)>"],
                   ["is:", "<call(reactor)>", STAR((",", "<call(reactor)>"))],
                   "{", PLUS("<reactor-item>"), "}"),
    # -- channel panel (PIPE RULING): in:/out: name the reactor's CHANNELS,
    #    plain names -- a channel is a publish/subscribe OBJECT the reactor
    #    HAS (created and destructed with it), not a data port; no types,
    #    no markers. The wire's channel must stand in the source's out: AND
    #    the destination's in: (both ends checked, elaborate).
    "reactor-panel": ("(", ["in:",  t_re_id("channel"),
                                    STAR((",", t_re_id("channel")))],
                           ["out:", t_re_id("channel"),
                                    STAR((",", t_re_id("channel")))],
                      ")"),
    "reactor-item":   ("<marked-member(marked)>", OR, "<reactor-member(member)>"),
    "reactor-member": (t_re_id("name"), t_op_colon,
                      (("behavior", "{", PLUS("<behavior-item>"), "}"),
                       OR,
                       ("work", "<work-tail(work)>"),
                       OR,
                       ("<type>", ";"))),
    # -- behavior body (PIPE RULING): causalities GROUP by in-channel --
    #    '<channel>: { causality+ }'; the SELF channel group is the bare
    #    dot as group head ('. :' / '.:'). Ungrouped causalities remain
    #    lawful exactly when ONE in-channel stands in the panel (they
    #    belong to it) or none does (self only) -- elaborate holds the
    #    group law. LL(2)-clean: a group head carries ':' at token 2; a
    #    causality head never does.
    "behavior-item":  ("<channel-group(group)>", OR, "<causality(causality)>"),
    "channel-group":  ((t_re_id("channel"), OR, "."), t_op_colon,
                       "{", PLUS("<causality>"), "}"),

    # (aspect and character DIED with the reactor ruling -- the reactor
    # unifies them: 'reactor' the state machine, 'reactor++' the mode
    # group.)
    # panel (R-41.1): FLAT and DIRECTION-SECTIONED -- 'in:'/'out:' speak
    # direction, the per-entry marker the relation (having implicit,
    # 'known:' explicit, 'had:' the optional visibility marker); 'signals:'
    # stays flat and top-level (a signal is neither had nor known). Comma
    # between entries within a section; sections keyword-led, juxtaposed;
    # trailing comma rejected by construction (C-2, R-41.5). 'in:'
    # overloads the for:-loop token -- contexts disjoint, LL-clean.
    "panel":       ("(", ["in:",      "<panel-entry>", STAR((",", "<panel-entry>"))],
                         ["out:",     "<panel-entry>", STAR((",", "<panel-entry>"))],
                         ["signals:", "<signal-decl>", STAR((",", "<signal-decl>"))],
                    ")"),
    "panel-entry": ([(t_kw_known, OR, t_kw_had)], "<decl-arg>"),
    "signal-decl": (t_re_id("name"), ["<parens-payload>"]),

    # == named cause (R-5, D-19): carries its own guard =======================
    "cause-tail": (["<parens-decl>"], "<causality/cause-explicit>", ";"),

    # == event definition (R-45): 'name : event(<decl-args>);' -- the =======
    # freestanding form of a signals: entry (14.1: one concept; a work's
    # signals: declares the same creature in panel position). Parens
    # REQUIRED (the inline entry TYPE of 14.2 stays with the F-9 passes
    # and factors then).
    "event-tail": ("<parens-payload>", ";"),

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
                          OR, t_kw_entry, OR, t_kw_exit, OR, t_kw_any),
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
                          ("<shrug(shrug)>",),
                          OR,
                          ("<spawn(spawn)>", (";", OR, "<effects>")))),
        "effect-marker": (t_op_spawn, OR, t_op_cancel, OR, t_op_activate),
        # R-46: the causality shrug -- '<cause> => ;' says "reckoned,
        # ignored"; under first-match it consumes the event for this
        # behavior. Chain-final by shape (nothing may follow).
        "shrug":        (";",),

        # -- spawn (pipe ruling; R-49: the recurrence tail DIED -- the
        #    timer concern is a plant-side feeder's): an entity/event
        #    call, optionally ROUTED ('to <channel>' -- bare word, a
        #    suffix: the emission publishes on the named out-channel of
        #    the enclosing reactor; suffix-less send FANS: all
        #    out-channels plus self).
        "spawn":        ("<call>", ["to", t_re_id("channel")]),
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
        "atom":     ("<group(group)>", OR, "<physical-literal(physical)>",
                     OR, t_re_string("literal-string"),    # D-14
                     OR, t_kw_true, OR, t_kw_false, OR, t_kw_nothing,
                     OR, "<data-access(operand)>"),
        "group":    ("(", "<expr>", ")"),
        # R-50: '<number> [ <unit> ]' -- the unit-carrying literal; the
        # bare number is the DIMENSIONLESS case (the zero vector).
        "physical-literal": ("<number(literal)>",
                             [t_br_open, "<unit>", t_br_close]),
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
    # self-terminating: the second colon delimits, D-21). "dropto label;" is
    # the forward-only JUMP to such a label. The keyword "exit:" is retired
    # from this duty and reserved for the work construct's fault egress (F-5).
    # Pass-2 checks (see SEMANTICS.txt): exit-labels may be defined ONLY at the
    # outermost function body (not inside loops, if/elif/else, match, or any
    # nested block); "dropto L;" targets an exit-label defined LATER (forward-only);
    # the label exists.
    "code": {
        TOP:            ("{", STAR("<statement>"), "}"),

        # D-25/D-29: the work terminals give/signal/tick and the explicit
        # destruct are STATEMENTS here (any nesting depth inside a work
        # body); unlawful outside work and clockwork bodies -- the semantic
        # layer rejects (SEMANTICS 23, 27).
        "statement":    ("<wire(wire)>",
                         OR, "<mutation(mutation)>", OR, "<if(if)>", OR, "<match(match)>",
                         OR, "<for(for)>", OR, "<count(count)>",
                         OR, "<break(break)>", OR, "<continue(continue)>", OR, "<dropto(dropto)>",
                         OR, "<exit-label>",
                         OR, "<give-stmt(give)>", OR, "<signal-stmt(signal)>",
                         OR, "<tick-stmt(tick)>", OR, "<destruct-stmt(destruct)>"),

        # -- wire (PIPE RULING): WIRING IS WORK -- a work statement creating
        #    a PIPE: 'a ----> b;' the plain arrow, 'a --[ statusx ]--> b;'
        #    the channel-named arrow (dash law >= 2 by regex, arrow tokens
        #    in the lexer's early tier). Ends are BARE locals holding the
        #    constructed instances (LL(2): the decision against a mutation
        #    falls at token 2 -- an arrow, never an op-mut; a dotted end
        #    would push the decision to token 3, so the member-held end is
        #    not admitted here). Wiring registers the destination as
        #    subscriber of the source's out-channel; both-end panel checks
        #    are elaborate's (PARTIAL: where the ends' reactor types are
        #    visible in the same body).
        "wire":         (t_re_id("source"),
                         ((t_op_wire_open, t_re_id("channel"), t_br_close,
                           t_op_wire_arrow),
                          OR,
                          t_op_wire_arrow),
                         t_re_id("dest"), ";"),

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
        # R-41.2 SITE MARKING: each target takes an optional 'known:' -- the
        # binding receives a VIEW; '=' stays relation-neutral. The
        # acquaintance-take from a data access ('known: m = a.b.c;') parses
        # through this same shape; the site-vs-panel agreement law is
        # FLAGGED OPEN -- the marker is recorded, no check invented.
        "mutation":     ("<site-target>", STAR((",", "<site-target>")),
                         "<op-mut>", "<rhs>",
                         (";", OR, ("else:", "<handler(handler)>"))),
        "site-target":  ([t_kw_known], "<lvalue>"),
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
                          ("from:", "<data-access(source)>")),
                         "<block>",
                         ["else:", "<handler(handler)>"]),   # D-16, D-26
        # (the 'from: give <src>' custody flavour is RETIRED by ruling --
        # from: takes the wound generator plainly; the call-site give
        # marker, when it lands, is where giving speaks)
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
        # COMMAND SPELLING RULING: commands are BARE words (the ':' died),
        # and every simple statement ends with ';'.
        "dropto":       ("dropto", t_re_id("label"), ";"),

        # -- work terminals (D-25, D-29, LANGUAGE 12.4/13.3; SEMANTICS 23;
        # R-41.4/7; command-spelling ruling) -- commands are BARE words,
        # every simple statement ends with ';'. 'give <ports>;' names the
        # leaving out-ports (elaborate checks the list against the panel's
        # out: section; unlawful in clockworks); bare 'give;' stands where
        # no out: is declared -- the ';' terminates the list, so the old
        # greedy-OPT corner is GONE. 'signal' (R-43: the exit rename --
        # one emission creature) takes an OPTIONAL variant (R-41.7: bare
        # 'signal;' is the nothing-more egress) and an OPTIONAL routing
        # suffix 'to <channel>' -- grammar admits it EVERYWHERE (one
        # statement world); the semantic layer holds the position law
        # (behavior work code only, SEMANTICS 23/31). 'destruct'
        # ends a having explicitly by calling the object's disposal work
        # (R-37, SEMANTICS 27).
        "give-stmt":    ("give", [t_re_id("port"),
                                  STAR((",", t_re_id("port")))], ";"),
        "signal-stmt":  ("signal", [(t_re_id("variant"), ["<parens-arg>"],
                                     ["to", t_re_id("channel")])],
                         ";"),
        "tick-stmt":    ("tick", ";"),
        "destruct-stmt": ("destruct", "<data-access(object)>",
                          (";", OR, ("else:", "<handler(handler)>"))),
        # -- exit-label (R-14): a bare drop-through label (no body, C-label);
        #    definable only at the outermost body (pass-2).
        # D-21/D-31 (B-1, R-39): labels operate on TWO ACCOUNTS. Bare
        # ':name:' is the DEAD ADDRESS -- dropto's target, drop-throughable
        # like a kernel-driver goto label. ':name: => { ... }' is the CATCH
        # REGION -- the elseto: target that catches routed signals; normal
        # flow SKIPS it (nobody falls into a handler).
        "exit-label":   (t_op_colon, t_re_id("label"), t_op_colon,
                         [t_op_spawn, "<block(region)>"]),
    },

    # == declarations =========================================================
    # The has:-block died with R-41's dissolution (class-shaped bodies own
    # member declarations through <class-item>); this rule serves the
    # TOP-LEVEL declaration branch of <named-item> only.
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
                   OR, "<type-physical(physical)>",
                   OR, t_re_id("type")),
    # R-50: the physical unit type -- 'physical[<unit>]'; the unit is a
    # product/quotient of unit names with integer, rational, or Unicode
    # superscript exponents. Names validate against UNITS.txt (semantic).
    "type-physical": ("physical", t_br_open, "<unit>", t_br_close),
    "unit":          ("<uprod>", STAR((t_op_div, "<uprod>"))),
    "upower-caret":  (t_op_caret,
                      ([t_op_sub], t_re_int("power"),
                       OR,
                       ("(", [t_op_sub], t_re_int("p"), t_op_div,
                        t_re_int("q"), ")"))),
    "uprod":         ("<ufactor>", STAR(([t_op_mul], "<ufactor>"))),
    "ufactor":       (t_re_id("uname"), ["<upower>"]),
    "upower":        (("<upower-caret>", OR, t_re_super("lifted")),),
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

    # HOMOGENEITY RULING (R-41 follow-up): ONE marker-admitting entry
    # shape in EVERY parens -- kind parameters (behavior, character,
    # cause) speak the same '[known:|had:] name [: type] [= default]'
    # entry as panel sections and member declarations; unmarked = had.
    # The one EXCEPTION is the signal payload (a signal is neither had
    # nor known): <parens-payload> keeps the plain entry.
    "parens-decl":    ("(", ["<list-decl>"], ")"),
    "list-decl":      ("<panel-entry>", STAR((",", "<panel-entry>"))),
    "parens-payload": ("(", ["<list-payload>"], ")"),
    "list-payload":   ("<decl-arg>", STAR((",", "<decl-arg>"))),
    # decl-arg (D-11; default type float, §2.1): the ONE entry shape --
    # 'name [: type] [= default]' -- marker-prefixed through
    # <panel-entry> everywhere a relation may speak.
    "decl-arg":    (t_re_id("arg-name"), [t_op_colon, "<type>"],
                    [t_op_assign, "<algebr>"]),

}
# R-9 (no leading-dot form; every member access names its binding) is enforced
# in pass-2 over the dotted head (D-8): the grammar carries no binding keywords.
