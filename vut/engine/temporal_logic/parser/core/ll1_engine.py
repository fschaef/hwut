"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

TABLE-DRIVEN PARSE ENGINE  --  LL(1) over the declarative grammar

Three stages turn the declarative GRAMMAR (grammar.py) into an AST:

    1. PREPROCESS  Resolve each grammar leaf to a node carrying its Terminal
                   identity: a bare-string keyword ('on:', '=>') routes through
                   T.string to its Terminal; a T.regex/T.captured terminal is
                   carried directly; a T.opaque terminal becomes a LuauNode under
                   its Role; an R reference becomes the NonTerminalNode bound to
                   its compiled pattern and reduce action.

    2. ANALYSE     Compute FIRST sets over the compiled grammar and VALIDATE
                   LL(1): every ALT branch must have a disjoint FIRST set,
                   and no optional/repetition may collide with what can follow.
                   Conflicts are reported, not hidden.

    3. PARSE       A stackless interpreter walks the compiled patterns on an
                   explicit work stack with one-token lookahead, choosing ALT
                   branches by FIRST set, and runs each rule's action to build
                   the AST node.

The engine is grammar-agnostic: it knows the combinators and the symbol kinds,
not the rule-file language. Swapping GRAMMAR/ACTIONS reuses it unchanged.
______________________________________________________________________________
"""
from dataclasses import dataclass

from .lexer       import Lexer
from .diagnostic  import Diagnostic, Phase, DiagnosticReporter
from ...luau.luau_fragment import Role
from .terminals   import t_fr_luau_open, t_fr_eof


# ---------------------------------------------------------------------------
# Compiled grammar is a tree of grammar_ast.Node objects (combinators AND
# leaves alike), so this engine never switches on an element kind -- it calls a
# node method. NonTerminalNode carries the per-rule pattern, action, and FIRST.
# ---------------------------------------------------------------------------
from . import grammar_ast as nodes
from .grammar_ast import (Node, TerminalNode, LuauNode, NonTerminalNode,
                           ELEM, REDUCE, LOOP)


class LL1ConflictError(Exception):
    """Raised by analysis when the grammar is not LL(1).

    Carries the list of human-readable conflict descriptions so the grammar
    author sees every conflict at once.
    """
    def __init__(self, conflicts):
        super().__init__("%d LL(1) conflict(s)" % len(conflicts))
        self.conflicts = conflicts


# ---------------------------------------------------------------------------
# A token's identity is the Terminal object the lexer attaches as Token.kind;
# the engine compares terminals by object identity, never by a name. The
# resync anchor ':end' is resolved once at Grammar build from the rule map.
# ---------------------------------------------------------------------------


class Grammar:
    """The compiled grammar: a name->NonTerminalNode map with FIRST sets analysed.

    Compiles GRAMMAR/ACTIONS into a uniform Node tree, computes FIRST sets, and
    validates LL(1) (raising LL1ConflictError on conflict). 'start' names the
    rule the engine begins each top-level item with. Acts as the 'ctx'/'grammar'
    the nodes are given: it exposes 'rules' (the name->NonTerminalNode map) and
    'compile_leaf' (leaf string -> leaf Node).
    """
    def __init__(self, grammar_dict, actions, start):
        """RETURN: None. Compiles, analyses, and validates the grammar."""
        from . import combinators as support
        self.rules    = {name: NonTerminalNode(name, actions.get(name))
                         for name in grammar_dict}
        self.start    = start
        for name, pattern in grammar_dict.items():
            self.rules[name].pattern = support.compile_element(pattern, self)
        from .terminals import T
        self.end_block = T.string(":end")   # resync anchor (already in the DB)
        self._analyse()

    # -- leaf resolution (called back by the authoring combinators) -----
    def compile_leaf(self, element):
        """
        RETURN: Node, the leaf Node for a grammar leaf.

        A grammar leaf is dispatched by type. A token's identity IS its Terminal
        object; the node carries that object directly, so no id table is
        consulted:

          - a Terminal object (terminals.py): a 'regex'/'captured' shape becomes
            a TerminalNode carrying that Terminal (captured is non-silent, kept
            for the builder; regex is non-silent, value-bearing); an 'opaque'
            shape becomes a LuauNode under the terminal's Role; a 'string' shape
            (an explicit T.string(...) keyword) becomes a silent TerminalNode --
            this is how a keyword that looks like '<...>' is written so it is not
            mistaken for a rule reference.
          - a bare string '<name>': a reference to the GRAMMAR rule 'name' (the
            interned NonTerminalNode). The angle brackets match the <name>
            spelling SYNTAX_DOC uses for nonterminals.
          - any other bare string: sugar for a silent string keyword, routed
            through T.string, which mints (or reuses) the Terminal.
          - an R reference (a Ref): the interned NonTerminalNode. Retained for
            compatibility; the GRAMMAR now writes references as '<name>'.
        """
        from .terminals import Terminal, Ref, T
        if isinstance(element, Terminal):
            if element.shape in ("regex", "captured"):
                return TerminalNode(element, silent=False)
            if element.shape == "opaque":
                return LuauNode(element.role)
            if element.shape == "string":
                return TerminalNode(element, silent=True)
            raise ValueError("terminal shape %r is not a grammar leaf"
                             % (element.shape,))
        if isinstance(element, Ref):
            if element.name not in self.rules:
                raise ValueError("undefined non-terminal %r" % (element.name,))
            return self.rules[element.name]
        if isinstance(element, str):
            if len(element) > 2 and element[0] == "<" and element[-1] == ">":
                name = element[1:-1]
                if name not in self.rules:
                    raise ValueError("undefined non-terminal %r" % (name,))
                return self.rules[name]
            return TerminalNode(T.string(element), silent=True)
        raise ValueError("grammar leaf is neither Terminal, Ref, nor str: %r"
                         % (element,))

    # -- analysis: FIRST sets + LL(1) validation ------------------------
    def _analyse(self):
        """RETURN: None. Computes FIRST sets to a fixpoint, then validates LL(1)."""
        changed = True
        while changed:
            changed = False
            for nt in self.rules.values():
                before = len(nt.first)
                nt.first |= nt.pattern.first_set(self)
                if len(nt.first) != before:
                    changed = True
        conflicts = []
        for nt in self.rules.values():
            nt.pattern.check_alts(nt.name, conflicts, self)
        if conflicts:
            raise LL1ConflictError(conflicts)


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
            if self.tok.kind is t_fr_eof:
                return
            if self.tok.kind is self.grammar.end_block:
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
        from .. import ast_nodes as ast
        rule_file = ast.RuleFile()
        start = self.grammar.rules[self.grammar.start]
        while self.tok.kind is not t_fr_eof:
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
    #   frames -- one Frame per NonTerminalNode currently being assembled; child
    #             values append to frames[-1]; a REDUCE pops it, runs the
    #             rule's action, and appends the result to the new top frame.
    #
    # Work instructions (tuples, tagged by [0], tags from grammar_ast):
    #   (ELEM,  node)  -- expand 'node' (node.expand decides what to push/consume)
    #   (REDUCE, nt)   -- finish NonTerminalNode 'nt': pop its frame, act, append
    #   (LOOP,  body)  -- a PLUS/STAR iteration point
    #
    # Each node's 'expand' performs its own step: a SeqNode pushes its parts in
    # reverse, an AltNode chooses a branch by lookahead, OptNode pushes its body
    # iff the lookahead starts it, Plus/Star push a LOOP marker. The engine just
    # dispatches; it never inspects a node's kind.

    def _match(self, element):
        """
        RETURN: value, the result of matching 'element' against the stream.

        Drives 'element' to completion on an explicit work stack and returns the
        value it produced (a rule's action result, a token, a Luau node, or None
        for silent/empty). Mismatches raise _ResyncError, which abandons the
        whole walk for the caller (parse) to recover.

        Uses a sentinel root frame to collect the single top-level value so the
        same value-append discipline applies uniformly at every level.
        """
        root = Frame(values=[], begin=self.tok.begin)
        frames = [root]
        work = [(ELEM, element)]
        while work:
            tag, payload = work.pop()
            if tag == ELEM:
                payload.expand(self, frames, work)
            elif tag == REDUCE:
                self._reduce(payload, frames)
            else:  # LOOP
                if self.starts(payload):
                    work.append((LOOP, payload))
                    work.append((ELEM, payload))
        return root.values[0] if root.values else None

    # -- helpers the nodes call back into (the node<->engine interface) --
    def open_frame(self, frames):
        """RETURN: None. Pushes a fresh Frame for a NonTerminalNode being entered."""
        frames.append(Frame(values=[], begin=self.tok.begin))

    def _reduce(self, nt, frames):
        """RETURN: None. Pops nt's frame, runs its action, appends to parent."""
        frame = frames.pop()
        if nt.action is None:
            value = frame.values[0] if frame.values else None
        else:
            value = nt.action(frame)
        if value is not None:
            frames[-1].values.append(value)

    def consume_terminal(self, term):
        """RETURN: Token or None. Consumes the expected token; None if silent.

        Raises _ResyncError on a mismatch (after reporting it).
        """
        if self.tok.kind is not term.token_id:
            self._error("expected %s, found %s"
                        % (term.token_id._name(), self.tok.kind._name()))
            raise _ResyncError()
        tok = self._advance()
        return None if term.silent else tok

    def consume_luau(self, luau_node):
        """RETURN: Luau, the span read under the node's role; resyncs on failure."""
        from .. import ast_nodes as ast
        if self.tok.kind is not t_fr_luau_open:
            self._error("expected '{' Luau block, found %s" % self.tok.kind._name())
            raise _ResyncError()
        open_tok = self._advance()
        block = self.lexer.read_luau_block(open_tok, luau_node.role)
        if block is None:
            self._error("Luau oracle failed", fatal=True)
            raise _ResyncError()
        self.tok = self.lexer.next()
        return ast.Luau(text=block.text, role=luau_node.role, begin=block.begin)

    def choose_alt(self, alt_node):
        """
        RETURN: Node, the AltNode branch whose FIRST set contains the lookahead.

        Reports and resyncs if no branch starts with the current token.
        """
        for branch in alt_node.branches:
            if self.tok.kind in branch.first_set(self.grammar):
                return branch
        self._error("no alternative matches %s" % self.tok.kind._name())
        raise _ResyncError()

    def starts(self, element):
        """RETURN: True, if the lookahead is in FIRST(element); else False."""
        return self.tok.kind in element.first_set(self.grammar)
