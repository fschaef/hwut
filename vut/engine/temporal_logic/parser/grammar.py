"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

RULE-FILE SYNTAX  --  the single source of truth.

This file is the grammar of the HWUT 2.0 rule-file language and its complete
prose specification, in one place:

  GRAMMAR     a dict mapping each non-terminal (a bare name, e.g. 'spawn') to
              its production. This IS the concrete grammar -- the data the parser
              engine compiles. It replaces the former hand-listed EBNF; the
              dict and the engine never drift because there is only the dict.

  SYNTAX_DOC  the prose specification: principles, per-production explanation,
              and the semantic sections (modes, state machines, mode groups,
              namespaces, includes, object-space init/deinit, clocks, the Luau
              helper set). This is the single prose source of truth; it carries
              everything the former SYNTAX text file held except the EBNF
              listing, which the GRAMMAR dict above now carries in executable
              form. (The standalone file is retired in favour of this docstring.)

GRAMMAR element vocabulary -- every element is one of:

  "<name>"            a reference to another GRAMMAR rule (a non-terminal),
                      written as a bare angle-bracketed string.
  t_re_id t_re_number a character-class terminal (T.regex), bound to a 't_re_...'
  t_re_string         variable in the preamble below. The four classes are id,
  t_re_name_colon     number, string, name_colon.
  t_kw_any t_kw_end   a captured keyword (T.captured), KEPT in the parse frame
  t_kw_begin          (not dropped as punctuation) because a builder must read
  t_kw_void           which one matched. Used where the keyword is an OR
  t_kw_container      discriminant -- ANY / END / BEGIN (trigger), VOID
                      (member-ref, sm-mode-ref), container (type-ref).
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
  "<name>"            a reference to GRAMMAR rule 'name' (a bare angle-bracketed
                      string, matching SYNTAX_DOC's <name> spelling).
  "literal"           a silent bare-string keyword.

ACTIONS (the reduce builders) and the parser engine live in actions.py and
parser_engine.py; actions.py imports GRAMMAR from here.
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
from .core.terminals    import T
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
t_kw_void       = T.captured("VOID")
t_kw_container  = T.captured("container")

# The four runtime self-bindings, as reserved keyword terminals. They are the
# ONLY heads a <shallow-member-access> rvalue admits ('event.x', 'sm.x', 'mg.x',
# 'mode.x'), so a member of the triggering event or the enclosing aggregate can
# be forwarded as an argument WITHOUT wrapping it in opaque Luau -- the static
# layer reads the reference directly. Reserving them keeps the rvalue LL(1) (the
# binding heads are disjoint from the bare-identifier branch's t_re_id) at the
# stated cost: 'event' / 'sm' / 'mg' / 'mode' can no longer be ordinary
# identifiers. The trailing-colon definition keywords ('mode:', etc.) are a
# different, longer token and still win in the lexer's longest-first tier.
t_kw_event      = T.captured("event")
t_kw_sm         = T.captured("sm")
t_kw_mg         = T.captured("mg")
t_kw_mode       = T.captured("mode")

# Bracket-guard vocabulary. 'not' is captured (the builder must SEE it to wrap a
# negation); 'and'/'or' stay silent (they only separate operands at a level). The
# six comparison operators are captured so the comparison builder reads the exact
# operator from the token; two-char operators precede their one-char prefixes in
# the lexer's longest-first ordering.
t_kw_not        = T.captured("not")
t_op_ge         = T.captured(">=")
t_op_le         = T.captured("<=")
t_op_eq         = T.captured("==")
t_op_ne         = T.captured("!=")
t_op_gt         = T.captured(">")
t_op_lt         = T.captured("<")


GRAMMAR = {
"top-level":      ("<namespace>", OR, "<include>", OR, "<causality>", OR, "<mode>",
                   OR, "<mode-group>", OR, "<state-machine>", OR, "<event-def>",
                   OR, "<clock-def>", OR, "<cause-def>", OR, "<effect-def>",
                   OR, "<declaration>"),

"include":        ("include:", t_re_string, "into:", "<dotted-name>"),
"namespace":      ("open:", "<dotted-name>", PLUS("<top-level>"), ":close"),

"event-def":      ("event:", t_re_id, "<decl-parens>"),
"clock-def":      ("clock:", t_re_id, t_re_number),
"declaration":    (t_re_id, ["<decl-parens>"], "is:", "<type-ref>"),
"type-ref":       (t_re_id, OR, t_kw_mode, OR, (t_kw_container, t_op_lt, ["<arg-list>"], t_op_gt, ["as:", t_opq_lvalue])),

"causality":      ("on:", "<cause>", PLUS(("=>", "<effect>"))),

"mode":           ("mode:", "<signature>", PLUS("<mode-elm>"), PLUS(("until:", "<cause>"))),
"state":          ("state:", "<signature>", STAR("<mode-elm>"), STAR(("until:", "<cause>"))),

"mode-group":     ("mode_group:", "<signature>", STAR(("is:", "<dotted-name>")),
                   PLUS("<mode-group-elm>"), ":end"),
"state-machine":  ("state_machine:", "<signature>", STAR(("is:", "<dotted-name>")),
                   PLUS("<state-machine-elm>"), ":end"),

"cause":          ("<cause-ref>", OR, ("<trigger>", ["&", "<guard>"])),
"cause-ref":      (t_re_id, "<arg-parens>"),

"trigger":        (t_re_id, OR, t_kw_any, OR, t_kw_end, OR, t_kw_begin),

"guard":          ("<luau-guard>", OR, "<bracket-guard>"),
"luau-guard":     t_opq_cond,
"bracket-guard":  ("[", "<or-cond>", "]"),
"or-cond":        ("<and-cond>", STAR(("or", "<and-cond>"))),
"and-cond":       ("<not-cond>", STAR(("and", "<not-cond>"))),
"not-cond":       ([t_kw_not], "<cond-atom>"),
"cond-atom":      ("<paren-cond>", OR, "<comparison>"),
"paren-cond":     ("(", "<or-cond>", ")"),
"comparison":     ("<evt-member>", "<cmp-op>", "<cond-operand>"),
"evt-member":     (".", t_re_id),
"cmp-op":         (t_op_ge, OR, t_op_le, OR, t_op_eq, OR, t_op_ne, OR, t_op_gt, OR, t_op_lt),
"cond-operand":   ("<evt-member>", OR, t_re_number, OR, t_re_string),
"effect":         ("<mutation>", OR, "<spawn>", OR, "<unspawn>", OR, "<mode-arming>",
                   OR, "<report-string>", OR, "<event-spec>", OR, "<effect-ref>"),
"effect-ref":     (t_re_id,),
"cause-def":      ("cause:", "<signature>", "on:", "<cause>"),
"effect-def":     ("effect:", "<signature>", PLUS(("=>", "<effect>"))),
"mutation":       t_opq_stmts,
"spawn":          ("+!", "<dotted-name>", "<arg-parens>", ["in:", "<dotted-name>", ["as:", t_opq_lvalue]]),
"unspawn":        ("-!", "<dotted-name>"),
"event-spec":     ("<dotted-name>", "<arg-parens>"),
"mode-arming":    ("!", "<dotted-name>", "<arg-parens>"),
"report-string":  t_re_string,

"arg-parens":            ("(", ["<arg-list>"], ")"),
"arg-list":              ("<arg>", STAR((",", "<arg>"))),
"arg":                   ("<rvalue>", OR, (t_re_id, "=", "<rvalue>")),
"rvalue":                (t_re_number, OR, t_re_string, OR, "<shallow-member-access>",
                          OR, t_re_id, OR, t_opq_expr),
"shallow-member-access": ("<binding>", ".", t_re_id),
"binding":               (t_kw_event, OR, t_kw_sm, OR, t_kw_mg, OR, t_kw_mode),

"mode-elm":  ("<causality>", OR, "<init>", OR, "<deinit>"),
"init":      ("init:", t_opq_stmts),
"deinit":    ("deinit:", t_opq_stmts),
"has-ref":   ("has:", "<member-ref>"),

"member-ref":        (t_re_id, [".", (t_kw_void, OR, t_re_id)]),

"mode-group-elm":    ("<mode>", OR, "<has-ref>", OR, "<init>", OR, "<deinit>"),
"state-machine-elm": ("<state>", OR, "<has-ref>", OR, "<default>", OR, "<init>", OR, "<deinit>"),
"default":           ("default:", "<sm-mode-ref>"),
"sm-mode-ref":       (t_re_id, ".", (t_kw_void, OR, t_re_id)),
"decl-parens":       ("(", ["<arg-decl-list>"], ")"),
"arg-decl-list":     ("<arg-decl>", STAR((";", "<arg-decl>"))),
"arg-decl":          (t_re_name_colon, t_re_id),
"dotted-name":       (t_re_id, STAR((".", t_re_id))),
"signature":         ("<dotted-name>", ["<decl-parens>"]),

}


