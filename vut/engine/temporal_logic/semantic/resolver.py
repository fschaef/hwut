"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

RESOLVER  (pass 2, README C / D -- APPLICATION POLICY; RATIONALE D-32)

The VUT-specific half of resolution. The GENERAL join -- innermost-out head
search, the SCOPE->TYPE tail descent, the cross-file proxy hop -- lives in
semantic/core/resolution.py and knows no rule kinds. This module supplies what
makes the join speak VUT:

  THE POLICY (core/resolution.ResolutionPolicy). Which Symbol kinds OPEN a scope
  (SCOPE descent) vs carry TYPE members, and which heads are PSEUDO-symbols
  (e / sm / mg / m / cw, bound by context). Built once here from the rule kinds
  and handed to the core join.

  THE (A)/(B) REFERENCE RULE (D). (A) kinds (event, clock, variable, struct,
  cause-def) are STRICT define-before-use: an undefined head is fatal [NAME] now.
  (B) kinds (mode, state, aggregate, arming/spawn target, base) are DECLARE-
  before-use with bounded-forward definition: an undefined (B) head is not an
  error YET -- it is an OBLIGATION queued on the scope, DRAINED at the scope
  close (drain_scope). An obligation unmet at close is fatal [NAME] at the
  obligating reference's offset. This decision is the application's; it rides
  into the core join as the on_local_miss callback.

Resolutions are keyed on node IDENTITY (id(node)), not on the node by value: AST
reference nodes are frozen dataclasses with value equality, so two textually
identical references would collide as keys yet may resolve to different symbols
(README H). The carrier types (Reference, ResolutionState, Obligation) and the
chaining lookup are re-exported from core/resolution for callers.
______________________________________________________________________________
"""
from vut.engine.temporal_logic.semantic.diagnostics import (
    SemanticClass, semantic_error)
from vut.engine.temporal_logic.semantic.core.scope_types import Scope, Symbol
from vut.engine.temporal_logic.semantic.core.resolution import (
    ResolutionPolicy, Reference, Obligation, ResolutionState,
    resolve_head, resolve_with_chain as _core_resolve_with_chain)


# --- the VUT resolution vocabulary (the rule-kind facts the core join needs) --

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

# The policy value handed to the general join: the rule-flavoured facts the
# descent needs, with no behaviour. Built once, reused.
POLICY = ResolutionPolicy(
    scope_head_kinds = frozenset(_SCOPE_HEAD_KINDS),
    pseudo_symbols   = frozenset(PSEUDO_SYMBOLS))


# --- the chaining lookup, with the VUT (A)/(B) miss policy bound in ----------

def resolve_with_chain(ref, scope, proxies, state, reporter) -> bool:
    """RETURN: True,  if 'ref' seats locally or through a mounted proxy.
              False, if it failed [NAME], was a covered-but-absent proxy name,
                     or was QUEUED as a (B) obligation (not an error yet).

    The application entry point: the general core join with the VUT (A)/(B)
    regime decision bound in as the local-miss handler. A head found locally or
    via a proxy seats in core; a pure local miss (no covering proxy) is handed to
    _queue_or_fail, which queues a bounded-forward (B) head as an obligation or
    fails an (A) head now.
    """
    return _core_resolve_with_chain(
        ref, scope, proxies, state, POLICY, reporter,
        on_local_miss=_bind_miss(reporter))


def resolve_reference(ref, scope, state, reporter) -> bool:
    """RETURN: True,  if 'ref' seats fully now (recorded in state.resolutions).
              False, if it failed [NAME], OR was QUEUED as a (B) obligation.

    The proxy-free form (no imports in play): the chaining lookup with an empty
    proxy set. Kept as the spine many callers and tests use directly.
    """
    return resolve_with_chain(ref, scope, (), state, reporter)


def _bind_miss(reporter):
    """RETURN: an on_local_miss callback closing over 'reporter'.

    The core join's on_local_miss signature is (ref, scope, state) -> bool; the
    VUT (A)/(B) policy also needs the reporter to locate an (A) failure. This
    closure carries it without threading a reporter argument through core. A
    bounded-forward (B)-eligible head (a bare single segment -- the shape a mode/
    aggregate/arming/spawn/base target takes) is queued as an Obligation on the
    scope, settled at the scope close by drain_scope; any other miss is a hard
    undefined name now (strict (A) define-before-use). The core join has already
    tried local + proxy before calling this.
    """
    def handler(ref, scope, state):
        head = ref.segments[0]
        if _head_is_B(ref, scope):
            state.obligations.setdefault(id(scope), []).append(
                Obligation(reference=ref, head=head))
            return False
        reporter.report(semantic_error(
            SemanticClass.NAME, ref.offset,
            "undefined name: '%s' in '%s'" % (head, ".".join(ref.segments))))
        return False
    return handler


def _head_is_B(ref, scope) -> bool:
    """RETURN: True if the reference is eligible for (B) bounded-forward queuing.

    A reference qualifies when nothing in scope yet defines the head AND its use
    context is a (B) site. The use context is the caller's (checks.py); here the
    conservative shape is honoured -- a single bare segment, the form a (B) target
    (mode / aggregate / arming / spawn / base) takes -- and the drain settles it.
    A dotted head that missed is a hard miss now.
    """
    return len(ref.segments) == 1


def drain_scope(scope, state, reporter):
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
        symbol, owner = resolve_head(ob.head, scope)
        if symbol is not None:
            state.resolutions[id(ob.reference.node)] = symbol
        else:
            reporter.report(semantic_error(
                SemanticClass.NAME, ob.reference.offset,
                "undefined name: '%s' (no definition by scope close)"
                % ob.head))
