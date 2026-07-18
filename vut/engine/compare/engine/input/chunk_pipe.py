"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Chunk pipe -- interpretation of input text as 'InputChunk' objects.

A chunk pipe absorbs lines of text from a 'line provider', i.e. an object
hat responds to a function:
 
                 .readline()
    
lines are then passed through the 'PatternFinder' to transform text into
'LineElement'-s such as numbers, whitespace or user-defined patterns.  A
sequence of 'LineElement'-s make up for a semantic representation of a text
line.

There are two types of list of lines:

 (i) LineSequence: where the sequence of lines matter for equivalence
                   consideration.

 (ii) Potpourri: where the exact sequence of lines does not matter in 
                 equivalence considerations. It is only required that
                 each line has its equivalent counterpart-somewhere.
_______________________________________________________________________________
""" 
from vut.engine.compare.engine.enums             import E_Chunk 
from vut.engine.compare.engine.line              import Line 
from vut.engine.compare.engine.input.input_chunk        import InputChunk,         \
                                                        InputChunkTerminal, \
                                                        InputChunk_factory
from vut.engine.compare.engine.input.pattern_finder     import PatternFinder
from vut.engine.compare.engine.input.line_scanner       import E_LineClass,       \
                                                        INSIGNIFICANT_LINE_CLASS_SET, \
                                                        classify
from vut.engine.compare.configuration            import Configuration

from itertools import count
from typeguard import typechecked
from typing    import AsyncIterator
import asyncio


class ChunkPipe:
    @typechecked
    def __init__(self, configuration: Configuration, line_provider: AsyncIterator):
        PatternFinder.__init__(self, configuration.pattern_finder)
        self.configuration = configuration
        self.line_provider = line_provider
        self.pf            = PatternFinder(self.configuration.pattern_finder)

    def create_producer_task(self, queue, fetch_gate = None):
        return asyncio.create_task(self._produce(queue, fetch_gate))

    async def _produce(self, queue, fetch_gate: asyncio.Event | None):
        try:
            sentinel = InputChunkTerminal()

            async for item in self.yield_input_chunks():
                await queue.put(item)
                if fetch_gate is not None:  # Pause, if someone stops you
                    await fetch_gate.wait()
            await queue.put(sentinel)

        except Exception:
            import traceback
            traceback.print_exc()
            await queue.put(sentinel)
            raise

class EquivalenceCheckChunkPipe(ChunkPipe):
    """PACKAGING POLICY (classification: 'engine/input/line_scanner.py'):

        REGION_DELIMITER   flush + toggle region framing
        BLANK / IGNORED    DROP -- the Judge never sees insignificant lines
        CONTENT            emit; in LINE context, a whole-line
                           VISIBLE_NOTHING is additionally skipped
                           (equals NO line at all -- see
                           'Line.is_visible_nothing'; the Lawyer's sequence
                           search skips it as GOOD_INSERT/GOOD_DELETE, so
                           the Judge must skip it likewise, THE LAW).
                           Potpourri keeps such lines; both faces count
                           them there.
    """
    @typechecked
    async def yield_input_chunks(self) -> InputChunk:
        chunk_type   = E_Chunk.LINE
        line_list    = []
        start_line_n = 1

        for line_n in count(1):
            line = await self.line_provider.readline()
            if not line:
                break

            line_class = classify(line, self.pf)

            if line_class is E_LineClass.REGION_DELIMITER:
                if chunk_type is E_Chunk.POTPOURRI and line_list:
                    # Flush buffered Potpourri
                    yield InputChunk_factory(chunk_type, start_line_n, line_n,
                                            line_list, self.configuration)

                line_list = []
                # switch 'Potpourri' <-> 'LineSequence'
                if chunk_type is E_Chunk.LINE: chunk_type = E_Chunk.POTPOURRI
                else:                          chunk_type = E_Chunk.LINE
                start_line_n = line_n
            elif line_class in INSIGNIFICANT_LINE_CLASS_SET:
                continue
            else:
                assert line_class is E_LineClass.CONTENT
                processed_line = Line(line_n, line, self.pf)

                if chunk_type is E_Chunk.LINE:
                    if processed_line.is_visible_nothing():
                        continue
                    yield InputChunk_factory(chunk_type, line_n, line_n,
                                            [processed_line], self.configuration)
                else:
                    line_list.append(processed_line)

        # Handle trailing potpourri block if stream ends without closing delimiter
        if chunk_type is E_Chunk.POTPOURRI and line_list:
            yield InputChunk_factory(chunk_type, start_line_n, line_n, 
                                    line_list, self.configuration)

class AssociationChunkPipe(ChunkPipe):
    """PACKAGING POLICY (classification: 'engine/input/line_scanner.py'):

        REGION_DELIMITER   flush + toggle region framing
        BLANK / IGNORED    KEEP -- the Lawyer displays every input line;
                           insignificant lines become neutral filler pairs
                           (see 'LinePair.is_equivalent')
        CONTENT            keep
    """
    @typechecked
    async def yield_input_chunks(self) -> InputChunk:
        """YIELDS: Chunks of input useful for association.
        """
        chunk_type   = E_Chunk.LINE_SEQUENCE
        line_list    = []
        start_line_n = 1
        for line_n in count(1):
            line = await self.line_provider.readline()
            if not line:
                break
            elif classify(line, self.pf) is E_LineClass.REGION_DELIMITER:
                if line_list or chunk_type is not E_Chunk.LINE_SEQUENCE:
                    yield InputChunk_factory(chunk_type, start_line_n, line_n,
                                            line_list,
                                            self.configuration)
                line_list = []
                # switch 'Potpourri' <-> 'LineSequence'
                if chunk_type is E_Chunk.LINE_SEQUENCE: chunk_type = E_Chunk.POTPOURRI
                else:                                   chunk_type = E_Chunk.LINE_SEQUENCE
                start_line_n = line_n
            else:
                # BLANK / IGNORED / CONTENT alike: kept for display.
                line_list.append(Line(line_n, line, self.pf))

        if line_list:
            yield InputChunk_factory(chunk_type, start_line_n, line_n, line_list, self.configuration)


