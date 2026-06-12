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
  t_re_id t_re_number a character-class terminal (T.regex), bound to a 't_re_...'
  t_re_string         variable in the preamble below. The four classes are id,
  t_re_name_colon     number, string, name_colon.
  t_kw_any t_kw_end   a captured keyword (T.captured), KEPT in the parse frame
  t_kw_begin ...      (not dropped as punctuation) because a builder must read
                      which one matched. Used where the keyword is an OR
                      discriminant -- ANY / END / BEGIN / CHANGE (cause-system),
                      VOID (ref-member), the kind keywords (kind-decl), the
                      built-in type and bool-literal keywords.
  t_opq_cond          an opaque Luau span terminal (T.opaque) carrying its Role
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
from ..luau.luau_fragment import Role


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
t_re_number     = T.regex(r'[+-]?\d+(?:\.\d+)?')
t_re_string     = T.regex(r'"[^"]*"')
t_re_id         = T.regex(r'[a-zA-Z_]\w*')

t_opq_cond      = T.opaque(Role.CONDITION)
t_opq_expr      = T.opaque(Role.EXPRESSION)
t_opq_lvalue    = T.opaque(Role.LVALUE)
t_opq_stmts     = T.opaque(Role.STATEMENT_BLOCK)

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

# Built-in value types and the boolean literals (variable declarations,
# rvalues, bracket-condition operands).
t_kw_int        = T.captured("int")
t_kw_float      = T.captured("float")
t_kw_string     = T.captured("string")
t_kw_bool       = T.captured("bool")
t_kw_true       = T.captured("true")
t_kw_false      = T.captured("false")

# Bracket-guard vocabulary. 'not' is captured (the builder must SEE it to wrap a
# negation); 'and'/'or' stay silent (they only separate operands at a level). The
# six comparison operators are captured so the cond-term builder reads the exact
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


GRAMMAR = {
"top-level":      ("<namespace>", OR, "<import>", OR, "<causality>", OR, "<mode>",
                   OR, "<mode-group>", OR, "<state-machine>", OR, "<def-event>",
                   OR, "<def-clock>", OR, "<def-cause>", OR, "<def-effect>",
                   OR, "<declaration>"),

"import":         ("import:", t_re_string, "into:", "<name-dotted>"),
"namespace":      ("open:", "<name-dotted>", PLUS("<top-level>"), ":close"),

"def-event":      ("event:", t_re_id, "<parens-decl>"),
"def-clock":      ("clock:", t_re_id, t_re_number),
"def-cause":      ("cause:", "<signature>", "for:", "<name-dotted>", "&", "<guard>"),
"def-effect":     ("effect:", "<signature>", PLUS(("=>", "<effect>"))),

"declaration":    (t_re_id, ["<parens-decl>"], "is:", "<kind-decl>"),
"kind-decl":      ("<kind-reactor>", OR, "<kind-struct>", OR, "<kind-container>",
                   OR, "<kind-variable>"),
"kind-reactor":   (t_kw_mode, OR, t_kw_state, OR, t_kw_mode_group,
                   OR, t_kw_state_machine),
"kind-struct":    (t_kw_struct,),
"kind-container": (t_kw_container, [t_op_lt, ["<list-arg>"], t_op_gt],
                   ["by:", t_opq_lvalue]),
"kind-variable":  (("<type-built-in>", OR, t_re_id), "<parens-arg>",
                   ["by:", t_opq_lvalue]),
"type-built-in":  (t_kw_int, OR, t_kw_float, OR, t_kw_string, OR, t_kw_bool),

"causality":      ("on:", "<cause>", PLUS(("=>", "<effect>"))),

"mode":           ("mode:", "<signature>", PLUS("<elm-mode>"), PLUS(("until:", "<cause>"))),
"state":          ("state:", "<signature>", STAR("<elm-mode>"), STAR(("until:", "<cause>"))),

"mode-group":     ("mode_group:", "<signature>", STAR(("is:", "<name-dotted>")),
                   PLUS("<elm-mode-group>"), ":end"),
"state-machine":  ("state_machine:", "<signature>", STAR(("is:", "<name-dotted>")),
                   PLUS("<elm-state-machine>"), ":end"),

"cause":          ("<cause-system>", OR, "<cause-named>"),
"cause-system":   ((t_kw_any, OR, t_kw_end, OR, t_kw_begin, OR, t_kw_change),
                   ["&", "<guard>"]),
"cause-named":    ("<name-dotted>", ["<parens-arg>"], ["&", "<guard>"]),

"guard":          ("<guard-luau>", OR, "<guard-bracket>"),
"guard-luau":     t_opq_cond,
"guard-bracket":  ("[", "<cond>", "]"),
"cond":           ("<cond-and>", STAR(("or", "<cond-and>"))),
"cond-and":       ("<cond-not>", STAR(("and", "<cond-not>"))),
"cond-not":       ([t_kw_not], "<cond-atom>"),
"cond-atom":      ("<cond-paren>", OR, "<cond-term>"),
"cond-paren":     ("(", "<cond>", ")"),
"cond-term":      ("<name-dotted>", ["<op-cmp>", "<operand-cond>"]),
"op-cmp":         (t_op_ge, OR, t_op_le, OR, t_op_eq, OR, t_op_ne,
                   OR, t_op_gt, OR, t_op_lt),
"operand-cond":   ("<name-dotted>", OR, t_re_number, OR, t_re_string,
                   OR, t_kw_true, OR, t_kw_false),

"effect":         ("<mutation>", OR, "<spawn>", OR, "<unspawn>", OR, "<arming-mode>",
                   OR, "<report-string>", OR, "<effect-named>"),
"effect-named":   ("<name-dotted>", ["<parens-arg>"]),
"mutation":       t_opq_stmts,
"spawn":          ("+!", "<name-dotted>", "<parens-arg>",
                   ["in:", "<name-dotted>", ["via:", "<rvalue>"]]),
"unspawn":        ("-!", "<name-dotted>"),
"arming-mode":    ("!", "<name-dotted>", "<parens-arg>"),
"report-string":  t_re_string,

"parens-arg":     ("(", ["<list-arg>"], ")"),
"list-arg":       ("<arg>", STAR((",", "<arg>"))),
"arg":            ("<rvalue>", OR, (t_re_id, "=", "<rvalue>")),
"rvalue":         (t_re_number, OR, t_re_string, OR, t_kw_true, OR, t_kw_false,
                   OR, "<name-dotted>", OR, t_opq_expr),

"elm-mode":  ("<causality>", OR, "<init>", OR, "<deinit>"),
"init":      ("init:", t_opq_stmts),
"deinit":    ("deinit:", t_opq_stmts),
"ref-has":   ("has:", "<ref-member>"),

"ref-member":        ("<name-dotted>", [".", t_kw_void]),

"elm-mode-group":    ("<mode>", OR, "<ref-has>", OR, "<init>", OR, "<deinit>"),
"elm-state-machine": ("<state>", OR, "<ref-has>", OR, "<default>", OR, "<init>",
                      OR, "<deinit>"),
"default":           ("default:", "<ref-member>"),

"parens-decl":       ("(", ["<list-decl-arg>"], ")"),
"list-decl-arg":     ("<decl-arg>", STAR((";", "<decl-arg>")), [";"]),
"decl-arg":          (t_re_name_colon, (t_re_id, OR, "<type-built-in>")),
"name-dotted":       (t_re_id, STAR((".", t_re_id))),
"signature":         ("<name-dotted>", ["<parens-decl>"]),

}
