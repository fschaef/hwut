"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

INTERPRET -- direct execution of the decorated AST: the semantics ORACLE.

A tree-walking interpreter over SemanticModules. It is the FIRST CONSUMER of
the serialisation boundary and honours it strictly: everything it needs it
reads off the typed tree and the seated RECIPES (Access) -- no name is ever
re-resolved here, no unit-internal surface is touched. Every future emitter
earns its green by matching this interpreter's event traces, not by being
read carefully.

SETTLED LAW EXECUTED (LANGUAGE.txt):
    - '=x=>' deactivates exactly the deactivable kinds (behaviour, aspect,
      character, recurring-emission handle); events and blocks are not
      deactivable (R-6 table).
    - 'every: n' emits once per n (seconds, virtual); 'as:' binds a handle;
      a recurring emission runs only while its entity is ACTIVE and is
      auto-cancelled at ~EXIT (R-15).
    - ~ENTRY / ~EXIT run on activation / deactivation; no trigger, no guard.
    - Clockwork (R-20/R-22): '=> emit' emits then awaits the tick; '=> ~NONE'
      passes one tick; groove is a repeating blocking select over its arms;
      'beat: n' fires every n ticks; '~ELSE' fires when no other arm
      matched; 'when: cond' is the tick-default.
    - An aspect governs ONE active behaviour: activating a behaviour inside
      an aspect deactivates the previously active sibling.

PROVISIONAL RULINGS (P-n; each one line to correct -- report lists them):
    P-1  Dispatch: ONE FIFO queue. An event is processed to completion --
         every matching causality of every active holder, in declaration
         order -- before the next event; effects run left to right; emitted
         events APPEND to the queue (breadth, no re-entrant dispatch).
    P-1b Guards of one event evaluate against the state AT EVENT ARRIVAL:
         the matched set is fixed FIRST, effects then run in declaration
         order -- an effect of this event never changes which of this
         event's guards held (the synchronous-instant law).
    P-2  '=> X' with X resolving to a definition ACTIVATES X's scope-default
         instance; a raw event target ENQUEUES. Activating the active, or
         deactivating the inactive, is a no-op.
    P-3  Time is VIRTUAL: the driver calls advance(seconds); recurring
         emissions fire at their multiples, oldest due first.
    P-4  Guards evaluate at dispatch time over current member state; 'e.'
         reads the fired event's payload; an unknown member reads 0.0.
    P-5  Members initialise per declared type: float 0.0, int 0, bool False,
         string "", list [], dict {}, struct all-0.0; parameters take the
         activation call's arguments, else their D-11 default, else 0.0.
    P-6  A named-cause use hot(v) matches its definition's event with the
         definition's guard evaluated under s.<param> bound to the use-site
         arguments.
    P-7  The tick of a clockwork is its cause; each tick advances the
         script by exactly one await. A GROOVE is a blocking select: while
         the script rests in one, an ARM CAUSE wakes it on that cause's OWN
         event (not the tick); 'beat:' counts ticks; the tick-default and
         '~ELSE' evaluate on ticks only, '~ELSE' when no other arm matched
         that tick. The groove repeats forever (statements after it never
         run).
______________________________________________________________________________
"""
import fnmatch
from collections import deque

from ..core.parser_generator.cst_nodes import NodeAbsent
from ..core.symbol.ast import ReferenceLeaf, ConstantLeaf
from . import ast_nodes as A


class _DropTo(Exception):
    """RETURN: never a value -- the forward jump of 'dropto:' (SEMANTICS 7):
              raised at the dropto, caught by the outermost body, which
              resumes at the named exit-label.
    """

    def __init__(self, label):
        self.label = label


class _Break(Exception):
    """RETURN: never a value -- 'break:;' leaving the enclosing loop."""


class _Continue(Exception):
    """RETURN: never a value -- 'continue:;' to the next iteration."""


class Instance:
    """RETURN: never a value itself -- the scope-default instance of one
              definition (or of one implicit level default): its member
              state, parameter values, activity, cancellation handles, and
              -- for a clockwork aspect -- the script's resumable state.
    """

    def __init__(self, qualified, kind):
        self.qualified = qualified
        self.kind      = kind
        self.members   = {}
        self.params    = {}
        self.active    = False
        self.handles   = {}          # handle name -> recurring emission
        self.active_child = None     # an aspect's one active behaviour
        self.clock     = None        # generator of a clockwork script


class Recurring:
    """RETURN: never a value itself -- one 'every:' emission: what to emit,
              its period, its next due time, and the owning instance (whose
              deactivation auto-cancels it, R-15).
    """

    def __init__(self, event, payload, period, owner, now):
        self.event   = event
        self.payload = payload
        self.period  = period
        self.due     = now + period
        self.owner   = owner
        self.alive   = True


class Machine:
    """RETURN: never a value itself -- one executable world over a list of
              SemanticModules: instances per definition, the event queue,
              virtual time, recurring emissions, and the trace.

    Drive it with post() and advance(); read the behaviour off trace() --
    the byte-stable line list the GOOD suite locks.
    """

    def __init__(self, modules):
        self.defs      = {}          # qualified -> (definition node, module)
        self.instances = {}          # qualified -> Instance
        self.queue     = deque()
        self.now       = 0.0
        self.recurring = []
        self.lines     = []
        for module in modules:
            self._index(module.file_node.items, scope=())
        for module in modules:
            self._activate_top(module.file_node.items, scope=())

    # -- construction -------------------------------------------------------

    def _index(self, items, scope):
        """RETURN: None, always. Records every definition node under its
                  fully-qualified name, recursing through namespaces --
                  the instance registry's ground truth.
        """
        for item in items:
            if isinstance(item, A.Namespace):
                self._index(item.items, scope + tuple(item.name.segments))
            elif isinstance(item, (A.Character, A.Aspect, A.Behavior,
                                   A.DefCause)):
                key = scope + tuple(item.signature.name.segments)
                self.defs[key] = item

    def _activate_top(self, items, scope):
        """RETURN: None, always. Activates the scope-default instance of
                  every non-abstract top-level definition and registers each
                  top-level causality as always-active (owned by the scope's
                  implicit level defaults).
        """
        for item in items:
            if isinstance(item, A.Namespace):
                self._activate_top(item.items,
                                   scope + tuple(item.name.segments))
            elif isinstance(item, (A.Character, A.Aspect, A.Behavior)):
                if not item.abstract:
                    self.activate(scope + tuple(item.signature.name.segments),
                                  args=())

    def instance(self, qualified):
        """RETURN: Instance, the scope-default instance for 'qualified',
                  created on first touch (an implicit level default when no
                  definition of that name exists -- the ruling: every level
                  has a default instance in the open scope).
        """
        key = tuple(qualified)
        if key not in self.instances:
            node = self.defs.get(key)
            kind = type(node).__name__.lower() if node else "default"
            inst = Instance(key, kind)
            if node is not None:
                self._init_members(inst, node)
            self.instances[key] = inst
        return self.instances[key]

    def _init_members(self, inst, node):
        """RETURN: None, always. Initialises the instance's members from the
                  definition's has: declarations (P-5 zero values per type)
                  and its parameters from the D-11 defaults.
        """
        for decl in getattr(node, "has", ()):
            inst.members[decl.name.segments[0]] = _zero_of(decl.type_)
        signature = getattr(node, "signature", None)
        if signature is not None and signature.params is not NodeAbsent:
            for arg in signature.params:
                if arg.default is not NodeAbsent:
                    inst.params[arg.name.segments[0]] = \
                        self.expr(arg.default, _Ctx(self, inst))
                else:
                    inst.params[arg.name.segments[0]] = 0.0

    # -- driving ------------------------------------------------------------

    def post(self, name, **payload):
        """RETURN: None, always. Enqueues one external event (its name as a
                  dotted string) with keyword payload members readable
                  through 'e.'.
        """
        self.queue.append((tuple(name.split(".")), dict(payload)))
        self.drain()

    def advance(self, seconds):
        """RETURN: None, always. Moves virtual time forward, firing every due
                  recurring emission in due order (P-3) and draining the
                  queue after each.
        """
        target = self.now + seconds
        while True:
            due = [r for r in self.recurring if r.alive and r.due <= target]
            if not due:
                break
            nxt = min(due, key=lambda r: r.due)
            self.now = nxt.due
            nxt.due += nxt.period
            self.line("tick   %.1fs %s" % (self.now, ".".join(nxt.event)))
            self.queue.append((nxt.event, dict(nxt.payload)))
            self.drain()
        self.now = target

    def drain(self):
        """RETURN: None, always. Processes the queue to exhaustion: one event
                  fully dispatched -- every matching causality of every
                  active holder, declaration order -- before the next (P-1).
        """
        while self.queue:
            event, payload = self.queue.popleft()
            self.line("event  %s%s" % (".".join(event), _fmt_payload(payload)))
            self.dispatch(event, payload)

    def trace(self):
        """RETURN: str, the full trace, one line per observable step -- the
                  oracle text a GOOD locks.
        """
        return "\n".join(self.lines)

    def line(self, text):
        """RETURN: None, always. Appends one trace line."""
        self.lines.append(text)

    # -- dispatch -----------------------------------------------------------

    def dispatch(self, event, payload):
        """RETURN: None, always. Fires 'event' at every ACTIVE causality
                  holder in registry order: PHASE 1 fixes the matched set
                  against the state at event arrival (P-1b -- an effect of
                  this event never changes which of this event's guards
                  held); PHASE 2 runs the matched effects in declaration
                  order. A clockwork whose tick matches advances one await
                  (P-7).
        """
        fired = []
        for key in sorted(self.defs):
            node = self.defs[key]
            inst = self.instances.get(key)
            if inst is None or not inst.active:
                continue
            if isinstance(node, A.Behavior):
                ctx = self._context_of(key, inst)
                ctx.e = payload
                ctx.event_name = event
                for causality in node.causalities:
                    if self.cause_matches(causality.cause, event, payload,
                                          ctx):
                        fired.append(("fire", causality, ctx))
            elif isinstance(node, A.Aspect) \
                    and isinstance(node.body, A.Clockwork):
                ctx = self._context_of(key, inst)
                ctx.event_name = event
                if self.cause_matches(node.body.tick, event, payload, ctx):
                    fired.append(("tick", node.body, (inst, ctx)))
                elif inst.clock is not None \
                        and inst.clock["groove"] is not None:
                    fired.append(("wake", node.body, (inst, ctx)))
        for kind, entry, carrier in fired:
            if kind == "tick":
                inst, ctx = carrier
                self.clock_step(inst, entry, event, payload, ctx)
            elif kind == "wake":
                inst, ctx = carrier
                self.clock_event(inst, entry, event, payload, ctx)
            else:
                for effect in entry.effects:
                    self.run_effect(effect, carrier)

    def _context_of(self, key, inst):
        """RETURN: _Ctx, the binding context of one holder: b = the holder
                  when it is a behaviour, a = the enclosing (or scope-default)
                  aspect, c = the scope-default character of the holder's
                  scope -- the default-instance-per-level ruling made
                  concrete.
        """
        scope = key[:-1]
        if inst.kind == "behavior":
            b = inst
            a = self.instance(scope + ("<aspect>",))
        else:
            b = self.instance(scope + ("<behavior>",))
            a = inst
        c = self.instance(scope + ("<character>",))
        return _Ctx(self, inst, e={}, b=b, a=a, c=c, s=inst.params)

    def cause_matches(self, cause, event, payload, ctx):
        """RETURN: bool, True exactly when the cause names the fired event
                  (directly, or through a named cause whose own guard holds
                  with s.<param> bound to the use-site arguments, P-6) and
                  the use-site guard holds.
        """
        target = cause.target
        if isinstance(target, A.Lifecycle):
            return False                       # lifecycle fires internally
        access = target.access
        if access.kind == "cause":
            definition = self.defs.get(access.target)
            if definition is None:
                return False
            frame = {}
            if definition.signature.params is not NodeAbsent \
                    and cause.args is not NodeAbsent:
                names = [p.name.segments[0]
                         for p in definition.signature.params]
                for name, arg in zip(names, cause.args):
                    frame[name] = self.expr(arg, ctx)
            inner = ctx.with_params(frame)
            inner.e = payload
            if not self.cause_matches(definition.cause, event, payload,
                                      inner):
                return False
            if cause.guard is not NodeAbsent \
                    and not _truthy(self.expr(cause.guard, ctx)):
                return False
            return True
        if tuple(access.target) != tuple(event):
            return False
        if cause.guard is not NodeAbsent \
                and not _truthy(self.expr(cause.guard, ctx)):
            return False
        return True

    # -- effects ------------------------------------------------------------

    def run_effect(self, effect, ctx):
        """RETURN: None, always. Executes one effect: '=>' activates a
                  definition target or enqueues a raw event (P-2), with
                  'every:' turning the emission recurring (R-15); '=x=>'
                  deactivates a deactivable target or cancels a handle; a
                  command block runs as an outermost body.
        """
        if isinstance(effect.action, A.CommandBlock):
            self.run_block(effect.action, ctx, outermost=True)
            return
        spawn = effect.action
        access = spawn.call.name.access
        args = [] if spawn.call.args is NodeAbsent \
               else [self.expr(a.value if isinstance(a, A.NamedArg) else a,
                               ctx) for a in spawn.call.args]
        if effect.marker == "=x=>":
            self.cancel(access, ctx)
            return
        if access.kind in ("character", "aspect", "behavior"):
            self.activate(access.target, args)
        elif spawn.every is not NodeAbsent:
            period = _number(self.expr(spawn.every, ctx))
            emission = Recurring(event=tuple(access.target), payload={},
                                 period=period, owner=ctx.inst, now=self.now)
            self.recurring.append(emission)
            self.line("recur  %s every %.1fs"
                      % (".".join(access.target), period))
            if spawn.handle is not NodeAbsent:
                ctx.inst.handles[spawn.handle.segments[0]] = emission
        else:
            self.queue.append((tuple(access.target), {}))
            self.line("emit   %s" % ".".join(access.target))

    def cancel(self, access, ctx):
        """RETURN: None, always. '=x=>': a handle cancels its recurring
                  emission; a definition target deactivates its instance;
                  anything else is a no-op at run time (the R-6 deactivable
                  table was elaborate's to reject).
        """
        if access.kind == "local" \
                and access.target[0] in ctx.inst.handles:
            emission = ctx.inst.handles[access.target[0]]
            emission.alive = False
            self.line("cancel %s" % access.target[0])
        elif access.kind in ("character", "aspect", "behavior"):
            self.deactivate(access.target)

    def activate(self, qualified, args):
        """RETURN: None, always. Activates the scope-default instance of
                  'qualified' (a no-op when already active, P-2): parameters
                  take the call's arguments; inside an aspect the previously
                  active sibling behaviour deactivates first (one active
                  behaviour per aspect); ~ENTRY causalities then run.
        """
        inst = self.instance(qualified)
        if inst.active:
            return
        node = self.defs.get(tuple(qualified))
        if node is not None and getattr(node, "abstract", False):
            return
        if node is not None:
            signature = node.signature
            if signature.params is not NodeAbsent:
                names = [p.name.segments[0] for p in signature.params]
                for name, value in zip(names, args):
                    inst.params[name] = value
        inst.active = True
        self.line("enter  %s" % ".".join(qualified))
        if node is not None and isinstance(node, A.Behavior):
            self._lifecycle(node, inst, "~ENTRY")
        if node is not None and isinstance(node, A.Aspect) \
                and isinstance(node.body, A.Clockwork):
            inst.clock = None                  # fresh script on activation

    def deactivate(self, qualified):
        """RETURN: None, always. Deactivates the instance (a no-op when
                  inactive): ~EXIT causalities run, then every recurring
                  emission it owns is auto-cancelled (R-15).
        """
        inst = self.instance(qualified)
        if not inst.active:
            return
        node = self.defs.get(tuple(qualified))
        if node is not None and isinstance(node, A.Behavior):
            self._lifecycle(node, inst, "~EXIT")
        for emission in self.recurring:
            if emission.owner is inst and emission.alive:
                emission.alive = False
                self.line("cancel (auto, ~EXIT) %s"
                          % ".".join(emission.event))
        inst.active = False
        inst.clock = None
        self.line("exit   %s" % ".".join(qualified))

    def _lifecycle(self, node, inst, kind):
        """RETURN: None, always. Runs every causality of 'node' whose cause
                  is the lifecycle event 'kind' -- no trigger, no guard
                  (LANGUAGE 3).
        """
        ctx = self._context_of(inst.qualified, inst)
        for causality in node.causalities:
            target = causality.cause.target
            if isinstance(target, A.Lifecycle) and target.kind == kind:
                for effect in causality.effects:
                    self.run_effect(effect, ctx)

    # -- clockwork ----------------------------------------------------------

    def clock_step(self, inst, clockwork, event, payload, ctx):
        """RETURN: None, always. Advances the instance's clockwork by one
                  TICK (P-7): plain statements run without pausing; an
                  emit-step emits then rests until the next tick; reaching a
                  groove parks the script there forever -- each tick then
                  evaluates beat/tick-default/~ELSE arms (an '~ELSE' fires
                  when no arm matched this tick); the script restarts when
                  its statement list is exhausted.
        """
        state = inst.clock
        if state is None:
            state = inst.clock = {"pc": 0, "groove": None, "beats": {}}
        ctx.e = payload
        ctx.event_name = event
        if state["groove"] is not None:
            self._groove_tick(state, ctx)
            return
        statements = list(clockwork.statements)
        while state["pc"] < len(statements):
            statement = statements[state["pc"]]
            if isinstance(statement, A.EmitStep):
                state["pc"] += 1
                if not isinstance(statement.target, A.EmitNone):
                    self._emit_call(statement.target, ctx)
                return                          # rest until the next tick
            if isinstance(statement, A.Groove):
                state["groove"] = statement
                self._groove_tick(state, ctx)
                return                          # parked, forever
            self.run_block_statement(statement, ctx)
            state["pc"] += 1
        state["pc"] = 0                         # exhausted: restart (R-20)

    def clock_event(self, inst, clockwork, event, payload, ctx):
        """RETURN: None, always. Wakes a groove-parked script on one of its
                  ARM CAUSES' own events (the blocking-select half of P-7):
                  the first cause-arm whose cause matches fires its body;
                  ticks never arrive here and beat/default/~ELSE never fire
                  here.
        """
        state = inst.clock
        if state is None or state["groove"] is None:
            return
        ctx.e = payload
        ctx.event_name = event
        for arm in state["groove"].arms:
            if isinstance(arm, A.BeatArm) \
                    or not isinstance(arm.cause, A.Cause):
                continue
            if self.cause_matches(arm.cause, event, payload, ctx):
                self._arm_body(arm, ctx)
                return

    def _groove_tick(self, state, ctx):
        """RETURN: None, always. One TICK inside the groove: 'beat:' arms
                  count and fire on their multiples; the tick-default fires
                  when its condition holds; '~ELSE' fires when no arm of
                  this tick matched (its optional guard permitting); source
                  order decides among simultaneous claims.
        """
        groove = state["groove"]
        for index, arm in enumerate(groove.arms):
            if isinstance(arm, A.BeatArm):
                state["beats"][index] = state["beats"].get(index, 0) + 1
                if state["beats"][index] % arm.beat == 0:
                    self._arm_body(arm, ctx)
                    return
            elif isinstance(arm.cause, A.TickDefault):
                if _truthy(self.expr(arm.cause.cond, ctx)):
                    self._arm_body(arm, ctx)
                    return
        for arm in groove.arms:
            if not isinstance(arm, A.BeatArm) \
                    and isinstance(arm.cause, A.ElseArm):
                guard = arm.cause.guard
                if guard is NodeAbsent or _truthy(self.expr(guard, ctx)):
                    self._arm_body(arm, ctx)
                return

    def _arm_body(self, arm, ctx):
        """RETURN: None, always. Runs one groove arm's body: emit-steps emit
                  (the groove owns the pacing, so no extra rest), plain
                  statements run.
        """
        for statement in arm.body:
            if isinstance(statement, A.EmitStep):
                if not isinstance(statement.target, A.EmitNone):
                    self._emit_call(statement.target, ctx)
            else:
                self.run_block_statement(statement, ctx)

    def _emit_call(self, call, ctx):
        """RETURN: None, always. One clockwork emission: the call target
                  routed exactly like an effect's spawn (raw event enqueued,
                  definition activated).
        """
        self.run_effect(
            A.Effect(marker="=>", action=A.Spawn(
                call=call, every=NodeAbsent, handle=NodeAbsent)), ctx)

    # -- command blocks -----------------------------------------------------

    def run_block(self, block, ctx, outermost=False):
        """RETURN: None, always. Executes the block's statements in order;
                  at the OUTERMOST body a 'dropto:' lands on its forward
                  exit-label (SEMANTICS 7) and execution resumes there.
        """
        statements = list(block.statements)
        index = 0
        while index < len(statements):
            statement = statements[index]
            if isinstance(statement, A.ExitLabel):
                index += 1
                continue
            try:
                self.run_block_statement(statement, ctx)
            except _DropTo as jump:
                if not outermost:
                    raise
                for ahead in range(index + 1, len(statements)):
                    stmt = statements[ahead]
                    if isinstance(stmt, A.ExitLabel) \
                            and stmt.label.segments[0] == jump.label:
                        index = ahead
                        break
            index += 1

    def run_block_statement(self, statement, ctx):
        """RETURN: None, always. Executes one statement of a command block --
                  the R-13 set plus the R-14 escapes ('dropto:' raises to the
                  outermost body; break/continue raise to the enclosing
                  loop).
        """
        match statement:
            case A.Mutation():
                self.mutate(statement, ctx)
            case A.If():
                for arm in statement.arms:
                    if _truthy(self.expr(arm.cond, ctx)):
                        self.run_block(arm.block, ctx)
                        return
                if statement.els is not NodeAbsent:
                    self.run_block(statement.els, ctx)
            case A.Match():
                value = self.expr(statement.scrutinee, ctx)
                for case in statement.cases:
                    if self._pattern_matches(case.pattern, value, ctx):
                        self.run_block(case.block, ctx)
                        return
            case A.For():
                for item in _iterable(self.expr(statement.source, ctx)):
                    ctx.locals[statement.var.segments[0]] = item
                    try:
                        self.run_block(statement.block, ctx)
                    except _Break:
                        break
                    except _Continue:
                        continue
            case A.Count():
                lo = _number(self.expr(statement.lo, ctx))
                hi = _number(self.expr(statement.hi, ctx))
                step = 1.0 if statement.step is NodeAbsent \
                       else _number(self.expr(statement.step, ctx))
                if statement.type_ == "int":
                    lo, hi, step = int(lo), int(hi), int(step)
                value = lo
                while value <= hi:
                    ctx.locals[statement.var.segments[0]] = value
                    try:
                        self.run_block(statement.block, ctx)
                    except _Break:
                        break
                    except _Continue:
                        pass
                    value = value + step
            case A.CountWith():
                start = 0 if statement.start is NodeAbsent \
                        else _number(self.expr(statement.start, ctx))
                if statement.type_ == "int":
                    start = int(start)
                index = start
                for item in _iterable(self.expr(statement.source, ctx)):
                    ctx.locals[statement.index.segments[0]] = index
                    ctx.locals[statement.var.segments[0]] = item
                    try:
                        self.run_block(statement.block, ctx)
                    except _Break:
                        break
                    except _Continue:
                        pass
                    index = index + (1 if statement.type_ == "int"
                                     else 1.0)
            case A.DropTo():
                raise _DropTo(statement.label.segments[0])
            case A.Break():
                raise _Break()
            case A.Continue():
                raise _Continue()
            case _:
                pass

    def _pattern_matches(self, pattern, value, ctx):
        """RETURN: bool, True exactly when 'value' meets the case pattern:
                  a literal equals, a Range holds inclusively (SEMANTICS 8),
                  a glob matches the string form, the Wildcard always.
        """
        if isinstance(pattern, A.Wildcard):
            return True
        if isinstance(pattern, A.Range):
            lo = _number(self.expr(pattern.lo, ctx))
            hi = _number(self.expr(pattern.hi, ctx))
            return lo <= _number(value) <= hi
        if isinstance(pattern, ConstantLeaf):
            if str(pattern.kind) == "glob":
                return fnmatch.fnmatchcase(str(value), pattern.text)
            return self._constant(pattern) == value
        return False

    def mutate(self, statement, ctx):
        """RETURN: None, always. Executes one mutation: the lvalue place
                  (binding member, optionally indexed) receives the
                  operator-combined value; the write is traced.
        """
        lvalue = statement.lvalue
        leaf = lvalue.name if isinstance(lvalue, A.DataAccess) else lvalue
        store, member = self._place_of(leaf, ctx)
        rhs = self.expr(statement.rhs, ctx)
        if isinstance(lvalue, A.DataAccess) and lvalue.steps:
            container = store.get(member)
            index = self.expr(lvalue.steps[0], ctx)
            if isinstance(container, list):
                index = int(_number(index))
                while len(container) <= index:
                    container.append(0.0)
                container[index] = _apply_op(statement.op,
                                             container[index], rhs)
            elif isinstance(container, dict):
                container[index] = _apply_op(statement.op,
                                             container.get(index, 0.0), rhs)
            self.line("set    %s[%r] %s %s"
                      % (".".join(leaf.segments), index, statement.op,
                         _fmt(rhs)))
            return
        old = store.get(member, 0.0)
        store[member] = _apply_op(statement.op, old, rhs)
        self.line("set    %s %s %s -> %s"
                  % (".".join(leaf.segments), statement.op, _fmt(rhs),
                     _fmt(store[member])))

    def _place_of(self, leaf, ctx):
        """RETURN: (dict, str), the store and key the binding-qualified
                  lvalue names: the level instance's members for e/b/a/c
                  heads (SEMANTICS 9 admitted them; 's' was rejected at
                  elaborate and never reaches here).
        """
        head = leaf.access.target[0]
        member = leaf.access.residue[0]
        store = {"e": ctx.e,
                 "b": ctx.b.members if ctx.b else {},
                 "a": ctx.a.members if ctx.a else {},
                 "c": ctx.c.members if ctx.c else {}}[head]
        return store, member

    # -- expressions --------------------------------------------------------

    def expr(self, node, ctx):
        """RETURN: object, the expression's value under the context: numbers
                  as float/int, truths as bool, strings/globs as str,
                  collections as list/dict -- every read routed by the
                  seated recipe, never by name.
        """
        match node:
            case ConstantLeaf():
                return self._constant(node)
            case A.BinOp():
                return _apply_bin(node.op,
                                  self.expr(node.lhs, ctx),
                                  self.expr(node.rhs, ctx))
            case A.Not():
                return not _truthy(self.expr(node.operand, ctx))
            case A.Neg():
                return -_number(self.expr(node.operand, ctx))
            case A.Ternary():
                if _truthy(self.expr(node.cond, ctx)):
                    return self.expr(node.then, ctx)
                return self.expr(node.els, ctx)
            case A.DataAccess():
                value = self.read(node.name, ctx)
                for step in node.steps:
                    index = self.expr(step, ctx)
                    if isinstance(value, list):
                        value = value[int(_number(index))]
                    elif isinstance(value, dict):
                        value = value.get(index, 0.0)
                    else:
                        value = 0.0
                return value
            case A.Call():
                return self.read(node.name, ctx)
            case ReferenceLeaf():
                return self.read(node, ctx)
            case A.Comprehension():
                return self._comprehend(node, ctx)
            case _:
                return 0.0

    def read(self, leaf, ctx):
        """RETURN: object, the value the reference's RECIPE names: a binding
                  member off the level instance (unknown member 0.0, P-4), a
                  local off the context frame, a declared member off its
                  owning instance; anything else 0.0.
        """
        access = leaf.access
        if access.kind == "binding":
            head = access.target[0]
            if head == "s":
                return ctx.params.get(access.residue[0], 0.0)
            store = {"e": ctx.e,
                     "b": ctx.b.members if ctx.b else {},
                     "a": ctx.a.members if ctx.a else {},
                     "c": ctx.c.members if ctx.c else {}}[head]
            return store.get(access.residue[0], 0.0)
        if access.kind == "local":
            name = access.target[0]
            if name in ctx.locals:
                return ctx.locals[name]
            return ctx.params.get(name, 0.0)
        if access.kind == "declaration":
            inst = self.instance(access.target[:-1] or ("<module>",))
            return inst.members.get(access.target[-1], 0.0)
        if access.residue:
            inst = self.instance(access.target)
            return inst.members.get(access.residue[0], 0.0)
        return 0.0

    def _comprehend(self, node, ctx):
        """RETURN: list, the comprehension's elements: the chained
                  generators drive their variables over their sources
                  (innermost last), the optional condition filters, the
                  element expression produces (R-17).
        """
        results = []

        def generate(index):
            """RETURN: None, always. Recurses one generator level deep,
                      appending an element per surviving variable tuple.
            """
            if index == len(node.generators):
                results.append(self.expr(node.element, ctx))
                return
            generator = node.generators[index]
            source = _iterable(self.expr(generator.source, ctx))
            names = [v.segments[0] for v in generator.variables]
            for item in source:
                values = item if isinstance(item, (list, tuple)) else (item,)
                for name, value in zip(names, values):
                    ctx.locals[name] = value
                if generator.cond is not NodeAbsent \
                        and not _truthy(self.expr(generator.cond, ctx)):
                    continue
                generate(index + 1)

        generate(0)
        return results

    def _constant(self, leaf):
        """RETURN: object, the machine value of a constant leaf: int, float,
                  bool, or the raw text for strings and globs (quotes
                  stripped for strings).
        """
        kind = str(leaf.kind)
        if kind == "int":
            return int(leaf.text)
        if kind == "float":
            return float(leaf.text)
        if kind == "bool":
            return leaf.text == "true"
        if kind == "string":
            return leaf.text.strip('"')
        return leaf.text


class _Ctx:
    """RETURN: never a value itself -- one execution context: the level
              instances behind the bindings (e as the fired payload dict, b/
              a/c as Instances, s as the parameter dict), the local frame of
              loops and comprehensions, and the event currently dispatched.
    """

    def __init__(self, machine, inst, e=None, b=None, a=None, c=None,
                 s=None):
        self.machine    = machine
        self.inst       = inst
        self.e          = e if e is not None else {}
        self.b          = b
        self.a          = a
        self.c          = c
        self.params     = s if s is not None else {}
        self.locals     = {}
        self.event_name = ()

    def with_params(self, frame):
        """RETURN: _Ctx, this context with 's.' rebound to 'frame' -- the
                  named-cause evaluation context (P-6), everything else
                  shared.
        """
        clone = _Ctx(self.machine, self.inst, e=self.e, b=self.b, a=self.a,
                     c=self.c, s=frame)
        clone.locals = self.locals
        clone.event_name = self.event_name
        return clone


# -- small pure helpers -------------------------------------------------------

def _zero_of(type_node):
    """RETURN: object, the P-5 zero value of a declared type: 0.0 float,
              0 int, False bool, "" string, [] list, {} dict, an all-0.0
              field dict for a struct, 0.0 for a named type.
    """
    if isinstance(type_node, A.BuiltinType):
        return {"int": 0, "float": 0.0, "bool": False,
                "string": ""}[type_node.kind]
    if isinstance(type_node, A.ListType):
        return []
    if isinstance(type_node, A.DictType):
        return {}
    if isinstance(type_node, A.StructType):
        return {field.segments[0]: 0.0 for field in type_node.fields}
    return 0.0


def _truthy(value):
    """RETURN: bool, the truth of a guard value: bools as they are, numbers
              non-zero, strings non-empty, collections non-empty.
    """
    return bool(value)


def _number(value):
    """RETURN: float|int, the numeric reading of 'value' -- numbers pass,
              bools count 1/0, everything else reads 0.0.
    """
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return value
    return 0.0


def _apply_bin(op, lhs, rhs):
    """RETURN: object, 'lhs op rhs' for the expression operators of R-4:
              arithmetic over numbers, comparisons yielding truths, and/or
              over truths.
    """
    if op == "and":
        return _truthy(lhs) and _truthy(rhs)
    if op == "or":
        return _truthy(lhs) or _truthy(rhs)
    if op == "==":
        return lhs == rhs                  # structural over containers
    if op == "!=":
        return lhs != rhs
    if op in ("in", "not in"):
        held = _contains(rhs, lhs)
        return held if op == "in" else not held
    numeric = {"<":  lambda a, b: a < b,   "<=": lambda a, b: a <= b,
               ">":  lambda a, b: a > b,   ">=": lambda a, b: a >= b,
               "+":  lambda a, b: a + b,   "-":  lambda a, b: a - b,
               "*":  lambda a, b: a * b,   "/":  lambda a, b: a / b
                                                 if b else 0.0}
    # "/" by zero yields 0.0 -- pre-handler runtime only: SEMANTICS 21
    # rejects every division that is not provably nonzero, so this branch
    # serves nothing a clean front half admits; it keeps the machine total.
    return numeric[op](_number(lhs), _number(rhs))


def _contains(container, value):
    """RETURN: bool, True exactly when 'value' is held by 'container': an
              element of a list, a KEY of a dict, a substring of a string;
              anything else holds nothing.
    """
    if isinstance(container, list):
        return value in container
    if isinstance(container, dict):
        return value in container
    if isinstance(container, str):
        return str(value) in container
    return False


def _apply_op(op, old, rhs):
    """RETURN: object, the mutated value: '=' replaces; '+=' '-=' '*=' '/='
              combine numerically ('/=' by zero reads 0.0).
    """
    if op == "=":
        return rhs
    return _apply_bin(op[0], old, rhs)


def _iterable(value):
    """RETURN: list, the iteration view of a collection source: a list as
              is, a dict's (key, value) pairs in key order, anything else
              empty.
    """
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [(k, value[k]) for k in sorted(value, key=str)]
    return []


def _fmt(value):
    """RETURN: str, the byte-stable trace form of a value: floats with one
              decimal, everything else via repr-free plain forms.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return "%.1f" % value
    if isinstance(value, list):
        return "[" + ", ".join(_fmt(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join("%s: %s" % (_fmt(k), _fmt(value[k]))
                               for k in sorted(value, key=str)) + "}"
    return str(value)


def _fmt_payload(payload):
    """RETURN: str, the trace suffix for an event payload -- '(k=v, ...)' in
              key order, empty when the payload is.
    """
    if not payload:
        return ""
    return "(" + ", ".join("%s=%s" % (k, _fmt(payload[k]))
                           for k in sorted(payload)) + ")"
