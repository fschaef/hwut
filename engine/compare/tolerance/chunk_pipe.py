"""SPDX-Linces: MIT; Project HWUT; (C) Frank-Rene Schaefer
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
from ut.engine.compare.engine.line              import Line 
from ut.engine.compare.engine.input_chunk       import E_Chunk, \
                                                       LineSequence, \
                                                       InputChunkTerminal
from ut.engine.compare.tolerance.pattern_finder import PatternFinder

from itertools import count

class ChunkPipe(PatternFinder):
    def __init__(self, configuration):
        PatternFinder.__init__(self, configuration.pattern_finder)
        self.configuration = configuration

    def generate(self, line_provider):
        """Generates 'chunks' from lines of the line provider. A chunk can either
        be a single line or a potpourri (bracketted by '||||' lines).

        The 'line_provider' must implement the '.readline()' function. It returns
        '' as soon as no more input is present. It is supposed to block!

        ASSUME: no line contains '\r'!

        YIELDS: LineSequence       if text element was a line.
                Potpourri          if text element is a potpourri.
                TerminalInputChunk to mark end of stream.
        """
        assert hasattr(line_provider, "readline")

        chunk_class  = LineSequence
        line_list    = []
        start_line_n = 1
        for line_n in count(1):
            line = line_provider.readline()
            if not line:
                break
            elif self.is_irrelevant(line):
                continue
            elif self.is_region_delimiter(line):
                if line_list or chunk_class != LineSequence:
                    yield chunk_class(start_line_n, line_n, line_list, self.configuration)
                line_list = []
                # switch 'potpourri' <-> 'line list'
                chunk_class = chunk_class.contrary()
                start_line_n = line_n
            else:
                line_list.append(Line(line_n, PatternFinder.do(self, line)))

        if line_list:
            yield chunk_class(start_line_n, line_n, line_list, self.configuration)

        yield InputChunkTerminal(line_n)

