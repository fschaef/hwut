"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: 'Potpourri' input chunk.

LineSequence: set of text lines where the sequence DOES NOT matter.

The two main functions of 'Potpourri' are (derived from 'InputChunk')

   .compare()           --> determines whether the chunk is equivalent to
                            another.
   .line_pairs() --> determines which lines should be best associated
                            for display.
________________________________________________________________________________
"""
from   vut.engine.compare.input.input_chunk            import InputChunk, E_Chunk
from   vut.engine.compare.engine.line                  import Line


class Potpourri(InputChunk):
    """Set of lines where the sequence does not matter.
    """
    def type(self):
        return E_Chunk.POTPOURRI

    def __init__(self, chunk_type, start_line_n, end_line_n, iterable, config):
        print("##chunk_type:", chunk_type)
        assert chunk_type is E_Chunk.POTPOURRI
        print("##chunk_type.passed:", chunk_type)
        iterable = tuple(iterable)
        print("##iterable:", iterable)

        def adapt(iterable, start_line_n, end_line_n):
            yield Line.from_potpourri(start_line_n, begin_f=True)
            yield from iterable
            yield Line.from_potpourri(end_line_n, begin_f=False)
        InputChunk.__init__(self, E_Chunk.POTPOURRI, start_line_n, end_line_n, iterable, config)
        ## InputChunk.__init__(self, E_Chunk.POTPOURRI, start_line_n, end_line_n, 
        ##                     adapt(iterable, start_line_n, end_line_n), config)


