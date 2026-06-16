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

from vut.engine.compare.engine.input.chunk_pipe  import ChunkPipe
from vut.engine.compare.engine.input.input_chunk import InputChunkVoid
from vut.engine.compare.configuration     import Configuration

from   typeguard import typechecked
import asyncio


@typechecked
async def generate_chunk_pairs(config:        Configuration, 
                               subject_pipe:  ChunkPipe,
                               nominal_pipe:  ChunkPipe):
    """YIELDS: [0] subject input chunk
               [1] nominal input chunk

    In general the type of the subject chunk is not equal to the type
    of the nominal chunk.
    """
    # Setup Queues
    q_s, q_n = asyncio.Queue(maxsize=10), asyncio.Queue(maxsize=1000)

    # Start Producers
    tasks = [ subject_pipe.create_producer_task(q_s),
              nominal_pipe.create_producer_task(q_n) ]

    s_item = n_item = InputChunkVoid()
    try:
        while True:
            # Futures: stream exhausted use 'sleep(0)', else use 'queue.get()'
            coro_s = asyncio.sleep(0, result=s_item) if s_item.is_terminal() else q_s.get()
            coro_n = asyncio.sleep(0, result=n_item) if n_item.is_terminal() else q_n.get()

            # Wait in parallel for subject and nominal queue
            s_item, n_item = await asyncio.gather(coro_s, coro_n)

            # Termination Check
            if s_item.is_terminal() and n_item.is_terminal(): break

            # Yield with Padding (EOF == InputChunkTerminal)
            yield s_item, n_item

    finally:
        for t in tasks:
            if not t.done(): t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

@typechecked
async def generate_chunk_pairs_type_aligned(config:       Configuration, 
                                            subject_pipe: ChunkPipe,
                                            nominal_pipe: ChunkPipe):
    """
    YIELDS: (SubjectChunk | None, NominalChunk | None)
    """
    # Setup Queues
    q_s, q_n = asyncio.Queue(maxsize=10), asyncio.Queue(maxsize=1000)

    # Start Producers
    tasks = [ subject_pipe.create_producer_task(q_s),
              nominal_pipe.create_producer_task(q_n) ]

    try:
        # Initial Fetch
        s_prev, n_prev = await asyncio.gather(q_s.get(), q_n.get())

        # Loop while BOTH are valid (not EOF)
        while not s_prev.is_terminal() and not n_prev.is_terminal():
            
            if s_prev.type() == n_prev.type():
                # MATCH
                yield (s_prev, n_prev)
                s_prev, n_prev = await asyncio.gather(q_s.get(), q_n.get())

            else:
                # MISMATCH
                s_next, n_next = await asyncio.gather(q_s.get(), q_n.get())

                if not n_next.is_terminal() and n_next.type() == s_prev.type():
                    yield (None, n_prev)     # Flush the extra Nominal
                    yield (s_prev, n_next)   # Pair held Subject with next Nominal
                    s_prev = s_next
                    n_prev = await q_n.get() # fill the slot of the consumed n_prev

                elif not s_next.is_terminal() and s_next.type() == n_prev.type():
                    yield (s_prev, None)     # pair extra subject with nominal 'None'
                    yield (s_next, n_prev)   # pair matching next subject with previous nominal
                    s_prev = await q_s.get() # fill the slot of the consumed 's_prev'
                    n_prev = n_next

                else: # No way to heal a mismatch of subject and nominal by one look-ahead
                    yield (None, n_prev)     # pair 'None' with prev. nominal 
                    yield (s_prev, None)     # pair prev. subject with nominal 'None'
                    s_prev = s_next          # take next into previous
                    n_prev = n_next

        # If Nominal still has data (Subject hit EOF)
        while not n_prev.is_terminal():
            yield (None, n_prev)
            n_prev = await q_n.get()
        # If Subject still has data (Nominal hit EOF)
        while not s_prev.is_terminal():
            yield (s_prev, None)
            s_prev = await q_s.get()

    finally:
        for t in tasks:
            if not t.done(): t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
