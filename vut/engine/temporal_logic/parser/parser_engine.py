"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

TABLE-DRIVEN PARSE ENGINE  --  LL(1) over the declarative grammar

Three stages turn the declarative GRAMMAR (grammar.py) into an AST:

    1. PREPROCESS  Resolve each grammar string to an engine symbol: a literal
                   ('on', '=>') to its E_TokenId via a table derived from the
                   lexer; '#ID'/'#NUMBER'/'#STRING' to their class token id;
                   '{luau:ROLE}' to a LuauRef; '<x>' to a NonTerminal bound to
                   its compiled pattern and reduce action.

    2. ANALYSE     Compute FIRST sets over the compiled grammar and VALIDATE
                   LL(1): every ALT branch must have a disjoint FIRST set,
                   and no optional/repetition may collide with what can follow.
                   Conflicts are reported, not hidden.

    3. PARSE       A recursive-descent interpreter walks the compiled patterns
                   with one-token lookahead, choosing ALT branches by FIRST
                   set, and runs each rule's action to build the AST node.

The engine is grammar-agnostic: it knows the combinators and the symbol kinds,
not the rule-file language. Swapping GRAMMAR/ACTIONS reuses it unchanged.
______________________________________________________________________________
"""
from dataclasses import dataclass

from .lexer       import Lexer, E_TokenId, _TOKEN_SPEC
from .diagnostic  import Diagnostic, Phase, DiagnosticReporter
from ..luau.luau_fragment import Role
from . import grammar   as G
from .grammar import SEQ, ALT, OPT, PLUS, STAR


# ---------------------------------------------------------------------------
# Compiled symbol kinds.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Terminal:
    """A resolved terminal: the token id to match and whether it bears a value.

    'silent' True means the matched token is punctuation and is dropped from a
    frame's values (keywords, symbols). False means it contributes (ID, NUMBER,
    STRING).
    """
    token_id: E_TokenId
    silent:   bool


@dataclass(frozen=True)
class LuauRef:
    """A resolved Luau span: the Role under which the parser drives the oracle."""
    role: Role


class NonTerminal:
    """A resolved rule: its name, compiled pattern, reduce action, FIRST set.

    'action' is None for a pass-through rule (forwards its single value). 'first'
    is filled by the analysis stage.
    """
    def __init__(self, name, action):
        """RETURN: None. Holds name and action; pattern/first set later."""
        self.name    = name
        self.action  = action
        self.pattern = None       # set during compile
        self.first   = set()      # set during analysis

    def __repr__(self):
        """RETURN: str, the rule name in angle brackets for diagnostics."""
        return "NT(%s)" % self.name


class LL1ConflictError(Exception):
    """Raised by analysis when the grammar is not LL(1).

    Carries the list of human-readable conflict descriptions so the grammar
    author sees every conflict at once.
    """
    def __init__(self, conflicts):
        super().__init__("%d LL(1) conflict(s)" % len(conflicts))
        self.conflicts = conflicts


# ---------------------------------------------------------------------------
# Stage 1: literal table from the lexer, and the preprocessor.
# ---------------------------------------------------------------------------
def _literal_table():
    """
    RETURN: dict, mapping a literal spelling to its E_TokenId id.

    Derived from the lexer's _TOKEN_SPEC: fixed-keyword patterns ('\\bon\\b')
    and escaped-symbol patterns ('=>', '\\+') become entries; character-class
    patterns (ID/NUMBER/STRING) and skip groups are excluded. One source of
    truth, shared with the lexer, so a spelling can never drift.
    """
    table = {}
    classes = {E_TokenId.ID, E_TokenId.NUMBER, E_TokenId.STRING,
               E_TokenId.MISMATCH, E_TokenId.LUAU_OPEN, E_TokenId.LUAU_BLOCK,
               E_TokenId.END_OF_FILE}
    for kind, pattern in _TOKEN_SPEC:
        if isinstance(kind, str):           # COMMENT / WS skip groups
            continue
        if kind in classes:
            continue
        literal = _literal_of(pattern)
        if literal is not None:
            table[literal] = kind
    return table


def _literal_of(pattern):
    """
    RETURN: str, the fixed spelling a pattern matches, or None if not fixed.

    A keyword pattern carries a word boundary on the side that abuts an
    identifier char: '\\bword\\b' (bare keyword), '\\bword:' (trailing-colon
    keyword, e.g. 'mode:'), or ':word\\b' (leading-colon terminator, e.g.
    ':end'). Each '\\b' is stripped independently. A symbol pattern is the
    (possibly escaped) literal. An escaped char ('\\+') is literal regardless of
    being a metacharacter; an UNescaped metacharacter means the pattern is a
    class or quantifier, not a fixed spelling, so None is returned.
    """
    p = pattern
    if p.startswith(r'\b'):
        p = p[2:]
    if p.endswith(r'\b'):
        p = p[:-2]
    META = set('[](){}?*+|.^$')
    out = []
    i = 0
    while i < len(p):
        if p[i] == '\\' and i + 1 < len(p):
            out.append(p[i + 1])        # escaped: literal regardless
            i += 2
        else:
            if p[i] in META:            # unescaped metachar: not a fixed literal
                return None
            out.append(p[i])
            i += 1
    return "".join(out)


_CLASS_TOKEN = {
    "#ID":         E_TokenId.ID,
    "#NUMBER":     E_TokenId.NUMBER,
    "#STRING":     E_TokenId.STRING,
    "#NAME_COLON": E_TokenId.NAME_COLON,
}


class Grammar:
    """The compiled grammar: a name->NonTerminal map with FIRST sets analysed.

    'build()' compiles GRAMMAR/ACTIONS, computes FIRST sets, and validates LL(1)
    (raising LL1ConflictError on conflict). 'start' names the rule the engine
    begins each top-level item with.
    """
    def __init__(self, grammar_dict, actions, start):
        """RETURN: None. Compiles, analyses, and validates the grammar."""
        self.literals = _literal_table()
        self.rules    = {name: NonTerminal(name, actions.get(name))
                         for name in grammar_dict}
        self.start    = start
        for name, pattern in grammar_dict.items():
            self.rules[name].pattern = self._compile(pattern)
        self._analyse()

    # -- compile --------------------------------------------------------
    def _compile(self, element):
        """
        RETURN: compiled element (Terminal, LuauRef, NonTerminal, or tuple).

        Resolves a grammar string to its symbol; recurses into combinator
        tuples, leaving the PO tag in place.
        """
        if isinstance(element, tuple):
            return (element[0],) + tuple(self._compile(e) for e in element[1:])
        elif not isinstance(element, str):
            raise ValueError("grammar element not a str/tuple: %r" % (element,))
        elif element.startswith("<"):
            if element not in self.rules:
                raise ValueError("undefined non-terminal %r" % element)
            return self.rules[element]
        elif element.startswith("{luau:"):
            role_name = element[len("{luau:"):-1]
            return LuauRef(Role[role_name])
        elif element in _CLASS_TOKEN:
            tid = _CLASS_TOKEN[element]
            return Terminal(tid, silent=False)
        elif element in self.literals:
            captured = element in G.CAPTURED_LITERALS
            return Terminal(self.literals[element], silent=not captured)
        else:
            raise ValueError(
                "unresolved grammar literal %r: no token in the lexer's "
                "_TOKEN_SPEC spells it. The grammar references %r but lexer.py "
                "defines no matching keyword/symbol pattern." % (element, element))

    # -- analysis: FIRST sets + LL(1) validation ------------------------
    def _analyse(self):
        """RETURN: None. Computes FIRST sets to a fixpoint, then validates LL(1)."""
        changed = True
        while changed:
            changed = False
            for nt in self.rules.values():
                before = len(nt.first)
                nt.first |= self._first_of(nt.pattern)
                if len(nt.first) != before:
                    changed = True
        self._validate_ll1()

    def _first_of(self, element):
        """
        RETURN: set, the E_TokenId ids that can begin 'element'.

        For a NonTerminal returns its current FIRST (fixpoint iteration fills
        these in). A LuauRef begins with LUAU_OPEN. Nullable handling: OPT/STAR
        contribute their body's FIRST but are themselves nullable; SEQ stops at
        the first non-nullable element.
        """
        if   isinstance(element, Terminal):    return {element.token_id}
        elif isinstance(element, LuauRef):     return {E_TokenId.LUAU_OPEN}
        elif isinstance(element, NonTerminal): return set(element.first)

        op = element[0]
        if op == SEQ:
            result = set()
            for sub in element[1:]:
                result |= self._first_of(sub)
                if not self._nullable(sub):
                    break
            return result

        if op == ALT:
            result = set()
            for sub in element[1:]:
                result |= self._first_of(sub)
            return result
        elif op in (OPT, PLUS, STAR):
            return self._first_of(element[1])
        else:
            raise ValueError("unknown op %r" % (op,))

    def _nullable(self, element):
        """
        RETURN: True,  if 'element' can match the empty token sequence.
                False, else.

        OPT and STAR are nullable; PLUS is not; SEQ is nullable iff all parts
        are; ALT iff any branch is. Terminals and Luau refs are never nullable.
        NonTerminal nullability is approximated as False here -- the rule-file
        grammar has no nullable non-terminals, so this stays exact for it.
        """
        if isinstance(element, (Terminal, LuauRef, NonTerminal)):
            return False
        op = element[0]
        if op in (OPT, STAR):
            return True
        elif op == PLUS:
            return False
        elif op == SEQ:
            return all(self._nullable(s) for s in element[1:])
        elif op == ALT:
            return any(self._nullable(s) for s in element[1:])
        return False

    def _validate_ll1(self):
        """RETURN: None. Raises LL1ConflictError if any ALT branch FIRST overlaps.

        For every ALT in every rule, the FIRST sets of the branches must be
        pairwise disjoint; otherwise one lookahead token cannot select a unique
        branch. Reports each overlapping pair with the rule and tokens involved.
        """
        conflicts = []
        for nt in self.rules.values():
            self._check_alts(nt.name, nt.pattern, conflicts)
        if conflicts:
            raise LL1ConflictError(conflicts)

    def _check_alts(self, rule_name, element, conflicts):
        """RETURN: None. Recursively checks every ALT under 'element'."""
        if isinstance(element, (Terminal, LuauRef, NonTerminal)):
            return
        op = element[0]
        if op == ALT:
            seen = {}
            for branch in element[1:]:
                f = self._first_of(branch)
                for tid in f:
                    if tid in seen:
                        conflicts.append(
                            "rule %s: token %s starts two ALT branches"
                            % (rule_name, tid.name))
                    else:
                        seen[tid] = branch
        for sub in element[1:]:
            self._check_alts(rule_name, sub, conflicts)


# ---------------------------------------------------------------------------
# Stage 3: the LL(1) interpreter.
# ---------------------------------------------------------------------------
@dataclass
class Frame:
    """The collected values and start offset handed to a rule's reduce action.

    'values' holds the matched child values with silent (punctuation) terminals
    already dropped. 'begin' is the offset of the rule's first token.
    """
    values: list
    begin:  int


class _ResyncError(Exception):
    """Internal: abandon the current top-level item and resync. Never escapes."""
    pass


class EngineParser:
    """Parses a rule file by interpreting a compiled Grammar with LL(1) lookahead.

    Drives the pull-Lexer with one token of lookahead, picks ALT branches by
    FIRST set, and runs reduce actions to build the AST. The walk is stackless:
    an explicit work stack and frame stack replace recursion, so deeply nested
    constructs (notably namespaces) cannot overflow the interpreter. Resyncs at
    'end'/top-level keywords on error.
    """
    _TOP_LEVEL = None       # filled after Grammar is known

    def __init__(self, source_text, oracle, reporter, grammar):
        """RETURN: None. Wires the lexer, grammar, and primes lookahead."""
        self.reporter = reporter
        self.grammar  = grammar
        self.lexer    = Lexer(source_text, oracle, reporter)
        self.tok      = self.lexer.next()
        self._top_first = self.grammar.rules[self.grammar.start].first

    # -- token plumbing -------------------------------------------------
    def _advance(self):
        """RETURN: Token, the current token; loads the next into lookahead."""
        cur = self.tok
        self.tok = self.lexer.next()
        return cur

    def _error(self, message, fatal=False):
        """RETURN: None. Appends a PARSER diagnostic at the lookahead."""
        self.reporter.report(Diagnostic(
            phase=Phase.PARSER, message=message,
            source_offset=self.tok.begin, fatal=fatal))

    def _resync(self):
        """RETURN: None. Resyncs to the next safe boundary after an error.

        Stops AT the next top-level keyword (a new item begins there), or
        CONSUMES an aggregate-closing 'end' and stops after it. Causalities have
        no terminator, so a top-level keyword is the boundary for a malformed
        rule; 'end' is the boundary inside a mode group or state machine.
        """
        anchors = self._top_first
        while True:
            if self.tok.kind == E_TokenId.END_OF_FILE:
                return
            if self.tok.kind == E_TokenId.KW_END_BLK:
                self._advance()
                return
            if self.tok.kind in anchors:
                return
            self._advance()

    # -- entry ----------------------------------------------------------
    def parse(self):
        """
        RETURN: RuleFile, the assembled AST (possibly partial on errors).

        Repeats the start rule until end-of-file, recovering past each error so
        every top-level item is attempted in one pass.
        """
        from . import ast_nodes as ast
        rule_file = ast.RuleFile()
        start = self.grammar.rules[self.grammar.start]
        while self.tok.kind != E_TokenId.END_OF_FILE:
            try:
                item = self._match(start)
                if item is not None:
                    rule_file.items.append(item)
            except _ResyncError:
                self._resync()
        return rule_file

    # -- the interpreter (stackless) ------------------------------------
    #
    # The walk is driven by an explicit work stack instead of Python recursion,
    # so parse depth is bounded by the heap, not the C stack: deeply nested
    # namespaces (open ... open ... close ... close) can no longer overflow.
    #
    # Two stacks cooperate:
    #   work   -- instructions still to perform, processed LIFO.
    #   frames -- one Frame per NonTerminal currently being assembled; child
    #             values append to frames[-1]; a REDUCE pops it, runs the
    #             rule's action, and appends the result to the new top frame.
    #
    # Work instructions (tuples, tagged by [0]):
    #   (ELEM,  element)  -- expand 'element', appending values to frames[-1]
    #   (REDUCE, nt)      -- finish NonTerminal 'nt': pop its frame, act, append
    #   (LOOP, body, plus_done) -- a PLUS/STAR iteration point (see below)
    #
    # A SEQ pushes its parts in reverse so they run left-to-right. An ALT
    # chooses its branch from one-token lookahead and pushes it. OPT pushes its
    # body iff the lookahead starts it. PLUS/STAR push a LOOP marker that, each
    # time it surfaces, re-checks the lookahead and -- while the body still
    # starts -- pushes the body and another LOOP beneath it, turning the
    # repetition into stack iteration.
    _ELEM   = 0
    _REDUCE = 1
    _LOOP   = 2

    def _match(self, element):
        """
        RETURN: value, the result of matching 'element' against the stream.

        Drives 'element' to completion on an explicit work stack and returns the
        value it produced (a NonTerminal's action result, a Terminal's token, a
        Luau node, or None for silent/empty). Mismatches raise _ResyncError,
        which abandons the whole walk for the caller (parse) to recover.

        Uses a sentinel root frame to collect the single top-level value so the
        same value-append discipline applies uniformly at every level.
        """
        root = Frame(values=[], begin=self.tok.begin)
        frames = [root]
        work = [(self._ELEM, element)]
        while work:
            item = work.pop()
            tag = item[0]
            if tag == self._ELEM:
                self._step_elem(item[1], frames, work)
            elif tag == self._REDUCE:
                self._step_reduce(item[1], frames)
            else:  # _LOOP
                self._step_loop(item[1], frames, work)
        return root.values[0] if root.values else None

    def _step_elem(self, element, frames, work):
        """RETURN: None. Expands one element, mutating 'frames'/'work' in place."""
        if isinstance(element, Terminal):
            value = self._match_terminal(element)
            if value is not None:
                frames[-1].values.append(value)
            return
        if isinstance(element, LuauRef):
            frames[-1].values.append(self._match_luau(element))
            return
        if isinstance(element, NonTerminal):
            # Open a new frame; schedule its reduce, then expand its pattern
            # (pushed last so it runs first).
            frames.append(Frame(values=[], begin=self.tok.begin))
            work.append((self._REDUCE, element))
            work.append((self._ELEM, element.pattern))
            return
        op = element[0]
        if op == SEQ:
            for sub in reversed(element[1:]):
                work.append((self._ELEM, sub))
        elif op == ALT:
            work.append((self._ELEM, self._choose_alt(element)))
        elif op == OPT:
            if self._starts(element[1]):
                work.append((self._ELEM, element[1]))
        elif op == PLUS:
            # One mandatory body, then a loop for the rest.
            work.append((self._LOOP, element[1]))
            work.append((self._ELEM, element[1]))
        elif op == STAR:
            work.append((self._LOOP, element[1]))
        else:
            raise ValueError("unknown op %r" % (op,))

    def _step_loop(self, body, frames, work):
        """RETURN: None. One repetition check: if the body starts, take it again."""
        if self._starts(body):
            work.append((self._LOOP, body))
            work.append((self._ELEM, body))

    def _step_reduce(self, nt, frames):
        """RETURN: None. Pops nt's frame, runs its action, appends to parent."""
        frame = frames.pop()
        if nt.action is None:
            value = frame.values[0] if frame.values else None
        else:
            value = nt.action(frame)
        if value is not None:
            frames[-1].values.append(value)

    def _match_terminal(self, term):
        """RETURN: Token or None. Consumes the expected token; None if silent."""
        if self.tok.kind != term.token_id:
            self._error("expected %s, found %s"
                        % (term.token_id.name, self.tok.kind.name))
            raise _ResyncError()
        tok = self._advance()
        return None if term.silent else tok

    def _match_luau(self, luau_ref):
        """RETURN: Luau, the span read under the ref's role; resyncs on failure."""
        from . import ast_nodes as ast
        if self.tok.kind != E_TokenId.LUAU_OPEN:
            self._error("expected '{' Luau block, found %s" % self.tok.kind.name)
            raise _ResyncError()
        open_tok = self._advance()
        block = self.lexer.read_luau_block(open_tok, luau_ref.role)
        if block is None:
            self._error("Luau oracle failed", fatal=True)
            raise _ResyncError()
        self.tok = self.lexer.next()
        return ast.Luau(text=block.text, role=luau_ref.role, begin=block.begin)

    def _choose_alt(self, alt_element):
        """
        RETURN: branch, the ALT branch whose FIRST set contains the lookahead.

        Reports and resyncs if no branch starts with the current token.
        """
        for branch in alt_element[1:]:
            if self.tok.kind in self.grammar._first_of(branch):
                return branch
        self._error("no alternative matches %s" % self.tok.kind.name)
        raise _ResyncError()

    def _starts(self, element):
        """RETURN: True, if the lookahead is in FIRST(element); else False."""
        return self.tok.kind in self.grammar._first_of(element)


# ---------------------------------------------------------------------------
# Public entry.
# ---------------------------------------------------------------------------
_COMPILED = None


def compiled_grammar():
    """RETURN: Grammar, the compiled+validated rule-file grammar (cached).

    Builds once on first use. Raises LL1ConflictError if the grammar block is
    not LL(1) -- surfaced eagerly so a grammar edit that breaks LL(1) fails loud.
    """
    global _COMPILED
    if _COMPILED is None:
        _COMPILED = Grammar(G.GRAMMAR, G.ACTIONS, start="<top-level>")
    return _COMPILED


def parse(source_text, oracle, reporter: DiagnosticReporter):
    """
    RETURN: RuleFile, the AST for 'source_text' via the table-driven engine.

    Same observable contract as parser.parse: diagnostics accumulate in
    'reporter'; the AST may be partial when errors were recovered.
    """
    return EngineParser(source_text, oracle, reporter, compiled_grammar()).parse()
