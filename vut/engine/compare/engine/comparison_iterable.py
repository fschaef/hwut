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

from itertools import zip_longest


def generate(config, subject_line_provider, nominal_line_provider, fill_f=False):
    """YIELDS: pairs of (subject input chunk, nominal input chunk).

    Input chunk: 'LineSequence' or 'Potpourri'.

    If one line provider exhausts, the 'fillvalue' is setup as its input chunk.
    When both line providers exhaust, the generator terminates.
    """
    assert hasattr(subject_line_provider, "readline")
    assert hasattr(nominal_line_provider, "readline")

    chunk_pipe = ChunkPipe(config)

    subject_iterable = chunk_pipe.generate(subject_line_provider)
    nominal_iterable = chunk_pipe.generate(nominal_line_provider)

    # chunk: 'LineSequence' or 'Potpourri' both derived from 'InputChunk'.
    if not fill_f:
        yield from zip_longest(subject_iterable, nominal_iterable)
    else:
        for subject, nominal in zip_longest(subject_iterable, nominal_iterable):
            if   subject is None: subject = nominal.empty_clone()
            elif nominal is None: nominal = subject.empty_clone()
            yield subject, nominal

