"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: A BOOK ENTRY WHILE IT IS ALIVE -- 'CTestRunInfo' -- and, the
         field of it that had no home before, THE MEMBER STATE.

A row of 'book.csv' is a record. This package is the thing that record
is of, held for as long as a session needs it. It lives in the
bookkeeper because the bookkeeper owns BOTH WITNESSES a case has:
'GOOD/', which is testimony, and 'book.csv', which is the record of it.

    WHY IT EXISTS

Before it, one question -- 'what standing does this case have?' -- was
answered in three places and joined in none:

    whether a nominal stands          'bookkeeper.nominal_stands_f',
                                      asked by eight callers
    whether it carries the mark       'operations/consume.carries_-
                                      unaccepted_f', asked by ONE, and
                                      that one inside the run's
                                      comparison
    what the book's verdict says      the book row

So ASPIRANT -- a state the enum had always carried -- was UNREACHABLE
by the path that should create it. MEASURED: a case whose GOOD held
nothing but '##! unaccepted' was booked PASS, selected, run, booked
FAIL, and then answered 'hwut.wishlist --fail' while answering
'--unaccepted' not at all.

    THE THREE STATES

        UNKNOWN    nothing accepted -- no nominal. A run that produced
                   no output, or none ending in the terminal token,
                   cannot leave this state: it was never accepted, so
                   it is not even an aspirant.

        ASPIRANT   accepted, INCOMPLETELY: the nominal stands and
                   carries at least one '##! unaccepted' region. It
                   stays aspirant for exactly as long as that mark
                   stands. Playable, never runnable -- no gate may
                   admit it.

        MEMBER     accepted whole. The only state a run may judge.

    STATE PATTERN, AND WHY

Each state is a class holding the event methods; the context delegates
to the one it holds. A state that does not answer an event INHERITS
THE REFUSAL, so a transition nobody wrote cannot happen by accident,
and a state added later cannot silently leave an event unhandled.

    NOTHING CHANGES BY ASSIGNMENT

Both classes refuse '__setattr__' outright and name the events in the
refusal. The single writers are '_transit' and '_with', reachable only
from an event method. That is the point of the package: what it
replaces was every caller free to form its own opinion and write it
down.
______________________________________________________________________________
"""
from .member_state import (CMemberState,            # noqa: F401
                           E_MemberState,
                           MemberStateFault,
                           of_evidence,
                           consistency_fault_tuple)
from .info         import CTestRunInfo, of_row      # noqa: F401
from .of_disk      import of_case                   # noqa: F401

__all__ = ["CTestRunInfo", "of_row", "of_case",
           "CMemberState", "E_MemberState", "MemberStateFault",
           "of_evidence", "consistency_fault_tuple"]
