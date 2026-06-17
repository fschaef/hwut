===============================================================================
LUAU SUPPORT MODULES
===============================================================================

Three modules under 'luau/' provide the compilation boundary for the 
transpiler: span termination, source-to-target location mapping, and 
generated-code type checking. Together they form an integrated pipeline:

    rule-file text
         │
         ├── find_matching_brace()              [luau_span_oracle.py]
         ▼
    (open_offset, end_offset)
         │
         ├── register_fragment()                [location_mapper.py]
         ▼
    Source2TargetLocationMapper
         │
         ├── analyze_text() / analyze_path()    [generated_code_checker.py]
         ▼
    [Diagnostic, ...] ── format_diagnostic() ──> error message


===============================================================================
QUICK START & PUBLIC ENTRY POINTS
===============================================================================

1. SCANNING OPAQUE SPANS (luau/luau_span_oracle.py)

Isolate verbatim Luau snippets inside a rule-file by identifying the exact 
closing '}' relative to an opening '{'. Braces inside Luau strings, long-bracket 
comments, or template blocks are bypassed by an oracle parse loop, not by
lexing Luau.

SIGNATURE:
  find_matching_brace(source: str, open_offset: int, role: Role, oracle: object) -> int

USAGE:
  from luau.luau_span_oracle import find_matching_brace, Role, LuauOracle
  
  oracle = LuauOracle(binary="luau-ast")
  closing_idx = find_matching_brace(
      source=rule_file_content, 
      open_offset=left_brace_index, 
      role=Role.CONDITION, 
      oracle=oracle
  )


2. PROVENANCE & LOCATION TRACKING (luau/location_mapper.py)

Track the relationship between the target generated file lines and the original 
rule-file locations out-of-band (since Luau lacks a '#line' pragma).

SIGNATURES:
  .advance(line_count: int) -> None
  .register_fragment(source_file: str, source_line: int, length: int, 
                     indent: int = 0, first_line_prefix: int = 0) -> int
  .source_line_of(target_line: int, target_column: int = 0) -> SourceLocation | None

USAGE:
  from luau.location_mapper import Source2TargetLocationMapper
  
  mapper = Source2TargetLocationMapper()
  
  # For transpiler-generated boilerplate lines:
  mapper.advance(line_count=5)
  
  # For a verbatim copied fragment block:
  placed_at = mapper.register_fragment(
      source_file="rules.vut", source_line=12, length=3, indent=4
  )


3. STATIC TYPE-CHECKING & ERROR ATTRIBUTION (luau/generated_code_checker.py)

Execute 'luau-analyze' over the full generated code context and accurately map 
any returned compiler error lines back to either the rule-file author or the 
transpiler infrastructure itself.

SIGNATURES:
  .analyze_text(target_text: str) -> list[Diagnostic]
  .analyze_path(target_path: str) -> list[Diagnostic]
  format_diagnostic(diag: Diagnostic) -> str

USAGE:
  from luau.generated_code_checker import GeneratedCodeChecker, format_diagnostic
  
  checker = GeneratedCodeChecker(mapper=mapper, binary="luau-analyze")
  diagnostics = checker.analyze_text(target_text=assembled_output)
  
  for diag in diagnostics:
      print(format_diagnostic(diag))


===============================================================================
0. SUBSTRATE DESIGN MAP ("bootstrap.lua")
===============================================================================

    │
    ├── (1) COMPARISON CORE -- _match and comparator value classes
    │      ├── _match(actual, expected)             -- Routing core: checks for metatable '__className'
    │      │                                           and ':match', falls back to Luau '=='
    │      ├── _comparator(class_name, match_fn)    -- Value class factory returning a callable
    │      └── Built-in Comparators                 -- Glob, Pattern, Approx, Less, LessEq,
    │                                                  Greater, GreaterEq, Eq, UnEq
    │
    ├── (2) QUERYABLE -- the eight-method query interface
    │      │            (Requires subclass to override :_instances())
    │      ├── _instance_matches(inst, conditions)  -- Multi-field checker routing through _match
    │      ├── :list / :has / :any / :all           -- Evaluates match sets (empty tables are truthy)
    │      ├── :none / :empty                       -- Logical inverses and emptiness validation
    │      ├── :last                                -- Newest-to-oldest scan (last element of array)
    │      └── :since(now, conditions)              -- Measures elapsed time from :_moment()
    │
    ├── (3a) SPACE + EVENT BASE -- runtime context boundary
    │      ├── Space.new()                          -- Context boundary; instantiates its own Tracer
    │      ├── Space:new_event_class(name)          -- Factory for Queryable event classes:
    │      │     │                                     overrides :_instances() to resolve the tracer ring,
    │      │     │                                     overrides :_moment() to return event 'time'
    │      │     ├── .new(fields, time, dt)         -- Stamping constructor
    │      │     └── .signal(fields, time, dt)      -- Pushes directly into the Space's Tracer
    │      └── EventBase                            -- Shared base without init/deinit lifecycles
    │
    ├── (3b) MODE BASE -- lifecycle + registry
    │      └── .new_mode_class(name)                -- Base container with a live set and until-causes
    │            ├── :_instances()                  -- Queryable contract; yields the live set
    │            ├── ._identity(params, order)      -- Param-joining null-separated key identity
    │            ├── .arm(params, ...)              -- Idempotent arming; runs 'init' once per unique key
    │            ├── .cease(self)                   -- Removes from live set, runs 'deinit' hook
    │            ├── :check_until(event)            -- Runs declarative until-checkers (first-wins)
    │            └── :add_until(checker)            -- Appends until-cause functions
    │
    ├── (3c) STATE-MACHINE BASE -- single-active habitat
    │      └── .new_state_machine_class(name)       -- Extends Mode Base; guarantees mutual exclusion
    │            ├── .set_default(arm_fn)           -- Sets implicit fallback arming (or VOID)
    │            ├── .switch_to(incoming)           -- Marks outgoing as switched and triggers .cease()
    │            ├── .ensure_active()               -- Enforces single-active invariant post-cessation
    │            └── binds 'sm' in members          -- Aggregate self-binding (counterpart: 'mg')
    │
    ├── (3d) MODE-GROUP BASE -- non-exclusive habitat
    │      └── .new_mode_group_class(name)          -- Extends Mode Base; no exclusion, members overlap
    │            └── binds 'mg' in members          -- Aggregate self-binding (counterpart: 'sm')
    │
    ├── (3e) REACTOR CONTAINERS -- where a spawned aggregate lives
    │      │   Slot protocol (mutexed reserve; construct runs after, unlocked):
    │      │     key = :slot_reserve()              -- int key, or NO_SLOT(0) on reject
    │      │     :slot_set(key, instance)           -- commit into the reserved slot
    │      │     :slot_free(key)                    -- release; idempotent on unknown key
    │      ├── .new_scalar_container()              -- ScalarReactorContainer: holds 0..1
    │      └── .new_multi_container(admit)          -- MultiReactorContainer: holds 0..N; 'admit'
    │                                                  rejects (default container: dup parameters)
    │
    └── (4) TRACER -- opt-in event history
           ├── Tracer.new()                         -- History ring container (default size = 1)
           ├── Tracer:watch(kind, last)             -- Registers coverage to close silent-nil bugs
           └── Tracer:record(event)                 -- Pushes occurrence and trims front to fit size bound


===============================================================================
COMPONENT MODULE REFERENCE
===============================================================================

1. luau/luau_span_oracle.py
-------------------------------------------------------------------------------
* Mechanism: avoids lexing Luau itself. It takes the text between '{' and each
  successive candidate '}', wraps it in the role's framing, and parses that with
  a headless 'luau-ast' process. The first candidate that parses is the true
  span boundary; braces inside strings, long-bracket comments, and templates
  thus fall out without a Luau lexer.

* Role Classification:
    - CONDITION: frames a rule guard.
    - EXPRESSION: frames a single rvalue.
    - STATEMENT_BLOCK: frames a function body.

* Exceptions:
    - FragmentSyntaxError: no candidate parses; carries the opening-brace file
      offset.
    - OracleError: the 'luau-ast' process failed or timed out.

* Reference Collection:
    - collect_references(source, open, close, mode): wraps the measured span
      in its role frame, parses via the parse_ast JSON seam, walks the AST
      for GLOBAL-rooted dotted chains, and maps locations back to source
      offsets as neutral core Reference pairs. Locals never surface; the
      pseudo-symbols 'e'/'sm'/'mg'/'m' surface as globals by design (the
      validation wrapper binds nothing).


2. luau/location_mapper.py
-------------------------------------------------------------------------------
* Mechanism: a generated line maps back to a source line by the block interval
  it falls in. Boilerplate the transpiler emits is counted (advance); each
  copied fragment registers its interval, recording the column shift its
  indentation introduces. A lookup outside any registered interval is
  boilerplate and maps to None.

* Functional Protocols:
    - .advance(): step the cursor over generated boilerplate lines.
    - .register_fragment(): record a source fragment's interval; return its
      target offset.
    - .source_line_of(): map a target line back to source, or None for
      boilerplate.


3. luau/generated_code_checker.py
-------------------------------------------------------------------------------
* Mechanism: runs 'luau-analyze' over the assembled generated code. Each error
  line is mapped through the location mapper: one landing inside a registered
  fragment interval is attributed to the rule-file author (with its source
  location); one landing outside any interval is flagged a transpiler bug.

* Diagnostic Outputs:
    - Author Error Formatting: '<file>:<line>:<col>: <kind>: <message>'.
    - Transpiler Error Formatting: '[generated code: likely transpiler bug] 
      <kind> at generated line <n> col <n>: <message>'.
