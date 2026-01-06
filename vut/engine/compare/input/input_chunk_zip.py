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
from vut.engine.compare.configuration        import Configuration

from   typeguard import typechecked
import asyncio


@typechecked
async def pair_for_equivalence_check(config: Configuration, 
                                     subject_pipe:   ChunkPipe,
                                     nominal_pipe:   ChunkPipe):
    """YIELDS: [0] subject input chunk
               [1] nominal input chunk
    """
    
    # Unbounded queues allow "reading into stack" while waiting
    subject_queue = asyncio.Queue()
    nominal_queue = asyncio.Queue()
    
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
    task_s = asyncio.create_task(produce(subject_pipe.do(), subject_queue))
    task_n = asyncio.create_task(produce(nominal_pipe.do(), nominal_queue))

    try:
        while True:
            # --- FAST PATH ---
            # If both queues have data, we don't need to wait or touch the gate.
            if not subject_queue.empty() and not nominal_queue.empty():
                # We have a pair!
                # Logic: If we have a backlog, we should STOP fetching to avoid over-eating.
                fetch_gate.clear()
                
                s_item = await subject_queue.get()
                n_item = await nominal_queue.get()
                
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
            # Note: We get() sequentially. If subject_queue is empty, we wait for S.
            # While waiting for S, N's producer sees the open gate and keeps filling nominal_queue.
            s_item = await subject_queue.get()
            n_item = await nominal_queue.get()

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

