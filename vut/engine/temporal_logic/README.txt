===============================================================================
REACTIVE RULE ENGINE  --  HWUT 2.0 Behavioural Trace Validator
DESIGN DOCUMENT
===============================================================================

NAME
  REACTIVE RULE ENGINE. Temporal properties are expressed as event-triggered,
  guarded reactions. This document describes the architecture and the reasoning
  behind it; it does NOT restate concrete syntax.

COMPANION FILES
  SYNTAX.txt        The dominating reference: concrete syntax of rule files and
                    event traces. Where this document needs a syntactic detail
                    it cites a SYNTAX.txt section rather than repeating it; on
                    any discrepancy, SYNTAX.txt wins.
  DISCUSSIONS.txt   Running design log: resolved decisions, rationales, and
                    rejected alternatives.

VOCABULARY
  TIME LINE     The runtime input events (TRACE) plus the engine's internally
                generated events (cascades, clocks).
  TRACE         Concrete input time line, parsed at run time; ends with END.
  RULE FILE     Plain-text rules authored by a human.
  TRANSPILER    Python tool that parses the rule file, runs static analysis,
                and emits the Luau ENGINE.
  ENGINE        The generated standalone Luau application that processes a
                trace and prints a report.
  OBJECT SPACE  The single Luau table space holding every runtime instance:
                events, objects, modes, and state machines.
  MODE          A declared, parameterized, dormant-until-armed rule unit.
  STATE MACHINE A habitat for modes in which at most one member-mode is active
                at a time; arming a member deactivates the previous one.
  REPORT        The deterministic block of text the engine prints for HWUT
                nominal-recording comparison.

-------------------------------------------------------------------------------
1. PURPOSE AND SHAPE
-------------------------------------------------------------------------------
  The component produces a deterministic textual report of observed behaviour,
  for validation against a nominal recording via the HWUT harness.

  THE TWO STAGES
    1. TRANSPILE (Python, once): parse the rule file, run static analysis, emit
       a complete, self-contained Luau application.
    2. RUN (Luau, once per trace): the generated engine reads a trace from a
       stream or file, evaluates the rules, and writes its output to stdout.

  CORE CONSTRAINT -- PORTABILITY
    The transpiler is pure Python; the engine is generated Luau on a standard
    interpreter. Per-event processing never crosses a language or process
    boundary -- the Python<->Luau seam is crossed exactly twice per test
    (launch, exit).

  REPORT vs. ERROR -- two distinct outcomes
    The engine never JUDGES behaviour; comparing the report to a nominal
    recording is HWUT's job. An ERROR is different: an ill-formed rule file or
    a malformed trace means the engine cannot operate, and that surfaces to the
    tester as a real failure (nonzero status plus a diagnostic), never as plain
    report text the author might silently diff away. Error classes: lex, parse,
    name, guard (read-only violation), cascade (cyclic causality), state-machine
    (e.g. missing 'until switched'), trace (e.g. not ending in END), and
    internal (tool/infrastructure).

-------------------------------------------------------------------------------
2. PIPELINE
-------------------------------------------------------------------------------
    RULE FILE (authored by a human)
        |
        |  STAGE 1 -- TRANSPILE (Python, once)
        |-- parse rule file (control plane); capture opaque Luau verbatim
        |-- static analysis (name resolution, cascade cycle check,
        |     guard read-only check)
        +-- emit standalone Luau application
        v
    ENGINE (generated Luau application)
        |
        |  STAGE 2 -- RUN (Luau, once per trace)
        |-- 'on BEGIN' object-space initialisation
        |-- read TRACE (must end with an explicit END event)
        |-- for each event in temporal order:
        |     |-- advance synthetic CLOCKs, emit their pending events
        |     |-- fire matching rules (GROUND_MODE + live modes + the active
        |     |     state-machine member)
        |     +-- expand cascades at instant T and mutate objects
        |-- 'on END' object-space teardown
        +-- collect and process output streams
        v
    OUTPUT
        |-- '##' debug stream: printed live during the run (emission order)
        +-- REPORT block: printed after completion (sorted and deduplicated)

-------------------------------------------------------------------------------
3. THE MODEL
-------------------------------------------------------------------------------
  This section gives the conceptual model. Concrete declaration and rule syntax
  is in SYNTAX.txt; the cross-references below point to it.

  EVENTS
    Ephemeral, struct-like aggregates with typed fields. They exist only at the
    instant they occur. 'time' and 'dt' (delta since the previous event) are
    intrinsic number fields. The pair (type, time) uniquely identifies an
    occurrence; within one instant T a given event kind occurs at most once --
    the property the termination guarantee rests on (section 5).
    (Declaration syntax: SYNTAX.txt A.2.4.)

  OBJECTS
    Stateful aggregates persisting across time, defined in 'on BEGIN' via the
    'Class.create' factory. They are user data, not a rule-language construct:
    the transpiler never reflects on them, and bad field accesses surface as
    ordinary Luau runtime errors.

  MODES
    Declared, parameterized, dormant rule units, armed as an effect of a cause.
    Identity is the parameter list, so a duplicate arming is a silent no-op.
    A live mode's inner rules fire with the 'mode' binding set to the instance;
    optional 'init'/'deinit' hooks run once at arming and once at cessation. A
    mode ends when one of its 'until' clauses fires (first-wins; no further
    'until' is then checked) or at END if still live.
    (Lifecycle, parameters, and queries: SYNTAX.txt A.2.3.)

  STATE MACHINES
    A habitat for modes with single-active semantics: arming one member-mode
    deactivates the previous one (its mandatory 'until switched' fires). This
    expresses a state machine directly -- each member is a state, arming is a
    transition, mutual exclusion is automatic. A state machine has its own
    'init'/'deinit', an optional 'default' member (an implicit do-nothing
    'VOID' mode when unspecified), and may carry parameters.
    (Declaration, the 'switched' rule, and the 'sm' binding: SYNTAX.txt A.2.5.)

  BINDINGS
    Engine-supplied names in scope inside a fired rule's Luau spans: 'event'
    (the triggering event), 'mode' (the enclosing mode instance), and 'sm'
    (the enclosing state machine). 'mode' and 'sm' are unbound at top level;
    referring to them there is a transpile-time error.
    (Full rules: SYNTAX.txt A.2.1.)

  TIME-LINE BOUNDS -- BEGIN AND END
    Two implicit events frame every trace: BEGIN fires zero-time-ahead before
    the first trace event, END zero-time-ahead after the last. A trace must end
    with an explicit END or the engine rejects it. 'on BEGIN' / 'on END' are
    where object-space init and teardown live; they are restricted handlers
    (no guard, no emission), detailed in SYNTAX.txt A.3.

  TRACE TIMING
    A trace is uniformly EXPLICITLY-TIMED or CLOCK-TIMED, never mixed. The
    engine never consults a system clock, so a saved trace always replays
    deterministically; 'dt' is always derived from the previous event's time.
    (SYNTAX.txt B.)

  CLOCKS
    A 'clock' declaration is a periodic emitter on synthetic time, used to give
    a regular cadence (e.g. differential-equation integration) between authored
    events. It generates ordinary events and respects the cascade rules; it is
    not a system-time source. (Mechanism and syntax: SYNTAX.txt A.4.)

-------------------------------------------------------------------------------
4. ARCHITECTURE -- TRANSPILER AND ENGINE
-------------------------------------------------------------------------------
  TWO PLANES
    CONTROL PLANE -- declarations, rule headers, triggers, and effect verbs --
    is parsed by the transpiler. Event-type and mode names on the control plane
    are STATICALLY LITERAL: a body may not compute which type it emits or which
    mode it arms, because those names are the edges of the cascade graph
    (section 5). Argument VALUES may be computed; only the names are fixed.

    DATA PLANE -- guard expressions, '=> { }' mutation blocks, '{ luau-expr }'
    rvalue spans, 'init'/'deinit' bodies, and 'on BEGIN'/'on END' bodies -- is
    opaque Luau carried verbatim into the engine.

  THE ONE-OBJECT-SPACE INVARIANT
    There is exactly one object model: the Luau table space of the running
    engine. Every runtime instance lives only there. The transpiler builds no
    parallel object model -- it owns FORM, Luau owns SUBSTANCE. No rule-file
    fragment may reach engine-internal objects except through dedicated
    read-only functions, and no fragment may emit events. At run time this space
    is held by a single 'Space' object that owns the tracer and produces every
    event class bound to it; two Spaces never share history.

  IDENTITY & METATABLES
    Events, modes, and state machines carry transpiler-generated metatables, so
    the static checks can identify their types at compile time (queryable via
    'typeof'/'getmetatable'). Objects, by contrast, are user-defined classes
    built at run time via 'Class.create'. Two mechanisms for two jobs.

  THE LUAU BOUNDARY (transpile-time)
    The rule-file parser meets opaque Luau only at '{' and must find the
    matching '}' without lexing Luau itself -- naive brace-counting is wrong
    because strings and comments can contain braces. It therefore delegates
    brace-finding to a Luau helper, which in the same pass reports the
    vocabulary references inside the span for name resolution. The span's
    syntactic role (condition / expression / statement-block) selects the
    framing the helper parses under.

  SANDBOXING & CAPABILITIES
    The generated bootstrap injects only the capabilities the test
    configuration grants (network, filesystem, etc. denied unless explicitly
    permitted) plus the fixed helper set (SYNTAX.txt C). Rule-file Luau cannot
    widen its own environment; Python is the trust boundary.

  WATCHDOG
    Rule-driven Luau is bounded by a maximum-instruction count via the VM count
    hook, NOT wall-clock -- an instruction budget interrupts at the same point
    on any hardware, keeping verdicts machine-independent.

  SOURCE MAPPING
    Because the engine is generated code, a fault can surface in Luau the author
    never wrote. The transpiler therefore emits source mapping back to the
    originating rule-file 'file:line', so every runtime fault and static
    diagnostic points at the author's source.

-------------------------------------------------------------------------------
5. CASCADES AND STATIC ANALYSIS
-------------------------------------------------------------------------------
  THE TERMINATION GUARANTEE
    Within an instant T a given event kind occurs at most once, so a cascade
    can only consume the finite set of declared event kinds -- it terminates
    even for cyclic declarations. The runtime 'emit' helper enforces this,
    tracking the kinds already seen on the current cascade path and raising a
    fatal operational error on a repeat.

  STATIC ANALYSIS CHECKS (Python, transpile time)
    - NAME RESOLUTION (fatal). Every event, mode, field, and state-machine
      member name must resolve; each state-machine member's 'until' list must
      end with 'switched'; a state-machine 'default' must reference a valid
      member or VOID. (A tolerated unknown name in a validation suite would be
      a silent false pass -- hence fatal.)
    - GUARD READ-ONLY (fatal). A sound syntactic check rejects assignments and
      recognised mutating builtins inside guards. Sound but not complete:
      mutation via a user-defined call is not detected. (Rationale and exempt
      forms: SYNTAX.txt <guard>.)
    - CASCADE CYCLE (fatal). A depth-first search of the cascade graph
      (nodes = event kinds; edge X->Y iff an X-triggered rule emits Y) reports
      any cycle and the offending chain. The search is bounded by a node-visit
      limit; exceeding it is itself an error, never a silent pass. This is the
      transpile-time counterpart of the runtime 'emit' guard above.

-------------------------------------------------------------------------------
6. RULES, MODES, STATE MACHINES, AND THE TRACER
-------------------------------------------------------------------------------
  Concrete forms for everything below are in SYNTAX.txt A.2 and B.1; this
  section records only the design choices behind them.

  UNIFORM RULE SHAPE
    A rule has the same shape -- 'on ... => ... off' -- wherever it appears:
    top level, inside a mode, or inside a state machine. Every effect carries
    its own '=>', and 'off' closes every block. The shape never depends on
    context (in particular, 'off' is never optional), so a rule's
    well-formedness never depends on what follows it.

  MODE LIFECYCLE
    Identity is the parameter list, making arming idempotent: an author writes
    '=> + MODE(...)' without first checking whether it is already live. 'init'
    runs once on creation, 'deinit' once on cessation. The first 'until' to
    fire wins and no further 'until' is checked, so 'deinit' has a single
    well-defined moment and an 'until' clause may safely inspect the
    still-living instance. Top-level rules belong to an internal singleton,
    GROUND_MODE, so the engine has one mechanism (the mode) rather than two.

  STATE-MACHINE LIFECYCLE
    Members are mutually exclusive; arming one fires the previous member's
    implicit 'until switched'. 'switched' is a mandatory, non-functional
    closing 'until' on every member: it has no runtime effect but forces the
    author to acknowledge that a member can also end by a sibling being armed,
    not only by its own events.

  POLYMORPHIC QUERIES
    Mode classes and traced-event histories share one query interface (lists,
    boolean reductions, and temporal queries), routed through a generated
    '_match' dispatcher that accepts literals or comparator value objects. The
    author writes the comparator; the engine does the dispatch. This replaced
    an earlier family of separately named query methods with one call surface.
    (Method names and comparators: SYNTAX.txt A.2.3 and C.)

  THE TRACER
    History is opt-in: an event is queryable only if registered with
    'tracer.watch' in 'on BEGIN'. A watched type holds one flat history stream
    -- every occurrence lands in a single ring, bounded by 'last=N' (default 1);
    match attributes are applied at query time, not as a stored key. Querying an
    unregistered event is a fatal transpile error -- this closes the silent-nil
    class of bug, where a forgotten registration would make every query return
    nil and look like an absence of behaviour. The author pays memory only for
    what is declared. (Call form and checks: SYNTAX.txt B.1.)

-------------------------------------------------------------------------------
7. THE REPORT AND LOGGING
-------------------------------------------------------------------------------
  Two output streams, separated by construction:

  REPORT BLOCK ('=> "..."')
    Report strings are buffered during the run; on completion the whole block
    is alphabetically sorted and deduplicated for absolute determinism. Sort
    and dedup are deliberately lossy (order, multiplicity): the author recovers
    what a test needs by encoding it INTO the string -- a zero-padded timestamp
    prefix for order, a state-held counter for multiplicity. This replaced an
    engine-side "designated-bad events" model; the engine reports, HWUT
    compares, neither judges.

  '##' DEBUG STREAM
    Luau 'print()' is intercepted live, prefixed '##', and emitted immediately
    in run order. '##' lines are ignored in HWUT comparison. (The same '##' is
    the rule-file comment marker.) Because report lines are assembled only after
    the run, the two streams never interleave.

-------------------------------------------------------------------------------
8. ENCODING PATTERNS
-------------------------------------------------------------------------------
  Temporal operators are expressed as arithmetic over the intrinsic 'time' and
  'dt' fields inside boolean guards:
    - BOUNDED RESPONSE: arm a mode on X; test violations against
      'mode.begin_time + N'; clear early via 'until Y'.
    - DEADLINE: as above, against a constant bound.
    - ABSENCE: a deadline guarding a boolean flag; the non-event becomes a
      report line at the bounding instant.
    - DEBOUNCE / UNLESS-CANCELLED: one 'until' on a deadline, one on the
      success event.
    - MUTUAL EXCLUSION: a guarded check on the 'ANY' trigger.
    - STATE MACHINE: one state machine, one member-mode per state.

-------------------------------------------------------------------------------
9. INTEGRATION SURFACE
-------------------------------------------------------------------------------
  TRANSPILER INTERFACE (Python)
    transpile(rule_file, capability_config) -> luau_application | errors
    The tester's do() runs the front-end and reports a wrong specification
    distinctly from a report mismatch.

  ENGINE INTERFACE (Luau)
    Executed via a system call feeding a trace stream. Output is the
    chronological '##' debug lines first, then the finalised deterministic
    REPORT block.

===============================================================================
