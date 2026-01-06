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
    subject_queue = asyncio.Queue(maxsize=2)
    nominal_queue = asyncio.Queue(maxsize=10)

    # Sentinel for EOF
    EOF = object()

    # 4. Start Producers
    ## task_s = asyncio.create_task(subject_pipe.produce(subject_queue, fetch_gate, EOF))
    ## task_n = asyncio.create_task(nominal_pipe.produce(nominal_queue, fetch_gate, EOF))

    task_s = subject_pipe.create_producer_task(subject_queue, EOF)
    task_n = nominal_pipe.create_producer_task(nominal_queue, EOF)

    def prepare_gather(last_s_item, last_n_item):
        """RETURNS: subject and nominal getter dependent on EOF has been 
                    reached or not
        """
        def _get_getter(last_item, queue):
            if last_item is EOF: return asyncio.sleep(0, result=EOF)
            else:                return queue.get()
        return _get_getter(last_s_item, subject_queue), \
               _get_getter(last_n_item, nominal_queue)
               
    def prepare_yield(s_item, n_item):
        s_out = s_item if s_item is not EOF else n_item.empty_clone()
        n_out = n_item if n_item is not EOF else s_item.empty_clone()
        return s_out, n_out

    try:
        s_item, n_item = None, None
        while True:
            abort_f = False
            while not subject_queue.empty() and not nominal_queue.empty(): 
                # item is EOF <=> queue.empty() 
                s_item = await subject_queue.get()
                n_item = await nominal_queue.get()
                if s_item is EOF and n_item is EOF: abort_f=True; break
                yield prepare_yield(s_item, n_item)
            if abort_f: break

            subject_get, nominal_get = prepare_gather(s_item, n_item)

            s_item, n_item = await asyncio.gather(subject_get, nominal_get)
                
            if s_item is EOF and n_item is EOF: break
            
            yield prepare_yield(s_item, n_item)

    finally:
        # Cleanup
        for t in [task_s, task_n]:
            if not t.done(): t.cancel()
            try:                           await t
            except asyncio.CancelledError: pass

