"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

OPERATOR INTERFACES  --  shape-identity signals over a truthful universal root.

Every operator-shaped node -- the generic CST castings (core.cst_nodes) AND the
typed AST nodes (the outer ast_nodes) -- derives from one of these. Their purpose
is SIGNALLING, not behaviour: a node's interface declares WHICH grammar operator
produced it (OR / OPT / SEQ / PLUS / STAR), truthfully, for both kinds of node,
with no fakery on either side.

Why signalling and not a callable accessor contract.  A digested AST node (say
Trigger, from an OR rule) does not retain a raw 'triggered_index' -- the branch
choice was TRANSLATED into typed fields (is_keyword, name) at the factory. And
nothing ever asks a held child for its operator internals: the engine, when a
node is a sub-element of a parent sequence, only PLACES it as a value; the
which-branch question is asked once, at the OR's own reduce, then baked in and
never re-asked. So an accessor contract ('give me your triggered_index') would
force every digested node to fabricate an answer no caller reads. The honest,
GENERAL law is therefore the truthful intersection: every node carries 'begin'
and is placeable, and DECLARES its shape by which interface it derives from.

What the signal is FOR (it carries real weight, it is not a bare tag):
  - error analysis / diagnostics: "expected an OR-construct, got a SEQ-shaped
    node" -- detectable uniformly on a generic node or a typed one;
  - the load-time validator: "this rule is an OR rule, so its factory's node
    must be OR-shaped" -- a pure shape-correspondence check;
  - a semantic pass walking constructs by grammatical category.
None of those call shape accessors; they READ THE SHAPE. That is the contract.

Where the shape-specific accessors live.  The GENERIC CST nodes expose
triggered_index / present+child / seq_children / rep_items as their OWN concrete
surface (the engine reads them off CST nodes during construction). Those are NOT
hoisted here as universal obligations, because a digested AST node cannot honour
them without fakery -- they are honestly answerable only on the generic casting.

core stays grammar-agnostic and language-free.
______________________________________________________________________________
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
