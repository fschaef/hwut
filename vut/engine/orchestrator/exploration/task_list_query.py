"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: SELECT BY QUERY -- a task list that answers a wish of fixed
         keywords out of what the directory offers and what the
         Bookkeeper recorded.

'CTestTaskListQuery' is an ordinary 'CTestTaskList': 'get_test_cases'
is the whole interface, so nothing downstream learns a second door
(P-8).

THE DOMAIN IS WHAT THE DIRECTORY OFFERS. The base answers questions
about those cases and nothing else, so a base entry naming a case the
directory no longer offers cannot enter a selection at all.

A case the base has never recorded has no last run: it neither
failed nor passed nor ran since any point -- but it IS older than
every point, so '--until=' wants it. The stale wish reaches what was
never touched.

THE ORDER is the order of 'CTestTaskListAll': files sorted, choices
sorted within a file.

An empty selection is legal and is the caller's to report (P-9).
______________________________________________________________________________
"""
import fnmatch
from datetime import datetime, timezone

from ..plan.wish    import cutoff_instant
from .specification import CTestCaseSequence
from .task_list     import CTestTaskList, CTestTaskListAll


RUN_OPERATION = "Run"


class CTestTaskListQuery(CTestTaskList):
    """The cases of the directory that answer every question the wish
    asks. Several globs hold ONE question, OR'ed; questions of
    different kinds are AND'ed."""

    def __init__(self, wish, bookkeeper=None, now=None):
        """
        RETURN: CTestTaskListQuery over 'wish'.

        'bookkeeper'  the ONE authority on what was recorded, made
                      above and handed down. Required where the wish
                      asks a base question ('--fail', '--pass',
                      '--since=', '--until='); 'None' where it asks
                      none.
        'now'         the instant the points are reckoned from, a
                      datetime; the current UTC instant where none is
                      given. It is a parameter so that a test may
                      state the clock.

        Raises AssertionError where a base question stands without a
        Bookkeeper -- refused at the door, not answered by guessing.
        """
        assert bookkeeper is not None or not wish.asks_base_f(), \
               "the wish asks the base (%s) and no Bookkeeper was " \
               "handed down" % wish
        self.wish       = wish
        self.bookkeeper = bookkeeper
        self.now        = now

    def get_test_cases(self, app_set):
        """
        RETURN: CTestCaseSequence, the cases of 'app_set' that answer
                every question the wish asks -- empty where none does.
        """
        every = CTestTaskListAll().get_test_cases(app_set)
        if self.wish.states_nothing_f(): return every
        return CTestCaseSequence(tuple(case for case in every
                                       if self._wanted_f(case)))

    def _wanted_f(self, case):
        """
        RETURN: bool, True where the case answers every question the
                wish asks.
        """
        if self.wish.glob_tuple and not self._glob_hit_f(case):
            return False
        if not self.wish.asks_base_f():
            return True

        entry = self.bookkeeper.result(case.source_file, case.choice,
                                       RUN_OPERATION)
        if entry is None:
            #  NEVER RUN. It has no last verdict and lies since no
            #  point -- but it is older than every point: '--until='
            #  alone among the base questions wants it.
            return self.wish.until_spec is not None \
                   and not self.wish.fail_f and not self.wish.pass_f \
                   and self.wish.since_spec is None

        if self.wish.fail_f and entry.get("verdict"):       return False
        if self.wish.pass_f and not entry.get("verdict"):   return False

        instant = self._instant(entry.get("when"))
        if self.wish.since_spec is not None:
            cutoff = cutoff_instant(self.wish.since_spec, self._now())
            if instant is None or instant < cutoff:         return False
        if self.wish.until_spec is not None:
            cutoff = cutoff_instant(self.wish.until_spec, self._now())
            if instant is None or instant >= cutoff:        return False
        return True

    def _now(self):
        """
        RETURN: datetime, the stated clock, or the current UTC instant
                where none was stated.
        """
        now = self.now or datetime.now(timezone.utc)
        if now.tzinfo is None: now = now.replace(tzinfo=timezone.utc)
        return now

    def _glob_hit_f(self, case):
        """
        RETURN: bool, True where any glob of the wish names the case.

        A glob of one member names the file and means every choice of
        it; a glob of two members names file and choice, one blank
        between (R-34).
        """
        choice = "" if case.choice is None else case.choice
        for text in self.wish.glob_tuple:
            file_glob, _, choice_glob = text.partition(" ")
            if not fnmatch.fnmatchcase(case.source_file,
                                       file_glob.strip()):
                continue
            choice_glob = choice_glob.strip()
            if not choice_glob:                            return True
            if fnmatch.fnmatchcase(choice, choice_glob):   return True
        return False

    def _instant(self, when_text):
        """
        RETURN: datetime, the recorded instant, UTC / None, where the
                entry carries no readable instant.
        """
        if not when_text: return None
        try:
            when = datetime.fromisoformat(when_text)
        except ValueError:
            return None
        if when.tzinfo is None: when = when.replace(tzinfo=timezone.utc)
        return when
