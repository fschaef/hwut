"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE MEMBER STATE: THE STATES, THE EVENTS, THE CONSISTENCY CHECKS.

One field of 'CTestRunInfo' ('info.py'), and the one that had no
home before: WHICH STANDING a case has, and the only thing that may
move it. The package docstring says what the states mean and why the
state pattern is used; this file holds them.
______________________________________________________________________________
"""
from enum        import Enum


class MemberStateFault(Exception):
    """A member state was asked to do what its state does not allow,
    or was written to by assignment rather than by an event."""


class E_MemberState(Enum):
    """
    THE STATE'S NAME, as a report prints it and a book column holds it.

    UNKNOWN    nothing accepted -- no book row, no nominal
    ASPIRANT   accepted incompletely -- the nominal carries at least
               one '##! unaccepted' region
    MEMBER     accepted whole -- no mark, terminal token present
    """
    UNKNOWN  = "unknown"
    ASPIRANT = "aspirant"
    MEMBER   = "member"

    def __str__(self):
        """RETURN: str, the state's token, as a book column holds it."""
        return self.value


class _State:
    """
    THE BASE REFUSES EVERY EVENT. A state answers only the events that
    MOVE it and inherits the rest, so a transition nobody wrote cannot
    happen, and a state added later cannot silently leave an event
    unhandled.

    Every method answers the NEXT state. Answering 'None' means 'this
    event does not move me', which is a legitimate outcome and not a
    fault: a run that produced no output leaves an aspirant exactly
    where it was.
    """
    NAME       = None
    RUNNABLE   = False
    PLAYABLE   = False
    ACCEPTABLE = True

    def on_accept_left_unaccepted(self):
        """RETURN: E_MemberState, ASPIRANT -- an acceptance closed with
                   at least one region nobody judged.
                   None, where this state does not move.

        The event every state answers the same way: however a case
        stood before, a GOOD carrying the mark is an aspirant."""
        return E_MemberState.ASPIRANT

    def on_accept_clean_good(self):
        """RETURN: E_MemberState, MEMBER -- an acceptance closed with no
                   region left unjudged and the terminal token in place.
                   None, where this state does not move."""
        return E_MemberState.MEMBER

    def on_detected_unaccepted_in_good(self):
        """RETURN: E_MemberState, ASPIRANT where a nominal is FOUND
                   carrying the mark -- a GOOD edited by hand, one an
                   older hwut wrote, or one sanitize met.
                   None, where this state does not move.

        The repair door: no re-acceptance is needed for the state to
        tell the truth again."""
        return E_MemberState.ASPIRANT

    def on_nominal_removed(self):
        """RETURN: E_MemberState, UNKNOWN -- the nominal is gone, so
                   nothing was accepted.
                   None, where this state does not move."""
        return E_MemberState.UNKNOWN

    def on_no_output(self):
        """RETURN: None. A run that produced nothing moves no state.
                   It cannot be accepted, so it cannot become an
                   aspirant either."""
        return None

    def on_no_terminal(self):
        """RETURN: None. A run whose output does not end in the
                   terminal token moves no state: it is never even
                   considered for accept or merge (R-70)."""
        return None

    def on_run_verdict(self, ok_f):
        """RETURN: None. A verdict is a fact about ONE run, not about
                   standing: a member that fails is still a member.
                   Raises MemberStateFault where the state is not
                   runnable -- such a case must never have reached a
                   comparison."""
        if not self.RUNNABLE:
            raise MemberStateFault(
                "a case in state '%s' was judged by a run -- every "
                "gate must refuse it before it is selected" % self.NAME)
        return None


class _Unknown(_State):
    """Nothing accepted. Not runnable, not playable -- there is no
    nominal to play against."""
    NAME     = E_MemberState.UNKNOWN
    PLAYABLE = False


class _Aspirant(_State):
    """Accepted incompletely. PLAYABLE -- the author returns to finish
    what the session left -- and never RUNNABLE."""
    NAME     = E_MemberState.ASPIRANT
    PLAYABLE = True


class _Member(_State):
    """Accepted whole. The only state a run may judge."""
    NAME     = E_MemberState.MEMBER
    RUNNABLE = True
    PLAYABLE = True


_STATE_DB = {E_MemberState.UNKNOWN:  _Unknown(),
             E_MemberState.ASPIRANT: _Aspirant(),
             E_MemberState.MEMBER:   _Member()}

EVENT_TUPLE = ("on_accept_left_unaccepted", "on_accept_clean_good",
               "on_detected_unaccepted_in_good", "on_nominal_removed",
               "on_no_output", "on_no_terminal", "on_run_verdict")


class CMemberState:
    """
    ONE CASE'S MEMBERSHIP, and the only door into it.

    Assignment is refused ('__setattr__' raises MemberStateFault), so a
    caller cannot form its own opinion of the state and write it down.
    The event methods below are the whole interface; each answers this
    object, so they chain.
    """
    __slots__ = ("_state", "_test", "_choice", "_frozen")

    def __init__(self, test, choice=None, state=E_MemberState.UNKNOWN):
        """
        RETURN: CMemberState, standing in 'state' -- UNKNOWN unless a
                caller states otherwise (see 'of_evidence', which reads
                the files instead of being told).
        """
        object.__setattr__(self, "_state",  state)
        object.__setattr__(self, "_test",   test)
        object.__setattr__(self, "_choice", choice)
        object.__setattr__(self, "_frozen", True)

    def __setattr__(self, name, value):
        """RAISES: MemberStateFault, always. The state moves through an
                   event or not at all."""
        raise MemberStateFault(
            "member state is not assignable ('%s'): call the event that "
            "means what you intend -- %s"
            % (name, ", ".join(EVENT_TUPLE)))

    def __delattr__(self, name):
        """RAISES: MemberStateFault, always."""
        raise MemberStateFault("member state is not assignable ('%s')" % name)

    #  ---- what it is ------------------------------------------------
    @property
    def state(self):
        """RETURN: E_MemberState, the state this case stands in."""
        return self._state

    @property
    def name(self):
        """RETURN: str, the case as a report names it -- 'test' or
                   'test choice'."""
        if self._choice is None: return str(self._test)
        return "%s %s" % (self._test, self._choice)

    def is_runnable(self):
        """RETURN: bool, whether a gate may admit this case to a run.
                   True for MEMBER alone: an aspirant carries lines
                   nobody has accepted, and an unknown has no nominal
                   to be judged against."""
        return _STATE_DB[self._state].RUNNABLE

    def is_playable(self):
        """RETURN: bool, whether 'hwut.run.play' may open this case --
                   ASPIRANT and MEMBER; an UNKNOWN has nothing to
                   play against."""
        return _STATE_DB[self._state].PLAYABLE

    #  ---- what moves it ---------------------------------------------
    def _transit(self, next_state):
        """RETURN: CMemberState, self -- in 'next_state' where the event
                   named one, unmoved where it answered None.

        The ONLY writer of '_state' in this module."""
        if next_state is not None:
            object.__setattr__(self, "_state", next_state)
        return self

    def on_accept_left_unaccepted(self):
        """RETURN: CMemberState, self, now ASPIRANT -- an interactive
                   acceptance closed with at least one region nobody
                   judged."""
        return self._transit(
            _STATE_DB[self._state].on_accept_left_unaccepted())

    def on_accept_clean_good(self):
        """RETURN: CMemberState, self, now MEMBER -- an acceptance
                   closed whole, by '--as-is' or by a session that
                   took every region."""
        return self._transit(
            _STATE_DB[self._state].on_accept_clean_good())

    def on_detected_unaccepted_in_good(self):
        """RETURN: CMemberState, self, now ASPIRANT -- the mark was
                   FOUND in a standing nominal, by sanitize or by any
                   reader. No re-acceptance is needed for the state to
                   tell the truth again."""
        return self._transit(
            _STATE_DB[self._state].on_detected_unaccepted_in_good())

    def on_nominal_removed(self):
        """RETURN: CMemberState, self, now UNKNOWN."""
        return self._transit(_STATE_DB[self._state].on_nominal_removed())

    def on_no_output(self):
        """RETURN: CMemberState, self, UNMOVED. A run that produced
                   nothing cannot be accepted, so it cannot become an
                   aspirant either -- an aspirant whose application
                   stops compiling stays an aspirant."""
        return self._transit(_STATE_DB[self._state].on_no_output())

    def on_no_terminal(self):
        """RETURN: CMemberState, self, UNMOVED. Output that does not end
                   in '<hwut-end>' is never considered for accept or
                   merge (R-70), so it moves nothing."""
        return self._transit(_STATE_DB[self._state].on_no_terminal())

    def on_run_verdict(self, ok_f):
        """RETURN: CMemberState, self, UNMOVED -- a verdict is a fact
                   about one run, and a member that fails is still a
                   member.

        RAISES: MemberStateFault, where the state is not runnable. A
                case that reached a comparison without being a member
                got past a gate that should have refused it, and that
                is a defect in the gate, not a verdict."""
        return self._transit(_STATE_DB[self._state].on_run_verdict(ok_f))

    def __repr__(self):
        """RETURN: str, the case and its state."""
        return "CMemberState(%s: %s)" % (self.name, self._state)


def of_evidence(test, choice, nominal_stands_f, carries_unaccepted_f):
    """
    RETURN: CMemberState, the state THE FILES testify to, never what a
            book row claims: no nominal is UNKNOWN; a nominal carrying
            '##! unaccepted' is ASPIRANT; anything else is MEMBER.

    THE MARK ALONE MAKES AN ASPIRANT. The terminal token is asked of a
    SUBJECT -- what a run produced -- and decides whether that output
    may be accepted or merged at all (R-70). It is NOT asked of the
    nominal here: a nominal may lawfully be empty, or end however its
    author accepted it, and MEASURED, treating a missing token in the
    nominal as an aspirant refused four cases of 'test-plan.py faults'
    whose fixture writes empty nominals on purpose.

    A file is testimony and a book row is a record of it, so where the
    two disagree the file wins and 'consistency_fault_tuple' names the
    disagreement.
    """
    if not nominal_stands_f:
        return CMemberState(test, choice, E_MemberState.UNKNOWN)
    if carries_unaccepted_f:
        return CMemberState(test, choice, E_MemberState.ASPIRANT)
    return CMemberState(test, choice, E_MemberState.MEMBER)


def consistency_fault_tuple(member_state, booked_state):
    """
    RETURN: tuple[str], one line per disagreement between what the FILES
            say (the member state, built by 'of_evidence') and what the
            BOOK claims ('booked_state', an E_MemberState or None where
            the book holds no row). Empty where the two agree.

    NAMED, NEVER MENDED HERE. A disagreement is repaired by a person
    through 'hwut.accept' or 'hwut.remove' (services E-41); this
    function is the eye, not the hand.
    """
    found = member_state.state
    if booked_state is None:
        if found is E_MemberState.UNKNOWN: return ()
        return ("%s: a nominal stands, and the book lacks it"
                % member_state.name,)
    if booked_state is found: return ()
    if found is E_MemberState.UNKNOWN:
        return ("%s: the book says '%s', and no nominal stands"
                % (member_state.name, booked_state),)
    if found is E_MemberState.ASPIRANT:
        return ("%s: the book says '%s', and the nominal carries an "
                "unaccepted region" % (member_state.name, booked_state),)
    return ("%s: the book says '%s', and the nominal is accepted whole"
            % (member_state.name, booked_state),)
