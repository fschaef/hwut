"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

GRAMMAR SPEC  --  the compiled grammar as a uniform polymorphic tree.

These '*_Spec' classes are the GRAMMAR layer: the static, compile-once,
shared-across-every-parse description of what the engine may match at each point
(OR_Spec / SEQ_Spec / OPT_Spec / STAR_Spec / PLUS_Spec, plus Terminal_Spec and
the per-rule Rule_Spec). They carry first2_set / nullable / the conflict scan /
expand -- they DESCRIBE and the engine consults them. They never hold a parse
result. The RESULT layer is cst_nodes (OR_Node / OPT_Node / SEQ_Node /
STAR_Node / PLUS_Node): a fresh node per occurrence, built by a Spec's
cst_reduce, recording what actually matched THIS time. One Spec (the mould)
yields many Nodes (the castings). The prefix mirrors the grammar operator the
author wrote (OR / OPT / SEQ / PLUS / STAR), Spec and Node alike: each operator
casts to its own node kind.
______________________________________________________________________________
"""
from vut.engine.temporal_logic.core.parser_generator.cst_nodes import (OR_Node, OPT_Node, SEQ_Node, PLUS_Node, STAR_Node,
                        ABSENT)

ELEM       = 0
REDUCE     = 1
LOOP       = 2
CST_REDUCE = 3      # operator self-reduce to a CST node (CST build mode only)
ROLE_STAMP = 4      # post-body marker: tag the just-produced value with a role


class SpecNode:
    __slots__ = ()

    def first2_set(self, grammar):
        """RETURN: set[tuple], the 2-token lookahead sequences beginning this node.

        Memoised once the grammar is sealed (after _analyse reaches its FIRST_2
        fixpoint): the set is a pure function of the node thereafter, and the
        parse-time presence/branch tests (engine starts/choose_alt) ask for it
        repeatedly. During the fixpoint the grammar is NOT sealed, so the set is
        recomputed each iteration and never cached stale.
        """
        if getattr(grammar, "_sealed", False):
            cached = getattr(self, "_first2_cache", None)
            if cached is not None:
                return cached
            result = self._compute_first2(grammar)
            try:
                self._first2_cache = result
            except AttributeError:
                pass
            return result
        return self._compute_first2(grammar)

    def _compute_first2(self, grammar):
        """RETURN: set[tuple], freshly computed FIRST_2 (no memoisation)."""
        raise NotImplementedError

    def nullable(self, grammar):
        raise NotImplementedError

    def children(self):
        return ()

    def expand(self, parser, frames, work):
        raise NotImplementedError


# ===========================================================================
# TERMINALS  --  the lexeme specification, now a first-class SpecNode.
#
# (D-7) A terminal is one immutable specification: its shape and the fields that
# shape implies (a regex pattern, a keyword spelling, an opaque span mode). It is
# also a SpecNode -- a citizen of the GRAMMAR tree walked exactly like OR_Spec /
# SEQ_Spec, no special-cased bare leaf -- because the tree must be homogeneous.
# So the lexical spec and the grammar leaf are ONE object: Terminal_Spec.
#
# It is INTERNED by _name(): one Terminal_Spec per distinct terminal, shared
# across every grammar position that references it, and that shared object IS the
# token identity (Token.kind). 'silent' (dropped as punctuation vs kept in the
# frame) is a pure function of shape -- string => silent, every other shape =>
# kept -- so it rides on the interned object without splitting identity: two
# positions naming the same terminal cannot disagree about silent, because shape
# is part of _name(). This is why the per-position wrapper of the old design
# (Terminal_Spec wrapping a separate interned Terminal) collapsed into one class.
#
# The conductor (the parser / Grammar) owns TERMINAL_DB and extracts the lexer's
# pattern table from it; the lexer matches bytes against patterns and tags each
# token with the interned Terminal_Spec. The lexer imports no spec machinery.
# ===========================================================================
TERMINAL_DB = []      # interned Terminal_Specs, in declaration order
_BY_NAME    = {}      # _name() -> Terminal_Spec, for interning and reuse

_SHAPE_SILENT = {"regex": False, "captured": False, "opaque": False,
                 "string": True, "framing": True}


def _register_terminal(term):
    """RETURN: Terminal_Spec, 'term' if newly interned, else the existing one.

    A Terminal_Spec's _name() is its identity. The first of a given _name() is
    recorded in TERMINAL_DB (declaration order, the lexer's class-precedence
    lever) and indexed; a later call producing the same _name() returns the
    already-interned object, so a keyword shared by several rules is ONE token.
    Two non-identical terminals can never share a _name() (the scheme encodes
    every distinguishing field), so a _name() clash is the same terminal.
    """
    name = term._name()
    existing = _BY_NAME.get(name)
    if existing is not None:
        return existing
    _BY_NAME[name] = term
    TERMINAL_DB.append(term)
    return term


class Terminal_Spec(SpecNode):
    """A terminal: its lexeme specification AND its seat in the GRAMMAR tree.

    'shape' is one of 'regex' / 'string' / 'captured' / 'opaque' / 'framing' --
    the discriminant the lexer's pattern extractor and the engine switch on.
    Per shape: 'pattern' for a regex class; 'spelling' for a string/captured
    keyword or a framing token's friendly tag; 'mode' (a span mode, see
    core.span_oracle.SpanMode) for an opaque span. Irrelevant fields are None.
    'silent' is derived from shape (see _SHAPE_SILENT): a string keyword is
    dropped as punctuation, every richer terminal is kept in the parse frame.

    IDENTITY is _name() -- shape plus every distinguishing field -- and the
    object is interned on it (_register_terminal), so the engine compares
    terminals by object identity (one Terminal_Spec per _name()), never by a
    hand-written id. The same object is what the lexer stamps on Token.kind.

    IMMUTABLE AFTER CONSTRUCTION: the fields are set once in __init__ and never
    reassigned, so the object is a safe HASHABLE KEY. __hash__/__eq__ are
    content-based on _name() (which is derived from those frozen-in-practice
    fields), making the value-key contract explicit rather than resting on the
    interning invariant alone; because interning yields exactly one object per
    _name(), content equality and identity coincide. This lets a terminal be a
    key in the role vocabulary (ROLES, ll2_engine).
    """
    __slots__ = ("shape", "pattern", "spelling", "mode", "silent",
                 "_name_str", "_hash")

    def __init__(self, shape, pattern=None, spelling=None, mode=None):
        self.shape    = shape
        self.pattern  = pattern
        self.spelling = spelling
        self.mode     = mode
        self.silent   = _SHAPE_SILENT[shape]
        self._name_str = self._compute_name()
        self._hash     = hash(self._name_str)

    def __hash__(self):
        return self._hash

    def __eq__(self, other):
        return isinstance(other, Terminal_Spec) and self._name_str == other._name_str

    @property
    def is_opaque(self):
        return self.shape == "opaque"

    def __call__(self, role):
        """RETURN: Tagged_Spec, a per-occurrence role-tagged VIEW of this terminal.

        The advisory role-hint call operator (D-10): 't_re_id("event")' tags the
        OCCURRENCE with the plain-string role 'event' for legibility and as a
        pass-2 resolution hint. The view delegates identity, lexing, and LL(2)
        to this terminal unchanged -- the role is NON-IDENTITY, recorded only on
        the wrapper, never entering _name() or the interning that makes one
        keyword one token. A fresh view per call (not interned).
        """
        return Tagged_Spec(self, role)

    def _name(self):
        """RETURN: str, the cached identity string (see _compute_name)."""
        return self._name_str

    def _compute_name(self):
        """RETURN: str, the terminal's identity -- shape plus its fields.

        The distinctness key and the debug-trace id. Two terminals are the same
        iff their _name() is equal; the scheme includes every distinguishing
        field. An opaque span's identity is 'opaque:' + the mode's qualified name
        (oracle sub-language plus role), so core hard-codes no language.
        """
        match self.shape:
            case "regex":    return "regex:" + self.pattern
            case "string":   return "string:" + self.spelling
            case "captured": return "captured:" + self.spelling
            case "opaque":   return "opaque:" + self.mode.qualified_name()
            case "framing":  return "framing:" + self.spelling
            case _:          raise ValueError("unknown terminal shape %r" % (self.shape,))

    def __repr__(self):
        return "Terminal(%s)" % (self._name(),)

    def _compute_first2(self, grammar):
        """RETURN: set[tuple], the length-1 lookahead beginning this terminal.

        An opaque span begins with the span-open framing token; every other
        terminal begins with itself (the interned identity).
        """
        if self.is_opaque:
            return {(t_fr_span_open,)}
        return {(self,)}

    def nullable(self, grammar):
        return False

    def expand(self, parser, frames, work):
        if self.is_opaque:
            frames[-1].add(parser.consume_span(self))
        else:
            value = parser.consume_terminal(self)
            if value is not None:
                frames[-1].add(value)


class TerminalFactory:
    """The terminal factory namespace exposed to grammar.py as 'T'.

    Each method builds a Terminal_Spec and interns it (recording declaration
    order on first sight, reusing on a repeat _name()). The factory only records;
    it mints no token id and generates no scanner -- the conductor extracts the
    lexer's pattern table from TERMINAL_DB, and the lexer compiles that.
    """
    @staticmethod
    def regex(pattern):
        """RETURN: Terminal_Spec, a character-class terminal matching 'pattern'.

        No name argument: the 't_re_...' variable it is bound to carries the
        name, and its line position in the preamble fixes the class precedence
        the extractor emits (earlier line wins).
        """
        return _register_terminal(Terminal_Spec("regex", pattern=pattern))

    @staticmethod
    def string(spelling):
        """RETURN: Terminal_Spec, a silent string keyword spelled as written.

        A plain keyword/symbol ('on:', '=>', '(', ':end'); dropped from the frame
        as punctuation (silent). The factory behind a bare string in GRAMMAR:
        the leaf compiler routes a plain-string leaf here, so every keyword is a
        terminal and rules sharing a spelling share one terminal (reuse).
        """
        return _register_terminal(Terminal_Spec("string", spelling=spelling))

    @staticmethod
    def captured(spelling):
        """RETURN: Terminal_Spec, a keyword kept in the frame for the builder.

        Unlike a silent string keyword, a captured keyword's token is passed to
        the reduce (the OR discriminants ANY / END / BEGIN / VOID / container).
        """
        return _register_terminal(Terminal_Spec("captured", spelling=spelling))

    @staticmethod
    def opaque(mode):
        """RETURN: Terminal_Spec, an opaque span terminal carrying its span mode.

        'mode' is a span mode (core.span_oracle.SpanMode) defined by whatever
        oracle measures the span -- e.g. the Luau layer's Role. It rides on the
        terminal, so a rule expresses "this position takes an opaque span of THIS
        kind" by which 't_opq_...' it names; the engine passes the mode to the
        oracle unread. The mode must expose qualified_name() (the identity) and
        name (diagnostics); any object with those is accepted, keeping core free
        of any one embedded language.
        """
        if not (hasattr(mode, "qualified_name") and hasattr(mode, "name")):
            raise ValueError("opaque terminal needs a span mode "
                             "(qualified_name()/name), got %r" % (mode,))
        return _register_terminal(Terminal_Spec("opaque", mode=mode))

    @staticmethod
    def framing(tag):
        """RETURN: Terminal_Spec, a framing token with no grammar spelling.

        Lexer/engine machinery rather than a written terminal: the opaque-span
        brace handoff (open and the synthesized block), the skip groups, and the
        end-of-file and mismatch sentinels. 'tag' is its friendly name; framing
        tokens reference through the same scheme and differ only in that tag.
        """
        return _register_terminal(Terminal_Spec("framing", spelling=tag))


T = TerminalFactory()


# Framing terminals: lexer/engine machinery with no place in GRAMMAR. Declared
# here because both the authoring side and the engine reference them, and they
# are tokens like any other -- referenced by identity, named by the same scheme
# -- special only in their friendly tags and in being created here, not from a
# rule.
t_fr_span_open  = T.framing("span-open")    # a bare '{'; handed to the oracle
t_fr_span_block = T.framing("span-block")   # the synthesized '{ ... }' span
t_fr_comment    = T.framing("comment")      # '## ...' skip group
t_fr_ws         = T.framing("whitespace")   # whitespace skip group
t_fr_mismatch   = T.framing("mismatch")     # illegal char; parser resyncs
t_fr_eof        = T.framing("end-of-file")  # sentinel returned past the end


class Ref:
    """A reference to another GRAMMAR rule (a non-terminal), authored as R(name).

    Holds the referenced rule's name; the engine interns one Rule_Spec per name
    and binds this reference to it at compile time. Not a terminal: it records
    nothing into TERMINAL_DB.
    """
    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return "R(%r)" % (self.name,)


def R(name):
    """RETURN: Ref, a reference to the GRAMMAR rule called 'name'."""
    return Ref(name)


def terminal_by_name(name):
    """RETURN: Terminal_Spec, the interned terminal whose _name() equals 'name'.

    Reverse of _name(): reconstructs a token's identity from a stored debug name
    (e.g. a monkey-fuzz fixture). Raises KeyError if none is registered.
    """
    return _BY_NAME[name]


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


# ---------------------------------------------------------------------------
# Leaves.  (Terminal_Spec is defined above, in the TERMINALS section: it is both
# the lexeme specification and the grammar-tree leaf, interned by _name().)
# ---------------------------------------------------------------------------
class Rule_Spec(SpecNode):
    __slots__ = ("name", "action", "pattern", "first")

    def __init__(self, name, action):
        self.name    = name
        self.action  = action
        self.pattern = None        
        self.first   = set()       # Now holds tuples of lengths 1 and 2

    def __repr__(self):
        return "PT(%s)" % self.name

    def _compute_first2(self, grammar):
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
    __slots__ = ("branches", "_first2_cache")

    def __init__(self, branches):
        self.branches = tuple(branches)

    def children(self):
        return self.branches


class SEQ_Spec(Branch_Spec):
    __slots__ = ()

    def __repr__(self):
        return "Seq(%s)" % ", ".join(map(repr, self.branches))

    def _compute_first2(self, grammar):
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
        """RETURN: SEQ_Node, over the surviving per-position values of the frame.

        'roles' rides parallel to 'children' (D-18): the advisory role of each
        surviving position, or None, enabling role-keyed access (node["key"])
        that is immune to captured-terminal index drift.
        """
        return SEQ_Node(children=tuple(frame.values),
                        roles=tuple(frame.roles), begin=frame.begin)


class OR_Spec(Branch_Spec):
    __slots__ = ()

    def __repr__(self):
        return "Alt(%s)" % " | ".join(map(repr, self.branches))

    def _compute_first2(self, grammar):
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
            # A tagged branch additionally contributes its role, the string
            # routing address an OrMap may key on (D-19); choose_alt returns the
            # Tagged_Spec itself when the branch is tagged, so its '.role' is
            # read directly here -- no stamp needed (an OR sub-frame holds one
            # value, so the branch role attaches to the OR_Node, not a slot).
            index = self.branches.index(chosen)
            role  = chosen.role if isinstance(chosen, Tagged_Spec) else None
            parser.open_frame(frames)
            work.append((CST_REDUCE, (self, (index, role))))
        work.append((ELEM, chosen))

    def cst_reduce(self, frame, extra):
        """RETURN: OR_Node, the matched branch index, its role, and reduced value.

        'extra' is (index, role): the grammar index of the branch choose_alt
        selected and the advisory role it carried (None if untagged). A branch
        that produced no surviving value (all-silent, or an empty inline branch)
        yields child=ABSENT.
        """
        index, role = extra
        child = frame.values[0] if frame.values else ABSENT
        return OR_Node(triggered_index=index, child=child, role=role,
                       begin=frame.begin)


class Operator_Spec(SpecNode):
    __slots__ = ("body", "_first2_cache")

    def __init__(self, body):
        self.body = body

    def children(self):
        return (self.body,)

    def _compute_first2(self, grammar):
        return self.body.first2_set(grammar)


class OPT_Spec(Operator_Spec):
    __slots__ = ()

    def __repr__(self):
        return "Opt(%r)" % (self.body,)

    def _compute_first2(self, grammar):
        # Includes empty baseline marker to flag structural path choice
        return self.body.first2_set(grammar) | {()}

    def nullable(self, grammar):
        return True

    def expand(self, parser, frames, work):
        present = parser.starts(self.body)
        if parser.cst_mode:
            # Reduce to an OPT_Node: child = the body's value when present,
            # ABSENT else. Presence is a STATE of the node, marked on it, never
            # inferred from a missing frame slot downstream.
            parser.open_frame(frames)
            work.append((CST_REDUCE, (self, present)))
        if present:
            work.append((ELEM, self.body))

    def cst_reduce(self, frame, present):
        """RETURN: OPT_Node, present = whether the optional fired,
                             child   = the body's surviving value, ABSENT else.
        """
        child = frame.values[0] if present and frame.values else ABSENT
        return OPT_Node(present=present, child=child, begin=frame.begin)


class STAR_Spec(Operator_Spec):
    __slots__ = ()

    def __repr__(self):
        return "Star(%r)" % (self.body,)

    def _compute_first2(self, grammar):
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
        return STAR_Node(items=tuple(frame.values), begin=frame.begin)


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
        return PLUS_Node(items=tuple(frame.values), begin=frame.begin)


class Tagged_Spec(Operator_Spec):
    """A role-tagged occurrence of an inner element (D-10): TRANSPARENT.

    Wraps one inner SpecNode (a terminal view or a rule reference) plus an
    advisory 'role' string. It is an Operator_Spec so the FIRST_2 fixpoint and
    the conflict walk descend through it via 'body'/children() exactly as for any
    operator. It adds NOTHING to the value stream: nullable, first2, and expand
    delegate straight to the body, so lexing, the LL(2) analysis, and the CST
    are byte-identical to writing the body bare. The role lives ONLY on this
    wrapper -- non-identity, repr-visible, walkable off the compiled grammar by
    a later layer (the pass-2 resolution hint). Tag terminals and rule
    references (non-nullable leaves); the body's nullability is delegated.
    """
    __slots__ = ("role",)

    def __init__(self, body, role):
        super().__init__(body)
        self.role = role

    def __repr__(self):
        return "%r@%s" % (self.body, self.role)

    def nullable(self, grammar):
        return self.body.nullable(grammar)

    def expand(self, parser, frames, work):
        # Transparent for lexing / FIRST_2 / LL(2): the body expands as if
        # unwrapped. The ONE addition (D-18): schedule a ROLE_STAMP to run AFTER
        # the body so the value the body contributes carries this role into its
        # frame slot, enabling role-keyed child access on the built SEQ_Node.
        # A tagged body is a non-nullable leaf (terminal view or rule reference)
        # that contributes exactly one value to the enclosing frame; 'slot' is
        # that value's index, captured now (the current value count). The stamp
        # is pushed BEFORE the body so it pops LAST (work is LIFO) -- it executes
        # once the value is present. In legacy (non-CST) mode the stamp still
        # runs but the role is never read, costing one frame-slot write.
        target = frames[-1]
        slot   = len(target.values)
        work.append((ROLE_STAMP, (self.role, target, slot)))
        self.body.expand(parser, frames, work)


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


# ---------------------------------------------------------------------------
# Rule shape classification (D-19): the CST node kind a rule produces is fixed
# by its top marker, knowable at load. This drives the AST-map shape gate -- an
# OrMap belongs only on an OR rule, an OptMap only on OPT, etc. It says NOTHING
# about what a factory PRODUCES (branch-dependent, opaque, not knowable here).
# ---------------------------------------------------------------------------
SHAPE_OR       = "OR"
SHAPE_OPT      = "OPT"
SHAPE_SEQ      = "SEQ"
SHAPE_PLUS     = "PLUS"
SHAPE_STAR     = "STAR"
SHAPE_TERMINAL = "TERMINAL"   # bare terminal: a Token, no operator node
SHAPE_FORWARD  = "FORWARD"    # bare reference: forwards the referent's product


def rule_shape(rule):
    """RETURN: str, the SHAPE_* of the CST node 'rule' reduces to.

    Reads the rule's top marker, unwrapping a top-level Tagged_Spec (transparent).
    A bare reference forwards its referent (SHAPE_FORWARD); a bare terminal is a
    Token (SHAPE_TERMINAL); otherwise the operator marker fixes the node kind.
    Used by the AST-map shape gate; never inspects what a factory builds.
    """
    p = rule.pattern
    while isinstance(p, Tagged_Spec):
        p = p.body
    if isinstance(p, OR_Spec):     return SHAPE_OR
    if isinstance(p, OPT_Spec):    return SHAPE_OPT
    if isinstance(p, SEQ_Spec):    return SHAPE_SEQ
    if isinstance(p, PLUS_Spec):   return SHAPE_PLUS
    if isinstance(p, STAR_Spec):   return SHAPE_STAR
    if isinstance(p, Terminal_Spec): return SHAPE_TERMINAL
    if isinstance(p, Rule_Spec):   return SHAPE_FORWARD
    return SHAPE_FORWARD
