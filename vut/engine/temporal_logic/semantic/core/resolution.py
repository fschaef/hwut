"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

RESOLUTION  (semantic/core -- GENERAL mechanism; RATIONALE D-32)

The JOIN half of the three-table model. Given the tables an application FILLS --
SCOPE (Scope), SYMBOL (Symbol), REFERENCE (Reference) -- this module resolves
each reference to the symbol it names: an innermost-out scope search for the
head, then a one-way SCOPE->TYPE descent for the dotted tail, with a mounted
proxy consulted when the head lies under an import's mount prefix.

This module knows NOTHING about the rule language. The two rule-flavoured facts
the descent needs -- which symbol kinds OPEN a scope (so a dotted segment is a
child scope, not a type member), and which heads are PSEUDO-symbols (bound by
context, not by any scope) -- arrive as an injected ResolutionPolicy (frozen
kind-sets the application builds). core is the schema + query engine; the
application (semantic/) is the ETL that loads the tables and supplies the policy.

The (A)/(B) regime decision (define-before-use vs bounded-forward) is NOT here --
it is application policy and lives in semantic/resolver.py, which calls this join.
______________________________________________________________________________
"""
from dataclasses import dataclass, field

from vut.engine.temporal_logic.semantic.diagnostics import (
    SemanticClass, semantic_error)
from vut.engine.temporal_logic.semantic.core.scope_types import Scope, Symbol


@dataclass(frozen=True)
class ResolutionPolicy:
    """The rule-flavoured facts the GENERAL join needs, injected by the app.

    'scope_head_kinds' is the set of Symbol.kind strings whose head descends by
    SCOPE (a dotted segment names a child scope) rather than by TYPE (a params
    member). 'pseudo_symbols' is the set of head spellings bound by context
    (e.g. a firing event's 'e'), present without sitting in any scope. Frozen
    sets so the policy is a value; the application builds one from its kinds.
    """
    scope_head_kinds: frozenset = frozenset()
    pseudo_symbols:   frozenset = frozenset()


@dataclass
class Reference:
    """One reference the join is asked to seat: its segments and offset.

    A neutral carrier so the join is decoupled from which AST node held the name
    (a Trigger, a BoolRef, an oracle Reference all reduce to this). 'node' is the
    originating AST object, kept ONLY so the resolution map can key on its
    identity (id(node)); it is never used by value. 'scope' is the reference's
    ENCLOSING scope -- the REFERENCE-table column the application fills at emit
    time (D-32); the head search starts here and walks outward.
    """
    segments: "tuple[str, ...]"
    offset:   int
    node:     object = None
    scope:    "Scope | None" = None


@dataclass
class Obligation:
    """A (B) forward reference whose target was not yet defined when seen.

    Held on the scope it must resolve within, and re-checked at the scope close.
    'reference' carries the offset a diagnostic points at if the obligation
    drains unmet -- the promise's site, not the close.
    """
    reference: Reference
    head:      str


@dataclass
class ResolutionState:
    """The evolving result of resolving one module's references.

    'resolutions' maps id(reference-node) -> Symbol for every seated reference.
    'obligations' maps a Scope (by identity) to the list of (B) forward
    references still owed within it; the application's drain reads and clears
    that list at a scope close. Keyed on identity throughout: a frozen reference
    node must not collapse with a textual twin (README H).
    """
    resolutions: "dict[int, Symbol]" = field(default_factory=dict)
    obligations: "dict[int, list]"   = field(default_factory=dict)


# --- head resolution ---------------------------------------------------------

def resolve_head(head: str, scope: Scope):
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


def descend(symbol, owner, segments, ref, state, policy, reporter) -> bool:
    """RETURN: True,  if the tail 'segments' (after the head) seats fully under
                     'symbol'; the leaf Symbol is recorded for 'ref'.
              False, if a segment cannot be seated (fatal [NAME] reported).

    The one-way SCOPE->TYPE descent (README C). 'symbol' is the resolved head,
    'owner' the scope it sits in. While in SCOPE regime a segment must name a
    child scope of the current scope; the first time the current symbol's kind is
    NOT in policy.scope_head_kinds the descent switches to TYPE, and from then on
    each segment is a params member. The switch is one-way (no type->scope).
    """
    in_scope_regime = symbol.kind in policy.scope_head_kinds
    cur_symbol = symbol
    cur_scope  = owner

    for seg in segments:
        if in_scope_regime:
            child  = _child_scope(cur_scope, cur_symbol.name)
            target = child.symbols.get(seg) if child is not None else None
            if target is not None:
                cur_symbol, cur_scope = target, child
                if target.kind not in policy.scope_head_kinds:
                    in_scope_regime = False    # one-way switch to TYPE
                continue
            if _seat_member(cur_symbol, seg):
                in_scope_regime = False
                cur_symbol = _member_symbol(cur_symbol, seg)
                continue
            _fail_name(ref, seg, reporter)
            return False
        else:
            if _seat_member(cur_symbol, seg):
                cur_symbol = _member_symbol(cur_symbol, seg)
                continue
            _fail_name(ref, seg, reporter)
            return False

    state.resolutions[id(ref.node)] = cur_symbol
    return True


def _child_scope(scope, name: str):
    """RETURN: the child Scope of 'scope' opened under 'name', or None."""
    if scope is None:
        return None
    for ch in scope.children:
        if ch.name == name:
            return ch
    return None


def _seat_member(symbol, seg: str) -> bool:
    """RETURN: True if 'seg' is a member spelling in symbol.params, else False."""
    return any(member == seg for member, _type in symbol.params)


def _member_symbol(symbol, seg: str):
    """RETURN: a leaf Symbol for member 'seg' of 'symbol' (kind = its type).

    A member is a (name, type) pair, not a stored Symbol; this lifts it to a
    Symbol so the descent continues uniformly and the resolution records a typed
    leaf. The leaf carries no params -- a scalar member ends the chain.
    """
    for member, mtype in symbol.params:
        if member == seg:
            return Symbol(name=seg, kind=mtype, params=(), offset=symbol.offset)
    return Symbol(name=seg, kind="?", params=(), offset=symbol.offset)


def _fail_name(ref, seg: str, reporter):
    """RETURN: None. Reports an undefined-name [NAME] at the reference offset."""
    reporter.report(semantic_error(
        SemanticClass.NAME, ref.offset,
        "undefined name: '%s' in '%s'" % (seg, ".".join(ref.segments))))


# --- the chaining lookup (local hop + cross-file proxy hop) -------------------

def resolve_with_chain(ref, scope, proxies, state, policy, reporter,
                       on_local_miss=None) -> bool:
    """RETURN: True,  if 'ref' seats -- locally, or through a mounted proxy when
                     its head lies under an import's mount prefix.
              False, if the head is neither local nor a declared name of the
                     proxy whose mount covers it, OR 'on_local_miss' handled it
                     (e.g. queued a (B) obligation) and returned False.

    The L-design cross-file lookup: ONE mechanism, two hops, NO walk into the
    imported module. The head is tried against the local scope chain first; a hit
    descends (policy-driven). On a local miss, 'proxies' is scanned for one whose
    mount prefix COVERS the segments; that proxy answers from the imported
    module's real table (always present -- static, D-31) by stripping the prefix.
    A covered head the proxy does not declare is a hard miss the caller turns into
    a missing-export link error. With no covering proxy and an 'on_local_miss'
    callback supplied, the miss is handed to the application (its (A)/(B) regime
    decision); with none supplied the miss is a plain False.
    """
    head = ref.segments[0]

    if head in policy.pseudo_symbols:
        # a pseudo head is present without a scope; its tail is validated by the
        # binding pass (E). Record the pseudo leaf and return.
        pseudo = Symbol(name=head, kind="pseudo", params=(), offset=ref.offset)
        state.resolutions[id(ref.node)] = pseudo
        return True

    symbol, owner = resolve_head(head, scope)
    if symbol is not None:
        return descend(symbol, owner, ref.segments[1:], ref, state, policy, reporter)

    proxy = _covering_proxy(ref.segments, proxies)
    if proxy is not None:
        donor = proxy.lookup(ref.segments)
        if donor is not None:
            state.resolutions[id(ref.node)] = donor
            return True
        return False                       # absent name (caller reports missing-export)

    if on_local_miss is not None:
        return on_local_miss(ref, scope, state)
    return False


def _covering_proxy(segments, proxies):
    """RETURN: the ModuleProxy whose mount prefix covers 'segments', or None.

    The routing step: a reference resolves through a proxy only when its leading
    segments match that proxy's mount path. An empty-mount proxy (current-scope
    import) covers any head and is tried last so a prefixed mount wins.
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
