#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Negative coverage. For every grammar rule, feed deliberately malformed
         token streams to that rule IN ISOLATION and record the parser's
         diagnostic response, so error detection and recovery are pinned by the
         HWUT recording just as the accepted language is by cover-syntax-tree.

CHOICES: one per grammar rule (e.g. '<causality>', '<mode>', ...).

DESCRIPTION:

Each rule is driven directly over a synthetic token list (no source text), the
same mechanism as cover-syntax-tree, but here the list is corrupted in three
mechanical ways derived from the rule's own canonical valid case:

    truncate         drop the final token of the valid case  ('A B C' -> 'A B')
    omit <i>         drop the i-th required terminal          ('A B C' -> 'A C')
    junk-head        replace the first token with an unexpected one

Only REQUIRED terminals (those outside any OPT/STAR, and the first element of a
PLUS) are dropped for 'omit': dropping an optional token would still be valid
and is not a negative case. A rule whose valid case is a single token has no
'truncate'/'omit' cases, only 'junk-head'.

For each malformed case the recording shows the input fragment, whether a node
was still built (recovery), and every diagnostic raised (phase, offset,
message). Driving a rule in ISOLATION keeps each case small and readable; a
sub-rule that simply stops early (consuming a valid prefix and leaving the rest)
is shown as 'no diagnostic; stopped early', which is itself meaningful.
______________________________________________________________________________
"""
import sys
from   config import HwutRunner

from vut.engine.temporal_logic.parser.diagnostic     import DiagnosticReporter
from vut.engine.temporal_logic.parser.parser_engine  import (compiled_grammar,
                                                             Terminal,
                                                             LuauRef,
                                                             NonTerminal,
                                                             EngineParser,
                                                             _ResyncError)
from vut.engine.temporal_logic.parser.grammar import SEQ, ALT, OPT, PLUS, STAR
from vut.engine.temporal_logic.parser.lexer   import E_TokenId, Token


# --------------------------------------------------------------------------
# Synthesis of a canonical VALID token list for a rule (minimal, one variadic
# point at its minimum). A trimmed copy of cover-syntax-tree's synthesizer with
# the same cycle-breaking so recursive rules (e.g. <namespace>) terminate.
# --------------------------------------------------------------------------
_FILLER = {
    E_TokenId.ID:     "X",
    E_TokenId.NUMBER: "1",
    E_TokenId.STRING: '"s"',
}

_LITERAL_BY_ID = {}
for _lit, _tid in compiled_grammar().literals.items():
    _LITERAL_BY_ID.setdefault(_tid, _lit)


def _tok(token_id):
    """RETURN: Token, a filler token for 'token_id' with a canonical lexeme."""
    if token_id in _FILLER:
        return Token(token_id, _FILLER[token_id], 0, 0)
    return Token(token_id, _LITERAL_BY_ID.get(token_id, token_id.name), 0, 0)


class _ListLexer:
    """A lexer stand-in serving a prebuilt token list (see cover-syntax-tree)."""
    def __init__(self, tokens):
        """RETURN: None. Holds the token list and a read cursor."""
        self.tokens = tokens
        self.i      = 0

    def next(self):
        """RETURN: Token, the next token, or END_OF_FILE past the end."""
        if self.i < len(self.tokens):
            tok = self.tokens[self.i]
            self.i += 1
            return tok
        return Token(E_TokenId.END_OF_FILE, "", 0, 0)

    def read_luau_block(self, open_tok, role):
        """RETURN: Token, a synthetic LUAU_BLOCK; rewinds one (see cover test)."""
        self.i -= 1
        return Token(E_TokenId.LUAU_BLOCK, "{ luau }", open_tok.begin,
                     open_tok.begin + 8)


def _synth(element, active_name=None):
    """RETURN: list, a minimal valid token sequence for 'element'."""
    state = {"active": set()}
    if active_name is not None:
        state["active"].add(active_name)
    return _synth_rec(element, state)


def _synth_rec(element, state):
    """RETURN: list, minimal tokens for 'element' with recursion broken."""
    if isinstance(element, Terminal):
        return [_tok(element.token_id)]
    if isinstance(element, LuauRef):
        return [Token(E_TokenId.LUAU_OPEN, "{", 0, 0)]
    if isinstance(element, NonTerminal):
        active = state["active"]
        active.add(element.name)
        try:
            return _synth_rec(element.pattern, state)
        finally:
            active.discard(element.name)
    op = element[0]
    if op == SEQ:
        out = []
        for sub in element[1:]:
            out += _synth_rec(sub, state)
        return out
    if op == ALT:
        return _synth_rec(_pick_alt(element[1:], state), state)
    if op == PLUS:
        return _synth_rec(element[1], state)         # exactly one repetition
    if op in (STAR, OPT):
        return []                                    # minimum is zero
    raise ValueError("unknown op %r" % (op,))


def _pick_alt(branches, state):
    """RETURN: element, an ALT branch not re-entering an active NonTerminal."""
    active = state["active"]
    for b in branches:
        if not _reenters(b, active):
            return b
    return branches[0]


def _reenters(element, active):
    """RETURN: True if 'element' can immediately reach an active NonTerminal."""
    if isinstance(element, (Terminal, LuauRef)):
        return False
    if isinstance(element, NonTerminal):
        return element.name in active or _reenters(element.pattern, active)
    op = element[0]
    if op == ALT:
        return all(_reenters(b, active) for b in element[1:])
    return _reenters(element[1], active)


# --------------------------------------------------------------------------
# Identify which token positions are REQUIRED (safe to omit for a negative
# case). A position is required if it is reached unconditionally -- not inside
# an OPT or STAR, and (for PLUS) only the first repetition is guaranteed.
# We mark required positions while re-synthesizing, in lockstep with _synth.
# --------------------------------------------------------------------------
def _required_flags(element, active_name=None):
    """
    RETURN: list[bool], one flag per synthesized token: True iff required.

    Mirrors _synth exactly, tagging each emitted token as required (reached
    unconditionally) or optional. Tokens under OPT/STAR are optional; the single
    PLUS repetition we emit is required (a PLUS needs at least one).
    """
    state = {"active": set()}
    if active_name is not None:
        state["active"].add(active_name)
    flags = []
    _flags_rec(element, state, True, flags)
    return flags


def _flags_rec(element, state, required, flags):
    """RETURN: None. Appends a required-flag per emitted token (see _synth)."""
    if isinstance(element, Terminal):
        flags.append(required)
        return
    if isinstance(element, LuauRef):
        flags.append(required)
        return
    if isinstance(element, NonTerminal):
        active = state["active"]
        active.add(element.name)
        try:
            _flags_rec(element.pattern, state, required, flags)
        finally:
            active.discard(element.name)
        return
    op = element[0]
    if op == SEQ:
        for sub in element[1:]:
            _flags_rec(sub, state, required, flags)
    elif op == ALT:
        _flags_rec(_pick_alt(element[1:], state), state, required, flags)
    elif op == PLUS:
        _flags_rec(element[1], state, required, flags)   # first rep required
    elif op in (STAR, OPT):
        pass                                             # emits nothing at min
    else:
        raise ValueError("unknown op %r" % (op,))


# --------------------------------------------------------------------------
# Drive a rule over a (malformed) token list in isolation.
# --------------------------------------------------------------------------
def _drive(rule, tokens):
    """
    RETURN: (node, reporter, consumed, leftover), the isolated-rule outcome.

    'node' is the AST built (or None if _ResyncError was raised); 'consumed' is
    how many of the supplied tokens were read; 'leftover' is the count left
    unconsumed (a sub-rule stopping early leaves a tail).
    """
    parser = EngineParser.__new__(EngineParser)
    parser.reporter   = DiagnosticReporter()
    parser.grammar    = compiled_grammar()
    parser.lexer      = _ListLexer(tokens)
    parser.tok        = parser.lexer.next()
    parser._top_first = parser.grammar.rules[parser.grammar.start].first
    node = None
    try:
        node = parser._match(rule)
    except _ResyncError:
        node = None
    consumed = parser.lexer.i - 1     # one token is always in lookahead
    if parser.tok.kind == E_TokenId.END_OF_FILE:
        consumed = len(tokens)
    leftover = len(tokens) - consumed
    return node, parser.reporter, consumed, max(leftover, 0)


def _fragment(tokens):
    """RETURN: str, the token list rendered as a readable fragment."""
    out = []
    for t in tokens:
        out.append("{ luau }" if t.kind == E_TokenId.LUAU_OPEN else t.text)
    return " ".join(out) if out else "(empty)"


def _junk_token():
    """RETURN: Token, an unexpected token unlikely to start any rule."""
    return Token(E_TokenId.MISMATCH, "?", 0, 0)


# --------------------------------------------------------------------------
# Build the malformed cases for one rule.
# --------------------------------------------------------------------------
def _negative_cases(rule):
    """
    RETURN: list[(label, tokens)], the malformed inputs for 'rule'.

    Derived mechanically from the rule's canonical valid case: a truncation
    (drop last token), one omission per required terminal, and a junk-head
    substitution. Duplicate token lists are de-duplicated by label set.
    """
    valid = _synth(rule.pattern, active_name=rule.name)
    flags = _required_flags(rule.pattern, active_name=rule.name)
    cases = []

    # junk-head: replace the first token with an unexpected one (or, for an
    # empty valid case, simply feed a lone junk token).
    if valid:
        cases.append(("junk-head", [_junk_token()] + valid[1:]))
    else:
        cases.append(("junk-head", [_junk_token()]))

    # truncate: drop the final token (only if there is more than one).
    if len(valid) >= 2:
        cases.append(("truncate", valid[:-1]))

    # omit-required: drop each required terminal in turn.
    omit_n = 0
    for i, req in enumerate(flags):
        if req:
            omit_n += 1
            cases.append(("omit-required-%d" % omit_n, valid[:i] + valid[i+1:]))

    return cases


def _print_outcome(node, reporter, consumed, leftover):
    """RETURN: None. Prints the recovery outcome and any diagnostics."""
    if node is None:
        print("   built:   no (rule abandoned)")
    else:
        print("   built:   %s" % type(node).__name__)
    print("   consumed: %d token(s); leftover: %d" % (consumed, leftover))
    if reporter.errors:
        for d in reporter.errors:
            print("   diag: %s off=%d %s"
                  % (d.phase.name, d.source_offset, d.message))
    else:
        print("   diag: (none; stopped early)")


def _make_choice(rule_name):
    """RETURN: function, the HWUT run-function for negative cases of a rule."""
    def run():
        g    = compiled_grammar()
        rule = g.rules[rule_name]
        print("=== negative: %s ===" % rule_name)
        for label, tokens in _negative_cases(rule):
            node, rep, consumed, leftover = _drive(rule, tokens)
            print("\n-- %s --" % label)
            print("   input: %s" % _fragment(tokens))
            _print_outcome(node, rep, consumed, leftover)
    return run


_GRAMMAR = compiled_grammar()
_CHOICES = {
    name.replace("<", "").replace(">", ""): _make_choice(name)
    for name in _GRAMMAR.rules
}


HwutRunner(
    argv       = [a for a in sys.argv if a != "DEV"],
    title      = "Grammar Rule Negative Coverage",
    choice_map = _CHOICES,
).run()
