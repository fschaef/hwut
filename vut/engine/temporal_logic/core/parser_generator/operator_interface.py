"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
================================================================================
                              OPERATOR INTERFACES
================================================================================

              +--------------------------------------------------+
              |               OPERATOR INTERFACE                 |
              |   (Universal Root: Carries 'begin', Placeable)   |
              +--------------------------------------------------+
              | Signals Grammar Op: OR / OPT / SEQ / PLUS / STAR |
              +--------------------------------------------------+
                                       |
                   +-------------------+-------------------+
                   |                                       |
                   v                                       v
     +---------------------------+           +---------------------------+
     |     GENERIC CST NODES     |           |      TYPED AST NODES      |
     |     (core.cst_nodes)      |           |       (outer nodes)       |
     +---------------------------+           +---------------------------+
     | Concrete Surface:         |           | Digested Structure:       |
     | - triggered_index         |           | - Choices translated into |
     | - present+child           |           |   typed fields at factory |
     | - seq_children / items    |           | - No internal operator    |
     |                           |           |   accessors (no fakery)   |
     | *Engine reads directly*   |           |                           |
     +---------------------------+           +---------------------------+

CORE PRINCIPLE: SIGNALLING OVER BEHAVIOUR
--------------------------------------------------------------------------------

The interface asserts structural identity, not a callable accessor contract.
The deep reason (D-19): the product a rule's factory builds is NOT KNOWABLE
before runtime -- an OR rule yields a different node kind per branch that fires
(a ConstantLeaf, an OpaqueLeaf, a passed-through operand), so no single interface can
be promised upward. A parent therefore CANNOT query a child product through a
shape accessor even in principle; it takes the product as an opaque typed value
and reads its own fields. Forcing a universal accessor like 'triggered_index'
onto a digested AST node would compel it to fabricate data that no caller reads
AND could not read coherently. The honest law is the shape-identity intersection.

WHERE THE INTERFACE LIVES
--------------------------------------------------------------------------------

The operator interface is a property of the GENERIC CST node a rule produces
BEFORE transformation -- OR_Node is OR_Interface, SEQ_Node is SEQ_Interface, and
so on. It is the contract between a rule's CST node and THAT SAME RULE's factory
or router (one level, internal): the OR rule's OrMap routes on the OR_Node it
receives; the SEQ rule's factory reads its SEQ_Node. Once the factory runs, the
product is opaque -- there is no operator-interface contract upward. A produced
AST node does not carry, derive from, or fake any operator interface as a
promise to its parent.


APPLICATIONS OF THE SHAPE SIGNAL
--------------------------------------------------------------------------------
The shape is read directly via interface type-matching to drive:

1. ERROR ANALYSIS: 
   Uniform diagnostics across both node categories 
   (e.g., "expected an OR-construct, got a SEQ-shaped node").

2. LOAD-TIME VALIDATION:
   The AST-map shape gate (D-19, ast_map.validate_ast_map_shapes) pins each
   rule's map entry to the rule's OWN shape -- an OrMap only on an OR rule, an
   OptMap on OPT, a StarMap on STAR; SEQ/PLUS take a single factory; a terminal
   needs none. It checks the rule's shape, never the opaque product.

3. SEMANTIC PASSES: 
   Walking constructs cleanly by their grammatical category.
================================================================================
"""
from abc import ABC


class Operator_Interface(ABC):
    """The truthful universal root: every operator-shaped node IS one of these.

    Carries the only contract that holds for EVERY node, generic or digested,
    without fakery: a source 'begin' offset, and being a placeable tree value.
    'begin' is provided by each node as an ordinary attribute/field (not an
    abstract property, which would collide with frozen-dataclass field ordering).
    No shape accessors are declared here; see the module docstring.
    """
    __slots__ = ()


class OR_Interface(Operator_Interface):
    """Signal: this node was produced by an alternation (OR) rule."""
    __slots__ = ()


class OPT_Interface(Operator_Interface):
    """Signal: this node was produced by an optional (OPT) position."""
    __slots__ = ()


class SEQ_Interface(Operator_Interface):
    """Signal: this node was produced by a sequence (SEQ) rule."""
    __slots__ = ()


class PLUS_Interface(Operator_Interface):
    """Signal: this node was produced by a one-or-more (PLUS) rule."""
    __slots__ = ()


class STAR_Interface(Operator_Interface):
    """Signal: this node was produced by a zero-or-more (STAR) rule."""
    __slots__ = ()
