===============================================================================
REACTIVE RULE ENGINE  --  HWUT 2.0 Behavioural Trace Validator
DESIGN DOCUMENT
===============================================================================

NAME
  REACTIVE RULE ENGINE. Temporal properties are expressed as event-triggered,
  guarded reactions. The authoritative concrete syntax is SYNTAX.txt; this
  document describes the architecture and is kept consistent with it.

COMPANION FILES
  SYNTAX.txt        Concrete syntax of rule files and event traces (the
                    dominating reference: all other files are measured against
                    it for consistency).
  DISCUSSIONS.txt   Running design log: resolved decisions, rationales, and
                    rejected alternatives.

VOCABULARY
  TIME LINE     The sequence of runtime input events (TRACE) plus the engine's
                internally generated events (cascades, clocks).
  TRACE         Concrete input time line parsed at run time; ends with END.
  RULE FILE     Plain-text rules authored by a human.
  TRANSPILER    Python tool that parses the rule file, runs static analysis,
                and emits the Luau ENGINE.
  ENGINE        The generated standalone Luau application that processes a
                trace and prints a report.
  OBJECT SPACE  The Luau table space holding every event, object, lurker, and
                focus instance at run time.
  LURKER        A declared, parameterized, dormant-until-armed rule unit.
  FOCUS         A habitat for lurkers in which at most one member-lurker is
                active at a time; arming a member deactivates the previous one.
  REPORT        The deterministic block of text printed by the engine for HWUT
                nominal-recording comparison.

-------------------------------------------------------------------------------
1. PURPOSE AND SHAPE
-------------------------------------------------------------------------------
  The component produces a deterministic textual report of observed behaviour
  for validation against a nominal recording via the HWUT harness.

  THE TWO STAGES
    1. TRANSPILE (Python, once): parse the rule file, run static analysis, and
       emit a complete, self-contained Luau application.
    2. RUN (Luau, once per trace): the generated engine reads a trace from a
       stream or file, evaluates the rules, and writes its output to stdout.
       The trace is purely runtime input and is never compiled into the
       application.

  CORE CONSTRAINT
    Portability. The transpiler is pure Python. The engine is generated Luau
    executing on a standard Luau interpreter. Per-event processing never
    crosses a language or process boundary.

  JUDGEMENT vs. ERROR
    The engine does not JUDGE behaviour -- comparing the report to a nominal
    recording is HWUT's job. But an ERROR is an error: when the rule file is
    ill-formed, or a trace is malformed, the engine cannot operate, and that
    surfaces to the Python tester as a real failure (a nonzero status with a
    diagnostic), never as plain report text the author could diff away. The
    failure classes are: lex, parse, name, guard (read-only violation),
    cascade (cyclic causality), focus (e.g. missing 'until switched'), trace
    (e.g. not ending in END), and internal (tool/infrastructure).

-------------------------------------------------------------------------------
2. PIPELINE
-------------------------------------------------------------------------------
    RULE FILE (authored by a human)
        |
        |  STAGE 1 -- TRANSPILE (Python, once)
        |-- parse rule file (control plane) ; capture opaque Luau verbatim
        |-- static analysis (name resolution, cascade cycle check,
        |     guard read-only check)
        +-- emit standalone Luau application
        v
    ENGINE (generated Luau application)
        |
        |  STAGE 2 -- RUN (Luau, once per trace)
        |-- 'on BEGIN' object-space initialisation
        |-- TRACE input (must end with an explicit END event)
        |-- evaluate each event in temporal order:
        |     |-- advance synthetic CLOCKs and emit their pending events
        |     |-- fire matching rules (global + live lurkers + active focus
        |     |     members)
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
  EVENTS
    Ephemeral struct-like aggregates with typed fields, declared
    'event NAME( field : type; ... )'. They exist only at the instant they
    occur. 'time' and 'dt' (delta since the previous event) are intrinsic
    fields of type number. The pair (type, time) uniquely identifies an
    occurrence; within one instant T a given event kind occurs at most once.

  OBJECTS
    Stateful aggregates persisting across time spans. Defined in the
    'on BEGIN' handler using Luau via the 'Class.create' factory.

  LURKERS
    Declared, parameterized, dormant rule units. Armed with '=> + LURKER(args)';
    identity is the parameter list, so a duplicate arming is a silent no-op.
    A live lurker's inner rules fire with 'lurker' bound to the instance.
    Optional 'init { }' runs once at arming, 'deinit { }' once at cessation.
    A lurker ends when one of its 'until' clauses fires (first-wins; no further
    'until' checked), or at END if still live. Engine-stamped members:
    'lurker.begin_time', 'lurker.begin_event_index'.

  FOCI
    A habitat for lurkers with single-active semantics. A focus member-lurker
    is named 'FOCUS.MEMBER'; arming one deactivates the previously active
    member (its 'until switched' fires). A focus has its own 'init'/'deinit'
    and 'until' clauses, an optional 'default' member (the implicit
    'FOCUS.VOID' do-nothing lurker when unspecified), and may carry parameters
    bound to the 'focus' binding. This expresses a state machine: each member
    is a state, arming is a transition, mutual exclusion is automatic.

  BINDINGS
    Inside any opaque Luau span attached to a fired rule, three engine-supplied
    bindings may be in scope: 'event' (the triggering event), 'lurker' (the
    enclosing lurker instance), and 'focus' (the enclosing focus). 'lurker' and
    'focus' are unbound at top level; referring to them there is a
    transpile-time error.

  TIME LINE BOUNDS -- BEGIN AND END
    Traces are framed by two implicit events: BEGIN fires immediately (zero
    time ahead) before the first trace event; END fires immediately after the
    last. An input trace must end with an explicit END event, otherwise the
    engine rejects it. ANY matches both boundary events. 'on BEGIN' and 'on
    END' handlers are special: they take no guard and may not emit events
    (their effect is a single Luau block); they are where object-space init
    and teardown live.

  TRACE TIMING
    A trace is uniformly EXPLICITLY-TIMED or CLOCK-TIMED; modes are never
    mixed. The engine never consults a system clock; 'dt' is always derived as
    the delta to the previous event's time.

  CLOCKS (synthetic-time generation)
    'clock <event-name> <number>' declares a periodic emitter on synthetic
    time. Activated at the first trace event, it emits its event every
    <number> of synthetic time, catching up linearly to each arriving trace
    event's timestamp. Used for differential-equation integration and other
    regular-cadence simulation between authored events.

-------------------------------------------------------------------------------
4. ARCHITECTURE -- TRANSPILER AND ENGINE
-------------------------------------------------------------------------------
  CONTROL PLANE (parsed by the transpiler)
    Declarations, rule headers, triggers, and effect verbs (=>, => +, => "..."),
    using statically literal event-type and lurker names.

  DATA PLANE (verbatim Luau carried into the engine)
    Guard expressions, '=> { }' mutation blocks, rvalue '{ luau-expr }' spans,
    'init'/'deinit' bodies, and the 'on BEGIN'/'on END' bodies. The rule-file
    parser does not lex Luau; it delegates brace-matching of each opaque span
    to the Luau side (see LUAU BOUNDARY below).

  THE ONE-OBJECT-SPACE INVARIANT
    There is exactly one object model: the Luau table space of the running
    engine process. Every event, object, lurker, and focus instance exists
    exclusively there. No rule-file Luau fragment may access engine-internal
    objects except through dedicated read-only functions, and no fragment may
    emit events.

  IDENTITY & METATABLES
    Events, lurkers, and foci are identified by transpiler-generated real
    metatables (queryable via 'typeof'/'getmetatable'). Objects are constructed
    in 'on BEGIN' via the 'Class.create' factory. Two mechanisms, two jobs:
    events/lurkers/foci need compile-time-identifiable type identity; objects
    are user-defined stateful aggregates.

  SANDBOXING & CAPABILITIES
    The generated bootstrap injects only the capabilities the test
    configuration grants (network, filesystem, etc. are denied unless
    explicitly permitted). It provides 'Class', 'tracer', the generated
    metatables, the comparator value classes, and the polymorphic '_match'
    dispatcher. Rule-file Luau cannot widen its environment.

  WATCHDOG LIMITS
    Luau execution arising from rule logic is bounded by a maximum-instruction
    count, enforced via the Luau VM count hook (not wall-clock, which would be
    non-deterministic across machines).

  SOURCE MAPPING
    The transpiler emits Luau carrying line directives or comments mapping back
    to the originating rule-file 'file:line', so a runtime fault or a static
    diagnostic points at the author's source.

  LUAU BOUNDARY (transpile-time)
    The rule-file parser meets opaque Luau only at '{'. To find the matching
    '}' without lexing Luau itself, it consults a Luau parser oracle
    ('luau-ast' via a Python module, with a pure-Python Luau-aware brace
    matcher as fallback). The same parse yields the references inside the span
    for name resolution. The span's syntactic role (condition / expression /
    statement-block) selects the framing the oracle parses under.

-------------------------------------------------------------------------------
5. CASCADES AND STATIC ANALYSIS
-------------------------------------------------------------------------------
  THE TERMINATION GUARANTEE
    Within a single instant T, a given event kind occurs at most once. Cascades
    monotonically consume the finite set of declared event kinds, guaranteeing
    termination even in cyclic declarations -- enforced at runtime by the
    'emit' helper, which keeps the per-cascade set of event kinds already seen
    on the current path and raises a fatal operational error if a repeat kind
    is emitted.

  STATIC ANALYSIS CHECKS (Python, at transpile time)
    - NAME RESOLUTION (fatal). Every event, lurker, field, and focus-member
      name resolves against declarations; focus members end their 'until' list
      with 'switched'; focus 'default' references a valid member or FOCUS.VOID.
      Unresolved names halt transpilation.
    - GUARD READ-ONLY (fatal). A sound syntactic check rejects assignments and
      recognised mutating builtins (table.insert, table.remove, table.sort,
      ...) inside guards. Sound but not complete: mutation via a user-defined
      function call is not detected.
    - CASCADE CYCLE (fatal). An exhaustive depth-first search of the cascade
      graph (nodes = event kinds; edge X->Y iff an X-triggered rule emits Y)
      detects any cycle and reports the offending chain. The search is bounded
      by a node-visit limit; exceeding it is itself a (limit) error, not a
      silent pass. This is the transpile-time counterpart of the runtime
      'emit' guard above.

-------------------------------------------------------------------------------
6. RULES, LURKERS, FOCI, AND THE TRACER
-------------------------------------------------------------------------------
  CONSEQUENCES
    'on <trigger> [ & <guard> ] => <effect>+ off'. Effects: event emission
    ('=>'), lurker arming ('=> +'), report string ('=> "..."'), or state
    mutation ('=> { ... }'). Effects may be interleaved freely; 'off' closes
    the block. The grammar is uniform inside lurkers and foci.

  LURKER LIFECYCLE
    Arming '=> + LURKER(params)' instantiates a class; identity is the
    parameter list; duplicate armings are silent no-ops. 'init' runs once on
    creation, 'deinit' once on cessation (an 'until' firing, or END). When one
    'until' fires, no further 'until' clauses for that instance are checked.
    Top-level rules belong to an internal singleton GLOBAL_LURKER.

  FOCUS LIFECYCLE
    A focus is armed like a habitat; its members are FOCUS.MEMBER lurkers, one
    active at a time. Arming a member fires the previous member's implicit
    'until switched'. 'switched' is a mandatory, non-functional closing 'until'
    on every member -- it forces the author to see that a member can end by a
    sibling being armed, not only by its own events. A focus has 'init',
    'deinit', a 'default' member, optional parameters (bound to 'focus'), and
    its own 'until' clauses.

  POLYMORPHIC QUERIES (lurkers and traced events)
    Lurker classes and traced event histories share one query interface routed
    through the generated '_match' dispatcher:
      lists:    ':list(conditions)'
      booleans: ':has()', ':any()', ':all()', ':none()', ':empty()'
      temporal: ':last()', ':since()'
    Conditions accept literal values or comparator objects (Glob, Approx, Less,
    LessEq, Greater, GreaterEq, Eq, UnEq, Pattern).

  THE TRACER
    A traced event may be queried only if registered in 'on BEGIN':
    'tracer.watch(EVENT, [by=key], [last=count])'. Querying an untraced event,
    or using key attributes the tracer is not keyed by, is a transpile-time
    fatal error (prevents the silent-nil class of bug).

-------------------------------------------------------------------------------
7. THE REPORT AND LOGGING
-------------------------------------------------------------------------------
  REPORT ASSEMBLY ('=> "..."')
    Report strings use Luau string interpolation. Lines are buffered during the
    run; on completion the whole block is alphabetically sorted and
    uniqueness-filtered (deduplicated) for absolute output determinism. Order
    and multiplicity are recovered by putting them into the string (a
    zero-padded timestamp prefix, a state-held counter).

  THE '##' DEBUG STREAM
    Luau 'print()' is intercepted live, prefixed with '##', and pushed to
    stdout immediately. '##' lines are ignored in HWUT nominal comparison. (The
    same '##' is the rule-file comment marker.)

-------------------------------------------------------------------------------
8. ENCODING PATTERNS
-------------------------------------------------------------------------------
  Temporal operators are replaced by arithmetic over the intrinsic 'time' and
  'dt' fields within boolean guards:
    - BOUNDED RESPONSE: arm a lurker on X; evaluate violations against
      'lurker.begin_time + N'; clear early via 'until Y'.
    - DEADLINE: as above against a constant bound.
    - ABSENCE: a deadline with a boolean flag; the non-event becomes a report
      line at the bounding instant.
    - DEBOUNCE / UNLESS-CANCELLED: one 'until' on a deadline, one on the
      success event.
    - MUTUAL EXCLUSION: a guarded check on the 'ANY' trigger.
    - STATE MACHINE: a focus, one member-lurker per state.

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
