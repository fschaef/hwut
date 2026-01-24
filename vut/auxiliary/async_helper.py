import asyncio
import collections
from   typing import AsyncIterator

class AsyncStreamReaderAdapter(collections.abc.AsyncIterator):
    def __init__(self, sync_stream):
        # sync_stream might be a file-handle OR a generator
        self.sync_stream = sync_stream

        if hasattr(sync_stream, "readline"):
            if asyncio.iscoroutinefunction(sync_stream.readline):
                self._read_call = sync_stream.readline
                self._is_async = True
            else:
                self._read_call = sync_stream.readline
                self._is_async = False
            self._readline = True
        else:
            self._readline = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        line = await self.readline()
        if not line:
            raise StopAsyncIteration
        return line

    async def readline(self):
        # 1. Handle standard file-like objects
        if self._readline:
            if self._is_async: return await self._read_call()
            else:              return self._read_call()
        
        # 2. Handle generators/iterators (common in tests)
        try:
            # We use next() because it's a synchronous generator
            return next(self.sync_stream)
        except StopIteration:
            return "" # Return empty string to signal EOF to our __anext__

async def async_zip_longest(aiter1, aiter2, sentinel=None):
    """Asynchronous version of itertools.zip_longest."""

    async def next_or_sentinel(aiter):
        try:
            return await aiter.__anext__()
        except StopAsyncIteration:
            return sentinel

    while True:
        # Fetch next from both concurrently
        res1, res2 = await asyncio.gather(
            next_or_sentinel(aiter1),
            next_or_sentinel(aiter2)
        )

        if res1 is sentinel and res2 is sentinel:
            break
            
        yield (None if res1 is sentinel else res1), \
              (None if res2 is sentinel else res2)

def AsyncIterator_ensured(input_obj) -> AsyncIterator:
    """RETURNS: Either 
                (1) 'input_obj' itself, if it can serve as an 'AsyncIterator'
                (2) A wrapper version of 'input_obj', which can serve as 'AsyncIterator'
    """
    if hasattr(input_obj, 'readline'):
        if isinstance(input_obj, AsyncIterator):
            return input_obj

    return AsyncStreamReaderAdapter(input_obj)

async def prefetch(aiter, buffer_size=1):
    """
    Decouples I/O from computation by pre-fetching items in the background. This 
    allows the OS to fetch the next chunk of data while the CPU is busy computing
    other things (usefule in an async for loop).
    """
    # Maxsize limits memory usage; the producer will 'wait' if the engine
    # falls too far behind.
    queue = asyncio.Queue(maxsize=buffer_size)
    
    # Internal sentinel to mark the end of the stream
    _EOF = object()

    async def producer():
        try:
            async for item in aiter:
                await queue.put(item)
        finally:
            # Always ensure the consumer knows we are done, even on error
            await queue.put(_EOF)

    # Schedule the producer to run in the background event loop
    task = asyncio.create_task(producer())

    try:
        while True:
            item = await queue.get()
            if item is _EOF:
                break
            yield item
    finally:
        # Cleanup: ensure we don't leave a dangling background task
        # if the engine stops early (e.g. a mismatch or user cancel)
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
