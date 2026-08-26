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
import os
from datetime import datetime, timezone

from ..plan.wish    import cutoff_instant
from .configuration_tree import CTestCaseSequence
from .task_list     import CTestTaskList, CTestTaskListAll


RUN_OPERATION = "Run"


class CTestTaskListQuery(CTestTaskList):
    """The cases of the directory that answer every question the wish
    asks. Several globs hold ONE question, OR'ed; questions of
    different kinds are AND'ed."""

    def __init__(self, wish, bookkeeper=None, now=None, directory=None,
                 root=None):
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
        'directory'   WHERE THIS QUERY STANDS, relative to the run's
                      root ('suite/TEST'). A glob may carry a PATH
                      MEMBER and a query without a directory cannot
                      answer one -- so a path-bearing glob simply
                      matches nothing here, rather than guessing. The
                      TARGET FORM of 'collision' and 'dependency'
                      (R-34) is untouched: those name NEIGHBOURS
                      within one directory and admit no path.
        'root'        the run's root, ABSOLUTE. A wishlist resolves
                      its './' against ITS OWN directory and so states
                      absolute targets; only the root can bring those
                      and this query's relative 'directory' to a
                      common form. 'None' where no absolute target can
                      arise.

        Raises AssertionError where a base question stands without a
        Bookkeeper -- refused at the door, not answered by guessing.
        """
        assert bookkeeper is not None or not wish.asks_base_f(), \
               "the wish asks the base (%s) and no Bookkeeper was " \
               "handed down" % wish
        self.wish       = wish
        self.bookkeeper = bookkeeper
        self.now        = now
        self.directory  = directory
        self.root       = root

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
        if self._excluded_f(case):                          return False
        if self.wish.asks_glob_f() and not self._glob_hit_f(case):
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

    def _excluded_f(self, case):
        """
        RETURN: bool, True where an exclusion of the wish names the
                case -- and an exclusion OUTRANKS every include: a
                case an exclusion names is not wanted, whatever else
                selected it.

        '--exclude-dir' names a DIRECTORY AND EVERYTHING BELOW IT. A
        glob carrying a '/' is matched against the whole relative
        path; a BARE NAME is matched against every path COMPONENT, so
        'OUT' drops 'a/OUT/TEST' and 'a/OUT/b/TEST' alike.
        """
        for text in self.wish.exclude_dir_tuple:
            if self._directory_hit_f(text.strip()):        return True
        for text in self.wish.exclude_tuple:
            file_glob, _, choice_glob = text.partition(" ")
            if not self._file_hit_f(case, file_glob.strip()): continue
            choice_glob = choice_glob.strip()
            if not choice_glob:                            return True
            choice = "" if case.choice is None else case.choice
            if fnmatch.fnmatchcase(choice, choice_glob):   return True
        return False

    def _directory_hit_f(self, glob_text):
        """
        RETURN: bool, True where 'glob_text' names this query's
                directory or an ancestor of it.
                False where the query does not know its directory --
                the question cannot be answered, and answering it by
                guessing would drop the wrong tests.
        """
        if self.directory is None: return False
        where = self.directory.replace(os.sep, "/").strip("/")
        if glob_text.startswith("./"): glob_text = glob_text[2:]
        if "/" in glob_text:
            #  A PATH: it names the directory or an ancestor of it.
            part_list = where.split("/")
            for end in range(1, len(part_list) + 1):
                if fnmatch.fnmatchcase("/".join(part_list[:end]),
                                       glob_text):          return True
            return False
        #  A BARE NAME: any component, so everything below it goes too.
        return any(fnmatch.fnmatchcase(part, glob_text)
                   for part in where.split("/"))

    def _glob_hit_f(self, case):
        """
        RETURN: bool, True where any glob of the wish names the case.

        A glob of one member names the file and means every choice of
        it; a glob of two members names file and choice, one blank
        between (R-34).

        THE FILE MEMBER MAY CARRY A PATH -- 'messaging/*/test-queue.py'
        -- which is matched against this query's directory joined with
        the file name. A path SELECTS ACROSS A TREE, which is what a
        wishlist does; it is illegal where a target NAMES A NEIGHBOUR
        ('collision', 'dependency'), and those read the bare form.

        A path-bearing glob against a query that does not know its
        directory matches NOTHING: the question cannot be answered
        here, and answering it by ignoring the path would select the
        right file in the wrong place.
        """
        choice = "" if case.choice is None else case.choice
        for text in self.wish.glob_tuple:
            file_glob, _, choice_glob = text.partition(" ")
            if not self._file_hit_f(case, file_glob.strip()): continue
            choice_glob = choice_glob.strip()
            if not choice_glob:                            return True
            if fnmatch.fnmatchcase(choice, choice_glob):   return True
        return False

    def _file_hit_f(self, case, file_glob):
        """
        RETURN: bool, True where 'file_glob' names the case's file --
                by the bare name where the glob carries no path, by
                '<directory>/<file>' where it does.

        A glob of './x' is the same as one of 'x': the leading dot is
        how a wishlist writes 'here' and carries no path of its own.

        AN ABSOLUTE GLOB is what a wishlist leaves behind, having
        resolved its './' against its own directory; it is matched
        against the case's absolute path, which only the root can
        build.
        """
        if file_glob.startswith("./"): file_glob = file_glob[2:]
        if "/" not in file_glob:
            return fnmatch.fnmatchcase(case.source_file, file_glob)
        if self.directory is None: return False
        where = "%s/%s" % (self.directory.replace(os.sep, "/").strip("/"),
                           case.source_file)
        if not os.path.isabs(file_glob):
            return fnmatch.fnmatchcase(where, file_glob)
        if self.root is None: return False
        whole = os.path.normpath(os.path.join(self.root, where))
        return fnmatch.fnmatchcase(whole.replace(os.sep, "/"), file_glob)

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
