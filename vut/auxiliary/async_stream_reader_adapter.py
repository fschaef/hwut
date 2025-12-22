class AsyncStreamReaderAdapter:
    def __init__(self, sync_stream):
        self.sync_stream = sync_stream

    async def readline(self):
        # The baby step: just wrap the sync call in a coroutine
        return self.sync_stream.readline()
