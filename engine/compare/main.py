"""SPDX-Linces: MIT; Project HWUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Comparing two input streams: 'subject' and 'nominal'

The stream 'subject' is supposed to be the output of a test application.  The
stream 'nominal' is the stored-away reference output of a good test run. The text
provided by a stream is interpreted in two ways:

-- line sequences, where the lines in the subject must occur in the same
                   sequence as in the nominal.
-- potpourri,      where the same lines must occur, but not necessarily
                   in the same sequence.

A stream can consist of multiple blocks of line sequences and potpourris.
Potpourris distinguish by '||||' markers aroud the concerned lines.

API:

  compare(subject_stream, nominal_stream) -> bool

     returns 'True' if both streams are equivalent, 'False' else.

  line_associations(subject_stream, nominal_stream)

     yields comparison information about the lines and potpourris that appear
     in the input streams.

The only requirement on the objects 'subject_stream' and 'nominal_stream'
is that they must provide the function:

  .readline() -> non-empty 'str', in case there is a line that can be read.
                 "",              if end of stream has been reached.
"""
from   ut.engine.compare.engine.analogy_db             import AnalogyDb
from   ut.engine.compare.engine.comparison_iterable    import generate
from   ut.engine.compare.engine.line_association_chunk import LineAssociationChunk
from   ut.engine.compare.engine.input_chunk            import E_Verdict, \
                                                                InputChunkEmpty


def compare(config, subject_line_provider, nominal_line_provider) -> E_Verdict:
    """RETURNS: True, if subject and nominal stream are equivalent.
                False, else.

    The function operates on coroutines reading lines from line providers.
    As soon as 'False' can be stated it aborts immediately-not consuming
    any further input. Caller functions then, might then terminate the data
    producing process.

    ONLY REQUIREMENT: line provider member function '.readline()'.

    The '.get()' function either returns a line of text or 'None' in case
    that the stream terminated.
    """
    analogy_db = AnalogyDb()

    for subject, nominal in generate(config,
                                     subject_line_provider, nominal_line_provider):
        verdict,   \
        analogy_db = subject.compare(nominal, analogy_db)

        if verdict != E_Verdict.EQUIVALENT:
            return verdict
    else:
        return E_Verdict.EQUIVALENT


def line_associations(config, subject_line_provider, nominal_line_provider):
    """YIELDS: LineAssociationChunk

    where:

    LineAssociationChunk.type() in (E_Chunk.LINE_SEQUENCE, E_Chunk.POTPOURRI)

    This function iterates over subject and nominal lines and compares them.
    When lines are too deviant from each other, 'plugs' in one sequence are
    inserted until it fits again the other sequences. Line associations are
    reported (yielded) in blocks of their type, i.e. assocations of
    'LineSequence'-s and 'Potpourri'-s are yielded in separate objects
    of type 'LineAssociationChunk'
    """
    analogy_db = AnalogyDb()

    for subject, nominal in generate(config,
                                     subject_line_provider, nominal_line_provider,
                                     fillvalue=InputChunkEmpty()):

        line_associations = subject.line_associations(nominal, analogy_db)

        if not line_associations: continue

        analogy_db = line_associations[-1].analogy_db
        yield LineAssociationChunk(subject.type(), line_associations)


