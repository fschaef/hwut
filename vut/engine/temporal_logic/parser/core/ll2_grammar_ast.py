"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

GRAMMAR NODES  --  the compiled grammar as a uniform polymorphic tree.
______________________________________________________________________________
"""
from .terminals import t_fr_span_open, t_fr_eof

ELEM   = 0
REDUCE = 1
LOOP   = 2


def merge_first2(set_a, set_b):
    """Cross-multiplies two sets of lookahead tuples, capping length at 2.
    
    Handles partial token-sequence padding where short path sequences 
    intersect with follow-up structures.
    """
    result = set()
    for tail_a in set_a:
        if len(tail_a) == 2:
            result.add(tail_a)
        elif len(tail_a) == 1:
            for tail_b in set_b:
                if len(tail_b) >= 1:
                    result.add((tail_a[0], tail_b[0]))
                else:
                    result.add(tail_a)
        else: # Empty tuple placeholder (nullable)
            for tail_b in set_b:
                result.add(tail_b)
    return result


class Node:
    __slots__ = ()

    def first2_set(self, grammar):
        """RETURN: set[tuple], the 2-token lookahead sequences beginning this node."""
        raise NotImplementedError

    def nullable(self, grammar):
        raise NotImplementedError

    def children(self):
        return ()

    def expand(self, parser, frames, work):
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Leaves.
# ---------------------------------------------------------------------------
class TerminalNode(Node):
    __slots__ = ("token_id", "silent")

    def __init__(self, token_id, silent):
        self.token_id = token_id
        self.silent   = silent

    @property
    def is_opaque(self):
        return self.token_id.shape == "opaque"

    def __repr__(self):
        if self.is_opaque:
            return "T(span:%s)" % self.token_id.mode.qualified_name()
        return "T(%s%s)" % (self.token_id._name(), "" if self.silent else "*")

    def first2_set(self, grammar):
        """Terminals provide a length-1 tuple layout contextually padded later."""
        if self.is_opaque:
            return {(t_fr_span_open,)}
        return {(self.token_id,)}

    def nullable(self, grammar):
        return False

    def expand(self, parser, frames, work):
        if self.is_opaque:
            frames[-1].values.append(parser.consume_span(self))
        else:
            value = parser.consume_terminal(self)
            if value is not None:
                frames[-1].values.append(value)


class PassThroughNode(Node):
    __slots__ = ("name", "action", "pattern", "first")

    def __init__(self, name, action):
        self.name    = name
        self.action  = action
        self.pattern = None        
        self.first   = set()       # Now holds tuples of lengths 1 and 2

    def __repr__(self):
        return "PT(%s)" % self.name

    def first2_set(self, grammar):
        return set(self.first)

    def nullable(self, grammar):
        return False

    def expand(self, parser, frames, work):
        parser.open_frame(frames)
        work.append((REDUCE, self))
        work.append((ELEM, self.pattern))


# ---------------------------------------------------------------------------
# Combinators: BranchNode and OperatorNode
# ---------------------------------------------------------------------------
class BranchNode(Node):
    __slots__ = ("branches",)

    def __init__(self, branches):
        self.branches = tuple(branches)

    def children(self):
        return self.branches


class SequenceNode(BranchNode):
    __slots__ = ()

    def __repr__(self):
        return "Seq(%s)" % ", ".join(map(repr, self.branches))

    def first2_set(self, grammar):
        if not self.branches:
            return {()}
        acc = self.branches[0].first2_set(grammar)
        for sub in self.branches[1:]:
            acc = merge_first2(acc, sub.first2_set(grammar))
        return acc

    def nullable(self, grammar):
        return all(sub.nullable(grammar) for sub in self.branches)

    def expand(self, parser, frames, work):
        for sub in reversed(self.branches):
            work.append((ELEM, sub))


class AlternativeNode(BranchNode):
    __slots__ = ()

    def __repr__(self):
        return "Alt(%s)" % " | ".join(map(repr, self.branches))

    def first2_set(self, grammar):
        result = set()
        for sub in self.branches:
            result |= sub.first2_set(grammar)
        return result

    def nullable(self, grammar):
        return any(sub.nullable(grammar) for sub in self.branches)

    def expand(self, parser, frames, work):
        work.append((ELEM, parser.choose_alt(self)))


class OperatorNode(Node):
    __slots__ = ("body",)

    def __init__(self, body):
        self.body = body

    def children(self):
        return (self.body,)

    def first2_set(self, grammar):
        return self.body.first2_set(grammar)


class OptionalNode(OperatorNode):
    __slots__ = ()

    def __repr__(self):
        return "Opt(%r)" % (self.body,)

    def first2_set(self, grammar):
        # Includes empty baseline marker to flag structural path choice
        return self.body.first2_set(grammar) | {()}

    def nullable(self, grammar):
        return True

    def expand(self, parser, frames, work):
        if parser.starts(self.body):
            work.append((ELEM, self.body))


class StarNode(OperatorNode):
    __slots__ = ()

    def __repr__(self):
        return "Star(%r)" % (self.body,)

    def first2_set(self, grammar):
        return self.body.first2_set(grammar) | {()}

    def nullable(self, grammar):
        return True

    def expand(self, parser, frames, work):
        work.append((LOOP, (self.body, -1)))


class PlusNode(OperatorNode):
    __slots__ = ()

    def __repr__(self):
        return "Plus(%r)" % (self.body,)

    def nullable(self, grammar):
        return False

    def expand(self, parser, frames, work):
        work.append((LOOP, (self.body, -1)))
        work.append((ELEM, self.body))


# ---------------------------------------------------------------------------
# LL(2) conflict detection -- external worklist walk
# ---------------------------------------------------------------------------
def _first2_sets_iterative(pattern, grammar):
    """Computes FIRST_2 sets iteratively without recursion to preserve C stack layers."""
    order = []
    work  = [pattern]
    while work:
        node = work.pop()
        order.append(node)
        if not isinstance(node, PassThroughNode):
            work.extend(node.children())

    first2 = {}
    null   = {}
    for node in reversed(order):
        if isinstance(node, TerminalNode):
            first2[node] = node.first2_set(grammar)
            null[node]  = False
        elif isinstance(node, PassThroughNode):
            first2[node] = set(node.first)        
            null[node]  = node.nullable(grammar)
        elif isinstance(node, SequenceNode):
            if not node.branches:
                first2[node] = {()}
            else:
                acc = first2[node.branches[0]]
                for sub in node.branches[1:]:
                    acc = merge_first2(acc, first2[sub])
                first2[node] = acc
            null[node]  = all(null[s] for s in node.branches)
        elif isinstance(node, AlternativeNode):
            first2[node] = set().union(*(first2[s] for s in node.branches)) \
                           if node.branches else set()
            null[node]  = any(null[s] for s in node.branches)
        else:  # OperatorNode
            first2[node] = set(first2[node.body])
            if isinstance(node, (OptionalNode, StarNode)):
                first2[node].add(())
            null[node]  = isinstance(node, (OptionalNode, StarNode))
    return first2


def collect_alt_conflicts(pattern, rule_name, grammar):
    """Detects distinct alternative paths that overlap on identical 2-token sequences."""
    first2 = _first2_sets_iterative(pattern, grammar)
    conflicts = []
    work = [pattern]
    while work:
        node = work.pop()
        if isinstance(node, AlternativeNode):
            seen = {}
            for branch in node.branches:
                for lookahead_tuple in first2[branch]:
                    if not lookahead_tuple:
                        continue
                    
                    # Pad out single dangling terminals to complete pair profiles
                    normalized = (lookahead_tuple[0], t_fr_eof) if len(lookahead_tuple) == 1 else lookahead_tuple
                    
                    if normalized in seen:
                        conflicts.append(
                            "rule %s: 2-token lookahead (%s, %s) starts two ALT branches"
                            % (rule_name, normalized[0]._name(), normalized[1]._name()))
                    else:
                        seen[normalized] = branch
        if not isinstance(node, PassThroughNode):
            work.extend(node.children())
    return conflicts

