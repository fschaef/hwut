"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

GRAMMAR NODES  --  the compiled grammar as a uniform polymorphic tree.

Compiling a rule turns its authored structure (see grammar.py / combinators.py)
into a tree of Node objects. EVERY element is a Node -- combinators (SeqNode,
AltNode, OptNode, PlusNode, StarNode) AND leaves (TerminalNode, LuauNode,
NonTerminalNode) alike -- so the engine never switches on a kind: it calls a
method and the node does the right thing.

Each Node implements the operations the parser-preparation and the parse itself
need:

    first_set(grammar) -> set[Terminal]   terminals that can begin this node
    nullable(grammar)  -> bool             can this node match no tokens
    check_alts(rule_name, conflicts, grammar)
                                           collect LL(1) conflicts beneath it
    expand(parser, frames, work)           one step of the iterative parse:
                                           push work / consume input / append a
                                           value to the current frame

'grammar' is passed in (a duck-typed object exposing the name->NonTerminalNode
map as '.rules'); nodes hold no engine state, so this module depends only on the
token-id enum and the Luau Role -- never on the engine.

The parse is driven by an explicit work stack (parser_engine._match), not by
recursion, so 'expand' pushes follow-up work rather than calling itself. The
work-instruction tags ELEM / REDUCE / LOOP are defined here and shared with the
engine.
______________________________________________________________________________
"""
from .terminals import t_fr_luau_open


# Work-instruction tags for the parser's explicit stack (see parser_engine).
#   (ELEM,  node)            expand 'node'
#   (REDUCE, nt)             finish NonTerminalNode 'nt': pop frame, act, append
#   (LOOP,  body)            a PLUS/STAR iteration point
ELEM   = 0
REDUCE = 1
LOOP   = 2


class Node:
    """Abstract base for every compiled grammar element.

    Subclasses are the combinators (SeqNode/AltNode/OptNode/PlusNode/StarNode)
    and the leaves (TerminalNode/LuauNode/NonTerminalNode). The four methods
    below are the whole interface the engine uses; no engine code inspects a
    node's concrete type.
    """
    __slots__ = ()

    def first_set(self, grammar):
        """RETURN: set[Terminal], the terminals that can begin this node."""
        raise NotImplementedError

    def nullable(self, grammar):
        """RETURN: True, if this node can match the empty token sequence; else
                False.
        """
        raise NotImplementedError

    def check_alts(self, rule_name, conflicts, grammar):
        """RETURN: None. Appends a description for each LL(1) conflict beneath
                this node (an ALT whose branches share a FIRST token).
        """
        raise NotImplementedError

    def expand(self, parser, frames, work):
        """RETURN: None. Performs one parse step for this node against the
                parser's token stream, mutating 'frames' and 'work' in place.

        A leaf consumes input and may append a value to frames[-1]; a combinator
        pushes follow-up (ELEM/REDUCE/LOOP) work. Raises _ResyncError (from the
        engine) on a token mismatch.
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Leaves.
# ---------------------------------------------------------------------------
class TerminalNode(Node):
    """A resolved terminal: the token id to match and whether it bears a value.

    'silent' True means the matched token is punctuation, dropped from a frame's
    values (keywords, symbols). False means it contributes its Token (ID, NUMBER,
    STRING, and the captured keywords).
    """
    __slots__ = ("token_id", "silent")

    def __init__(self, token_id, silent):
        self.token_id = token_id
        self.silent   = silent

    def __repr__(self):
        return "T(%s%s)" % (self.token_id._name(), "" if self.silent else "*")

    def first_set(self, grammar):
        return {self.token_id}

    def nullable(self, grammar):
        return False

    def check_alts(self, rule_name, conflicts, grammar):
        return

    def expand(self, parser, frames, work):
        value = parser.consume_terminal(self)
        if value is not None:
            frames[-1].values.append(value)


class LuauNode(Node):
    """A resolved Luau span: the Role under which the parser drives the oracle."""
    __slots__ = ("role",)

    def __init__(self, role):
        self.role = role

    def __repr__(self):
        return "Luau(%s)" % self.role.name

    def first_set(self, grammar):
        return {t_fr_luau_open}

    def nullable(self, grammar):
        return False

    def check_alts(self, rule_name, conflicts, grammar):
        return

    def expand(self, parser, frames, work):
        frames[-1].values.append(parser.consume_luau(self))


class NonTerminalNode(Node):
    """A resolved rule reference: its name, compiled pattern, action, FIRST set.

    'action' is None for a pass-through rule (forwards its single value).
    'pattern' (the compiled body Node) and 'first' (the FIRST set) are filled by
    the engine during compile/analysis. A reference and its definition are the
    SAME object -- the engine interns one NonTerminalNode per rule name -- so a
    reference sees the definition's pattern and FIRST automatically.
    """
    __slots__ = ("name", "action", "pattern", "first")

    def __init__(self, name, action):
        self.name    = name
        self.action  = action
        self.pattern = None        # set during compile
        self.first   = set()       # filled during analysis

    def __repr__(self):
        return "NT(%s)" % self.name

    def first_set(self, grammar):
        return set(self.first)

    def nullable(self, grammar):
        # The rule-file grammar has no nullable non-terminals; treat as False
        # (kept exact for this grammar, as the previous engine did).
        return False

    def check_alts(self, rule_name, conflicts, grammar):
        # A reference does not re-descend into the referenced rule; each rule's
        # own pattern is checked once when the engine iterates the rule set.
        return

    def expand(self, parser, frames, work):
        # Open a fresh frame, schedule the reduce, then expand the pattern
        # (pushed last so it runs first).
        parser.open_frame(frames)
        work.append((REDUCE, self))
        work.append((ELEM, self.pattern))


# ---------------------------------------------------------------------------
# Combinators.
# ---------------------------------------------------------------------------
class SeqNode(Node):
    """A sequence: match each child in order."""
    __slots__ = ("parts",)

    def __init__(self, parts):
        self.parts = tuple(parts)

    def __repr__(self):
        return "Seq(%s)" % ", ".join(map(repr, self.parts))

    def first_set(self, grammar):
        result = set()
        for sub in self.parts:
            result |= sub.first_set(grammar)
            if not sub.nullable(grammar):
                break
        return result

    def nullable(self, grammar):
        return all(sub.nullable(grammar) for sub in self.parts)

    def check_alts(self, rule_name, conflicts, grammar):
        for sub in self.parts:
            sub.check_alts(rule_name, conflicts, grammar)

    def expand(self, parser, frames, work):
        for sub in reversed(self.parts):
            work.append((ELEM, sub))


class AltNode(Node):
    """An alternation: match exactly one branch, chosen by one-token lookahead."""
    __slots__ = ("branches",)

    def __init__(self, branches):
        self.branches = tuple(branches)

    def __repr__(self):
        return "Alt(%s)" % " | ".join(map(repr, self.branches))

    def first_set(self, grammar):
        result = set()
        for sub in self.branches:
            result |= sub.first_set(grammar)
        return result

    def nullable(self, grammar):
        return any(sub.nullable(grammar) for sub in self.branches)

    def check_alts(self, rule_name, conflicts, grammar):
        seen = {}
        for branch in self.branches:
            for tid in branch.first_set(grammar):
                if tid in seen:
                    conflicts.append(
                        "rule %s: token %s starts two ALT branches"
                        % (rule_name, tid._name()))
                else:
                    seen[tid] = branch
        for branch in self.branches:
            branch.check_alts(rule_name, conflicts, grammar)

    def expand(self, parser, frames, work):
        work.append((ELEM, parser.choose_alt(self)))


class OptNode(Node):
    """An option: match the body zero or one time."""
    __slots__ = ("body",)

    def __init__(self, body):
        self.body = body

    def __repr__(self):
        return "Opt(%r)" % (self.body,)

    def first_set(self, grammar):
        return self.body.first_set(grammar)

    def nullable(self, grammar):
        return True

    def check_alts(self, rule_name, conflicts, grammar):
        self.body.check_alts(rule_name, conflicts, grammar)

    def expand(self, parser, frames, work):
        if parser.starts(self.body):
            work.append((ELEM, self.body))


class PlusNode(Node):
    """A repetition: match the body one or more times."""
    __slots__ = ("body",)

    def __init__(self, body):
        self.body = body

    def __repr__(self):
        return "Plus(%r)" % (self.body,)

    def first_set(self, grammar):
        return self.body.first_set(grammar)

    def nullable(self, grammar):
        return False

    def check_alts(self, rule_name, conflicts, grammar):
        self.body.check_alts(rule_name, conflicts, grammar)

    def expand(self, parser, frames, work):
        # One mandatory body, then a loop for the rest.
        work.append((LOOP, self.body))
        work.append((ELEM, self.body))


class StarNode(Node):
    """A repetition: match the body zero or more times."""
    __slots__ = ("body",)

    def __init__(self, body):
        self.body = body

    def __repr__(self):
        return "Star(%r)" % (self.body,)

    def first_set(self, grammar):
        return self.body.first_set(grammar)

    def nullable(self, grammar):
        return True

    def check_alts(self, rule_name, conflicts, grammar):
        self.body.check_alts(rule_name, conflicts, grammar)

    def expand(self, parser, frames, work):
        work.append((LOOP, self.body))
