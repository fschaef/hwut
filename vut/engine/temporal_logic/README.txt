===============================================================================
TEMPORAL LOGIC ENGINE  --  HWUT 2.0 Comparison Engine Component
DESIGN DOCUMENT
===============================================================================

STATUS
  The architecture in this document is settled. The concrete rule-file syntax
  is maintained in a separate file, SYNTAX.txt, and is still being drafted.
  Ongoing design discussion is recorded in DISCUSSIONS.txt; this README states
  the design as fact and does not reproduce the discussion that produced it.

COMPANION FILES
  SYNTAX.txt        Concrete syntax of rule files (events, objects, rules).
  DISCUSSIONS.txt   Running design log: resolved decisions, rejected
                    alternatives with rationale, and live questions.

VOCABULARY  --  three things, three names, used consistently throughout:
  TIME LINE     The sequence of events. Input and (expanded) output.
  RULE SET      The parsed rules plus the static cascade graph. Authored by a
                human as RULE FILES (plain text); see SYNTAX.txt.
  ENGINE        The component that runs the rule set against a time line. It
                owns the single OBJECT SPACE in which all events and objects
                live (see section 4).


-------------------------------------------------------------------------------
1. PURPOSE
-------------------------------------------------------------------------------

  The engine consumes a TIME LINE of events, runs a RULE SET against it, and
  produces a longer time line in which every consequence of those rules has
  been expanded. A thin separate layer then reads that output and produces a
  pass / fail verdict.

  The engine has exactly ONE mode. There is no separate "check mode" and no
  separate "simulate mode": the engine runs; verification is a property of the
  time line it produces, not an operation it performs.

  The origin of the input time line is outside the engine's concern. Events may
  be streamed live from a model or a system under test, or replayed from a
  recorded file -- to the engine these are indistinguishable: a sequence of
  events in time order.

  CORE CONSTRAINT
    The engine core is pure-Python-compatible and highly portable: no
    heavyweight dependencies, no platform-specific code in the core. Every
    decision in this document was taken with portability as a primary axis.


-------------------------------------------------------------------------------
2. PIPELINE  --  WHAT THE ENGINE DOES
-------------------------------------------------------------------------------

  The whole component, at a glance:

    RULE FILES                        (authored by a human; see SYNTAX.txt)
        |
        |  parsed once
        v
    +-----------+        +---------------------------------+
    | RULE SET  |        |            ENGINE               |
    | - rules   |------->|                                 |
    | - cascade |        |  for each input event, in time  |
    |   graph   |        |  order:                         |
    +-----------+        |    - fire matching rules        |
                         |    - expand cascades at T       |
    INPUT TIME LINE      |    - mutate the object space    |
    e1 e2 e3 ... eN  ----|--->                             |
    (ends with           |                                 |
     TERMINATION)        +----------------+----------------+
                                          |
                                          v
                              OUTPUT TIME LINE
                              (input events + every emitted event)
                                          |
                                          v
                         +----------------+----------------+
                         |          BAD LAYER              |
                         |  scan output for events whose   |
                         |  type is in the BAD set         |
                         +----------------+----------------+
                                          |
                                          v
                              VERDICT: pass, or fail + the
                              offending events as evidence

  The RULE SET watches the time line and derives new events from it. The ENGINE
  is the machinery that performs that watching and deriving. The BAD LAYER is
  not part of the engine; it is a separate, trivial pass over the output.


-------------------------------------------------------------------------------
3. THE MODEL
-------------------------------------------------------------------------------

  EVENTS
    Ephemeral, struct-like aggregates: named typed fields, optionally member
    functions (C-struct-like). An event exists only at the instant it occurs.
    'time' is an intrinsic struct field of every event -- a member like any
    other, not a separate annotation. 'dt' (delta since the previous event) is
    likewise intrinsic. The pair (event type, time) uniquely identifies an
    occurrence.

  OBJECTS
    Stateful aggregates persisting across time spans (e.g. a 'vehicle' with
    position, velocity, mass).

  RULES
    Declared in rule files. A rule file declares event structures, object
    structures, ordinary CONSEQUENCES, and ARMABLE UNITS.

  CONSEQUENCE
    Form:   on <trigger-event> [AND <guard>] : <body>
    The leading event is the TRIGGER; the consequence fires the instant that
    event occurs. The GUARD is a boolean expression evaluated at trigger time
    with full logic over object and event state. The BODY produces results
    (section 6). An ordinary consequence is ALWAYS LIVE.

  THE 'ANY' TRIGGER
    A consequence may use the trigger 'ANY', which matches every event type,
    including events produced by cascade expansion and including TERMINATION.
    'ANY' is the means to check purely state-dependent conditions after every
    event, e.g.:   on ANY AND (car.gas == 0) : emit FRUSTRATION

  TIME LINE TERMINATION
    Every input time line MUST end with a TERMINATION event. The engine
    validates this as a precondition and REJECTS an input time line that lacks
    it. TERMINATION is the guaranteed final instant at which any still-pending
    obligation can be judged (see section 5, and section 7 truncation note).

  NO PURE TIME TRIGGERS / THE ENGINE EMITS NOTHING ON ITS OWN INITIATIVE
    Every rule anchors to a real event. The engine has no time-based trigger,
    no wakeup queue, and no internal clock. Periodic behaviour (e.g. a TICK
    every 100 ms) is produced by whoever generates the INPUT time line, not by
    the engine. The engine only ever reacts to events it was fed.
      Rationale: an engine that emitted its own events would be generating a
      time line rather than validating a given one, contradicting section 1.
      A periodic-clock feature was considered and rejected for this reason; a
      convenience helper that pre-fills a time line with periodic TICKs belongs
      in the HWUT harness layer (section 9), outside the engine core.


-------------------------------------------------------------------------------
4. ARCHITECTURE  --  CONTROL PLANE AND DATA PLANE
-------------------------------------------------------------------------------

  The component is split into two planes with one clean seam between them.

    +========================= RULE FILE ===========================+
    |                                                               |
    |   CONTROL PLANE  (parsed by the DSL parser)                   |
    |   .........................................................   |
    |   . declarations . triggers . 'on .. AND .. :' . emit/arm/  .  |
    |   . guard position .......... . unarm (literal names) ......   |
    |                         |                                     |
    |                         | seam                                |
    |                         v                                     |
    |   DATA PLANE  (captured as opaque text, run by embedded Lua)  |
    |   .........................................................   |
    |   . { state-changing blocks } . member-function bodies .....   |
    |   . guard expressions ....................................     |
    |                                                               |
    +===============================================================+

         CONTROL PLANE                         DATA PLANE
         owns FORM                             owns SUBSTANCE
         -------------------                   ----------------------
         the DSL parser                        the embedded Lua VM
         struct/rule structure                 object state + values
         the cascade graph                     all data computation
         emit/arm/unarm verbs                  member functions
         (statically literal names)            guard evaluation

  THE ONE-OBJECT-SPACE INVARIANT
    There is exactly one object space: the Lua interpreter's table space. Every
    event instance and every simulation object exists there and ONLY there. The
    DSL parser builds no parallel object model and holds no simulation data; it
    produces structure (the parsed rule set and the static cascade graph) and,
    at runtime, drives the run -- but every value it reads or writes is read
    from / written to the single Lua object space.
      In short: the rules are parsed by us; the objects they operate on live in
      Lua. No marshalling, no mirror model, nothing to keep in sync.

  PARSING STRATEGY  (control plane)
    A small, hand-written, pure-Python recursive-descent parser. No
    parser-generator dependency. The control-plane grammar is small enough that
    a hand-written parser gives the best portability and the best domain-aware
    error messages at low cost.

  EMBEDDED LANGUAGE  (data plane)
    Lua. Chosen because it is tiny, is ANSI C with no dependencies (it builds
    everywhere -- portability), and is sandboxable by construction: the
    embedding builds the environment table handed to each script, so omitting
    os / io / dofile / loadstring etc. makes the filesystem, clock and network
    simply unreachable. There is no feature flag to forget; absence is the
    mechanism.

  WHY THE SPLIT, NOT 'WHOLE RULE FILE IN LUA'
    Making the entire rule file a Lua program was considered and rejected. It
    would surrender the static cascade check (section 5), domain-specific error
    messages, and the ability of the grammar to ENFORCE the static-name line
    and the structural invariants -- all to save a few hundred lines of parser.

  EVENT STRUCTS vs EVENT EMISSION  --  the asymmetry
    Event structs and instances live in the Lua object space like everything
    else; their fields are readable from Lua and their member functions ARE
    Lua. But event EMISSION is not a Lua call: 'emit' is a control-plane verb
    taking a statically literal type name. The emitted event's field VALUES are
    Lua-evaluated; the type NAME is a static literal. Same for arm / unarm:
    literal unit name. Thus type name = static (a cascade-graph edge); data =
    dynamic (Lua-evaluated).

  THE WATCHDOG  --  instruction budget, not wall-clock
    Every Lua execution -- data-plane block, member function, guard expression
    -- is bounded by a maximum INSTRUCTION COUNT, enforced via the Lua VM count
    hook. The budget is a configuration parameter.
      Rationale: an instruction budget interrupts at the same point regardless
      of host hardware, so a test verdict is deterministic across machines. A
      wall-clock timeout was rejected: it would make the same test pass on a
      fast host and fail on a slow one -- unacceptable for a testing framework.
      Documentation should give a rough wall-clock calibration for authors'
      orientation, but the enforced quantity is the instruction count.


-------------------------------------------------------------------------------
5. CASCADES AND TERMINATION
-------------------------------------------------------------------------------

  A consequence body may emit an event; that event may trigger further
  consequences at the same instant T. This is a CASCADE.

  THE TERMINATION GUARANTEE
    Within a single instant T, a given event type may occur at most once. A
    cascade at T therefore monotonically consumes a finite set of event types
    and must terminate.

    Cascade at instant T:

        trigger event A at T
              |
              +---> emit B  ---> emit D
              |                    |
              +---> emit C         +---> emit A   ... BLOCKED: type A
                       |                          already occurred at T
                       +---> emit B  ... BLOCKED: type B
                                       already occurred at T

    Each emitted type is consumed once; re-emission of an already-seen type at
    the same T is blocked. The cascade is therefore finite by construction.

  THE STATIC CASCADE GRAPH
    Nodes are event types; an edge A -> B means "some rule triggered by A may
    emit B". Because emit/arm/unarm take statically literal names (section 4),
    every edge is visible by static inspection of the rule files alone -- Lua
    data-plane blocks contain no emit and contribute no edges. The graph is
    built once, at parse time.

        ANY ---> FRUSTRATION        (an 'ANY' rule is an edge from every node;
       / | \                         this fans in-edges wide but adds no cycle
      .  .  .                         that the once-per-T rule cannot break)

    A cycle in this graph is not an error: the once-per-T rule guarantees a
    cascade traverses any cycle at most once per instant before a repeated
    type blocks it.

  ARMING IS SOUND FOR STATIC ANALYSIS, FOR FREE
    A dormant armable unit is still a static node/edge in the graph. Arming
    only gates whether an existing edge is live at runtime; it never adds an
    edge. The static graph is the over-approximation in which every unit is
    always armed; runtime behaviour is always a subset of it. Gating an edge
    cannot create a new cycle, so arming never affects termination.


-------------------------------------------------------------------------------
6. RULES  --  CONSEQUENCES, ARMABLE UNITS, BODIES
-------------------------------------------------------------------------------

  ORDINARY CONSEQUENCE
    Always live. Fires whenever its trigger event occurs and its guard holds.

  ARMABLE UNIT
    A separate, first-class declared entity with the same internal shape as a
    consequence (trigger, optional guard, body) but DORMANT by default: while
    dormant its trigger may occur and it does not fire. It becomes live only
    when ARMED and returns to dormant when UNARMED.

    Lifecycle:

        +-----------+    arm  (by a consequence body)    +-----------+
        |  DORMANT  | --------------------------------->  |   LIVE    |
        |           |                                    |           |
        | trigger   | <---------------------------------  | fires on  |
        | ignored   |    unarm trigger fires (its own     | trigger + |
        +-----------+    'on <event> AND <guard>')        | guard     |
                                                          +-----------+

    - "Arming is a consequence": the ACT of arming is performed by an ordinary
      consequence's body; the thing armed is the armable unit. The consequence
      is never dormant -- only the armable unit is.
    - Arming arms for time > now: an arm takes effect strictly for events after
      the arming instant; a unit armed inside a body at T is not made live for
      other consequences already firing at T.
    - The unarm trigger is an ordinary 'on <event> AND <guard>'. It introduces
      no new trigger type: it anchors to a real event (typically a fed TICK)
      with a time-valued guard.
    - The armed state is a readable boolean member of the unit, e.g.
      'LOOK_FOR_CAR_SPEED.armed', usable inside any guard.
    - The only runtime state this mechanism adds to the engine is the set of
      currently-armed unit names.

    ACCEPTED LIMITATION -- no overlapping windows (v1)
      The armed state is a single boolean. Arming an already-armed unit is
      idempotent (set-to-true). Therefore two overlapping arm-windows of the
      SAME unit cannot be represented: the first unarm to fire closes the
      window for both. v1 accepts this; rule authors must ensure windows of a
      given unit do not overlap. Known upgrade path: make the armed state a
      counter (arm increments, unarm decrements, live while > 0) -- deferred
      because it changes what '.armed' means to a guard.

  WINDOW RESOLUTION
    A window bounded by a time guard expires no more precisely than the
    granularity of its anchoring event. A "+10 s" window anchored to a 100 ms
    TICK is accurate to 100 ms. This is correct: time advances only when an
    event says so.

  BODIES
    A body is a FLAT LIST of items. Each item is one of:

      CONTROL-PLANE actions  (parsed by the DSL parser):
          emit  <EventType>( <field> = <expr>, ... )
          arm   <UnitName>
          unarm <UnitName>

      DATA-PLANE block  (delegated verbatim to embedded Lua):
          { <lua state-changing code> }

    The two never nest: emit / arm / unarm never appear inside a '{ }' block.
    Control-plane items and data-plane blocks are interleaved at the top level
    of the body only.

    THE STATIC-NAME LINE
      The operands of emit / arm / unarm are statically literal type / unit
      names; they are never computed at runtime. These names are the edges of
      the cascade graph (section 5). The FIELD VALUES of an emitted event may
      be Lua-evaluated; only the type NAME is a static literal.

    Data-plane blocks may use the full power of Lua, restricted only by the
    sandbox environment and the instruction-budget watchdog (section 4). They
    mutate simulation objects and perform no emit / arm / unarm.


-------------------------------------------------------------------------------
7. THE BAD LAYER  --  JUDGEMENT
-------------------------------------------------------------------------------

  Events are not inherently bad. Badness is in the eye of the viewer. A rule
  file emits events -- including ominously named ones like VIOLATION -- with no
  judgement attached; VIOLATION is just an event type.

  Judgement is a thin separate layer, driven by a BAD section:

      BAD { VIOLATION; CRASH; SMELL; }

  BAD is a flat set of bare event-TYPE names. It carries no predicate: a form
  like 'BAD { VIOLATION.time < 6am }' is rejected, because it would fold a
  logic operation into a layer whose sole job is to point at types. An author
  who needs "an early violation is the bad one" makes that distinction in a
  CONSEQUENCE (on VIOLATION AND VIOLATION.time < 6am : emit EARLY_VIOLATION)
  and lists EARLY_VIOLATION in BAD. Classification stays in the rule set; BAD
  stays a dumb set of names.

  BAD belongs to the HWUT TEST DEFINITION, not to the rule files. The rule
  files (the model) are pure, non-judgemental and reusable; the rule-file
  grammar has no BAD production at all. One rule set can be held to several
  acceptance policies by pairing it with different BAD sets.

  VERDICT
    After the engine produces its time line, the BAD layer scans for events
    whose type is in the BAD set. A non-empty result is a test failure; the
    matching events, in time order with intrinsic 'time' / 'dt' intact, are the
    minimal evidence for an HWUT diff.

  TRUNCATION / STILL-ARMED UNITS
    Because every time line ends with a validated TERMINATION event (section
    3), an obligation whose deadline never arrived can be caught with a backstop
    rule: 'on TERMINATION AND <unit>.armed : emit VIOLATION'. The non-event
    becomes an event at the guaranteed final instant.


-------------------------------------------------------------------------------
8. ENCODING PATTERNS  --  THE SUBSTITUTE FOR TEMPORAL OPERATORS
-------------------------------------------------------------------------------

  The engine has no temporal operators ("within", "eventually", "until",
  "always") and needs none: time is a field, and temporal reasoning is ordinary
  arithmetic over the intrinsic 'time' / 'dt' fields inside boolean guards.
  Every bounded-future obligation is expressed as a past-facing guard on a real
  event; it is never checked ahead of time, it EXPIRES INTO A CONSEQUENCE at
  the first event at or after its deadline.

  Because the engine gives no safety net for this manual encoding, the
  canonical patterns below ARE the correctness guarantee. Authors copy them.
  (Concrete spelling depends on SYNTAX.txt; the patterns themselves are fixed.)

    - BOUNDED RESPONSE   "X must be followed by Y within N":
                         arm a unit at X; the unit emits VIOLATION on a TICK
                         past X.time + N if Y has not been seen; unarm on Y.
    - DEADLINE           "X must complete before absolute time T":
                         as above with the bound a constant rather than X.time+N.
    - ABSENCE            "Y must not happen between X and the bound":
                         a deadline with a flag; the non-event becomes an event
                         at the bounding instant.
    - DEBOUNCE /         "alarm at the bound unless ACK arrives":
      UNLESS-CANCELLED   arm at X, unarm on ACK, emit on the bounding event.
    - MUTUAL EXCLUSION   "A and B must not both hold":
                         on ANY AND (A and B) : emit VIOLATION.

  EXPRESSIVENESS
    The engine expresses exactly the bounded, falsifiable obligations. An
    obligation with no violating instant (unbounded liveness -- "eventually,
    no deadline") is not falsifiable by any finite test and is therefore out of
    scope by design, not by limitation.


-------------------------------------------------------------------------------
9. HWUT INTEGRATION SURFACE
-------------------------------------------------------------------------------

  PUBLIC API  (shape; signatures to be finalised)

    run(time_line, rule_set) -> time_line'
        The whole engine. Events in, cascades expanded, time line out.
        Performs no verification. Rejects a time_line not ending in
        TERMINATION.

    classify(time_line', bad_set) -> (failed?, [offending events])
        The BAD layer. A pure type-set filter over the produced time line.
        bad_set comes from the HWUT test definition, not the rule files.

  HARNESS-LEVEL HELPERS  (outside the engine core)
    Convenience utilities such as pre-filling a time line with periodic TICK
    events live here, in the harness layer -- never in the engine core, which
    emits nothing on its own initiative (section 3).

  Detail -- diff format, error reporting -- is owned by the HWUT integration
  work and is not specified in this document.


-------------------------------------------------------------------------------
10. IMPLEMENTATION NOTES  --  WHAT NOT TO GET WRONG
-------------------------------------------------------------------------------

  These are settled decisions with consequences an implementer must respect.

  - The static-name line (section 6) is load-bearing: the moment emit/arm/unarm
    accept a runtime-computed name, the static cascade check (section 5) is
    gone. The grammar must enforce literal names.

  - The watchdog is an instruction count, not wall-clock time (section 4).
    A wall-clock implementation makes test verdicts hardware-dependent.

  - The engine emits nothing on its own initiative (section 3): no internal
    clock, no wakeup queue. Periodic events come from the input time line.

  - The input time line must end with TERMINATION and the engine must REJECT
    input that does not (section 3). This is the precondition that makes
    pending-obligation backstops (section 7) sound.

  - There is one object space, Lua's (section 4). Do not build a parallel
    object model in the DSL layer.

  - 'ANY' matches every event type including cascade-emitted events and
    TERMINATION (section 3).

  REMAINING DELIVERABLE
    The concrete rule-file syntax (SYNTAX.txt) is still being drafted. It is
    the only part of the design not yet fixed. Everything in this README is
    settled.

===============================================================================
END OF DESIGN DOCUMENT
===============================================================================
