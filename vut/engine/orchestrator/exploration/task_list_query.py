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
from vut.engine.bookkeeper.test_run_info import of_case, E_MemberState
from vut.auxiliary import clock
from datetime import datetime, timezone

from ..plan.wish    import cutoff_instant
from ..plan.label   import (STANDARD_LABEL, evaluate_f,
                            label_name_tuple, literal_target_f,
                            parse_expression)
from .configuration_tree import CTestCaseSequence
from .task_list     import (CTestTaskList, CTestTaskListAll,
                            SelectionError)


#  THE OPERATION NAMES AN OBSERVATION, NEVER A DECISION (E-36): the
#  local database records what THIS MACHINE SAW, per operation, and
#  'observation_of_case' is the only thing that may be handed it. The
#  Bookkeeper's 'result()' answers what the software IS -- a verdict
#  for a (test, choice) -- and knows no operation at all.
RUN_OPERATION = "Run"


def directory_hit_f(where, glob_text):
    """
    RETURN: bool, True where 'glob_text' names the directory 'where'
            (relative, '/'-separated) or an ancestor of it.

    ONE RULE WHEREVER A DIRECTORY IS NAMED (disc-10): a glob carrying '/'
    is matched against the path and every ancestor; a BARE NAME against
    every path COMPONENT -- so everything below what it names goes too.
    """
    where = where.replace(os.sep, "/").strip("/")
    if glob_text.startswith("./"): glob_text = glob_text[2:]
    if "/" in glob_text:
        part_list = where.split("/")
        return any(fnmatch.fnmatchcase("/".join(part_list[:end]), glob_text)
                   for end in range(1, len(part_list) + 1))
    return any(fnmatch.fnmatchcase(part, glob_text)
               for part in where.split("/"))


def dir_ruled_out_f(where, rule_tuple):
    """
    RETURN: bool, True where the directory rules -- ('+', glob) for
            '--dir', ('-', glob) for '--exclude-dir', in command-line
            order -- leave the directory 'where' out.

    GREP'S RULE (services E-15): the LAST rule matching decides; where
    none matches, the directory is out only where the FIRST rule is a
    '--dir'.
    """
    if not rule_tuple: return False
    last = None
    for kind, text in rule_tuple:
        if directory_hit_f(where, text.strip()): last = kind
    if last is not None: return last == "-"
    return rule_tuple[0][0] == "+"


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
        self.meta_hidden_n  = 0      # cases the standard label hid
        self.wish_skipped_n = 0      # cases the wish did not want
        self.label_tree = None
        self.label_settled_f = False
        self.language_db     = {}       # source_file -> language | None

    def get_test_cases(self, app_set):
        """
        RETURN: CTestCaseSequence, the cases of 'app_set' that answer
                every question the wish asks -- empty where none does.
        """
        self._settle_label()
        self._settle_language(app_set)
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

        COUNTED, NOT FORGOTTEN. A case the wish does not want is
        SKIPPED -- 'wish_skipped_n' -- and the run's last line draws
        how many. One exception is named apart: a case the standard
        label 'meta' hides from a wish that named NO label is EXCLUDED
        -- 'meta_hidden_n' -- stated in the numbers, drawn nowhere.
        Silence about the framework's own tests is the wish's; the
        number is the reader's.
        """
        if self._label_hidden_f(case):
            if self.label_tree is None: self.meta_hidden_n  += 1
            else:                       self.wish_skipped_n += 1
            return False
        wanted = self._wanted_by_wish_f(case)
        if not wanted: self.wish_skipped_n += 1
        return wanted

    def _wanted_by_wish_f(self, case):
        """
        RETURN: bool, True where the case answers every question the
                wish asks, the labels apart.
        """
        if self._dir_ruled_out_f():                         return False
        if self._outside_language_f(case):                  return False
        if self._excluded_f(case):                          return False
        if self.wish.asks_glob_f() and not self._glob_hit_f(case):
            return False
        if not self.wish.asks_base_f():
            return True

        #  '--unaccepted' (E-58): NO NOMINAL STANDS. A fact of the
        #  store, not of the book -- a nominal can be blessed and the
        #  book know nothing of it (accepted outside the book, E-41).
        if self.wish.unaccepted_f:
            if self._nominal_stands_f(case): return False
            if not (self.wish.fail_f or self.wish.pass_f
                    or self.wish.since_spec or self.wish.until_spec
                    or self.wish.faster_than_ms is not None):
                return True
        entry = self.bookkeeper.result(case.source_file, case.choice)
        observed = self._observation(case)
        if entry is None:
            #  NEVER RUN. It has no last verdict and lies since no
            #  point -- but it is older than every point: '--until='
            #  alone among the base questions wants it.
            return self.wish.until_spec is not None \
                   and not self.wish.fail_f and not self.wish.pass_f \
                   and self.wish.since_spec is None

        #  AN ASPIRANT IS NEITHER (B-14): what never ran cannot have
        #  failed, and '--fail' iterates FAIL and nothing else.
        verdict = entry.get("verdict")
        if self.wish.fail_f and not (verdict is not None and verdict.failed_f):
            return False
        if self.wish.pass_f and not (verdict is not None and verdict.passed_f):
            return False

        #  THE INSTANT AND THE DURATION ARE OBSERVATIONS, and live in
        #  THIS MACHINE'S local database, never in the book (E-22).
        #  SILENCE IS NOT SELECTED: a case this machine has not
        #  observed answers no observation question, and a fresh
        #  checkout selects nothing here -- the correct answer, not a
        #  defect.
        if self.wish.faster_than_ms is not None:
            if observed is None or observed.duration_ms is None:
                return False
            if observed.duration_ms >= self.wish.faster_than_ms:
                return False
        instant = None if observed is None \
                  else self._instant_of_epoch(observed.when)
        if self.wish.since_spec is not None:
            cutoff = cutoff_instant(self.wish.since_spec, self._now())
            if instant is None or instant < cutoff:         return False
        if self.wish.until_spec is not None:
            cutoff = cutoff_instant(self.wish.until_spec, self._now())
            if instant is None or instant >= cutoff:        return False
        return True

    def _test_run_info(self, case):
        """
        RETURN: CTestRunInfo, the case's live entry -- its MEMBER STATE
                read from the files, its other fields from the book
                (B-15). None where no bookkeeper is at hand, or where
                the store cannot be read.

        THE ONE DOOR. This query no longer asks whether a nominal
        stands and decides for itself what that means: it asks the
        entry, and the entry answers 'is_runnable()'.
        """
        if self.bookkeeper is None: return None
        try:
            return of_case(self.bookkeeper.directory, case.source_file,
                           case.choice, self.bookkeeper)
        except Exception:
            return None

    def _nominal_stands_f(self, case):
        """RETURN: bool, True where something was accepted for the case
        -- the entry is not UNKNOWN. False where nothing was, or where
        no bookkeeper is at hand."""
        info = self._test_run_info(case)
        if info is None: return False
        return info.member_state.state is not E_MemberState.UNKNOWN


    def _observation(self, case):
        """
        RETURN: Observation | None -- what THIS MACHINE last saw the
                'Run' of that case do; None where it has seen none, or
                where the local file cannot be read (a corrupt local
                file selects nothing rather than refusing a whole run).
        """
        from .observation_access import observation_of_case
        return observation_of_case(self.bookkeeper, case, RUN_OPERATION)

    @staticmethod
    def _instant_of_epoch(when):
        """
        RETURN: datetime | None, the epoch second as an aware UTC
                instant -- the shape the window compares against.
        """
        if when is None: return None
        from datetime import datetime, timezone
        return datetime.fromtimestamp(int(when), tz=timezone.utc)

    def _settle_language(self, app_set):
        """
        RETURN: None. Settles the wish's language question for THIS
                app set: every name '--language' gives must stand as an
                entry of 'language-setup' (R-75), and each test
                application's resolved language is noted for the
                predicate.

        Raises SelectionError, naming the name and the declared
        entries, where a name no entry declares is asked for: a
        misspelt language silently selecting nothing is how an author
        comes to believe a set is empty.
        """
        if not self.wish.language_tuple: return
        setup_db = getattr(app_set.directory_spec, "language_setup", None) \
                   or {}
        for name in self.wish.language_tuple:
            if name not in setup_db:
                raise SelectionError(
                    "'--language=%s' names no entry of 'language-setup' "
                    "in 'hwut-root.conf'; declared: %s"
                    % (name, ", ".join(sorted(setup_db)) or "(none)"))
        self.language_db = {app.source_file: app.language
                            for app in app_set}

    def _outside_language_f(self, case):
        """
        RETURN: bool, True where the wish names languages and the
                case's test application is of none of them.
        """
        if not self.wish.language_tuple: return False
        return self.language_db.get(case.source_file) \
               not in self.wish.language_tuple

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
        selects through a wish is silent alike -- else 'hwut.report.wishlist'
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
        now = self.now or clock.now()
        if now.tzinfo is None: now = now.replace(tzinfo=timezone.utc)
        return now

    def _dir_ruled_out_f(self):
        """
        RETURN: bool, True where the wish's directory rules -- '--dir'
                and '--exclude-dir' -- leave this query's directory out.

        GREP'S RULE, as GNU grep settles '--include' against
        '--exclude': the rules are read IN COMMAND-LINE ORDER and the
        LAST ONE MATCHING decides. Where none matches, the directory is
        out only where the FIRST rule is a '--dir' -- naming a
        directory asks for it and nothing else, and several are a union
        among themselves (disc-10), NARROWING the rest of the wish:
        '--dir a --fail' is 'the failing runs under a'.

        A wish built without its ordered rules states includes before
        excludes, so an exclusion still wins there.

        THE MATCHING IS ONE RULE: a glob carrying '/' is matched
        against the whole relative path and every ancestor, a BARE NAME
        against every path COMPONENT -- so an '--exclude-dir' takes
        everything below what it names.
        """
        rule_tuple = self.wish.dir_rule_tuple \
                     or tuple(("+", text) for text in self.wish.dir_tuple) \
                      + tuple(("-", text)
                              for text in self.wish.exclude_dir_tuple)
        if not rule_tuple or self.directory is None: return False
        return dir_ruled_out_f(self.directory, rule_tuple)

    def _excluded_f(self, case):
        """
        RETURN: bool, True where an '--exclude' of the wish names the
                case -- and such an exclusion OUTRANKS every include: a
                case it names is not wanted, whatever else selected it.
                Directories are the directory rules' ('_dir_ruled_out_f').
        """
        for text in self.wish.exclude_tuple:
            file_glob, _, choice_glob = text.partition(" ")
            if not self._file_hit_f(case, file_glob.strip()): continue
            choice_glob = choice_glob.strip()
            if not choice_glob:                            return True
            choice = "" if case.choice is None else case.choice
            if fnmatch.fnmatchcase(choice, choice_glob):   return True
        return False

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
