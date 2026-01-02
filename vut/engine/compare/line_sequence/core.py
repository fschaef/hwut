"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: 'LineSequence' input chunk.

LineSequence: set of text lines where the sequence matters.

The two main functions of 'LineSequence' are (derived from 'InputChunk')

   .compare()           --> determines whether the chunk is equivalent to
                            another.
   .line_pairs() --> determines which lines should be best associated
                            for display.
________________________________________________________________________________
"""
from   vut.engine.compare.input.input_chunk             import InputChunk, \
                                                               E_Chunk

class LineSequence(InputChunk):
    """Set of lines where the sequence matters.
    """
    def __init__(self, chunk_type, start_line_n, end_line_n, iterable, config):
        InputChunk.__init__(self, E_Chunk.LINE_SEQUENCE, start_line_n, end_line_n, iterable, config)

    def type(self):
        return E_Chunk.LINE_SEQUENCE



