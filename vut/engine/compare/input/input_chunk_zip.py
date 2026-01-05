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

from vut.engine.compare.input.chunk_pipe     import ChunkPipe
from vut.engine.compare.input.input_chunk    import InputChunkEmpty, E_Chunk
from vut.engine.compare.configuration        import Configuration
from vut.auxiliary.async_helper              import async_zip_longest, \
                                                    prefetch

from   typeguard import typechecked
from   typing    import AsyncIterator
import asyncio


@typechecked
async def pair_for_equivalence_check(config: Configuration, 
                                     subject_line_provider: AsyncIterator, 
                                     nominal_line_provider: AsyncIterator): 
    """YIELDS: [0] subject input chunk
               [1] nominal input chunk
    """
    
    # 1. Setup Pipes
    pipe0 = ChunkPipe(config)
    pipe1 = ChunkPipe(config)
    
    # 2. Control Mechanisms
    # Unbounded queues allow "reading into stack" while waiting
    q_s = asyncio.Queue()
    q_n = asyncio.Queue()
    
    # The GATE: Controls when producers are allowed to fetch
    fetch_gate = asyncio.Event()
    fetch_gate.set() # Start open to get the first items

    # Sentinel for EOF
    EOF = object()

    # 3. Persistent Producer Logic
    async def produce(provider, queue):
        iterator = provider.__aiter__()
        try:
            async for item in iterator:
                await queue.put(item)
                # GATE CHECK:
                # After putting an item, we check if we should pause.
                # We wait here if the gate is closed.
                await fetch_gate.wait()
            await queue.put(EOF)
        except Exception:
            await queue.put(EOF)
            raise

    # 4. Start Producers
    task_s = asyncio.create_task(produce(pipe0.stream_for_equivalence_check(subject_line_provider), q_s))
    task_n = asyncio.create_task(produce(pipe1.stream_for_equivalence_check(nominal_line_provider), q_n))

    try:
        while True:
            # --- FAST PATH ---
            # If both queues have data, we don't need to wait or touch the gate.
            if not q_s.empty() and not q_n.empty():
                # We have a pair!
                # Logic: If we have a backlog, we should STOP fetching to avoid over-eating.
                fetch_gate.clear()
                
                s_item = await q_s.get()
                n_item = await q_n.get()
                
                # EOF Handling
                if s_item is EOF and n_item is EOF:
                    break
                
                s_out = s_item if s_item is not EOF else n_item.empty_clone()
                n_out = n_item if n_item is not EOF else s_item.empty_clone()
                
                yield s_out, n_out
                continue

            # --- WAITING PATH (Case 2) ---
            # One or both are empty.
            # ACTION: Open the gate. 
            # This allows the empty one to fetch, AND the full one to buffer (stack up) 
            # while we wait, exactly as requested.
            fetch_gate.set()
            
            # Wait for data. 
            # Note: We get() sequentially. If q_s is empty, we wait for S.
            # While waiting for S, N's producer sees the open gate and keeps filling q_n.
            s_item = await q_s.get()
            n_item = await q_n.get()

            # (Repeat logic from Fast Path)
            if s_item is EOF and n_item is EOF:
                break

            s_out = s_item if s_item is not EOF else n_item.empty_clone()
            n_out = n_item if n_item is not EOF else s_item.empty_clone()

            yield s_out, n_out

    finally:
        # Cleanup
        fetch_gate.set() # Unblock tasks so they can exit/cancel
        for t in [task_s, task_n]:
            if not t.done(): t.cancel()
            try:                           await t
            except asyncio.CancelledError: pass

@typechecked
async def pair_for_association(config:                Configuration, 
                               subject_line_provider: AsyncIterator, 
                               nominal_line_provider: AsyncIterator): 
    """YIELDS: [0] subject input chunk
               [1] nominal input chunk

    """
    chunk_pipe0 = ChunkPipe(config)
    chunk_pipe1 = ChunkPipe(config)

    # PREFETCH: In the background new data is requested, even if the outer loop does not
    #           'await' and give us a thread, the data is already on the way while the 
    #           CPU is working on the data.
    subject_iterable = prefetch(chunk_pipe0.stream_for_association(subject_line_provider), buffer_size=10)
    nominal_iterable = prefetch(chunk_pipe1.stream_for_association(nominal_line_provider), buffer_size=10)

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
