"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

RESOLVE / LINK  (pass 2 driver, disc-4 SETTLED 1 -- the LOCAL/GLOBAL split)

Resolution has a LOCAL part and a GLOBAL part; two verbs name two real
transforms (disc-4 SETTLED 1):

  resolve(parsed_module) -> ResolvedModule
        LOCAL: build and seal the module's scope tree, seat its intra-module
        references concretely (local_resolutions, PERMANENT), drain its (B)
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
from .core.module_proxy    import (ModuleProxy, E_Presence)
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

    The producer (disc-4 SETTLED 6): for each Import{filename, mount}, find the
    already-analysed imported module in 'resolved_modules' and wrap its table
    (the sealed ground scope's symbols) under the import's mount prefix. The view
    is a REFERENCE to that table, not a copy -- mounting is addressing. A proxy
    whose imported module is not (yet) in the set is left ABSENT with no table;
    it manifests via the loader at link, or names a missing-library link error.
    """
    proxies = []
    for item in parsed_module.ast.items:
        if not isinstance(item, Import):
            continue
        target = resolved_modules.get(item.filename)
        table  = target.scope_tree.symbols if target is not None else None
        proxies.append(ModuleProxy(
            path     = item.filename,
            mount    = tuple(item.mount),
            presence = E_Presence.PRESENT if table is not None else E_Presence.ABSENT,
            table    = table))
    return tuple(proxies)


def resolve(parsed, oracle, reporter):
    """RETURN: ResolvedModule on success; None when the LOCAL pass gated for
              this module (the reporter then holds the located diagnostics).

    The LOCAL axis (disc-4 SETTLED 1): build and seal this one module's scope
    tree, seat its intra-module references concretely into local_resolutions,
    drain its (B) forward obligations at each scope close, and record its local
    cascade_part (edges only -- cycle detection is a link-time, whole-program
    step). Cross-file references are recorded as relocations, not seated here.
    'parsed' is the ParsedModule; 'oracle' the SpanOracle. Returns None if scope
    build or resolution gated.
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
        scope_tree        = scope,
        relocations       = (),               # cross-file recipes; none yet
        cascade_part      = cascade_part,
        header            = None,
        provenance        = parsed.provenance,
        local_resolutions = state.resolutions)


def link(resolved_modules, root_key, reporter):
    """RETURN: ResolvedProgram on success; None when the GLOBAL pass gated (a
              cascade cycle or a link error; the reporter holds the diagnostics).

    The GLOBAL axis (disc-4 SETTLED 1). 'resolved_modules' maps key ->
    ResolvedModule; 'root_key' names the entry module. Seats relocations eagerly
    (a no-op while the relocation sets are empty), folds every module's
    cascade_part into one whole-program graph, runs cycle detection on the fold
    (the cascade-cycle gate -- a cycle may span modules, so it is found only
    after the fold), fuses the set into the one ResolvedModule the result
    carries, and attaches 'main' iff the root has an entry point. The folded
    cascade is a link product: a relink refolds it, it is not incrementally
    invalidated (stance (a)).
    """
    root = resolved_modules[root_key]

    # --- seat relocations (eager; empty set -> no-op for now) ----------------
    for module in resolved_modules.values():
        for reloc in module.relocations:
            pass                          # STEP 2: seat_relocation over the set

    # --- fold cascade_parts -> one whole-program graph, then scan ------------
    cascade = _fold_cascades(resolved_modules)
    find_cycles(cascade, reporter)
    if reporter.has_fatal():
        return None

    # --- fuse the set into the one resolved module ---------------------------
    fused = ResolvedModule(
        key               = root.key,
        scope_tree        = root.scope_tree,
        relocations       = root.relocations,
        cascade_part      = cascade,
        header            = root.header,
        provenance        = root.provenance,
        local_resolutions = root.local_resolutions)

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


def _resolve_module(module, root_scope, state, reporter, proxies=(), loader=None):
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
    for segments, offset, node in _references(module):
        ref = Reference(segments=tuple(segments), offset=offset, node=node)
        resolve_with_chain(ref, root_scope, proxies, state, loader, reporter)


def _references(node, _seen=None):
    """YIELD: [0] tuple[str, ...]  the reference's dotted segment list
             [1] int              the reference's source offset
             [2] object           the AST node carrying the reference

    A structural walk of the frozen AST yielding REFERENCE sites only. The
    distinction the walk must honour: a declaration's 'name' (a StateMachine,
    Mode, State, EventDef, ... defining occurrence) is NOT a reference and must
    not be resolved; only the reference-bearing node kinds in _REF_SITES carry a
    'name' that points AT a declaration. The walk descends every dataclass field
    and list element (identity-guarded against shared frozen nodes) and yields a
    reference only at a node whose type is a known reference site.
    """
    if _seen is None:
        _seen = set()
    if node is None or id(node) in _seen:
        return
    _seen.add(id(node))

    fields = getattr(node, "__dataclass_fields__", None)
    if fields is not None:
        if type(node).__name__ in _REF_SITES:
            name = getattr(node, "name", None)
            if _is_segment_list(name):
                yield tuple(name), getattr(node, "begin", 0), node
        for fname in fields:
            yield from _references(getattr(node, fname), _seen)
        return

    if isinstance(node, (list, tuple)):
        for elem in node:
            yield from _references(elem, _seen)


# The AST node kinds whose 'name' field is a REFERENCE (points at a declaration),
# as opposed to a DEFINING occurrence. Resolving a declaration's own name would
# be a false undefined-name; only these sites drive resolution. Extended as the
# reference taxonomy is settled (disc-5).
_REF_SITES = {
    "Trigger",        # the triggering event of a cause (ground-scope event)
    "BoolRef",        # a bare boolean reference standing as a condition
    # DEFERRED to disc-5 (scope-context resolution): DefaultRef, CauseRef,
    # EffectRef, Comparison operands, Arg NAME values, ModeArming, Spawn,
    # Unspawn, HasRef. These resolve from their ENCLOSING scope (e.g. a state
    # machine's 'default: crossing.Idle' resolves 'crossing' from the namespace
    # scope, then descends into its child scope), which the current flat
    # ground-scope walk does not track. Adding them needs the scope-context
    # walk settled in disc-5 first.
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
