"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

RESOLVER  (pass 2, README C / D)

Turns a reference -- a <name-dotted> segment list with an offset -- into the
Symbol it names, against the scope tree (scope_tree.py). Two ideas, kept apart:

HEAD + TWO DESCENT REGIMES (C). The HEAD (first segment) resolves innermost-out
through the open enclosers, after the four PSEUDO-SYMBOLS e / sm / mg / m
(and cw) which resolve FIRST. The resolved head's class then selects the TAIL
descent, and the regimes never unify:

    SCOPE descent   a namespace/aggregate head walks the scope tree.
    TYPE  descent   a variable/struct/pseudo-symbol head walks the params
                    member lists on the Symbol.

A chain switches ONCE, scope -> type; a type segment never reopens scope. A
segment the legal descent cannot seat -- including a type -> scope back-switch
-- is undefined, fatal [NAME].

THE (A)/(B) REFERENCE RULE (D). (A) kinds (event, clock, variable, struct,
cause-def) are STRICT define-before-use. (B) kinds (mode, has-member, arming /
spawn target, is-base) are DECLARE-before-use with bounded-forward definition:
a (B) reference whose target is not yet defined is not an error YET -- it is an
OBLIGATION queued on the scope, and DRAINS at the scope close. An obligation
still unmet at close is fatal [NAME], the diagnostic carrying the obligating
REFERENCE's offset (not the close). A tolerated unknown name in a validation
tool is a false PASS, so the drain is the layer's quietest correctness boundary.

The resolutions this module produces are keyed on node IDENTITY (id(node)), not
on the node as a dict key: AST reference nodes are frozen dataclasses with value
equality, so two textually identical references would collide as keys yet may
resolve to different symbols (README H).
______________________________________________________________________________
"""
from dataclasses import dataclass, field

from vut.engine.temporal_logic.semantic.diagnostics import (
    SemanticClass, semantic_error)
from vut.engine.temporal_logic.semantic.core.scope_types import Scope, Symbol


PSEUDO_SYMBOLS = ("e", "sm", "mg", "m", "cw")

# Kinds whose head walks the scope tree (SCOPE descent) vs the params list
# (TYPE descent). A pseudo-symbol head is always TYPE.
_SCOPE_HEAD_KINDS = {"namespace", "mode-group", "state-machine"}
_TYPE_HEAD_KINDS  = {"variable", "struct"}

# (A)/(B) regime by kind (D). (A): strict define-before-use. (B): bounded
# forward. Kinds not listed (the pseudo-symbols, containers) are resolved
# structurally, not under either ordering rule.
_REGIME_A = {"event", "clock", "variable", "struct", "cause-def"}
_REGIME_B = {"mode", "state", "mode-group", "state-machine"}


@dataclass
class Reference:
    """One reference the resolver is asked to seat: its segments and offset.

    A neutral carrier so the resolver is decoupled from which AST node held the
    name (a Trigger, a BoolRef, an oracle Reference all reduce to this). 'node'
    is the originating AST object, kept ONLY so the resolution map can key on
    its identity (id(node)); it is never used by value.
    """
    segments: "tuple[str, ...]"
    offset:   int
    node:     object = None


@dataclass
class Obligation:
    """A (B) forward reference whose target was not yet defined when seen.

    Held on the scope it must resolve within, and re-checked at the scope
    close. 'reference' carries the offset the diagnostic points at if the
    obligation drains unmet -- the promise's site, not the close.
    """
    reference: Reference
    head:      str


@dataclass
class ResolutionState:
    """The evolving result of resolving one module's references.

    'resolutions' maps id(reference-node) -> Symbol for every seated reference.
    'obligations' maps a Scope (by identity) to the list of (B) forward
    references still owed within it. The drain at a scope close reads and clears
    that scope's list. Keyed on identity throughout: a frozen reference node
    must not collapse with a textual twin (README H).
    """
    resolutions: "dict[int, Symbol]"        = field(default_factory=dict)
    obligations: "dict[int, list]"          = field(default_factory=dict)


# --- head resolution ---------------------------------------------------------

def _resolve_head(head: str, scope: Scope):
    """RETURN: (Symbol, owning-Scope) if 'head' resolves innermost-out from
              'scope' through its open enclosers; (None, None) if no scope on
              the chain declares it.

    Walks parent links from 'scope' to the unit root, returning the first scope
    whose symbols hold 'head'. Pseudo-symbols are handled by the caller before
    this; here 'head' is an ordinary spelling.
    """
    cur = scope
    while cur is not None:
        sym = cur.symbols.get(head)
        if sym is not None:
            return sym, cur
        cur = cur.parent
    return None, None


def _descend(symbol: Symbol, owner: Scope, segments, ref, state, reporter) -> bool:
    """RETURN: True,  if the tail 'segments' (after the head) seats fully under
                     'symbol'; the leaf Symbol is recorded for 'ref'.
              False, if a segment cannot be seated (fatal [NAME] already
                     reported), or a type -> scope back-switch was attempted.

    Implements the one-way scope -> type descent (C). 'symbol' is the resolved
    head and 'owner' the scope it sits in. While in SCOPE regime a segment must
    be a child namespace/aggregate of the current scope; the first time the
    current symbol is a TYPE-bearing kind (variable/struct/pseudo) the descent
    switches to TYPE and from then on each segment is a params member. A
    member-bearing symbol met in SCOPE regime triggers the single switch.
    """
    in_scope_regime = symbol.kind in _SCOPE_HEAD_KINDS
    cur_symbol = symbol
    cur_scope  = owner

    for seg in segments:
        if in_scope_regime:
            # find a child scope of cur_scope named by the aggregate/namespace,
            # then the segment within it.
            child = _child_scope(cur_scope, cur_symbol.name)
            target = child.symbols.get(seg) if child is not None else None
            if target is not None:
                cur_symbol, cur_scope = target, child
                if target.kind not in _SCOPE_HEAD_KINDS:
                    in_scope_regime = False    # one-way switch to TYPE
                continue
            # not a scope child: try switching to TYPE on cur_symbol's params.
            if _seat_member(cur_symbol, seg):
                in_scope_regime = False
                cur_symbol = _member_symbol(cur_symbol, seg)
                continue
            _fail_name(ref, seg, reporter)
            return False
        else:
            # TYPE regime: seg must be a params member; never reopens scope.
            if _seat_member(cur_symbol, seg):
                cur_symbol = _member_symbol(cur_symbol, seg)
                continue
            _fail_name(ref, seg, reporter)
            return False

    state.resolutions[id(ref.node)] = cur_symbol
    return True


def _child_scope(scope: Scope, name: str):
    """RETURN: the child Scope of 'scope' opened under 'name', or None."""
    if scope is None:
        return None
    for ch in scope.children:
        if ch.name == name:
            return ch
    return None


def _seat_member(symbol: Symbol, seg: str) -> bool:
    """RETURN: True if 'seg' is a member spelling in symbol.params, else False."""
    return any(member == seg for member, _type in symbol.params)


def _member_symbol(symbol: Symbol, seg: str) -> Symbol:
    """RETURN: a leaf Symbol for member 'seg' of 'symbol' (kind = its type).

    A member is a (name, type) pair, not a stored Symbol (D-4); this lifts it to
    a Symbol so the descent can continue uniformly and the resolution records a
    typed leaf. The leaf carries no params -- a scalar member ends the chain.
    """
    for member, mtype in symbol.params:
        if member == seg:
            return Symbol(name=seg, kind=mtype, params=(), offset=symbol.offset)
    return Symbol(name=seg, kind="?", params=(), offset=symbol.offset)


def _fail_name(ref: Reference, seg: str, reporter):
    """RETURN: None. Reports an undefined-name [NAME] at the reference offset."""
    reporter.report(semantic_error(
        SemanticClass.NAME, ref.offset,
        "undefined name: '%s' in '%s'" % (seg, ".".join(ref.segments))))


# --- the public resolve-one-reference ----------------------------------------

def resolve_reference(ref: Reference, scope: Scope, state: ResolutionState,
                      reporter) -> bool:
    """RETURN: True,  if 'ref' seats fully now (recorded in state.resolutions).
              False, if it failed [NAME], OR was QUEUED as a (B) obligation on
                     'scope' (a (B) head not yet defined is not an error yet).

    The entry point per reference. A pseudo-symbol head takes TYPE descent on
    its bound symbol (seated by the caller's context; here treated as a present
    head of kind 'pseudo'). An ordinary head resolves innermost-out: found ->
    descend; not found and (B)-eligible -> queue an obligation; not found and
    (A) -> fatal [NAME] now (strict define-before-use).
    """
    head = ref.segments[0]
    tail = ref.segments[1:]

    if head in PSEUDO_SYMBOLS:
        # The pseudo-symbol's bound symbol is supplied by binding context (E);
        # for the resolver core it is a present TYPE head with no scope.
        pseudo = Symbol(name=head, kind="pseudo", params=(), offset=ref.offset)
        if not tail:
            state.resolutions[id(ref.node)] = pseudo
            return True
        # pseudo members are checked by the binding pass (E); here we record the
        # pseudo head and let E validate the tail against the bound symbol.
        state.resolutions[id(ref.node)] = pseudo
        return True

    symbol, owner = _resolve_head(head, scope)
    if symbol is not None:
        return _descend(symbol, owner, tail, ref, state, reporter)

    # head undefined here. (B): queue obligation (bounded forward). (A): fatal.
    if _head_is_B(ref, scope):
        state.obligations.setdefault(id(scope), []).append(
            Obligation(reference=ref, head=head))
        return False
    _fail_name(ref, head, reporter)
    return False


def _head_is_B(ref: Reference, scope: Scope) -> bool:
    """RETURN: True if the reference is eligible for (B) bounded-forward queuing.

    A reference qualifies when nothing in scope yet defines the head AND the
    reference's USE context is a (B) site. The resolver core cannot see the use
    context (that is the caller's), so it conservatively queues a single-segment
    bare head -- the shape a (B) target (mode / aggregate / arming / spawn /
    base) takes -- and lets the drain settle it. A dotted head that missed is a
    hard miss now. (Refined when checks.py supplies the use-site regime.)
    """
    return len(ref.segments) == 1


def resolve_with_chain(ref: Reference, scope: Scope, proxies, state: ResolutionState,
                       loader=None, reporter=None) -> bool:
    """RETURN: True,  if 'ref' seats -- locally, or through a mounted proxy when
                     its head lies under an import's mount prefix (the seating is
                     recorded in state.resolutions for either origin).
              False, if the head is neither local nor a declared name of the
                     proxy whose mount covers it (the caller reports the link
                     error), OR was queued as a (B) obligation.

    The L-design cross-file lookup (disc-4 SETTLED 2 / SETTLED 6): ONE lookup
    mechanism, two hops, NO walk into the imported module. The head is tried
    against the local scope chain first. On a local miss, 'proxies' is scanned
    for one whose mount prefix COVERS the reference's segments; that proxy
    answers from the imported module's real table (loading it first if ABSENT) by
    stripping the mount prefix. A proxy hit seats the leaf for 'ref'; a covered
    head the proxy does not declare is a hard miss the caller turns into a
    missing-export link error. With no covering proxy the behaviour is exactly
    the local resolve_reference.
    """
    head = ref.segments[0]

    symbol, owner = _resolve_head(head, scope)
    if symbol is not None:
        return _descend(symbol, owner, ref.segments[1:], ref, state, reporter)

    proxy = _covering_proxy(ref.segments, proxies)
    if proxy is not None:
        donor = proxy.lookup(ref.segments, loader, reporter)
        if donor is not None:
            state.resolutions[id(ref.node)] = donor
            return True
        return False                       # absent name / absent file (caller reports)

    return resolve_reference(ref, scope, state, reporter)


def _covering_proxy(segments, proxies):
    """RETURN: the ModuleProxy whose mount prefix covers 'segments', or None.

    The routing step: a reference resolves through a proxy only when its leading
    segments match that proxy's mount path. An empty-mount proxy (current-scope
    import) covers any head and is tried last so a prefixed mount wins. 'proxies'
    is an iterable of ModuleProxy; the first non-empty mount that covers wins.
    """
    if not proxies:
        return None
    fallback = None
    for proxy in proxies:
        if not proxy.mount:
            fallback = proxy
            continue
        if proxy.covers(segments):
            return proxy
    return fallback


def drain_scope(scope: Scope, state: ResolutionState, reporter):
    """RETURN: None. At a scope close, re-resolves every (B) obligation owed on
              'scope'; an obligation whose head is now defined seats, one still
              unmet is fatal [NAME] at the REFERENCE's offset (D).

    The (B) drain. By close, the whole scope's symbols are recorded, so a
    bounded-forward reference either finds its now-defined target or is a real
    undefined name -- the moment a false PASS is prevented. Clears the scope's
    obligation list.
    """
    owed = state.obligations.pop(id(scope), [])
    for ob in owed:
        symbol, owner = _resolve_head(ob.head, scope)
        if symbol is not None:
            state.resolutions[id(ob.reference.node)] = symbol
        else:
            reporter.report(semantic_error(
                SemanticClass.NAME, ob.reference.offset,
                "undefined name: '%s' (no definition by scope close)"
                % ob.head))
