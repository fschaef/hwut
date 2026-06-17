"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

EMITTER  --  the world's CODE-GENERATION contract.

The second of the world's three outward faces (span, EMISSION, execution). An
Emitter consumes the resolved meaning construct and produces a standalone
program in the world's target language. The semantic layer drives it; nothing
below the world names the target language.

A world MAY validate the code it emits -- the Luau world runs luau-analyze over
its output and attributes errors home -- but validation is INTERNAL to emission:
it has no outward contract, is never reached from outside the world, and so
appears as no method here. A world that does not validate omits it silently.

STATUS: CONTRACT ONLY. No concrete Emitter is built (the emitter session is
todo-4). This file fixes the shape the future LuauEmitter implements; the method
signature below is provisional and widens when the resolved-program -> target
mapping is designed.
______________________________________________________________________________
"""
from abc import ABC, abstractmethod


class EmissionError(Exception):
    """INFRASTRUCTURE failure during code generation.

    Raised when emission cannot proceed for a reason the rule author cannot fix
    (a missing target-language tool, an internal codegen invariant violated).
    Distinct from a rule-file error, which is caught earlier by the semantic
    checks and never reaches the emitter.
    """
    pass


class Emitter(ABC):
    """Abstract boundary the semantic layer uses to generate target code.

    A concrete emitter consumes the resolved program and returns the text of a
    standalone program in the world's target language. The semantic layer
    constructs nothing here; an emitter instance is the world's contribution to
    the back of the pipeline, the counterpart of the SpanOracle at the front.
    Keeping this abstract is what lets a second world (C, Python, ...) supply its
    own code generator with no change above the world.
    """

    @abstractmethod
    def emit(self, resolved_program):
        """RETURN: str, the complete source text of the generated program.

        Raises EmissionError on infrastructure failure.

        'resolved_program' is the frozen semantic artefact (the resolved
        meaning construct: AST, scope tree, resolutions, mounts, cascade,
        queried events, source map). The emitter reads it and never mutates it.
        A world that validates its output does so inside this call, before
        returning.
        """
        raise NotImplementedError
