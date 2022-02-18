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

from vut.engine.compare.tolerance.chunk_pipe import ChunkPipe
from vut.engine.compare.engine.input_chunk   import InputChunkEmpty, E_Chunk

from itertools import zip_longest


def generate(config, subject_line_provider, nominal_line_provider, align_f):
    """YIELDS: [0] subject input chunk
               [1] nominal input chunk

    Input chunk: 'LineSequence', 'Potpourri', or None.

    If one line provider exhausts, the 'fillvalue' is setup as its input chunk.
    When both line providers exhaust, the generator terminates.
    """
    assert hasattr(subject_line_provider, "readline")
    assert hasattr(nominal_line_provider, "readline")

    # Two types of input chunks: 'LineSequence' <-- 'InputChunk'
    #                            'Potpourri'    <-- 'InputChunk'
    chunk_pipe       = ChunkPipe(config)
    subject_iterable = chunk_pipe.generate(subject_line_provider)
    nominal_iterable = chunk_pipe.generate(nominal_line_provider)

    if not align_f: 
        for s, n in zip_longest(subject_iterable, nominal_iterable):
            if s is None: s = n.empty_clone()
            if n is None: n = s.empty_clone()
            yield s, n
    else:           
        yield from _zip_aligned(subject_iterable, nominal_iterable)
    

def _zip_aligned(subject_iterable, nominal_iterable):
    """YIELDS: [0] subject input chunk
               [1] nominal input chunk

    where the same-type input chunks are 'aligned'. That is, the chunks are 
    either of the same type or one of them is 'None'. 
    """
    empty                             = InputChunkEmpty()
    subject_delayed = nominal_delayed = empty

    def _flush_delayed():
        if nominal_delayed.type() != E_Chunk.EMPTY: yield None, nominal_delayed
        if subject_delayed.type() != E_Chunk.EMPTY: yield subject_delayed, None

    for subject, nominal in zip_longest(subject_iterable, nominal_iterable):
        assert not (subject is None and nominal is None)

        if   nominal and nominal.type() == subject_delayed.type():
            if nominal_delayed.type() != E_Chunk.EMPTY: yield None, nominal_delayed
            yield subject_delayed, nominal
            if subject is None: subject_delayed = empty
            else:               subject_delayed = subject
            nominal_delayed = empty

        elif subject and subject.type() == nominal_delayed.type():
            if subject_delayed.type() != E_Chunk.EMPTY: yield subject_delayed, None
            yield subject, nominal_delayed
            subject_delayed = empty
            if nominal is None: nominal_delayed = empty
            else:               nominal_delayed = nominal

        else:
            yield from _flush_delayed()
            subject_delayed = nominal_delayed = empty
            if   subject is None:                  yield None,    nominal
            elif nominal is None:                  yield subject, None
            elif subject.type() == nominal.type(): yield subject, nominal
            else:                                  subject_delayed, nominal_delayed = subject, nominal

        assert not (subject_delayed.type() == nominal_delayed.type()) \
               or  (subject_delayed.type() == E_Chunk.EMPTY)

    yield from _flush_delayed()

