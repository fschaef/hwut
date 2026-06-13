"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

RULE-FILE SYNTAX  --  the single source of truth.

This file is the grammar of the HWUT 2.0 rule-file language:

  GRAMMAR     a dict mapping each non-terminal (a bare name, e.g. 'spawn') to
              its production. This IS the concrete grammar -- the data the parser
              engine compiles. It replaces the former hand-listed EBNF; the
              dict and the engine never drift because there is only the dict.

The prose specification (principles, per-production explanation, semantic
sections) is SYNTAX_DOC = grammar.txt beside this file; it defers every
production to this dict and dominates all other prose.

GRAMMAR element vocabulary -- every element is one of:

  "<name>"            a reference to another GRAMMAR rule (a non-terminal),
                      written as a bare angle-bracketed string.
  "<name(role)>"      the SAME reference carrying an advisory ROLE HINT, a
                      plain string (D-10): the position is expected to resolve
                      to that role ('<cause(clock)>', '<name-dotted(event)>').
                      Likewise a terminal is tagged by CALLING it with a role,
                      't_re_id("event")'. The hint is NON-IDENTITY -- it does
                      not affect lexing, interning, or the LL(2) analysis, and
                      it adds nothing to the CST values; it is recorded on the
                      compiled grammar (a transparent Tagged_Spec) for legibility
                      and as a pass-2 resolution hint walkable by position.
  t_re_id t_re_number a character-class terminal (T.regex), bound to a 't_re_...'
  t_re_string         variable in the preamble below. The four classes are id,
  t_re_name_colon     number, string, name_colon.
  t_kw_any t_kw_end   a captured keyword (T.captured), KEPT in the parse frame
  t_kw_begin ...      (not dropped as punctuation) because a builder must read
                      which one matched. Used where the keyword is an OR
                      discriminant -- ANY / END / BEGIN / CHANGE (cause-system),
                      VOID (ref-member), the kind keywords (kind-decl), the
                      built-in type and bool-literal keywords.
  t_opq_cond          an opaque Luau span terminal (T.opaque) carrying its E_SpanMode
  t_opq_expr          (CONDITION / EXPRESSION / LVALUE / STATEMENT_BLOCK). The
  t_opq_lvalue        role rides on the object, so the position's role is fixed
  t_opq_stmts         by which 't_opq_...' the rule names.
  "literal"           a bare string: a terminal spelled exactly as in a rule
                      file ('on:', '=>', '('), SILENT -- dropped from the frame
                      as punctuation. Plain keywords stay bare strings (a
                      deliberate slight inconsistency for visual sweetness); they
                      get no t_... definition and are extracted from the grammar
                      to populate the lexer.
  (a, b, ...)         an implicit SEQUENCE: match a, then b, ... -- a tuple.
  [a, b, ...]         an OPTIONAL: match the bracketed sequence zero or one
                      time -- a list. (One element, [x], is just x optional.)
  (a, OR, b, ...)    an ALTERNATION: OR is a sentinel placed BETWEEN branches
                      inside a tuple, read as 'a | b | ...'.
  PLUS(x) STAR(x)     one-or-more / zero-or-more (combinator classes, one body).
                      (A sequence is a bare tuple; an optional is a bare list;
                      there is no SEQ and no OPT.)

Rule names carry the FUNCTIONALITY PREFIX (D-27): def-event, kind-container,
cond-term, ref-has, elm-mode, list-arg, parens-decl, name-dotted, ...

ACTIONS (the reduce builders) live in ast_map.py, which imports GRAMMAR from
here; the engine lives in core/.
______________________________________________________________________________
"""

# Grammar combinators, terminals, and references. Authored directly: a bare
# tuple is an implicit SEQUENCE (no Seq() call); a bare list is an OPTIONAL (no
# Opt() call); a tuple holding the OR sentinel between branches is an
# ALTERNATION; Plus/Star are combinator classes; T.* mints the richer terminals
# (recorded in terminals.py's database for the lexer generator); a bare '<name>'
# is a rule reference.
#
#   (a, b, ...)      implicit sequence: match a, then b, ...
#   [a, b, ...]      optional: match the bracketed sequence zero or one time
#   (a, OR, b, ...) alternation: one branch, chosen by FIRST set
#   PLUS(x)          x one or more times
#   STAR(x)          x zero or more times
#   t_...            a terminal object bound in the preamble below
#   "<name>"         a reference to another GRAMMAR rule
#   "literal"        a silent bare-string keyword
from .core.combinators import OR, PLUS, STAR
from .core.ll2_grammar_spec import T
from .core.span_oracle import E_SpanMode


# -- terminal preamble -------------------------------------------------------
# The richer terminals, defined once as named objects. Each T.* call records the
# terminal into terminals.TERMINAL_DB in declaration order; the lexer generator
# (lexer.py) reads that database -- plus the bare-string keywords extracted from
# GRAMMAR -- to mint _TOKEN_SPEC and the token ids. The author supplies no token
# id and no precedence number; for the regex classes, the only precedence lever
# is the order of the lines below, which the generator emits verbatim. A class
# that is a PREFIX of another must come first: t_re_name_colon ('id:') before
# t_re_id ('id'), or a 'name:' would be eaten as a bare id and a stray ':'.
#
# The naming convention groups terminals by family: t_re_ for regex classes,
# t_opq_ for opaque Luau spans, t_kw_ for captured keywords (kept in the frame).
t_re_name_colon = T.regex(r'[a-zA-Z_]\w*:')
t_re_number     = T.regex(r'\d+(?:\.\d+)?')
t_re_string     = T.regex(r'"[^"]*"')
t_re_id         = T.regex(r'[a-zA-Z_]\w*')

t_opq_cond      = T.opaque(E_SpanMode.CONDITION)
t_opq_expr      = T.opaque(E_SpanMode.EXPRESSION)
t_opq_lvalue    = T.opaque(E_SpanMode.LVALUE)
t_opq_stmts     = T.opaque(E_SpanMode.STATEMENT_BLOCK)

t_kw_any        = T.captured("ANY")
t_kw_end        = T.captured("END")
t_kw_begin      = T.captured("BEGIN")
t_kw_change     = T.captured("CHANGE")
t_kw_void       = T.captured("VOID")

# Declaration-kind keywords (kind-decl discriminants). The definition keywords
# ('mode:', 'state_machine:', ...) are the longer trailing-colon tokens and win
# in the lexer's longest-first tier; the bare spellings below appear only on the
# right of 'is:'. The runtime self-bindings ('e'/'sm'/'mg'/'m') are NOT here:
# they are ordinary identifiers, resolved as pseudo-symbols in pass 2 (D-24).
t_kw_mode          = T.captured("mode")
t_kw_state         = T.captured("state")
t_kw_mode_group    = T.captured("mode_group")
t_kw_state_machine = T.captured("state_machine")
t_kw_struct        = T.captured("struct")
t_kw_container     = T.captured("container")
t_kw_clockwork         = T.captured("clockwork")

# Built-in value types and the boolean literals (variable declarations,
# rvalues, bracket-condition operands).
t_kw_int        = T.captured("int")
t_kw_float      = T.captured("float")
t_kw_string     = T.captured("string")
t_kw_bool       = T.captured("bool")
t_kw_true       = T.captured("true")
t_kw_false      = T.captured("false")

# Bracket-guard vocabulary. 'not' is captured (the builder must SEE it to wrap a
# negation); the comparison operators are captured so the builder reads the exact
# operator from the token; two-char operators precede their one-char prefixes in
# the lexer's longest-first ordering. '<'/'>' double as the container
# type-parameter brackets -- same captured terminals, position decides.
t_kw_not        = T.captured("not")
t_op_ge         = T.captured(">=")
t_op_le         = T.captured("<=")
t_op_eq         = T.captured("==")
t_op_ne         = T.captured("!=")
t_op_gt         = T.captured(">")
t_op_lt         = T.captured("<")

# Expression operators (D-13). All CAPTURED: each level that carries two operators
# ('or'/'nor', 'xor'/'nxor', 'and'/'nand', '+'/'-', 'shl:'/'shr:') needs the exact
# token kept so the left-fold builder records which BinOp it is; '*' and unary '-'
# are captured for a uniform builder. Numbers are UNSIGNED (the lexer carves '+'
# and '-' as their own atoms); negation is the unary-minus operator at alg-un.
t_op_add        = T.captured("+")
t_op_sub        = T.captured("-")
t_op_mul        = T.captured("*")
t_kw_shl        = T.captured("shl:")
t_kw_shr        = T.captured("shr:")
t_kw_and        = T.captured("and")
t_kw_nand       = T.captured("nand")
t_kw_or         = T.captured("or")
t_kw_nor        = T.captured("nor")
t_kw_xor        = T.captured("xor")
t_kw_nxor       = T.captured("nxor")
t_op_question   = T.captured("?")    # the bool->num bridge leader


# ADVISORY ROLE HINTS:
# Role hints are restricted to what is mentioned in the per-item vocabulary
# below. Role hints in the vocabulare, that are unused do not harm.
#
# Role hints in rules:     '<rule(role)>'
#            in terminals: t_something("role")
#
# Roles are decorations, but are communicated to the semantic analyzer.
ROLES = {
    # terminals (keyed by the interned terminal object; hashable + immutable)
    t_re_id:         ("event", "clock", "type", "name", "arg-name"),
    t_re_string:     ("filename", "report"),
    t_re_number:     ("period",),
    t_re_name_colon: ("member",),
    # rule references (keyed by the '<name>' reference string)
    "<name-dotted>": ("namespace", "event", "cause", "emission", "mode",
                      "aggregate", "container", "instance", "base", "member",
                      "operand", "reference", "name"),
    "<cause>":       ("heartbeat",),
}

GRAMMAR = {
"top-level":      ("<namespace>", OR, "<import>", OR, "<causality>", OR, "<mode>",
                   OR, "<mode-group>", OR, "<state-machine>", OR, "<clockwork>",
                   OR, "<def-event>", OR, "<def-clock>", OR, "<def-cause>",
                   OR, "<def-effect>", OR, "<declaration>"),

"import":         ("import:", t_re_string("filename"), "into:", "<name-dotted(namespace)>"),
"namespace":      ("open:", "<name-dotted(namespace)>", PLUS("<top-level>"), ":close"),

"def-event":      ("event:", t_re_id("event"), "<parens-decl>"),
"def-clock":      ("clock:", t_re_id("clock"), t_re_number("period")),
"def-cause":      ("cause:", "<signature>", "for:", "<name-dotted(event)>", "&", "<guard>"),
"def-effect":     ("effect:", "<signature>", PLUS(("=>", "<effect>"))),

"declaration":    (t_re_id("name"), ["<parens-decl>"], "is:", "<kind-decl>"),
"kind-decl":      ("<kind-reactor>", OR, "<kind-struct>", OR, "<kind-container>",
                   OR, "<kind-variable>"),
"kind-reactor":   (t_kw_mode, OR, t_kw_state, OR, t_kw_mode_group,
                   OR, t_kw_state_machine, OR, t_kw_clockwork),
"kind-struct":    (t_kw_struct,),
"kind-container": (t_kw_container, [t_op_lt, ["<list-arg>"], t_op_gt],
                   ["by:", t_opq_lvalue]),
"kind-variable":  (("<type-built-in>", OR, t_re_id("type")), "<parens-arg>",
                   ["by:", t_opq_lvalue]),
"type-built-in":  (t_kw_int, OR, t_kw_float, OR, t_kw_string, OR, t_kw_bool),

"causality":      ("on:", "<cause>", PLUS(("=>", "<effect>"))),

"mode":           ("mode:", "<signature>", PLUS("<elm-mode>"), PLUS(("until:", "<cause>"))),
"state":          ("state:", "<signature>", STAR("<elm-mode>"), STAR(("until:", "<cause>"))),

"mode-group":     ("mode_group:", "<signature>", STAR(("is:", "<name-dotted(base)>")),
                   PLUS("<elm-mode-group>"), ":end"),
"state-machine":  ("state_machine:", "<signature>", STAR(("is:", "<name-dotted(base)>")),
                   PLUS("<elm-state-machine>"), ":end"),

# --- clockwork: a tick-scripted stimulus actor (D-11) -------------------------
# 'clockwork: <id> [(sig)] on: <cause>' then a body of clockwork elements, ':end'.
# 'on:' reuses <cause> (trigger + optional guard, the heartbeat shape); pass 2
# resolves the trigger to a clock. The body element is a step or an init/deinit.
"clockwork":          ("clockwork:", "<signature>", "on:", "<cause(heartbeat)>",
                   PLUS("<elm-clockwork>"), ":end"),
"elm-clockwork":      ("<step-clockwork>", OR, "<init>", OR, "<deinit>"),

# The step alternation. Each branch opens with a distinct leader: a bare
# emission with <name-dotted> (the identifier class); every other step with its
# own trailing-colon keyword or '{'. LL(2)-clean by leader.
"step-clockwork":     ("<clockwork-instant>", OR, "<clockwork-wait>", OR, "<clockwork-select>",
                   OR, "<clockwork-if>", OR, "<clockwork-while>", OR, "<spawn>",
                   OR, "<unspawn>", OR, "<arming-mode>", OR, "<incr>", OR, "<decr>",
                   OR, "<mutation>", OR, "<clockwork-name-step>"),

# A name-led step left-factored on its shared <name-dotted> prefix, so the three
# name-led forms (paced emission, assignment, guarded reciprocal) are LL(2)-clean:
# the tail dispatches on the next token -- '(' / 'gets:' / 'recip:' (D-13).
"clockwork-name-step": ("<name-dotted>",
                   ("<parens-arg>", OR, "<assign-rhs>", OR, "<recip-rhs>")),
# assignment:  <lvalue> gets: <algebr>
"assign-rhs":     ("gets:", "<algebr>"),
# guarded reciprocal: <lvalue> recip: <algebr> else: <body> :end  (1/x, or run body
# when the value is zero -- the only division path, total by construction).
"recip-rhs":      ("recip:", "<algebr>", "else:", PLUS("<elm-clockwork>"), ":end"),
# saturating step counters; 'by:' amount (default 1, pass 2) and 'to:' clamp both
# optional. 'by:' is required to introduce the amount so a bare next statement
# (also name-led) is never mistaken for it.
"incr":           ("incr:", "<name-dotted(operand)>", ["by:", "<algebr>"],
                   ["to:", "<algebr>"]),
"decr":           ("decr:", "<name-dotted(operand)>", ["by:", "<algebr>"],
                   ["to:", "<algebr>"]),
# Immediate injection (tick-free) into the current queue.
"clockwork-instant":  ("instant:", "<name-dotted(emission)>", "<parens-arg>"),
# Suspend until a cause fires; optional co-temporal effect tail.
"clockwork-wait":     ("wait:", "<cause>", STAR(("=>", "<effect>"))),
# First-of-many: only wait lines inside.
"clockwork-select":   ("select:", PLUS("<clockwork-wait>"), ":end"),
# Control frames; conditions reuse <guard>; one ':end' per if-chain, own for while.
"clockwork-if":       ("if:", "<guard>", PLUS("<step-clockwork>"),
                   STAR(("elif:", "<guard>", PLUS("<step-clockwork>"))),
                   ["else:", PLUS("<step-clockwork>")], ":end"),
"clockwork-while":    ("while:", "<guard>", PLUS("<step-clockwork>"), ":end"),

"cause":          ("<cause-system>", OR, "<cause-named>"),
"cause-system":   ((t_kw_any, OR, t_kw_end, OR, t_kw_begin, OR, t_kw_change),
                   ["&", "<guard>"]),
"cause-named":    ("<name-dotted(cause)>", ["<parens-arg>"], ["&", "<guard>"]),

"guard":          ("<guard-luau>", OR, "<guard-bracket>"),
"guard-luau":     t_opq_cond,
"guard-bracket":  ("[", "<cond>", "]"),

# Condition ladder (D-13). Left-assoc folds, loosest to tightest:
# or/nor < xor/nxor < and/nand < not < comparison. '[' always opens a nested
# condition (the condition world); the two-token worlds never collide because
# algebra groups with '(' (the algebra world) instead.
"cond":        ("<cond-or>",),
"cond-or":     ("<cond-xor>", STAR(("<op-or>",  "<cond-xor>"))),
"cond-xor":    ("<cond-and>", STAR(("<op-xor>", "<cond-and>"))),
"cond-and":    ("<cond-not>", STAR(("<op-and>", "<cond-not>"))),
"cond-not":    ([t_kw_not], "<cond-atom>"),
"cond-atom":   ("<cond-bracket>", OR, "<comparison>"),
"cond-bracket":("[", "<cond>", "]"),
"comparison":  ("<algebr>", ["<op-cmp>", "<algebr>"]),
"op-or":       (t_kw_or,  OR, t_kw_nor),
"op-xor":      (t_kw_xor, OR, t_kw_nxor),
"op-and":      (t_kw_and, OR, t_kw_nand),
"op-cmp":      (t_op_ge, OR, t_op_le, OR, t_op_eq, OR, t_op_ne,
                OR, t_op_gt, OR, t_op_lt),

# Algebraic ladder (D-13). shift < add < mul < unary-minus < atom. '(' always
# opens nested algebra; the '?'-bridge is the ONLY bool->num crossing.
"algebr":      ("<alg-shift>",),
"alg-shift":   ("<alg-add>", STAR(("<op-shift>", "<alg-add>"))),
"alg-add":     ("<alg-mul>", STAR(("<op-add>",   "<alg-mul>"))),
"alg-mul":     ("<alg-un>",  STAR(("<op-mul>",   "<alg-un>"))),
"alg-un":      ([t_op_sub], "<alg-atom>"),
"alg-atom":    ("<alg-paren>", OR, "<bridge>", OR, t_re_number, OR, t_re_string,
                OR, t_kw_true, OR, t_kw_false, OR, t_opq_expr,
                OR, "<name-dotted(operand)>"),
"alg-paren":   ("(", "<algebr>", ")"),
"op-shift":    (t_kw_shl, OR, t_kw_shr),
"op-add":      (t_op_add, OR, t_op_sub),
"op-mul":      (t_op_mul,),
"bridge":      (t_op_question, "<cond>", "then:", "<algebr>", "else:", "<algebr>"),

"effect":         ("<mutation>", OR, "<spawn>", OR, "<unspawn>", OR, "<arming-mode>",
                   OR, "<report-string>", OR, "<effect-named>"),
"effect-named":   ("<name-dotted(emission)>", ["<parens-arg>"]),
"mutation":       t_opq_stmts,
"spawn":          ("spawn:", "<name-dotted(aggregate)>", "<parens-arg>",
                   ["in:", "<name-dotted(container)>", ["via:", "<algebr>"]]),
"unspawn":        ("unspawn:", "<name-dotted(instance)>"),
"arming-mode":    ("arm:", "<name-dotted(mode)>", "<parens-arg>"),
"report-string":  t_re_string("report"),

"parens-arg":     ("(", ["<list-arg>"], ")"),
"list-arg":       ("<arg>", STAR((",", "<arg>"))),
"arg":            ("<algebr>", OR, (t_re_id("arg-name"), "=", "<algebr>")),

"elm-mode":  ("<causality>", OR, "<init>", OR, "<deinit>"),
"init":      ("init:", t_opq_stmts),
"deinit":    ("deinit:", t_opq_stmts),
"ref-has":   ("has:", "<ref-member>"),

"ref-member":        ("<name-dotted(member)>", [".", t_kw_void]),

"elm-mode-group":    ("<mode>", OR, "<ref-has>", OR, "<init>", OR, "<deinit>"),
"elm-state-machine": ("<state>", OR, "<ref-has>", OR, "<default>", OR, "<init>",
                      OR, "<deinit>"),
"default":           ("default:", "<ref-member>"),

"parens-decl":       ("(", ["<list-decl-arg>"], ")"),
"list-decl-arg":     ("<decl-arg>", STAR((";", "<decl-arg>")), [";"]),
"decl-arg":          (t_re_name_colon("member"), (t_re_id("type"), OR, "<type-built-in>")),
"name-dotted":       (t_re_id, STAR((".", t_re_id))),
"signature":         ("<name-dotted(name)>", ["<parens-decl>"]),

}
