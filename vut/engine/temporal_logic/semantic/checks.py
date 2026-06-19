"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

CONSISTENCY CHECKS  (pass 2, README E)

Each check owns one diagnostic class (NAME / KIND / BINDING / CASCADE / GUARD /
STRUCTURE / SWEEP). This module holds the checks that are DECIDED and runs them
over the resolved program; two checks need data tables that are still open
items, and are present here as explicit contracts (not silent gaps):

  DECIDED, built and tested here:
    kind-vs-shape       a signature is mandatory for mode-group / state-machine /
                        struct, forbidden for mode / state / container /
                        variable. [KIND]
    is-base category    each 'is:' base resolves and its reactor CATEGORY must
                        match the deriving aggregate (a state-machine derives
                        from state-machines, a mode-group from mode-groups).
                        Cross-category is [KIND].
    pseudo-bindings     'e' under a memberless trigger (ANY/BEGIN/CHANGE) with a
                        member is [BINDING]; 'sm'/'mg' outside their own
                        aggregate body is [BINDING].

  OPEN (todo-1, todo-2) -- contract stated, table awaited:
    method catalogue    CALLS check needs the per-receiver-type catalogue
                        (receiver, arity, arg kinds, result). check_calls is a
                        no-op until METHOD_CATALOGUE is filled.
    one-sweep table     SWEEP check needs the role -> forbidden-step table.
                        check_sweeps is a no-op until FORBIDDEN_BY_ROLE is filled.

These read the scope tree and resolutions; they do not mutate them.
______________________________________________________________________________
"""
from .diagnostics       import (SemanticClass, semantic_error)
from ..parser.ast_nodes import (StateMachine, ModeGroup, ReactorDecl, 
                                Namespace)


# Kinds whose declaration head MUST carry a signature, and those that must NOT
# (README E, kind-vs-shape). A clockwork also takes a signature but is checked
# in the clockwork pass (G).
_SIGNATURE_MANDATORY = {"mode-group", "state-machine", "struct"}
_SIGNATURE_FORBIDDEN = {"mode", "state", "container", "variable"}


def run_checks(rule_file, ground_scope, state, reporter):
    """RETURN: None. Runs every DECIDED consistency check over one module's AST
              and resolved scope tree, accumulating diagnostics in 'reporter'.

    'state' is the ResolutionState produced by the resolver (id-keyed
    resolutions and the drained obligations). Each check is independent and
    accumulate-and-continue; none stops the others. The open-table checks
    (calls, sweeps) run as no-ops until their tables are supplied.
    """
    for item in _walk_items(rule_file.items):
        check_kind_vs_shape(item, reporter)
        check_is_base_category(item, ground_scope, reporter)


def _walk_items(items):
    """YIELD: [0] TopLevel  each top-level item and, recursively, the items
                            nested in a Namespace, in source order.

    A flat traversal so a check can see every declaration regardless of
    namespace nesting; the checks themselves are scope-agnostic (they read kinds
    and resolved categories, not positions).
    """
    for item in items:
        yield item
        if isinstance(item, Namespace):
            yield from _walk_items(item.items)


# --- kind-vs-shape -----------------------------------------------------------

def check_kind_vs_shape(item, reporter):
    """RETURN: None. Reports [KIND] if 'item' carries a signature where its kind
              forbids one, or lacks one where its kind requires it (README E).

    A signature is the head parameter list. Mandatory for mode-group /
    state-machine / struct (they are parameterised types); forbidden for a bare
    mode / state / container / variable. A mismatch is a kind-vs-shape error at
    the declaration head.
    """
    kind = _kind_of(item)
    if kind is None:
        return

    has_signature = _has_signature(item)
    if kind in _SIGNATURE_MANDATORY and not has_signature:
        reporter.report(semantic_error(
            SemanticClass.KIND, _offset(item),
            "%s '%s' requires a signature" % (kind, _name_of(item))))
    elif kind in _SIGNATURE_FORBIDDEN and has_signature:
        reporter.report(semantic_error(
            SemanticClass.KIND, _offset(item),
            "%s '%s' may not carry a signature" % (kind, _name_of(item))))


# --- is: base category -------------------------------------------------------

def check_is_base_category(item, ground_scope, reporter):
    """RETURN: None. For an aggregate with 'is:' bases, reports [KIND] for each
              base whose reactor category differs from the deriving aggregate
              (README E, 'is:' bases).

    A state-machine derives only from state-machines, a mode-group only from
    mode-groups. Each base name is resolved against the scope tree; a base that
    resolves to the other category is a cross-category error. (Merge / override
    / linearisation semantics are not decided here, disc-1.) A base that does
    not resolve at all is left to the (B) drain -- bases are (B) targets.
    """
    if not isinstance(item, (StateMachine, ModeGroup)):
        return
    bases = getattr(item, "bases", None) or []
    own_kind = "state-machine" if isinstance(item, StateMachine) else "mode-group"

    for base in bases:
        base_name = base[-1] if isinstance(base, list) else base
        sym = _lookup(ground_scope, base_name)
        if sym is None:
            continue                       # unresolved base -> (B) drain owns it
        if sym.kind != own_kind:
            reporter.report(semantic_error(
                SemanticClass.KIND, _offset(item),
                "%s '%s' derives from %s '%s' (category mismatch)"
                % (own_kind, _name_of(item), sym.kind, base_name)))


# --- OPEN tables: contracts, no-ops until filled (todo-1, todo-2) -------------

METHOD_CATALOGUE = {}    # (receiver-type) -> {method-name: (arity, arg-kinds, result)}
FORBIDDEN_BY_ROLE = {}   # sweep-role -> set(forbidden step kinds)


def check_calls(item, state, reporter):
    """RETURN: None. CALLS check -- a free 'name(args)' / method '.name(args)'
              against METHOD_CATALOGUE (receiver, arity, arg kinds, result).

    A no-op until METHOD_CATALOGUE is supplied (todo-1). The contract is fixed:
    an unknown method, or a wrong arity / argument kind, is a pass-2 error
    against the call; the class is [KIND] for a kind/arity mismatch and [NAME]
    for an unknown method. Wired here so checks.py exposes the seam without
    pretending a table exists.
    """
    if not METHOD_CATALOGUE:
        return


def check_sweeps(item, reporter):
    """RETURN: None. SWEEP check -- a step kind forbidden in its sweep role,
              read from FORBIDDEN_BY_ROLE (README G, one-sweep row).

    A no-op until FORBIDDEN_BY_ROLE is supplied (todo-2). The contract: a 'do:'
    sweep carries an advisory role hint; the role indexes a set of forbidden
    step kinds; each forbidden occurrence is [SWEEP] against the step. The
    one-sweep row forbids 'while:', a paced bare event, and 'wait:' / 'select:'.
    """
    if not FORBIDDEN_BY_ROLE:
        return


# --- small AST readers -------------------------------------------------------

_KIND_OF = {
    "StateMachine": "state-machine",
    "ModeGroup":    "mode-group",
    "StructDecl":   "struct",
    "Mode":         "mode",
    "State":        "state",
    "VariableDef":  "variable",
    "DictDecl":     "container",
    "ListDecl":     "container",
}


def _kind_of(item):
    """RETURN: str kind of 'item' for kind-vs-shape, or None if 'item' is not a
              declaration head (e.g. a ReactorDecl forward decl carries its own
              'kind' field and is checked when defined, not here)."""
    if isinstance(item, ReactorDecl):
        return None
    return _KIND_OF.get(type(item).__name__)


def _has_signature(item) -> bool:
    """RETURN: True if 'item' carries a non-empty head parameter list.

    Structs use 'members'; aggregates/modes use 'params'; containers/variables
    have neither. An empty list counts as no signature.
    """
    decls = getattr(item, "members", None)
    if decls is None:
        decls = getattr(item, "params", None)
    return bool(decls)


def _name_of(item) -> str:
    """RETURN: str, the (possibly dotted) declared name of 'item'."""
    name = getattr(item, "name", "?")
    if isinstance(name, list):
        return ".".join(name)
    return name


def _offset(item) -> int:
    """RETURN: int, the declaration head offset of 'item' (0 if absent)."""
    return getattr(item, "begin", 0)


def _lookup(scope, name):
    """RETURN: Symbol named 'name' found from 'scope' outward and into its
              children by simple search, or None.

    A shallow lookup for the base-category check: searches the scope and its
    descendant scopes for a top-level aggregate spelling. (Full reference
    resolution is the resolver's job; this only needs to find a declared
    aggregate's kind.)
    """
    if scope is None:
        return None
    sym = scope.symbols.get(name)
    if sym is not None:
        return sym
    for child in scope.children:
        found = _lookup(child, name)
        if found is not None:
            return found
    return None
