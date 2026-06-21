"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

RESOLVE / LINK  (pass 2 driver, disc-4 SETTLED 1 -- the LOCAL/GLOBAL split)

Resolution has a LOCAL part and a GLOBAL part; two verbs name two real
transforms (disc-4 SETTLED 1):

  resolve(parsed_module) -> ResolvedModule
        LOCAL: build and seal the module's scope tree, seat its intra-module
        references concretely (ast_decoration_db, PERMANENT), drain its (B)
        forward obligations, and record its local cascade contribution
        (cascade_part, edges only). Cross-file references are RECORDED AS
        RELOCATIONS, not seated -- that is link's job. A local gate (undefined
        name, kind/shape error) returns None.

  link(resolved_modules, root_key) -> ResolvedProgram
        GLOBAL: seat the relocations (eager loop over seat(); disc-4 SETTLED 3),
        graft mounts onto sealed donors, FOLD every module's cascade_part into
        ONE whole-program graph and run cycle detection on it (a cascade cycle
        may span modules, so it can only be found after the fold), and FUSE the
        module set into the one ResolvedModule the ResolvedProgram carries, with
        'main' iff the root has an entry point. A global gate (cascade cycle,
        link error) returns None.

resolve_program() is the kept public seam: load the import closure, resolve()
each parsed module, link() the set. The single-module path is resolve() of one
module + link() of the singleton set; its relocation set is legitimately empty
(no imports), so the eager seat loop is a no-op for it.

A stage that records an error stops the pipeline after reporting; diagnostics
accumulate WITHIN a stage. The result frame is ResolvedProgram (program.py), the
emitter's entire input.
______________________________________________________________________________
"""
from .modules         import load_import_closure
from .scope_tree      import build_scopes
from .resolver        import (ResolutionState, drain_scope,
                              Reference, resolve_with_chain)
from .checks          import run_checks
from .cascade         import (Cascade, build_cascade, find_cycles)
from .core.resolved_module import ResolvedModule
from .core.module_proxy    import ModuleProxy
from .core.program         import ResolvedProgram

from vut.engine.temporal_logic.parser.ast_nodes import Import


def resolve_program(root_source, root_key, oracle, loader, reporter):
    """RETURN: ResolvedProgram on success; None when any stage gated (the
              reporter then holds the located diagnostics).

    The public seam: load the import closure, resolve() each parsed module
    locally, then link() the set into one ResolvedProgram. 'root_source' is the
    entry text; 'oracle' the SpanOracle (called a second time for opaque-span
    references); 'loader' fetches imported modules; 'reporter' is shared with
    pass 1. An author error is a located diagnostic, never a raise; an
    infrastructure fault (loader down) sets the reporter's fatal flag.
    """
    load_table = load_import_closure(root_source, root_key, oracle, loader, reporter)
    if not load_table.ok:
        return None                       # import cycle or loader failure

    resolved = {}
    for key, parsed in load_table.modules.items():
        module = resolve(parsed, oracle, reporter)
        if module is None:
            return None                   # a local gate in some module
        resolved[key] = module

    return link(resolved, load_table.root_key, reporter)


def proxies_from_imports(parsed_module, resolved_modules):
    """RETURN: tuple of ModuleProxy, one per Import in 'parsed_module', each a
              mounted view of the imported module's real symbol table.

    The producer (disc-4 SETTLED 6 KEPT half): for each Import{filename, mount},
    find the already-analysed imported module in 'resolved_modules' and wrap its
    table (the sealed ground scope's symbols) under the import's mount prefix. The
    view is a REFERENCE to that table, not a copy -- mounting is addressing. Under
    static resolution (D-31) the imported table is present at link; an import with
    no resolved target is a missing-library link error the caller raises (it does
    not produce a half-built proxy).
    """
    proxies = []
    for item in parsed_module.ast.items:
        if not isinstance(item, Import):
            continue
        target = resolved_modules.get(item.filename)
        if target is None:
            continue                          # missing-library: caller reports (STEP 4)
        proxies.append(ModuleProxy(
            path  = item.filename,
            mount = tuple(item.mount),
            table = target.symbol_table.symbols))
    return tuple(proxies)


def resolve(parsed, oracle, reporter):
    """RETURN: ResolvedModule on success; None when the LOCAL pass gated for
              this module (the reporter then holds the located diagnostics).

    The LOCAL axis (disc-4 SETTLED 1): build and seal this one module's scope
    tree, seat its intra-module references concretely into ast_decoration_db,
    drain its (B) forward obligations at each scope close, and record its local
    cascade_part (edges only -- cycle detection is a link-time, whole-program
    step). Cross-file references are seated at LINK against the mounted proxies
    (static -- D-31), not here. 'parsed' is the ParsedModule; 'oracle' the
    SpanOracle. Returns None if scope build or resolution gated.
    """
    # --- SCOPE (build + seal) ------------------------------------------------
    scope = build_scopes(parsed.ast, reporter)
    if reporter.has_fatal():
        return None

    # --- RESOLVE (local reference walk + drain (B) obligations) --------------
    # LOCAL pass: empty proxies -- cross-file seating is link's, once the other
    # modules' tables exist (the deferred finishing pass; see link()).
    state = ResolutionState()
    _resolve_module(parsed.ast, scope, state, reporter, proxies=())
    _drain_all(scope, state, reporter)
    if reporter.has_fatal():
        return None

    # --- CHECKS (decided per-module consistency checks) ----------------------
    run_checks(parsed.ast, scope, state, reporter)
    if reporter.has_fatal():
        return None

    # --- local cascade contribution (edges only; no cycle scan) --------------
    cascade_part = build_cascade(parsed.ast, reporter)
    if reporter.has_fatal():
        return None

    return ResolvedModule(
        key               = parsed.key,
        ast               = parsed.ast,
        symbol_table      = scope,
        cascade_part      = cascade_part,
        header            = None,
        provenance        = parsed.provenance,
        ast_decoration_db = state.resolutions)


def link(resolved_modules, root_key, reporter):
    """RETURN: ResolvedProgram on success; None when the GLOBAL pass gated (a
              cascade cycle or a link error; the reporter holds the diagnostics).

    The GLOBAL axis (disc-4 SETTLED 1). 'resolved_modules' maps key ->
    ResolvedModule; 'root_key' names the entry module. Seats cross-file
    references statically against the mounted proxies (D-31 -- one re-link, no
    incremental machinery), folds every module's cascade_part into one whole-
    program graph, runs cycle detection on the fold (the cascade-cycle gate -- a
    cycle may span modules, so it is found only after the fold), fuses the set
    into the one ResolvedModule the result carries, and attaches 'main' iff the
    root has an entry point. The folded cascade is a link product: a replacement
    re-link refolds it whole, it is not incrementally invalidated.
    """
    root = resolved_modules[root_key]

    # --- cross-file seating against mounted proxies (static; STEP 4) ----------
    # The reference walk seats cross-file heads through proxies_from_imports;
    # link drives it once over the whole set. No relocation recipes, no eager
    # seat loop -- resolution is static and total (D-31).

    # --- fold cascade_parts -> one whole-program graph, then scan ------------
    cascade = _fold_cascades(resolved_modules)
    find_cycles(cascade, reporter)
    if reporter.has_fatal():
        return None

    # --- fuse the set into the one resolved module ---------------------------
    fused = ResolvedModule(
        key               = root.key,
        ast               = root.ast,
        symbol_table      = root.symbol_table,
        cascade_part      = cascade,
        header            = root.header,
        provenance        = root.provenance,
        ast_decoration_db = root.ast_decoration_db)

    return ResolvedProgram(
        module     = fused,
        main       = None,                # entry-point Symbol: STEP 6
        source_map = None)


def _fold_cascades(resolved_modules):
    """RETURN: Cascade, the whole-program graph folded from every module's
              cascade_part (edges, offsets, and queried unioned).

    Set-union over the per-module adjacency dicts -- no AST is re-walked; each
    module's cascade_part was built once at resolve() and is merged here. A
    relink refolds from the same per-module parts (stance (a)).
    """
    whole = Cascade()
    for module in resolved_modules.values():
        part = module.cascade_part
        if part is None:
            continue
        for src, dsts in part.edges.items():
            for dst in sorted(dsts):
                whole.add_edge(src, dst, part.offset_of.get((src, dst), 0))
        whole.queried |= part.queried
    return whole


def _resolve_module(module, root_scope, state, reporter, proxies=()):
    """RETURN: None. Walks the module's reference-bearing nodes and seats each
              reference against the local scope chain, or through a mounted proxy
              when its head lies under an import's mount prefix.

    The reference-walk producer (disc-4 SETTLED 6). A field-driven traversal of
    the frozen AST: every node carrying a 'name' that is a dotted segment list is
    a reference; its (segments, offset, node) drive resolve_with_chain against
    'root_scope' and 'proxies'. The walk is structural (it follows dataclass
    fields and lists), so a node kind not enumerated here still has its
    references found as long as it spells them in a 'name' segment list. Cross-
    file heads route to a covering proxy; everything else resolves locally or
    queues a (B) obligation.
    """
    for segments, offset, node, scope in _references(module, root_scope):
        ref = Reference(segments=tuple(segments), offset=offset, node=node,
                        scope=scope)
        resolve_with_chain(ref, scope, proxies, state, reporter)


def _references(node, scope, _seen=None):
    """YIELD: [0] tuple[str, ...]  the reference's dotted segment list
             [1] int              the reference's source offset
             [2] object           the AST node carrying the reference
             [3] Scope            the reference's ENCLOSING scope

    The REFERENCE-table fill (RATIONALE D-32). One descent of the frozen AST,
    carrying the enclosing scope as it goes: when the walk enters a scope-opening
    node (Namespace / StateMachine / ModeGroup) it switches to that node's child
    scope (matched by dotted name), so every reference is yielded WITH the scope
    it must resolve from -- enclosing_scope is a COLUMN filled here, not a later
    lookup (disc-5 FINDING 2 dissolved). A reference vs a declaration is WHICH
    rows a node emits: only _REF_SITES node kinds carry a 'name' that points AT a
    declaration and yield a row; a declaration's own 'name' yields none (FINDING
    1). The walk is identity-guarded against shared frozen nodes and descends
    every dataclass field and list element.
    """
    if _seen is None:
        _seen = set()
    if node is None or id(node) in _seen:
        return
    _seen.add(id(node))

    fields = getattr(node, "__dataclass_fields__", None)
    if fields is not None:
        child = _opened_child_scope(node, scope)
        inner = child if child is not None else scope
        if type(node).__name__ in _REF_SITES:
            name = getattr(node, "name", None)
            if _is_segment_list(name):
                yield tuple(name), getattr(node, "begin", 0), node, scope
        for fname in fields:
            yield from _references(getattr(node, fname), inner, _seen)
        return

    if isinstance(node, (list, tuple)):
        for elem in node:
            yield from _references(elem, scope, _seen)


def _opened_child_scope(node, scope):
    """RETURN: the child Scope 'node' opened under 'scope' (matched by dotted
              name), or None if 'node' opens no scope.

    The lockstep step (D-32): a scope-opening AST node -- Namespace, StateMachine,
    ModeGroup -- has a matching child in the scope tree built from the same AST.
    Match it by the dotted name build_scopes named the scope with, so the walk
    descends the AST and the scope tree together. A node that opens no scope (or
    whose child is not found) leaves the enclosing scope unchanged.
    """
    if type(node).__name__ not in _SCOPE_OPENER_NODES or scope is None:
        return None
    name = getattr(node, "name", None)
    dotted = ".".join(name) if _is_segment_list(name) else name
    for ch in scope.children:
        if ch.name == dotted:
            return ch
    return None


# AST node kinds that OPEN a child scope (matched to scope_tree's _open_scope_for).
# Application vocabulary -- it names rule aggregates -- and so lives here in the
# semantic (filler) layer, not in core.
_SCOPE_OPENER_NODES = {"Namespace", "StateMachine", "ModeGroup"}


# The AST node kinds whose 'name' field is a REFERENCE (points at a declaration),
# as opposed to a DEFINING occurrence. Resolving a declaration's own name would
# be a false undefined-name; only these sites drive resolution. Widened site by
# site (S3); each addition is proven by a flip in the reference-report dump.
# The enclosing scope now rides on every reference (D-32), so a site that
# resolves from a non-ground scope (e.g. DefaultRef inside a state machine) is
# unblocked -- the gate below is the only thing holding a site back.
_REF_SITES = {
    "Trigger",        # the triggering event of a cause (ground-scope event)
    "BoolRef",        # a bare boolean reference standing as a condition
    # NOT YET ADMITTED (widened one at a time under the dump's safety net):
    #   DefaultRef, CauseRef, EffectRef, ModeArming, Spawn, Unspawn, HasRef
    #     -- plain 'name' segment lists; resolve from enclosing lexical scope.
    #   Spawn.into_container / Spawn.key  -- extra segment-list fields on Spawn.
    #   Comparison.left/right, Arg(NAME).value
    #     -- the EVENT-MEMBER axis (TYPE-descent against the firing event's
    #        members), NOT enclosing lexical scope; handled separately.
}

# Every AST node kind that COULD carry a reference, for the observation dump
# (reference_report). Independent of _REF_SITES so the dump's row set is STABLE:
# widening _REF_SITES flips a row from UNSEATED to a seated symbol, it does not
# add or remove rows. The plain-'name' lexical-scope sites only.
_CANDIDATE_REF_SITES = {
    "Trigger", "BoolRef", "DefaultRef", "CauseRef", "EffectRef",
    "ModeArming", "Spawn", "Unspawn", "HasRef",
}


def _is_segment_list(value) -> bool:
    """RETURN: True if 'value' is a non-empty list/tuple of strings (a dotted
              reference's segment list), else False.

    The segment-list shape test. A reference's 'name' is list[str]; a bare
    string name (a keyword argument name, a filename) is NOT a segment list and
    must not be mistaken for a reference.
    """
    if not isinstance(value, (list, tuple)) or not value:
        return False
    return all(isinstance(seg, str) for seg in value)


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


# --- observation: the reference-resolution report (S3 safety net) ------------

def reference_report(module, root_scope, state):
    """YIELD: [0] str    the reference's dotted segments, '.'-joined
             [1] str    the enclosing scope's kind name (GROUND / NAMESPACE /
                        STATE_MACHINE / MODE_GROUP)
             [2] str    the seated Symbol's name and kind, or 'UNSEATED' if no
                        resolution exists for the node

    The S3 observation net. Walks EVERY candidate reference site
    (_CANDIDATE_REF_SITES -- a fixed taxonomy, independent of _REF_SITES) in
    source order, carrying the enclosing scope exactly as the resolver walk does,
    and reports whether each one seated in 'state'. The row SET is stable: a site
    not yet admitted to _REF_SITES shows UNSEATED; admitting it flips that one row
    to its seated symbol, a single reviewable diff. This is what makes each S3
    widening provable rather than blind (B-first discipline).
    """
    for segments, _offset, node, scope in _candidate_references(module, root_scope):
        sym = state.resolutions.get(id(node))
        if sym is None:
            seated = "UNSEATED"
        else:
            seated = "%s:%s" % (sym.name, sym.kind)
        yield ".".join(segments), scope.kind.name, seated


def _candidate_references(node, scope, _seen=None):
    """YIELD: the same 4-tuple as _references, but gated on _CANDIDATE_REF_SITES
             (every site that COULD carry a reference) rather than _REF_SITES
             (those admitted so far).

    The dump's walk. Identical scope-carrying descent to _references; only the
    gate differs, so the dump sees every candidate site with its true enclosing
    scope whether or not the resolver currently seats it.
    """
    if _seen is None:
        _seen = set()
    if node is None or id(node) in _seen:
        return
    _seen.add(id(node))

    fields = getattr(node, "__dataclass_fields__", None)
    if fields is not None:
        child = _opened_child_scope(node, scope)
        inner = child if child is not None else scope
        if type(node).__name__ in _CANDIDATE_REF_SITES:
            name = getattr(node, "name", None)
            if _is_segment_list(name):
                yield tuple(name), getattr(node, "begin", 0), node, scope
        for fname in fields:
            yield from _candidate_references(getattr(node, fname), inner, _seen)
        return

    if isinstance(node, (list, tuple)):
        for elem in node:
            yield from _candidate_references(elem, scope, _seen)
