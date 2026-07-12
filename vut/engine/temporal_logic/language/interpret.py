"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

INTERPRET -- direct execution of the decorated AST: the semantics ORACLE.

A tree-walking interpreter over SemanticModules. It is the FIRST CONSUMER of
the serialisation boundary and honours it strictly: everything it needs it
reads off the typed tree and the seated RECIPES (Access) -- no name is ever
re-resolved here, no unit-internal surface is touched. Every future emitter
earns its green by matching this interpreter's event traces, not by being
read carefully.

SETTLED LAW EXECUTED (LANGUAGE.txt, pipe ruling):
    - '=x=>' deactivates exactly the deactivable kinds (behavior member,
      recurring-emission handle); events and blocks are not deactivable
      (SEMANTICS 1; the reactor row's re-speak is flagged in OPEN --
      construction is standing, destruct is the end).
    - 'every: n' emits once per n (seconds, virtual); 'as:' binds a handle;
      ownership is the constructing reactor's -- destruct auto-cancels
      (R-15).
    - ~ENTRY / ~EXIT run on a behavior's arming / disarming; no trigger,
      no guard.
    - THE PIPE MODEL: a channel is a publish/subscribe object the reactor
      HAS; wiring subscribes; emission publishes ('to <chan>' one channel,
      suffix-less FANS: all outs plus self); delivery walks live
      subscribers (a destructed one reads Nothing, skipped); zero live
      subscribers is the 'drop <chan> <event>' line. The bus is no more.

PROVISIONAL RULINGS (P-n; each one line to correct -- report lists them):
    P-1  Dispatch: ONE FIFO queue of routed deliveries. A delivery is
         processed to completion -- every matching causality of the
         receiver's armed behaviors, in declaration order -- before the
         next; effects run left to right; emitted events APPEND to the
         queue (breadth, no re-entrant dispatch).
    P-1b Guards of one delivery evaluate against the state AT ARRIVAL:
         the matched set is fixed FIRST, effects then run in declaration
         order -- an effect of this delivery never changes which of its
         guards held (the synchronous-instant law).
    P-3  Time is VIRTUAL: the driver calls advance(seconds); recurring
         emissions fire at their multiples, oldest due first.
    P-4  Guards evaluate at dispatch time over current member state; 'e.'
         reads the fired event's payload; an unknown member reads 0.0.
    P-5  Members initialise per declared type: float 0.0, int 0, bool False,
         string "", list [], dict {}, struct all-0.0; parameters take the
         construction call's arguments, else their D-11 default, else 0.0.
    P-6  A named-cause use hot(v) matches its definition's event with the
         definition's guard evaluated under s.<param> bound to the use-site
         arguments.
    P-7  RETIRED (R-25): the tick-paced clockwork left the language; the
         law of its successor (the pull-driven clockwork) lands with the
         work construct.
______________________________________________________________________________
"""
import fnmatch
import re
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


class _Nothing:
    """RETURN-note (class): the runtime face of 'Nothing' (R-38) -- one
    shared instance; equality only with itself; prints as 'Nothing'."""
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    def __repr__(self):
        return "Nothing"


NOTHING = _Nothing()


class _Signal(Exception):
    """RETURN-note: not a value carrier in the language sense -- the Python
    vehicle of an exit: (LANGUAGE 12.4): 'name' the variant, 'payload' the
    evaluated argument tuple. Caught at the call site and matched against
    the handler; a signal is a branch taken, not a value (12.10).
    """
    def __init__(self, name, payload):
        super().__init__(name)
        self.name, self.payload = name, payload


class _Yield(Exception):
    """The Python vehicle of tick: -- carries the per-tick out-bundle upward
    to the generator driver (LANGUAGE 13.3, R-41.1)."""
    def __init__(self, outs):
        super().__init__("tick")
        self.outs = outs


class _WorkContext:
    """RETURN-note (class): the callee-side context of one work run --
    'locals' the panel-bound frame plus body locals; quacks like the
    reactive ctx for expr/mutate (no bindings, no event).
    """
    def __init__(self, engine, work, frame):
        self.engine = engine
        self.work = work
        self.locals = frame
        self.bindings = {}
        self.event_name = None


class _ClockworkRun:
    """RETURN-note (class): one wound clockwork -- a resumable body walk.
    next() runs the body until the following tick: (returning its bundle)
    or its end/finish: (raising _Signal('finished')); an exit: raises its
    own signal (LANGUAGE 13.4). repr is byte-stable (traces print it).
    """
    def __init__(self, engine, node, frame):
        self._name = ".".join(node.signature.name.segments)
        wctx = _WorkContext(engine, node, frame)
        def drive():
            try:
                yield from engine.gen_statements(node.body, wctx)
            except _Finished:
                pass
        self._gen = drive()

    def next(self):
        try:
            return next(self._gen)
        except StopIteration:
            raise _Signal("finished", ())

    def __repr__(self):
        return "<clockwork %s wound>" % self._name


class _Finished(Exception):
    """The Python vehicle of a work body reaching give: -- carries the
    out-bundle in declaration order (LANGUAGE 12.3/12.4, R-41.4)."""
    def __init__(self, outs):
        super().__init__("give")
        self.outs = outs


class Instance:
    """RETURN: never a value itself -- the scope-default instance of one
              definition (or of one implicit level default): its member
              state, parameter values, activity, cancellation handles, and
    """

    def __init__(self, qualified, kind):
        self.qualified = qualified
        self.kind      = kind
        self.members   = {}
        self.params    = {}
        self.active    = False
        self.active_behaviors = set()   # reactor ruling: the armed set
        self.handles   = {}          # handle name -> recurring emission
        self.active_child = None     # an aspect's one active behaviour


class Recurring:
    """RETURN: never a value itself -- one 'every:' emission: what to emit,
              its period, its next due time, and the owning instance (whose
              deactivation auto-cancels it, R-15); 'to_channel' the routed
              suffix of the spawn ('' = suffix-less: the send FANS, pipe
              ruling) -- honoured when the owner is a CONSTRUCTED reactor.
    """

    def __init__(self, event, payload, period, owner, now, to_channel=""):
        self.event      = event
        self.payload    = payload
        self.period     = period
        self.due        = now + period
        self.owner      = owner
        self.alive      = True
        self.to_channel = to_channel


class Channel:
    """RETURN: never a value itself -- one PUBLISH/SUBSCRIBE object (pipe
              ruling): the reactor HAS it (created and destructed with it,
              named in its panel); it KNOWS its subscribers -- (instance,
              in-channel-name) pairs; delivery walks them (known-hub law:
              a destructed subscriber is skipped); zero subscribers is the
              'drop' trace line.
    """

    def __init__(self, name, owner):
        self.name        = name
        self.owner       = owner
        self.subscribers = []           # [(instance, in_channel_name)]


class ReactorInstance(Instance):
    """RETURN: never a value itself -- one CONSTRUCTED reactor (pipe
              ruling): 'a = lamp(...);' builds it STANDING -- no on/off
              switch; a 'reactor' arms its FIRST declared behavior, a
              'reactor++' ALL of them. It owns its out channels and its
              self channel (they die with it); 'destructed' is the
              known-hub face delivery reads.
    """

    def __init__(self, label, node):
        super().__init__(qualified=(label,), kind=node.mode)
        self.label      = label
        self.node       = node
        self.destructed = False
        self.outs = {c.segments[0]: Channel(c.segments[0], self)
                     for c in node.outs}
        self.self_channel = Channel(".", self)
        # pipe ruling: the self channel is how the reactor hears its OWN
        # emissions -- its one standing subscriber is the reactor itself,
        # receive-routed to the '.' groups.
        self.self_channel.subscribers.append((self, "."))


class FeederInstance:
    """RETURN: never a value itself -- one wound harness FEEDER (pipe
              ruling, provided kind): 'f = script("...")' holds the
              written event sequence and ONE out channel; play() replays
              one event per drain step. An entry is an event name with an
              OPTIONAL D-28 named-argument payload (R-42) --
              'dial_turned(delta = 2.5)' -- whose fields travel as the
              event's payload and read through 'e.'; values are literals
              of the lexical laws (bare digits int, dot or exponent marks
              float, quoted "..." a string). A malformed entry refuses
              loudly at winding: a golden master never guesses.
    """

    def __init__(self, label, text):
        self.label      = label
        self.destructed = False
        self.out        = Channel("", self)
        self.events     = []            # [(event name, payload dict)]
        for entry in (s.strip() for s in _split_entries(text)):
            if not entry:
                continue
            self.events.append(_parse_feed_entry(entry))


def _split_entries(text):
    """RETURN: list, the script string cut at every ';' standing OUTSIDE a
              quoted "..." literal -- a payload string may carry ';'
              without ending its entry (R-42).
    """
    parts, current, quoted = [], [], False
    for ch in text:
        if ch == '"':
            quoted = not quoted
            current.append(ch)
        elif ch == ";" and not quoted:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


def _parse_feed_entry(entry):
    """RETURN: (str, dict), the event name and its payload from one script
              entry (R-42): 'name' bare, or 'name(field = literal, ...)'.

    Raises RuntimeError on any malformed entry -- unclosed parens, a
    missing '=', an unreadable literal -- naming the entry verbatim.
    """
    m = re.fullmatch(r'([A-Za-z_]\w*)\s*(\((.*)\))?', entry, re.DOTALL)
    if m is None:
        raise RuntimeError("feeder entry %r is not "
                           "'name' or 'name(field = literal, ...)' (R-42)"
                           % entry)
    name, payload = m.group(1), {}
    if m.group(2) is not None:
        body = m.group(3).strip()
        for field in (_split_fields(body) if body else ()):
            fm = re.fullmatch(r'\s*([A-Za-z_]\w*)\s*=\s*(.+?)\s*', field,
                              re.DOTALL)
            if fm is None:
                raise RuntimeError("feeder payload field %r is not "
                                   "'field = literal' (R-42, D-28)" % field)
            payload[fm.group(1)] = _feed_literal(fm.group(2), entry)
    return name, payload


def _split_fields(body):
    """RETURN: list, the payload body cut at every ',' standing outside a
              quoted "..." literal.
    """
    parts, current, quoted = [], [], False
    for ch in body:
        if ch == '"':
            quoted = not quoted
            current.append(ch)
        elif ch == "," and not quoted:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


def _feed_literal(text, entry):
    """RETURN: str, the unquoted string of a quoted "..." literal.
              int, for bare digits (optional sign).
              float, where the dot or the exponent marks it (the
              exponent-floats ruling: '1e-6', '2.5e3', '1E+10').

    Raises RuntimeError where none of the three literal laws reads it.
    """
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    if re.fullmatch(r'[+-]?\d+', text):
        return int(text)
    if re.fullmatch(r'[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?', text) \
            and (("." in text) or ("e" in text) or ("E" in text)):
        return float(text)
    raise RuntimeError("feeder payload value %r in %r is no literal of "
                       "the lexical laws (int, float, or \"string\") "
                       "(R-42)" % (text, entry))


class Machine:
    """RETURN: never a value itself -- one executable world over a list of
              SemanticModules: the definition index, the routed event
              queue, virtual time, recurring emissions, and the trace.

    Drive it as a PLANT (pipe ruling): run('<wiring work>') constructs,
    wires, and winds; step()/play() replay the feeders; advance() moves
    virtual time. Read the behaviour off trace() -- the byte-stable line
    list the GOOD suite locks. The bus is no more: every event travels a
    channel.
    """

    def __init__(self, modules):
        self.defs      = {}          # qualified -> (definition node, module)
        self.queue     = deque()     # routed deliveries:
                                     # (instance, in_channel, event, payload)
        self.feeders   = []          # wound feeders, construction order
        self.now       = 0.0
        self.recurring = []
        self.lines     = []
        for module in modules:
            self._index(module.file_node.items, scope=())

    # -- construction -------------------------------------------------------

    def _index(self, items, scope):
        """RETURN: None, always. Records every definition node under its
                  fully-qualified name, recursing through namespaces --
                  the instance registry's ground truth.
        """
        for item in items:
            if isinstance(item, A.Namespace):
                self._index(item.items, scope + tuple(item.name.segments))
            elif isinstance(item, (A.Reactor,
                                   A.DefCause, A.Work, A.ClockworkDef)):
                key = scope + tuple(item.signature.name.segments)
                if isinstance(item, A.Work) \
                        and len(item.signature.name.segments) == 2 \
                        and isinstance(self.defs.get(key), list):
                    self.defs[key].append(item)     # overload joins (R-32)
                elif isinstance(item, A.Work) \
                        and len(item.signature.name.segments) == 2:
                    self.defs[key] = [item]         # first of a set
                else:
                    self.defs[key] = item
            elif isinstance(item, A.ClassDef):
                key = scope + tuple(item.signature.name.segments)
                self.defs[key] = item
                for work in item.works:
                    wkey = key + tuple(work.signature.name.segments)
                    if wkey not in self.defs:      # a completion wins over
                        self.defs[wkey] = work     # its semi-declaration

    def _init_members(self, inst, node):
        """RETURN: None, always. Initialises the instance's members from the
                  definition body's member declarations (R-41.10; P-5 zero
                  values per type) and its parameters from the D-11
                  defaults.
        """
        for decl in getattr(node, "members", ()):
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
            # pipe ruling: every owner is a constructed reactor; the due
            # emission routes like any of its emissions (fan or 'to').
            self.routed_emit(nxt.owner, nxt.event, dict(nxt.payload),
                             nxt.to_channel)
            self.drain()
        self.now = target

    def drain(self):
        """RETURN: None, always. Processes the queue to exhaustion: one event
                  fully dispatched -- every matching causality of every
                  subscriber's in-channel, declaration order within the
                  receiver, before the next entry (P-1); every entry is a
                  ROUTED delivery -- the bus died with the pipe build.
        """
        while self.queue:
            inst, in_channel, event, payload = self.queue.popleft()
            self.line("event  %s.%s %s%s"
                      % (inst.label, in_channel, ".".join(event),
                         _fmt_payload(payload)))
            self.dispatch_routed(inst, in_channel, event, payload)

    def trace(self):
        """RETURN: str, the full trace, one line per observable step -- the
                  oracle text a GOOD locks.
        """
        return "\n".join(self.lines)

    def line(self, text):
        """RETURN: None, always. Appends one trace line."""
        self.lines.append(text)

    # -- dispatch -----------------------------------------------------------

    def _context_of(self, key, inst):
        """RETURN: _Ctx, the binding context of one reactor holder: the
                  bare-dot self binding reaches the reactor's own members
                  (reactor ruling -- behaviors own no state).
        """
        return _Ctx(self, inst, e={}, self_=inst, s=inst.params)

    # -- the pipe model (pipe ruling) ----------------------------------------

    def construct_reactor(self, label, node, args, ctx):
        """RETURN: ReactorInstance, built STANDING (pipe ruling: no on/off
                  switch -- construction is activation): members
                  initialised, channels created, and the standing default
                  armed ('reactor' its FIRST declared behavior, 'reactor++'
                  ALL) with ~ENTRY running.
        """
        inst = ReactorInstance(label, node)
        self._init_members(inst, node)
        self.line("make   %s : %s" % (label,
                                      ".".join(node.signature.name.segments)))
        names = [b.signature.name.segments[0] for b in node.behaviors]
        initial = names[:1] if node.mode == "single" else names
        for name in initial:
            self.activate_behavior(inst, node, name)
        return inst

    def wire(self, statement, ctx):
        """RETURN: None, always. Executes one wire statement (WIRING IS
                  WORK): the destination subscribes to the source's out
                  channel -- the named one, or the source's single one for
                  the plain arrow (a feeder's single out for a feeder
                  source); the subscriber entry carries the DESTINATION
                  in-channel name the routed delivery selects.
        """
        source = ctx.locals.get(statement.source.segments[0])
        dest   = ctx.locals.get(statement.dest.segments[0])
        if isinstance(source, FeederInstance):
            channel = source.out
        else:
            name = statement.channel \
                   or next(iter(source.outs), "")
            channel = source.outs.get(name)
        in_channel = statement.channel
        if not in_channel:
            ins = tuple(c.segments[0] for c in dest.node.ins) \
                  if isinstance(dest, ReactorInstance) else ()
            in_channel = ins[0] if len(ins) == 1 else \
                         (channel.name if channel is not None else "")
        channel.subscribers.append((dest, in_channel))
        self.line("wire   %s --[%s]--> %s"
                  % (statement.source.segments[0],
                     channel.name or in_channel,
                     statement.dest.segments[0]))

    def publish(self, channel, event, payload):
        """RETURN: None, always. Delivers one event through a channel: every
                  subscriber receives it as a routed queue entry
                  (breadth, P-1; synchronously in the deliverer's thread --
                  the drain IS that thread); a DESTRUCTED subscriber reads
                  Nothing and is skipped (known-hub law); zero live
                  subscribers is the ruled trace line 'drop <chan> <event>'.
        """
        alive = [(inst, in_ch) for inst, in_ch in channel.subscribers
                 if not inst.destructed]
        if not alive:
            self.line("drop   %s %s" % (channel.name or ".",
                                        ".".join(event)))
            return
        for inst, in_channel in alive:
            self.queue.append((inst, in_channel, event, payload))

    def routed_emit(self, inst, event, payload, to_channel):
        """RETURN: None, always. One emission out of a constructed reactor
                  (pipe ruling): 'to <channel>' publishes on that one out
                  channel; suffix-less FANS -- every out channel plus the
                  self channel.
        """
        if to_channel:
            self.line("emit   %s.%s %s" % (inst.label, to_channel,
                                           ".".join(event)))
            self.publish(inst.outs[to_channel], event, payload)
            return
        self.line("emit   %s.* %s" % (inst.label, ".".join(event)))
        for name in inst.outs:
            self.publish(inst.outs[name], event, payload)
        self.publish(inst.self_channel, event, payload)

    def dispatch_routed(self, inst, in_channel, event, payload):
        """RETURN: None, always. Fires one delivered event at one
                  subscriber: the armed behaviors' causalities of the
                  matching CHANNEL GROUP -- '.' for the self channel; bare
                  (ungrouped) causalities belong to the panel's single
                  in-channel, or to the self channel where none is
                  declared. PHASE 1 fixes the matched set (P-1b), PHASE 2
                  runs the effects in declaration order.
        """
        if inst.destructed:
            return                       # known-hub law: reads Nothing
        node = inst.node
        ins = tuple(c.segments[0] for c in node.ins)
        bare_channel = ins[0] if len(ins) == 1 else "."  # group law:
                                         # several ins have no bare form
                                         # (elaborate rejected it)
        ctx = self._context_of(inst.qualified, inst)
        ctx.e = payload
        ctx.event_name = event
        fired = []
        for behavior in node.behaviors:
            if behavior.signature.name.segments[0] \
                    not in inst.active_behaviors:
                continue
            pools = [g.causalities for g in behavior.groups
                     if g.channel == in_channel]
            if in_channel == bare_channel:
                pools.append(behavior.causalities)
            for pool in pools:
                for causality in pool:
                    if self.cause_matches(causality.cause, event,
                                          payload, ctx):
                        fired.append((causality, ctx))
        for causality, carrier in fired:
            for effect in causality.effects:
                self.run_effect(effect, carrier)

    def run(self, name, args=()):
        """RETURN: None, always. The harness verb driving a PLANT: the
                  statement-form call of the named top-level work (the
                  wiring work); its constructions, wires, and feeders stand
                  afterwards, ready for play().
        """
        work = self.defs[tuple(name.split("."))]
        self.line("run    %s" % name)
        self.call_work(work, list(args), _Ctx(self, None))

    def step(self):
        """RETURN: bool, True when a feeder replayed -- ONE feeder round
                  (the harness step law): each wound, live feeder replays
                  ONE event onto its out channel, the queue drained to
                  exhaustion after each; False when every feeder stands
                  exhausted or destructed.
        """
        fed = False
        for feeder in self.feeders:
            if feeder.destructed or not feeder.events:
                continue
            event, payload = feeder.events.pop(0)
            self.line("feed   %s %s" % (feeder.label, event))
            self.publish(feeder.out, (event,), dict(payload))
            self.drain()
            fed = True
        return fed

    def play(self):
        """RETURN: None, always. Replays every wound feeder to exhaustion,
                  one step() round at a time.
        """
        while self.step():
            pass

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
        if access.kind == "behavior":
            # reactor ruling: 'A => Name' activates the behavior member in
            # THIS reactor -- resolved through the firing context, never a
            # global position.
            node = getattr(ctx.inst, "node", None) \
                   or self.defs.get(tuple(ctx.inst.qualified))
            if isinstance(node, A.Reactor):
                self.activate_behavior(ctx.inst, node, access.target[-1])
        elif spawn.every is not NodeAbsent:
            period = _number(self.expr(spawn.every, ctx))
            to_channel = "" if spawn.to_channel is NodeAbsent \
                         else spawn.to_channel.segments[0]
            emission = Recurring(event=tuple(access.target), payload={},
                                 period=period, owner=ctx.inst, now=self.now,
                                 to_channel=to_channel)
            self.recurring.append(emission)
            self.line("recur  %s every %.1fs"
                      % (".".join(access.target), period))
            if spawn.handle is not NodeAbsent:
                ctx.inst.handles[spawn.handle.segments[0]] = emission
        else:
            # pipe ruling: an emission is ROUTED -- 'to <channel>'
            # publishes on that out channel, suffix-less FANS to all out
            # channels plus self. The bus is no more.
            payload = {a.name: self.expr(a.value, ctx)
                       for a in ([] if spawn.call.args is NodeAbsent
                                 else spawn.call.args)
                       if isinstance(a, A.NamedArg)}
            to_channel = "" if spawn.to_channel is NodeAbsent \
                         else spawn.to_channel.segments[0]
            self.routed_emit(ctx.inst, tuple(access.target), payload,
                             to_channel)

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
        elif access.kind == "behavior":
            node = getattr(ctx.inst, "node", None) \
                   or self.defs.get(tuple(ctx.inst.qualified))
            if isinstance(node, A.Reactor):
                self.deactivate_behavior(ctx.inst, node, access.target[-1])
        # (reactor activation/deactivation by name DIED with the pipe
        # build: construction is standing, destruct is the end; the
        # SEMANTICS 1 deactivable-table re-speak is flagged in OPEN.)

    def activate_behavior(self, inst, node, name):
        """RETURN: None, always. Activates the named behavior member in a
                  reactor instance (reactor ruling): a no-op when already
                  armed; in a 'reactor' (state machine) the previously
                  active behavior deactivates FIRST -- one state at a time;
                  in a 'reactor++' (mode group) the set simply grows.
                  ~ENTRY causalities of the entered behavior run.
        """
        if name in inst.active_behaviors:
            return
        if node.mode == "single":
            for other in tuple(inst.active_behaviors):
                self.deactivate_behavior(inst, node, other)
        inst.active_behaviors.add(name)
        self.line("enter  %s.%s" % (".".join(inst.qualified), name))
        behavior = self._behavior_of(node, name)
        if behavior is not None:
            self._lifecycle_behavior(behavior, inst, "~ENTRY")

    def deactivate_behavior(self, inst, node, name):
        """RETURN: None, always. Disarms the named behavior member (a no-op
                  when inactive): its ~EXIT causalities run, then every
                  recurring emission the reactor owns... stays -- ownership
                  is the REACTOR's; auto-cancel rides reactor deactivation
                  (R-15), not the behavior flip.
        """
        if name not in inst.active_behaviors:
            return
        behavior = self._behavior_of(node, name)
        if behavior is not None:
            self._lifecycle_behavior(behavior, inst, "~EXIT")
        inst.active_behaviors.discard(name)
        self.line("leave  %s.%s" % (".".join(inst.qualified), name))

    def _behavior_of(self, node, name):
        """RETURN: Behavior, the reactor's behavior member of that name, if
                  declared. None, else.
        """
        for behavior in node.behaviors:
            if behavior.signature.name.segments[0] == name:
                return behavior
        return None

    def _lifecycle_behavior(self, behavior, inst, kind):
        """RETURN: None, always. Runs every causality of the behavior member
                  whose cause is the lifecycle event 'kind' -- no trigger,
                  no guard; the context is the REACTOR instance (reactor
                  ruling: behaviors own no state).
        """
        node = behavior
        ctx = self._context_of(inst.qualified, inst)
        for causality in node.causalities:
            target = causality.cause.target
            if isinstance(target, A.Lifecycle) and target.kind == kind:
                for effect in causality.effects:
                    self.run_effect(effect, ctx)

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
                index += 1        # both accounts (B-1/R-39): the bare label
                continue          # is a dead address; a catch region is
                                  # SKIPPED by normal flow -- signals enter
                                  # it via elseto: routing only (unbuilt)
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

    # -- works and clockworks (LANGUAGE 12/13; SEMANTICS 23 PARTIAL) --------

    def _resolve_work(self, access):
        """RETURN: Node, the Work/ClockworkDef the dotted access names --
                  None, else. Member works resolve through their class's
                  qualified name.
        """
        node = self.defs.get(tuple(access))
        if isinstance(node, list):
            return node                       # a constructor overload set
        if isinstance(node, (A.Work, A.ClockworkDef)):
            return node
        return None

    def _bind_panel(self, work, args, ctx):
        """RETURN: dict, the callee frame: in: entries bound from the call's
                  arguments BY DIRECTION (R-41.1) -- positionals in
                  declaration order, 'name = value' by name, panel defaults
                  filling the rest (LANGUAGE 12.5).
        """
        entries = tuple(work.panel.ins)
        frame, positional = {}, []
        for arg in args:
            if isinstance(arg, A.NamedArg):
                frame[arg.name] = self.expr(arg.value, ctx)
            else:
                positional.append(self.expr(arg, ctx))
        cursor = 0                       # positionals fill the UNCLAIMED
        for entry in entries:            # inputs in declaration order (a
            name = entry.name.segments[0]  # named selector may lead, R-33)
            if name in frame:
                continue
            if cursor < len(positional):
                frame[name] = positional[cursor]
                cursor += 1
            elif entry.default is not NodeAbsent:
                frame[name] = self.expr(entry.default, ctx)
        for entry in work.panel.outs:
            name = entry.name.segments[0]
            if entry.default is not NodeAbsent:
                frame[name] = self.expr(entry.default, ctx)
        return frame

    def call_work(self, work, args, ctx):
        """RETURN: tuple, the out-bundle in declaration order after the
                  body reached give:. Raises _Signal when an exit: fires
                  (LANGUAGE 12.3: the sum -- all outputs or one signal).
        """
        frame = self._bind_panel(work, args, ctx)
        if isinstance(work, A.ClockworkDef):
            return (_ClockworkRun(self, work, frame),)   # winding (13.4)
        callee = _WorkContext(self, work, frame)
        statements = list(work.body)
        index = 0
        try:
            while index < len(statements):
                statement = statements[index]
                if isinstance(statement, A.ExitLabel):
                    index += 1        # B-1/R-39: bare = dead address; a
                    continue          # catch region is SKIPPED by normal
                                      # flow (elseto: routing unbuilt)
                try:
                    self.run_block_statement(statement, callee)
                except _DropTo as jump:
                    for ahead in range(index + 1, len(statements)):
                        stmt = statements[ahead]
                        if isinstance(stmt, A.ExitLabel) \
                                and stmt.region is NodeAbsent \
                                and stmt.label.segments[0] == jump.label:
                            index = ahead
                            break            # forward-only, bare only
                index += 1
        except _Finished as f:
            return f.outs
        raise _Signal("fell_off", ())          # unreachable under 12.4 law

    def aware_mutation(self, statement, ctx):
        """RETURN: None, always. The AWARE assignment (LANGUAGE 12.6): the
                  RHS work call runs; on finish the targets bind in
                  declaration order; on a signal the handler arms match
                  first-match, payload fields scoped to the arm; an absent
                  action is the shrug.
        """
        rhs = statement.rhs
        work = self._resolve_work(rhs.name.segments) \
               if isinstance(rhs, A.DataAccess) else None
        if work is None:                       # fallible primitive (12.9)
            try:
                self.mutate(statement, ctx)
            except ZeroDivisionError:
                sig = _Signal("div_by_zero", ())
                self.line("signal div_by_zero()")
                self.run_handler(statement.handler, sig, ctx)
            return
        args = [] if rhs.args is NodeAbsent else list(rhs.args)
        if isinstance(work, list):            # overload resolution (R-33):
            selector = args[0].name \
                       if args and isinstance(args[0], A.NamedArg) else None
            work = _select_overload(work, selector)    # by the named FIRST
                                              # argument, SEMANTICS 26
        targets = (statement.lvalue,) + tuple(statement.extra_lvalues)
        try:
            bundle = self.call_work(work, args, ctx)
        except _Signal as sig:
            self.line("signal %s%r" % (sig.name, tuple(sig.payload)))
            self.run_handler(statement.handler, sig, ctx)
            return
        for target, value in zip(targets, bundle):
            self._assign(target, value, ctx)

    def run_handler(self, handler, sig, ctx):
        """RETURN: None, always. Matches one signal against the handler's
                  arms, first-match (LANGUAGE 12.6): a named arm binds its
                  payload fields as locals of the arm's action; the bare
                  arm matches anything and binds nothing; an absent action
                  is the written shrug. Re-raises the signal when no arm
                  matches (exhaustiveness is elaborate's law; the runtime
                  stays honest).
        """
        for arm in handler.arms:
            if arm.variant is NodeAbsent:
                matched = True
            else:
                matched = arm.variant.segments[0] == sig.name
            if not matched:
                continue
            for field, value in zip(arm.fields, sig.payload):
                ctx.locals[field.segments[0]] = value
            action = arm.action
            if action is NodeAbsent:
                return                          # the shrug
            if isinstance(action, A.ExitSignal):
                payload = () if action.args is NodeAbsent else tuple(
                    self.expr(a, ctx) for a in action.args)
                raise _Signal(action.variant.segments[0], payload)
            self.run_block(action, ctx)
            return
        raise sig

    def gen_statements(self, statements, ctx):
        """YIELD: [0] tuple  each tick-bundle a clockwork body delivers, in
                            delivery order, walked GENERATIVELY so a tick:
                            inside any nested block suspends WITHOUT
                            unwinding its enclosing loops (LANGUAGE 13.3).

        Non-suspending statements execute through the ordinary dispatcher
        (whose Finish/ExitSignal raises propagate out untouched).
        """
        for statement in statements:
            yield from self.gen_statement(statement, ctx)

    def gen_statement(self, statement, ctx):
        """YIELD: [0] tuple  the tick-bundles this one statement delivers --
                            recursing generatively through if/match/for/
                            count bodies; every other statement runs via
                            run_block_statement and yields nothing.
        """
        match statement:
            case A.Tick():
                yield tuple(ctx.locals.get(e.name.segments[0])
                            for e in ctx.work.panel.outs)
            case A.If():
                for arm in statement.arms:
                    if _truthy(self.expr(arm.cond, ctx)):
                        yield from self.gen_statements(
                            arm.block.statements, ctx)
                        return
                if statement.els is not NodeAbsent:
                    yield from self.gen_statements(
                        statement.els.statements, ctx)
            case A.Match():
                value = self.expr(statement.scrutinee, ctx)
                for case_ in statement.cases:
                    if self._pattern_matches(case_.pattern, value, ctx):
                        yield from self.gen_statements(
                            case_.block.statements, ctx)
                        return
            case A.For() if not statement.pulls:
                for item in _iterable(self.expr(statement.source, ctx)):
                    ctx.locals[statement.var.segments[0]] = item
                    try:
                        yield from self.gen_statements(
                            statement.block.statements, ctx)
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
                        yield from self.gen_statements(
                            statement.block.statements, ctx)
                    except _Break:
                        break
                    except _Continue:
                        pass
                    value = value + step
            case _:
                self.run_block_statement(statement, ctx)

    def for_from(self, statement, ctx):
        """RETURN: None, always. The consumption loop 'for: v from: cw'
                  (LANGUAGE 13.5): each iteration pulls once; 'finished' IS
                  the loop's own end; any other signal matches the trailing
                  handler (absent handler re-raises -- exhaustiveness is
                  elaborate's law).
        """
        source = statement.source
        node = self._resolve_work(source.name.segments) \
               if isinstance(source, A.DataAccess) else None
        if isinstance(node, A.ClockworkDef):        # wind at the loop (13.5)
            args = [] if source.args is NodeAbsent else list(source.args)
            run = self.call_work(node, args, ctx)[0]
        else:
            run = self.expr(source, ctx)            # an already-wound run
        if not isinstance(run, _ClockworkRun):
            raise TypeError("for: ... from: expects a wound clockwork")
        while True:
            try:
                bundle = run.next()
            except _Signal as sig:
                if sig.name == "finished":
                    return
                self.line("signal %s%r" % (sig.name, tuple(sig.payload)))
                if statement.handler is NodeAbsent:
                    raise
                self.run_handler(statement.handler, sig, ctx)
                return
            value = bundle[0] if len(bundle) == 1 else bundle
            ctx.locals[statement.var.segments[0]] = value
            try:
                self.run_block(statement.block, ctx)
            except _Break:
                return
            except _Continue:
                continue

    def _assign(self, lvalue, value, ctx):
        """RETURN: None, always. Binds one aware-assignment target: a bare
                  name lands in the locals, a bound member through the
                  ordinary mutation place.
        """
        if isinstance(lvalue, A.KnownSite):
            lvalue = lvalue.target              # R-41.2: marker unwraps
        leaf = lvalue.name if isinstance(lvalue, A.DataAccess) else lvalue
        store, member = self._place_of(leaf, ctx)
        store[member] = value
        self.line("bind   %s = %r" % (".".join(leaf.segments), value))

    def run_block_statement(self, statement, ctx):
        """RETURN: None, always. Executes one statement of a command block --
                  the R-13 set plus the R-14 escapes ('dropto:' raises to the
                  outermost body; break/continue raise to the enclosing
                  loop).
        """
        match statement:
            case A.Give():                      # LANGUAGE 12.4 (R-37,
                raise _Finished(tuple(          # R-41.4): the out-bundle
                    ctx.locals.get(e.name.segments[0])   # leaves in
                    for e in ctx.work.panel.outs))       # declaration
                                                         # order (12.5);
                                                         # the written list
                                                         # is elaborate's
                                                         # check
            case A.Wire():                      # pipe ruling: WIRING IS WORK
                self.wire(statement, ctx)
            case A.Destruct():                  # R-37: the having ends HERE
                obj = statement.object
                leaf = obj.name if isinstance(obj, A.DataAccess) else obj
                name = leaf.segments[0]
                self.line("destruct %s" % ".".join(leaf.segments))
                if isinstance(ctx, _WorkContext):
                    held = ctx.locals.pop(name, None)
                                                # the name dies with the
                                                # having; disposal dispatch
                                                # rides the type document
                    if isinstance(held, (ReactorInstance, FeederInstance)):
                        held.destructed = True  # the hub's pointer zeroes:
                                                # every knower -- channel
                                                # subscriber lists included
                                                # -- reads Nothing from this
                                                # instant (HAVE_KNOW_BE (3))
                        for emission in self.recurring:
                            if emission.owner is held and emission.alive:
                                emission.alive = False   # R-15: ownership
                                self.line(                # ends with the
                                    "cancel (auto, destruct) %s"  # owner
                                    % ".".join(emission.event))
            case A.Tick():                      # LANGUAGE 13.3: deliver,
                raise _Yield(tuple(             # suspend until the pull
                    ctx.locals.get(e.name.segments[0])
                    for e in ctx.work.panel.outs))
            case A.ExitSignal():                # LANGUAGE 12.4: fault egress
                if statement.variant is NodeAbsent:
                    # R-41.7: bare exit: -- the nothing-more egress; the
                    # puller receives the built-in variant ('finished'
                    # today; the rename rides a flagged fork).
                    raise _Signal("finished", ())
                raise _Signal(statement.variant.segments[0],
                              () if statement.args is NodeAbsent else tuple(
                                  self.expr(a, ctx) for a in statement.args))
            case A.Mutation() if statement.handler is not NodeAbsent:
                self.aware_mutation(statement, ctx)
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
            case A.For() if statement.pulls:
                self.for_from(statement, ctx)
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
                  operator-combined value; the write is traced. A KnownSite
                  wrapper (R-41.2) unwraps -- the marker has no runtime
                  effect until the knowing model's runtime lands
                  (HAVE_KNOW_BE (3)).
        """
        lvalue = statement.lvalue
        if isinstance(lvalue, A.KnownSite):
            lvalue = lvalue.target
        leaf = lvalue.name if isinstance(lvalue, A.DataAccess) else lvalue
        # -- pipe ruling: 'a = TrafficLight(...);' is already a mutation +
        #    call -- SEMANTICS recognises reactor construction (no new
        #    grammar); 'f = script("...")' winds the harness feeder. Both
        #    build STANDING and store the instance in the body local; no
        #    'set' line -- construction traces as construction.
        if statement.op == "=" and not statement.extra_lvalues \
                and isinstance(ctx, _WorkContext) \
                and len(leaf.segments) == 1 \
                and isinstance(statement.rhs, A.DataAccess) \
                and statement.rhs.args is not NodeAbsent \
                and not statement.rhs.steps:
            label = leaf.segments[0]
            head = tuple(statement.rhs.name.segments)
            definition = self.defs.get(head)
            if isinstance(definition, A.Reactor):
                args = [self.expr(a.value if isinstance(a, A.NamedArg)
                                  else a, ctx)
                        for a in statement.rhs.args]
                ctx.locals[label] = self.construct_reactor(
                    label, definition, args, ctx)
                return
            if head == ("script",):
                text = str(self.expr(tuple(statement.rhs.args)[0], ctx))
                feeder = FeederInstance(label, text)
                ctx.locals[label] = feeder
                self.feeders.append(feeder)
                self.line("wind   %s : script" % label)
                return
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
        if isinstance(ctx, _WorkContext):
            return ctx.locals, leaf.segments[0]   # work port / body local
        head = leaf.access.target[0]
        member = leaf.access.residue[0]
        store = {"e": ctx.e,
                 "": ctx.self_.members}[head]   # '' = the bare-dot self
        return store, member

    # -- expressions --------------------------------------------------------

    def expr(self, node, ctx):
        """RETURN: object, the expression's value under the context: numbers
                  as float/int, truths as bool, strings/globs as str,
                  collections as list/dict -- every read routed by the
                  seated recipe, never by name.
        """
        match node:
            case A.NothingLeaf():
                return NOTHING
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
                # a signal-less work in expression position (12.6: no
                # signals -> no else: -> callable anywhere a value is):
                # dispatch the call, its single gives-value IS the value
                if node.args is not NodeAbsent:
                    target = self._resolve_work(node.name.segments)
                    if target is not None and not isinstance(target, list):
                        bundle = self.call_work(target, list(node.args), ctx)
                        return bundle[0] if len(bundle) == 1 else bundle
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
        if isinstance(ctx, _WorkContext):
            return ctx.locals.get(leaf.segments[0], 0.0)
        if access.kind == "binding":
            head = access.target[0]
            store = {"e": ctx.e,
                     "": ctx.self_.members}[head]   # '' = bare-dot self
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
    """RETURN: never a value itself -- one execution context (reactor
              ruling): 'e' the fired payload dict, 'self_' the REACTOR
              instance behind the bare-dot binding, 'params' the
              named-cause parameter frame (P-6), the local frame of loops
              and comprehensions, and the event currently dispatched.
    """

    def __init__(self, machine, inst, e=None, self_=None, s=None):
        self.machine    = machine
        self.inst       = inst
        self.e          = e if e is not None else {}
        self.self_      = self_ if self_ is not None else inst
        self.params     = s if s is not None else {}
        self.locals     = {}
        self.event_name = ()

    def with_params(self, frame):
        """RETURN: _Ctx, this context with 's.' rebound to 'frame' -- the
                  named-cause evaluation context (P-6), everything else
                  shared.
        """
        clone = _Ctx(self.machine, self.inst, e=self.e, self_=self.self_,
                     s=frame)
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


def _absence_norm(value):
    """RETURN: object, 'value' with Nothing read as its numeric face 0 --
              the EQUIVALENCE ruling: 'm != Nothing', 'm != 0', and bare
              'm' are one gate, so Nothing compares as zero. (Both runtime
              faces of absence normalise: the NOTHING sentinel and an
              unbound None.)
    """
    return 0 if value is NOTHING or value is None else value


def _truthy(value):
    """RETURN: bool, the truth of a guard value: Nothing and zero are
              false (the equivalence ruling: one absence), bools as they
              are, strings non-empty, collections non-empty.
    """
    return bool(_absence_norm(value))


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
        return _absence_norm(lhs) == _absence_norm(rhs)  # structural over
    if op == "!=":                                       # containers;
        return _absence_norm(lhs) != _absence_norm(rhs)  # Nothing reads 0
    if op in ("in", "not in"):
        held = _contains(rhs, lhs)
        return held if op == "in" else not held
    numeric = {"<":  lambda a, b: a < b,   "<=": lambda a, b: a <= b,
               ">":  lambda a, b: a > b,   ">=": lambda a, b: a >= b,
               "+":  lambda a, b: a + b,   "-":  lambda a, b: a - b,
               "*":  lambda a, b: a * b,   "/":  lambda a, b: a / b}
    # "/" by zero RAISES (D-26): SEMANTICS 21 admits a division only when
    # provably nonzero or handler-covered (LANGUAGE 12.9), so the raise is
    # always caught by the aware assignment's div_by_zero path.
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


def _select_overload(overloads, selector):
    """RETURN: Work, the overload whose FIRST input carries the selector's
              name (R-33, SEMANTICS 26) -- unique by the definition-site
              distinctness law; the first member if none matches (the run
              stays total; elaborate rejected the call shape already).
    """
    for work in overloads:
        entries = tuple(work.panel.ins)
        if entries and entries[0].name.segments[0] == selector:
            return work
    return overloads[0]


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
