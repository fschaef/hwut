"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

WORLD  --  the target-language axis.

A WORLD is the embedded/target language the rule file is written against and
compiled out to. It exposes exactly three outward faces, each an ABC defined
HERE and nowhere else -- the world is the sole authority for what a target
language must provide:

    span        SpanOracle   measure an opaque '{ ... }' span; collect its
                             references.            (front of the pipeline)
    emission    Emitter      generate a standalone program from the resolved
                             meaning construct.     (back of the pipeline)
    execution   Runner       run the generated program over a trace.

Validation (checking emitted code) is INTERNAL to emission, has no outward
contract, and so is no face of its own.

One concrete world ships: world/luau/ (the reference implementation). Adding a
target language means adding a sibling (world/c/, world/python/, ...) that
implements these three ABCs; no component above the world names a language.
______________________________________________________________________________
"""
from .span_oracle import SpanOracle, SpanResult, Reference, SpanMode, \
                         SpanSyntaxError, SpanOracleError
from .emission    import Emitter, EmissionError
from .execution   import Runner,  ExecutionError
