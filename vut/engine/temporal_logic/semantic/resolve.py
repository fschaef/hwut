"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

RESOLVE  (pass 2 driver, README THE PIPELINE / I)

The public seam: resolve_program() runs the four stages behind one hard gate
each, and returns a frozen ResolvedProgram on success or None when a stage
gated. The stages, in dependency order:

    1. LOAD     every reachable module PARSED (modules.load_import_closure); an import
                cycle or loader failure gates here.

    2. SCOPE    build each module's scope tree and seal it (scope_tree); the
                graft of mounts onto sealed donors is a scope-stage step.

    3. RESOLVE  seat every reference and drain (B) obligations at scope close
                (resolver); undefined names gate here.

    4. CHECKS   the decided consistency checks (checks) and the cascade graph
                with its cycle detection (cascade); kind/category/cascade errors
                gate here.

A stage that records an error stops the pipeline after reporting; later stages
over broken input are suppressed. Diagnostics accumulate WITHIN a stage. The
result frame is ResolvedProgram (program.py), the emitter's entire input.

This first driver wires the SINGLE-MODULE path end to end (load -> build ->
resolve+drain over the whole tree -> checks -> cascade). Multi-module grafting
(asymmetric mount onto sealed donors) is the next step; the load walk already
produces the module set it will consume.
______________________________________________________________________________
"""
from .modules    import load_import_closure
from .scope_tree import build_scopes
from .resolver   import (ResolutionState, drain_scope)
from .checks     import run_checks
from .cascade    import (build_cascade, find_cycles)
from .program    import ResolvedProgram


def resolve_program(root_source, root_key, oracle, loader, reporter):
    """RETURN: ResolvedProgram on success; None when any stage gated (the
              reporter then holds the located diagnostics).

    Runs the four stages in order, gating between them. 'root_source' is the
    entry text; 'oracle' the SpanOracle (called a second time for opaque-span
    references); 'loader' fetches imported modules; 'reporter' is shared with
    pass 1. An author error is a located diagnostic, never a raise; an
    infrastructure fault (loader down) sets the reporter's fatal flag.
    """
    # --- stage 1: LOAD -------------------------------------------------------
    load_table = load_import_closure(root_source, root_key, oracle, loader, reporter)
    if not load_table.ok:
        return None                       # import cycle or loader failure

    # --- stage 2: SCOPE (build + seal, per module) ---------------------------
    scopes = {}
    for key, parsed in load_table.modules.items():
        scopes[key] = build_scopes(parsed.ast, reporter)
    if reporter.has_fatal():
        return None
    root_scope = scopes[load_table.root_key]

    # --- stage 3: RESOLVE (+ drain (B) obligations) --------------------------
    state = ResolutionState()
    _resolve_module(load_table.modules[load_table.root_key].ast,
                    root_scope, state, reporter)
    _drain_all(root_scope, state, reporter)
    if reporter.has_fatal():
        return None

    # --- stage 4: CHECKS + CASCADE -------------------------------------------
    root_ast = load_table.modules[load_table.root_key].ast
    run_checks(root_ast, root_scope, state, reporter)
    cascade = build_cascade(root_ast, reporter)
    find_cycles(cascade, reporter)
    if reporter.has_fatal():
        return None

    return ResolvedProgram(
        ast         = root_ast,
        scope_tree  = root_scope,
        resolutions = state.resolutions,
        mounts      = {},                 # graft is the next increment
        cascade     = cascade,
        queried     = frozenset(cascade.queried),
        source_map  = None)


def _resolve_module(rule_file, root_scope, state, reporter):
    """RETURN: None. Seats the references of one module against its scope tree.

    The reference walk per module is the resolver's territory; this driver
    invokes it. (The first end-to-end path resolves the references the cascade
    and checks already read by name; the explicit per-node reference walk over
    every guard/effect/operand is the resolver's expansion step, wired here as
    it grows.)
    """
    # The reference-bearing nodes (triggers, effects, operands, guards) are
    # walked by the resolver as its coverage expands. The driver holds the seam;
    # nothing to seat in the current single-module smoke path beyond what the
    # scope build already recorded.
    return None


def _drain_all(scope, state, reporter):
    """RETURN: None. Drains (B) obligations at every scope close, innermost
              first, so a forward reference is settled in the scope that owed it.

    A post-order walk of the scope tree: children drain before their parent, so
    an obligation owed deep in a nest is checked against that scope's completed
    symbols before the enclosing scope closes.
    """
    for child in scope.children:
        _drain_all(child, state, reporter)
    drain_scope(scope, state, reporter)
