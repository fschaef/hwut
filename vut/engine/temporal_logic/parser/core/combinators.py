"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

SYNTAX SUPPORT  --  the authoring combinators for the GRAMMAR in grammar.py.

A grammar rule is written with these combinators plus bare tuples and the
terminal/reference objects from terminals.py:

    (a, b, ...)      an implicit SEQUENCE (a tuple is a sequence by default)
    [a, b, ...]      an OPTIONAL (a list is zero-or-one): a one-element list is
                     that element made optional; more elements, an optional
                     sequence
    (a, ALT, b, ...) an ALTERNATION: ALT is a sentinel placed BETWEEN branches
                     inside a tuple, read as 'a | b | ...'. A branch that is
                     itself a sequence is grouped: (a, ALT, (b, c))
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
bare tuple), no OPT alias (an optional is a bare list), and ALT is not a call
but a between-branches sentinel (the Alt CLASS it lowers to is internal). These
authoring objects are lightweight: each carries its children
and names the runtime node class it becomes (its 'node_class' in grammar_ast).
'compile(ctx)' lowers the authored structure into that uniform Node tree,
deferring LEAF resolution -- a terminal object, an '<name>' rule reference, or a
bare-string keyword -> TerminalNode / LuauNode / NonTerminalNode -- to 'ctx', the engine,
which owns the token-id table and the rule map. Thus this module depends only on
grammar_ast -- never on the parser engine -- and grammar.py depends only on this
vocabulary plus terminals.py.
______________________________________________________________________________
"""
from . import grammar_ast as nodes


# A bare tuple is a sequence; a bare list is an optional; ALL alternation is
# written with the ALT sentinel placed BETWEEN branches inside a tuple --
# (a, ALT, b, ALT, c) -- so a rule body reads like BNF's 'a | b | c' with no
# wrapping call. The sentinel is a unique object; the Alt CLASS below is what a
# tuple-with-ALT lowers to.
ALT = type("_AltSentinel", (), {"__repr__": lambda self: "ALT"})()


def _alt_from_tuple(parts):
    """RETURN: Alt, built by splitting 'parts' on the ALT sentinel.

    Each segment between sentinels is one branch: a one-element segment is that
    element directly; a multi-element segment is an implicit-sequence tuple
    (so a branch that is itself a sequence is grouped, e.g. (a, ALT, (b, c))).
    """
    branches, cur = [], []
    for p in parts:
        if p is ALT:
            branches.append(cur[0] if len(cur) == 1 else tuple(cur))
            cur = []
        else:
            cur.append(p)
    branches.append(cur[0] if len(cur) == 1 else tuple(cur))
    return Alt(*branches)


def _compile_child(child, ctx):
    """RETURN: Node, the compiled form of one authored child.

    A combinator delegates to its own compile(); a bare tuple is an implicit
    sequence -- unless it contains the ALT sentinel, in which case it is an
    ALTERNATION split on ALT into branches; a list is an OPTIONAL ( '[ ... ]' --
    zero or one time ): a one-element list is that element made optional, a
    multi-element list is an optional sequence. Any other value (a terminal
    object, a '<name>' rule reference, or a bare-string keyword) is a leaf the
    engine resolves via ctx.compile_leaf.
    """
    if isinstance(child, _Combinator):
        return child.compile(ctx)
    if isinstance(child, tuple):
        if ALT in child:
            return _alt_from_tuple(child).compile(ctx)
        return Seq(*child).compile(ctx)
    if isinstance(child, list):
        body = child[0] if len(child) == 1 else Seq(*child)
        return Opt(body).compile(ctx)
    return ctx.compile_leaf(child)


class _Combinator:
    """Base for the authoring combinators. Holds children; names a node class.

    Called directly in grammar.py: Alt and Seq take their children variadically
    (Alt(a, b, ...)), Opt/Plus/Star take a single body (Opt(x)). A subclass sets
    'node_class' (the grammar_ast type it lowers into) and 'compile(ctx)' builds
    that node from its compiled children.
    """
    __slots__ = ("children",)
    node_class = None

    def __init__(self, *children):
        self.children = children

    def compile(self, ctx):
        """RETURN: Node, this combinator lowered into its node_class."""
        raise NotImplementedError


class Seq(_Combinator):
    """An implicit/explicit sequence; lowers to SeqNode.

    Written as a bare tuple in grammar.py (the implicit form); constructed
    variadically (Seq(a, b, ...)) where an explicit instance is needed.
    """
    node_class = nodes.SeqNode

    def compile(self, ctx):
        return self.node_class([_compile_child(c, ctx) for c in self.children])


class Alt(_Combinator):
    """An alternation; lowers to AltNode. Alt(a, b, ...)."""
    node_class = nodes.AltNode

    def compile(self, ctx):
        return self.node_class([_compile_child(c, ctx) for c in self.children])


class _Unary(_Combinator):
    """A one-body combinator (Opt/Plus/Star); lowers to its node_class(body).

    Constructed with a single body argument (Opt(x)); stored in the shared
    'children' tuple so the base __init__ and this compile() stay uniform.
    """
    __slots__ = ()

    def compile(self, ctx):
        (body,) = self.children
        return self.node_class(_compile_child(body, ctx))


class Opt(_Unary):
    """Optional; lowers to OptNode."""
    node_class = nodes.OptNode


class Plus(_Unary):
    """One-or-more; lowers to PlusNode."""
    node_class = nodes.PlusNode


class Star(_Unary):
    """Zero-or-more; lowers to StarNode."""
    node_class = nodes.StarNode


# -- the authoring surface used in grammar.py ---------------------------------
# PLUS(x) and STAR(x) are exposed under CAPITALIZED aliases of their classes, to
# read as grammar operators called on one body. There is no SEQ alias (a sequence
# is a bare tuple), no OPT alias (an optional is a bare list, e.g. [x] or [a, b];
# the Opt CLASS still exists and is what a list lowers to), and ALT is the
# sentinel defined at the top of this module -- written BETWEEN branches inside a
# tuple, not as a call (the Alt CLASS it lowers to stays internal). The terminal
# factories (T) live in terminals.py; a rule reference is the bare string
# '<name>' resolved by the engine. grammar.py imports ALT/PLUS/STAR and T.
PLUS = Plus
STAR = Star


def compile_element(element, ctx):
    """RETURN: Node, the compiled form of a top-level authored 'element'.

    The single entry the engine calls per rule body. A bare tuple is an implicit
    sequence; a combinator lowers itself; a terminal object, an R reference, or a
    bare-string keyword is a leaf resolved by 'ctx'.
    """
    return _compile_child(element, ctx)
