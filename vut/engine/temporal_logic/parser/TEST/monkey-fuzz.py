#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Monkey coverage. Walk the compiled grammar with a DETERMINISTIC random
         stream to synthesize large, valid rule-files, parse them, and print the
         resulting AST. The walk is reproducible (a profile = a seed + weights),
         so the printed AST is deterministic and the HWUT recording IS the
         assertion: any drift -- including a regression from the forthcoming
         stackless engine rewrite -- shows up as a binary diff.

CHOICES: deep, wide, luau, balanced.

DESCRIPTION:

Because the walk follows the actual grammar, it can only emit input the grammar
accepts; a parse error or a changed tree is therefore unambiguously a parser
bug, never a bad fixture. The walk is bounded two ways so it always terminates
and the printed tree stays reviewable:

    depth budget   each descent decrements a budget; at zero, ALT is forced to
                   a NON-RECURSIVE branch and PLUS/STAR take their minimum, so
                   recursion (e.g. <namespace> in <top-level>) cannot run away.
    repetition cap each PLUS/STAR count is drawn from the profile but capped.

PROFILES (a seed plus a weight dict):

    deep       biases ALT toward the recursive branch and grants a large depth
               budget, so namespaces nest deeply. This profile is the stack
               stress / acceptance case for a stackless engine: a recursive
               engine eventually overflows; a stackless one prints a stable,
               deep tree.
    wide       biases PLUS/STAR toward larger counts: long effect chains, many
               members, many untils, many args.
    luau       biases toward Luau-bearing effects and emits heavily nested
               (still balanced) fragment bodies.
    balanced   moderate everything.

The intrinsic check is liveness: the walk terminates and the parse raises
nothing. The recording check is identity: the printed AST matches GOOD.
______________________________________________________________________________
"""
import sys
import config                                                       # noqa: F401

from dataclasses import is_dataclass, fields

from vut.language_support.python.hwut_runner            import HwutRunner
from vut.language_support.python.deterministic_random   import DeterministicStream
from vut.engine.temporal_logic.parser.diagnostic        import DiagnosticReporter
from vut.engine.temporal_logic.parser.parser_engine     import (compiled_grammar,
                                                               Terminal,
                                                               LuauRef,
                                                               NonTerminal,
                                                               EngineParser)
from vut.engine.temporal_logic.parser.grammar import SEQ, ALT, OPT, PLUS, STAR
from vut.engine.temporal_logic.parser.lexer   import E_TokenId, Token


_FILLER = {
    E_TokenId.ID:     "X",
    E_TokenId.NUMBER: "1",
    E_TokenId.STRING: '"s"',
}

_LITERAL_BY_ID = {}
for _lit, _tid in compiled_grammar().literals.items():
    _LITERAL_BY_ID.setdefault(_tid, _lit)


def _tok(token_id, n):
    """RETURN: Token, a filler token; identifiers get a per-walk suffix 'Xn'."""
    if token_id == E_TokenId.ID:
        return Token(token_id, "X%d" % n, 0, 0)
    if token_id in _FILLER:
        return Token(token_id, _FILLER[token_id], 0, 0)
    return Token(token_id, _LITERAL_BY_ID.get(token_id, token_id.name), 0, 0)


class _ListLexer:
    """A lexer stand-in serving a prebuilt token list to the engine.

    'luau_texts' is a FIFO of the synthetic block texts to return, one per
    read_luau_block call, in the order the LUAU_OPEN tokens occur.
    """
    def __init__(self, tokens, luau_texts):
        """RETURN: None. Holds the token list, cursor, and luau text queue."""
        self.tokens     = tokens
        self.i          = 0
        self.luau_texts = list(luau_texts)
        self._luau_i    = 0

    def next(self):
        """RETURN: Token, the next token, or END_OF_FILE past the end."""
        if self.i < len(self.tokens):
            tok = self.tokens[self.i]
            self.i += 1
            return tok
        return Token(E_TokenId.END_OF_FILE, "", 0, 0)

    def read_luau_block(self, open_tok, role):
        """RETURN: Token, the next queued LUAU_BLOCK; rewinds one (see cover)."""
        self.i -= 1
        text = (self.luau_texts[self._luau_i]
                if self._luau_i < len(self.luau_texts) else "{ luau }")
        self._luau_i += 1
        return Token(E_TokenId.LUAU_BLOCK, text, open_tok.begin,
                     open_tok.begin + len(text))


class Walker:
    """Walks a compiled grammar with a DeterministicStream to emit valid tokens.

    A walk is fully determined by (stream seed, profile weights), so the token
    sequence -- and thus the parsed AST -- is reproducible.
    """
    def __init__(self, grammar, stream, profile):
        """RETURN: None. Binds the grammar, the random stream, and the profile."""
        self.g       = grammar
        self.s       = stream
        self.p       = profile
        self.id_n    = 0
        self.tokens  = []
        self.luau    = []
        self._active = []
        self.visited = set()      # rule names entered during the walk

    def walk_file(self, n_items):
        """RETURN: (tokens, luau_texts) for 'n_items' top-level constructs."""
        start = self.g.rules[self.g.start]
        for _ in range(n_items):
            self._emit(start, self.p["depth"])
        self.tokens.append(Token(E_TokenId.END_OF_FILE, "", 0, 0))
        return self.tokens, self.luau

    def _next_id(self):
        """RETURN: int, a fresh identifier suffix so names vary across the walk."""
        self.id_n += 1
        return self.id_n

    def _emit(self, element, budget):
        """RETURN: None. Appends tokens for 'element', bounded by 'budget'."""
        if isinstance(element, Terminal):
            self.tokens.append(_tok(element.token_id, self._next_id()))
            return
        if isinstance(element, LuauRef):
            self._emit_luau(budget)
            return
        if isinstance(element, NonTerminal):
            self.visited.add(element.name)
            self._active.append(element.name)
            try:
                self._emit(element.pattern, budget - 1)
            finally:
                self._active.pop()
            return
        op = element[0]
        if op == SEQ:
            for sub in element[1:]:
                self._emit(sub, budget)
        elif op == ALT:
            self._emit(self._pick_alt(element[1:], budget), budget)
        elif op == OPT:
            if budget > 0 and self._coin(self.p["opt"]):
                self._emit(element[1], budget)
        elif op == PLUS:
            for _ in range(self._rep_count(1, budget)):
                self._emit(element[1], budget)
        elif op == STAR:
            for _ in range(self._rep_count(0, budget)):
                self._emit(element[1], budget)
        else:
            raise ValueError("unknown op %r" % (op,))

    def _pick_alt(self, branches, budget):
        """
        RETURN: element, a chosen ALT branch.

        When the budget is spent, restricts the choice to branches that do NOT
        re-enter the rule being expanded so the walk terminates. While budget
        remains, with probability 'recurse'% prefers a branch that re-enters an
        active rule (deep nesting); otherwise picks uniformly.
        """
        if budget <= 0:
            active = set(self._active)
            safe = [b for b in branches if not _branch_reenters(b, active)]
            pool = safe if safe else _shallowest(branches)
            return pool[self.s.next_int(0, len(pool) - 1)]
        active = set(self._active)
        recursive = [b for b in branches if _branch_reenters(b, active)]
        if recursive and self._coin(self.p["recurse"]):
            pool = recursive
        else:
            pool = list(branches)
        return pool[self.s.next_int(0, len(pool) - 1)]

    def _rep_count(self, minimum, budget):
        """RETURN: int, a repetition count drawn from the profile and capped."""
        if budget <= 0:
            return max(minimum, 1) if minimum == 0 else minimum
        hi = self.p["reps"]
        return self.s.next_int(max(minimum, 1), hi)

    def _coin(self, pct):
        """RETURN: True with probability pct/100 (deterministic)."""
        return self.s.next_int(1, 100) <= pct

    def _emit_luau(self, budget):
        """RETURN: None. Emits a LUAU_OPEN and queues a balanced block body.

        The body is opaque to the parser, so only balance matters. The 'luau'
        profile nests braces to exercise the oracle's matching; others stay flat.
        """
        depth = self.s.next_int(0, self.p["luau"])
        inner = "x" + "{ y }" * depth
        text  = "{ " + inner + " }"
        self.luau.append(text)
        self.tokens.append(Token(E_TokenId.LUAU_OPEN, "{", 0, 0))


# Reachability closure: _REACHES[R] = set of rule names reachable FROM R
# (including R itself), computed once over the grammar graph. Used so the walker
# can ask "does this branch lead back into a rule currently being expanded?"
# without descending the (cyclic) grammar at walk time.
def _direct_refs(element, out):
    """RETURN: None. Collects the NonTerminal names directly named in 'element'."""
    if isinstance(element, NonTerminal):
        out.add(element.name)
        return
    if isinstance(element, (Terminal, LuauRef)):
        return
    for e in element[1:]:
        _direct_refs(e, out)


def _build_reaches(grammar):
    """RETURN: dict, name -> set of rule names reachable from it (transitive)."""
    direct = {}
    for name, rule in grammar.rules.items():
        s = set()
        _direct_refs(rule.pattern, s)
        direct[name] = s
    reaches = {n: set([n]) | direct[n] for n in direct}
    changed = True
    while changed:
        changed = False
        for n in reaches:
            for m in list(reaches[n]):
                if m in reaches and not reaches[m] <= reaches[n]:
                    reaches[n] |= reaches[m]
                    changed = True
    return reaches


_REACHES = _build_reaches(compiled_grammar())


def _branch_reenters(element, active):
    """RETURN: True if 'element' references a rule that can reach an active rule.

    Uses the precomputed reachability closure, so this is a finite set test even
    though the grammar graph is cyclic. 'active' is the set of rule names on the
    walk's current descent path.
    """
    refs = set()
    _direct_refs(element, refs)
    for r in refs:
        if _REACHES.get(r, set()) & active:
            return True
    return False


def _reaches_nonterminal(element):
    """RETURN: True if 'element' contains any NonTerminal (may recurse/descend)."""
    if isinstance(element, Terminal) or isinstance(element, LuauRef):
        return False
    if isinstance(element, NonTerminal):
        return True
    return any(_reaches_nonterminal(e) for e in element[1:])


def _shallowest(branches):
    """RETURN: list, the branch(es) with the fewest NonTerminals (fallback)."""
    scored = [(sum(_count_nt(e) for e in (b,)), b) for b in branches]
    lo = min(s for s, _ in scored)
    return [b for s, b in scored if s == lo]


def _count_nt(element):
    """RETURN: int, the number of NonTerminals reachable in 'element'."""
    if isinstance(element, (Terminal, LuauRef)):
        return 0
    if isinstance(element, NonTerminal):
        return 1
    return sum(_count_nt(e) for e in element[1:])


# --------------------------------------------------------------------------
# Profiles: a seed and weight dict each.
#   depth : descent budget before ALT is forced shallow / reps forced minimal
#   reps  : maximum PLUS/STAR repetition count
#   opt   : percent chance an OPT is taken
#   luau  : maximum nested-brace depth inside a Luau block
#   items : number of top-level constructs in the file
# --------------------------------------------------------------------------
_PROFILES = {
    "deep":     {"seed": 0x0DEE,  "depth": 30, "reps": 1, "opt": 20,
                 "luau": 0, "items": 3, "recurse": 80},
    "wide":     {"seed": 0x031D,  "depth": 6,  "reps": 5, "opt": 60,
                 "luau": 1, "items": 6, "recurse": 10},
    "luau":     {"seed": 0x1A41,  "depth": 6,  "reps": 2, "opt": 50,
                 "luau": 6, "items": 6, "recurse": 15},
    "balanced": {"seed": 0xBA1,   "depth": 8,  "reps": 2, "opt": 45,
                 "luau": 2, "items": 5, "recurse": 25},
    "states":   {"seed": 0x101,   "depth": 8,  "reps": 4, "opt": 40,
                 "luau": 1, "items": 6, "recurse": 20},
}


def _fmt(node, indent=0):
    """RETURN: str, a stable indented rendering of an AST node / list / leaf."""
    pad = "  " * indent
    if isinstance(node, list):
        if not node:
            return pad + "[]"
        return "\n".join(_fmt(x, indent) for x in node)
    if is_dataclass(node):
        lines = [pad + type(node).__name__]
        for f in fields(node):
            val = getattr(node, f.name)
            if is_dataclass(val) or isinstance(val, list):
                lines.append("%s  %s:" % (pad, f.name))
                lines.append(_fmt(val, indent + 2))
            else:
                lines.append("%s  %s = %r" % (pad, f.name, val))
        return "\n".join(lines)
    return pad + repr(node)


# --------------------------------------------------------------------------
# Source rendering and coverage (used by --debug and the coverage choice).
# --------------------------------------------------------------------------
# Tokens before which a newline reads naturally; keeps rendered source legible
# and, more importantly, lets the REAL lexer re-parse it (newlines separate the
# statement-ish constructs the language expects).
_NEWLINE_BEFORE = {
    E_TokenId.ARROW, E_TokenId.KW_UNTIL, E_TokenId.KW_ON, E_TokenId.KW_MODE,
    E_TokenId.KW_MGROUP, E_TokenId.KW_SM, E_TokenId.KW_STATE,
    E_TokenId.KW_EVENT, E_TokenId.KW_CLOCK, E_TokenId.KW_OPEN,
    E_TokenId.KW_CLOSE, E_TokenId.KW_HAS, E_TokenId.KW_DEFAULT,
    E_TokenId.KW_INIT, E_TokenId.KW_DEINIT, E_TokenId.KW_END_BLK,
}


def _render_source(tokens, luau_texts):
    """
    RETURN: str, readable source text for the synthesized token stream.

    Splices each queued Luau block in at its LUAU_OPEN and inserts a newline
    before statement-ish tokens so the text is legible and re-lexable by the
    REAL lexer. Identifiers keep their per-walk suffix so names stay distinct.
    """
    luau_i = 0
    out    = []
    for t in tokens:
        if t.kind == E_TokenId.END_OF_FILE:
            continue
        if t.kind == E_TokenId.LUAU_OPEN:
            text = luau_texts[luau_i] if luau_i < len(luau_texts) else "{ }"
            luau_i += 1
            if out and not out[-1].endswith("\n"):
                out.append(" ")
            out.append(text)
            continue
        if out and t.kind in _NEWLINE_BEFORE:
            out.append("\n")
        elif out and not out[-1].endswith("\n"):
            out.append(" ")
        out.append(t.text)
    return "".join(out).strip() + "\n"


def _collect_node_types(node, seen):
    """RETURN: None. Adds the type name of every AST dataclass found in 'node'."""
    if isinstance(node, list):
        for x in node:
            _collect_node_types(x, seen)
    elif is_dataclass(node) and type(node).__module__.endswith("ast_nodes"):
        seen.add(type(node).__name__)
        for f in fields(node):
            _collect_node_types(getattr(node, f.name), seen)


def _all_node_types():
    """RETURN: set, names of AST node types that can appear in a finished tree.

    Excludes RuleFile (the container) and the transient assembler nodes
    InitBlock/DeinitBlock, which exist only to be sorted into a parent's
    init/deinit fields and never persist in the tree.
    """
    import vut.engine.temporal_logic.parser.ast_nodes as ast_mod
    transient = {"RuleFile", "InitBlock", "DeinitBlock"}
    out = set()
    for name in dir(ast_mod):
        obj = getattr(ast_mod, name)
        if isinstance(obj, type) and is_dataclass(obj) and name not in transient:
            out.add(name)
    return out


def _strip_begin(text):
    """RETURN: str, the formatted AST with 'begin = N' lines removed.

    Used to compare structure across two parses whose only legitimate
    difference is source-offset provenance.
    """
    return "\n".join(l for l in text.splitlines()
                     if l.strip().split(" = ")[0] != "begin")


def _make_choice(profile_name):
    """RETURN: function, the HWUT run-function for one fuzz profile."""
    def run():
        debug = "--debug" in sys.argv
        g       = compiled_grammar()
        profile = _PROFILES[profile_name]
        stream  = DeterministicStream(profile["seed"])
        walker  = Walker(g, stream, profile)
        tokens, luau_texts = walker.walk_file(profile["items"])

        # Parse the synthesized token stream directly (the recorded path).
        parser = EngineParser.__new__(EngineParser)
        parser.reporter   = DiagnosticReporter()
        parser.grammar    = g
        parser.lexer      = _ListLexer(tokens, luau_texts)
        parser.tok        = parser.lexer.next()
        parser._top_first = g.rules[g.start].first
        rule_file = parser.parse()

        print("=== monkey: %s ===" % profile_name)
        print("tokens synthesized: %d" % (len(tokens) - 1))
        print("top-level items:    %d" % len(rule_file.items))
        if parser.reporter.errors:
            print("UNEXPECTED DIAGNOSTICS:")
            for d in parser.reporter.errors:
                print("   %s off=%d %s"
                      % (d.phase.name, d.source_offset, d.message))
        else:
            print("diagnostics:        none")

        # Per-profile coverage: rules the walk entered, node types it produced.
        node_types = set()
        _collect_node_types(rule_file.items, node_types)
        all_rules = set(g.rules)
        all_nodes = _all_node_types()
        print("## rules visited:      ((%d)) / ((%d))" % (len(walker.visited),
                                                       len(all_rules)))
        print("## node types built:   ((%d)) / ((%d))" % (len(node_types),
                                               len(all_nodes)))

        if debug:
            # Render the SAME walk as real source and re-parse it through the
            # REAL lexer, to (a) let a human read text vs. AST and (b) prove the
            # synthesized program is genuinely lexable, not just hand-fed.
            from vut.engine.temporal_logic.parser.parser_engine import parse \
                as real_parse
            from fake_luau_oracle import FakeLuauOracle
            source = _render_source(tokens, luau_texts)
            rep2   = DiagnosticReporter()
            rule_file2 = real_parse(source, FakeLuauOracle(), rep2)
            # Compare structure only: the token-fed walk emits offset-0 tokens,
            # so 'begin' provenance legitimately differs from the real lexer's.
            same = (_strip_begin(_fmt(rule_file.items))
                    == _strip_begin(_fmt(rule_file2.items)))
            print("\n[debug] rules NOT visited:  %s"
                  % (sorted(all_rules - walker.visited) or "(none)"))
            print("[debug] node types NOT built: %s"
                  % (sorted(all_nodes - node_types) or "(none)"))
            print("[debug] real-lexer reparse: %s, %d diagnostic(s)"
                  % ("AST matches" if same else "AST DIFFERS",
                     len(rep2.errors)))
            print("\n[debug] ---- rendered source ----")
            print(source.rstrip())
            print("[debug] ---- end source ----")

        print("\n-- AST --")
        print(_fmt(rule_file.items))
    return run


def _run_depth_bomb():
    """RETURN: None. Nested-namespace liveness probe; the stackless acceptance test.

    Parses 'open a.b ... close' nested to increasing depths and prints only a
    one-line PASS/FAIL per depth (not the AST), so the recording stays tiny and
    stable. A recursive engine overflows past a few dozen levels (RecursionError
    -> FAIL); a stackless engine parses every depth (PASS). This choice is the
    objective criterion for the engine rewrite.
    """
    from vut.engine.temporal_logic.parser.parser_engine import parse
    from vut.engine.temporal_logic.parser.diagnostic    import DiagnosticReporter
    from fake_luau_oracle import FakeLuauOracle

    print("=== monkey: depth-bomb (namespace nesting) ===")
    for n in (10, 50, 100, 500, 20000):
        src = "open a.b\n" * n + "on T => Ping()\n" + "close\n" * n
        rep = DiagnosticReporter()
        try:
            rf = parse(src, FakeLuauOracle(), rep)
            ok = (not rep.errors) and len(rf.items) == 1
            print("depth %5d : %s" % (n, "PASS" if ok else "FAIL (diagnostics)"))
        except RecursionError:
            print("depth %5d : FAIL (RecursionError: engine not stackless)" % n)


def _run_coverage():
    """RETURN: None. Aggregate rule and node-type coverage across all profiles.

    Runs every profile's walk, unions the rules entered and the AST node types
    produced, and reports what the monkey suite collectively exercises. SUCCESS
    per rule/node reached; FAIL for any never reached -- so a construct no
    profile touches is visible rather than silently untested.
    """
    g         = compiled_grammar()
    all_rules = set(g.rules)
    all_nodes = _all_node_types()
    seen_rules = set()
    seen_nodes = set()
    for name, profile in _PROFILES.items():
        walker = Walker(g, DeterministicStream(profile["seed"]), profile)
        tokens, luau_texts = walker.walk_file(profile["items"])
        parser = EngineParser.__new__(EngineParser)
        parser.reporter   = DiagnosticReporter()
        parser.grammar    = g
        parser.lexer      = _ListLexer(tokens, luau_texts)
        parser.tok        = parser.lexer.next()
        parser._top_first = g.rules[g.start].first
        rule_file = parser.parse()
        seen_rules |= walker.visited
        _collect_node_types(rule_file.items, seen_nodes)

    print("=== monkey: aggregate coverage ===")
    print("\n##-- rules ((%d)) / ((%d)) --" % (len(seen_rules & all_rules),
                                     len(all_rules)))
    for r in sorted(all_rules):
        print("%s: %s" % ("SUCCESS" if r in seen_rules else "FAIL", r))
    print("\n##-- node types (%d/%d) --" % (len(seen_nodes & all_nodes),
                                          len(all_nodes)))
    for n in sorted(all_nodes):
        print("%s: %s" % ("SUCCESS" if n in seen_nodes else "FAIL", n))


_CHOICES = {name: _make_choice(name) for name in _PROFILES}
_CHOICES["depth_bomb"] = _run_depth_bomb
_CHOICES["coverage"]   = _run_coverage


HwutRunner(
    argv       = [a for a in sys.argv if a not in ("DEV", "--debug")],
    title      = "Grammar Monkey Fuzz",
    choice_map = _CHOICES,
).run()
