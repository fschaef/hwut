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
        effect's spawn, a clockwork emit): a name resolving to nothing there
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
from dataclasses import dataclass

from ..core.diagnostic import DiagnosticReporter, Diagnostic, Phase
from ..core.symbol.ast import NodeList, ReferenceLeaf
from ..core.parser_generator.cst_nodes import NodeAbsent
from .module_states import DeclaredModule, SemanticModule
from . import ast_nodes as A


BINDINGS         = ("e", "b", "a", "c", "s")
WRITABLE_HEADS   = ("e", "b", "a", "c")     # SEMANTICS 9: 's.' is read-only
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

    # -- module and definitions ----------------------------------------------

    def module(self, root):
        """RETURN: None, always. Walks every top-level item under the top
                  scope.
        """
        for item in root.items:
            self.item(item)

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
            case A.Character():
                self.definition(item, body=None)
            case A.Aspect():
                self.definition(item, body=item.body)
            case A.Behavior():
                self.definition(item, body=item.causalities)
            case A.Declaration():
                self.type_of(item.type_)
            case _:
                pass

    def definition(self, node, body):
        """RETURN: None, always. Walks one definition: 'is:' targets are
                  required references with argument checking (SEMANTICS 19,
                  20), parameters and has: members open the frame, the body
                  walks inside it.
        """
        for call in node.is_:
            access = self.seat(call.name)
            self.check_arguments(access, call.args, call.name.begin)
        frame = self._params_of(node.signature)
        for decl in node.has:
            frame[decl.name.segments[0]] = "local"
            self.type_of(decl.type_)
        if isinstance(body, A.Clockwork):
            body_items = (body,)
        elif body is None:
            body_items = ()
        else:
            body_items = tuple(body)
        for inner in body_items:            # nested definitions join the frame
            if isinstance(inner, (A.Character, A.Aspect, A.Behavior)):
                frame[inner.signature.name.segments[0]] = "local"
        with self._frame(frame):
            for inner in body_items:
                if isinstance(inner, (A.Character, A.Aspect, A.Behavior,
                                      A.Causality, A.DefCause)):
                    self.item(inner)
                else:
                    self.clockwork(inner)

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
                  target; a command block walks as an outermost body.
        """
        if isinstance(node.action, A.Spawn):
            spawn = node.action
            self.emission_target(spawn.call)
            if spawn.every is not NodeAbsent:
                self.expr(spawn.every)
            if spawn.handle is not NodeAbsent:
                self._top_frame()[spawn.handle.segments[0]] = "local"
        else:
            self.block(node.action, outermost=True)

    def emission_target(self, call):
        """RETURN: Access, the recipe seated on an emission target (an
                  effect's spawn or a clockwork emit): a raw event is
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
                     if isinstance(s, A.ExitLabel)]
        seen = 0
        for statement in node.statements:
            if isinstance(statement, A.ExitLabel):
                if not outermost:
                    self._reject_at(statement.label.begin, "STRUCTURE",
                                    "exit-label %r inside a nested block: "
                                    "exit-labels live only at the outermost "
                                    "body (SEMANTICS 7b)"
                                    % statement.label.segments[0])
                else:
                    seen += 1
                continue
            self.statement(statement, exits=exits[seen:] if outermost
                           else (exits or []))

    def statement(self, node, exits):
        """RETURN: None, always. Walks one statement; 'exits' carries the
                  exit-labels still AHEAD in the outermost body, so any
                  dropto below this point checks forward-only existence.
        """
        match node:
            case A.Mutation():
                if node.op == "/=":
                    self._division(node.rhs)
                self.lvalue(node.lvalue)
                self.expr(node.rhs)
            case A.If():
                for arm in node.arms:
                    self.expr(arm.cond)
                    self.block(arm.block, outermost=False, exits=exits)
                if node.els is not NodeAbsent:
                    self.block(node.els, outermost=False, exits=exits)
            case A.Match():
                self.expr(node.scrutinee)
                for case in node.cases:
                    if isinstance(case.pattern, A.Range):
                        self.expr(case.pattern.lo)
                        self.expr(case.pattern.hi)
                    self.block(case.block, outermost=False, exits=exits)
            case A.For():
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
                                    "dropto: %r targets no exit-label defined "
                                    "LATER in the same outermost body "
                                    "(SEMANTICS 7c, forward-only)" % label)
            case A.Break() | A.Continue():
                pass
            case _:
                pass

    def lvalue(self, node):
        """RETURN: None, always. Applies the LVALUE LAW (SEMANTICS 9, pass-4
                  half): a mutation lvalue is a binding-qualified member --
                  head in {e, b, a, c}; 's.' is read-only; a non-binding head
                  is rejected. The recipe seats regardless (the walk stays
                  total) and any index steps walk as expressions.
        """
        leaf = node.name if isinstance(node, A.DataAccess) else node
        head = leaf.segments[0]
        if head not in BINDINGS:
            self._reject_at(leaf.begin, "STRUCTURE",
                            "lvalue %r is not binding-qualified: a mutation "
                            "writes a member, head in {e, b, a, c} "
                            "(SEMANTICS 9)" % ".".join(leaf.segments))
        elif head not in WRITABLE_HEADS:
            self._reject_at(leaf.begin, "STRUCTURE",
                            "lvalue head 's' is read-only: arguments are "
                            "never written (SEMANTICS 9)")
        self.seat(leaf, event_ok=True)      # seat without a second rejection
        if isinstance(node, A.DataAccess):
            if node.args is not NodeAbsent:
                self._args(node.args)
            for step in node.steps:
                self.expr(step)

    # -- clockwork -----------------------------------------------------------------

    def clockwork(self, node):
        """RETURN: None, always. Walks a clockwork body: the tick cause, then
                  every clockwork statement.
        """
        if not isinstance(node, A.Clockwork):
            return
        self.cause(node.tick)
        for statement in node.statements:
            self.clock_statement(statement)

    def clock_statement(self, node):
        """RETURN: None, always. Walks one clockwork statement: an emit's
                  target is an emission; a groove walks arm by arm; a plain
                  statement is a command in a nested context.
        """
        match node:
            case A.EmitStep():
                if not isinstance(node.target, A.EmitNone):
                    self.emission_target(node.target)
            case A.Groove():
                for arm in node.arms:
                    self.clock_arm(arm)
            case _:
                self.statement(node, exits=[])

    def clock_arm(self, arm):
        """RETURN: None, always. Walks one groove arm: its cause (a
                  cause-explicit, the ~ELSE arm, or the tick-default), then
                  its body of clockwork statements.
        """
        match arm:
            case A.ClockArm():
                head = arm.cause
                if isinstance(head, A.Cause):
                    self.cause(head)
                elif isinstance(head, A.ElseArm):
                    if head.guard is not NodeAbsent:
                        self.expr(head.guard)
                elif isinstance(head, A.TickDefault):
                    self.expr(head.cond)
                for statement in arm.body:
                    self.clock_statement(statement)
            case A.BeatArm():
                for statement in arm.body:
                    self.clock_statement(statement)

    # -- expressions and types --------------------------------------------------------

    def expr(self, node):
        """RETURN: None, always. Walks one expression: recipes seat at every
                  DataAccess/Call/ReferenceLeaf (raw events are NOT legitimate
                  here -- an unresolved name rejects, SEMANTICS 19); structure
                  recurses; leaves and typed absences end the descent.
        """
        match node:
            case A.BinOp():
                if node.op == "/":
                    self._division(node.rhs)
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
            access = self._local(segments) or self._table(segments)
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

    def _local(self, segments):
        """RETURN: Access, a local-frame hit for the head segment (innermost
                  frame first) with the remaining segments as residue, if any
                  frame holds the head.
                  None, else.
        """
        for frame in reversed(self.frames):
            if segments[0] in frame:
                return Access(kind="local", target=(segments[0],),
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
