"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE IDENTIFIERS OF A COVERAGE OUTPUT (coverage D-42): test run
         ids and test run group ids, numbers in base 64 written at one
         width.

    0-9  A-Z  _  a-z  ~        the digits, in ASCII order

SORTING THE TEXT SORTS THE NUMBERS where every identifier of an output
stands at the same width, and none of the formats' own signs (',', ';',
':', '@', '*', '+') is a digit.
______________________________________________________________________________
"""

#  THE SPELLING IS THE ID MODULE'S ('engine/bookkeeper/id_scope.py'),
#  shared with every other id of the tree; what stays here is the
#  layout of ONE coverage output: where its group ids begin.
from ...bookkeeper.api import BASE, DIGITS, id_number, id_text  # noqa: F401


def group_id_start(run_n):
    """
    RETURN: int, the first group id of an output holding 'run_n' test
            runs: the next ROUND value above the last test run id --
            'g00' after 'f2g', '10' after any single digit.
    """
    last  = max(run_n - 1, 0)
    scale = BASE
    while scale * BASE <= last: scale *= BASE
    return (last // scale + 1) * scale
