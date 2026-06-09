"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

TABLE-DRIVEN PARSE ENGINE  --  LL(2) over the declarative grammar
______________________________________________________________________________
"""
from dataclasses import dataclass

from .lexer       import Lexer
from .diagnostic  import Diagnostic, Phase, DiagnosticReporter
from .span_oracle import SpanResult
from .terminals   import t_fr_span_open, t_fr_eof


# ---------------------------------------------------------------------------
# Compiled grammar is a tree of ll2_grammar_ast.Node objects
# ---------------------------------------------------------------------------
from . import ll2_grammar_ast as nodes
from .ll2_grammar_ast import (Node, TerminalNode, PassThroughNode,
                              collect_alt_conflicts, ELEM, REDUCE, LOOP)


class LL2ConflictError(Exception):
    """Raised by analysis when the grammar is not LL(2)."""
    def __init__(self, conflicts):
        super().__init__("%d LL(2) conflict(s)" % len(conflicts))
        self.conflicts = conflicts


class Grammar:
    """The compiled grammar: a name->PassThroughNode map with FIRST_2 sets analysed."""
    def __init__(self, grammar_dict, actions, start):
        from . import combinators as support
        self.rules    = {name: PassThroughNode(name, actions.get(name))
                         for name in grammar_dict}
        self.start    = start
        for name, pattern in grammar_dict.items():
            self.rules[name].pattern = support.compile_element(pattern, self, nodes)
        from .terminals import T
        self.end_block = T.string(":end")   
        self._analyse()

    def compile_leaf(self, element):
        from .terminals import Terminal, Ref, T
        if isinstance(element, Terminal):
            match element.shape:
                case "regex" | "captured" | "opaque":
                    return TerminalNode(element, silent=False)
                case "string":
                    return TerminalNode(element, silent=True)
                case _:
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

    def _analyse(self):
        """Computes FIRST_2 sets to a fixpoint, then validates LL(2)."""
        changed = True
        while changed:
            changed = False
            for nt in self.rules.values():
                before = len(nt.first)
                nt.first |= nt.pattern.first2_set(self)
                if len(nt.first) != before:
                    changed = True
        conflicts = []
        for nt in self.rules.values():
            conflicts.extend(collect_alt_conflicts(nt.pattern, nt.name, self))
        if conflicts:
            raise LL2ConflictError(conflicts)


@dataclass
class Frame:
    values: list
    begin:  int


class _ResyncError(Exception):
    pass


class EngineParser:
    """Parses a rule file by interpreting a compiled Grammar with LL(2) lookahead."""
    _TOP_LEVEL = None       

    def __init__(self, source_text, oracle, reporter, grammar, lexer=None):
        """RETURN: None. Builds the parser and PRIMES the 2-token window.

        'lexer' may be supplied to drive a prebuilt token stream (a test
        ListLexer) instead of lexing 'source_text'; when given, 'source_text' and
        'oracle' are ignored. Whichever lexer is used, tok1/tok2 are primed here
        and NOWHERE ELSE -- a caller must not construct via __new__ and prime by
        hand, or the two-token window can be left half-initialised (the bug that
        a single-token 'self.tok' priming reintroduced).
        """
        self.reporter = reporter
        self.grammar  = grammar
        self.lexer    = lexer if lexer is not None else Lexer(source_text, oracle, reporter)
        # Prime the 2-token lookahead window
        self.tok1     = self.lexer.next()
        self.tok2     = self.lexer.next()
        # Monotonic count of tokens consumed out of the window. Used as a
        # lexer-agnostic progress measure for the loop guard: token byte-offsets
        # are unreliable (synthetic test streams set every begin to 0), so the
        # guard counts CONSUMED tokens rather than reading tok.begin.
        self._consumed = 0
        self._top_first = self.grammar.rules[self.grammar.start].first

    def _advance(self):
        """Advances the sliding window: tok1 gets tok2, tok2 fetches next."""
        cur = self.tok1
        self.tok1 = self.tok2
        self.tok2 = self.lexer.next()
        self._consumed += 1
        return cur

    def _error(self, message, fatal=False):
        self.reporter.report(Diagnostic(
            phase=Phase.PARSER, message=message,
            source_offset=self.tok1.begin, fatal=fatal))

    def _resync(self):
        """Skips tokens until a top-level anchor, ALWAYS consuming at least one.

        Called after a _match raised _ResyncError. The first token is the one the
        failed match choked on, so it is skipped UNCONDITIONALLY before scanning:
        a top-level anchor token (e.g. an identifier, which can start a forward-
        decl) may be exactly the token that just failed in context, and stopping
        on it without advancing would re-attempt the same failing parse at the
        same position forever. After the mandatory skip, advance to the next
        anchor (or the end-of-block, which is consumed, or EOF).
        """
        anchors = {tup[0] for tup in self._top_first if tup}
        if self.tok1.kind is t_fr_eof:
            return
        # Mandatory progress: drop the token the failed match stopped on.
        if self.tok1.kind is self.grammar.end_block:
            self._advance()
            return
        self._advance()
        while True:
            if self.tok1.kind is t_fr_eof:
                return
            if self.tok1.kind is self.grammar.end_block:
                self._advance()
                return
            if self.tok1.kind in anchors:
                return
            self._advance()

    def parse(self):
        from .. import ast_nodes as ast
        rule_file = ast.RuleFile()
        start = self.grammar.rules[self.grammar.start]
        while self.tok1.kind is not t_fr_eof:
            try:
                item = self._match(start)
                if item is not None:
                    rule_file.items.append(item)
            except _ResyncError:
                self._resync()
        return rule_file

    def _match(self, element):
        root = Frame(values=[], begin=self.tok1.begin)
        frames = [root]
        work = [(ELEM, element)]
        while work:
            tag, payload = work.pop()
            if tag == ELEM:
                payload.expand(self, frames, work)
            elif tag == REDUCE:
                self._reduce(payload, frames)
            else:  # LOOP
                # 'payload' is (body, last_consumed): the loop body and the value
                # of self._consumed at which the PREVIOUS iteration began. A
                # repetition may re-enter only if the window can start the body
                # AND at least one token has been consumed since that iteration.
                # The progress guard stops an infinite loop when starts() is
                # optimistic (e.g. a length-1 FIRST_2 entry matches the lookahead)
                # but the body then fails to consume anything: without it the same
                # non-advancing iteration is retried forever. _consumed is used
                # rather than tok.begin because synthetic token streams (test
                # fixtures) set every begin to 0, so byte offset is no progress
                # measure; _consumed counts tokens that have left the window.
                body, last_consumed = payload
                if self._consumed != last_consumed and self.starts(body):
                    work.append((LOOP, (body, self._consumed)))
                    work.append((ELEM, body))
        return root.values[0] if root.values else None

    def open_frame(self, frames):
        frames.append(Frame(values=[], begin=self.tok1.begin))

    def _reduce(self, nt, frames):
        frame = frames.pop()
        if nt.action is None:
            value = frame.values[0] if frame.values else None
        else:
            value = nt.action(frame)
        if value is not None:
            frames[-1].values.append(value)

    def consume_terminal(self, term):
        if self.tok1.kind is not term.token_id:
            self._error("expected %s, found %s"
                        % (term.token_id._name(), self.tok1.kind._name()))
            raise _ResyncError()
        tok = self._advance()
        return None if term.silent else tok

    def consume_span(self, span_node):
        """RETURN: SpanResult, the opaque span at the cursor (text, mode, begin).

        The grammar-agnostic counterpart of consuming a token: an opaque terminal
        position pulls a whole '{ ... }' span via the injected oracle and yields a
        neutral SpanResult. The engine does NOT build any language-specific AST
        node here (that was a layering leak); the rule's reduce action turns the
        SpanResult into whatever the language wants. 'mode' rides from the opaque
        terminal to the oracle unread.

        CRUCIAL ordering: tok1 is the SPAN_OPEN, but the 2-token window has ALREADY
        lexed tok2 from just inside the block (the first control-plane token after
        '{'). We must NOT advance the window here -- advancing would call
        lexer.next() to refill tok2 and lex deeper into the block interior as
        control-plane, hitting a stray operator as a MISMATCH before the oracle
        ever sees the span. Instead, rewind the lexer to the open delimiter, let
        the oracle skip the whole block (which repositions the cursor past the
        close), then re-prime the window from after the block.
        """
        mode = span_node.token_id.mode
        if self.tok1.kind is not t_fr_span_open:
            self._error("expected '{' opaque span, found %s"
                        % self.tok1.kind._name())
            raise _ResyncError()
        open_tok = self.tok1
        # Rewind: discard the lookahead lexed from inside the block, and put the
        # lexer cursor back at the open delimiter so read_span measures the span
        # from '{' and leaves the cursor just past the matching '}'.
        self.lexer.cursor = open_tok.begin
        block = self.lexer.read_span(open_tok, mode)
        if block is None:
            self._error("span oracle failed", fatal=True)
            raise _ResyncError()
        # Re-prime the 2-token lookahead window behind the skipped block.
        self.tok1 = self.lexer.next()
        self.tok2 = self.lexer.next()
        self._consumed += 1
        return SpanResult(text=block.text, mode=mode, begin=block.begin)

    def choose_alt(self, alt_node):
        """RETURN: Node, the ALT branch whose FIRST_2 set admits the lookahead.

        Raises _ResyncError when no branch matches. Selection is TWO-PASS, and
        the order matters: a full 2-token pair match is strictly preferred over a
        length-1 (single-token) match.

        A length-1 entry '(t,)' in a branch's FIRST_2 means "this branch can
        begin with t and then end" -- it must NOT pre-empt a sibling branch that
        consumes 't' followed by a specific second token. The canonical case is
        <arg>: the positional branch's FIRST_2 holds '(id,)' (a bare-identifier
        rvalue) and the named branch's holds '(id, =)'. On lookahead '(id, =)'
        the full-pair pass picks NAMED; on '(id, <anything-else>)' no full pair
        matches, so the length-1 pass picks POSITIONAL. A single greedy 'pair OR
        truncation' test would let positional win on '(id, =)' (its '(id,)'
        matches by truncation) and mis-parse every named argument.
        """
        lookahead_2  = (self.tok1.kind, self.tok2.kind)
        single       = (self.tok1.kind,)

        # Pass 1: a branch that consumes BOTH lookahead tokens wins outright.
        for branch in alt_node.branches:
            if lookahead_2 in branch.first2_set(self.grammar):
                return branch
        # Pass 2: no two-token match -- a branch beginning with this one token
        # (then ending, or followed by anything) may take it.
        for branch in alt_node.branches:
            if single in branch.first2_set(self.grammar):
                return branch

        self._error("no alternative matches 2-token lookahead (%s, %s)"
                    % (self.tok1.kind._name(), self.tok2.kind._name()))
        raise _ResyncError()

    def starts(self, element):
        """RETURN: True, if the 2-token window can begin 'element'; False else.

        Matches a full pair first, then a length-1 entry (the element derives a
        single token, or what follows it is nullable). Same precedence rationale
        as choose_alt, though for an OPT/STAR body the test is only presence, not
        branch selection.
        """
        elem_set    = element.first2_set(self.grammar)
        lookahead_2 = (self.tok1.kind, self.tok2.kind)
        return lookahead_2 in elem_set or (self.tok1.kind,) in elem_set

