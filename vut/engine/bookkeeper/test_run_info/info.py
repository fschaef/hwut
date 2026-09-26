"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: A BOOK ENTRY, ALIVE. 'CTestRunInfo' is one row of 'book.csv'
         while a session holds it: what the register issued, what the
         last run found, and -- the part that had no home before --
         WHICH MEMBER STATE THE CASE STANDS IN.

A row on disk is a record; this is the thing that record is of. It
belongs to the bookkeeper because the bookkeeper owns both witnesses:
'GOOD/' and 'book.csv'.

    WHAT IT HOLDS

        test, choice            which case, as the book names it
        test_id, choice_id      what the register issued (B-13)
        member_state            unknown | aspirant | member
                                ('member_state.py' -- the state
                                machine, and the only thing that
                                moves it)
        last_verdict            what the LAST RUN found: True, False,
                                or None where none has run. NOT the
                                member state: a member that failed is
                                still a member (E-15).
        report                  the run's word for why
        last_accept             when acceptance was written
        coverage, stderr        what the run recorded beside stdout
        stain                   the flapping record (B-2)

    NOTHING CHANGES BY ASSIGNMENT

Every field is sealed, as the member state is. A run's outcome enters
through 'on_run_verdict'; an acceptance through the accept events,
which the info forwards to its member state and which also write
'last_accept'. There is no setter, and '__setattr__' says so with the
event names.

    THE VERDICT COLUMN AND THE STATE ARE TWO THINGS

The book's 'verdict' column has carried three values -- true, false,
aspirant -- which conflates a RUN'S OUTCOME with a CASE'S STANDING.
'aspirant' is not a verdict; it is the reason there can be none.
Here they are separate: 'member_state' says whether the case may be
run at all, 'last_verdict' what happened when it was. What the column
should hold is a question for the cut that wires this in.
______________________________________________________________________________
"""
from .member_state import (CMemberState, E_MemberState,   # noqa: F401
                           MemberStateFault, of_evidence,
                           consistency_fault_tuple)


EVENT_TUPLE = ("on_accept_left_unaccepted", "on_accept_clean_good",
               "on_detected_unaccepted_in_good", "on_nominal_removed",
               "on_no_output", "on_no_terminal", "on_run_verdict",
               "on_stain")


class CTestRunInfo:
    """
    ONE BOOK ENTRY WHILE IT IS ALIVE.

    Built by 'of_row' from what the book holds plus what the files
    testify; moved only by the events below, each of which answers
    this object so they chain.
    """
    __slots__ = ("_test", "_choice", "_test_id", "_choice_id",
                 "_member_state", "_last_verdict", "_report",
                 "_last_accept", "_coverage", "_stderr", "_stain")

    def __init__(self, test, choice=None, member_state=None,
                 test_id=None, choice_id=None, last_verdict=None,
                 report=None, last_accept=None, coverage=None,
                 stderr=None, stain=None):
        """
        RETURN: CTestRunInfo, the entry as given. 'member_state' None
                means a case nothing is known about yet -- UNKNOWN.
        """
        if member_state is None:
            member_state = CMemberState(test, choice)
        for name, value in (("_test", test), ("_choice", choice),
                            ("_test_id", test_id),
                            ("_choice_id", choice_id),
                            ("_member_state", member_state),
                            ("_last_verdict", last_verdict),
                            ("_report", report),
                            ("_last_accept", last_accept),
                            ("_coverage", coverage),
                            ("_stderr", stderr), ("_stain", stain)):
            object.__setattr__(self, name, value)

    def __setattr__(self, name, value):
        """RAISES: TestRunInfoFault, always -- nothing here is
                   assignable. Call the event that means what you
                   intend."""
        raise MemberStateFault(
            "a test run info is not assignable ('%s'): call the event "
            "that means what you intend -- %s"
            % (name, ", ".join(EVENT_TUPLE)))

    def __delattr__(self, name):
        """RAISES: TestRunInfoFault, always."""
        raise MemberStateFault(
            "a test run info is not assignable ('%s')" % name)

    #  ---- what it is ------------------------------------------------
    @property
    def name(self):
        """RETURN: str, the case as a report names it -- 'test' or
                   'test choice'."""
        return self._member_state.name

    @property
    def member_state(self):
        """RETURN: CMemberState, the case's standing -- ask it
                   'is_runnable()', 'is_playable()', '.state'."""
        return self._member_state

    @property
    def last_verdict(self):
        """RETURN: True where the last run was equivalent to its
                   nominal, False where it was not, None where no run
                   has judged this case. NEVER the member state."""
        return self._last_verdict

    @property
    def report(self):
        """RETURN: str or None, the last run's word for WHY -- 'ok',
                   'unaccepted', 'terminated-without-end' and the
                   rest."""
        return self._report

    @property
    def last_accept(self):
        """RETURN: str or None, when acceptance was written, as the
                   book holds it. None where nothing was accepted --
                   which, with a standing nominal, is the
                   disagreement 'consistency_fault_tuple' names."""
        return self._last_accept

    @property
    def test_id(self):
        """RETURN: str or None, the id the register issued (B-13)."""
        return self._test_id

    @property
    def choice_id(self):
        """RETURN: str or None, the choice's id within the test."""
        return self._choice_id

    @property
    def stain(self):
        """RETURN: dict or None, the flapping record (B-2): how often
                   the case disagreed with itself, and when."""
        return self._stain

    def is_runnable(self):
        """RETURN: bool, whether a gate may admit this case to a run --
                   the member state's answer, forwarded so that a gate
                   need not reach past the info."""
        return self._member_state.is_runnable()

    def is_playable(self):
        """RETURN: bool, whether 'hwut.run.play' may open this case."""
        return self._member_state.is_playable()

    #  ---- what moves it ---------------------------------------------
    def _with(self, **field_db):
        """RETURN: CTestRunInfo, self, with the named fields written.
                   The ONLY writer in this class."""
        for name, value in field_db.items():
            object.__setattr__(self, "_" + name, value)
        return self

    def on_accept_left_unaccepted(self, when=None):
        """RETURN: CTestRunInfo, self -- the case is an ASPIRANT, and
                   'last_accept' says when the incomplete acceptance
                   was written. An acceptance happened; it was not
                   finished."""
        self._member_state.on_accept_left_unaccepted()
        return self._with(last_accept=when or self._last_accept)

    def on_accept_clean_good(self, when=None):
        """RETURN: CTestRunInfo, self -- the case is a MEMBER, and the
                   last run's verdict is dropped: what was judged
                   against is no longer what stands."""
        self._member_state.on_accept_clean_good()
        return self._with(last_accept=when or self._last_accept,
                          last_verdict=None, report=None)

    def on_detected_unaccepted_in_good(self):
        """RETURN: CTestRunInfo, self -- the mark was FOUND in a
                   standing nominal, so the case is an aspirant
                   however it was booked. The repair door; no
                   acceptance happened, so 'last_accept' stands."""
        self._member_state.on_detected_unaccepted_in_good()
        return self

    def on_nominal_removed(self):
        """RETURN: CTestRunInfo, self -- nothing is accepted any more,
                   so the acceptance and the verdict go with it."""
        self._member_state.on_nominal_removed()
        return self._with(last_accept=None, last_verdict=None,
                          report=None)

    def on_no_output(self):
        """RETURN: CTestRunInfo, self, UNMOVED in state. A run that
                   produced nothing cannot be accepted, so it cannot
                   change what was."""
        self._member_state.on_no_output()
        return self

    def on_no_terminal(self):
        """RETURN: CTestRunInfo, self, UNMOVED in state (R-70)."""
        self._member_state.on_no_terminal()
        return self

    def on_run_verdict(self, ok_f, report=None):
        """
        RETURN: CTestRunInfo, self, with 'last_verdict' and 'report'
                written. The MEMBER STATE DOES NOT MOVE: a member that
                failed is still a member (E-15).

        RAISES: MemberStateFault, where the case is not runnable -- it
                got past a gate that should have refused it.
        """
        self._member_state.on_run_verdict(ok_f)
        return self._with(last_verdict=bool(ok_f),
                          report=report or self._report)

    def on_stain(self, repeat_n, when):
        """RETURN: CTestRunInfo, self, with the flapping record written
                   (B-2). A stain says the case disagreed with itself;
                   it moves no state."""
        return self._with(stain={"repeat_n": int(repeat_n),
                                 "when": when})

    def __repr__(self):
        """RETURN: str, the case, its state, and the last verdict."""
        return "CTestRunInfo(%s: %s, last_verdict=%s)" \
               % (self.name, self._member_state.state, self._last_verdict)


def of_row(test, choice, row_db, nominal_stands_f, carries_unaccepted_f):
    """
    RETURN: CTestRunInfo, a live entry: the member state built from
            THE FILES ('of_evidence'), every other field from the
            book's row.

    THE FILES DECIDE THE STATE, the row decides the rest. A file is
    testimony; a row is a record of it. Where the two disagree,
    'consistency_fault_tuple' names it -- it is not mended here.
    """
    row_db = row_db or {}
    verdict = row_db.get("verdict")
    return CTestRunInfo(
        test          = test,
        choice        = choice,
        member_state  = of_evidence(test, choice, nominal_stands_f,
                                    carries_unaccepted_f),
        test_id       = row_db.get("test_id"),
        choice_id     = row_db.get("choice_id"),
        last_verdict  = None if verdict is None else bool(verdict is True),
        report        = row_db.get("report"),
        last_accept   = row_db.get("last_accept") or None,
        coverage      = row_db.get("coverage") or None,
        stderr        = row_db.get("stderr") or None,
        stain         = row_db.get("stain"))
