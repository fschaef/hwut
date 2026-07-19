"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Comparing two input streams: 'subject' and 'nominal'

The stream 'subject' is supposed to be the output of a test application.  The
stream 'nominal' is the stored-away reference output of a good test run. The text
provided by a stream is interpreted in two ways:

-- line sequences, where the lines in the subject must occur in the same
                   sequence as in the nominal.

-- potpourri,      where the same lines must occur, but not necessarily
                   in the same sequence.

A stream can consist of multiple blocks of line sequences and potpourris.
Regions are framed as "##! <handler> [<param>|<param>=<value>]*" ... "####"
lines; e.g. "##! potpourri" opens an order-free block ('region/registry.py').

API:

  compare(subject_stream, nominal_stream) -> bool

     returns 'True' if both streams are equivalent, 'False' else.

  associate(subject_stream, nominal_stream)

     yields comparison information about the lines and potpourris that appear
     in the input streams.

The only requirement on the objects 'subject_stream' and 'nominal_stream'
is that they must provide the function:

  .readline() -> non-empty 'str', in case there is a line that can be read.
                 "",              if end of stream has been reached.
________________________________________________________________________________
"""
from   vut.engine.compare.engine.analogy_db             import AnalogyDb
import vut.engine.compare.engine.frozen_analogy_db      as     frozen_analogy_db
from   vut.engine.compare.engine                        import constraints
from   vut.engine.compare.core.chunk_pair import ChunkPair
from   vut.engine.compare.engine.input.chunk_pipe              import EquivalenceCheckChunkPipe, \
                                                               AssociationChunkPipe
from   vut.engine.compare.engine.input.input_chunk_zip         import generate_chunk_pairs, \
                                                               generate_chunk_pairs_type_aligned
from   vut.engine.compare.configuration                 import Configuration

from   vut.auxiliary.async_helper                       import AsyncIterator_ensured

from   typeguard import typechecked

import io
from   contextlib import aclosing

@typechecked
async def is_equivalent(config: Configuration,
                        subject_line_provider,
                        nominal_line_provider) -> bool:
    """RETURNS: True, if subject and nominal stream are equivalent.
                False, else.

    The function operates on coroutines reading lines from line providers.
    As soon as 'False' can be stated it aborts immediately-not consuming
    any further input. Caller functions then, might then terminate the data
    producing process.

    ONLY REQUIREMENT: line provider member function '.readline()'.

    The '.get()' function either returns a line of text or 'None' in case
    that the stream terminated.

    CROSS-CHECK (debug): with 'config.cross_check_f' set (or environment
    variable VUT_COMPARE_CROSS_CHECK=1) the verdict is ADDITIONALLY derived
    through the Lawyer's full association and both must agree -- THE LAW of
    'engine/semantics.py', asserted live on every call. This mode buffers
    the input streams entirely (no early-abort economy).
    """
    if config.cross_check_f:
        return await _is_equivalent_cross_checked(config,
                                                  subject_line_provider,
                                                  nominal_line_provider)
    return await _is_equivalent_fast(config,
                                     subject_line_provider,
                                     nominal_line_provider)

async def _is_equivalent_fast(config,
                              subject_line_provider,
                              nominal_line_provider) -> bool:
    """RETURNS: True, if subject and nominal stream are equivalent.
                False, else.

    The hand-tuned fast path (the 'Judge'): chunk-by-chunk fast-fail scan
    that aborts on the first non-equivalent chunk pair.
    """
    assert hasattr(subject_line_provider, "readline")
    assert hasattr(nominal_line_provider, "readline")

    # Ensure that the flyweight-required registry is context-local (thread/asyncio task)
    token = frozen_analogy_db.context_frozen_analogy_db_registry.set(frozen_analogy_db.FrozenAnalogyRegistry())
    # Stateful constraints: fresh space per run; static checks are LOUD here
    # (before any line is read) -- see 'engine/constraints.py'.
    token_constraints = constraints.context_new(config)

    try:
        analogy_db = AnalogyDb()
        subject    = EquivalenceCheckChunkPipe(config, AsyncIterator_ensured(subject_line_provider))
        nominal    = EquivalenceCheckChunkPipe(config, AsyncIterator_ensured(nominal_line_provider))

        # subject, nominal = 'LINE' or 'POTPOURRI'
        async for subject, nominal in generate_chunk_pairs(config, subject, nominal):
            verdict,   \
            analogy_db = subject.is_equivalent_to_nominal(nominal, analogy_db)
            # analogy db is updated as required to main 'equivalence', else not (of course)

            if not verdict:
                return False
        else:
            return True
    finally:
        constraints.context_constraint_context.reset(token_constraints)
        frozen_analogy_db.context_frozen_analogy_db_registry.reset(token)

@typechecked
async def is_equivalent_by_association(config: Configuration,
                                       subject_line_provider,
                                       nominal_line_provider) -> bool:
    """RETURNS: True, if subject and nominal stream are equivalent -- verdict
                      derived through the Lawyer's full association.
                False, else.

    The 'degenerate Judge': instead of the hand-tuned fast path, the complete
    edit search of 'associate()' runs and its result is reduced to a boolean
    via 'ChunkPair.is_equivalent()'. By THE LAW ('engine/semantics.py') the
    result MUST equal 'is_equivalent()'. Used by the cross-check mode and by
    benchmarking; also the reference implementation should the fast path ever
    be in doubt.
    """
    # 'aclosing': an early 'return False' must finalize the generator IN THIS
    # context -- 'associate' resets a ContextVar in its 'finally'; default
    # event-loop finalization would run it in a foreign context and fail.
    async with aclosing(associate(config, subject_line_provider,
                                          nominal_line_provider)) as pair_iterable:
        async for chunk_pair in pair_iterable:
            if not chunk_pair.is_equivalent():
                return False
    return True

class CrossCheckError(AssertionError):
    """Judge and Lawyer disagreed on an input pair -- THE LAW of
    'engine/semantics.py' is broken. Carries the complete buffered input so
    the counterexample is reproducible.
    """
    def __init__(self, verdict_judge, verdict_lawyer, subject_txt, nominal_txt):
        self.verdict_judge  = verdict_judge
        self.verdict_lawyer = verdict_lawyer
        self.subject_txt    = subject_txt
        self.nominal_txt    = nominal_txt
        super().__init__(
            "THE LAW is broken: is_equivalent() -> %s, but association -> %s\n"
            "--- subject %s\n%s--- nominal %s\n%s--- end\n"
            % (verdict_judge, verdict_lawyer,
               "-" * 32, subject_txt, "-" * 32, nominal_txt))

async def _buffer_lines(line_provider) -> str:
    """RETURNS: str, the entire remaining content of 'line_provider'.
    """
    reader    = AsyncIterator_ensured(line_provider)
    line_list = []
    while True:
        line = await reader.readline()
        if not line:
            break
        line_list.append(line)
    return "".join(line_list)

async def _is_equivalent_cross_checked(config,
                                       subject_line_provider,
                                       nominal_line_provider) -> bool:
    """RETURNS: True/False, the Judge's verdict -- after asserting that the
                Lawyer's verdict agrees (raises 'CrossCheckError' else).

    Debug harness behind 'config.cross_check_f'. Both faces must see the
    identical input, so the streams are buffered completely up-front; the
    fast path's early-abort economy is intentionally sacrificed here.
    """
    subject_txt = await _buffer_lines(subject_line_provider)
    nominal_txt = await _buffer_lines(nominal_line_provider)

    verdict_judge  = await _is_equivalent_fast(config,
                                               io.StringIO(subject_txt),
                                               io.StringIO(nominal_txt))
    verdict_lawyer = await is_equivalent_by_association(config,
                                                        io.StringIO(subject_txt),
                                                        io.StringIO(nominal_txt))
    if verdict_judge != verdict_lawyer:
        raise CrossCheckError(verdict_judge, verdict_lawyer,
                              subject_txt, nominal_txt)
    return verdict_judge

@typechecked
async def associate(config: Configuration, subject_line_provider, nominal_line_provider):
    """YIELDS: ChunkPair

    where:

         ChunkPair.type() in (LINE_SEQUENCE, POTPOURRI)

    This function iterates over subject and nominal lines and compares them.
    When lines are too deviant from each other, 'plugs' in one sequence are
    inserted until it fits again the other sequences. Line associations are
    reported (yielded) in blocks of their type, i.e. assocations of
    'LineSequence'-s and 'Potpourri'-s are yielded in separate objects
    of type 'ChunkPair'.

    Data structure:    ChunkPair(list[LinePair])

                       LinePair: .line_n                             
                                 .subject_list = Cells ...           
                                 .nominal_list = Cells ...           

    HINT: Use 'AnalogyProvenanceDb' to track the origins of analogies!
          Simply pass incoming ChunkPairs to '.update()'.

    SEE: "feeder/ui.py", for example how to feed an user interface with that 
         information.
    """
    assert hasattr(subject_line_provider, "readline")
    assert hasattr(nominal_line_provider, "readline")

    # Ensure that the flyweight-required registry is context-local (thread/asyncio task)
    token = frozen_analogy_db.context_frozen_analogy_db_registry.set(frozen_analogy_db.FrozenAnalogyRegistry())
    # Stateful constraints: fresh space per run; static checks are LOUD here
    # (before any line is read) -- see 'engine/constraints.py'.
    token_constraints = constraints.context_new(config)

    try:
        analogy_db = AnalogyDb()

        subject = AssociationChunkPipe(config, AsyncIterator_ensured(subject_line_provider))
        nominal = AssociationChunkPipe(config, AsyncIterator_ensured(nominal_line_provider))

        # subject, nominal = 'LineSequence', 'Potpourri' or None
        async for subject, nominal in generate_chunk_pairs_type_aligned(config, subject, nominal):

            result = ChunkPair.from_input_chunks(subject, nominal, analogy_db)
            analogy_db = result.analogy_db()

            # Stateful constraints: a non-equivalent chunk (of ANY type) is
            # the Judge's abort point -- the Lawyer kills the space so no
            # later binding is processed either (THE LAW).
            context = constraints.context_get()
            if (context is not None and context.alive
                    and not result.is_equivalent()):
                context.kill()

            yield result

    finally:
        constraints.context_constraint_context.reset(token_constraints)
        frozen_analogy_db.context_frozen_analogy_db_registry.reset(token)
