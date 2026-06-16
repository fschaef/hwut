"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

SYNTAX SUPPORT  --  the authoring combinators for the GRAMMAR in grammar.py.

A grammar rule is written with these combinators plus bare tuples and the
terminal/reference objects from terminals.py:

    (a, b, ...)      an implicit SEQUENCE (a tuple is a sequence by default)
    [a, b, ...]      an OPTIONAL (a list is zero-or-one): a one-element list is
                     that element made optional; more elements, an optional
                     sequence
    (a, OR, b, ...) an ALTERNATION: OR is a sentinel placed BETWEEN branches
                     inside a tuple, read as 'a | b | ...'. A branch that is
                     itself a sequence is grouped: (a, OR, (b, c))
    PLUS(x)          x one or more times
    STAR(x)          x zero or more times
    t_...            a terminal object (T.regex/T.captured/T.opaque, terminals.py)
    "<name>"         a reference to another GRAMMAR rule (a bare string in angle
                     brackets; matches the <name> spelling used in SYNTAX_DOC)
    "literal"        a bare-string keyword: a silent terminal spelled as written.
                     A keyword that genuinely looks like '<...>' is spelled
                     explicitly with T.string("<...>") so it is not read as a ref.

The remaining combinator classes are exposed under capitalized aliases
(PLUS/STAR), called directly on one body. There is no SEQ alias (a sequence is a
bare tuple), no OPT alias (an optional is a bare list), and OR is not a call
but a between-branches sentinel (the Alt CLASS it lowers to is internal). These
authoring objects are lightweight: each carries its children
and names the runtime node class it becomes (its 'node_class' in grammar_spec).
'compile(ctx)' lowers the authored structure into that uniform SpecNode tree,
deferring LEAF resolution -- a terminal object, an '<name>' rule reference, or a
bare-string keyword -> Terminal_Spec / Rule_Spec -- to 'ctx', the engine,
which owns the token-id table and the rule map. Thus this module depends only on
grammar_spec -- never on the parser engine -- and grammar.py depends only on this
vocabulary plus terminals.py.
______________________________________________________________________________
"""
from . import ll2_grammar_spec as _default_nodes

# The node module is parameterisable: the engine compiles to ll2_grammar_spec
# (the active LL(2) hierarchy, the default here). A node module exposes the node-
# class names with matching constructors; compile_element(..., nodes=<module>)
# threads the choice through, and the combinator classes read their node_class
# off the active module per compile -- so combinators never hard-depends on one
# hierarchy.
nodes = _default_nodes


# A bare tuple is a sequence; a bare list is an optional; ALL alternation is
# written with the OR sentinel placed BETWEEN branches inside a tuple --
# (a, OR, b, OR, c) -- so a rule body reads like BNF's 'a | b | c' with no
# wrapping call. The sentinel is a unique object; the Alt CLASS below is what a
# tuple-with-OR lowers to.
OR = type("_AltSentinel", (), {"__repr__": lambda self: "OR"})()

# A grammar VALUE may be a dict instead of a pattern: a SUBSPACE (D-20). Its TOP
# key holds the rule's own pattern; its other keys are member rules reachable
# ONLY from within this subspace (or a nested one). TOP is a unique sentinel
# key, conventionally written first. Subspaces flatten to the one flat rule map
# (bare names, unchanged resolver) before compile; an encapsulation gate then
# rejects a reference into a subspace from outside it. See core/subspace.py.
TOP = type("_TopKey", (), {"__repr__": lambda self: "TOP"})()


def _alt_from_tuple(parts):
    """RETURN: Alt, built by splitting 'parts' on the OR sentinel.

    Each segment between sentinels is one branch: a one-element segment is that
    element directly; a multi-element segment is an implicit-sequence tuple
    (so a branch that is itself a sequence is grouped, e.g. (a, OR, (b, c))).
    """
    branches, cur = [], []
    for p in parts:
        if p is OR:
            branches.append(cur[0] if len(cur) == 1 else tuple(cur))
            cur = []
        else:
            cur.append(p)
    branches.append(cur[0] if len(cur) == 1 else tuple(cur))
    return Alt(*branches)


def _compile_child(child, ctx, nodes):
    """RETURN: SpecNode, the compiled form of one authored child.

    A combinator delegates to its own compile(); a bare tuple is an implicit
    sequence -- unless it contains the OR sentinel, in which case it is an
    ALTERNATION split on OR into branches; a list is an OPTIONAL ( '[ ... ]' --
    zero or one time ): a one-element list is that element made optional, a
    multi-element list is an optional sequence. Any other value (a terminal
    object, a '<name>' rule reference, or a bare-string keyword) is a leaf the
    engine resolves via ctx.compile_leaf.

    'nodes' is the node module to build into (grammar_spec; LL(1) used the retired grammar_ast,
    ll2_grammar_spec for LL(2)); it is threaded down so one combinator tree can
    lower into either hierarchy.
    """
    if isinstance(child, _Combinator):
        return child.compile(ctx, nodes)
    if isinstance(child, tuple):
        if OR in child:
            return _alt_from_tuple(child).compile(ctx, nodes)
        return Seq(*child).compile(ctx, nodes)
    if isinstance(child, list):
        body = child[0] if len(child) == 1 else Seq(*child)
        return Opt(body).compile(ctx, nodes)
    return ctx.compile_leaf(child)


class _Combinator:
    """Base for the authoring combinators. Holds children; names a node class.

    Called directly in grammar.py: Alt and Seq take their children variadically
    (Alt(a, b, ...)), Opt/Plus/Star take a single body (Opt(x)). A subclass sets
    '_node_name' (the node-class name, looked up on the node module passed to
    compile) and 'compile(ctx, nodes)' builds that node from its compiled
    children. The name is resolved per-compile rather than bound at class
    definition, so the same combinator lowers into either the LL(1) or LL(2) node
    hierarchy depending on which module the engine threads in.
    """
    __slots__ = ("children",)
    _node_name = None

    def __init__(self, *children):
        self.children = children

    def compile(self, ctx, nodes):
        """RETURN: SpecNode, this combinator lowered into nodes.<_node_name>."""
        raise NotImplementedError


class Seq(_Combinator):
    """An implicit/explicit sequence; lowers to SEQ_Spec.

    Written as a bare tuple in grammar.py (the implicit form); constructed
    variadically (Seq(a, b, ...)) where an explicit instance is needed.
    """
    _node_name = "SEQ_Spec"

    def compile(self, ctx, nodes):
        cls = getattr(nodes, self._node_name)
        return cls([_compile_child(c, ctx, nodes) for c in self.children])


class Alt(_Combinator):
    """An alternation; lowers to OR_Spec. Alt(a, b, ...)."""
    _node_name = "OR_Spec"

    def compile(self, ctx, nodes):
        cls = getattr(nodes, self._node_name)
        return cls([_compile_child(c, ctx, nodes) for c in self.children])


class _Unary(_Combinator):
    """A one-body combinator (Opt/Plus/Star); lowers to its node_class(body).

    Constructed with a single body argument (Opt(x)); stored in the shared
    'children' tuple so the base __init__ and this compile() stay uniform.
    """
    __slots__ = ()

    def compile(self, ctx, nodes):
        cls = getattr(nodes, self._node_name)
        (body,) = self.children
        return cls(_compile_child(body, ctx, nodes))


class Opt(_Unary):
    """Optional; lowers to OPT_Spec."""
    _node_name = "OPT_Spec"


class Plus(_Unary):
    """One-or-more; lowers to PLUS_Spec."""
    _node_name = "PLUS_Spec"


class Star(_Unary):
    """Zero-or-more; lowers to STAR_Spec."""
    _node_name = "STAR_Spec"


# -- the authoring surface used in grammar.py ---------------------------------
# PLUS(x) and STAR(x) are exposed under CAPITALIZED aliases of their classes, to
# read as grammar operators called on one body. There is no SEQ alias (a sequence
# is a bare tuple), no OPT alias (an optional is a bare list, e.g. [x] or [a, b];
# the Opt CLASS still exists and is what a list lowers to), and OR is the
# sentinel defined at the top of this module -- written BETWEEN branches inside a
# tuple, not as a call (the Alt CLASS it lowers to stays internal). The terminal
# factories (T) live in terminals.py; a rule reference is the bare string
# '<name>' resolved by the engine. grammar.py imports OR/PLUS/STAR and T.
PLUS = Plus
STAR = Star


def compile_element(element, ctx, nodes=_default_nodes):
    """RETURN: SpecNode, the compiled form of a top-level authored 'element'.

    The single entry the engine calls per rule body. A bare tuple is an implicit
    sequence; a combinator lowers itself; a terminal object, an R reference, or a
    bare-string keyword is a leaf resolved by 'ctx'. 'nodes' selects the target
    node hierarchy (defaults to ll2_grammar_spec, the active LL(2) hierarchy); a
    different engine may pass its own module.
    """
    return _compile_child(element, ctx, nodes)
