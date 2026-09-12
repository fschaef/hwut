"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ADAPTATION -- a nominal stands, and the candidate differs.

DESCRIPTION
       The working nominal is READ, not built: whatever the GOOD file
       carries -- plain lines, tolerances, and possibly regions left
       undecided by an earlier partial acceptance -- is what the session
       opens on. 'hwut.accept' itself never writes here without
       '--force'; a change to something already judged is
       'hwut.accept.interactive's business, and this module is what it
       reads through.

       THE DYNAMICS DIFFER FROM A FIRST ACCEPTANCE: an adaptation starts
       from whatever regions already stand, or none, and a take outside
       every region REPLACES rather than splits. The same reducer serves
       both; what differs is the ground it works on.
______________________________________________________________________________
"""
from vut.services._accept_common import read_text


def standing_nominal(good_path):
    """
    RETURN: str, the nominal that stands for this key, as the GOOD file
            carries it -- regions and all.

            None, where the file cannot be read: nothing to adapt.
    """
    return read_text(good_path)
