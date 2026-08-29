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
from ..plan.label   import (STANDARD_LABEL, evaluate_f,
                            label_name_tuple, literal_target_f,
                            parse_expression)
from .configuration_tree import CTestCaseSequence
from .task_list     import (CTestTaskList, CTestTaskListAll,
                            SelectionError)


RUN_OPERATION = "Run"


class CTestTaskListQuery(CTestTaskList):
    """The cases of the directory that answer every question the wish
    asks. Several globs hold ONE question, OR'ed; questions of
    different kinds are AND'ed."""

    def __init__(self, wish, bookkeeper=None, now=None, directory=None,
                 root=None, label_view=None):
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

        'label_view'  what 'hwut-root.labels' assigns (CLabelView,
                      plan/label.py), built by the file's reader and
                      handed down. Required where the wish asks a
                      LABEL question; where handed at all, the query
                      SILENCES the standard label: a wish that asks no
                      label does not want what 'meta' labels (disc-8).
                      'None' means NO LABEL KNOWLEDGE REACHES HERE --
                      no silence, and a '--label' wish is REFUSED
                      rather than answered by guessing.

        Raises AssertionError where a base question stands without a
        Bookkeeper -- refused at the door, not answered by guessing.
        """
        assert bookkeeper is not None or not wish.asks_base_f(), \
               "the wish asks the base (%s) and no Bookkeeper was " \
               "handed down" % wish
        assert label_view is None \
               or (directory is not None and root is not None), \
               "a label view is handed to a query that does not " \
               "know its place (directory and root)"
        self.wish       = wish
        self.bookkeeper = bookkeeper
        self.now        = now
        self.directory  = directory
        self.root       = root
        self.label_view = label_view
        self.label_tree = None
        self.label_settled_f = False

    def get_test_cases(self, app_set):
        """
        RETURN: CTestCaseSequence, the cases of 'app_set' that answer
                every question the wish asks -- empty where none does.
        """
        self._settle_label()
        every = CTestTaskListAll().get_test_cases(app_set)
        #  A wish stating nothing takes ALL AVAILABLE -- unless a
        #  standard label stands somewhere, for then 'available' is
        #  itself the question. An empty or silence-free view is NO
        #  VIEW for this purpose, so a tree that labels nothing walks
        #  the very path it walked before labels existed.
        if self.wish.states_nothing_f() \
           and (self.label_view is None
                or not self.label_view.silences_f()):
            return every
        return CTestCaseSequence(tuple(case for case in every
                                       if self._wanted_f(case)))

    def _wanted_f(self, case):
        """
        RETURN: bool, True where the case answers every question the
                wish asks.
        """
        if self._label_hidden_f(case):                      return False
        if self._outside_dir_f():                           return False
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

    def _settle_label(self):
        """
        RETURN: None. Settles the wish's label question, once, at the
                first selection -- inside 'get_test_cases', which is
                the one door every face already guards.

        Raises SelectionError where the wish asks a label question and
        no label view was handed down -- refused, not silently
        answered with everything -- or where it names a label that
        does not stand, BY NAME: a misspelt label silently naming
        nothing is how an author comes to believe a set is empty.
        """
        if self.label_settled_f: return
        self.label_settled_f = True
        if not self.wish.asks_label_f(): return
        if self.label_view is None:
            raise SelectionError(
                "'--label %s' asks 'hwut-root.labels', and no label "
                "view reaches this selection" % self.wish.label_spec)
        self.label_tree = parse_expression(self.wish.label_spec)
        unknown = [name for name in label_name_tuple(self.label_tree)
                   if name not in self.label_view.defined]
        if unknown:
            raise SelectionError(
                "no label '%s' stands in 'hwut-root.labels'"
                % "', '".join(unknown))

    def _label_hidden_f(self, case):
        """
        RETURN: bool, True where the labels hide the case: the wish's
                label expression does not name it -- or, where the
                wish asks NO label, the standard label 'meta' does.
                False where no label view reaches this query: no
                knowledge, no silence.

        THE SILENCE IS THE WISH'S, not one face's: a wish that asks no
        label does not want what 'meta' labels, and every face that
        selects through a wish is silent alike -- else 'hwut.wishlist'
        and 'hwut.run --wishlist' would select different sets and the
        disc-5 round trip would no longer close.
        """
        if self.label_view is None: return False
        where = os.path.normpath(os.path.join(
                    self.root, self.directory, case.source_file))
        label_set = self.label_view.label_set_of(where, case.choice)
        if self.label_tree is not None:
            return not evaluate_f(self.label_tree, label_set)
        if STANDARD_LABEL not in label_set:      return False
        #  AN EXPLICIT TARGET DOMINATES THE SILENCE (disc-8): the
        #  silence is what a wish carries when it asks NOTHING, and a
        #  named run is not nothing. A face that names a run and then
        #  passes it by is the silent failure this whole feature
        #  exists to prevent, arriving from the other side.
        return not self._named_literally_f(case)

    def _now(self):
        """
        RETURN: datetime, the stated clock, or the current UTC instant
                where none was stated.
        """
        now = self.now or datetime.now(timezone.utc)
        if now.tzinfo is None: now = now.replace(tzinfo=timezone.utc)
        return now

    def _outside_dir_f(self):
        """
        RETURN: bool, True where the wish names DIRECTORIES and this
                query's directory is none of them.

        '--dir' NARROWS, it does not add (disc-10, fork a): '--dir a
        --fail' is 'the failing runs under a', which is how a person
        says it. Several globs are a UNION among themselves -- naming
        two directories asks for both -- exactly as '--label' unions
        its labels and narrows against the rest.

        THE MATCHING IS '--exclude-dir's OWN: a glob carrying '/' is
        matched against the whole relative path, a BARE NAME against
        every path COMPONENT. One rule, learnt once.
        """
        if not self.wish.dir_tuple: return False
        return not any(self._directory_hit_f(text.strip())
                       for text in self.wish.dir_tuple)

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

    def _named_literally_f(self, case):
        """
        RETURN: bool, True where a LITERAL target of the wish names
                the case -- the file alone, which names every choice
                of it, or file and choice together.

        A glob does not count ('literal_target_f'): where it meets
        only silenced runs it draws a WARNING instead
        ('glob_reach'), so nothing is ever quietly passed by.
        """
        for text in self.wish.glob_tuple:
            if not literal_target_f(text):        continue
            if self._target_hit_f(case, text):    return True
        return False

    def glob_reach(self, app_set):
        """
        RETURN: [0] frozenset[str], every glob of the wish that met at
                    least one case here, the labels disregarded.
                [1] frozenset[str], those of them that met at least
                    one case the labels leave VISIBLE.

        A caller unions both over the whole walk before it judges: a
        glob silenced in one directory may stand plainly in the next,
        and a warning about it there would be a lie.
        """
        met     = set()
        visible = set()
        for case in CTestTaskListAll().get_test_cases(app_set):
            for text in self.wish.glob_tuple:
                if not self._target_hit_f(case, text): continue
                met.add(text)
                if not self._label_hidden_f(case): visible.add(text)
        return frozenset(met), frozenset(visible)

    def _target_hit_f(self, case, text):
        """
        RETURN: bool, True where the one target 'text' names the case.
        """
        choice = "" if case.choice is None else case.choice
        file_glob, _, choice_glob = text.partition(" ")
        if not self._file_hit_f(case, file_glob.strip()): return False
        choice_glob = choice_glob.strip()
        if not choice_glob:                               return True
        return fnmatch.fnmatchcase(choice, choice_glob)

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
        return any(self._target_hit_f(case, text)
                   for text in self.wish.glob_tuple)

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
