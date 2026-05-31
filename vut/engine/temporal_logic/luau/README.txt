LUAU SUPPORT MODULES
====================

Three modules in 'luau/' provide the Luau-language boundary for the
transpiler: span termination, source-to-target location mapping, and
generated-code type checking. Together they form a pipeline:

    rule-file text
         |
         | find_matching_brace()          [luau_fragment.py]
         v
    (open_offset, end_offset)
         |
         | register_fragment()            [location_mapper.py]
         v
    Source2TargetLocationMapper
         |
         | analyze_text() / analyze_path() [generated_code_checker.py]
         v
    [Diagnostic, ...]  --  format_diagnostic()  -->  error message


0. Luau bootstrap

    bootstrap.lua
    │
    ├── _match(actual, expected)                    -- the one core comparator router
    │
    ├── Comparators (Glob…Pattern)                  -- each: __className + :match(actual)
    │
    ├── Queryable                                   -- 8 methods; needs only _instances()
    │      ├── Event class      (per event kind)    -- _instances() = its Tracer ring
    │      └── Mode registry     (per mode kind)    -- _instances() = live instances
    │
    ├── Space : owns the Tracer; factory for event classes bound to it
    │      ├── Space.new()                          -- instantiates its own Tracer
    │      └── Space:new_event_class(name)          -- Queryable event class, time/dt;
    │                                                  bound to this Space; NO init/deinit
    │
    ├── ModeBase : Queryable-backed registry + Lifecycle
    │      │            (begin_time/begin_event_index, idempotent identity,
    │      │             until-list iteration w/ first-wins, init/deinit dispatch)
    │      └── StateMachineBase : owns member modes, single-active + 'switched',
    │                             default/VOID, own init/deinit, 'sm' binding
    │
    └── Tracer : watch(kind, last); record() pushes into one flat ring per type
                 (no attribute keying); an event class queries this ring

-------------------------------------------------------------------------------
1. luau/luau_fragment.py
-------------------------------------------------------------------------------

A rule-file span is an opaque Luau fragment delimited by '{' and a matching
'}'. The matching '}' is located by 'find_matching_brace'.

  find_matching_brace(source, open_offset, role, oracle) -> int

    'source'       -- the full rule-file text as a string.
    'open_offset'  -- index in 'source' of the opening '{'.
    'role'         -- Role.CONDITION, Role.EXPRESSION, or Role.STATEMENT_BLOCK.
                     Selects the wrapper applied to each candidate span.
    'oracle'       -- object with a 'parse(text) -> ParseResult' method.
                     The standard oracle is LuauOracle().

    Returns the index in 'source' of the matching '}'.

    Raises FragmentSyntaxError(message, open_offset) when no candidate '}'
    produces a parseable fragment. 'open_offset' on the exception locates the
    opening brace in 'source'.

    Raises OracleError(message) on an infrastructure failure of the oracle
    subprocess.

  Role (enum)

    CONDITION       -- guard expression: '& { <expr> }'
    EXPRESSION      -- rvalue:           '{ <luau-expr> }'
    STATEMENT_BLOCK -- body:             '=> { <stmts> }', init, deinit,
                                         on BEGIN, on END

  LuauOracle(binary="luau-ast")

    Standard oracle. Instantiate once; pass to every call of
    'find_matching_brace'. 'binary' is the path to the 'luau-ast' executable.

  ParseResult

    Returned by an oracle's 'parse' method. Fields: 'ok' (bool), 'error' (str
    or None). Custom oracles must return this type.


-------------------------------------------------------------------------------
2. luau/location_mapper.py
-------------------------------------------------------------------------------

The transpiler emits a generated Luau file composed of boilerplate lines and
verbatim-copied fragment lines. 'Source2TargetLocationMapper' records the
mapping from target line numbers back to origin locations in the rule file.
The mapper is driven in emission order: one call per emitted piece.

  Source2TargetLocationMapper()

    Construct once at the start of emission. Drive it as each line is emitted.

  .advance(line_count)

    Account for 'line_count' generated lines (boilerplate, blank lines,
    provenance comments). These lines have no source origin and resolve to None
    on lookup.

  .register_fragment(source_file, source_line, length,
                     indent=0, first_line_prefix=0) -> int

    Register a verbatim fragment of 'length' lines at the current cursor.
    Returns the target line number at which the fragment was placed.

    'source_file'       -- rule-file path, used in Diagnostic.source.file.
    'source_line'       -- zero-based line in 'source_file' of the fragment's
                          first line.
    'length'            -- number of lines in the fragment. Must equal the
                          number of lines emitted for this fragment.
    'indent'            -- column at which every emitted fragment line begins.
    'first_line_prefix' -- extra width emitted before the fragment on its first
                          line only (e.g. 3 for an 'if ' prefix). Zero when the
                          fragment begins its own line.

  .source_line_of(target_line, target_column=0) -> SourceLocation | None

    Resolve a target location to its origin. Returns None when 'target_line'
    falls on a boilerplate line registered via 'advance'.

  .target_line_count -> int

    Total number of target lines accounted for so far (advanced + registered).

  SourceLocation

    Returned by 'source_line_of'. Fields: 'file' (str), 'line' (int),
    'column' (int). All values are zero-based.


-------------------------------------------------------------------------------
3. luau/generated_code_checker.py
-------------------------------------------------------------------------------

'GeneratedCodeChecker' runs 'luau-analyze' on the assembled target text and
maps every diagnostic back to its origin via a 'Source2TargetLocationMapper'.

  GeneratedCodeChecker(mapper, binary="luau-analyze")

    'mapper' -- the 'Source2TargetLocationMapper' built during emission. It
               must describe the same text that is passed to 'analyze_text' or
               'analyze_path'.
    'binary' -- path to the 'luau-analyze' executable.

  .analyze_text(target_text) -> [Diagnostic]

    Write 'target_text' to a temporary file, run 'luau-analyze', and return
    the mapped diagnostics. 'target_text' must be exactly the text described
    by 'mapper', including any '--!strict' or other directives as their own
    emitted lines.

  .analyze_path(target_path) -> [Diagnostic]

    Run 'luau-analyze' on an existing file. The file must be exactly the text
    described by 'mapper'.

    Both methods return an empty list on a clean run. Both raise
    'AnalyzerError(message)' on an infrastructure failure.

  Diagnostic

    Fields:
      'kind'            -- analyzer category string ('TypeError',
                          'SyntaxError', 'LocalUnused', ...).
      'message'         -- analyzer diagnostic text.
      'source'          -- SourceLocation in the rule file, or None when the
                          diagnostic falls on a boilerplate line.
      'target_line'     -- zero-based line in the generated file.
      'target_column'   -- zero-based column in the generated file.
      'is_in_generated_code' -- True when 'source' is None.

  format_diagnostic(diag) -> str

    Render 'diag' as a single human-readable line.
    Author diagnostics: '<file>:<line>:<col>: <kind>: <message>'.
    Generated-code diagnostics: '[generated code: likely transpiler bug]
    <kind> at generated line <n> col <n>: <message>'.
