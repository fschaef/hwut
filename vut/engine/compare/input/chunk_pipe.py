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
from vut.engine.compare.input.input_chunk        import InputChunk
from vut.engine.compare.input.pattern_finder     import PatternFinder
from vut.engine.compare.configuration            import Configuration

from itertools import count
from typeguard import typechecked
from typing    import AsyncIterator

class ChunkPipe(PatternFinder):
    @typechecked
    def __init__(self, configuration: Configuration):
        PatternFinder.__init__(self, configuration.pattern_finder)
        self.configuration = configuration

    @typechecked
    async def stream_for_equivalence_check(self, line_provider: AsyncIterator) -> InputChunk:
        async for _ in self.stream_for_association(line_provider):
            yield _

    @typechecked
    async def stream_for_association(self, line_provider: AsyncIterator) -> InputChunk:
        """YIELDS: Chunks of input useful for association.
        """
        chunk_type   = E_Chunk.LINE_SEQUENCE
        line_list    = []
        start_line_n = 1
        for line_n in count(1):
            line = await line_provider.readline()
            if not line:
                break
            elif self.is_region_delimiter(line):
                if line_list or chunk_type is not E_Chunk.LINE_SEQUENCE:
                    yield InputChunk(chunk_type, start_line_n, line_n, 
                                     line_list, 
                                     self.configuration)
                line_list = []
                # switch 'Potpourri' <-> 'LineSequence'
                if chunk_type is E_Chunk.LINE_SEQUENCE: chunk_type = E_Chunk.POTPOURRI
                else:                                   chunk_type = E_Chunk.LINE_SEQUENCE
                start_line_n = line_n
            else:
                line_list.append(Line(line_n, PatternFinder.do(self, line)))

        if line_list:
            yield InputChunk(chunk_type, start_line_n, line_n, line_list, self.configuration)


