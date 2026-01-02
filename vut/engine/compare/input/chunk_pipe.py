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
from vut.engine.compare.line_sequence.core       import LineSequence
from vut.engine.compare.potpourri.core           import Potpourri
from vut.engine.compare.input.pattern_finder import PatternFinder
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
    async def generate(self, line_provider: AsyncIterator):
        """Generates 'chunks' from lines of the line provider. A chunk can either
        be a single line or a potpourri (bracketted by '||||' lines).

        The 'line_provider' must implement the '.readline()' function. It returns
        '' as soon as no more input is present. It is supposed to block!

        ASSUME: no line contains '\r'!

        YIELDS: LineSequence       if text element was a line.
                Potpourri          if text element is a potpourri.
                TerminalInputChunk to mark end of stream.
        """
        chunk_type   = E_Chunk.LINE_SEQUENCE
        chunk_class  = LineSequence
        line_list    = []
        start_line_n = 1
        for line_n in count(1):
            line = await line_provider.readline()
            if not line:
                break
            elif self.is_region_delimiter(line):
                if line_list or chunk_class != LineSequence:
                    yield chunk_class(chunk_type, start_line_n, line_n, 
                                      line_list, 
                                      self.configuration)
                line_list = []
                # switch 'Potpourri' <-> 'LineSequence'
                if chunk_class == LineSequence: chunk_class = Potpourri;    chunk_type = E_Chunk.LINE_SEQUENCE
                else:                           chunk_class = LineSequence; chunk_type = E_Chunk.POTPOURRI
                start_line_n = line_n
            else:
                line_list.append(Line(line_n, PatternFinder.do(self, line)))

        if line_list:
            yield chunk_class(chunk_type, start_line_n, line_n, line_list, self.configuration)


