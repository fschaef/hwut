SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
==============================================================================
TEST RUN INFO -- A BOOK ENTRY, ALIVE
==============================================================================

A row of 'GOOD/book.csv' is a RECORD. This component is the thing that
record is of, held for as long as a session needs it: what the register
issued, what the last run found, and which MEMBER STATE the case stands
in.

It lives in the bookkeeper because the bookkeeper owns both witnesses a
case has -- 'GOOD/', which is testimony, and 'book.csv', which is the
record of that testimony.

------------------------------------------------------------------------------
THE MEMBER STATE IS THE STATE, AND NOTHING ELSE
------------------------------------------------------------------------------

    UNKNOWN     nothing accepted -- no nominal stands.

    ASPIRANT    accepted, INCOMPLETELY: the nominal stands and carries
                at least one '##! unaccepted' region. It stays an
                aspirant for exactly as long as that mark stands.
                Playable, never runnable.

    MEMBER      accepted whole -- no mark, and the terminal token in
                place. The only state a run may judge.

An aspirant arises ONE way: an interactive acceptance closed with a
region nobody judged. A run that produced no output, or none ending in
'<hwut-end>', cannot be accepted at all -- so it is not even an
aspirant, and it leaves UNKNOWN where it was.

------------------------------------------------------------------------------
THE VERDICT AND THE STATE ARE FACTUALLY SEPARATE
------------------------------------------------------------------------------

'book.csv' compresses them into one 'verdict' column holding
'true | false | aspirant'. THE COMPRESSION IS THE FILE'S BUSINESS; the
two are separate attributes and this component keeps them so:

    member_state    whether the case may be run at all
    last_verdict    True, False, or None -- what happened when it was.
                    None where no run has judged it.

A member that failed is still a member (E-15). 'aspirant' is not a
verdict; it is the reason there can be none.

PASS, precisely: the case does not negate the total verdict and is not
an error. An aspirant is neither -- it is not considered, and there is
no way to measure it.

------------------------------------------------------------------------------
NOTHING CHANGES BY ASSIGNMENT
------------------------------------------------------------------------------

'CMemberState' and 'CTestRunInfo' both refuse '__setattr__' and
'__delattr__' outright, and the refusal names the events. The single
writers are '_transit' and '_with', reachable only from an event
method. A caller cannot form its own opinion of a case's standing and
write it down; it says what HAPPENED and the object decides what that
means.

    on_accept_left_unaccepted()       an acceptance closed with a
                                      region unjudged        -> ASPIRANT
    on_accept_clean_good()            an acceptance closed whole
                                                             -> MEMBER
    on_detected_unaccepted_in_good()  the mark was FOUND in a standing
                                      nominal -- a hand-edited GOOD, one
                                      an older hwut wrote, one sanitize
                                      met                    -> ASPIRANT
    on_nominal_removed()                                     -> UNKNOWN
    on_no_output()                    moves nothing
    on_no_terminal()                  moves nothing
    on_run_verdict(ok_f, report)      writes the verdict; the STATE does
                                      not move. RAISES where the case is
                                      not runnable
    on_stain(repeat_n, when)          the flapping record (B-2)

THE BASE STATE REFUSES. Each state class answers only the events that
move it and inherits 'this does not move me' for the rest, so a
transition nobody wrote cannot happen, and a state added later cannot
silently leave an event unhandled.

------------------------------------------------------------------------------
THE TWO WITNESSES MAY DISAGREE
------------------------------------------------------------------------------

'of_evidence' builds the state from THE FILES, never from the book: a
file is testimony, a row is a record of it, and where they differ the
file wins. 'consistency_fault_tuple' NAMES every disagreement and mends
none -- repair belongs to a person, through 'hwut.accept' or
'hwut.remove' (services E-41). This component is the eye; sanitize is
the voice; the faces are the hand.

------------------------------------------------------------------------------
FILES
------------------------------------------------------------------------------

    __init__.py       the door, and why the component exists
    member_state.py   E_MemberState, the state classes, CMemberState,
                      of_evidence, consistency_fault_tuple
    info.py           CTestRunInfo, of_row
    TEST/             the states, the seal, the evidence, the
                      consistency table
