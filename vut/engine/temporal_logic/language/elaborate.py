"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

ELABORATE -- the third transition of the module spine:

    DeclaredModule --elaborate--> SemanticModule

STEP 0, MOUNT (F-1, SEMANTICS 12). Every recorded import is mounted: the peer
DeclaredModule's export_db -- the DECLARED surface: existence, kind,
abstractness, member names with default flags, never a body -- is read into
this module's symbol table under the import alias. A peer the caller did not
supply is a REJECT: declaration-first ordering says the full declared surface
exists before any module elaborates, so a missing peer is a build fault.

STEP 1, RESOLVE. Every ReferenceLeaf receives ONE recipe -- an Access seated
into its '_access' slot (written once, via resolve()). ACCESS IS KNOWN,
ALWAYS (the spine contract): the resolution law, first hit wins:

    (1) BINDING HEAD, {e, b, a, c, s} (LANGUAGE 4.1). Every level has a
        DEFAULT INSTANCE in the currently open scope, so a binding NEVER
        rejects on position: the recipe records the binding and its member
        residue; WHICH concrete instance is link's business.
    (2) LOCAL FRAMES, innermost outward: signature parameters, has: members,
        nested definitions, loop/comprehension variables (SEMANTICS 6),
        spawn handles (SEMANTICS 11).
    (3) THE TABLE, scope-aware outward (SEMANTICS 12): from the writing scope
        toward top level, LONGEST declared prefix wins; segments beyond the
        match become the RESIDUE. Residue is VERIFIED as far as the declared
        surface reaches: its FIRST segment into a definition-kind or cause
        target must name a declared member (parameter or has: name), local
        and mounted alike; deeper residue and residue under a binding travel
        to link (SEMANTICS 19).
    (4) RAW EVENT -- only at a CAUSE TARGET or an EMISSION TARGET (an
        effect's spawn): a name resolving to nothing there
        IS a raw event (R-1), recipe kind 'event', no diagnostic.
        ANYWHERE ELSE a name resolving to nothing is a REJECT (SEMANTICS 19):
        every reference resolves or rejects.

SETTLED CHECKS carried by the same walk (one descent, one context):
    SEMANTICS  2   a guarded USE of a named cause -> REJECT (GUARD)
    SEMANTICS  5   a lifecycle cause takes no guard -> REJECT (GUARD)
    SEMANTICS  7   exit-labels outermost-only (7b); dropto forward-only with
                   existence (7c) -> REJECT (STRUCTURE)
    SEMANTICS  9   the LVALUE LAW (pass-4 half): a mutation lvalue is a
                   binding-qualified member with head in {e, b, a, c};
                   's.' is read-only; a non-binding lvalue head -> REJECT
    SEMANTICS 17   an effect/emit target resolving to an ABSTRACT definition
                   draws the WARN remark -- uniformly, local and mounted
                   (abstractness rides the export)
    SEMANTICS 19   unresolved reference / unknown first-level member
    SEMANTICS 21   a DIVISION whose denominator is not provably nonzero (a
                   nonzero constant, optionally negated) requires the
                   'else:' fault handler; the handler surface is PENDING --
                   until it lands, such a division REJECTS outright.
    SEMANTICS 20   the PYTHON ARGUMENT LAW (D-11): a PARENTHESISED use of a
                   resolved parameterised target supplies every parameter
                   without a default, exactly once, positionals before named,
                   no unknown names; a BARE use is a reference, not a call --
                   no argument judgement.

GATE LAW. Contract violated by SOFTWARE (a driver calling this unit on a
dirty reporter -- the F-6 discipline is the driver's) -> ABORT by raising.
Fault in PARSED CONTENT -> error diagnostic through the reporter, walk
continues (collect and continue). Diagnostics: phase SEMANTIC; tags NAME
(mount/19/20), GUARD (2/5/17), STRUCTURE (7/9); REJECT = fatal True,
WARN (17) = fatal False.
______________________________________________________________________________
"""
import dataclasses
from dataclasses import dataclass

from ..core.diagnostic import DiagnosticReporter, Diagnostic, Phase
from ..core.symbol.ast import NodeList, ReferenceLeaf
from ..core.parser_generator.cst_nodes import NodeAbsent
from .module_states import DeclaredModule, SemanticModule
from . import ast_nodes as A


BINDINGS         = ("e", "")    # reactor ruling: 'e.' the event payload,
                                # '' the bare-dot SELF ('.x') -- the
                                # reactor/class instance; b/a/c/s died with
                                # the kinds they named
WRITABLE_HEADS   = ("e", "")
SURFACE_KINDS    = ("character", "aspect", "behavior", "cause")


@dataclass(frozen=True)
class Access:
    """RETURN: Access, one reference's RECIPE: where the written name landed.

    'kind'    what the matched head IS: a declared kind ('character',
              'aspect', 'behavior', 'cause', 'declaration', 'import',
              'namespace'), 'binding' (an e/b/a/c/s head, LANGUAGE 4.1),
              'local' (a parameter, member, loop variable, spawn handle, or
              nested definition), or 'event' (a raw event at a cause or
              emission target -- the R-1 case, a KNOWN access).
    'target'  the fully-qualified segments of the matched head: the table key
              for declared names, the binding letter for bindings, the
              local's own name for locals, the written segments for events.
    'residue' the written segments BEYOND the matched head -- member
              navigation; its first level is verified against the declared
              surface where one exists, the rest is link's; () when the whole
              name matched.
    'origin'  the import path the target was mounted from; None for names of
              this module (including bindings, locals, and events).
    """
    kind:    str
    target:  tuple
    residue: tuple = ()
    origin:  "str|None" = None


class SymbolTable:
    """RETURN: never a value itself -- this module's resolution surface: its
              own export entries plus every mounted peer's, keyed by
              fully-qualified segments, each carrying the ExportEntry and the
              import path it arrived through (None for own names).

    What SemanticModule.symbol_table holds. Deterministic to iterate (sorted
    keys). LOCAL frames are walk-time state, deliberately NOT stored: they
    exist only inside their construct and have no life at the surface.
    """

    def __init__(self):
        self._entries = {}

    def enter(self, qualified, entry, origin=None):
        """RETURN: None, always. Records 'qualified' (a segment tuple) with
                  its ExportEntry and origin; an existing key is left
                  untouched (first wins -- collisions were declare's to
                  reject, and a mount never shadows an own name).
        """
        key = tuple(qualified)
        if key not in self._entries:
            self._entries[key] = (entry, origin)

    def longest_match(self, segments):
        """RETURN: (tuple, ExportEntry, str|None), the LONGEST prefix of
                  'segments' that is a recorded key, with its entry and
                  origin, if any prefix is recorded.
                  None, else.
        """
        for cut in range(len(segments), 0, -1):
            hit = self._entries.get(tuple(segments[:cut]))
            if hit is not None:
                return tuple(segments[:cut]), hit[0], hit[1]
        return None

    def entry_of(self, qualified):
        """RETURN: ExportEntry, the entry recorded under exactly 'qualified',
                  if present.
                  None, else -- the checks' lookup for a recipe's target.
        """
        hit = self._entries.get(tuple(qualified))
        return hit[0] if hit is not None else None

    def __iter__(self):
        """RETURN: iterator, over (qualified, (ExportEntry, origin)) pairs in
                  sorted key order -- deterministic for printing and diffing.
        """
        return iter(sorted(self._entries.items()))

    def __len__(self):
        """RETURN: int, the number of recorded names."""
        return len(self._entries)



def _bare_name(side):
    """RETURN: str, the single-segment name a plain operand speaks, if it
              is one (a bare reference or a step-less, argument-less data
              access). None, else.
    """
    leaf = side.name if isinstance(side, A.DataAccess) \
           and side.args is NodeAbsent and not side.steps else \
           side if isinstance(side, ReferenceLeaf) else None
    if leaf is not None and len(leaf.segments) == 1:
        return leaf.segments[0]
    return None


def _is_zeroish(node):
    """RETURN: True, if 'node' is one of the ABSENCE spellings a gate may
              compare against -- the Nothing literal or the literal 0
              (EQUIVALENCE ruling: 'm != Nothing', 'm != 0', and bare 'm'
              are one gate; Nothing is the absent value, zero its numeric
              face). False, else.
    """
    if isinstance(node, A.NothingLeaf):
        return True
    from ..core.symbol.ast import ConstantLeaf
    return isinstance(node, ConstantLeaf) \
           and str(node.kind) in ("int", "float") \
           and float(node.text) == 0.0


def _nothing_gate(cond):
    """RETURN: (name, op), when 'cond' is a recognized Nothing-gate of
              SEMANTICS 28 (EQUIVALENCE ruling): '<name> != Nothing',
              '<name> != 0', and bare '<name>' all yield (name, '!=');
              '<name> == Nothing' and '<name> == 0' yield (name, '==');
              operand order free.
              None, else.
    """
    bare = _bare_name(cond)
    if bare is not None:
        return bare, "!="                    # bare truthiness IS the gate
    if not isinstance(cond, A.BinOp) or cond.op not in ("==", "!="):
        return None
    lhs, rhs = cond.lhs, cond.rhs
    if _is_zeroish(rhs):
        side = lhs
    elif _is_zeroish(lhs):
        side = rhs
    else:
        return None
    name = _bare_name(side)
    return (name, cond.op) if name is not None else None


def _diverges(block):
    """RETURN: bool, True exactly when the block's LAST statement leaves
              the body (exit: or give:) -- the divergence the initial-gate
              narrowing of SEMANTICS 28 requires (conservative: deeper
              divergence shapes defer).
    """
    stmts = tuple(block.statements)
    return bool(stmts) and isinstance(stmts[-1], (A.ExitSignal, A.Give))


def _is_semi(work):
    """RETURN: bool, True exactly when 'work' is a SEMI-DECLARATION (D-27):
              no body AND an entirely empty panel -- the brief class-body
              listing whose complete definition must follow (SEMANTICS 25).
    """
    p = work.panel
    return work.body is NodeAbsent and not (p.ins or p.outs or p.signals)


def _first_begin(node):
    """RETURN: int, the smallest source offset of any leaf under 'node',
              if one exists. None, else.

    Generic dataclass descent; a leaf is anything carrying 'begin'.
    """
    best = None
    stack = [node]
    while stack:
        n = stack.pop()
        b = getattr(n, "begin", None)
        if isinstance(b, int):
            best = b if best is None else min(best, b)
        if dataclasses.is_dataclass(n):
            stack.extend(getattr(n, f.name) for f in dataclasses.fields(n))
        elif isinstance(n, (tuple, list)):
            stack.extend(n)
    return best


def _collect(nodes, kinds):
    """YIELD: [0] Node  every node of the given kinds, found by a full
                       structural descent through dataclass fields, tuples,
                       and NodeLists starting at 'nodes'.

    Purely structural: no scoping, no order guarantees beyond depth-first.
    Used for whole-body laws (LANGUAGE 12.4 emission coverage, 13.3 tick
    hosting) that ordinary scoped walking would have to thread manually.
    """
    import dataclasses as _dc
    seen = set()
    stack = list(nodes)
    while stack:
        node = stack.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        if isinstance(node, kinds):
            yield node
        if _dc.is_dataclass(node):
            for f in _dc.fields(node):
                stack.append(getattr(node, f.name))
        elif isinstance(node, (tuple, list)):
            stack.extend(node)


def elaborate_module(declared: DeclaredModule, peers: dict,
                     reporter: DiagnosticReporter) -> SemanticModule:
    """RETURN: SemanticModule, the given module with every ReferenceLeaf
              carrying its Access recipe and the symbol_table filled -- the
              serialisation boundary of the front half.
              Raises ValueError if 'reporter' already carries any diagnostic:
              the F-6 discipline is the DRIVER'S contract, so a dirty entry
              is a SOFTWARE fault and aborts; every fault in the PARSED
              CONTENT is reported through 'reporter' instead and never
              interrupts the walk.

    'peers' maps an import PATH (the unquoted string as written) to that
    peer's DeclaredModule; the caller's worklist owns loading order
    (declaration-first law). Mounting reads each peer's export_db under the
    import alias -- the declared surface, never a body.
    """
    if reporter.errors:
        raise ValueError(
            "gate: %d diagnostic(s) block elaborate -- elaborate only ever "
            "starts from a clean declare (driver contract, F-6 discipline)"
            % len(reporter.errors))
    table = SymbolTable()
    for qualified, entry in declared.export_db:
        table.enter(qualified, entry, origin=None)
    _mount_imports(declared, peers, table, reporter)
    _Walk(table, reporter).module(declared.file_node)
    return SemanticModule(origin=declared.origin,
                          file_node=declared.file_node,
                          export_db=declared.export_db,
                          symbol_table=table)


def _mount_imports(declared, peers, table, reporter):
    """RETURN: None, always. Step 0 (F-1): reads every imported peer's
              export_db into 'table' under the import alias; a peer the
              caller did not supply is rejected (declaration-first: a missing
              peer is a build fault in the CONTENT-facing sense -- the source
              names a unit the build cannot provide).
    """
    for item in declared.file_node.items:
        if not isinstance(item, A.Import):
            continue
        path = item.path.text.strip('"')
        alias = tuple(item.alias.segments)
        peer = peers.get(path)
        if peer is None:
            _reject(reporter, item.alias.begin, "NAME",
                    "import %r cannot be mounted: no declared peer supplied "
                    "for this path (declaration-first, SEMANTICS 12)" % path)
            continue
        for qualified, entry in peer.export_db:
            table.enter(alias + tuple(qualified), entry, origin=path)


class _Walk:
    _work_depth = 0        # >0 while inside a work/clockwork body (SEM 23)
    _known = set()         # the body's known names (SEM 28, R-41): the
                           # 'known:'-marked in: entries and marked sites
                           # -- may be Nothing
    _narrowed = set()      # knowns proven not-Nothing at this walk point
    _dead = set()          # names destructed on this path (SEM 30, R-40)
    _given = set()         # names given away on this path (ruling: the
                           # haver holds Nothing in the given thing's
                           # place -- every access rejects)

    def _init_completion_state(self):
        self._semi = {}         # class -> {member: semi-Work}   (D-27)
        self._completed = {}    # class -> {member}
        self._overloads = {}    # (class, ext) -> [Work]         (R-32)
        self._work_defs = {}    # segments -> Work|ClockworkDef (agreement)
    _handled = False       # True inside a handler-carrying statement (12.9)
    """RETURN: never a value itself -- the one tree walk of this pass: scope
              and local-frame state, recipe seating, and every settled check
              (unit header) in a single descent, so no construct is visited
              twice and no check sees a different context than resolution
              did.
    """

    def __init__(self, table, reporter):
        self.table    = table
        self.reporter = reporter
        self.scope    = ()          # namespace path of the writing site
        self.frames   = []          # local frames, innermost LAST
        # -- pipe model (pipe ruling; SEMANTICS 31) -------------------------
        self._reactor_defs = {}     # qualified -> Reactor node (wire checks)
        self._reactor_ins  = None   # in-channel names, reactor under walk
        self._reactor_outs = None   # out-channel names, reactor under walk
        self._local_pipe   = {}     # work-body local -> (kind, qualified):
                                    # kind 'reactor'/'reactor++'/'feeder' --
                                    # the PARTIAL visibility for wire-end
                                    # checks (same-body constructions only)

    # -- module and definitions ----------------------------------------------

    def module(self, root):
        """RETURN: None, always. Walks every top-level item under the top
                  scope; afterwards the SEMANTICS-25 second direction: every
                  semi-declared member work must have been completed by a
                  '+class.ext' definition.
        """
        self._init_completion_state()
        self._scan_reactors(root.items, ())
        for item in root.items:        # pre-scan: the agreement law (ruled:
            match item:                # known/had are part of the TYPE)
                case A.Work() | A.ClockworkDef():   # needs the callee's
                    segs = tuple(item.signature.name.segments)   # panel
                    if len(segs) == 1 and not _is_semi(item) \
                            and segs not in self._work_defs:
                        self._work_defs[segs] = item
                case _:
                    pass
        for item in root.items:
            self.item(item)
        for key in sorted(self._overloads):
            self._overload_disjoint(key, self._overloads[key])
        for cname in sorted(self._semi):
            done = self._completed.get(cname, set())
            for member in sorted(set(self._semi[cname]) - done):
                self._reject_at(
                    self._semi[cname][member].signature.name.begin, "WORK",
                    "member work '%s.%s' is semi-declared but never "
                    "completed by '+%s.%s : work(...)' (SEMANTICS 25)"
                    % (cname, member, cname, member))

    def _scan_reactors(self, items, scope):
        """RETURN: None, always. Records every Reactor node under its
                  qualified name, recursing through namespaces -- the
                  channel-surface ground truth for the wire-end checks
                  (pipe ruling, SEMANTICS 31; the surface is read from the
                  AST because the export table publishes names, not
                  channels).
        """
        for item in items:
            if isinstance(item, A.Namespace):
                self._scan_reactors(item.items,
                                    scope + tuple(item.name.segments))
            elif isinstance(item, A.Reactor):
                key = scope + tuple(item.signature.name.segments)
                self._reactor_defs[key] = item

    def item(self, item):
        """RETURN: None, always. Dispatches one top-level (or namespaced)
                  item; causalities walk directly, definitions open their
                  frame, namespaces extend the scope.
        """
        match item:
            case A.Namespace():
                saved = self.scope
                self.scope = saved + tuple(item.name.segments)
                for inner in item.items:
                    self.item(inner)
                self.scope = saved
            case A.Import():
                pass                        # mounted in step 0; alias declared
            case A.Causality():
                self.causality(item)
            case A.DefCause():
                with self._frame(self._params_of(item.signature)):
                    self.cause(item.cause)
            case A.Reactor():
                self.reactor(item)
            case A.Declaration():
                self.type_of(item.type_)
            case A.ClassDef():
                self.class_def(item)
            case A.Work() if len(item.signature.name.segments) == 2:
                kind = "dtor" if item.signature.name.segments[1] == "-" \
                       else "ctor"
                self.completion(item, kind)
            case A.Work() | A.ClockworkDef():
                self.work_def(item)
            case _:
                pass

    def handler_arms(self, handler):
        """RETURN: None, always. Walks a handler's arm actions (LANGUAGE
                  12.6): block actions walk as nested statements; exit:
                  actions are collected by the surrounding work walk;
                  exhaustiveness over the callee's signal set is deferred
                  (SEMANTICS 24, PARTIAL).
        """
        for arm in handler.arms:
            if isinstance(arm.action, (A.ExitSignal,)) \
                    or arm.action is NodeAbsent:
                continue
            self.block(arm.action, outermost=False)

    def class_def(self, node):
        """RETURN: None, always. Walks one class (LANGUAGE 11, R-41.3): is:
                  targets seat; member-declaration types walk (the marker is
                  the relation, having implicit); FULL member works walk in
                  the members' frame; SEMI-DECLARATIONS (D-27: no panel, no
                  body) are recorded for the completion law (SEMANTICS 25)
                  and walk nothing (SEMANTICS 23 -- PARTIAL: custody checks
                  await the type document).
        """
        for call in node.is_:
            self.seat(call.name)
        frame = {}
        for member in node.members:
            self.type_of(member.type_)
            frame[member.name.segments[0]] = "member"
        cname = node.signature.name.segments[0]
        with self._frame(frame):
            for work in node.works:
                if _is_semi(work):
                    self._semi.setdefault(cname, {})[
                        work.signature.name.segments[0]] = work
                    continue
                self.work_def(work)

    def completion(self, node, kind):
        """RETURN: None, always. One '+class.ext' / '-class' completion
                  (D-27, SEMANTICS 25): the class must exist; a '+' must
                  complete a SEMI-DECLARED member and its panel must GIVE
                  the class; a '-' needs no semi-declaration, at most one
                  per class, and its panel must TAKE the class; the body
                  walks as an ordinary work. Marker/panel agreement is
                  checked over TYPED entries only (untyped defer, PARTIAL).
        """
        cname, member = node.signature.name.segments
        def _exact(key):
            hit = self.table.longest_match(key)
            return hit is not None and hit[0] == key
        if not _exact(tuple(self.scope) + (cname,)) and not _exact((cname,)):
            self._reject_at(node.signature.name.begin, "WORK",
                            "completion names class %r -- no such class "
                            "(SEMANTICS 25)" % cname)
        if kind == "ctor":
            self._overloads.setdefault((cname, member), []).append(node)
            semi = self._semi.get(cname, {})
            if member in semi:
                self._completed.setdefault(cname, set()).add(member)
            else:
                self._reject_at(node.signature.name.begin, "WORK",
                                "'+%s.%s' completes no semi-declared member "
                                "work of %r (SEMANTICS 25)"
                                % (cname, member, cname))
            self._agree(node, cname, section=node.panel.outs,
                        verb="out:", marker="+")
        else:
            # at most one '-class': held by declare's duplicate law already
            # (the qualified name (class, '-') collides) -- no second check.
            if node.panel.signals and not node.explicit:
                self._reject_at(
                    node.signature.name.begin, "WORK",
                    "'-%s' declares signals without the explicit flag -- "
                    "AUTOMATIC DESTRUCTION CANNOT FAIL (LANGUAGE 11.4, "
                    "R-36/R-37): only '-%s()' may signal, because every "
                    "destruction of an explicit class is written "
                    "(destruct) and every signal answered" % (cname, cname))
            self._agree(node, cname, section=node.panel.ins,
                        verb="in:", marker="-")
        self.work_def(node)

    def _overload_disjoint(self, key, overloads):
        """RETURN: None, always. The SEMANTICS-26 overload law (R-33):
                  overloads of one '+class.ext' identify BY ARGUMENT NAME --
                  their FIRST input entries carry pairwise DISTINCT names (a
                  first-input-less overload cannot be identified: rejected);
                  the call-site half lives in _check_overloaded_call.
        """
        if len(overloads) < 2:
            return                       # a single completion needs no
                                         # identification -- not an overload
        seen = {}
        for work in overloads:
            entries = tuple(work.panel.ins)
            if not entries:
                self._reject_at(
                    work.signature.name.begin, "WORK",
                    "constructor overload of '+%s.%s' has no input -- an "
                    "overload identifies by its FIRST argument's name "
                    "(SEMANTICS 26)" % key)
                continue
            first = entries[0].name.segments[0]
            if first in seen:
                self._reject_at(
                    work.signature.name.begin, "WORK",
                    "constructor overloads of '+%s.%s' share the first "
                    "input name %r -- overloads identify by at least the "
                    "first argument (SEMANTICS 26)"
                    % (key[0], key[1], first))
            seen[first] = work

    def _check_overloaded_call(self, rhs):
        """RETURN: None, always. The call-site half of SEMANTICS 26 (R-33):
                  a call of an OVERLOADED extension leads with a NAMED
                  argument -- the SELECTOR -- whose name is one overload's
                  first input; non-overloaded calls pass untouched.
        """
        segs = getattr(getattr(rhs, "name", None), "segments", None)
        if not segs or len(segs) != 2:
            return
        overloads = self._overloads.get(tuple(segs))
        if not overloads or len(overloads) < 2:
            return
        args = () if rhs.args is NodeAbsent else tuple(rhs.args)
        firsts = set()
        for w in overloads:
            entries = tuple(w.panel.ins)
            if entries:
                firsts.add(entries[0].name.segments[0])
        if not args or not isinstance(args[0], A.NamedArg):
            self._reject_at(
                rhs.name.begin, "WORK",
                "call of overloaded '%s.%s' must lead with a NAMED "
                "argument selecting the overload (one of: %s) "
                "(SEMANTICS 26)"
                % (segs[0], segs[1], ", ".join(sorted(firsts))))
            return
        selector = args[0].name
        if selector not in firsts:
            self._reject_at(
                rhs.name.begin, "WORK",
                "%r selects no overload of '%s.%s' (first-input names: %s) "
                "(SEMANTICS 26)"
                % (selector, segs[0], segs[1], ", ".join(sorted(firsts))))

    def _agree(self, node, cname, section, verb, marker):
        """RETURN: None, always. The marker/panel agreement of SEMANTICS 25
                  over the flat panel (R-41.1): among the section's TYPED
                  CUSTODY entries (unmarked or 'had:' -- a 'known:' entry is
                  a view, never the constructed product nor the received
                  debt) one must name the class; a section with only untyped
                  entries defers (PARTIAL); a typed section without the
                  class REJECTS.
        """
        typed = [e for e in section
                 if e.type_ is not NodeAbsent and e.marker != "known"]
        if not typed:
            return                          # untyped: deferred (PARTIAL)
        for entry in typed:
            t = entry.type_
            name = getattr(getattr(t, "name", None), "segments", None) \
                   or getattr(t, "segments", None)
            if name and name[0] == cname:
                return
        self._reject_at(node.signature.name.begin, "WORK",
                        "'%s%s' marker demands an %s custody entry of "
                        "type %r (SEMANTICS 25, role by panel R-30/R-41.1)"
                        % (marker, cname, verb, cname))

    def work_def(self, node):
        """RETURN: None, always. Walks one work or clockwork (LANGUAGE 12/13;
                  SEMANTICS 23, PARTIAL): panel entry types walk; the body --
                  absent for a spec -- walks with all panel port names in
                  frame; every variant-carrying exit: must name a declared
                  signal variant and every declared variant must be emitted
                  by some exit: (12.4, both directions); tick: is lawful only
                  in a clockwork with an out: section; give: is UNLAWFUL in a
                  clockwork and, in a work, its port list must name the
                  panel's out: ports (R-41.4, SEMANTICS 23).
        """
        panel = node.panel
        frame = {}
        for entry in (tuple(panel.ins) + tuple(panel.outs)):
            frame[entry.name.segments[0]] = "port"
        declared = {sig.name.segments[0] for sig in panel.signals}
        if node.body is NodeAbsent:
            return                                # a SPEC: panel only
        emitted = set()
        self._work_depth += 1
        self._local_pipe = {}       # pipe ruling: wire-end visibility is
                                    # per-body (same-body constructions)
        # SEM 28 is ALWAYS ACTIVE and FLOW-SENSITIVE (ruling, R-41
        # follow-up): the checker complains only about UNGATED access to a
        # known -- where the flow makes Nothing impossible (a dominating
        # gate narrowed the name), the access is fine. No mention-gating,
        # no activation switch. The known inputs are the 'known:'-marked
        # in: entries (R-41.1); marked sites join (R-41.2).
        self._known = {e.name.segments[0] for e in panel.ins
                       if e.marker == "known"}
        self._narrowed = set()
        self._dead = set()
        self._given = set()
        try:
            with self._frame(frame):
                labels = [st.label.segments[0] for st in node.body
                          if isinstance(st, A.ExitLabel)
                          and st.region is NodeAbsent]   # B-1: bare only
                seen = 0
                reachable = True
                for statement in node.body:
                    if isinstance(statement, A.ExitLabel):
                        reachable = True     # a label: flow may land here
                        if statement.region is NodeAbsent:
                            seen += 1
                    elif not reachable:
                        # ruling: give is the LAST statement on its path --
                        # unreachable code is an error.
                        self._reject_at(
                            _first_begin(statement) or 0, "STRUCTURE",
                            "unreachable statement -- the path above "
                            "already left through give/exit/dropto; "
                            "unreachable code is an error (ruling)")
                        reachable = True     # report ONCE per dead run
                    if isinstance(statement,
                                  (A.Give, A.ExitSignal, A.DropTo)):
                        reachable = False
                    self.work_statement(statement, node, declared, emitted,
                                        exits=labels[seen:])
                for found in _collect(node.body,
                                      (A.ExitSignal, A.Tick, A.Give)):
                    if isinstance(found, A.ExitSignal):
                        self.check_exit(found, node, declared, emitted)
                    elif isinstance(found, A.Tick):
                        self.check_tick(found, node)
                    else:
                        self.check_give(found, node)
        finally:
            self._work_depth -= 1
            self._local_pipe = {}
            self._known = set()
            self._narrowed = set()
            self._dead = set()
            self._given = set()
        for name in sorted(declared - emitted):
            self.reporter.report(Diagnostic(
                phase=Phase.SEMANTIC,
                message="signal '%s' is declared but no reachable exit "
                        "emits it (LANGUAGE 12.4)" % name,
                source_offset=node.signature.name.begin,
                fatal=True, tag="WORK"))

    def work_statement(self, statement, node, declared, emitted, exits=()):
        """RETURN: None, always. Walks one work-body statement: exit:
                  verified against the declared signal set; tick: verified
                  against the out: section; plain statements walk as
                  ordinary code (nested blocks descend through the same
                  check).
        """
        match statement:
            case A.ExitSignal() | A.Give() | A.Tick():
                pass                          # checked by the collection
            case A.Destruct():
                self.statement(statement, exits=exits)   # the general
                                              # walker owns SEM 27/30
            case _:
                self.statement(statement, exits=exits)

    def check_exit(self, statement, node, declared, emitted):
        """RETURN: None, always. One exit: against the declared signal set
                  (LANGUAGE 12.4, first direction); a declared emission is
                  recorded for the second direction. A BARE exit: (R-41.7,
                  the nothing-more egress) names no variant and passes --
                  its lawfulness in WORKS rides a flagged fork, so no check
                  is invented here.
        """
        if statement.variant is NodeAbsent:
            return                               # bare: the built-in egress
        name = statement.variant.segments[0]
        if name not in declared:
            self.reporter.report(Diagnostic(
                phase=Phase.SEMANTIC,
                message="exit names '%s' -- not a declared signal of this "
                        "%s (LANGUAGE 12.4)"
                        % (name, "clockwork" if isinstance(
                            node, A.ClockworkDef) else "work"),
                source_offset=statement.variant.begin,
                fatal=True, tag="WORK"))
        else:
            emitted.add(name)

    def check_tick(self, statement, node):
        """RETURN: None, always. One tick: against its host (LANGUAGE 13.3,
                  R-41.1): lawful only in a clockwork with an out: section
                  (the per-tick outputs -- the retired ticks: rides out:).
        """
        if not (isinstance(node, A.ClockworkDef) and node.panel.outs):
            self.reporter.report(Diagnostic(
                phase=Phase.SEMANTIC,
                message="tick is lawful only in a clockwork with an "
                        "out: section (LANGUAGE 13.3)",
                source_offset=0,
                fatal=True, tag="WORK"))

    def check_give(self, statement, node):
        """RETURN: None, always. One give: against its host (R-41.4,
                  SEMANTICS 23): UNLAWFUL in a clockwork (a clockwork
                  delivers with tick: and ends only through exit:); in a
                  work the port list must name the panel's out: ports --
                  each exactly once, none foreign, none missing (name and
                  arity; the out-bundle leaves in declaration order, 12.5).
        """
        if isinstance(node, A.ClockworkDef):
            self._reject_at(
                node.signature.name.begin, "WORK",
                "give is unlawful in a clockwork -- it delivers with "
                "tick and ends only through exit (LANGUAGE 13.3, "
                "R-41.4)")
            return
        declared = [e.name.segments[0] for e in node.panel.outs]
        written  = [p.segments[0] for p in statement.ports]
        anchor = statement.ports[0].begin if written \
                 else node.signature.name.begin
        for name in written:
            if name not in declared:
                self._reject_at(
                    anchor, "WORK",
                    "give names %r -- not an out: port of this work "
                    "(LANGUAGE 12.4, R-41.4)" % name)
        seen = set()
        for name in written:
            if name in seen:
                self._reject_at(
                    anchor, "WORK",
                    "give names out: port %r twice (LANGUAGE 12.4, "
                    "R-41.4)" % name)
            seen.add(name)
        for name in declared:
            if name not in seen:
                self._reject_at(
                    anchor, "WORK",
                    "give leaves out: port %r unnamed -- the list names "
                    "the panel's out: ports, name and arity (LANGUAGE "
                    "12.4, R-41.4; SEMANTICS 23)" % name)
        # ORDER LAW (ruled): one order everywhere -- the written list
        # MIRRORS the panel's declaration order exactly; anything else
        # would leave two orders in the program text.
        if sorted(written) == sorted(declared) and written != declared:
            self._reject_at(
                anchor, "WORK",
                "give writes the out: ports out of order (%s) -- the list "
                "mirrors the panel's declaration order (%s); one order "
                "everywhere (LANGUAGE 12.4, order ruling)"
                % (", ".join(written), ", ".join(declared)))

    def reactor(self, node):
        """RETURN: None, always. Walks one reactor (reactor + pipe rulings):
                  'is:' targets are required references with argument
                  checking (SEMANTICS 19, 20); member declaration types walk;
                  the BEHAVIOR NAMES open the frame (activation targets --
                  'A => Name'); member works walk as works (their self is
                  this reactor through the bare-dot binding); each behavior
                  is ONLY causalities -- grouped by in-channel or bare --
                  walked in the reactor's frame. The reactor's members are
                  reached exclusively through '.x' -- bare member names are
                  NOT in frame. PIPE LAWS (SEMANTICS 31): a group's channel
                  stands in the panel's in: ('.' is the self channel,
                  always lawful); ungrouped causalities beside SEVERAL
                  in-channels are unlawful (messy interfering namespaces);
                  a routed emission's 'to' target stands in out: (checked
                  in effect(), the channel context opened here).
        """
        for call in node.is_:
            access = self.seat(call.name)
            self.check_arguments(access, call.args, call.name.begin)
        for decl in node.members:
            self.type_of(decl.type_)
        ins  = {c.segments[0] for c in node.ins}
        outs = {c.segments[0] for c in node.outs}
        frame = {b.signature.name.segments[0]: "behavior"
                 for b in node.behaviors}
        self._reactor_ins, self._reactor_outs = ins, outs
        try:
            with self._frame(frame):
                for work in node.works:
                    self.item(work)
                for behavior in node.behaviors:
                    for group in behavior.groups:
                        if group.channel != "." \
                                and group.channel not in ins:
                            self._reject_at(
                                group.begin, "PIPE",
                                "channel group %r names no in: channel of "
                                "this reactor (in: %s) (SEMANTICS 31)"
                                % (group.channel,
                                   ", ".join(sorted(ins)) or "-"))
                        for causality in group.causalities:
                            self.causality(causality)
                    if tuple(behavior.causalities) and len(ins) > 1:
                        self._reject_at(
                            _first_begin(tuple(behavior.causalities)[0])
                            or node.signature.name.begin, "PIPE",
                            "ungrouped causalities beside several in: "
                            "channels (%s): with more than one in-channel "
                            "every causality states its channel group "
                            "(SEMANTICS 31)" % ", ".join(sorted(ins)))
                    for causality in behavior.causalities:
                        self.causality(causality)
        finally:
            self._reactor_ins, self._reactor_outs = None, None

    def _params_of(self, signature):
        """RETURN: dict, one local frame holding the signature's parameter
                  names (kind 'local') -- empty when unparameterised; a D-11
                  default expression walks here (it reads the surrounding
                  scope, not the frame being built).
        """
        frame = {}
        if signature.params is not NodeAbsent:
            for arg in signature.params:
                frame[arg.name.segments[0]] = "local"
                if arg.type_ is not NodeAbsent:
                    self.type_of(arg.type_)
                if arg.default is not NodeAbsent:
                    self.expr(arg.default)
        return frame

    # -- causality --------------------------------------------------------------

    def causality(self, node):
        """RETURN: None, always. Walks one causality: the cause, then every
                  effect of the chain.
        """
        self.cause(node.cause)
        for effect in node.effects:
            self.effect(effect)

    def cause(self, node):
        """RETURN: None, always. Seats the cause target's recipe (raw event
                  legitimate here) and applies the guard laws: a lifecycle
                  takes no guard (SEMANTICS 5); a guarded USE of a named
                  cause is a second guard (SEMANTICS 2). Arguments check
                  against a resolved target (SEMANTICS 20); the guard
                  expression walks.
        """
        guarded = node.guard is not NodeAbsent
        if isinstance(node.target, A.Lifecycle):
            if guarded:
                self._reject_at(0, "GUARD",
                                "a lifecycle cause (%s) takes no guard "
                                "(SEMANTICS 5)" % node.target.kind)
        else:
            access = self.seat(node.target, event_ok=True)
            if guarded and access.kind == "cause" and not access.residue:
                self._reject_at(node.target.begin, "GUARD",
                                "a use of named cause %r supplies arguments, "
                                "not a second guard (SEMANTICS 2)"
                                % ".".join(node.target.segments))
            self.check_arguments(access, node.args, node.target.begin)
        if node.args is not NodeAbsent:
            self._args(node.args)
        if guarded:
            self.expr(node.guard)

    def effect(self, node):
        """RETURN: None, always. Walks one effect: a spawn seats its emission
                  target; a routed spawn's 'to' channel must stand in the
                  enclosing reactor's out: panel (pipe ruling, SEMANTICS
                  31); a command block walks as an outermost body.
        """
        if isinstance(node.action, A.Spawn):
            spawn = node.action
            self.emission_target(spawn.call)
            if spawn.to_channel is not NodeAbsent:
                channel = spawn.to_channel.segments[0]
                spawn.to_channel.resolve(Access(kind="channel",
                                                target=(channel,)))
                if self._reactor_outs is not None \
                        and channel not in self._reactor_outs:
                    self._reject_at(
                        spawn.to_channel.begin, "PIPE",
                        "'to %s' names no out: channel of this reactor "
                        "(out: %s) (SEMANTICS 31)"
                        % (channel,
                           ", ".join(sorted(self._reactor_outs)) or "-"))
            if spawn.every is not NodeAbsent:
                self.expr(spawn.every)
            if spawn.handle is not NodeAbsent:
                self._top_frame()[spawn.handle.segments[0]] = "local"
        else:
            self.block(node.action, outermost=True)

    def emission_target(self, call):
        """RETURN: Access, the recipe seated on an emission target (an
                  effect's spawn): a raw event is
                  legitimate; a target resolving to an ABSTRACT definition --
                  local or mounted, the flag rides the export -- draws the
                  SEMANTICS-17 WARN remark; arguments check against a
                  resolved surface (SEMANTICS 20).
        """
        access = self.seat(call.name, event_ok=True)
        entry = self.table.entry_of(access.target)
        if entry is not None and entry.abstract and not access.residue:
            self.reporter.report(Diagnostic(
                phase=Phase.SEMANTIC,
                message="effect targets ABSTRACT entity %r (SEMANTICS 17: "
                        "well-formed; every occurrence must be visible)"
                        % ".".join(access.target),
                source_offset=call.name.begin,
                fatal=False,
                tag="GUARD"))
        self.check_arguments(access, call.args, call.name.begin)
        self._args(call.args)
        return access

    # -- command block (SEMANTICS 7 and 9 live here) --------------------------------

    def block(self, node, outermost, exits=None):
        """RETURN: None, always. Walks one command block. At the OUTERMOST
                  body the exit-label order list is built first, so 'dropto:'
                  checks forward-only existence (SEMANTICS 7c); in any nested
                  block an exit-label definition is rejected outright
                  (SEMANTICS 7b) and droptos check against the outer list.
        """
        if outermost:
            exits = [s.label.segments[0] for s in node.statements
                     if isinstance(s, A.ExitLabel)
                     and s.region is NodeAbsent]    # B-1: only the DEAD
                                                    # ADDRESS account is a
                                                    # dropto: target
        seen = 0
        reachable = True
        for statement in node.statements:
            if isinstance(statement, A.ExitLabel):
                reachable = True             # a label is a jump target:
                                             # flow may land here
            elif not reachable:
                # ruling: give is always the LAST statement on its path --
                # code after a diverging command is unreachable, an ERROR.
                self._reject_at(
                    _first_begin(statement) or 0, "STRUCTURE",
                    "unreachable statement -- the path above already left "
                    "through give/exit/dropto; unreachable code is an "
                    "error (ruling)")
                reachable = True             # report ONCE per dead run
            if isinstance(statement, (A.Give, A.ExitSignal, A.DropTo)):
                reachable = False
            if isinstance(statement, A.ExitLabel):
                if not outermost:
                    self._reject_at(statement.label.begin, "STRUCTURE",
                                    "exit-label %r inside a nested block: "
                                    "exit-labels live only at the outermost "
                                    "body (SEMANTICS 7b)"
                                    % statement.label.segments[0])
                else:
                    seen += 1
                if statement.region is not NodeAbsent:
                    # B-1/R-39: the catch region's interior walks like any
                    # code -- its exit:-signals already count toward 12.4's
                    # emitted set via the deep collection; labels inside a
                    # region reject through the nested-block law.
                    self.block(statement.region, outermost=False,
                               exits=exits if outermost else ())
                continue
            self.statement(statement, exits=exits[seen:] if outermost
                           else (exits or []))

    def statement(self, node, exits):
        """RETURN: None, always. Walks one statement; 'exits' carries the
                  exit-labels still AHEAD in the outermost body, so any
                  dropto below this point checks forward-only existence.
        """
        match node:
            case A.Destruct():
                # SEMANTICS 27: lawful only inside work/clockwork bodies --
                # an automatic (reactive) context cannot answer a disposal;
                # the (i)-(iii) path checks await type flow (DEFERRED). The
                # handler walks so its arms stay lawful.
                if self._work_depth == 0:
                    self._reject_at(
                        (node.object.name.begin
                         if isinstance(node.object, A.DataAccess)
                         else node.object.begin), "WORK",
                        "destruct is lawful only inside work and "
                        "clockwork bodies (SEMANTICS 27)")
                if node.handler is not NodeAbsent:
                    self.handler_arms(node.handler)
                leaf = node.object.name \
                       if isinstance(node.object, A.DataAccess) \
                       else node.object
                if isinstance(leaf, ReferenceLeaf) \
                        and len(leaf.segments) == 1:
                    self._dead.add(leaf.segments[0])   # SEM 30: the name
                return                                 # dies with the having
            case A.Mutation() if node.handler is not NodeAbsent:
                # LANGUAGE 12.9 (PARTIAL): the statement's handler covers the
                # union of its fault sources, div_by_zero included; per-arm
                # exhaustiveness over that union is deferred.
                self._site_markers(node)                # R-41.2
                self._receive_agreement(node)           # known/had typing
                self.lvalue(node.lvalue)
                for extra in node.extra_lvalues:
                    self.lvalue(extra)
                if isinstance(node.rhs, A.DataAccess):
                    self._check_overloaded_call(node.rhs)   # SEMANTICS 26
                saved, self._handled = self._handled, True
                try:
                    self.expr(node.rhs)
                finally:
                    self._handled = saved
                self.handler_arms(node.handler)
                return
            case A.Wire():
                self.wire_statement(node)
            case A.Mutation():
                if node.op == "/=":
                    self._division(node.rhs)
                self._site_markers(node)                # R-41.2
                self._receive_agreement(node)           # known/had typing
                self._nothing_assignment(node)          # SEMANTICS 28
                self.lvalue(node.lvalue)
                self.expr(node.rhs)
                self._record_pipe_local(node)           # SEMANTICS 31
            case A.If():
                # SEMANTICS 28 narrowing (PARTIAL: exact-shape gates only).
                # 'k != Nothing' narrows k in the then-block; 'k == Nothing'
                # narrows k in the else-block; the initial-gate form -- a
                # '== Nothing' then-block that DIVERGES (exit:/give:) --
                # narrows k for the REST of the body.
                dead_before = set(self._dead)          # SEM 30: branch-
                given_before = set(self._given)        # local deaths/gives
                for i, arm in enumerate(node.arms):    # do not leak (joins
                    self.expr(arm.cond)                # defer)
                    gate = _nothing_gate(arm.cond) if i == 0 else None
                    added = None
                    if gate and gate[1] == "!=" \
                            and gate[0] not in self._narrowed:
                        added = gate[0]
                        self._narrowed.add(added)
                    self.block(arm.block, outermost=False, exits=exits)
                    if added is not None:
                        self._narrowed.discard(added)
                    if gate and gate[1] == "==" and node.els is NodeAbsent \
                            and len(node.arms) == 1 \
                            and _diverges(arm.block):
                        self._narrowed.add(gate[0])      # rest-of-body gate
                    self._dead = set(dead_before)
                    self._given = set(given_before)
                if node.els is not NodeAbsent:
                    gate = _nothing_gate(node.arms[0].cond) \
                           if len(node.arms) == 1 else None
                    added = None
                    if gate and gate[1] == "==" \
                            and gate[0] not in self._narrowed:
                        added = gate[0]
                        self._narrowed.add(added)
                    self.block(node.els, outermost=False, exits=exits)
                    if added is not None:
                        self._narrowed.discard(added)
                    self._dead = set(dead_before)
                    self._given = set(given_before)
            case A.Match():
                self.expr(node.scrutinee)
                for case in node.cases:
                    if isinstance(case.pattern, A.Range):
                        self.expr(case.pattern.lo)
                        self.expr(case.pattern.hi)
                    self.block(case.block, outermost=False, exits=exits)
            case A.For():
                # (the 'from: give' flavour is RETIRED by ruling -- from:
                # takes the wound generator plainly; the _given machinery
                # stays for the give sites still to land. NOTHING CAN
                # NEVER BE GIVEN stands as law and re-attaches there.)
                self.expr(node.source)
                with self._frame({node.var.segments[0]: "local"}):
                    self.block(node.block, outermost=False, exits=exits)
            case A.Count():
                self.expr(node.lo)
                self.expr(node.hi)
                if node.step is not NodeAbsent:
                    self.expr(node.step)
                with self._frame({node.var.segments[0]: "local"}):
                    self.block(node.block, outermost=False, exits=exits)
            case A.CountWith():
                self.expr(node.source)
                if node.start is not NodeAbsent:
                    self.expr(node.start)
                with self._frame({node.index.segments[0]: "local",
                                  node.var.segments[0]: "local"}):
                    self.block(node.block, outermost=False, exits=exits)
            case A.DropTo():
                label = node.label.segments[0]
                node.label.resolve(Access(kind="local", target=(label,)))
                if label not in exits:
                    self._reject_at(node.label.begin, "STRUCTURE",
                                    "dropto %r targets no exit-label defined "
                                    "LATER in the same outermost body "
                                    "(SEMANTICS 7c, forward-only)" % label)
            case A.Break() | A.Continue():
                pass
            case A.ExitLabel():
                if node.region is not NodeAbsent:
                    # B-1/R-39: the catch region's interior walks like any
                    # code; its exit:-signals count toward 12.4's emitted
                    # set via the deep collection.
                    self.block(node.region, outermost=False, exits=exits)
            case _:
                pass

    def _record_pipe_local(self, node):
        """RETURN: None, always. Records a same-body construction for the
                  PARTIAL wire-end checks (pipe ruling, SEMANTICS 31): a
                  plain '=' of a resolved reactor / reactor++ / feeder
                  call into ONE bare local makes that local's channel
                  surface visible to wires below it. Anything else leaves
                  no record (the deferral: cross-body typing rides the
                  type document).
        """
        if node.op != "=" or node.extra_lvalues:
            return
        target = node.lvalue
        if isinstance(target, A.KnownSite):
            target = target.target
        leaf = target.name if isinstance(target, A.DataAccess) else target
        if len(leaf.segments) != 1:
            return
        rhs = node.rhs
        if not isinstance(rhs, A.DataAccess) or rhs.steps:
            return
        access = getattr(rhs.name, "access", None)
        if access is None or access.residue:
            return
        if access.kind in ("reactor", "reactor++", "feeder"):
            self._local_pipe[leaf.segments[0]] = (access.kind,
                                                  tuple(access.target))

    def wire_statement(self, node):
        """RETURN: None, always. The WIRE laws (pipe ruling, SEMANTICS 31):
                  a wire is a WORK statement (WIRING IS WORK -- unlawful in
                  a reactive command-block); both ends resolve as body
                  locals; where an end's construction is visible in the
                  same body (PARTIAL -- _record_pipe_local), the named
                  channel must stand in the source's out: AND the
                  destination's in:; the plain arrow resolves to the
                  source's SINGLE out: channel (several or none reject;
                  interim law, flagged). A feeder end's channel surface is
                  provided (deferred, flagged) and skips its panel side.
        """
        if self._work_depth == 0:
            self._reject_at(node.source.begin, "PIPE",
                            "a wire is a WORK statement (wiring is work, "
                            "pipe ruling): unlawful in a reactive "
                            "command-block (SEMANTICS 31)")
        ends = []
        for leaf in (node.source, node.dest):
            access = self._local(tuple(leaf.segments))
            if access is None:
                access = Access(kind="local", target=tuple(leaf.segments))
                self._reject_at(leaf.begin, "PIPE",
                                "wire end %r resolves to no body local: "
                                "both ends are locals holding constructed "
                                "instances (SEMANTICS 31)"
                                % leaf.segments[0])
            leaf.resolve(access)
            ends.append(self._local_pipe.get(leaf.segments[0]))
        src, dst = ends
        channel = node.channel
        if channel == "":
            if src is not None and src[0] != "feeder":
                outs = tuple(c.segments[0]
                             for c in self._reactor_defs[src[1]].outs) \
                       if src[1] in self._reactor_defs else ()
                if len(outs) == 1:
                    channel = outs[0]
                else:
                    self._reject_at(
                        node.source.begin, "PIPE",
                        "the plain arrow rides the source's SINGLE out: "
                        "channel; %r declares %s (SEMANTICS 31, interim "
                        "law)" % (node.source.segments[0],
                                  ", ".join(outs) or "none"))
        else:
            if src is not None and src[0] != "feeder" \
                    and src[1] in self._reactor_defs:
                outs = {c.segments[0]
                        for c in self._reactor_defs[src[1]].outs}
                if channel not in outs:
                    self._reject_at(
                        node.source.begin, "PIPE",
                        "wire channel %r stands in no out: of the source "
                        "(out: %s) (SEMANTICS 31)"
                        % (channel, ", ".join(sorted(outs)) or "-"))
        if channel and dst is not None and dst[0] != "feeder" \
                and dst[1] in self._reactor_defs:
            ins = {c.segments[0]
                   for c in self._reactor_defs[dst[1]].ins}
            if channel not in ins:
                self._reject_at(
                    node.dest.begin, "PIPE",
                    "wire channel %r stands in no in: of the destination "
                    "(in: %s) (SEMANTICS 31)"
                    % (channel, ", ".join(sorted(ins)) or "-"))

    def lvalue(self, node):
        """RETURN: None, always. Applies the LVALUE LAW (SEMANTICS 9, pass-4
                  half): a mutation lvalue is a binding-qualified member --
                  head in {e, b, a, c}; 's.' is read-only; a non-binding head
                  is rejected. The recipe seats regardless (the walk stays
                  total) and any index steps walk as expressions.
        """
        if isinstance(node, A.KnownSite):
            node = node.target                  # R-41.2: marker recorded by
                                                # _site_markers; the place
                                                # walks unchanged
        leaf = node.name if isinstance(node, A.DataAccess) else node
        head = leaf.segments[0]
        if self._work_depth > 0:
            # SEMANTICS 23 (PARTIAL): inside a work body the targets are the
            # panel's ports and body locals -- bare names; the reactive
            # qualification law does not apply. A first ASSIGNMENT creates
            # the body local: its name joins the work frame here, so later
            # READS resolve (a read BEFORE any assignment still rejects --
            # the definite-assignment temperament ahead of the full 12.4/
            # 12.6 check, which stays deferred and marked in SEMANTICS).
            if len(leaf.segments) == 1 and self.frames:
                self.frames[-1].setdefault(head, "local")
            if isinstance(node, A.DataAccess):
                for step in node.steps:
                    self.expr(step)
            return
        if head not in BINDINGS:
            self._reject_at(leaf.begin, "STRUCTURE",
                            "lvalue %r is not binding-qualified: a reactive "
                            "mutation writes a member of the reactor -- the "
                            "bare-dot self binding '.name' (or 'e.' for the "
                            "payload copy-out; SEMANTICS 9, reactor ruling)"
                            % ".".join(leaf.segments))
        self.seat(leaf, event_ok=True)      # seat without a second rejection
        if isinstance(node, A.DataAccess):
            if node.args is not NodeAbsent:
                self._args(node.args)
            for step in node.steps:
                self.expr(step)

    # -- expressions and types --------------------------------------------------------

    def expr(self, node):
        """RETURN: None, always. Walks one expression: recipes seat at every
                  DataAccess/Call/ReferenceLeaf (raw events are NOT legitimate
                  here -- an unresolved name rejects, SEMANTICS 19); structure
                  recurses; leaves and typed absences end the descent.
        """
        match node:
            case A.BinOp():
                if node.op == "/" and not self._handled:
                    self._division(node.rhs)
                # SEMANTICS 28: comparing a known against an ABSENCE
                # spelling is the gate itself -- always lawful (equivalence
                # ruling: Nothing and the literal 0 are one absence); any
                # OTHER operation on an un-narrowed known is the
                # inappropriate operation caught immediately.
                nothing_compare = node.op in ("==", "!=") and (
                    _is_zeroish(node.lhs) or _is_zeroish(node.rhs))
                if not nothing_compare:
                    self._known_operand(node.lhs)
                    self._known_operand(node.rhs)
                self.expr(node.lhs)
                self.expr(node.rhs)
            case A.Not() | A.Neg():
                self.expr(node.operand)
            case A.Ternary():
                self.expr(node.cond)
                self.expr(node.then)
                self.expr(node.els)
            case A.DataAccess():
                self.seat(node.name)
                if node.args is not NodeAbsent:
                    self._args(node.args)
                for step in node.steps:
                    self.expr(step)
            case A.Call():
                access = self.seat(node.name)
                self.check_arguments(access, node.args, node.name.begin)
                self._args(node.args)
            case ReferenceLeaf():
                self.seat(node)
            case A.Comprehension():
                names = {}
                for generator in node.generators:
                    self.expr(generator.source)
                    for var in generator.variables:
                        names[var.segments[0]] = "local"
                    if generator.cond is not NodeAbsent:
                        with self._frame(dict(names)):
                            self.expr(generator.cond)
                with self._frame(names):
                    self.expr(node.element)
            case _:
                pass

    def type_of(self, node):
        """RETURN: None, always. Walks one type: a named type must resolve
                  (SEMANTICS 19); a struct's fields declare, the plain
                  aggregates carry nothing.
        """
        if isinstance(node, A.NamedType):
            self.seat(node.name)

    # -- resolution ----------------------------------------------------------------

    def seat(self, leaf, event_ok=False):
        """RETURN: Access, the recipe resolved for 'leaf' and seated into its
                  slot -- the resolution law of the unit header in order:
                  binding head (scope-default instance, never a position
                  reject), local frames innermost-out, the table scope-aware
                  outward with longest-prefix-and-residue, and finally: a raw
                  EVENT where 'event_ok' (a cause or emission target, R-1),
                  a SEMANTICS-19 rejection anywhere else. A table hit with
                  residue has its FIRST residue segment verified against the
                  target's declared member surface.
        """
        segments = tuple(leaf.segments)
        head = segments[0]
        if head in BINDINGS:
            access = Access(kind="binding", target=(head,),
                            residue=segments[1:])
        else:
            access = self._local(segments) or self._table(segments) \
                     or self._provided(segments)
            if access is None:
                if event_ok:
                    access = Access(kind="event", target=segments)
                else:
                    access = Access(kind="event", target=segments)
                    self._reject_at(leaf.begin, "NAME",
                                    "unresolved reference %r: every reference "
                                    "resolves or rejects; a raw event is "
                                    "legitimate only as a cause or emission "
                                    "target (SEMANTICS 19)"
                                    % ".".join(segments))
            elif access.residue and access.kind in SURFACE_KINDS:
                entry = self.table.entry_of(access.target)
                if entry is not None:
                    names = tuple(m.name for m in entry.members)
                    if access.residue[0] not in names:
                        self._reject_at(leaf.begin, "NAME",
                                        "%r is no declared member of %r "
                                        "(surface: %s) (SEMANTICS 19)"
                                        % (access.residue[0],
                                           ".".join(access.target),
                                           ", ".join(names) or "-"))
        leaf.resolve(access)
        return access

    def check_arguments(self, access, args, offset):
        """RETURN: None, always. The PYTHON ARGUMENT LAW (SEMANTICS 20, D-11)
                  against a resolved parameterised target: a BARE use (typed
                  absence) is a reference, never judged; a PARENTHESISED use
                  places positionals first (a positional after a named
                  argument rejects), covers every parameter without a default
                  exactly once, names no unknown parameter, and doubles none.
                  Targets without a declared surface (events, bindings,
                  locals, residue-navigated members) are never judged here.
        """
        if args is NodeAbsent or not isinstance(args, NodeList):
            return
        if access.residue or access.kind not in SURFACE_KINDS:
            return
        entry = self.table.entry_of(access.target)
        if entry is None:
            return
        params = [m for m in entry.members if m.category == "param"]
        names  = [m.name for m in params]
        covered, named_seen = {}, False
        position = 0
        for arg in args:
            if isinstance(arg, A.NamedArg):
                named_seen = True
                if arg.name not in names:
                    self._reject_at(offset, "NAME",
                                    "%r names no parameter of %r (parameters:"
                                    " %s) (SEMANTICS 20)"
                                    % (arg.name, ".".join(access.target),
                                       ", ".join(names) or "-"))
                elif arg.name in covered:
                    self._reject_at(offset, "NAME",
                                    "parameter %r of %r supplied twice "
                                    "(SEMANTICS 20)"
                                    % (arg.name, ".".join(access.target)))
                else:
                    covered[arg.name] = True
            else:
                if named_seen:
                    self._reject_at(offset, "NAME",
                                    "positional argument after a named one in"
                                    " the use of %r (SEMANTICS 20)"
                                    % ".".join(access.target))
                if position >= len(params):
                    self._reject_at(offset, "NAME",
                                    "too many arguments for %r: %d "
                                    "parameter(s) declared (SEMANTICS 20)"
                                    % (".".join(access.target), len(params)))
                else:
                    covered[params[position].name] = True
                position += 1
        for parameter in params:
            if not parameter.has_default and parameter.name not in covered:
                self._reject_at(offset, "NAME",
                                "required parameter %r of %r not supplied "
                                "(SEMANTICS 20)"
                                % (parameter.name, ".".join(access.target)))

    def _known_operand(self, operand):
        """RETURN: None, always. SEMANTICS 28's operand law: a known name
                  used as an operand must be NARROWED (proven not-Nothing by
                  a dominating gate) -- the had world needs no check by
                  construction (0.5).
        """
        if self._work_depth == 0:
            return
        leaf = operand.name if isinstance(operand, A.DataAccess) else operand
        if not isinstance(leaf, ReferenceLeaf):
            return
        name = leaf.segments[0]
        if len(leaf.segments) == 1 and name in self._dead:
            self._reject_at(
                leaf.begin, "CUSTODY",
                "%r was destructed on this path -- the having ended; the "
                "name knows nothing of existence (HAVE_KNOW_BE, "
                "SEMANTICS 30)" % name)
            return
        if len(leaf.segments) == 1 and name in self._given:
            self._reject_at(
                leaf.begin, "CUSTODY",
                "%r was given away on this path -- the haver holds Nothing "
                "in its place; access to the given is impossible "
                "(HAVE_KNOW_BE (2), SEMANTICS 30)" % name)
            return
        if len(leaf.segments) == 1 and name in self._known \
                and name not in self._narrowed:
            self._reject_at(
                leaf.begin, "NOTHING",
                "operation on known %r without a Nothing-gate -- a known "
                "holder may be Nothing; gate it ('if: %s != Nothing') or "
                "operate on a had substitute (SEMANTICS 28)" % (name, name))

    def _nothing_assignment(self, node):
        """RETURN: None, always. SEMANTICS 28's assignment law inside work
                  bodies: a HAD holder (local, takes-/gives-port) never
                  receives Nothing -- neither the literal nor an un-narrowed
                  known; KNOWN holders receive anything.
        """
        if self._work_depth == 0:
            return
        lvalue = node.lvalue
        if isinstance(lvalue, A.KnownSite):
            return                    # R-41.2: a marked target is a KNOWN
                                      # holder -- it admits Nothing
        leaf = lvalue.name if isinstance(lvalue, A.DataAccess) else lvalue
        target = leaf.segments[0]
        if len(leaf.segments) != 1 or target in self._known:
            return                        # known holders admit Nothing
        rhs = node.rhs
        rdead = (rhs.name if isinstance(rhs, A.DataAccess) else
                 rhs if isinstance(rhs, ReferenceLeaf) else None)
        if rdead is not None and len(rdead.segments) == 1 \
                and rdead.segments[0] in self._dead:
            self._reject_at(
                rdead.begin, "CUSTODY",
                "%r was destructed on this path -- the having ended; the "
                "name knows nothing of existence (HAVE_KNOW_BE, "
                "SEMANTICS 30)" % rdead.segments[0])
        if rdead is not None and len(rdead.segments) == 1 \
                and rdead.segments[0] in self._given:
            self._reject_at(
                rdead.begin, "CUSTODY",
                "%r was given away on this path -- the haver holds Nothing "
                "in its place; access to the given is impossible "
                "(HAVE_KNOW_BE (2), SEMANTICS 30)" % rdead.segments[0])
        if isinstance(rhs, A.NothingLeaf):
            self._reject_at(
                leaf.begin, "NOTHING",
                "Nothing assigned to had holder %r -- having requires "
                "existence; only known holders admit Nothing "
                "(LANGUAGE 0.5, SEMANTICS 28)" % target)
        elif (rleaf := (rhs.name if isinstance(rhs, A.DataAccess)
                        and rhs.args is NodeAbsent else
                        rhs if isinstance(rhs, ReferenceLeaf) else None)) \
                is not None \
                and len(rleaf.segments) == 1 \
                and rleaf.segments[0] in self._known \
                and rleaf.segments[0] not in self._narrowed:
            self._reject_at(
                leaf.begin, "NOTHING",
                "had holder %r receives known %r that may be Nothing -- "
                "gate first (SEMANTICS 28)"
                % (target, rleaf.segments[0]))


    def _resolve_call_work(self, rhs):
        """RETURN: Work|ClockworkDef, the definition a call rhs resolves to,
                  if the resolution is decidable here (a top-level work by
                  bare name; a '+class.ext' extension when single or picked
                  by its SELECTOR). None, else (PARTIAL: everything
                  undecidable defers to the type document).
        """
        if not isinstance(rhs, A.DataAccess) or rhs.args is NodeAbsent:
            return None
        segs = tuple(rhs.name.segments)
        if segs in self._work_defs:
            return self._work_defs[segs]
        overloads = self._overloads.get(segs)
        if not overloads:
            return None
        if len(overloads) == 1:
            return overloads[0]
        args = tuple(rhs.args)
        if not args or not isinstance(args[0], A.NamedArg):
            return None
        selector = args[0].name             # NamedArg.name is a str
        for w in overloads:
            entries = tuple(w.panel.ins)
            if entries and entries[0].name.segments[0] == selector:
                return w
        return None

    def _receive_agreement(self, node):
        """RETURN: None, always. The AGREEMENT law (ruled, then leaned
                  ONE-WAY): known and had are part of the TYPE. A known
                  out: entry MUST be received at a 'known:'-marked site (a
                  view never becomes custody); a custody out: entry MAY be
                  received known -- the unclaimed custody is had elsewhere
                  or destructed, and the known hub handles destruction
                  properly. Targets pair against outs in declaration order
                  (12.5); checked where the callee resolves here (PARTIAL);
                  arity itself is 12.5's deferred law.
        """
        work = self._resolve_call_work(node.rhs)
        if work is None:
            return
        targets = (node.lvalue,) + tuple(node.extra_lvalues)
        outs = tuple(work.panel.outs)
        for target, entry in zip(targets, outs):
            site_known = isinstance(target, A.KnownSite)
            entry_known = (entry.marker == "known")
            if site_known == entry_known:
                continue
            inner = target.target if site_known else target
            leaf = inner.name if isinstance(inner, A.DataAccess) else inner
            if entry_known:
                self._reject_at(
                    leaf.begin, "TYPE",
                    "target %r receives the known out: entry %r without "
                    "the known: site marker -- known and had are part of "
                    "the type; a view never becomes custody (agreement "
                    "ruling, R-41.2)"
                    % (leaf.segments[-1], entry.name.segments[0]))
            # the OTHER direction is LAWFUL (ruling): a custody out:
            # entry MAY be received at a known: site -- the unclaimed
            # custody must be had somewhere else or is destructed, and
            # a destructed known is proper: the known hub hands its
            # readers Nothing (HAVE_KNOW_BE (3)).

    def _site_markers(self, node):
        """RETURN: None, always. Records each 'known:'-marked binding target
                  of one mutation (R-41.2): inside a work body the marked
                  single name JOINS the known set -- knownness propagates
                  without gating; the SEMANTICS-28 gates keep firing at the
                  OPERATION. The site-vs-panel AGREEMENT law is flagged open
                  -- no check is invented here.
        """
        if self._work_depth == 0:
            return
        for target in (node.lvalue,) + tuple(node.extra_lvalues):
            if not isinstance(target, A.KnownSite):
                continue
            inner = target.target
            leaf = inner.name if isinstance(inner, A.DataAccess) else inner
            if len(leaf.segments) == 1:
                self._known.add(leaf.segments[0])
                self._narrowed.discard(leaf.segments[0])

    def _division(self, denominator):
        """RETURN: None, always. The SEMANTICS-21 check on one division: a
                  denominator that is PROVABLY NONZERO -- a nonzero numeric
                  constant, optionally negated -- passes; anything else may
                  be zero at run time and requires the 'else:' fault
                  handler, whose surface is pending: until it lands, the
                  division REJECTS.
        """
        if _provably_nonzero(denominator):
            return
        offset = getattr(denominator, "begin", 0)
        self._reject_at(offset, "GUARD",
                        "division by a possibly-zero denominator requires an "
                        "'else:' fault handler (SEMANTICS 21; handler "
                        "surface pending)")

    def _provided(self, segments):
        """RETURN: Access, the PROVIDED-kind hit (pipe ruling): 'script' is
                  the harness FEEDER -- a provided class-type-like kind, an
                  event source with out-channels and no in-channels;
                  keyboard/file/socket siblings and the DRAIN mirror are
                  stubs (flagged open).
                  None, else.
        """
        if segments[0] == "script":
            return Access(kind="feeder", target=(segments[0],),
                          residue=segments[1:])
        return None

    def _local(self, segments):
        """RETURN: Access, a local-frame hit for the head segment (innermost
                  frame first) with the remaining segments as residue, if any
                  frame holds the head.
                  None, else.
        """
        for frame in reversed(self.frames):
            if segments[0] in frame:
                kind = "behavior" if frame[segments[0]] == "behavior" \
                       else "local"
                return Access(kind=kind, target=(segments[0],),
                              residue=segments[1:])
        return None

    def _table(self, segments):
        """RETURN: Access, the table's scope-aware outward hit: the writing
                  scope's prefixes from innermost to top level, LONGEST match
                  per prefix, first scope that matches wins, if any does.
                  None, else.
        """
        for depth in range(len(self.scope), -1, -1):
            hit = self.table.longest_match(self.scope[:depth] + segments)
            if hit is not None:
                target, entry, origin = hit
                matched_own = len(target) - depth
                return Access(kind=entry.kind, target=target,
                              residue=segments[matched_own:], origin=origin)
        return None

    # -- shared small parts -------------------------------------------------------

    def _args(self, args):
        """RETURN: None, always. Walks a call's argument list (positional
                  expressions and named-argument values); a typed absence or
                  empty list ends the descent.
        """
        if args is NodeAbsent or not isinstance(args, NodeList):
            return
        for arg in args:
            if isinstance(arg, A.NamedArg):
                self.expr(arg.value)
            else:
                self.expr(arg)

    def _frame(self, names):
        """RETURN: object, a context manager holding 'names' (name -> kind)
                  as the innermost local frame for its 'with' body.
        """
        walk = self

        class _F:
            def __enter__(self):
                walk.frames.append(dict(names))

            def __exit__(self, *a):
                walk.frames.pop()
        return _F()

    def _top_frame(self):
        """RETURN: dict, the innermost local frame, creating a module-level
                  one when none is open (a spawn handle at top level still
                  needs a home; SEMANTICS 11 keeps it entity-local, which the
                  frame lifetime enforces).
        """
        if not self.frames:
            self.frames.append({})
        return self.frames[-1]

    def _reject_at(self, offset, tag, message):
        """RETURN: None, always. One REJECT through the reporter."""
        _reject(self.reporter, offset, tag, message)


def _provably_nonzero(node):
    """RETURN: bool, True exactly when 'node' is a numeric constant whose
              value is not zero, possibly under negation -- the one
              denominator shape SEMANTICS 21 admits without a handler.
    """
    if isinstance(node, A.Neg):
        return _provably_nonzero(node.operand)
    from ..core.symbol.ast import ConstantLeaf
    if isinstance(node, ConstantLeaf) and str(node.kind) in ("int", "float"):
        return float(node.text) != 0.0
    return False


def _reject(reporter, offset, tag, message):
    """RETURN: None, always. Reports one REJECT-severity diagnostic: phase
              SEMANTIC, fatal (stops at the next phase boundary), under the
              given tag.
    """
    reporter.report(Diagnostic(phase=Phase.SEMANTIC, message=message,
                               source_offset=offset, fatal=True, tag=tag))
