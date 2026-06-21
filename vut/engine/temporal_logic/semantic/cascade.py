"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

CASCADE GRAPH  (pass 2, README F)

Nodes are event KINDS; an edge X -> Y exists iff an X-triggered rule emits Y
(an EventSpec effect). Arming and spawning create no edges. Liveness is
over-approximated -- every reactor's rules contribute their edges
unconditionally, so a cycle here is a possible no-time re-fire, conservatively
flagged.

  -- a rule on ANY contributes its emission edges inbound from EVERY node;
  -- 'until:' causes contribute no edges;
  -- system-produced kinds (clock events, BEGIN, END, CHANGE) have outgoing
     edges but no rule-authored inbound edge; naming a system kind as an
     emission is a semantic error [CASCADE];
  -- CHANGE is delivered at the step boundary, so it adds no inbound edge.

A cascade CYCLE is fatal [CASCADE]: an event kind re-firing within one no-time
cascade. Detection is a stackless coloured DFS, linear in nodes plus edges;
every back-edge is reported with its full event chain, ACCUMULATE-AND-CONTINUE
(unlike the import cycle, which stops its stage outright).
______________________________________________________________________________
"""
from dataclasses import dataclass, field

from .diagnostics       import (SemanticClass, semantic_error)
from ..parser.ast_nodes import (Causality, EventSpec, Namespace, Mode, State, StateMachine, ModeGroup)

_SYSTEM_KINDS = ("ANY", "BEGIN", "END", "CHANGE")


@dataclass
class Cascade:
    """The event-kind graph: adjacency plus the offset each edge was seen at.

    'edges' maps a source kind to the set of kinds it emits. 'any_emits' holds
    the emissions of ANY-triggered rules, applied inbound from every node when
    the graph is closed. 'offset_of' remembers a representative offset per edge
    for the cycle diagnostic. 'queried' accumulates every kind a rule consumes
    (the emitter's tracer set, README H).
    """
    edges:     "dict[str, set]"   = field(default_factory=dict)
    any_emits: "set"              = field(default_factory=set)
    offset_of: "dict[tuple, int]" = field(default_factory=dict)
    queried:   "set"              = field(default_factory=set)

    def add_edge(self, src: str, dst: str, offset: int):
        """RETURN: None. Records edge src -> dst, remembering 'offset' once."""
        self.edges.setdefault(src, set()).add(dst)
        self.offset_of.setdefault((src, dst), offset)


def build_cascade(module, reporter) -> Cascade:
    """RETURN: Cascade, the event-kind graph of 'module' (edges + queried).

    Walks every Causality (including those nested in reactors and namespaces),
    reads the trigger kind and each EventSpec emission, and records an edge per
    emission. ANY-triggered emissions are held aside and fanned in from every
    node once all nodes are known. Reports [CASCADE] for an emission naming a
    system kind. Does NOT detect cycles -- that is find_cycles, run after the
    graph is whole.
    """
    cascade = Cascade()

    for rule in _all_causalities(module.items):
        trigger = rule.cause.trigger
        src     = ".".join(trigger.name)
        cascade.queried.add(src)

        for effect in rule.effects:
            if not isinstance(effect, EventSpec):
                continue                     # arm/spawn/other: no cascade edge
            dst = ".".join(effect.name)
            if dst in _SYSTEM_KINDS:
                reporter.report(semantic_error(
                    SemanticClass.CASCADE, effect.begin,
                    "emission names system kind '%s'" % dst))
                continue
            if trigger.is_keyword and src == "ANY":
                cascade.any_emits.add((dst, effect.begin))
            elif trigger.is_keyword:
                # BEGIN/END/CHANGE are system sources: outgoing edge only.
                cascade.add_edge(src, dst, effect.begin)
            else:
                cascade.add_edge(src, dst, effect.begin)

    _close_any(cascade)
    return cascade


def _close_any(cascade: Cascade):
    """RETURN: None. Fans every ANY-triggered emission in from every known node.

    An ANY rule fires at every event, so its emissions are reachable from each
    node in the graph. Applied after the explicit edges so the node set is
    known; CHANGE is excluded as a source (delivered at the step boundary).
    """
    nodes = set(cascade.edges.keys())
    for dsts in cascade.edges.values():
        nodes |= dsts
    for dst, offset in cascade.any_emits:
        for src in nodes:
            if src == "CHANGE":
                continue
            cascade.add_edge(src, dst, offset)


def find_cycles(cascade: Cascade, reporter):
    """RETURN: None. Reports every cascade cycle as [CASCADE] with its full
              event chain; accumulate-and-continue (README F).

    A stackless coloured DFS: WHITE unseen, GREY on the active path, BLACK done.
    A GREY target on descent is a back-edge -> a cycle; the chain from that
    target through the active path is the report. Every back-edge is reported,
    not just the first, so the author sees all cascade loops in one pass.
    """
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {}

    nodes = set(cascade.edges.keys())
    for dsts in cascade.edges.values():
        nodes |= dsts
    for n in nodes:
        colour.setdefault(n, WHITE)

    for start in sorted(nodes):
        if colour[start] != WHITE:
            continue
        # explicit stack of (node, iterator over its out-edges, path)
        stack = [(start, iter(sorted(cascade.edges.get(start, ()))), [start])]
        colour[start] = GREY
        while stack:
            node, succ, path = stack[-1]
            nxt = next(succ, None)
            if nxt is None:
                colour[node] = BLACK
                stack.pop()
                continue
            if colour.get(nxt) == GREY:
                chain = path[path.index(nxt):] + [nxt] if nxt in path \
                        else path + [nxt]
                offset = cascade.offset_of.get((node, nxt), 0)
                reporter.report(semantic_error(
                    SemanticClass.CASCADE, offset,
                    "cascade cycle: " + " -> ".join(chain)))
            elif colour.get(nxt, WHITE) == WHITE:
                colour[nxt] = GREY
                stack.append((nxt, iter(sorted(cascade.edges.get(nxt, ()))),
                              path + [nxt]))


# --- AST traversal -----------------------------------------------------------

def _all_causalities(items):
    """YIELD: [0] Causality  every rule at top level, inside a namespace, and
                             inside a reactor's modes/states, in source order.

    The cascade graph spans the whole module: a rule inside a state contributes
    its edges just as a top-level rule does (liveness is over-approximated).
    """
    for item in items:
        if isinstance(item, Causality):
            yield item
        elif isinstance(item, Namespace):
            yield from _all_causalities(item.items)
        elif isinstance(item, (Mode, State)):
            yield from getattr(item, "causalities", [])
        elif isinstance(item, StateMachine):
            for st in item.states:
                yield from getattr(st, "causalities", [])
        elif isinstance(item, ModeGroup):
            for md in item.modes:
                yield from getattr(md, "causalities", [])
