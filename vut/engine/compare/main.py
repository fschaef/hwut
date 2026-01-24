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
Potpourris are marked by '||||' delimiters around the concerned lines.

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
from   vut.engine.compare.engine.association.chunk_pair import ChunkPair
from   vut.engine.compare.input.chunk_pipe              import EquivalenceCheckChunkPipe, \
                                                               AssociationChunkPipe
from   vut.engine.compare.input.input_chunk_zip         import generate_chunk_pairs, \
                                                               generate_chunk_pairs_type_aligned
from   vut.engine.compare.configuration                 import Configuration

from   vut.auxiliary.async_helper                       import AsyncIterator_ensured

from   typeguard import typechecked

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
    """
    assert hasattr(subject_line_provider, "readline")
    assert hasattr(nominal_line_provider, "readline")

    # Ensure that the flyweight-required registry is context-local (thread/asyncio task)
    token = frozen_analogy_db.context_frozen_analogy_db_registry.set(frozen_analogy_db.FrozenAnalogyRegistry()) 

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
        frozen_analogy_db.context_frozen_analogy_db_registry.reset(token)

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

    try:
        analogy_db = AnalogyDb()

        subject = AssociationChunkPipe(config, AsyncIterator_ensured(subject_line_provider))
        nominal = AssociationChunkPipe(config, AsyncIterator_ensured(nominal_line_provider))

        # subject, nominal = 'LineSequence', 'Potpourri' or None
        async for subject, nominal in generate_chunk_pairs_type_aligned(config, subject, nominal):

            result = ChunkPair.from_input_chunks(subject, nominal, analogy_db)
            analogy_db = result.analogy_db()
            yield result

    finally:
        frozen_analogy_db.context_frozen_analogy_db_registry.reset(token)
