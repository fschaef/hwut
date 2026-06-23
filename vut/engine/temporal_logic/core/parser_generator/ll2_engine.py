"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

TABLE-DRIVEN PARSE ENGINE  --  LL(2) over the declarative grammar
______________________________________________________________________________
"""
from dataclasses import dataclass

from vut.engine.temporal_logic.lexer.lexer import Lexer
from vut.engine.temporal_logic.core.diagnostic import Diagnostic, Phase, DiagnosticReporter
from vut.engine.temporal_logic.core.parser_generator.ll2_grammar_spec import t_fr_span_open, t_fr_eof


# ---------------------------------------------------------------------------
# Compiled grammar is a tree of ll2_grammar_spec.SpecNode objects
# ---------------------------------------------------------------------------
import vut.engine.temporal_logic.core.parser_generator.ll2_grammar_spec as nodes
from vut.engine.temporal_logic.core.parser_generator.ll2_grammar_spec import (SpecNode, Terminal_Spec, Rule_Spec,
                              collect_alt_conflicts, ELEM, REDUCE, LOOP,
                              CST_REDUCE, ROLE_STAMP)
from dataclasses import replace as _dc_replace
from vut.engine.temporal_logic.core.parser_generator.cst_nodes import OR_Node, OPT_Node, SEQ_Node, PLUS_Node, STAR_Node, OpaqueTerminal

_CST_NODE_TYPES = (OR_Node, OPT_Node, SEQ_Node, PLUS_Node, STAR_Node)


def _is_cst_node(value):
    """RETURN: True, if 'value' is one of the four CST node types; False else.

    Used by the CST reduce to decide whether a rule's forwarded child can have a
    rule name stamped onto it (only the frozen CST nodes carry a 'name' field; a
    bare Token or OpaqueTerminal forwarded by a single-terminal rule does not).
    """
    return isinstance(value, _CST_NODE_TYPES)


class LL2ConflictError(Exception):
    """Raised by analysis when the grammar is not LL(2)."""
    def __init__(self, conflicts):
        super().__init__("%d LL(2) conflict(s)" % len(conflicts))
        self.conflicts = conflicts


class RoleUniquenessError(Exception):
    """Raised when one SEQ rule gives two positions the SAME advisory role (D-18).

    Role-keyed child access (node["key"]) selects the SINGLE position carrying a
    role, so two siblings sharing a role in one sequence make every keyed read
    of that role ambiguous. This is checked at compile time -- like the LL(2)
    conflict and the role-vocabulary check, all violations are collected and
    raised together -- so the ambiguity fails loud at load with the rule named,
    not as a ValueError deep in a factory at parse time. Inline sub-sequences
    are checked independently of their enclosing sequence: a role unique within
    each SEQ_Node is all role access needs.
    """
    def __init__(self, violations):
        super().__init__("%d role-uniqueness violation(s)" % len(violations))
        self.violations = violations


class RoleVocabularyError(Exception):
    """Raised when a role hint (D-10) violates the declared ROLES vocabulary.

    A grammar may supply a ROLES dict mapping each role-bearing pattern -- a
    terminal object, or a rule reference written '<name>' -- to the tuple of
    role strings it is ALLOWED to carry. Every advisory role hint in the grammar
    ('t_re_id("event")', '<name-dotted(event)>') is checked against it at compile
    time: an undeclared pattern or an unlisted role is a load error, so a typo
    ('evnet') fails loud here instead of misdirecting the semantic layer later.
    """
    def __init__(self, violations):
        super().__init__("%d role-vocabulary violation(s)" % len(violations))
        self.violations = violations


class Grammar:
    """The compiled grammar: a name->Rule_Spec map with FIRST_2 sets analysed."""
    def __init__(self, grammar_dict, actions=None, start=None,
                 cst=False, transformers=None, roles=None):
        """RETURN: None. Compiles 'grammar_dict' and analyses it for LL(2).

        Three reduction modes, by argument:
          - actions (the legacy ACTIONS dict): each rule's _build_* hand-builder
            runs at reduce; the pre-CST model, retained unchanged.
          - cst=True with no transformers: the engine builds the canonical CST
            (cst_nodes) and nothing else.
          - transformers (a PARTIAL dict, rule-name -> callable): implies CST
            mode; the engine builds the CST, then for each rule that HAS a
            transformer, calls it on that rule's finished CST node and forwards
            the result. A rule with no transformer entry passes its CST node
            through untouched. The dict is partial by design (D-5): there is no
            completeness check, so a forgotten transformer is a CST node reaching
            the consumer, not a load error.

        'transformers' and 'actions' are mutually exclusive -- a grammar either
        runs the legacy builders or the CST/overlay path, never both. Supplying
        transformers forces cst=True regardless of the flag.

        'roles' (optional) is the role vocabulary (D-10): a dict mapping each
        role-bearing pattern -- a terminal object, or a rule reference as the
        string '<name>' -- to the tuple of role strings it may carry. When
        given, every advisory role hint in the grammar is validated against it
        at compile time (RoleVocabularyError on an undeclared pattern or an
        unlisted role -- the typo guard). When None, role hints are not checked.
        """
        import vut.engine.temporal_logic.core.parser_generator.combinators as support
        if transformers is not None and actions is not None:
            raise ValueError("Grammar: 'actions' and 'transformers' are "
                             "mutually exclusive (legacy vs CST-overlay path)")
        # The engine owns flattening (D-21): a grammar value may be a SUBSPACE (a
        # TOP-keyed dict). flatten() lowers a possibly-nested grammar to the flat
        # QUALIFIED-named rule map plus each rule's body-resolution scope; a flat
        # grammar passes through unchanged (all rules at the root scope). The
        # engine compiles the flat map and resolves references scope-aware.
        from vut.engine.temporal_logic.core.parser_generator.subspace import flatten
        flat, scope_of = flatten(grammar_dict)
        self.flat         = flat
        self.scope_of     = scope_of
        self.cst          = cst or (transformers is not None)
        self.transformers = transformers if transformers is not None else {}
        self.roles        = roles
        _actions          = actions if actions is not None else {}
        if transformers is not None:
            stray = set(self.transformers) - set(flat)
            if stray:
                raise ValueError("Grammar: transformers name rules not in the "
                                 "grammar: %s" % ", ".join(sorted(stray)))
        self._sealed  = False     # FIRST_2 memo gate: off during the _analyse
                                  # fixpoint (sets still growing), on after.
        self.rules    = {name: Rule_Spec(name, _actions.get(name))
                         for name in flat}
        self.start    = start
        self._current_scope = ()
        for name, pattern in flat.items():
            self._current_scope = scope_of.get(name, ())
            self.rules[name].pattern = support.compile_element(pattern, self, nodes)
        self._current_scope = ()
        from vut.engine.temporal_logic.core.parser_generator.ll2_grammar_spec import T
        self.end_block = T.string(":end")   
        self._analyse()
        self._sealed = True       # FIRST_2 sets are now final -> memoise.
        self._validate_role_uniqueness()
        if roles is not None:
            self._validate_roles()

    def _validate_role_uniqueness(self):
        """RETURN: None. Raises RoleUniquenessError if a SEQ repeats a role (D-18).

        Walks every rule's compiled pattern; at each SEQ_Spec, collects the roles
        of its DIRECT branches (a Tagged_Spec branch carries '.role') and flags
        any role appearing more than once -- that role's keyed access would be
        ambiguous on the built SEQ_Node. Each violation names the rule (or
        '<inline>' for an anonymous sub-sequence) and the duplicated role; all
        are collected so one compile reports every clash. Inline sequences are
        scoped independently -- a role may recur ACROSS different sequences, just
        not WITHIN one.
        """
        from vut.engine.temporal_logic.core.parser_generator.ll2_grammar_spec import Tagged_Spec, SEQ_Spec
        violations = []
        seen = set()

        def role_of(branch):
            return branch.role if isinstance(branch, Tagged_Spec) else None

        def visit(node, rule_name):
            if id(node) in seen:
                return
            seen.add(id(node))
            if isinstance(node, SEQ_Spec):
                counts = {}
                for sub in node.branches:
                    r = role_of(sub)
                    if r is not None:
                        counts[r] = counts.get(r, 0) + 1
                for r, n in sorted(counts.items()):
                    if n > 1:
                        violations.append(
                            "rule %r: role %r on %d positions of one sequence"
                            % (rule_name, r, n))
            for c in node.children():
                visit(c, rule_name)

        for name, rule in self.rules.items():
            if rule.pattern is not None:
                visit(rule.pattern, name)
        if violations:
            raise RoleUniquenessError(sorted(set(violations)))

    def _validate_roles(self):
        """RETURN: None. Raises RoleVocabularyError if a role hint is undeclared.

        Walks every rule's compiled pattern, finds each advisory role hint
        (a Tagged_Spec, D-10), resolves the vocabulary KEY -- the wrapped
        terminal object, or '<rule-name>' for a wrapped rule reference -- and
        checks the carried role against self.roles[key]. An undeclared key or a
        role outside its declared tuple is a violation; all are collected and
        raised together so one compile reports every typo.
        """
        from vut.engine.temporal_logic.core.parser_generator.ll2_grammar_spec import (Tagged_Spec, Terminal_Spec, Rule_Spec,
                                        Operator_Spec, Branch_Spec)
        violations = []
        seen = set()

        def visit(node):
            if id(node) in seen:
                return
            seen.add(id(node))
            if isinstance(node, Tagged_Spec):
                body = node.body
                if isinstance(body, Terminal_Spec):
                    key, shown = body, body._name()
                elif isinstance(body, Rule_Spec):
                    key = "<%s>" % body.name
                    shown = key
                else:
                    key = shown = None
                allowed = self.roles.get(key) if key is not None else None
                if allowed is None:
                    violations.append(
                        "role %r on %s: no vocabulary declared in ROLES"
                        % (node.role, shown))
                elif node.role not in allowed:
                    violations.append(
                        "role %r on %s: not in declared vocabulary %s"
                        % (node.role, shown, tuple(allowed)))
            for c in node.children():
                visit(c)

        for rule in self.rules.values():
            visit(rule.pattern)
        if violations:
            raise RoleVocabularyError(sorted(set(violations)))

    def compile_leaf(self, element):
        from vut.engine.temporal_logic.core.parser_generator.ll2_grammar_spec import Terminal_Spec, Tagged_Spec, Ref, T
        from vut.engine.temporal_logic.core.parser_generator.subspace import resolve
        # Mutually-exclusive leaf kinds: a tagged terminal view, a bare terminal,
        # a Ref object, or a reference/keyword string. if/elif -- exactly one fires.
        if isinstance(element, Tagged_Spec):
            # A role-tagged terminal view ('t_re_id("event")', D-10). Its body is
            # an already-resolved terminal; the wrapper is transparent, returned
            # as-is so lexing/LL(2)/CST are unchanged and the role rides along.
            return element
        elif isinstance(element, Terminal_Spec):
            # A terminal is already its own interned grammar leaf (D-7): the
            # lexeme spec and the SpecNode are one object, shared across every
            # position naming it, 'silent' derived from shape. Return it as-is.
            if element.shape not in ("regex", "captured", "opaque", "string"):
                raise ValueError("terminal shape %r is not a grammar leaf"
                                 % (element.shape,))
            return element
        elif isinstance(element, Ref):
            target = resolve(element.name, self._current_scope, self.rules)
            if target is None:
                raise ValueError("undefined non-terminal %r (scope %s)"
                                 % (element.name, "/".join(self._current_scope) or "<root>"))
            return self.rules[target]
        elif isinstance(element, str):
            if len(element) > 2 and element[0] == "<" and element[-1] == ">":
                name = element[1:-1]
                role = None
                # '<name(role)>' carries an advisory role hint (D-10): split the
                # parenthesised role off the rule name. The role is recorded on a
                # transparent Tagged_Spec wrapping the referenced rule; it does
                # not alter the reference's identity, lexing, or LL(2). The name
                # may be path-qualified ('<algebr/shift>') or bare; resolve()
                # binds it scope-aware against the writing rule's subspace (D-21).
                if name.endswith(")") and "(" in name:
                    name, _, rest = name.partition("(")
                    role = rest[:-1]
                target = resolve(name, self._current_scope, self.rules)
                if target is None:
                    raise ValueError("undefined non-terminal %r (scope %s)"
                                     % (name, "/".join(self._current_scope) or "<root>"))
                rule = self.rules[target]
                return Tagged_Spec(rule, role) if role else rule
            return T.string(element)
        else:
            raise ValueError("grammar leaf is neither Terminal_Spec, Ref, nor "
                             "str: %r" % (element,))

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
    """A reduction frame: the surviving values of one operator, plus their roles.

    'values' holds one entry per surviving grammar position (silent terminals
    leave none); 'roles' is the SAME length, a parallel list of the advisory
    role string for each value or None. The two lists are kept in lockstep by
    'add()' -- every value enters with a role slot, defaulting None, so an
    untagged position reads role None and a '<type(key)>'-tagged one reads
    'key'. 'roles' is consumed only by SEQ_Spec.cst_reduce (role-keyed child
    access, D-18); other reduces ignore it.
    """
    __slots__ = ("values", "roles", "begin")

    def __init__(self, values=None, begin=0):
        self.values = [] if values is None else values
        self.roles  = [None] * len(self.values)
        self.begin  = begin

    def add(self, value, role=None):
        """RETURN: None. Appends 'value' with its 'role', keeping the lists equal."""
        self.values.append(value)
        self.roles.append(role)


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
        self.cst_mode = grammar.cst
        self.transformers = grammar.transformers
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
        start = self.grammar.rules[self.grammar.start]
        if self.cst_mode:
            # CST mode: no reach into the outer ast_nodes. The file is the
            # zero-or-more top-level items, collected into a STAR_Node named
            # "<file>". The outer layer transforms this into its Module if it
            # wants; core stays grammar-agnostic and AST-free.
            items = []
            while self.tok1.kind is not t_fr_eof:
                try:
                    item = self._match(start)
                    if item is not None:
                        items.append(item)
                except _ResyncError:
                    self._resync()
            from vut.engine.temporal_logic.core.parser_generator.cst_nodes import STAR_Node
            return STAR_Node(items=tuple(items), name="<file>")
        # SEAM: engine constructs parser.ast_nodes (Module/Luau). Neutrality
        # blocker for the standalone parser-generator. See DISCUSSIONS/seam-1.
        from vut.engine.temporal_logic.parser import ast_nodes as ast
        module_node = ast.ModuleRoot()
        while self.tok1.kind is not t_fr_eof:
            try:
                item = self._match(start)
                if item is not None:
                    module_node.items.append(item)
            except _ResyncError:
                self._resync()
        return module_node

    def _match(self, element):
        root = Frame(begin=self.tok1.begin)
        frames = [root]
        work = [(ELEM, element)]
        while work:
            tag, payload = work.pop()
            if tag == ELEM:
                payload.expand(self, frames, work)
            elif tag == REDUCE:
                self._reduce(payload, frames)
            elif tag == CST_REDUCE:
                self._cst_reduce(payload, frames)
            elif tag == ROLE_STAMP:
                # Post-body marker (D-18): the tagged element has just contributed
                # its single value to 'target_frame' at 'slot' (captured as the
                # value count at schedule time). Stamp the role onto that slot.
                # Scheduled by Tagged_Spec.expand AFTER the body, so the value is
                # present. Capturing the slot index (not 'roles[-1]' now) keeps
                # the stamp correct even if the body opened/closed nested frames
                # or a later sibling already appended. A tagged non-nullable leaf
                # always fills the slot; a no-fill (impossible here) is skipped.
                role, target_frame, slot = payload
                if slot < len(target_frame.roles):
                    target_frame.roles[slot] = role
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
        frames.append(Frame(begin=self.tok1.begin))

    def _reduce(self, nt, frames):
        frame = frames.pop()
        if self.cst_mode:
            # A named rule forwards its single child CST node, STAMPING the rule
            # name onto it (the child was built anonymous, name=None, by an inline
            # operator or a leaf). A rule that produced no surviving value
            # contributes nothing. The rule's pattern is a single operator, so
            # exactly one value survives in the common case; a bare-terminal rule
            # forwards its Token unnamed (a Token carries no 'name' to stamp).
            value = frame.values[0] if frame.values else None
            if value is not None and _is_cst_node(value):
                value = _dc_replace(value, name=nt.name)
            # Transformer overlay (D-5): if this rule HAS a transformer, hand it
            # the finished, name-stamped CST node and forward whatever it returns
            # (a typed AST node, or an adjusted CST node). Children are already
            # transformed -- they reduced first (bottom-up) -- so the transformer
            # sees finished child values, never raw sub-frames. A rule with no
            # entry forwards its CST node untouched. The dict is partial: a
            # missing entry is passthrough, never an error.
            if value is not None:
                fn = self.transformers.get(nt.name)
                if fn is not None:
                    value = fn(value)
            if value is not None:
                frames[-1].add(value)
            return
        if nt.action is None:
            value = frame.values[0] if frame.values else None
        else:
            value = nt.action(frame)
        if value is not None:
            frames[-1].add(value)

    def _cst_reduce(self, payload, frames):
        """RETURN: None. Pops an operator's sub-frame, builds its CST node, appends.

        'payload' is (operator_node, extra): the grammar operator that opened the
        frame and the per-operator extra (the branch index for OR, the present
        flag for OPT, None for SEQ/STAR/PLUS). The node's own cst_reduce builds
        the right CST node from the collected frame values; the result is
        appended to the parent frame.
        """
        node, extra = payload
        frame = frames.pop()
        value = node.cst_reduce(frame, extra)
        frames[-1].add(value)

    def consume_terminal(self, term):
        if self.tok1.kind is not term:
            self._error("expected %s, found %s"
                        % (term._name(), self.tok1.kind._name()))
            raise _ResyncError()
        tok = self._advance()
        return None if term.silent else tok

    def consume_span(self, span_node):
        """RETURN: OpaqueTerminal, the opaque span at the cursor (text, mode, begin).

        The grammar-agnostic counterpart of consuming a token: an opaque terminal
        position pulls a whole '{ ... }' span via the injected oracle and yields a
        neutral OpaqueTerminal. The engine does NOT build any language-specific AST
        node here (that was a layering leak); the rule's reduce action turns the
        OpaqueTerminal into whatever the language wants. 'mode' rides from the opaque
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
        mode = span_node.mode
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
        return OpaqueTerminal(text=block.text, mode=mode, begin=block.begin)

    def choose_alt(self, alt_node):
        """RETURN: SpecNode, the OR branch whose FIRST_2 set admits the lookahead.

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
