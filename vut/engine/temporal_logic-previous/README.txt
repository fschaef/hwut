===============================================================================
REACTIVE RULE ENGINE  --  HWUT 2.0 Behavioural Trace Validator
DESIGN DOCUMENT
===============================================================================

MODULE TYPE STATES:

  SourceModule                     SourceModule               (text) one per file, isolated
        |                                |
        | parse                          | parse
        |                                |
  ParsedModule                     ParsedModule               (ast) per file, isolated
        |                                |
        | declare                        | declare            publish DECLARATIONS
        |                                |                    (export names + kinds
        |                                |                     + scopes). No refs.
        |                                |
  DeclaredModule                   DeclaredModule             (ast + declaration surface)
        |                                |                    References untouched.
        |                                |
        | elaborate                      | elaborate          OWN ast + OTHER modules' 
        |                                |                    DECLARATIONS:
        |                                |                    - replaced/decorate ast nodes
        |                                |                    - build symbol table
        |                                |                    - references EXISTENCE-
        |                                |                      checked, recipes EMPTY
        |                                |
  SemanticModule                   SemanticModule             (decorated ast + symbol table)
        |                                |                    Reference access known/defined
        |                                |                         |
        '---------------+----------------+-------------- ... ------'   (disk boundary for pre-builds)
                        |
                Set of SemanticModules
                        |
                        |
                 +------+----------------+
                 |                       |
            no entry point          + entry point
                 |                       |
              Library                    |    link: Implement Reference accesses.
                                         |          (load modules complete symbol table)
                                         |
                                     Executable
                                         |
                                         | emit
                                         |
                                      Luau app

-------------------------------------------------------------------------------
NAME
  REACTIVE RULE ENGINE. Temporal properties are expressed as event-triggered,
  guarded reactions. This document describes the architecture and the reasoning
  behind it; it does NOT restate concrete syntax.

COMPANION FILES
  SYNTAX_DOC         The dominating reference: concrete syntax of rule files and
  (parser/grammar.py) event traces, carried as the module docstring of
                     parser/grammar.py. Where this document needs a syntactic
                     detail it cites a SYNTAX_DOC section rather than repeating
                     it; on any discrepancy, SYNTAX_DOC wins.

  DISCUSSIONS.txt   Running design log: resolved decisions, rationales, and
                    rejected alternatives.

  UNIT READMEs      Per-unit mechanics, topology-first: parser/README.txt,
                    semantic/README.txt (the 'declare'/'elaborate' contract,
                    export_db, Access, recipe), and the link/emitter unit docs.
                    This document is the engine-wide map; a unit README is the
                    mechanics of one box on it. RATIONALE.txt (per unit) holds
                    the settled decisions behind those mechanics.

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
                events, objects, reactors, and aggregates.
  REACTOR       A declared, parameterized, dormant-until-armed rule unit with
                optional init/deinit hooks and closing 'until' causes. MODE and
                STATE are its two forms.
  MODE          A reactor that overlaps freely with its siblings; closed by its
                own 'until' causes. Lives at GROUND level or in a MODE GROUP.
  STATE         A reactor inside a STATE MACHINE; mutually exclusive with its
                siblings; its block ends structurally (next element or 'end').
                Optional trailing 'until' causes; it also ceases when a sibling
                is armed.
  MODE GROUP    An aggregate of modes with no exclusion: any number of member
                modes are active at once.
  STATE MACHINE An aggregate of states in which at most one member-state is
                active at a time; arming a member deactivates the previous one.
  AGGREGATE     A MODE GROUP or a STATE MACHINE (both are reactors). Spawned by
                'spawn:' into a container; its existence ended by 'unspawn:'.
                Both are clockwork-only. A single persistent instance is the
                default-container dedup (a duplicate spawn is a silent no-op),
                not a declaration.
  CONTAINER     A structure that holds aggregate instances -- one (a
                ScalarReactorContainer) or many (a MultiReactorContainer). It
                admits an offered instance under a mutexed slot protocol.
  NAMESPACE     A named scope, 'open <dotted-name> ... close', bracketing nested
                declarations. Nests to any depth; names are scoped to it.
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
    (e.g. an ill-formed state machine), trace (e.g. not ending in
    END), and internal (tool/infrastructure).

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
        |     |-- fire matching rules (GROUND + live modes + the active state
        |     |     of each live state machine)
        |     +-- expand cascades at instant T and mutate objects
        |-- 'on END' object-space teardown
        +-- collect and process output streams
        v
    OUTPUT
        |-- '##' debug stream: printed live during the run (emission order)
        +-- REPORT block: printed after completion (sorted and deduplicated)

STAGE 1: (more detail) THE CONSTRUCTION OF MEANING

A rule engine is built in the following steps, each consuming the product of
the one before:

  - LEXER => TOKEN STREAM: (atomic chunks of meaning)

      Tokens are the smallest spans that denote (a keyword, a name, a number,
      an opaque span). Below a token is mere spelling; at a token, meaning
      begins.

  - GRAMMAR => ABSTRACT SYNTAX TREE (AST)

      The grammar defines how tokens operate to build structures in the space
      of meaning: which token, adjacent to which structure, forms which larger
      structure. Each AST node is produced by a pattern rule that matched. The
      AST holds the BUILD COMMANDS for the meaning the text expresses -- not
      the meaning itself.

  - SEMANTICS => CONSTRUCT (standalone luau engine)

      (1) ANALYSIS: AST => SemanticModule  (per module)

      Each module is carried through two transitions (see section 3, MODULE
      TYPE STATES). 'declare' publishes its export_db -- the names, kinds, and
      scopes it exports -- without touching references. 'elaborate' then reads
      the module's own ast and the export_db of the modules it imports: it
      mutates the ast where a node's kind is now known ('=> name' becomes a
      spawn-event / spawn-mode / activate-mode node, kind-selected from a peeked
      export_db) and builds the symbol table, writing for each reference a
      RECIPE -- the known way to reach it. Access is KNOWN, not yet implemented.

      (2) LINK: Set of SemanticModules => one program  (over the set)

      'link' folds the set: it IMPLEMENTS every recipe (turning KNOWN access
      into wired access) and runs the cross-module checks that are only
      decidable over the whole graph -- cascade-cycle foremost. A rootless fold
      packs into a LIBRARY; a fold with an entry point becomes an EXECUTABLE.

      (3) EMISSION => STANDALONE LUAU ENGINE

      From the finished executable plan, EMISSION produces the program.

  - EXECUTION => REPORT
      The engine runs, processing a trace and writing the report.

-------------------------------------------------------------------------------
3. MODULE TYPE STATES & TRANSITIONS
-------------------------------------------------------------------------------

  The diagram at the head of this document is the spine of STAGE 1. A rule file
  becomes an engine by passing through a chain of MODULE TYPE STATES, each a
  distinct type, each reached by one total transition. A module is processed
  per file and in isolation until the fold; the cross-file work is concentrated
  in 'link'.

  THE STATES (per module, then the fold)

    SourceModule     a module identified by its path. The text is ephemeral:
                     the parser iterates it through the path and discards it.
    ParsedModule     ast (root node: ast.ModuleRoot) + origin (provenance back
                     to the source path). Text gone.
    DeclaredModule   ast + export_db. The export_db is the module's PUBLIC half:
                     name -> (kind, scope), export names only. References are
                     untouched at this state.
    SemanticModule   IS-A DeclaredModule (export_db stays present and peekable)
                     + symbol_table. The ast is mutated; each reference carries
                     a RECIPE. Access is KNOWN, not implemented.
    Library          a packed set of SemanticModules, no entry point, NOT
                     linked. Rootless: consumed, never launched. Re-enters a
                     later build as a set of SemanticModules.
    Executable       a linked program bound to an entry point. The seam to
                     EMISSION.

  THE TRANSITIONS

    parse      SourceModule -> ParsedModule.   Per module, isolated. The parser
               stays single-file and provenance-free; ParsedModule is wrapped
               above it at the load stage, where 'origin' is attached.
    declare    ParsedModule -> DeclaredModule. Per module, NO peek at any other
               module. Publishes export_db; references untouched.
    elaborate  DeclaredModule -> SemanticModule. Per module; PEEKS the export_db
               of imported modules (existence + kind only). Mutates the ast
               ('=> name' node-swap, kind-selected from a peeked export_db) and
               builds the symbol table, writing a RECIPE per reference. Resolves
               to KNOWN access; implements nothing.
    link       Set of SemanticModules -> LinkedModule. Over the SET: a worklist
               per module iterated to fixpoint IMPLEMENTS each recipe, and the
               cross-module cascade-cycle check (section 6) is decided here.
               + entry point -> Executable; none -> Library.
    emit       Executable -> Luau application.

  THREE RULES THAT HOLD THE CHAIN TOGETHER

    DECLARATION-FIRST   Every module 'declare's before any module 'elaborate's.
                        A module's imports must each be at least a DeclaredModule
                        before elaborate peeks them. A SemanticModule, being a
                        DeclaredModule, stands in wherever an export_db is peeked
                        -- so a half-progressed set still presents uniform
                        surfaces.
    KNOWN vs IMPLEMENTED elaborate writes the recipe (how a name is reached);
                        link wires it. Recipe-building is the semantic unit's
                        work, never link's.
    DISK BOUNDARY       SemanticModule serialises out and loads back in. A
                        pre-built (library) module on disk is consulted for its
                        export_db during another module's elaborate.

  The semantic unit (parse aside, which is the parser's) owns 'declare' and
  'elaborate'. Its contract is in semantic/README.txt; 'link' and EMISSION are
  separate units. This section is the map; those READMEs are the mechanics.

-------------------------------------------------------------------------------
4. THE MODEL
-------------------------------------------------------------------------------

  This section gives the conceptual model. Concrete declaration and rule syntax
  is in SYNTAX_DOC (parser/grammar.py); the cross-references below point to it.

  EVENTS
    Ephemeral, struct-like aggregates with typed fields. They exist only at the
    instant they occur. 'time' and 'dt' (delta since the previous event) are
    intrinsic number fields. The pair (type, time) uniquely identifies an
    occurrence; within one instant T a given event kind occurs at most once --
    the property the termination guarantee rests on (section 6).
    (Declaration syntax: SYNTAX_DOC (parser/grammar.py) A.2.4.)

    DELIVERY is implicit. There is no subscription construct: an event reaches a
    reactor precisely when that reactor names it in an 'on:' cause, and the
    cause's guard ('& { ... }') is the only filter. The engine derives the
    publisher/subscriber wiring from the set of event types named across the
    live 'on:' causes; the author expresses reaction, and routing follows.
    (Cause and guard syntax: SYNTAX_DOC (parser/grammar.py) A.2.2.)

  OBJECTS
    Stateful aggregates persisting across time, defined in 'on BEGIN' via the
    'Class.create' factory. They are user data, not a rule-language construct:
    the transpiler never reflects on them, and bad field accesses surface as
    ordinary Luau runtime errors.

  REACTORS
    A reactor is a declared, parameterized, dormant rule unit, armed as an
    effect of a cause. Identity is the parameter list, so a duplicate arming is
    a silent no-op. A live reactor's inner rules fire with the 'm' binding
    set to the instance; optional 'init'/'deinit' hooks run once at arming and
    once at cessation. MODE and STATE are its two forms; they share one body
    shape and differ only in how they close and whether they exclude siblings.

  MODES
    A mode overlaps freely with its siblings: any number are live at once. A
    mode ends when one of its 'until' clauses fires (first-wins; no further
    'until' is then checked) or at END if still live. A mode lives at GROUND
    level or as a member of a mode group.
    (Lifecycle, parameters, and queries: SYNTAX_DOC (parser/grammar.py) A.2.3.)

  STATES
    A state is a mode living in a state machine. Its block is terminated
    structurally (by the next state-machine element or 'end'); its own trailing
    'until' causes are optional (first-wins), and it also ceases when a sibling
    state is armed.
    (Declaration: SYNTAX_DOC (parser/grammar.py) A.2.5.)

  MODE GROUPS
    An aggregate of modes with no exclusion: arming one member does not
    deactivate another, and any number of members are live at once. A mode
    group has its own 'init'/'deinit', may carry parameters, has no 'default',
    and is closed by 'end' (it has no closing 'until' clauses of its own).
    (Declaration: SYNTAX_DOC (parser/grammar.py) A.2.6.)

  STATE MACHINES
    An aggregate of states with single-active semantics: arming one member
    state deactivates the previously active one (automatic mutual exclusion).
    Each member is a state, arming is a transition, mutual exclusion is
    automatic. A state machine has its own 'init'/'deinit', an optional
    'default' member (an implicit do-nothing 'VOID' state when unspecified),
    may carry parameters, and is closed by 'end'. Its Luau spans bind the
    state machine as 'sm'.
    (Declaration and the 'sm' binding: SYNTAX_DOC (parser/grammar.py)
    A.2.5.)

  AGGREGATE SPAWNING AND CONTAINERS
    A mode group or state machine (an AGGREGATE) is spawned with the 'spawn:'
    verb -- the clockwork-only counterpart to the bare 'arm:' that arms a single
    mode. Spawn has ONE shape: a mandatory argument list (the parentheses are
    required, empty for an argument-less type, 'spawn: T()'), with an optional
    'into:' target. A bare type name without parentheses is a syntax error --
    there is no parameterless or bracketless form. Absent 'into:', the instance
    goes to the per-kind DEFAULT container, which accepts it unless one of
    identical type and identical parameters is already present (then the spawn
    is a silent no-op, exactly like a duplicate arming -- identity is the
    parameters). Present, 'into:' names a container: a dict target carries a key
    subscript ('into: roster[e.id]'), a list target is bare and appends
    ('into: queue'); the container admits or rejects under a mutexed slot
    protocol, and a rejected offer constructs nothing. Several aggregates of one
    type run concurrently when their container holds many. An instance's
    existence is ended with 'unspawn:', also clockwork-only, which takes a
    reference by name (bare or dotted), not a fresh invocation; ending runs
    'deinit' once and releases the instance from its container.
    (Effect forms: SYNTAX_DOC (parser/grammar.py) <spawn>, <unspawn>; the
    container protocol: section on the runtime substrate.)

  BINDINGS
    Engine-supplied names in scope inside a fired rule's Luau spans: 'e'
    (the triggering event), 'm' (the enclosing mode/state instance), 'sm' (the
    enclosing state machine), and 'mg' (the enclosing mode group). 'm',
    'sm', and 'mg' are unbound at top level; referring to them there is a
    transpile-time error. 'sm' and 'mg' are the two aggregate self-bindings,
    one in scope at a time per the enclosing aggregate kind. The same spellings
    serve both planes (a guard '[ e.temp > limit ]' and a Luau span
    '{ e.temp > limit }' read identically); they are not reserved words.
    (Full rules: SYNTAX_DOC (parser/grammar.py) A.2.1.)

  TIME-LINE BOUNDS -- BEGIN AND END
    Two implicit events frame every trace: BEGIN fires zero-time-ahead before
    the first trace event, END zero-time-ahead after the last. A trace must end
    with an explicit END or the engine rejects it. 'on BEGIN' / 'on END' are
    where object-space init and teardown live; they are restricted handlers
    (no guard, no emission), detailed in SYNTAX_DOC (parser/grammar.py) A.3.

  TRACE TIMING
    A trace is uniformly EXPLICITLY-TIMED or CLOCK-TIMED, never mixed. The
    engine never consults a system clock, so a saved trace always replays
    deterministically; 'dt' is always derived from the previous event's time.
    (SYNTAX_DOC (parser/grammar.py) B.)

  CLOCKS
    A 'clock' declaration is a periodic emitter on synthetic time, used to give
    a regular cadence (e.g. differential-equation integration) between authored
    events. It generates ordinary events and respects the cascade rules; it is
    not a system-time source. (Mechanism and syntax: SYNTAX_DOC (parser/grammar.py) A.4.)

-------------------------------------------------------------------------------
5. ARCHITECTURE -- TRANSPILER AND ENGINE
-------------------------------------------------------------------------------
  TWO PLANES
    CONTROL PLANE -- declarations, rule headers, triggers, and effect verbs --
    is parsed by the transpiler. Event-type and mode names on the control plane
    are STATICALLY LITERAL: a body may not compute which type it emits or which
    mode it arms, because those names are the edges of the cascade graph
    (section 6). Argument VALUES may be computed; only the names are fixed.

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
    Events, reactors, and aggregates carry transpiler-generated metatables, so
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
    permitted) plus the fixed helper set (SYNTAX_DOC (parser/grammar.py) C). Rule-file Luau cannot
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
6. CASCADES AND STATIC ANALYSIS
-------------------------------------------------------------------------------
  THE TERMINATION GUARANTEE
    Within an instant T a given event kind occurs at most once, so a cascade
    can only consume the finite set of declared event kinds -- it terminates
    even for cyclic declarations. The runtime 'emit' helper enforces this,
    tracking the kinds already seen on the current cascade path and raising a
    fatal operational error on a repeat.

  STATIC ANALYSIS CHECKS (Python, transpile time)
    - NAME RESOLUTION (fatal). Every event, reactor, field, and aggregate
      member name must resolve;
      a state-machine 'default' must reference a valid member or VOID; a 'has:'
      and a member reference must resolve against the enclosing aggregate. (A
      tolerated unknown name in a validation suite would be a silent false pass
      -- hence fatal.)
    - GUARD READ-ONLY (fatal). A sound syntactic check rejects assignments and
      recognised mutating builtins inside guards. Sound but not complete:
      mutation via a user-defined call is not detected. (Rationale and exempt
      forms: SYNTAX_DOC (parser/grammar.py) <guard>.)
    - CASCADE CYCLE (fatal). A depth-first search of the cascade graph
      (nodes = event kinds; edge X->Y iff an X-triggered rule emits Y) reports
      any cycle and the offending chain. The search is bounded by a node-visit
      limit; exceeding it is itself an error, never a silent pass. This is the
      transpile-time counterpart of the runtime 'emit' guard above.

-------------------------------------------------------------------------------
7. RULES, REACTORS, AGGREGATES, AND THE TRACER
-------------------------------------------------------------------------------
  Concrete forms for everything below are in SYNTAX_DOC (parser/grammar.py) A.2 and B.1; this
  section records only the design choices behind them.

  UNIFORM RULE SHAPE
    A rule has the same shape -- 'on <cause> ( => <effect> )+' -- wherever it
    appears: top level, inside a mode, inside a state, inside a mode group, or
    inside a state machine. Every effect carries its own '=>', so the effect
    list is self-delimiting: it ends at the first line that is not an '=>'
    effect, and a rule needs no closing keyword. Because the follower of a rule
    (a top-level keyword, a member keyword, 'until', 'end', or end-of-file) is
    never '=>', a rule's well-formedness never depends on what follows it. The
    enclosing aggregate -- a mode group or a state machine -- is itself closed
    by 'end'; a mode by its 'until' causes; a state structurally (by the next
    element or 'end').

  MODE LIFECYCLE
    Identity is the parameter list, making arming idempotent: an author writes
    '=> arm: MODE(...)' without first checking whether it is already live. 'init'
    runs once on creation, 'deinit' once on cessation. The first 'until' to
    fire wins and no further 'until' is checked, so 'deinit' has a single
    well-defined moment and an 'until' clause may safely inspect the
    still-living instance. Top-level rules belong to an internal singleton,
    GROUND_MODE, so the engine has one mechanism (the reactor) rather than two.

  AGGREGATE SPAWNING
    A single mode is armed with the bare effect 'arm:'; an aggregate -- a mode
    group or a state machine -- is spawned with 'spawn:' and ended with
    'unspawn:', both clockwork-only (never a bare '=>' effect). 'spawn:' directs
    its instance to a container via 'into:': the per-kind default when omitted,
    or a named dict (at a key) or list (append) when given. The verbs keep the
    targets distinct: 'arm:' takes a reactor, 'spawn:'/'unspawn:' take an
    aggregate; 'unspawn:' takes a reference by name, not a fresh invocation.

  STATE-MACHINE LIFECYCLE
    Member states are mutually exclusive; arming one deactivates the
    previously active state (automatic mutual exclusion). A state can therefore
    end either by a sibling being armed or by one of its own 'until' causes,
    whichever fires first. A mode group runs no exclusion: arming a member
    leaves its siblings live.

  POLYMORPHIC QUERIES
    Mode classes and traced-event histories share one query interface (lists,
    boolean reductions, and temporal queries), routed through a generated
    '_match' dispatcher that accepts literals or comparator value objects. The
    author writes the comparator; the engine does the dispatch. This replaced
    an earlier family of separately named query methods with one call surface.
    (Method names and comparators: SYNTAX_DOC (parser/grammar.py) A.2.3 and C.)

  THE TRACER
    History is opt-in: an event is queryable only if registered with
    'tracer.watch' in 'on BEGIN'. A watched type holds one flat history stream
    -- every occurrence lands in a single ring, bounded by 'last=N' (default 1);
    match attributes are applied at query time, not as a stored key. Querying an
    unregistered event is a fatal transpile error -- this closes the silent-nil
    class of bug, where a forgotten registration would make every query return
    nil and look like an absence of behaviour. The author pays memory only for
    what is declared. (Call form and checks: SYNTAX_DOC (parser/grammar.py) B.1.)

-------------------------------------------------------------------------------
8. THE REPORT AND LOGGING
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
9. ENCODING PATTERNS
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
    - STATE MACHINE: one state machine, one member state per state.

-------------------------------------------------------------------------------
10. INTEGRATION SURFACE
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

