"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

GRAMMAR SPEC  --  the compiled grammar as a uniform polymorphic tree.

These '*_Spec' classes are the GRAMMAR layer: the static, compile-once,
shared-across-every-parse description of what the engine may match at each point
(OR_Spec / SEQ_Spec / OPT_Spec / STAR_Spec / PLUS_Spec, plus Terminal_Spec and
the per-rule Rule_Spec). They carry first2_set / nullable / the conflict scan /
expand -- they DESCRIBE and the engine consults them. They never hold a parse
result. The RESULT layer is cst_nodes (OR_Node / SEQ_Node / STAR_Node /
PLUS_Node): a fresh node per occurrence, built by a Spec's cst_reduce, recording
what actually matched THIS time. One Spec (the mould) yields many Nodes (the
castings). The prefix mirrors the grammar operator the author wrote (OR / OPT /
SEQ / PLUS / STAR); OPT_Spec has no OPT_Node -- an optional casts to an OR_Node
whose absent state is the ABSENT child.
______________________________________________________________________________
"""
from .terminals import t_fr_span_open, t_fr_eof
from .cst_nodes import OR_Node, SEQ_Node, PLUS_Node, STAR_Node, ABSENT

ELEM       = 0
REDUCE     = 1
LOOP       = 2
CST_REDUCE = 3      # operator self-reduce to a CST node (CST build mode only)


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


class SpecNode:
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
class Terminal_Spec(SpecNode):
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


class Rule_Spec(SpecNode):
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
# Combinators: Branch_Spec and Operator_Spec
# ---------------------------------------------------------------------------
class Branch_Spec(SpecNode):
    __slots__ = ("branches",)

    def __init__(self, branches):
        self.branches = tuple(branches)

    def children(self):
        return self.branches


class SEQ_Spec(Branch_Spec):
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
        if parser.cst_mode:
            # Materialise this sequence as its own SEQ_Node. Open a sub-frame so
            # the surviving per-position values collect here (not the parent),
            # then reduce. The node is anonymous (name=None); a named rule whose
            # pattern is this sequence stamps its rule name at the Rule_Spec
            # reduce, so inline sequences stay None and rule-level ones get named.
            parser.open_frame(frames)
            work.append((CST_REDUCE, (self, None)))
        for sub in reversed(self.branches):
            work.append((ELEM, sub))

    def cst_reduce(self, frame, _extra):
        """RETURN: SEQ_Node, over the surviving per-position values of the frame."""
        return SEQ_Node(children=tuple(frame.values))


class OR_Spec(Branch_Spec):
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
        chosen = parser.choose_alt(self)
        if parser.cst_mode:
            # Capture WHICH branch fired (its grammar index) and reduce to an
            # OR_Node carrying that index plus the branch's reduced value. The
            # sub-frame collects exactly one value (the chosen branch's result).
            index = self.branches.index(chosen)
            parser.open_frame(frames)
            work.append((CST_REDUCE, (self, index)))
        work.append((ELEM, chosen))

    def cst_reduce(self, frame, index):
        """RETURN: OR_Node, the matched branch index and its single reduced value.

        'index' is the grammar index of the branch choose_alt selected. A branch
        that produced no surviving value (all-silent, or an empty inline branch)
        yields child=ABSENT.
        """
        child = frame.values[0] if frame.values else ABSENT
        return OR_Node(triggered_index=index, child=child)


class Operator_Spec(SpecNode):
    __slots__ = ("body",)

    def __init__(self, body):
        self.body = body

    def children(self):
        return (self.body,)

    def first2_set(self, grammar):
        return self.body.first2_set(grammar)


class OPT_Spec(Operator_Spec):
    __slots__ = ()

    def __repr__(self):
        return "Opt(%r)" % (self.body,)

    def first2_set(self, grammar):
        # Includes empty baseline marker to flag structural path choice
        return self.body.first2_set(grammar) | {()}

    def nullable(self, grammar):
        return True

    def expand(self, parser, frames, work):
        present = parser.starts(self.body)
        if parser.cst_mode:
            # An optional is the two-branch alternation '(body | empty)'. Reduce
            # to an OR_Node: index 0 = body present (child = its value), index 1
            # = absent (child = ABSENT). Absence is a STATE of OR_Node, marked on
            # the node, never inferred from a missing frame slot downstream.
            index = 0 if present else 1
            parser.open_frame(frames)
            work.append((CST_REDUCE, (self, index)))
        if present:
            work.append((ELEM, self.body))

    def cst_reduce(self, frame, index):
        """RETURN: OR_Node, index 0 (present, child=value) or 1 (absent, ABSENT)."""
        if index == 0:
            child = frame.values[0] if frame.values else ABSENT
        else:
            child = ABSENT
        return OR_Node(triggered_index=index, child=child)


class STAR_Spec(Operator_Spec):
    __slots__ = ()

    def __repr__(self):
        return "Star(%r)" % (self.body,)

    def first2_set(self, grammar):
        return self.body.first2_set(grammar) | {()}

    def nullable(self, grammar):
        return True

    def expand(self, parser, frames, work):
        if parser.cst_mode:
            # Open a sub-frame so each loop iteration's reduced body value
            # collects here; reduce to a STAR_Node (items possibly empty). The
            # CST_REDUCE is pushed FIRST so it runs LAST, after the loop drains.
            parser.open_frame(frames)
            work.append((CST_REDUCE, (self, None)))
        work.append((LOOP, (self.body, -1)))

    def cst_reduce(self, frame, _extra):
        """RETURN: STAR_Node, over the (possibly empty) collected repetitions."""
        return STAR_Node(items=tuple(frame.values))


class PLUS_Spec(Operator_Spec):
    __slots__ = ()

    def __repr__(self):
        return "Plus(%r)" % (self.body,)

    def nullable(self, grammar):
        return False

    def expand(self, parser, frames, work):
        if parser.cst_mode:
            # As STAR_Spec, but the body is matched once eagerly before the loop,
            # so items is guaranteed non-empty. Sub-frame collects all
            # repetitions; CST_REDUCE (pushed first, runs last) builds PLUS_Node.
            parser.open_frame(frames)
            work.append((CST_REDUCE, (self, None)))
        work.append((LOOP, (self.body, -1)))
        work.append((ELEM, self.body))

    def cst_reduce(self, frame, _extra):
        """RETURN: PLUS_Node, over the collected repetitions (guaranteed non-empty)."""
        return PLUS_Node(items=tuple(frame.values))


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
        if not isinstance(node, Rule_Spec):
            work.extend(node.children())

    first2 = {}
    null   = {}
    for node in reversed(order):
        if isinstance(node, Terminal_Spec):
            first2[node] = node.first2_set(grammar)
            null[node]  = False
        elif isinstance(node, Rule_Spec):
            first2[node] = set(node.first)        
            null[node]  = node.nullable(grammar)
        elif isinstance(node, SEQ_Spec):
            if not node.branches:
                first2[node] = {()}
            else:
                acc = first2[node.branches[0]]
                for sub in node.branches[1:]:
                    acc = merge_first2(acc, first2[sub])
                first2[node] = acc
            null[node]  = all(null[s] for s in node.branches)
        elif isinstance(node, OR_Spec):
            first2[node] = set().union(*(first2[s] for s in node.branches)) \
                           if node.branches else set()
            null[node]  = any(null[s] for s in node.branches)
        else:  # Operator_Spec
            first2[node] = set(first2[node.body])
            if isinstance(node, (OPT_Spec, STAR_Spec)):
                first2[node].add(())
            null[node]  = isinstance(node, (OPT_Spec, STAR_Spec))
    return first2


def collect_alt_conflicts(pattern, rule_name, grammar):
    """Detects distinct alternative paths that overlap on identical 2-token sequences."""
    first2 = _first2_sets_iterative(pattern, grammar)
    conflicts = []
    work = [pattern]
    while work:
        node = work.pop()
        if isinstance(node, OR_Spec):
            seen = {}
            for branch in node.branches:
                for lookahead_tuple in first2[branch]:
                    if not lookahead_tuple:
                        continue
                    
                    # Pad out single dangling terminals to complete pair profiles
                    normalized = (lookahead_tuple[0], t_fr_eof) if len(lookahead_tuple) == 1 else lookahead_tuple
                    
                    if normalized in seen:
                        conflicts.append(
                            "rule %s: 2-token lookahead (%s, %s) starts two OR branches"
                            % (rule_name, normalized[0]._name(), normalized[1]._name()))
                    else:
                        seen[normalized] = branch
        if not isinstance(node, Rule_Spec):
            work.extend(node.children())
    return conflicts
