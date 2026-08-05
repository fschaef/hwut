"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE READING -- one textual stream, interpreted under a description.

DESCRIPTION
       A comparison never sees text. It sees a READING: the text as
       classified lines, as LineElements under the configured patterns,
       as chunks with their regions -- 'D(b)' of the equivalence
       'Equivalence(D(b_pole), D(b), T)'. This module is the ONE door to
       that interpretation; the machinery behind it fills the rest of
       this directory.

       ONE CONSTRUCTOR, NO MODES. Subject and nominal are the same kind
       of thing -- a comparison merely aligns two readers. Both are made
       HERE, by the same call, and nothing downstream can tell them
       apart by type. What distinguishes them is which ARGUMENT POSITION
       they take in a comparison, never what they are.

       A READING IS CONSUMABLE ONCE. It is a pull stream -- chunks on
       demand -- which is what lets a judge abort on the first
       non-equivalent pair while the producing process still runs. A
       rewind would demand materialisation and silently kill that
       economy; a consumer that needs the text twice buffers the TEXT
       and constructs two readings (the cross-check mode does exactly
       that).

       THE TOLERANCE IS NOT IN HERE. 'T' belongs to the comparison where
       two readings meet; the same reading may be judged strictly today
       and loosely tomorrow. And a reading is never STORED: it is a
       function of (text, description), and the description evolves --
       the artifact is the text, the reading is its projection.

       TWO FACES, ONE INTERPRETATION. The Judge reads for a fast
       verdict, the Lawyer reads keeping what a display needs; both
       classify, lex and frame identically ('chunk_pipe.py').
______________________________________________________________________________
"""
from   vut.engine.compare.reading.chunk_pipe import EquivalenceCheckChunkPipe, \
                                                    AssociationChunkPipe
from   vut.auxiliary.async_helper            import AsyncIterator_ensured


def judge_reading(configuration, line_provider):
    """
    RETURN: EquivalenceCheckChunkPipe, the reading of ONE textual stream
            for the Judge's face: chunks on demand, fit for a fast-fail
            verdict.

    The only requirement on 'line_provider' is '.readline()'.
    """
    return EquivalenceCheckChunkPipe(configuration,
                                     AsyncIterator_ensured(line_provider))


def lawyer_reading(configuration, line_provider):
    """
    RETURN: AssociationChunkPipe, the reading of ONE textual stream for
            the Lawyer's face: the same interpretation, keeping what a
            display needs.

    The only requirement on 'line_provider' is '.readline()'.
    """
    return AssociationChunkPipe(configuration,
                                AsyncIterator_ensured(line_provider))
