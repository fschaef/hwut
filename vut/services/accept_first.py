"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FIRST ACCEPTANCE -- no nominal stands.

DESCRIPTION
       ACCEPT IS PARTIAL BY DEFAULT (E-60). Where nothing stands, what
       gets recorded is not the candidate but a nominal that says
       'nobody has judged any of this': the candidate's chunk structure
       mirrored as '##! unaccepted' regions of filler lines, with the
       closing token outside every region. The next run then reads
       '[ ?! ]' (O-25) -- not a failure and not a regression, but a
       thing somebody still owes a decision on.

       '--force' is the old blessing: the candidate whole, as it stands.

       THE SESSION OPENS ON THE VIRGIN NOMINAL. 'hwut.accept.interactive'
       on a first acceptance hands the keyed session that nominal, and
       every take lifts a decision out of a region. This module is what
       supplies it; the session itself is 'lib/viewers/keyed'.

       THE DYNAMICS DIFFER FROM AN ADAPTATION: a first acceptance starts
       from a FULL MIRROR and fragments it; nothing in the nominal is
       decided until taken.
______________________________________________________________________________
"""
from vut.services.lib.accept.virgin import virgin_nominal


def opening_nominal(configuration, subject_text, force_f):
    """
    RETURN: str, the nominal a first acceptance records -- the
            candidate WHOLE where '--force' was said, otherwise its
            mirror of '##! unaccepted' regions with nothing decided.

            None, where the candidate does not end in the closing
            token: such a stream never COMPLETED (R-70), and nothing
            is recorded for it.
    """
    if force_f:
        return subject_text if subject_text.rstrip("\n").endswith("<hwut-end>") \
               else None
    return virgin_nominal(configuration, subject_text)


def question(key, force_f):
    """
    RETURN: str, what to ask before recording -- worded for what will
            actually be written, since a reader confirming 'record as
            undecided' is agreeing to something quite different from
            'take this whole'.
    """
    if force_f:
        return "record the candidate of '%s' as its nominal, whole?" % key.name
    return ("record '%s' as UNACCEPTED -- the shape, nothing decided; "
            "decide in 'hwut.accept.interactive'?" % key.name)
