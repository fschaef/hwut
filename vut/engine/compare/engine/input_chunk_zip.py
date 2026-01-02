"""SPDX-License: MIT; (C) Frank-Rene Schäfer; Project: hwut
_______________________________________________________________________________

PURPOSE: Yielding pairs of 'InputChunk'-s from subject and nominal to be
         compared.

The 'ChunkPipe' interprets the input streams of subject and nominal. An
input chunk can be:

   -- LineSequence: set of lines where the sequence is *relevant*.

   -- Potpourri:    set of lines where the sequence is *unimportant*.

The function 'generate()' yields pairs of those input chunks to be
compared.
_______________________________________________________________________________
"""

from vut.engine.compare.tolerance.chunk_pipe import ChunkPipe
from vut.engine.compare.engine.input_chunk   import InputChunkEmpty, E_Chunk
from vut.engine.compare.configuration        import Configuration
from vut.auxiliary.async_helper              import async_zip_longest, \
                                                    prefetch

from typeguard import typechecked
from typing    import AsyncIterator


@typechecked
async def do(config:                Configuration, 
             subject_line_provider: AsyncIterator, 
             nominal_line_provider: AsyncIterator, 
             align_f:               bool):
    """YIELDS: [0] subject input chunk
               [1] nominal input chunk

    Input chunk: 'LineSequence', 'Potpourri', or None.

    If one line provider exhausts, the 'fillvalue' is setup as its input chunk.
    When both line providers exhaust, the generator terminates.
    """
    chunk_pipe = ChunkPipe(config)

    # PREFETCH: In the background new data is requested, even if the outer loop does not
    #           'await' and give us a thread, the data is already on the way while the 
    #           CPU is working on the data.
    subject_iterable = prefetch(chunk_pipe.generate(subject_line_provider), buffer_size=10)
    nominal_iterable = prefetch(chunk_pipe.generate(nominal_line_provider), buffer_size=10)

    if not align_f: 
        async for s, n in async_zip_longest(subject_iterable, nominal_iterable):
            if s is None: s = n.empty_clone()
            if n is None: n = s.empty_clone()
            yield s, n
    else:           
        # In async generators, 'yield from' is replaced by 'async for ... yield'
        async for s, n in _zip_aligned(subject_iterable, nominal_iterable):
            yield s, n


async def _zip_aligned(subject_iterable, nominal_iterable):
    """YIELDS: [0] subject input chunk
               [1] nominal input chunk

    where the same-type input chunks are 'aligned'. That is, the chunks are 
    either of the same type or one of them is 'None'. 
    """
    empty = InputChunkEmpty()
    subject_delayed = nominal_delayed = empty

    async def _flush_delayed():
        if nominal_delayed.type() != E_Chunk.EMPTY: yield None, nominal_delayed
        if subject_delayed.type() != E_Chunk.EMPTY: yield subject_delayed, None

    async for subject, nominal in async_zip_longest(subject_iterable, nominal_iterable):
        assert not (subject is None and nominal is None)

        if nominal and nominal.type() == subject_delayed.type():
            if nominal_delayed.type() != E_Chunk.EMPTY: yield None, nominal_delayed
            yield subject_delayed, nominal
            subject_delayed = subject if subject is not None else empty
            nominal_delayed = empty

        elif subject and subject.type() == nominal_delayed.type():
            if subject_delayed.type() != E_Chunk.EMPTY: yield subject_delayed, None
            yield subject, nominal_delayed
            subject_delayed = empty
            nominal_delayed = nominal if nominal is not None else empty

        else:
            # Replace 'yield from' with explicit loop
            async for s_del, n_del in _flush_delayed():
                yield s_del, n_del
                
            subject_delayed = nominal_delayed = empty
            if   subject is None:                  yield None, nominal
            elif nominal is None:                  yield subject, None
            elif subject.type() == nominal.type(): yield subject, nominal
            else:                                  subject_delayed, nominal_delayed = subject, nominal

        assert not (subject_delayed.type() == nominal_delayed.type()) \
               or (subject_delayed.type() == E_Chunk.EMPTY)

    async for s_del, n_del in _flush_delayed():
        yield s_del, n_del
