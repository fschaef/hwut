===============================================================================
WORLD  --  THE TARGET-LANGUAGE AXIS
===============================================================================

A WORLD is the embedded/target language a rule file is written against and
compiled out to. The rule grammar is language-neutral; the world is where
language-specificity is quarantined. The world is the SOLE authority for what a
target language must provide -- no component above it names a language, and no
component below it defines the world's interface.

A world exposes THREE outward faces, each an ABC defined in this directory:

    .------------- pipeline ------------------------------------------.
    |  front                                                back      |
    |   span   ----parse---- ... ----resolve---- emission -- execution|
    '-----------------------------------------------------------------'

    span        SpanOracle  (span_oracle.py)   measure an opaque '{ ... }'
                            span and collect the names referenced inside it.
                            Consumed by the LEXER, through the abstract ABC --
                            the lexer never names a language.

    emission    Emitter     (emission.py)      generate a standalone program
                            in the target language from the resolved meaning
                            construct. Consumed by the SEMANTIC layer.

    execution   Runner      (execution.py)     run the generated program over
                            a trace, returning its output for HWUT comparison.

VALIDATION IS INTERNAL TO EMISSION. A world may check the code it emits; the
Luau world runs luau-analyze and attributes errors home. This has NO outward
contract -- it is reached only from inside emission, never from above the world,
and so is no face of its own and no ABC here.

-------------------------------------------------------------------------------
THE ABCs
-------------------------------------------------------------------------------

    span_oracle.py   SpanOracle  -- find_close, collect_references, delimiters;
                     plus the neutral vocabulary Reference / SpanResult /
                     SpanMode and the errors SpanSyntaxError / SpanOracleError.
                     BUILT.
    emission.py      Emitter     -- emit(resolved_program) -> str; EmissionError.
                     CONTRACT ONLY (todo-4); signature provisional.
    execution.py     Runner      -- run(program_text, trace) -> str;
                     ExecutionError. CONTRACT ONLY and THIN (todo-4); the
                     contract grows when a second world arrives.

The three are co-equal faces of one interface, re-exported from __init__.py --
the world authority. A second target language is a sibling directory
implementing all three.

-------------------------------------------------------------------------------
WORLDS
-------------------------------------------------------------------------------

    luau/   the reference world (Roblox's Luau). span BUILT; emission and
            execution UNBUILT (todo-4); their substrate -- location mapping and
            the internal generated-code validator -- already present. See
            luau/__init__.py for what is re-exported (the validator is not).

-------------------------------------------------------------------------------
DEPENDENCIES
-------------------------------------------------------------------------------

A concrete world imports its own face ABCs from this package and the neutral
Reference vocabulary they carry. It imports nothing from the lexer, the parser,
or the semantic layer: the contract points INTO the world (consumers depend on
the ABCs), never out of it.
