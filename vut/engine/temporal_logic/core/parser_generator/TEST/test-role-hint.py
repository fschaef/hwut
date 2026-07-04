#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

ROLE-HINT FUNCTIONALITY  --  the advisory role tag and its checked vocabulary.

A grammar position may carry an advisory ROLE: a plain string naming the kind a
reference or terminal is expected to denote. Two authoring forms lower to a
transparent Tagged_Spec -- a terminal CALL, t("role"), and a reference SUFFIX,
'<name(role)>'. The tag is NON-IDENTITY: it changes no token, no FIRST_2 set, no
reduced value. The allowed roles are declared in a ROLES vocabulary checked at
compile time. These choices pin each part.

    CHOICES:
    call_operator       t("role") yields a Tagged_Spec over the SAME interned
                        terminal; role recorded; per-occurrence (distinct
                        wrappers, shared body); repr shows the role.
    ref_suffix          '<name(role)>' compiles to a Tagged_Spec over the rule;
                        '<name>' (no role) stays a bare Rule_Spec.
    terminal_key        Terminal_Spec is a content-hashed value key: same
                        _name() -> equal and same hash (and interned to one
                        object); usable as a dict key; a Tagged_Spec is not its
                        body.
    transparent_first2  FIRST_2 sets and LL(2) acceptance are identical for a
                        grammar with vs without the role tags.
    transparent_parse   An end-to-end parse yields the identical CST under the
                        tagged and the bare grammar (the tag adds no value).
    vocabulary          The ROLES check: a declared vocabulary compiles clean;
                        an undeclared role (typo) or a hint on a pattern with no
                        entry is a RoleVocabularyError; no roles dict opts out.
    walk_positions      Each role is recoverable by walking the compiled
                        grammar, keyed by its pattern.
______________________________________________________________________________
"""
import sys

import config                                                   # noqa: F401
from config import HwutRunner

from vut.engine.temporal_logic.core.parser_generator.combinators import OR, STAR
from vut.engine.temporal_logic.core.parser_generator.ll2_grammar_spec import (
        T, Terminal_Spec, Tagged_Spec, Rule_Spec)
from vut.engine.temporal_logic.core.parser_generator.ll2_engine import (
        Grammar, EngineParser, RoleVocabularyError)
from vut.engine.temporal_logic.core.lexer.lexer import register_grammar
from vut.engine.temporal_logic.core.diagnostic import DiagnosticReporter


# Toy VALUE terminals: '@'-led regex classes so no real-grammar terminal in the
# process-global DB shadows them at lex time (see test-engine for the rationale).
t_ID  = T.regex(r'@id\b')
t_NUM = T.regex(r'@num\b')


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def _fmt_set(s):
    """RETURN: str, a FIRST_2 set rendered stably (sorted by token debug names)."""
    def key(tup):
        return tuple(t._name() for t in tup)
    def show(tup):
        return "(" + ", ".join(t._name() for t in tup) + ")"
    return "{" + ", ".join(show(t) for t in sorted(s, key=key)) + "}"


def _render(node, indent=0):
    """RETURN: str, a stable indented rendering of a CST node / token / list."""
    pad = "  " * indent
    if isinstance(node, (list, tuple)):
        return "\n".join(_render(x, indent) for x in node) if node else pad + "[]"
    name = type(node).__name__
    if name == "Token":
        return pad + "Token(%s)" % node.kind._name()
    lines = [pad + name]
    for attr in ("triggered_index", "present", "name"):
        if hasattr(node, attr):
            lines.append(pad + "  %s = %r" % (attr, getattr(node, attr)))
    for attr in ("child", "children", "items"):
        if hasattr(node, attr):
            val = getattr(node, attr)
            lines.append(pad + "  %s:" % attr)
            lines.append(_render(val, indent + 2))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
def run_call_operator():
    """RETURN: None. The terminal call operator t("role") yields a transparent view.

    Calling a terminal with a role returns a Tagged_Spec whose body IS the same
    interned terminal object (identity preserved -- the tag rides alongside, not
    inside, identity). Two calls on one terminal make two DISTINCT wrappers (the
    tag is per-occurrence) sharing the one body. The repr shows the role.
    """
    banner("t('role') wraps the interned terminal, role recorded")
    tagged = t_ID("event")
    print("type:        ", type(tagged).__name__)
    print("role:        ", tagged.role)
    print("body is t_ID:", tagged.body is t_ID)
    print("repr:        ", repr(tagged))

    banner("per-occurrence: distinct wrappers, shared body")
    a = t_ID("event")
    b = t_ID("clock")
    print("a is b:           ", a is b)
    print("a.body is b.body:  ", a.body is b.body)
    print("roles:            ", a.role, "/", b.role)


def run_ref_suffix():
    """RETURN: None. '<name(role)>' compiles to a Tagged_Spec; '<name>' does not.

    The reference-suffix form tags a rule reference. After compile, the leaf at
    the tagged position is a Tagged_Spec wrapping the referenced Rule_Spec; the
    bare reference compiles to the Rule_Spec directly.
    """
    grammar = {
        "top": ("<a(event)>", "<a>"),
        "a":   (t_ID,),
    }
    register_grammar(grammar)
    g = Grammar(grammar, {"top": None, "a": None}, start="top")
    seq = g.rules["top"].pattern          # SEQ_Spec: [tagged-ref, bare-ref]
    first, second = seq.branches

    banner("tagged reference '<a(event)>'")
    print("type:           ", type(first).__name__)
    print("role:           ", getattr(first, "role", None))
    print("body is rule a: ", first.body is g.rules["a"])

    banner("bare reference '<a>'")
    print("type:           ", type(second).__name__)
    print("is rule a:      ", second is g.rules["a"])


def run_terminal_key():
    """RETURN: None. Terminal_Spec is a content-hashed value key.

    Two T.regex of the same pattern are interned to ONE object, so they are the
    same instance, equal, and share a hash -- a terminal is therefore a stable
    dict key. A Tagged_Spec wrapping a terminal is a different type and not equal
    to the terminal, so a role view never collides with its base key.
    """
    a = T.regex(r'@id\b')
    b = T.regex(r'@id\b')

    banner("interning + value-key identity")
    print("a is b:    ", a is b)
    print("a == b:    ", a == b)
    print("hash equal:", hash(a) == hash(b))

    banner("usable as a dict key")
    d = {a: ("event", "clock")}
    print("d[b]:      ", d[b])           # same key by identity/content
    print("t_NUM in d:", t_NUM in d)

    banner("a tagged view is not its base key")
    tagged = a("event")
    print("tagged == a:", tagged == a)
    print("tagged in d:", tagged in d)


def _bare_and_tagged():
    """RETURN: (bare_dict, tagged_dict), two grammars equal but for role tags."""
    bare = {
        "args":   ("<arg>", STAR(("COMMA", "<arg>"))),
        "arg":    ("<rvalue>", OR, (t_ID, "EQ", "<rvalue>")),
        "rvalue": (t_NUM, OR, t_ID),
    }
    tagged = {
        "args":   ("<arg>", STAR(("COMMA", "<arg>"))),
        "arg":    ("<rvalue>", OR, (t_ID("arg-name"), "EQ", "<rvalue(value)>")),
        "rvalue": (t_NUM, OR, t_ID),
    }
    return bare, tagged


def run_transparent_first2():
    """RETURN: None. The role tags leave FIRST_2 and LL(2) acceptance unchanged.

    Compiles the same grammar bare and with role tags on a terminal and a
    reference; prints each rule's FIRST_2 from both, and that both compile
    LL(2)-clean. Equal sets are the transparency proof at the analysis level.
    """
    bare, tagged = _bare_and_tagged()
    register_grammar(bare)
    gb = Grammar(bare,   {k: None for k in bare},   start="args")
    gt = Grammar(tagged, {k: None for k in tagged}, start="args")

    banner("FIRST_2 per rule: bare vs tagged")
    for name in ("args", "arg", "rvalue"):
        sb = _fmt_set(gb.rules[name].first)
        st = _fmt_set(gt.rules[name].first)
        print("  %-8s equal=%s" % (name, sb == st))
        print("    bare:   %s" % sb)
        print("    tagged: %s" % st)
    print("both LL(2)-clean: yes (no conflict raised)")


def run_transparent_parse():
    """RETURN: None. The tagged and bare grammars build the identical CST.

    Drives the same inputs through both grammars in CST mode and prints whether
    the rendered trees are identical -- the role tag must add nothing to any
    reduced value.
    """
    bare, tagged = _bare_and_tagged()
    register_grammar(bare)
    gb = Grammar(bare,   cst=True, start="args")
    gt = Grammar(tagged, cst=True, start="args")

    banner("CST identity: bare vs tagged")
    for src in ("@id", "@id EQ @num", "@id COMMA @num"):
        rb = DiagnosticReporter(); rt = DiagnosticReporter()
        nb = EngineParser(src, rb, gb)._match(gb.rules["args"])
        nt = EngineParser(src, rt, gt)._match(gt.rules["args"])
        same = _render(nb) == _render(nt)
        print("  %-18s identical=%s  (errs %d/%d)"
              % (src, same, len(rb.errors), len(rt.errors)))


def run_vocabulary():
    """RETURN: None. The ROLES check: clean pass, two failures, opt-out.

    With a 'roles' dict the compile validates every hint: a role outside a
    declared pattern's tuple is the TYPO guard; a hint on a pattern with no entry
    is rejected too; both raise RoleVocabularyError. With no 'roles' dict the
    hints are not checked.
    """
    g = {
        "top":  ("<a>", OR, "<b>"),
        "a":    (t_ID("event"), "EQ"),
        "b":    (t_NUM, "<a(reference)>"),
    }
    acts = {"top": None, "a": None, "b": None}

    banner("declared vocabulary -> compiles clean")
    Grammar(g, acts, start="top",
            roles={t_ID: ("event", "clock"), "<a>": ("reference", "operand")})
    print("compiled OK (every hint declared)")

    banner("undeclared ROLE on a declared pattern -> rejected (typo guard)")
    try:
        Grammar(g, acts, start="top",
                roles={t_ID: ("evnet", "clock"), "<a>": ("reference",)})
        print("UNEXPECTED: no error")
    except RoleVocabularyError as exc:
        for v in exc.violations:
            print("  ", v)

    banner("hint on a pattern with NO vocabulary entry -> rejected")
    try:
        Grammar(g, acts, start="top", roles={t_ID: ("event",)})
        print("UNEXPECTED: no error")
    except RoleVocabularyError as exc:
        for v in exc.violations:
            print("  ", v)

    banner("no roles dict -> hints not checked (opt-out)")
    Grammar(g, acts, start="top")
    print("compiled OK (validation skipped)")


def run_walk_positions():
    """RETURN: None. Every role is recoverable by walking the compiled grammar.

    Walks each rule's compiled pattern, collects each Tagged_Spec, and prints its
    key (the wrapped terminal's _name(), or '<rule>') and role -- the data the
    semantic layer reads by position.
    """
    grammar = {
        "top":  ("clockwork:", "<a(clock)>", t_ID("name")),
        "a":    (t_NUM,),
    }
    register_grammar(grammar)
    g = Grammar(grammar, {"top": None, "a": None}, start="top")

    found = []
    seen = set()

    def walk(node):
        if id(node) in seen:
            return
        seen.add(id(node))
        if isinstance(node, Tagged_Spec):
            body = node.body
            key = body._name() if isinstance(body, Terminal_Spec) else "<%s>" % body.name
            found.append((key, node.role))
        for c in node.children():
            walk(c)

    for name in sorted(g.rules):
        walk(g.rules[name].pattern)

    banner("roles walked off the compiled grammar")
    for key, role in sorted(found):
        print("  %-18s -> %s" % (key, role))


HwutRunner(
    argv       = sys.argv,
    title      = "Role-Hint Facility",
    choice_map = {
        "call_operator":      run_call_operator,
        "ref_suffix":         run_ref_suffix,
        "terminal_key":       run_terminal_key,
        "transparent_first2": run_transparent_first2,
        "transparent_parse":  run_transparent_parse,
        "vocabulary":         run_vocabulary,
        "walk_positions":     run_walk_positions,
    },
).run()
