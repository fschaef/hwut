===============================================================================
REACTIVE RULE ENGINE  --  HWUT 2.0 Behavioural Trace Validator
DESIGN DOCUMENT
===============================================================================

STATUS
  The architecture is settled. The concrete rule-file syntax is in SYNTAX.txt
  (settled; minor cosmetic points only). Ongoing design discussion is in
  DISCUSSIONS.txt; this README states the design as fact.

NAME
  This component is a REACTIVE RULE ENGINE, not a temporal logic engine. It
  has no temporal operators (no "eventually", "until", "always" as logic
  operators) and is not a model checker. Temporal properties are EXPRESSED as
  ordinary event-triggered, guarded reactions. It resembles a production-rule
  system crossed with runtime verification. The word "temporal logic" is
  avoided deliberately: it would invite a contributor to look for operator
  semantics that do not exist.

COMPANION FILES
  SYNTAX.txt        Concrete syntax of rule files and event traces.
  DISCUSSIONS.txt   Running design log: resolved decisions with rationale,
                    rejected/superseded alternatives, live questions.

VOCABULARY
  TIME LINE     The sequence of events. Runtime input (a TRACE) and, expanded,
                the engine's internal product.
  TRACE         A concrete input time line, supplied at run time. Different on
                every run; parsed by the engine at run time.
  RULE FILES    The plain-text rules a human authors; see SYNTAX.txt.
  TRANSPILER    The Python tool that parses rule files, statically analyses
                them, and EMITS a standalone Luau application.
  ENGINE        The emitted Luau application: it reads a trace, runs the
                rules, and prints a report.
  OBJECT SPACE  The Luau table space in which all event, object and lurker
                INSTANCES live at run time.
  LURKER        A declared, parameterized, dormant-until-armed rule unit.
                'lurk <name> ... until ...'. See sections 5-6.
  REPORT        The deterministic block of text the engine prints; HWUT
                compares it against a nominal recording. See section 7.


-------------------------------------------------------------------------------
1. PURPOSE AND SHAPE
-------------------------------------------------------------------------------

  The component validates observed behaviour against nominal behaviour, the
  HWUT way: it does not judge -- it produces a deterministic textual report of
  what happened, and HWUT compares that report against a nominal recording.
  Equivalence is a pass; divergence is a fail. The verdict comes from the
  comparison, never from a rule declaring an outcome harmful (section 7).

  THE TWO-STAGE SHAPE  --  TRANSPILE, THEN RUN
    Stage 1, TRANSPILE (Python, once per rule set):
      Python parses the rule files, runs static analysis (section 5), and
      emits a complete, self-contained Luau application -- the ENGINE. Python
      does not run during a test.
    Stage 2, RUN (Luau, once per trace):
      The emitted Luau application reads a TRACE at run time, parses it, runs
      the rules against it, and prints a report. The trace is runtime input
      and is NOT compiled into the application -- one transpiled engine runs
      against many different traces.

    The Python<->Luau boundary is crossed exactly twice in a test's life:
    launch and exit. There is no per-event boundary crossing, no embedded
    interpreter on the hot path, no inter-process communication during a run.

  CORE CONSTRAINT
    Portability. The transpiler is pure Python. The engine is generated Luau
    and runs on a standard Luau interpreter -- a mature, widely available
    runtime. (An earlier design embedded a pure-Python Luau, "pluau", on the
    hot path; that placed the whole performance and portability story on an
    immature dependency and was dropped. See DISCUSSIONS R-23.)


-------------------------------------------------------------------------------
2. PIPELINE
-------------------------------------------------------------------------------

    RULE FILES                        (authored by a human; see SYNTAX.txt)
        |
        |  STAGE 1 -- TRANSPILE (Python, once)
        |    - parse rule files
        |    - static analysis: cascade graph, name resolution (section 5)
        |    - emit a standalone Luau application
        v
    ENGINE  (a generated Luau application)
        |
        |  STAGE 2 -- RUN (Luau, once per trace)
        |
    TRACE  ------>  the engine, at run time:
    (runtime input,   - parses the trace
     ends with        - for each event, in time order:
     TERMINATION)         fire matching rules; fire each live lurker
                          instance; expand cascades at T; mutate objects
                      - collects '=> "..."' report lines
                      - prints '##' debug lines as they occur
        |
        v
    OUTPUT (printed by the engine):
        '##' debug lines      -- during the run, emission order,
                                 not sorted, not deduplicated, not compared
        REPORT block          -- after the run: the '=> "..."' lines,
                                 sorted alphabetically and deduplicated
        |
        v
    HWUT compares the REPORT block against the NOMINAL recording, tolerantly
    (numeric tolerance, pattern matching). Equivalent = pass, divergent =
    fail. HWUT does not judge -- it reports divergence.

  Static analysis happens once, in Python, at transpile time. The entire run
  happens inside one Luau process. Per-event work never crosses a process or
  language boundary.


-------------------------------------------------------------------------------
3. THE MODEL
-------------------------------------------------------------------------------

  EVENTS
    Ephemeral struct-like aggregates: named typed fields, optionally member
    functions. An event exists only at the instant it occurs. 'time' and 'dt'
    (delta since the previous event) are intrinsic struct fields of every
    event, of type 'number'. The pair (event type, time) uniquely identifies
    an occurrence.

  OBJECTS
    Stateful aggregates persisting across time spans.

  RULES
    Declared in rule files: event structures, object structures, the SETUP
    section, ordinary CONSEQUENCES, and LURKERS.

  SETUP  --  OBJECT-SPACE INITIALISATION
    A rule file contains a SETUP section: Luau code, run ONCE when the engine
    starts, before any event, that constructs the singleton objects and their
    initial state. Object declarations give structure; SETUP gives initial
    state.

  CONSEQUENCE
    'on <trigger> [ & <guard> ] : <body>'. The trigger event fires the
    consequence; the guard is a boolean expression over state; the body
    produces results (section 6). An ordinary consequence is ALWAYS LIVE.

  THE 'ANY' TRIGGER
    A trigger may be the keyword ANY, matching every event type -- including
    cascade-emitted events and TERMINATION. ANY is the means to check purely
    state-dependent conditions after every event.

  TIME LINE TERMINATION
    Every input trace MUST end with a TERMINATION event. The engine validates
    this precondition and REJECTS a trace lacking it. TERMINATION is the
    guaranteed final instant at which any pending obligation can be reported.
    It is otherwise an ordinary event: ANY matches it, rules trigger on it.

  TRACE TIMING  --  TWO MODES, NEVER MIXED
    Each event carries an intrinsic 'time'. A trace as a whole is either
    EXPLICITLY-TIMED (every event states its time) or CLOCK-TIMED (times
    derived from the system clock at the moment of live capture); the two are
    never mixed within one trace. Clock timing is a LIVE-CAPTURE mode only:
    saving a captured trace freezes the clock-derived values into real
    timestamps, so every SAVED trace file is explicitly-timed and replays
    identically. The engine never consults a clock. 'dt' is always derived by
    the engine as the delta to the previous event's 'time'; it is never
    written in a trace.

  NO PURE TIME TRIGGERS / THE ENGINE EMITS NOTHING ON ITS OWN INITIATIVE
    Every rule anchors to a real event. The engine has no time-based trigger,
    no wakeup queue, no internal clock. Periodic behaviour (e.g. a TICK every
    100 ms) is produced by whoever generates the input trace.
      Rationale: an engine emitting its own events would be generating a time
      line rather than validating a given one. A periodic-clock feature was
      considered and rejected; a helper that pre-fills periodic TICKs belongs
      in the HWUT harness layer, outside the engine.


-------------------------------------------------------------------------------
4. ARCHITECTURE  --  TRANSPILER AND ENGINE
-------------------------------------------------------------------------------

  Two components, one direction of dependency: the Python TRANSPILER produces
  the Luau ENGINE. They do not run at the same time.

    +===================== TRANSPILER (Python) =====================+
    |  parses rule files (control plane)                            |
    |  - declarations, rule headers, triggers, body verbs           |
    |    => (emit), => + (arm), => "..." (report)                   |
    |  - the body verbs' event-type / lurker names are STATICALLY    |
    |    LITERAL (the static-name line)                             |
    |  runs STATIC ANALYSIS (section 5): cascade graph, name         |
    |    resolution, reachability                                   |
    |  EMITS a standalone Luau application                          |
    +===============================================================+
                              | emits
                              v
    +======================= ENGINE (Luau) =========================+
    |  a self-contained Luau application:                           |
    |  - parses the runtime TRACE                                   |
    |  - the firing loop, cascade expansion, lurker population      |
    |  - the OBJECT SPACE: all event/object/lurker instances        |
    |  - guards and '{ }' state blocks (Luau, from the rule files,  |
    |    carried verbatim into the generated code)                  |
    |  - collects report lines; prints the report                  |
    +===============================================================+

  WHY TRANSPILE RATHER THAN EMBED
    An earlier design made Python the engine and embedded a Luau interpreter
    as a sandbox Python called into per event. That placed a language
    boundary on the hot path and rested portability on an immature
    pure-Python Luau. Transpiling instead -- Python emits Luau, a real Luau
    runtime executes it -- removes the hot-path boundary entirely and rests on
    a mature runtime. (DISCUSSIONS R-23.)

  WHAT STAYS IN PYTHON, AND WHY
    Parsing the rule files and the STATIC ANALYSIS stay in Python. Static
    analysis (the cascade graph, name resolution) is a compile-time activity
    and Luau is a poor substrate for it. Python is, in effect, a COMPILER that
    targets Luau: it parses, it checks, it emits code. The cascade graph is
    computed in Python, used to validate the rule set, and need not exist at
    run time.

  THE ONE-OBJECT-SPACE INVARIANT
    There is exactly one object space: the Luau table space of the running
    engine. Every event, object and lurker INSTANCE exists there and only
    there. There is no parallel object model anywhere.

  CONTROL PLANE vs DATA PLANE  (a property of the rule files / the transpiler)
    CONTROL PLANE -- parsed and understood by the transpiler: declarations,
      rule headers, triggers, and the body verbs => / => + / => "..." with
      STATICALLY LITERAL event-type and lurker names. The transpiler builds
      the cascade graph from these.
    DATA PLANE -- Luau text the transpiler does NOT parse: member-function
      bodies, '{ }' state-changing blocks, guard expressions, the SETUP body.
      The transpiler carries these verbatim into the generated engine.

  EVENT STRUCTS vs EVENT EMISSION  --  the asymmetry
    Event structs/instances live in the object space; an event is a Luau
    table with a metatable identifying its type (no third-party class library
    is required). Member functions are Luau. But 'emit' (=>) is a control-
    plane verb taking a statically literal type name -- the transpiler sees
    it. The emitted event's field VALUES are Luau-evaluated; the type NAME is
    a static literal. Same for '=> +' arm: literal lurker name, Luau-evaluated
    parameter values.

  GENERATED-CODE SANDBOXING
    The engine's restrictions are a property of GENERATION: the transpiler
    emits Luau that runs in a restricted environment -- it emits only the
    capabilities a rule set is permitted, and omits os/io/network unless the
    HWUT test configuration grants them. Because the transpiler controls
    exactly what it emits, the sandbox is enforced at generation time rather
    than by a live embedding. The permitted-capability set is a transpiler
    input and a per-test decision (section 9).

  TYPE CHECKING ACROSS THE SEAM
    The rule-file declarations carry types; Luau does not see the declaration
    language. Runtime type checks are available via Luau's metatable identity
    ('typeof' / the type-carrying metatable of each event/object). The
    generated bootstrap provides an adapter exposing checks such as
    is-event-of-type and field-presence assertions. This is runtime checking,
    not static -- but it is checkable rather than silent.

  THE WATCHDOG  --  instruction budget, not wall-clock
    Luau execution arising from rule logic (guards, '{ }' state blocks,
    member functions, SETUP) is bounded by a maximum INSTRUCTION COUNT via the
    Luau VM count hook. The budget is a configuration parameter.
      Rationale: an instruction budget interrupts at the same point on any
      hardware, so a test verdict is deterministic across machines. A
      wall-clock timeout was rejected: it would make the same test pass on a
      fast host and fail on a slow one. Documentation may give a wall-clock
      calibration for orientation; the enforced quantity is the instruction
      count.

  DEBUGGABILITY OF GENERATED CODE  --  a load-bearing obligation
    Because the engine is generated, a fault can surface in Luau source the
    author never wrote. The transpiler MUST emit Luau that maps back to
    rule-file source -- line directives or comments carrying the originating
    'file:line' -- or run-time and load-time diagnostics become unusable.

  THE LUA HELPERS  --  transpile-time Luau companions to the Python transpiler
    Python cannot parse Luau without taking on a Luau-parser dependency. Two
    distinct transpile-time tasks need Luau-parsing capability, and they are
    served by two separate small Luau scripts that share parsing utilities.
    All Luau code in the project lives in the 'lua/' subdirectory:

        lua/
          aux.lua          -- shared Luau lexer / parser utilities
          find_end.lua     -- transpile-time DAEMON: FIND_END requests
          analyze.lua     -- transpile-time batch tool: ANALYZE requests
          bootstrap.lua    -- run-time: the sandbox environment, injected
                              builtins (armed, last, since, format, ...),
                              event/object/lurker table+metatable helpers,
                              capture of print() for the '##' debug stream
          run.lua          -- run-time: the engine harness that loads the
                              bootstrap and the generated rule code, parses
                              the trace, drives the firing loop

    'aux.lua' is plain shared code (no process of its own). 'find_end.lua'
    and 'analyze.lua' are separate processes with separate lifecycles, each
    launched lazily when the Python transpiler first needs it.

    The two are NOT fused into one daemon: they answer different questions
    (one position-in / position-out, the other batched name-resolution
    analysis), have different protocols, and have different invocation
    patterns (interactive vs single batch). They share infrastructure
    (aux.lua), not roles.

    Both helpers run only at transpile time, never at test time. The
    Python<->Luau boundary rule (sections 1, 4) is unaffected: the helpers
    are build-time tools, not on the per-event path.

  THE find_end.lua DAEMON  --  finding the end of an opaque Luau span
    The rule-file parser must find the closing '}' of every opaque Luau
    span (guard, '{ }' state-changing block, member-function body, SETUP
    body). Brace-counting from the rule-file parser alone is wrong: Luau
    strings, long-bracket strings, line comments and long-bracket comments
    can all contain '{' / '}' that are not structural. Correct counting
    requires recognising Luau strings and comments -- i.e. a partial Luau
    lexer in the rule-file parser. That was rejected: the rule-file parser
    must stay small and have no Luau awareness.

    Instead the rule-file parser delegates the question to 'find_end.lua',
    a persistent daemon. Lazy launch: started on the first opaque '{' the
    parser encounters, persists for the transpiler's lifetime. Per-query
    cost is a pipe round-trip, not a process startup.

    PROTOCOL  (line-oriented over stdin/stdout):

        request:    FIND_END source=<path> pos=<byte-offset>
        response:   END_AT <byte-offset>
                    SYNTAX_ERROR line=<n> col=<m> message=<text>

    'pos' is the byte offset just AFTER the opening '{'. The daemon scans
    Luau from there, tracking string / long-string / comment / brace
    context, and returns the byte offset of the matching '}'. Read
    characters [pos, end) are the opaque Luau span; the parser resumes
    after the '}'.

    INTERPOLATED STRINGS  --  obligation on the lexer in 'aux.lua'
      Luau interpolated strings (backtick-delimited, with '{...}' holes
      containing arbitrary Luau expressions) are first-class syntax. The
      shared lexer in 'aux.lua' MUST recognise them: while scanning for
      the outer matching '}', the daemon must enter an interpolated string
      at a backtick, correctly skip its text and its '{...}' holes (each
      hole being itself an opaque Luau expression to be skipped past), and
      exit at the matching closing backtick. A '{' inside a backtick
      string's hole is NOT a structural brace; a '}' closing a hole is NOT
      the answer to FIND_END. Missing this is a wrong-answer bug, not just
      a missed feature -- the daemon would return the position of a hole's
      '}' as the span's end and the rule-file parser would silently
      misparse.

  THE analyze.lua TOOL  --  batch reference analysis (R-24, this section
  refined: split off from find_end.lua, still the same batch role)
    After parsing the whole rule file, the Python transpiler invokes
    'analyze.lua' ONCE with the full typed vocabulary and every Luau
    fragment collected from the file. The tool reports references to
    vocabulary names per fragment so Python can run Check 2 (section 5)
    across opaque Luau spans without learning Luau.

    Carries no rule-language model: the tool reports references; Python
    applies semantic policy.

    REQUEST FORMAT  (Python -> analyze.lua, plain text, content-blind framing).
    Two parts: a TYPED VOCABULARY header, then a batch of CODE fragments.

    The vocabulary header lists every declared EVENT and LURKER name from
    the rule files, one per line, with its kind and (for LURKER) its
    parameters whitespace-separated on the same line:

        EVENT TICK
        EVENT PING ip port payload
        EVENT TERMINATION
        LURKER NETWORK_WATCHER ip port firewall
        END_VOCABULARY

    Kinds are exactly EVENT and LURKER. Objects are NOT in the vocabulary:
    the transpiler reflects on event types (cascade graph) and lurker names
    (arming) but never on objects -- object field accesses are ordinary
    Luau, parsed natively by Luau and reported by Luau at run time, with no
    Python-side check to support. The helper therefore needs no object
    knowledge: anything outside the EVENT/LURKER vocabulary is opaque to it.

    After END_VOCABULARY, a batch of CODE fragments. Each fragment uses
    bracketed framing with a line count, so the parser reads N lines
    unconditionally without scanning content -- arbitrary Luau quoting and
    escaping pass through verbatim:

        CODE[42] 3 {
        local x = "hello \"world\""
        if x:match("a") then
          print(x)
        }
        CODE[43] 1 {
        vehicle.speed > 0
        }

    The line count after CODE[<id>] is load-bearing: the parser reads exactly
    N lines and does not scan them. The closing '}' on its own line (after
    the N counted lines) terminates the fragment. A wrong count or missing
    brace is a malformed stream and aborts. Fragment ids are integers chosen
    by the requester.

    RESPONSE FORMAT  (analyze.lua -> Python, JSON).
    Structured analysis output is better served by JSON: the response carries
    identifiers, integer line numbers, classified reference kinds, and
    bounded error messages. The asymmetry is deliberate -- content-blind
    framing for opaque user code in; structured data for analysis out. The
    helper writes one entry per fragment id:

        {
          "42": {
            "status": "ok",
            "references": [ { ...one per reference... } ]
          },
          "43": {
            "status": "syntax_error",
            "message": "...", "line": 2, "col": 5
          }
        }

    Per-reference fields are flat. 'kind' is closed at five values:
        "field"   -- vocabulary name used as a field-access receiver.
                     Fields: name (receiver), field, line, col.
        "builtin" -- a recognised name-bearing builtin call: 'last',
                     'since', 'armed', 'historian.track'. Fields: name (the
                     builtin), first_arg = {literal: bool, value?},
                     extra_args = [{name, literal, value?}], line, col.
        "filter"  -- 'EVENT(attrs)' as a query (the last-matching-event form).
                     Fields: name (event), attrs = [{name, literal, value?}],
                     line, col.
        "bare"    -- vocabulary name appearing as a bare identifier, neither
                     called nor field-accessed. Fields: name, line, col.
        (no 5th 'kind'; syntax_error replaces 'references' at the entry level.)

    'line'/'col' are 1-based relative to the fragment (line 1 = first counted
    line). Python adds the fragment's rule-file offset to recover the
    'rules.tl:line' source location for diagnostics.

    The helper does NOT report references to names outside the vocabulary
    (local variables, Luau builtins, noise). It does NOT categorize beyond
    the five kinds. Schema extends only if Python's needs extend -- and
    Python's needs are pinned by Check 2 (section 5), the static-name line
    extended to builtins, and historian coverage (section 6).

    INTERPOLATED STRINGS  --  references inside holes are reported
      Luau interpolated strings (backtick-delimited, with '{...}' holes
      containing arbitrary Luau expressions) appear naturally in '=> "..."'
      report-string bodies and elsewhere. 'analyze.lua' MUST descend into
      each interpolation hole and report any vocabulary references found
      inside it, exactly as it would report references found anywhere else
      in the fragment. The reference's line/col are relative to the
      fragment as usual -- no protocol extension; the report does not need
      to flag a reference as "inside an interpolation". The shared lexer in
      'aux.lua' performs the recognition; both helpers benefit from one
      correct implementation.

    THE STATIC-NAME LINE FOR BUILTINS
      The first argument of 'last(EVENT, ...)', 'since(EVENT, ...)',
      'armed(LURKER, ...)', and 'historian.track(EVENT, ...)' MUST be a
      LITERAL vocabulary name. The helper reports literal vs non-literal;
      Python emits a FATAL diagnostic on non-literal, exactly as it does for
      a computed '=>' target. Computation of these names would defeat the
      static check the helper exists to support.

  HELPER FAILURE MODES  --  bimodal, kept distinct
    Both helpers can fail in two completely different ways, and the user
    experience of each is utterly different. The diagnostics must reflect
    the distinction; muddling them is itself a defect.

    INPUT-SIDE failure: the helper ran correctly, but the Luau it was
    given does not parse -- a real syntax error in the author's guard or
    block. The helper returns SYNTAX_ERROR (find_end.lua) or
    status="syntax_error" (analyze.lua) with line/col/message. The Python
    transpiler surfaces this as an ORDINARY rule-file syntax error pointing
    at 'rules.tl:<line>'. The author can fix it by editing their code.

    INFRASTRUCTURE failure: the helper process crashed, failed to start,
    its pipe broke, or its response was malformed. This is a SOFTWARE
    PROBLEM unrelated to the parsed code -- a bug in the helper, a missing
    Luau interpreter, an OS resource limit. The Python transpiler reports
    it as an internal/infrastructure error explicitly NOT pointing at
    'rules.tl' ("transpiler helper failed: <reason> -- please report"). The
    author cannot fix this by editing rules.

    Each helper's implementation is obligated to fail gracefully on bad
    Luau input (return SYNTAX_ERROR, do not throw). Throwing on bad input
    would turn an input-side failure into a spurious infrastructure
    failure.


-------------------------------------------------------------------------------
5. CASCADES, TERMINATION, AND STATIC ANALYSIS
-------------------------------------------------------------------------------

  A consequence body may emit an event that triggers further consequences at
  the same instant T. This is a CASCADE.

  THE TERMINATION GUARANTEE
    Within a single instant T, a given event type may occur at most once. A
    cascade at T therefore monotonically consumes a finite set of event types
    and must terminate -- for ANY rule set, even one whose graph has cycles.

    Cascade at instant T:

        trigger event A at T
              |
              +---> emit B  ---> emit D
              |                    |
              +---> emit C         +---> emit A  ... BLOCKED: A seen at T
                       |
                       +---> emit B  ............ BLOCKED: B seen at T

  THE STATIC CASCADE GRAPH
    Nodes are event types; an edge A -> B means "some rule (or lurker rule)
    triggered by A may emit B". Because => and => + take statically literal
    names (section 4), every edge is visible to the transpiler by static
    inspection of the rule files alone -- Luau '{ }' blocks contain no emit
    and contribute no edges. An 'ANY' rule is an edge from every node to
    whatever it emits. The graph is built once, at transpile time, in Python.

  STATIC ANALYSIS  --  run once at transpile time, in Python
    The parser produces, per rule, a record: trigger type, the list of
    statically-literal event types the body emits, the list of lurkers it
    arms, and a source location. No '{ }' Luau span is inspected. Three
    checks run over these records:

    CHECK 1 -- CASCADE DEPTH (warning-level).
      Compute the longest simple path in the cascade graph: the worst-case
      number of events one input event can expand into at a single T.
      Termination itself is never in question (the once-per-T rule bounds
      every cascade); an unexpectedly large depth is reported as a WARNING
      because it usually signals a modelling mistake.

    CHECK 2 -- NAME RESOLUTION (FATAL).
      Every event-type name (in a trigger, an emit, an 'as' bind), every
      lurker name (in '=> +'), and every field name (in an event-spec or an
      arm-spec parameter block) must resolve against the declared sets. An
      unresolved name is a FATAL error: transpilation fails, no engine is
      emitted.
      The transpiler also resolves names referenced INSIDE Luau spans
      (guards, '{ }' blocks, the SETUP body) using the 'analyze.lua'
      helper (section 4). Specifically: first-argument names of recognised
      builtins ('last', 'since', 'armed', 'historian.track') -- which must
      be LITERAL vocabulary names (the static-name line, extended);
      event-as-filter references 'EVENT(attrs)'; and historian coverage and
      keying compatibility (section 6, historian compile-time checks).
      Object field accesses are NOT checked by the transpiler -- objects
      are not in the helper's vocabulary (section 4); Luau reports any bad
      access at run time. Each transpiler-side failure is FATAL with a
      'rules.tl:line' diagnostic.
      Rationale: in a validation suite a tolerated unknown name is a silent
      false pass -- a misspelled '=> VIOLATTION(...)' would emit a phantom
      event type, the intended event would never occur, and the divergence
      from nominal behaviour would go unreported. Every name-resolution
      failure is therefore fatal, without exception.

    CHECK 3 -- REACHABILITY (warning-level).
      Event types that can actually occur = those a trace may contain plus
      everything reachable in the graph. A rule whose trigger type is
      unreachable is a dead rule -- reported as a WARNING. A lurker never
      armed by any '=> +' is likewise a WARNING, NOT a fatal error: a sound
      "never armed" verdict would require the analyser to see every arming,
      and indirect/computed arming (a deferred feature) would make that
      impossible -- so the analyser must not treat it as certain.

    POLICY: name-resolution failures are FATAL (they corrupt the verdict);
    structural smells -- deep cascades, dead rules, never-armed lurkers -- are
    WARNINGS (the run is still sound; they merely signal likely mistakes).

  ARMING IS SOUND FOR STATIC ANALYSIS, FOR FREE
    A lurker's rules are static nodes/edges in the graph like any rule. The
    graph treats every lurker as always-armed -- the over-approximation.
    Arming only gates whether an existing edge is live at run time; it never
    adds an edge. Runtime behaviour is always a subset of the static graph,
    so arming -- and even future computed arming -- never affects the
    termination guarantee. (Computed arming would degrade only the Check 3
    warnings, never termination, because arming gates edges rather than
    creating them.)


-------------------------------------------------------------------------------
6. RULES  --  CONSEQUENCES, LURKERS, BODIES
-------------------------------------------------------------------------------

  ORDINARY CONSEQUENCE
    Always live. Fires whenever its trigger occurs and its guard holds.

  LURKER  --  'lurk <name>( <params> ) : <rules> until <conditions>'
    A lurker is a declared, parameterized CLASS of dormant rule unit. It is
    armed into existence as an INSTANCE; the instance lurks (is live) until
    one of the lurker's 'until' conditions ends it.

    Lifecycle of one instance:

        '=> +' arms an instance          one 'until' condition becomes
        into existence                   true for this instance
              |                                    |
              v                                    v
        +-----------+   instance lurks:      +-----------+
        |  ARMED /  |   its rules fire        |  no longer |
        |  LURKING  |   for this instance,    |  lurking   |
        |           |   'self' bound to it    | (not live) |
        +-----------+                         +-----------+

    - '=> +' is the constructor. Each '=> +' creates a FRESH, distinct
      instance: identity is parameters + arm time, and two armings cannot
      share an arm time (the same rule cannot fire twice at one T). There is
      no "re-arm" case.
    - An instance is a plain data aggregate: declared parameters bound onto
      'self', plus engine-stamped 'self.armed_at' (arm time) and
      'self.armed_index' (sequence index of the arming event). No member
      functions, no constructor body -- arming only binds data.
    - Parameters: primitives bound by value; object-typed parameters bound as
      REFERENCES into the one object space, never copies.
    - 'until' is a CONDITION, not a destructor. When an 'until' clause becomes
      true for an instance, that instance stops being live. Nothing executes.
      A lurker may have several 'until' clauses; the instance ends when ANY
      fires (serves debounce / unless-cancelled).
    - The engine maintains a live-instance population per lurker class and
      evaluates each live instance against each event.
    - 'armed(LURKER, ...)' is an engine-provided guard builtin: an existence
      test over the live population, matching a subset of parameters
      (unsupplied parameters are wildcards). It enables conditional arming as
      an ordinary guard. See SYNTAX.txt.
    - There is no explicit disarm verb. A lurker is ended only by its own
      'until' clauses.

    TRUNCATION BACKSTOP
      Because every trace ends with a validated TERMINATION event, an
      obligation whose deadline never arrived is caught by a lurker rule
      'on TERMINATION & { ... } : => "..."', which fires for each still-live
      instance.

    TEARDOWN
      There is no teardown pass. At end of the trace the engine's object
      space is discarded; all lurker instances are released with it.

  THE HISTORIAN  --  configured event-history queries
    Guards and bodies may need to consult past events: "did this PING come
    from an IP that successfully logged in?", "how long since the last
    HEARTBEAT?". The engine provides this through a HISTORIAN: a Luau object,
    configured in SETUP, that records past events of declared types according
    to a declared keying.

    DECLARATION  (in SETUP):
        historian.track(PING, by=ip)            -- keep the last PING per ip
        historian.track(HEARTBEAT)              -- keep the last HEARTBEAT
        historian.track(LOGIN, by=user, last=5) -- keep last 5 LOGINs per user

    The 'by=' clause names the attribute(s) that key the per-instance history;
    'last=' bounds how many entries to retain per key (default 1). The author
    pays only for the history declared -- nothing implicit.

    QUERY BUILTINS  (in guards and bodies):
        last(EVENT [, attrs])   -- the most recent matching EVENT, or nil
        since(EVENT [, attrs])  -- current time minus last(EVENT, attrs).time,
                                   or nil if never seen
        EVENT(attrs)            -- shorthand for last(EVENT, attrs)

    The first argument is a STATICALLY LITERAL event name (the static-name
    line, extended to history builtins). The transpiler-helper (section 4)
    extracts these calls; the transpiler validates them.

    COMPILE-TIME CHECKS
      For every query 'last(EVENT, ...)' / 'since(EVENT, ...)' /
      'EVENT(attrs)' the transpiler verifies, via the helper's report:
      1. EVENT is declared as historised in SETUP. Otherwise FATAL:
         "rules.tl:120: last(PING) used but PING is not historised --
          add historian.track(PING) in SETUP."
      2. The query's match attributes are compatible with the historian's
         keying. 'last(PING, ip=x)' against a historian without 'by=ip' is
         FATAL: "PING is historised, but not keyed by ip -- the historian's
         by=... must include the attributes you query against."
      Both diagnostics are author-fixable and prevent the silent-false-pass
      class of error: a query that always returns nil produces test results
      that look like absence of behaviour when the real cause is missing
      historisation. (Same rationale as Check 2, section 5.)

  BODIES
    A body is a single body item, or a flat list in '[ ]'. Each item:
        => <event-spec>      emit an event
        => + <arm-spec>      arm a lurker instance
        => "<luau-string>"   report a line of text (section 7)
        { <luau-code> }      mutate objects (Luau state-changing block)
    '=>' / '=> +' never appear inside a '{ }' block.

    THE STATIC-NAME LINE
      The event-type name in '=>' and the lurker name in '=> +' are
      statically literal -- never computed by Luau. They are the edges of the
      cascade graph (section 5). Field VALUES may be Luau-evaluated; only the
      names are literal. If this line is broken, the static cascade check is
      lost.


-------------------------------------------------------------------------------
7. THE REPORT  --  HWUT DOES NOT JUDGE
-------------------------------------------------------------------------------

  HWUT PHILOSOPHY
    HWUT's core does not judge. It does not contain the notion of "bad". It
    compares a recording of what happened against a NOMINAL recording and
    reports DIVERGENCE -- non-equivalence of observed with nominal behaviour.
    Equivalence is a pass; non-equivalence is a fail. The verdict comes from
    the comparison, never from a rule declaring an outcome harmful.

    (An earlier design had a 'BAD' section naming failure event types. That
    embedded judgement into the test, against HWUT philosophy, and is
    superseded by the report facility below. See DISCUSSIONS R-22.)

  THE REPORT FACILITY  --  '=> "..."'
    A consequence body item '=> "<luau-string-expr>"' produces a line of TEXT
    -- it REPORTS what happened. The string is an interpolated Luau
    expression, so it may carry state:
        on STOP_SIGN_PASSED as s : => "stop sign passed, lane " .. s.lane
    A report line is deliberate, declared, test-significant behaviour: the
    author chose to surface it. The set of report lines IS the test's output.

  DETERMINISTIC REPORT ASSEMBLY
    Report lines are NOT printed during the run. They are collected, and after
    the whole trace completes they are SORTED alphabetically and
    UNIQUENESS-FILTERED (deduplicated). The result is a deterministic block of
    text -- identical regardless of event-processing order or repetition.
    HWUT then compares that block to the nominal block.

  SILENCE EXCEPT FOR RELEVANT BEHAVIOUR
    The reporting world stays silent except when relevant behaviour occurs.
    Every report line is, by construction, behaviour the author chose to
    surface; a report line is never noise.

  RECOVERING ORDER AND MULTIPLICITY  --  authoring pattern
    Sort + dedup make the report deterministic but LOSSY: time order and
    multiplicity are discarded. The author recovers whatever the test needs by
    putting it INTO the reported string:
      - ORDER: prefix the timestamp or sequence index --
        '=> "t=" .. format(eve.time) .. " vehicle stopped"'. Format the number
        to FIXED WIDTH (zero-padded): lexical sort puts "t=10" before "t=2"
        otherwise.
      - MULTIPLICITY: include a counter held in object state, so otherwise
        identical events become distinct lines --
        '=> "violation #" .. global.violation_count'.
    This is a skill the test author must learn -- describing behaviour
    precisely is the discipline the tool demands. The nominal recording is
    the backstop: captured with the same discipline, a miscompare still
    surfaces.

  THE '##' DEBUG STREAM
    Luau code (a '{ }' state block, a member function, SETUP) may call
    print(). The engine captures print() output, AUTO-PREFIXES it with '##',
    and emits it. HWUT treats '##' lines as comments -- non-significant, not
    compared. They are a live trace the test developer uses to understand how
    the process evolved.
    '##' lines are printed DURING the run, in emission order: NOT sorted, NOT
    deduplicated. The two streams are therefore temporally separated by
    construction -- all '##' lines (during the run) precede the deterministic
    report block (assembled after the run). No interleaving. Because '##'
    lines are never compared, their non-determinism is harmless.

  COMPARISON IS TOLERANT
    The HWUT comparison core does not do raw string equality. It judges the
    report against the nominal with tolerance: numeric tolerance (4.200001
    matches 4.2), analogy and pattern matching, "happy patterns". The engine
    PRODUCES the deterministic report; HWUT COMPARES it tolerantly; neither
    JUDGES in the sense of declaring an outcome bad.


-------------------------------------------------------------------------------
8. ENCODING PATTERNS  --  THE SUBSTITUTE FOR TEMPORAL OPERATORS
-------------------------------------------------------------------------------

  The engine has no temporal operators ("within", "eventually", "until",
  "always") and needs none: time is a field, and temporal reasoning is
  arithmetic over time/dt inside boolean guards. Every bounded-future
  obligation is a past-facing guard on a real event; it EXPIRES INTO A
  CONSEQUENCE at the first event at or after its deadline.

  Canonical patterns (concrete spelling in SYNTAX.txt):
    - BOUNDED RESPONSE   arm a lurker at X; it reports a violation on a TICK
                         past X.armed_at + N; an 'until' on Y ends it early.
    - DEADLINE           as above, bound a constant rather than armed_at + N.
    - ABSENCE            a deadline with a flag; the non-event becomes a
                         report line at the bounding instant.
    - DEBOUNCE /         arm at X; one 'until' on a deadline, one 'until' on
      UNLESS-CANCELLED   the success event.
    - MUTUAL EXCLUSION   on ANY & { A and B } : => "both A and B hold".

  EXPRESSIVENESS
    The engine expresses exactly the bounded, falsifiable obligations. An
    obligation with no violating instant (unbounded liveness) is not
    falsifiable by a finite test and is out of scope by design.


-------------------------------------------------------------------------------
9. HWUT INTEGRATION SURFACE
-------------------------------------------------------------------------------

  TRANSPILER  (Python, stage 1)
    transpile(rule_files, capability_config) -> luau_application | errors
        Parses and statically analyses the rule files; on success emits a
        standalone Luau application. A name-resolution failure (section 5)
        aborts with errors and emits nothing. 'capability_config' is the
        per-test permitted-capability set (file/network access etc.); the
        transpiler emits an engine restricted to it.

  ENGINE  (generated Luau, stage 2)
    The emitted application takes a TRACE as runtime input, parses it, runs,
    and prints the output: the '##' debug lines during the run, then the
    sorted/deduplicated report block. It rejects a trace not ending in
    TERMINATION. It performs no judgement.

  HWUT then compares the printed report block against the nominal recording.

  HARNESS-LEVEL HELPERS  (outside transpiler and engine)
    Convenience utilities such as pre-filling a trace with periodic TICK
    events live here -- never in the engine, which emits nothing on its own
    initiative (section 3).

  Diff format and error-reporting detail are owned by the HWUT integration
  work and not specified here.


-------------------------------------------------------------------------------
10. IMPLEMENTATION NOTES  --  WHAT NOT TO GET WRONG
-------------------------------------------------------------------------------

  - Two stages, one boundary crossing each way: Python transpiles (stage 1),
    a standalone Luau engine runs (stage 2). Python is not in the loop during
    a run. There is no per-event language or process boundary (sections 1, 4).

  - The trace is RUNTIME input, parsed by the engine in Luau. It is never
    compiled into the engine; one engine runs many traces (section 1).

  - The static-name line (section 6) is load-bearing: if => or => + accept a
    runtime-computed name, the static cascade check (section 5) is gone.

  - Static analysis (cascade graph, name resolution) runs in PYTHON at
    transpile time. Name-resolution failures are FATAL -- no engine is
    emitted. Structural smells are warnings (section 5).

  - The generated Luau MUST carry source mapping back to rule-file 'file:line'
    or diagnostics in generated code become unusable (section 4).

  - The watchdog is an instruction count, not wall-clock time (section 4):
    a wall-clock timeout makes test verdicts hardware-dependent.

  - The engine emits nothing on its own initiative (section 3): no internal
    clock, no wakeup queue. Periodic events come from the input trace.

  - The input trace must end with TERMINATION; the engine must REJECT a
    trace that does not (section 3).

  - There is one object space, the Luau engine's (section 4). No parallel
    object model anywhere.

  - A lurker instance's identity is parameters + arm time; every '=> +' is a
    fresh instance; 'until' is a condition, not a destructor; teardown is
    discarding the object space (section 6).

  - 'ANY' matches every event type including cascade-emitted events and
    TERMINATION.

  - The engine does not judge (section 7). '=> "..."' report lines are
    sorted and deduplicated into a deterministic block; HWUT compares that
    block to a nominal recording. '##' debug lines (captured Luau print())
    are emission-order, not sorted, not deduplicated, not compared. There is
    no 'BAD' section -- it embedded judgement and was removed.

  - Two Luau helpers (section 4) run at transpile time only, in 'lua/':
    'find_end.lua' is a persistent daemon that finds the closing '}' of an
    opaque Luau span (so the rule-file parser never lexes Luau);
    'analyze.lua' is a one-shot batch tool that reports references to
    vocabulary names in collected Luau fragments. Shared parsing utilities
    in 'lua/aux.lua'. Both fail in two distinct ways and the diagnostics
    must keep them separate: an INPUT-SIDE syntax error points at
    'rules.tl:<line>' (author can fix); an INFRASTRUCTURE failure (process
    died, garbled response) is reported as an internal error not pointing
    at the rule file.

  - The historian (section 6) is configured in SETUP. History queries
    'last' / 'since' / 'EVENT(attrs)' are statically checked against
    historian coverage at transpile time -- a query against an unhistorised
    type is FATAL, not a silent nil.

  - The engine maintains a bounded diagnostic LOG (circular buffer; size is
    a config parameter, default generous) recording each event with its
    timestamp and the rules that fired (with 'file:line'). The log is
    diagnostic, not test-significant: it does not affect the report.

  REMAINING DELIVERABLE
    Minor cosmetic syntax points in SYNTAX.txt (S-10, S-11). Everything else
    in this README and the rule-definition grammar is settled.

===============================================================================
END OF DESIGN DOCUMENT
===============================================================================
