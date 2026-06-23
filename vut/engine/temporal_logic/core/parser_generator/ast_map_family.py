"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
================================================================================
                          AST-MAP ROUTER FAMILY (D-19)
================================================================================

An AST_MAP value is applied to the CST node its rule reduced to. For SEQ and
PLUS rules that value is a single factory receiving the node. For the BRANCHING
shapes -- OR (which branch fired), OPT (present / absent), STAR (empty / non-
empty) -- the value is a ROUTER: a small dict-shaped object that picks the
factory for the case the node carries, replacing hand-written triggered_index /
opt.present / 'if items' dispatch.

A router is CALLABLE: applied as 'fn(node)' at the one transformer seam in the
engine (Grammar._reduce), exactly like a plain factory, so the engine needs no
new case. Its '.shape' names the rule shape it belongs on. The routers are core
machinery (they name no rule; they route over CST node kinds); the load-time
shape gate that pins a router to its rule's shape lives in the outer layer
(ast_map.validate_ast_map_shapes), since only that layer holds the AST map.

ROUTE LEAVES. A leaf is a factory (a callable receiving the routed value) OR a
plain constant (returned as-is) OR the PASS sentinel (forward the routed value
unchanged). So 'OptMap({True: OpaqueLeaf.from_span, False: None})' needs no
'lambda _: None'.

WHAT ROUTERS DO NOT DO. They never inspect what a factory PRODUCES -- a routed
factory may build any node kind, opaque to its parent (an OR branch's product
is branch-dependent and unknowable at load). Routing keys off what the CST node
ITSELF carries (its fired branch / present flag / item count), never off the
product.
================================================================================
"""
from vut.engine.temporal_logic.core.parser_generator.ll2_grammar_spec import (SHAPE_OR, SHAPE_OPT, SHAPE_STAR)


class _Pass:
    """The PASS sentinel: a route leaf that forwards the routed value unchanged."""
    __slots__ = ()
    def __repr__(self):
        return "PASS"


PASS = _Pass()


def _apply_leaf(leaf, value):
    """RETURN: object, the route leaf applied to 'value'.

    PASS forwards 'value' unchanged; a callable leaf is called on 'value'; any
    other leaf is a constant returned as-is.
    """
    if leaf is PASS:
        return value
    if callable(leaf):
        return leaf(value)
    return leaf


class OrMap:
    """Router for an OR rule: pick the factory for the branch that fired (D-19).

    'routes' maps a branch ADDRESS to a leaf. An address is an int (the branch's
    triggered_index), a str (the branch's advisory role), or a tuple of either
    (several branches sharing one leaf -- the grouping that collapses a
    triggered_index 'i in (0,1,7)' fan-out). The matched branch's reduced value
    (or_node.child) is the routed value handed to the leaf.
    """
    shape = SHAPE_OR

    def __init__(self, routes):
        self._routes = dict(routes)

    def addresses(self):
        """RETURN: list, every individual branch address named, tuples flattened.

        The flat address list the shape gate validates against the OR's branch
        count and role tags.
        """
        flat = []
        for key in self._routes:
            flat.extend(key if isinstance(key, tuple) else (key,))
        return flat

    def __call__(self, or_node):
        """RETURN: object, the leaf for the fired branch applied to its child.

        Raises KeyError if no route matches the fired branch (load-gated to be
        total over the OR's branches, so this guards a hand-built node only).
        """
        for key, leaf in self._routes.items():
            addrs = key if isinstance(key, tuple) else (key,)
            if any(or_node.route_key(a) for a in addrs):
                return _apply_leaf(leaf, or_node.child)
        raise KeyError("OrMap: no route for branch index %d / role %r"
                       % (or_node.triggered_index, or_node.role))

    def __repr__(self):
        return "OrMap(%r)" % (self._routes,)


class OptMap:
    """Router for an OPT rule: pick by whether the optional fired (D-19).

    'routes' maps True -> the present leaf (handed opt_node.child) and False ->
    the absent leaf (a constant such as None or [], or a callable handed the
    OPT_Node). Either key may be omitted -- a missing case defaults to PASS for
    True (forward the child) and None for False.
    """
    shape = SHAPE_OPT

    def __init__(self, routes):
        self._routes = dict(routes)

    def __call__(self, opt_node):
        """RETURN: object, the present-leaf on the child, or the absent-leaf."""
        if opt_node.present:
            return _apply_leaf(self._routes.get(True, PASS), opt_node.child)
        leaf = self._routes.get(False, None)
        # An absent optional has no child value; a callable absent-leaf receives
        # the OPT_Node itself (rare), a constant is returned as-is.
        return leaf(opt_node) if callable(leaf) else leaf

    def __repr__(self):
        return "OptMap(%r)" % (self._routes,)


class StarMap:
    """Router for a STAR rule: pick by empty vs non-empty repetition (D-19).

    'routes' maps True -> the non-empty leaf (handed the STAR_Node to fold over
    its items) and False -> the empty leaf (a constant such as [], or a callable
    handed the STAR_Node). A missing True defaults to PASS (forward the node);
    a missing False defaults to None.
    """
    shape = SHAPE_STAR

    def __init__(self, routes):
        self._routes = dict(routes)

    def __call__(self, star_node):
        """RETURN: object, the non-empty leaf on the node, or the empty-leaf."""
        if star_node.items:
            return _apply_leaf(self._routes.get(True, PASS), star_node)
        leaf = self._routes.get(False, None)
        return leaf(star_node) if callable(leaf) else leaf

    def __repr__(self):
        return "StarMap(%r)" % (self._routes,)
