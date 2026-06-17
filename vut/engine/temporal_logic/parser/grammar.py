"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer

RULE-FILE GRAMMAR -- the concrete grammar the engine compiles.

This file is DATA ONLY: the GRAMMAR dict and the terminal/preamble bindings.
All documentation -- the element vocabulary, per-production prose, terminal
ordering rationale, role-hint conventions -- lives in grammar.txt, the single
source of truth for the rule-file syntax. Do not add explanatory comments
here; document in grammar.txt.
"""

from vut.engine.temporal_logic.core.parser_generator.combinators import OR, PLUS, STAR, TOP
from vut.engine.temporal_logic.core.parser_generator.ll2_grammar_spec import T
from vut.engine.temporal_logic.world.span_oracle import E_SpanMode


t_re_name_colon = T.regex(r'[a-zA-Z_]\w*:')
t_re_number     = T.regex(r'\d+(?:\.\d+)?')
t_re_string     = T.regex(r'"[^"]*"')
t_re_id         = T.regex(r'[a-zA-Z_]\w*')

t_opq_expr      = T.opaque(E_SpanMode.EXPRESSION)
t_opq_lvalue    = T.opaque(E_SpanMode.LVALUE)
t_opq_stmts     = T.opaque(E_SpanMode.STATEMENT_BLOCK)

t_kw_any        = T.captured("ANY")
t_kw_end        = T.captured("END")
t_kw_begin      = T.captured("BEGIN")
t_kw_change     = T.captured("CHANGE")
t_kw_void       = T.captured("VOID")

t_kw_mode          = T.captured("mode")
t_kw_state         = T.captured("state")
t_kw_mode_group    = T.captured("mode_group")
t_kw_state_machine = T.captured("state_machine")
t_kw_struct        = T.captured("struct")
t_kw_dict          = T.captured("dict")
t_kw_list          = T.captured("list")
t_kw_clockwork         = T.captured("clockwork")

t_kw_int        = T.captured("int")
t_kw_float      = T.captured("float")
t_kw_string     = T.captured("string")
t_kw_bool       = T.captured("bool")
t_kw_true       = T.captured("true")
t_kw_false      = T.captured("false")

t_kw_not        = T.captured("not")
t_op_ge         = T.captured(">=")
t_op_le         = T.captured("<=")
t_op_eq         = T.captured("==")
t_op_ne         = T.captured("!=")
t_op_gt         = T.captured(">")
t_op_lt         = T.captured("<")

t_op_add        = T.captured("+")
t_op_sub        = T.captured("-")
t_op_mul        = T.captured("*")
t_op_div        = T.captured("/")
t_kw_shl        = T.captured("shl:")
t_kw_shr        = T.captured("shr:")
t_kw_and        = T.captured("and")
t_kw_nand       = T.captured("nand")
t_kw_or         = T.captured("or")
t_kw_nor        = T.captured("nor")
t_kw_xor        = T.captured("xor")
t_kw_nxor       = T.captured("nxor")
t_op_question   = T.captured("?")


ROLES = {
    t_re_id:         ("event", "clock", "type", "name", "arg-name"),
    t_re_string:     ("filename", "report"),
    t_re_number:     ("period",),
    t_re_name_colon: ("member",),
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
    
    "declaration":    {
        TOP:        (t_re_id("name"), ["<parens-decl>"], "is:", "<decl>"),
        "decl":     ("<reactor>", OR, "<struct>", OR, "<dict>",
                     OR, "<list>", OR, "<variable>"),
        "reactor":  (t_kw_mode, OR, t_kw_state, OR, t_kw_mode_group,
                     OR, t_kw_state_machine, OR, t_kw_clockwork),
        "struct":   (t_kw_struct,),
        "dict":     ("<type-dict>", ["by:", t_opq_lvalue]),
        "list":     ("<type-list>", ["by:", t_opq_lvalue]),
        "variable": (("<type-built-in>", OR, t_re_id("type")), "<parens-arg>",
                     ["by:", t_opq_lvalue]),
    },
    "type-built-in":  (t_kw_int, OR, t_kw_float, OR, t_kw_string, OR, t_kw_bool),
    "type-dict":      (t_kw_dict, t_op_lt, "<type(key)>", ",", "<type(value)>",
                       t_op_gt),
    "type-list":      (t_kw_list, t_op_lt, "<type(element)>", t_op_gt),
    "type":           ("<type-built-in>", OR, "<type-dict>", OR, "<type-list>",
                       OR, t_re_id("type")),
    
    "causality":      ("on:", "<cause>", PLUS(("=>", "<effect>"))),
    
    "mode":           ("mode:", "<signature>", PLUS("<elm-mode>"), PLUS(("until:", "<cause>"))),
    "state":          ("state:", "<signature>", STAR("<elm-mode>"), STAR(("until:", "<cause>"))),
    
    "mode-group":     ("mode_group:", "<signature>", STAR(("is:", "<name-dotted(base)>")),
                       PLUS("<elm-mode-group>"), ":end"),
    "state-machine":  ("state_machine:", "<signature>", STAR(("is:", "<name-dotted(base)>")),
                       PLUS("<elm-state-machine>"), ":end"),
    
    "clockwork":          ("clockwork:", "<signature>", "on:", "<cause(heartbeat)>",
                       PLUS("<elm-clockwork>"), ":end"),
    "elm-clockwork":      ("<step>", OR, "<init>", OR, "<deinit>"),
    
    "step":     {
        TOP:        ("<instant>", OR, "<wait>", OR, "<select>",
                     OR, "<if>", OR, "<while>", OR, "<spawn>",
                     OR, "<unspawn>", OR, "<arming-mode>", OR, "<incr>", OR, "<decr>",
                     OR, "<mutation>", OR, "<name-step>"),
        "name-step": ("<name-dotted>",
                      ("<parens-arg>", OR, "<assign-rhs>", OR, "<recip-rhs>")),
        "assign-rhs": ("gets:", "<algebr>"),
        "recip-rhs":  ("recip:", "<algebr>", "else:", PLUS("<elm-clockwork>"), ":end"),
        "incr":     ("incr:", "<name-dotted(operand)>", ["by:", "<algebr>"],
                     ["to:", "<algebr>"]),
        "decr":     ("decr:", "<name-dotted(operand)>", ["by:", "<algebr>"],
                     ["to:", "<algebr>"]),
        "instant":  ("instant:", "<name-dotted(emission)>", "<parens-arg>"),
        "wait":     ("wait:", "<cause>", STAR(("=>", "<effect>"))),
        "select":   ("select:", PLUS("<wait>"), ":end"),
        "if":       ("if:", "<guard>", PLUS("<step>"),
                     STAR(("elif:", "<guard>", PLUS("<step>"))),
                     ["else:", PLUS("<step>")], ":end"),
        "while":    ("while:", "<guard>", PLUS("<step>"), ":end"),
        "spawn":    {
            TOP:     ("spawn:", "<name-dotted(aggregate)>", "<parens-arg>",
                      ["into:", "<into>"]),
            "into":  ("<name-dotted(container)>", ["[", "<name-dotted(key)>", "]"]),
            },
    },
    
    "cause":          ("<cause-system>", OR, "<cause-named>"),
    "cause-system":   ((t_kw_any, OR, t_kw_end, OR, t_kw_begin, OR, t_kw_change),
                       ["&", "<guard>"]),
    "cause-named":    ("<name-dotted(cause)>", ["<parens-arg>"], ["&", "<guard>"]),
    
    "guard":          ("[", "<cond>", "]"),
    
    "cond": {
        TOP:        ("<or>",),
        "or":       ("<xor>", STAR(("<op-or>",  "<xor>"))),
        "xor":      ("<and>", STAR(("<op-xor>", "<and>"))),
        "and":      ("<not>", STAR(("<op-and>", "<not>"))),
        "not":      ([t_kw_not], "<atom>"),
        "atom":     ("<bracket>", OR, "<comparison>"),
        "bracket":  ("[", "<cond>", "]"),
        "comparison": ("<algebr>", ["<op-cmp>", "<algebr>"]),
        "op-or":    (t_kw_or,  OR, t_kw_nor),
        "op-xor":   (t_kw_xor, OR, t_kw_nxor),
        "op-and":   (t_kw_and, OR, t_kw_nand),
        "op-cmp":   (t_op_ge, OR, t_op_le, OR, t_op_eq, OR, t_op_ne,
                     OR, t_op_gt, OR, t_op_lt),
    },
    
    "algebr": {
        TOP:        ("<shift>", ["undef:", "<shift>"]),
        "shift":    ("<add>", STAR(("<op-shift>", "<add>"))),
        "add":      ("<mul>", STAR(("<op-add>",   "<mul>"))),
        "mul":      ("<un>",  STAR(("<op-mul>",   "<un>"))),
        "un":       ([t_op_sub], "<atom>"),
        "atom":     ("<paren>", OR, "<bridge>", OR, t_re_number, OR, t_re_string,
                     OR, t_kw_true, OR, t_kw_false, OR, t_opq_expr,
                     OR, "<operand>"),
        "operand":  (t_re_id("receiver"), ["<parens-arg>"], STAR("<postfix>")),
        "postfix":  (".", t_re_id("member"), ["<parens-arg>"]),
        "paren":    ("(", "<algebr>", ")"),
        "op-shift": (t_kw_shl, OR, t_kw_shr),
        "op-add":   (t_op_add, OR, t_op_sub),
        "op-mul":   (t_op_mul, OR, t_op_div),
        "bridge":   (t_op_question, "<cond>", "then:", "<algebr>", "else:", "<algebr>"),
    },
    
    "effect":         ("<mutation>", OR, "<unspawn>", OR, "<arming-mode>",
                       OR, "<report-string>", OR, "<effect-named>"),
    "effect-named":   ("<name-dotted(emission)>", ["<parens-arg>"]),
    "mutation":       "<code-block>",
    "code-block":     (t_opq_stmts, OR, "<do-sweep(one-sweep)>"),
    "do-sweep":       ("do:", PLUS("<step>"), ":end"),
    "unspawn":        ("unspawn:", "<name-dotted(instance)>"),
    "arming-mode":    ("arm:", "<name-dotted(mode)>", "<parens-arg>"),
    "report-string":  t_re_string("report"),
    
    "parens-arg":     ("(", ["<list-arg>"], ")"),
    "list-arg":       ("<arg>", STAR((",", "<arg>"))),
    "arg":            ("<algebr>", OR, (t_re_id("arg-name"), "=", "<algebr>")),
    
    "elm-mode":  ("<causality>", OR, "<init>", OR, "<deinit>"),
    "init":      ("init:", "<code-block>"),
    "deinit":    ("deinit:", "<code-block>"),
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
