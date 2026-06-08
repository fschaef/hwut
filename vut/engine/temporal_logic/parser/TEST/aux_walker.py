#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

Shared grammar-walk substrate for the parser test suite.

ONE skeleton, TWO policies. Every test that synthesizes a token stream from the
compiled grammar walks the SAME recursion here; the differences between the
canonical coverage walk and the random fuzz walk are isolated to a 'WalkPolicy'
that answers six questions:

    pick_alt(branches, ctx)      which ALT branch to descend
    opt_reps(node, ctx)          0 or 1 -- include an OPT body?
    plus_reps(node, ctx)         >= 1   -- how many PLUS repetitions?
    star_reps(node, ctx)         >= 0   -- how many STAR repetitions?
    on_terminal(node, ctx)       emit one TerminalNode's token
    on_luau(node, ctx)           emit one LuauNode's token

The structural recursion (Terminal/Luau/NonTerminal/Seq/Alt/Opt/Plus/Star) is
written ONCE, in 'walk'. A new grammar node type is handled in one place.

CONTEXT:

    The skeleton threads a 'WalkContext' carrying only what BOTH policies need:
    the active-rule stack (for recursion avoidance) and the 'required' flag
    (False once inside any OPT/STAR body). Each policy keeps its OWN private
    state (budget, RNG, markers, id counter, the emitted path) on itself or on a
    field of ctx it alone reads -- the skeleton never inspects policy state, so
    ctx does not accumulate one side's bookkeeping for the other.

SHARED PRIMITIVES (used by every walker AND by the drivers):

    FILLER / tok            canonical filler token for a Terminal
    ListLexer               serves a prebuilt token list to EngineParser
    drive                   parse a token list against one rule in isolation
    reaches / branch_reenters  precomputed reachability over the (cyclic) grammar

CANONICAL WALK (positive + negative coverage):

    PathStep / Path         a path with per-step 'required' provenance
    rule_paths              [i]  the canonical paths through a rule (one
                                 variadic point varied at a time)
    deviations              [ii] one malformed token list per deviation of a
                                 path (junk-head / truncate / omit-required)
______________________________________________________________________________
"""
from dataclasses import dataclass, field

from vut.engine.temporal_logic.parser.rule_parser import compiled_grammar
from vut.engine.temporal_logic.parser.core.ll1_engine import EngineParser, _ResyncError
from vut.engine.temporal_logic.parser.core.grammar_ast import (
        TerminalNode, LuauNode, NonTerminalNode,
        SeqNode, AltNode, OptNode, PlusNode, StarNode)
from vut.engine.temporal_logic.parser.core.lexer import Token
from vut.engine.temporal_logic.parser.core.terminals import (t_fr_luau_open,
                                                          t_fr_luau_block,
                                                          t_fr_eof,
                                                          t_fr_mismatch)
from vut.engine.temporal_logic.parser.grammar import (
        t_re_id, t_re_number, t_re_string, t_re_name_colon)


# ==========================================================================
# Shared token synthesis.
# ==========================================================================
FILLER = {
    t_re_id:          "X",
    t_re_number:      "1",
    t_re_string:      '"s"',
    t_re_name_colon:  "n:",
}


def tok(term, suffix=None):
    """RETURN: Token, a filler token for terminal 'term', identity = the Terminal.

    A value-bearing regex class gets its FILLER lexeme; a string/captured keyword
    gets its own spelling. 'suffix', when given, is appended to a value-bearing
    identifier so a walk can emit distinct names ('X' -> 'X1'); it is ignored for
    keywords, whose spelling is fixed.
    """
    if term in FILLER:
        base = FILLER[term]
        if suffix is not None and term is t_re_id:
            return Token(term, "%s%d" % (base, suffix), 0, 0)
        if suffix is not None and term is t_re_name_colon:
            return Token(term, "n%d:" % suffix, 0, 0)
        return Token(term, base, 0, 0)
    return Token(term, term.spelling, 0, 0)


def junk_token():
    """RETURN: Token, an unexpected token unlikely to start any rule."""
    return Token(t_fr_mismatch, "?", 0, 0)


# ==========================================================================
# Shared lexer stand-in.
# ==========================================================================
class ListLexer:
    """A lexer stand-in that serves a prebuilt token list to the engine.

    Implements the two methods EngineParser uses: 'next()' returns the next token
    (END_OF_FILE past the end) and 'read_luau_block(open_tok, role)' returns a
    synthetic LUAU_BLOCK. 'luau_texts', when non-empty, is a FIFO of block texts
    served one per read_luau_block call; when empty, every block reads '{ luau }'.
    """
    def __init__(self, tokens, luau_texts=()):
        """RETURN: None. Holds the token list, a read cursor, and a luau FIFO."""
        self.tokens     = tokens
        self.i          = 0
        self.luau_texts = list(luau_texts)
        self._luau_i    = 0

    def next(self):
        """RETURN: Token, the next token, or an END_OF_FILE sentinel past the end."""
        if self.i < len(self.tokens):
            t = self.tokens[self.i]
            self.i += 1
            return t
        return Token(t_fr_eof, "", 0, 0)

    def read_luau_block(self, open_tok, role):
        """RETURN: Token, a synthetic LUAU_BLOCK at the open offset.

        The engine consumes the LUAU_OPEN with _advance() and then calls next()
        to reload lookahead. The real lexer swallows the block bytes so the next
        token is the one AFTER the block; we step the cursor back by one so the
        engine's following next() returns the correct post-block token.
        """
        self.i -= 1
        text = (self.luau_texts[self._luau_i]
                if self._luau_i < len(self.luau_texts) else "{ luau }")
        self._luau_i += 1
        return Token(t_fr_luau_block, text, open_tok.begin,
                     open_tok.begin + len(text))


# ==========================================================================
# Shared executor: drive one rule over a (possibly malformed) token list.
# ==========================================================================
@dataclass(frozen=True)
class DriveResult:
    """The outcome of driving one rule in isolation over a token list."""
    node:     object
    reporter: object
    consumed: int
    leftover: int


def drive(grammar, rule, tokens, luau_texts=()):
    """RETURN: DriveResult, the isolated-rule parse outcome over 'tokens'.

    'node' is the AST built, or None if the rule was abandoned (_ResyncError).
    'consumed' is how many supplied tokens were read; 'leftover' is the tail a
    sub-rule left unconsumed by stopping early. A positive caller ignores the
    counts; a negative caller prints them as the recovery signal.
    """
    parser = EngineParser.__new__(EngineParser)
    parser.reporter   = DiagnosticReporter()
    parser.grammar    = grammar
    parser.lexer      = ListLexer(tokens, luau_texts)
    parser.tok        = parser.lexer.next()
    parser._top_first = grammar.rules[grammar.start].first
    node = None
    try:
        node = parser._match(rule)
    except _ResyncError:
        node = None
    consumed = parser.lexer.i - 1          # one token is always in lookahead
    if parser.tok.kind is t_fr_eof:
        consumed = len(tokens)
    leftover = len(tokens) - consumed
    return DriveResult(node, parser.reporter, consumed, max(leftover, 0))


# DiagnosticReporter is imported lazily to keep this module's import graph flat
# at definition time; it is the reporter EngineParser writes into.
from vut.engine.temporal_logic.parser.core.diagnostic import DiagnosticReporter  # noqa: E402


# ==========================================================================
# Shared reachability closure over the (cyclic) grammar graph.
# ==========================================================================
def _children(element):
    """RETURN: tuple, the child nodes of a combinator node.

    SeqNode/AltNode hold several children; Opt/Plus/Star hold one body. A leaf
    (Terminal/Luau/NonTerminal) has no children and is handled by the callers.
    """
    if isinstance(element, SeqNode):
        return element.parts
    if isinstance(element, AltNode):
        return element.branches
    if isinstance(element, (OptNode, PlusNode, StarNode)):
        return (element.body,)
    return ()


def _direct_refs(element, out):
    """RETURN: None. Collects the NonTerminal names directly named in 'element'."""
    if isinstance(element, NonTerminalNode):
        out.add(element.name)
        return
    if isinstance(element, (TerminalNode, LuauNode)):
        return
    for e in _children(element):
        _direct_refs(e, out)


def reaches(grammar):
    """RETURN: dict, rule name -> set of rule names reachable from it (transitive).

    Computed once over the grammar graph (the result includes the rule itself).
    Lets a walk ask 'does this branch lead back into a rule being expanded?' as a
    finite set test, without descending the cyclic grammar at walk time.
    """
    direct = {}
    for name, rule in grammar.rules.items():
        s = set()
        _direct_refs(rule.pattern, s)
        direct[name] = s
    out = {n: set([n]) | direct[n] for n in direct}
    changed = True
    while changed:
        changed = False
        for n in out:
            for m in list(out[n]):
                if m in out and not out[m] <= out[n]:
                    out[n] |= out[m]
                    changed = True
    return out


def shallow_reenters(element, active):
    """RETURN: True if 'element' can re-enter an active rule via its OBLIGATORY prefix.

    A SeqNode re-enters only if its first part does; the recursion deeper in a
    sequence (e.g. inside a PLUS) is reached only after a non-recursive prefix
    and terminates under a budget, so it does not count. This is the canonical
    walk's notion of re-entry -- distinct from the deep reachability closure the
    random walk uses, which asks whether a branch can EVER lead back.
    """
    if isinstance(element, (TerminalNode, LuauNode)):
        return False
    if isinstance(element, NonTerminalNode):
        return element.name in active or shallow_reenters(element.pattern, active)
    if isinstance(element, AltNode):
        return all(shallow_reenters(b, active) for b in element.branches)
    if isinstance(element, SeqNode):
        return shallow_reenters(element.parts[0], active) if element.parts else False
    return shallow_reenters(element.body, active)


def branch_reenters(element, active, reach):
    """RETURN: True if 'element' references a rule that can reach an active rule.

    'active' is the set of rule names on the current descent path; 'reach' is the
    precomputed closure from reaches(). Finite even though the grammar is cyclic.
    """
    refs = set()
    _direct_refs(element, refs)
    for r in refs:
        if reach.get(r, set()) & active:
            return True
    return False


# ==========================================================================
# The walk skeleton + policy interface.
# ==========================================================================
@dataclass
class WalkContext:
    """Carries ONLY what both policies need: the active-rule stack and 'required'.

    'active' is the set of rule names currently being expanded (recursion
    avoidance). 'required' is True while the skeleton is on an unconditional path
    and False once inside any OPT/STAR body -- the canonical policy reads it to
    tag PathSteps; the random policy ignores it. Policies keep their own private
    state on themselves, not here.
    """
    active:   set  = field(default_factory=set)
    required: bool = True


class WalkPolicy:
    """The six decisions that distinguish one grammar walk from another.

    A policy emits tokens by appending to its own collection in on_terminal /
    on_luau; the skeleton never holds the result. Subclasses keep any extra
    state (budget, RNG, markers, id counter, the path being built) as their own
    attributes.
    """
    def pick_alt(self, branches, ctx):
        """RETURN: element, the ALT branch to descend."""
        raise NotImplementedError

    def opt_reps(self, node, ctx):
        """RETURN: int (0 or 1), whether to include this OPT's body."""
        raise NotImplementedError

    def plus_reps(self, node, ctx):
        """RETURN: int (>= 1), how many times to repeat this PLUS body."""
        raise NotImplementedError

    def star_reps(self, node, ctx):
        """RETURN: int (>= 0), how many times to repeat this STAR body."""
        raise NotImplementedError

    def on_terminal(self, node, ctx):
        """RETURN: None. Emit one TerminalNode's token (records 'required' if it cares)."""
        raise NotImplementedError

    def on_luau(self, node, ctx):
        """RETURN: None. Emit one LuauNode's token."""
        raise NotImplementedError


def walk(element, policy, ctx):
    """RETURN: None. Walk 'element', driving emission through 'policy'.

    The structural recursion is fixed; every grammar-shaping decision is a
    policy hook. NonTerminal pushes/pops the active set so recursion avoidance
    works for both policies; OPT/STAR descend with ctx.required forced False so
    the canonical policy tags those tokens optional.
    """
    if isinstance(element, TerminalNode):
        policy.on_terminal(element, ctx)
        return
    if isinstance(element, LuauNode):
        policy.on_luau(element, ctx)
        return
    if isinstance(element, NonTerminalNode):
        ctx.active.add(element.name)
        try:
            walk(element.pattern, policy, ctx)
        finally:
            ctx.active.discard(element.name)
        return
    if isinstance(element, SeqNode):
        for sub in element.parts:
            walk(sub, policy, ctx)
        return
    if isinstance(element, AltNode):
        walk(policy.pick_alt(element.branches, ctx), policy, ctx)
        return
    if isinstance(element, OptNode):
        if policy.opt_reps(element, ctx) > 0:
            _walk_body(element.body, policy, ctx)
        return
    if isinstance(element, PlusNode):
        for k in range(policy.plus_reps(element, ctx)):
            # the first repetition of a PLUS is required; later ones are not
            _walk_body(element.body, policy, ctx, required=(k == 0))
        return
    if isinstance(element, StarNode):
        for _ in range(policy.star_reps(element, ctx)):
            _walk_body(element.body, policy, ctx)
        return
    raise ValueError("unknown grammar node %r" % (element,))


def _walk_body(body, policy, ctx, required=False):
    """RETURN: None. Walk a variadic body with ctx.required saved and restored."""
    saved = ctx.required
    ctx.required = required and saved
    try:
        walk(body, policy, ctx)
    finally:
        ctx.required = saved


# ==========================================================================
# Canonical policy + the path/deviation generators (positive & negative).
# ==========================================================================
@dataclass(frozen=True)
class PathStep:
    """One emitted token of a canonical path, with its required-ness provenance."""
    token:    Token
    required: bool


@dataclass(frozen=True)
class Path:
    """A labelled canonical path: a case name plus its ordered steps."""
    label: str
    steps: tuple

    def tokens(self):
        """RETURN: list, the Token of every step, in order."""
        return [s.token for s in self.steps]


class _CanonicalPolicy(WalkPolicy):
    """Emits the minimal canonical path: first non-reentrant ALT branch, a fixed
    repetition budget spent on ONE variadic point, minimal fillers elsewhere.

    'reps' is the count for the FIRST PLUS/STAR met and present/absent for the
    FIRST OPT; later variadic points take their minimum (PLUS->1, STAR->0,
    OPT->0) so each path isolates one varying point. The emitted PathSteps carry
    ctx.required so the negative generator needs no second walk.
    """
    def __init__(self, reps, minimal=False):
        """RETURN: None. Binds the variadic budget.

        'minimal' True produces the pure-minimum path (every OPT absent, every
        STAR zero, every PLUS one repetition) -- the canonical valid case the
        negative deviations are derived from. 'minimal' False spends 'reps' on
        the first variadic point, which the positive case enumeration varies.

        The canonical re-entry test is shallow (shallow_reenters), so this policy
        needs no reachability closure -- unlike the random walk.
        """
        self.reps  = reps
        self.used  = minimal      # minimal -> budget already spent, all minimums
        self.steps = []           # PathSteps accumulated during the walk

    def pick_alt(self, branches, ctx):
        """RETURN: element, the first branch not re-entering an active rule.

        Uses the canonical (shallow) re-entry test: a branch counts as
        re-entering only if its obligatory prefix leads back, so a rule like
        <namespace> (a terminal-led sequence whose recursion sits inside a PLUS)
        is a valid pick. Distinct from the random walk's deep-closure test.
        """
        for b in branches:
            if not shallow_reenters(b, ctx.active):
                return b
        return branches[0]

    def _budget(self, node):
        """RETURN: int, reps for the first variadic point, minimum thereafter."""
        if not self.used:
            self.used = True
            if isinstance(node, OptNode):
                return 1 if self.reps >= 1 else 0
            return self.reps
        return 1 if isinstance(node, PlusNode) else 0

    def opt_reps(self, node, ctx):
        """RETURN: int, the OPT budget (one varying point)."""
        return self._budget(node)

    def plus_reps(self, node, ctx):
        """RETURN: int, the PLUS budget (>= 1).

        _budget returns 'reps' (>=1) for the first variadic point and 1 for a
        later PLUS, so it is already >= 1 for a PLUS; no extra clamp is needed.
        """
        return self._budget(node)

    def star_reps(self, node, ctx):
        """RETURN: int, the STAR budget."""
        return self._budget(node)

    def on_terminal(self, node, ctx):
        """RETURN: None. Append a filler-token PathStep tagged with ctx.required."""
        self.steps.append(PathStep(tok(node.token_id), ctx.required))

    def on_luau(self, node, ctx):
        """RETURN: None. Append a LUAU_OPEN PathStep tagged with ctx.required."""
        self.steps.append(PathStep(Token(t_fr_luau_open, "{", 0, 0), ctx.required))


def _first_variadic(element):
    """RETURN: the first PLUS/STAR/OPT node under 'element', or None."""
    if isinstance(element, (TerminalNode, LuauNode)):
        return None
    if isinstance(element, NonTerminalNode):
        return _first_variadic(element.pattern)
    if isinstance(element, (PlusNode, StarNode, OptNode)):
        return element
    children = element.parts if isinstance(element, SeqNode) else element.branches
    for sub in children:
        found = _first_variadic(sub)
        if found is not None:
            return found
    return None


def _alt_branches(pattern):
    """RETURN: list, the branches of the first ALT under 'pattern', or []."""
    if isinstance(pattern, NonTerminalNode):
        return _alt_branches(pattern.pattern)
    if isinstance(pattern, AltNode):
        return list(pattern.branches)
    return []


def _variadic_cases(pattern):
    """RETURN: list, the (label, reps) cases for a rule's first variadic point.

    PLUS -> 1x,2x; STAR -> 0x,1x,2x; OPT -> absent,present; none -> one default.
    """
    node = _first_variadic(pattern)
    if isinstance(node, PlusNode):
        return [("1x", 1), ("2x", 2)]
    if isinstance(node, StarNode):
        return [("0x", 0), ("1x", 1), ("2x", 2)]
    if isinstance(node, OptNode):
        return [("absent", 0), ("present", 1)]
    return [("default", 1)]


def _canonical_path(grammar, rule, label, reps):
    """RETURN: Path, one canonical path through 'rule' for the given budget."""
    pol = _CanonicalPolicy(reps)
    ctx = WalkContext(active={rule.name})
    walk(rule.pattern, pol, ctx)
    return Path(label, tuple(pol.steps))


def rule_paths(grammar, rule):
    """RETURN: iterator of Path, the canonical paths through 'rule'.   [i]

    An ALT rule yields one path per branch ('alternative i'); otherwise one path
    per case of the rule's first variadic point (1x/2x, 0x/1x/2x, absent/present)
    or a single 'default' path. Each path's steps carry per-token required-ness.
    """
    branches = _alt_branches(rule.pattern)
    if branches:
        for i, branch in enumerate(branches):
            pol = _CanonicalPolicy(1)
            ctx = WalkContext(active={rule.name})
            walk(branch, pol, ctx)
            yield Path("alternative %d" % i, tuple(pol.steps))
    else:
        for label, reps in _variadic_cases(rule.pattern):
            yield _canonical_path(grammar, rule, label, reps)


def minimal_path(grammar, rule):
    """RETURN: Path, the single pure-minimum canonical path through 'rule'.

    Every OPT absent, every STAR zero, every PLUS one repetition -- the canonical
    valid case the negative 'deviations' are derived from. Distinct from
    rule_paths, which enumerates the positive cases by varying one point.
    """
    pol = _CanonicalPolicy(0, minimal=True)
    ctx = WalkContext(active={rule.name})
    walk(rule.pattern, pol, ctx)
    return Path("minimal", tuple(pol.steps))


def deviations(path):
    """RETURN: iterator of (label, tokens), one malformed input per deviation.  [ii]

    Derived from a single canonical Path, reading PathStep.required directly:
        junk-head            first token replaced with an unexpected one
        truncate             final token dropped              (only if len >= 2)
        omit-required-k      each required step dropped in turn
    Dropping an OPTIONAL token would still be valid, so only required steps are
    omitted. A single-token path yields only 'junk-head'.
    """
    toks = path.tokens()
    if toks:
        yield ("junk-head", [junk_token()] + toks[1:])
    else:
        yield ("junk-head", [junk_token()])
    if len(toks) >= 2:
        yield ("truncate", toks[:-1])
    omit_n = 0
    for i, step in enumerate(path.steps):
        if step.required:
            omit_n += 1
            yield ("omit-required-%d" % omit_n, toks[:i] + toks[i + 1:])
