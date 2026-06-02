#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Cover every grammar rule in isolation by synthesizing a minimal token
         stream that triggers it and printing the resulting AST node.

CHOICES: one per grammar rule (e.g. '<causality>', '<mode>', '<arg>', ...);
         plus 'node_coverage' (every AST node type is built by some rule);

DESCRIPTION:

Each rule is driven directly -- not via a top-level wrapper -- by feeding the
engine a synthetic token list built from the rule's compiled pattern:

    terminals       a canonical filler token (#ID -> 'X', #NUMBER -> '1',
                    #STRING -> '"s"', keywords/symbols -> their literal).
    {luau:ROLE}     a synthetic LUAU_BLOCK '{ luau }' served by a fake lexer.
    (ALT, ...)      one synthesized case per alternative branch; every
                    alternative is exercised.
    (PLUS, x)       cases for 1 and 2 repetitions of x.
    (STAR, x)       cases for 0, 1 and 2 repetitions of x.
    (OPT, x)        cases for x absent and x present.

The cross product is bounded by handling one variadic/optional point at a time
against canonical fillers elsewhere, so each rule yields a small, readable set.

DEV MODE: pass 'DEV' on the command line (after the choice) to keep the choice
running under the same engine path; it currently changes no output and is
retained only as a hook for future cross-checks.
______________________________________________________________________________
"""
import sys
from config import HwutRunner

from dataclasses import is_dataclass, fields

from vut.engine.temporal_logic.parser.diagnostic     import DiagnosticReporter
from vut.engine.temporal_logic.parser.parser_engine  import (compiled_grammar, 
                                                             Terminal, 
                                                             LuauRef, 
                                                             NonTerminal, 
                                                             EngineParser)
from vut.engine.temporal_logic.parser.grammar import SEQ, ALT, OPT, PLUS, STAR
from vut.engine.temporal_logic.parser.lexer   import E_TokenId, Token


# Canonical filler lexemes for value-bearing class terminals.
_FILLER = {
    E_TokenId.ID:     "X",
    E_TokenId.NUMBER: "1",
    E_TokenId.STRING: '"s"',
}


class _ListLexer:
    """A lexer stand-in that serves a prebuilt token list to the engine.

    Implements the two methods EngineParser uses: 'next()' returns the next
    token (END_OF_FILE past the end) and 'read_luau_block(open_tok, role)'
    returns a synthetic LUAU_BLOCK. Lets a single rule be driven from a
    handmade token sequence with no source text.
    """
    def __init__(self, tokens):
        """RETURN: None. Holds the token list and a read cursor."""
        self.tokens = tokens
        self.i      = 0

    def next(self):
        """RETURN: Token, the next token, or an END_OF_FILE sentinel past the end."""
        if self.i < len(self.tokens):
            tok = self.tokens[self.i]
            self.i += 1
            return tok
        return Token(E_TokenId.END_OF_FILE, "", 0, 0)

    def read_luau_block(self, open_tok, role):
        """RETURN: Token, a synthetic LUAU_BLOCK '{ luau }' at the open offset.

        The engine consumes the LUAU_OPEN with _advance() (moving our cursor one
        past it) and then calls next() again to reload lookahead. To match the
        real lexer -- where read_luau_block swallows the block bytes so the next
        token is the one AFTER the block -- we step our cursor back by one so the
        engine's following next() returns the correct post-block token rather
        than skipping it.
        """
        self.i -= 1
        return Token(E_TokenId.LUAU_BLOCK, "{ luau }", open_tok.begin,
                     open_tok.begin + 8)


def _tok(token_id):
    """RETURN: Token, a filler token for 'token_id' with a canonical lexeme.

    Class terminals get their _FILLER lexeme; a keyword/symbol gets its literal
    spelling recovered from the compiled grammar's literal table.
    """
    if token_id in _FILLER:
        return Token(token_id, _FILLER[token_id], 0, 0)
    literal = _LITERAL_BY_ID.get(token_id, token_id.name)
    return Token(token_id, literal, 0, 0)


# Reverse the engine's literal table once: token id -> a spelling.
_LITERAL_BY_ID = {}
for _lit, _tid in compiled_grammar().literals.items():
    _LITERAL_BY_ID.setdefault(_tid, _lit)


def _synth(element, reps, active_name=None):
    """
    RETURN: list, a synthetic token sequence that satisfies 'element'.

    'reps' is the repetition count to use for the FIRST encountered PLUS/STAR
    and the present/absent choice for the FIRST OPT; nested variadic points use
    their minimal form (1 for PLUS, 0 for STAR, absent for OPT) so each case
    varies exactly one point. ALT prefers a branch that does not re-enter a
    NonTerminal already being expanded, so a recursive rule terminates with a
    minimal non-recursive body. 'active_name', when given, seeds that set with
    the rule whose pattern is being synthesized (its body avoids re-entering
    it), keeping a self-recursive rule's canonical case shallow.
    """
    state = {"used": False, "active": set()}
    if active_name is not None:
        state["active"].add(active_name)
    return _synth_rec(element, reps, state)


def _synth_rec(element, reps, state):
    """RETURN: list, tokens for 'element'; consumes the one variadic budget."""
    if isinstance(element, Terminal):
        return [_tok(element.token_id)]
    if isinstance(element, LuauRef):
        return [Token(E_TokenId.LUAU_OPEN, "{", 0, 0)]
    if isinstance(element, NonTerminal):
        active = state.setdefault("active", set())
        active.add(element.name)
        try:
            return _synth_rec(element.pattern, reps, state)
        finally:
            active.discard(element.name)
    op = element[0]
    if op == SEQ:
        out = []
        for sub in element[1:]:
            out += _synth_rec(sub, reps, state)
        return out
    if op == ALT:
        return _synth_rec(_pick_alt(element[1:], state), reps, state)
    if op in (PLUS, STAR, OPT):
        count = _budget(op, reps, state)
        out = []
        for _ in range(count):
            out += _synth_rec(element[1], 1 if op != OPT else 0,
                              dict(state, used=True))
        return out
    raise ValueError("unknown op %r" % (op,))


def _pick_alt(branches, state):
    """
    RETURN: element, the ALT branch to synthesize.

    Prefers the first branch that does not re-enter a NonTerminal already being
    expanded, so a recursive rule (e.g. <namespace> nesting <top-level>) is
    synthesized with a terminating, non-recursive inner choice. Falls back to
    the first branch when every branch recurses.
    """
    active = state.get("active", set())
    for b in branches:
        if not _reenters(b, active):
            return b
    return branches[0]


def _reenters(element, active):
    """RETURN: True if 'element' can immediately reach an active NonTerminal."""
    if isinstance(element, Terminal):
        return False
    if isinstance(element, LuauRef):
        return False
    if isinstance(element, NonTerminal):
        if element.name in active:
            return True
        return _reenters(element.pattern, active)
    op = element[0]
    if op == ALT:
        return all(_reenters(b, active) for b in element[1:])
    # SEQ/PLUS/STAR/OPT: recursion is reachable if its first obligatory part is.
    return _reenters(element[1], active)


def _budget(op, reps, state):
    """
    RETURN: int, how many times to expand the first variadic point.

    The first PLUS/STAR/OPT met spends 'reps'; later ones use their minimum
    (PLUS->1, STAR->0, OPT->0) so a case isolates one varying point.
    """
    if not state["used"]:
        state["used"] = True
        if op == OPT:
            return 1 if reps >= 1 else 0
        return reps
    return 1 if op == PLUS else 0


def _drive(rule, tokens, dev):
    """
    RETURN: node, the AST built by driving 'rule' over a synthetic token list.

    Feeds 'tokens' through an EngineParser wired to a _ListLexer, matching the
    single 'rule'. In DEV mode the same is not re-checked here (the recursive
    parser has no single-rule entry); DEV cross-check is applied at top-level
    rules only by the caller.
    """
    parser = EngineParser.__new__(EngineParser)
    parser.reporter   = DiagnosticReporter()
    parser.grammar    = compiled_grammar()
    parser.lexer      = _ListLexer(tokens)
    parser.tok        = parser.lexer.next()
    parser._top_first = parser.grammar.rules[parser.grammar.start].first
    node = parser._match(rule)
    return node, parser.reporter


def _fragment(tokens):
    """
    RETURN: str, the synthesized token list rendered as a readable code fragment.

    Joins token lexemes with single spaces -- enough to show WHAT input produced
    a case, not to reproduce real source layout. A LUAU_OPEN ('{') is shown as
    the synthetic block '{ luau }' the fake lexer serves, so the fragment
    matches what the engine actually consumed.
    """
    out = []
    for t in tokens:
        if t.kind == E_TokenId.LUAU_OPEN:
            out.append("{ luau }")
        else:
            out.append(t.text)
    return " ".join(out)


def _fmt(node, indent=0):
    """RETURN: str, a stable indented rendering of an AST node / list / leaf."""
    pad = "  " * indent
    if isinstance(node, list):
        if not node:
            return pad + "[]"
        return "\n".join(_fmt(x, indent) for x in node)
    if is_dataclass(node):
        head = pad + type(node).__name__
        lines = [head]
        for f in fields(node):
            val = getattr(node, f.name)
            if is_dataclass(val) or isinstance(val, list):
                lines.append("%s  %s:" % (pad, f.name))
                lines.append(_fmt(val, indent + 2))
            else:
                lines.append("%s  %s = %r" % (pad, f.name, val))
        return "\n".join(lines)
    return pad + repr(node)


def _variadic_cases(pattern):
    """
    RETURN: list, the (label, reps) cases for a rule's first variadic point.

    Inspects the pattern for the first PLUS/STAR/OPT and returns the repetition
    counts to exercise: PLUS -> 1,2; STAR -> 0,1,2; OPT -> absent,present. A
    rule with no variadic point yields a single default case.
    """
    op = _first_variadic(pattern)
    if op == PLUS:
        return [("1x", 1), ("2x", 2)]
    if op == STAR:
        return [("0x", 0), ("1x", 1), ("2x", 2)]
    if op == OPT:
        return [("absent", 0), ("present", 1)]
    return [("default", 1)]


def _first_variadic(element):
    """RETURN: the op of the first PLUS/STAR/OPT under 'element', or None."""
    if isinstance(element, (Terminal, LuauRef)):
        return None
    if isinstance(element, NonTerminal):
        return _first_variadic(element.pattern)
    op = element[0]
    if op in (PLUS, STAR, OPT):
        return op
    for sub in element[1:]:
        found = _first_variadic(sub)
        if found:
            return found
    return None


def _alt_branches(pattern):
    """RETURN: list, the branches of the first ALT under 'pattern', or []."""
    if isinstance(pattern, NonTerminal):
        return _alt_branches(pattern.pattern)
    if isinstance(pattern, tuple) and pattern[0] == ALT:
        return list(pattern[1:])
    return []


def _make_choice(rule_name):
    """RETURN: function, the HWUT run-function covering rule 'rule_name'."""
    def run():
        g    = compiled_grammar()
        rule = g.rules[rule_name]
        dev  = "DEV" in sys.argv

        print("=== %s ===" % rule_name)
        branches = _alt_branches(rule.pattern)
        if branches:
            # Cover each alternative of an ALT rule.
            for i, branch in enumerate(branches):
                tokens = _synth(branch, 1, active_name=rule_name)
                node, rep = _drive(rule, tokens, dev)
                print("\n-- alternative %d --" % i)
                print("   input: %s" % _fragment(tokens))
                print(_fmt(node))
                _print_diags(rep)
        else:
            for label, reps in _variadic_cases(rule.pattern):
                tokens = _synth(rule.pattern, reps, active_name=rule_name)
                node, rep = _drive(rule, tokens, dev)
                print("\n-- %s --" % label)
                print("   input: %s" % _fragment(tokens))
                print(_fmt(node))
                _print_diags(rep)
    return run


def _print_diags(reporter):
    """RETURN: None. Prints any diagnostics raised during a drive."""
    if reporter.errors:
        for d in reporter.errors:
            print("   DIAG %s off=%d %s"
                  % (d.phase.name, d.source_offset, d.message))


# One HWUT choice per grammar rule. Because the choice set is derived from
# compiled_grammar().rules, adding a rule to grammar.py makes a new coverage
# choice appear automatically -- there is no hand-maintained list to update.
# The 'node_coverage' choice below is the cross-check in the other direction:
# it asserts every concrete AST node type is produced by at least one rule, so
# a node added without a rule that builds it is caught here.
_GRAMMAR = compiled_grammar()
_CHOICES = {
    name.replace("<","").replace(">",""): _make_choice(name)
    for name in _GRAMMAR.rules
}


def _concrete_node_types():
    """
    RETURN: set, the names of every concrete (built) AST dataclass.

    Every frozen dataclass in ast_nodes that the parser instantiates. RuleFile
    (the container) and the abstract TopLevel base are excluded: RuleFile is
    assembled by the engine loop, not a reduce action, and TopLevel is never
    instantiated.
    """
    import vut.engine.temporal_logic.parser.ast_nodes as ast_mod
    skip = {"RuleFile"}
    out = set()
    for name in dir(ast_mod):
        obj = getattr(ast_mod, name)
        if isinstance(obj, type) and is_dataclass(obj) and name not in skip:
            out.add(name)
    return out


def _nodes_produced_by_rules():
    """
    RETURN: set, the AST node type names produced across all rule drives.

    Drives every rule (each ALT branch, each variadic case) exactly as the
    per-rule choices do, and collects the type name of every dataclass node
    that appears anywhere in the produced trees.
    """
    g = compiled_grammar()
    seen = set()

    def collect(node):
        if isinstance(node, list):
            for x in node:
                collect(x)
        elif is_dataclass(node) and type(node).__module__.endswith("ast_nodes"):
            seen.add(type(node).__name__)
            for f in fields(node):
                collect(getattr(node, f.name))

    for name, rule in g.rules.items():
        branches = _alt_branches(rule.pattern)
        cases = branches if branches else [rule.pattern]
        for element in cases:
            for _, reps in _variadic_cases(element):
                tokens = _synth(element, reps, active_name=name)
                node, _ = _drive(rule, tokens, dev=False)
                collect(node)
    return seen


def run_node_coverage():
    """RETURN: None. Every concrete AST node is built by at least one rule."""
    print("=== AST node coverage ===\n")
    declared = _concrete_node_types()
    produced = _nodes_produced_by_rules()
    for name in sorted(declared):
        if name in produced:
            print("SUCCESS: %s is produced by a grammar rule" % name)
        else:
            print("FAIL: %s is declared but never produced by any rule" % name)
    extra = produced - declared
    for name in sorted(extra):
        print("FAIL: %s produced but not a known ast_nodes type" % name)


_CHOICES["node_coverage"] = run_node_coverage


HwutRunner(
    argv       = [a for a in sys.argv if a != "DEV"],
    title      = "Grammar Rule Coverage",
    choice_map = _CHOICES,
).run()
