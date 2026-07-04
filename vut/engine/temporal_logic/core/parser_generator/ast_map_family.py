"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
================================================================================
                          AST-MAP ROUTER FAMILY (D-19)
================================================================================

An AST_MAP value is applied to the CST node its rule reduced to. The family
carries one TYPED wrapper per rule shape, so the outer layer's load-time shape
gate can assert map-entry kind against rule shape (an OrMap on a SEQ rule is a
load error, not a runtime surprise):

    SEQ   the value is a SeqMap: ONE constructor receiving the finished node,
          which is its own role-db ('node["role"]', strict).
    OR    the value is an OrMap: pick the leaf for the BRANCH that fired.
    OPT   the value is an OptMap: transform the child when PRESENT; NodeAbsent is
          the typed absence value, FIXED by the machinery and not author-supplied.
    STAR  the value is a StarMap: ONE item constructor applied uniformly over
          the items; the product is a NodeList, EMPTY when nothing matched.
    PLUS  the value is a PlusMap: as StarMap; the node guarantees 1..n items,
          so the NodeList is never empty.

A map value is CALLABLE: applied as 'fn(node)' at the one transformer seam in
the engine (Grammar._reduce), exactly like a plain factory, so the engine needs
no new case. Its '.shape' names the rule shape it belongs on. The family is core
machinery (it names no rule; it routes over CST node kinds); the load-time
shape gate that pins a map entry to its rule's shape lives in the outer layer
(ast_map.validate_ast_map_shapes), since only that layer holds the AST map.

StarMap and PlusMap are APPLIERS: one item constructor, applied uniformly,
one product type (NodeList) regardless of arity -- emptiness is a state read
off the product, never a different product. (The historic A-13 arity-router
idea is retired; this family is the ruling.)
"""
from .ll2_grammar_spec import (SHAPE_OR, SHAPE_OPT, SHAPE_SEQ,
                               SHAPE_STAR, SHAPE_PLUS)
from .cst_nodes import NodeAbsent
from ..symbol.ast import NodeList


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
    triggered_index), a str (the branch's role -- usable only when the branch is
    a PLAIN rule or terminal, the only thing nameable, A-13), or a tuple of
    either (several branches sharing one leaf). The matched branch's reduced
    value (or_node.child) is the routed value handed to the leaf.
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
    """Router for an OPT rule: transform the child when PRESENT; absent -> NodeAbsent.

    ONE-ARMED by law (A-13): 'present' is the only thing the author controls -- a
    leaf (factory or PASS) applied to opt_node.child when the optional fired. The
    absent case is FIXED to NodeAbsent, the typed absence value, and has no
    parameter, so an OPT can never be made to carry a second alternative. Default
    present-leaf is PASS (forward the child unchanged).
    """
    shape = SHAPE_OPT

    def __init__(self, present=PASS):
        self._present = present

    def __call__(self, opt_node):
        """RETURN: object, the present-leaf on the child if the optional fired;
                   NodeAbsent otherwise.

        The absent arm always yields NodeAbsent -- not author-supplied (A-13).
        """
        if opt_node.present:
            return _apply_leaf(self._present, opt_node.child)
        return NodeAbsent

    def __repr__(self):
        return "OptMap(%r)" % (self._present,)


class SeqMap:
    """Applier for a SEQ rule: ONE constructor over the finished sequence node.

    The node is its own role-db: the constructor reads the children it means by
    role ('node["cause"]', strict -- a role the rule does not carry raises), so
    the factory line documents the rule it serves. 'ctor' may also be PASS
    (forward the node unchanged: an explicit, typed passthrough that still
    satisfies the coverage gate).
    """
    shape = SHAPE_SEQ

    def __init__(self, ctor):
        self._ctor = ctor

    def __call__(self, seq_node):
        """RETURN: object, the constructor's product for 'seq_node' -- the
                  rule's AST node if 'ctor' builds one, or 'seq_node' itself
                  under PASS.
        """
        return _apply_leaf(self._ctor, seq_node)

    def __repr__(self):
        return "SeqMap(%r)" % (self._ctor,)


class StarMap:
    """Applier for a STAR rule: ONE item constructor, uniformly, over 0..n items.

    NOT a router (A-13): arity selects nothing. The product is always a
    NodeList -- EMPTY when the star matched nothing -- so emptiness is a state
    the consumer reads off the one product type, never a different product.
    Default item leaf is PASS (collect the reduced items unchanged).
    """
    shape = SHAPE_STAR

    def __init__(self, item_ctor=PASS):
        self._item_ctor = item_ctor

    def __call__(self, star_node):
        """RETURN: NodeList, the item leaf applied to every matched item in
                  match order -- empty if the star matched nothing.
        """
        return NodeList(tuple(_apply_leaf(self._item_ctor, it)
                              for it in star_node.items))

    def __repr__(self):
        return "StarMap(%r)" % (self._item_ctor,)


class PlusMap:
    """Applier for a PLUS rule: as StarMap, over 1..n items.

    The PLUS node guarantees at least one item by parse, so the produced
    NodeList is never empty; no arity check is performed here -- the guarantee
    is the engine's, not this applier's.
    """
    shape = SHAPE_PLUS

    def __init__(self, item_ctor=PASS):
        self._item_ctor = item_ctor

    def __call__(self, plus_node):
        """RETURN: NodeList, the item leaf applied to every matched item in
                  match order -- never empty (PLUS matches at least once).
        """
        return NodeList(tuple(_apply_leaf(self._item_ctor, it)
                              for it in plus_node.items))

    def __repr__(self):
        return "PlusMap(%r)" % (self._item_ctor,)
