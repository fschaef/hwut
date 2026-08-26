"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE TEST REGISTER of one directory -- every test application
         and every choice carries a NUMBER, and the number survives a
         rename.

DESCRIPTION
       RELATIONAL, two tables, ids scoped where their names are unique:

           APP      app_id    o--o  application file name
           CHOICE   choice_id o--o  choice name, PER application

       A RUN is a 'TestRunId': the application's id, and the choice's
       where the test has choices. Renaming an application touches ONE
       entry, however many choices it has; that is what the second
       table buys.

       IDS ARE DIRECTORY-LOCAL (coverage RATIONALE D-14): unique inside
       this directory by construction, meaningless outside it. A gather
       across directories qualifies at gather time and never stores.

       GIVING BACK. 'hwut.accept' must name a run BEFORE it knows the
       acceptance will stand -- a coverage record is seated at harvest.
       So it allocates as usual and, if it aborts, calls
       'give_back(run_id)': the id is removed and the scope's mark
       steps back IF that id is still the last one issued. Where it is
       not -- something else allocated in between -- the mark stands
       and the number is simply retired. Both outcomes are safe under
       the law below; no reservation, no transaction, no pending state.

       AN ID IS ISSUED ONCE AND NEVER AGAIN (bookkeeper RATIONALE B-2).
       Each scope counts from 0 upward; the next id is one above the
       highest that scope ever issued, and the file carries that
       high-water mark ('N:' lines) so a removal cannot lower it.
       REMOVAL DELETES the name; the number is RETIRED. So an id MAY
       leave this book -- a coverage record, a group table, a report
       may carry it -- and decodes later to the same test, or to 'no
       longer registered', never to another test.

       THE CEILING IS ID_LIMIT (2**32): a scope that would issue that
       id REFUSES BY NAME. The two scopes are the applications of the
       directory and the choices of ONE application; group ids are a
       third scope of their own ('group_table.py').

       THE GENERATION ('G:') counts mutations of this file. A snapshot
       of the register -- what a coverage delivery carries (coverage
       D-25) -- names the generation it copied, so a reader can say
       whether the directory has moved since, rather than decoding
       against a table that has changed.

       THE FILE is 'GOOD/test_ids.dat', beside the result base, written
       the same way: atomically, left write-protected. It is written on
       every mutation. A MISSING file reads as an empty register (a
       fresh directory); a DAMAGED one REFUSES BY NAME -- unlike the
       result base, which reads empty on damage, because exploration
       restricts itself to this register and an empty reading would
       silently hide every test.

WHO WRITES
       THE SHAPE 'TestRunId' STANDS IN 'test_run_id.py', this
       component's, and every consumer imports it from there. THIS
       module owns the allocation, the file and the names.

       Allocation happens at ACCEPT: a test enters the register when
       its first candidate is blessed. Renaming and removal are the
       healing services' business, through this adapter and never
       around it. One writer per key space; this module is the writer.
______________________________________________________________________________
"""
import os
import stat
from   pathlib     import Path

from   .test_run_id import TestRunId, ID_LIMIT


FILE_NAME      = "test_ids.dat"
FORMAT_VERSION = "5"


class TestIdFault(ValueError):
    """A register that cannot be read, a name collision, or an id that
    names nothing where a name was required."""
    pass


def next_id_of(mark, scope_name):
    """
    RETURN: int, 'mark' itself -- the id a scope issues next, where it
            lies below ID_LIMIT.

    Raises TestIdFault where it does not: the scope has issued 2**32
    ids and issues no more.
    """
    if mark >= ID_LIMIT:
        raise TestIdFault("%s has issued %i ids; no more are issued"
                          % (scope_name, ID_LIMIT))
    return mark


class TestIdDb:
    """The register of one directory: two tables, and the one door to
    'GOOD/test_ids.dat'.

    Made where the Bookkeeper is made; a service that needs one makes
    it inside the service. Every mutator PERSISTS before it returns.
    """

    def __init__(self, directory):
        """
        RETURN: TestIdDb over 'directory', loaded from its
                'GOOD/test_ids.dat'. A missing file reads as an empty
                register; a damaged one raises TestIdFault naming the
                first fault.
        """
        self.directory   = Path(directory)
        self._app_db     = {}     # app_id -> name
        self._app_id_db  = {}     # name   -> app_id
        self._choice_db  = {}     # app_id -> {choice_id: name}
        self._next_app   = 0      # high-water mark of the app scope
        self._next_choice_db = {} # app_id -> high-water mark of its choices
        self.generation      = 0  # bumped on every mutation (coverage D-25)
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return
        self._parse(text)

    @property
    def path(self):
        """RETURN: Path, the one file of this register."""
        return self.directory / "GOOD" / FILE_NAME

    def __len__(self):
        """RETURN: int, how many applications are registered."""
        return len(self._app_db)

    # -- asking ---------------------------------------------------------
    def run_id_of(self, app, choice=None, allocate_f=False):
        """
        RETURN: TestRunId, the run's id -- the standing one, or a
                freshly allocated one where 'allocate_f' (persisted
                before return).
                None, where it is unknown and allocation was not asked
                for.

        Raises TestIdFault where the scope that must issue has reached
        ID_LIMIT.

        Allocation is NEXT-NEVER-REUSED in each scope: the app id one
        above the highest app id this directory ever issued, the
        choice id one above the highest THIS app ever issued.
        """
        app_id = self._app_id_db.get(app)
        if app_id is None:
            if not allocate_f: return None
            app_id = next_id_of(self._next_app, "the app scope")
            self._next_app          = app_id + 1
            self._app_db[app_id]    = app
            self._app_id_db[app]    = app_id
            self._choice_db[app_id] = {}
            self._next_choice_db[app_id] = 0
            self._save()
        if choice is None:
            return TestRunId(app_id, None)

        choice_db = self._choice_db[app_id]
        for choice_id, name in choice_db.items():
            if name == choice: return TestRunId(app_id, choice_id)
        if not allocate_f: return None
        choice_id = next_id_of(self._next_choice_db[app_id],
                               "the choice scope of app %i" % app_id)
        self._next_choice_db[app_id] = choice_id + 1
        choice_db[choice_id] = choice
        self._save()
        return TestRunId(app_id, choice_id)

    def name_of(self, run_id):
        """
        RETURN: (str, str|None), the application and choice names that
                run id spells.
                None, where the register does not hold it -- which the
                caller must not read as 'nobody': it is a question
                about a number this directory never issued.
        """
        app = self._app_db.get(run_id.app_id)
        if app is None: return None
        if run_id.choice_id is None: return (app, None)
        choice = self._choice_db[run_id.app_id].get(run_id.choice_id)
        return None if choice is None else (app, choice)

    def app_iterable(self):
        """
        YIELD: [0] int   the application's id, ascending
               [1] str   its file name
               [2] tuple of (int, str), its choices, id-ascending
        """
        for app_id in sorted(self._app_db):
            yield (app_id, self._app_db[app_id],
                   tuple(sorted(self._choice_db[app_id].items())))

    def roster(self):
        """
        RETURN: tuple of str, every registered application file name,
                sorted -- what exploration restricts itself to.
        """
        return tuple(sorted(self._app_id_db))

    def vanished(self):
        """
        RETURN: tuple of (int, str), id and name of every registered
                application whose FILE IS ABSENT in the directory --
                a test that vanished UNOFFICIALLY, removal never
                passing through 'hwut.remove'. Empty where the
                register and the directory agree.
        """
        return tuple((app_id, name)
                     for app_id, name in sorted(self._app_db.items())
                     if not (self.directory / name).is_file())

    # -- healing --------------------------------------------------------
    def rename_app(self, app_id, fresh):
        """
        RETURN: str, the OLD name. The id is unchanged -- that is the
                point of the register: however many choices the test
                has, a rename touches this one entry.

        Raises TestIdFault on an unknown id, or where 'fresh' is
        another live application's name.
        """
        standing = self._app_db.get(app_id)
        if standing is None:
            raise TestIdFault("no app id %s is registered" % app_id)
        holder = self._app_id_db.get(fresh)
        if holder is not None and holder != app_id:
            raise TestIdFault("renaming app %i to '%s' collides with "
                              "app %i" % (app_id, fresh, holder))
        del self._app_id_db[standing]
        self._app_db[app_id]   = fresh
        self._app_id_db[fresh] = app_id
        self._save()
        return standing

    def rename_choice(self, app_id, choice_id, fresh):
        """
        RETURN: str, the OLD choice name; the ids are unchanged.

        Raises TestIdFault on an unknown id pair, or where 'fresh' is
        another live choice of the same application.
        """
        choice_db = self._choice_db.get(app_id)
        if choice_db is None or choice_id not in choice_db:
            raise TestIdFault("no run id %s is registered"
                              % TestRunId(app_id, choice_id))
        for standing_id, name in choice_db.items():
            if name == fresh and standing_id != choice_id:
                raise TestIdFault(
                    "renaming choice %s to '%s' collides with %s"
                    % (TestRunId(app_id, choice_id), fresh,
                       TestRunId(app_id, standing_id)))
        old = choice_db[choice_id]
        choice_db[choice_id] = fresh
        self._save()
        return old

    def give_back(self, run_id):
        """
        RETURN: True,  the scope's mark stepped BACK: that id was the
                       last one issued and is now unissued.
                False, the entry is gone but the mark STANDS: something
                       was issued after it, and lowering the mark would
                       hand the later id out twice.

        Raises TestIdFault where the run id is not registered.

        FOR AN ABORTED ACCEPT, which must name a run before it knows
        the acceptance will stand. Either outcome is safe: an id whose
        mark stepped back reached no file that survives, and one whose
        mark stands is simply retired (B-4).
        """
        if run_id.choice_id is None:
            standing = self._app_db.get(run_id.app_id)
            if standing is None:
                raise TestIdFault("no app id %s is registered"
                                  % run_id.app_id)
            if self._choice_db[run_id.app_id]:
                raise TestIdFault(
                    "app %i still holds %i choice(s); give those back "
                    "first" % (run_id.app_id,
                               len(self._choice_db[run_id.app_id])))
            self.remove_app(run_id.app_id)
            if run_id.app_id + 1 != self._next_app: return False
            self._next_app = run_id.app_id
            self._save()
            return True

        self.remove_choice(run_id.app_id, run_id.choice_id)
        mark = self._next_choice_db[run_id.app_id]
        if run_id.choice_id + 1 != mark: return False
        self._next_choice_db[run_id.app_id] = run_id.choice_id
        self._save()
        return True

    def remove_app(self, app_id):
        """
        RETURN: str, the name that is gone. The entry is DELETED, its
                choices with it; the ids are RETIRED -- the app scope's
                mark stands, so no later test is issued this number.

        Raises TestIdFault on an unknown id.
        """
        standing = self._app_db.get(app_id)
        if standing is None:
            raise TestIdFault("no app id %s is registered" % app_id)
        del self._app_db[app_id]
        del self._app_id_db[standing]
        del self._choice_db[app_id]
        del self._next_choice_db[app_id]
        self._save()
        return standing

    def remove_choice(self, app_id, choice_id):
        """
        RETURN: str, the choice name that is gone; its id is RETIRED --
                the application's mark stands.

        Raises TestIdFault on an unknown id pair.
        """
        choice_db = self._choice_db.get(app_id)
        if choice_db is None or choice_id not in choice_db:
            raise TestIdFault("no run id %s is registered"
                              % TestRunId(app_id, choice_id))
        old = choice_db.pop(choice_id)
        self._save()
        return old

    # -- the file ---------------------------------------------------------
    def format(self):
        """
        RETURN: str, the register as it is stored:
                    'G:<generation>'                  bumped per mutation
                    'N:<next app id>'                 the app scope's mark
                    'A:<id> <name>'                   per application
                    'N:<app_id>.<next choice id>'     its choice mark
                    'C:<app_id>.<choice_id> <name>'   per choice
                ids ascending.

        MACHINE-FREE: names and numbers, no paths outside the tree, no
        timestamps.
        """
        line_list = ["##VUT-TEST-IDS " + FORMAT_VERSION,
                     "G:%i" % self.generation,
                     "N:%i" % self._next_app]
        for app_id, name, choice_tuple in self.app_iterable():
            line_list.append("A:%i %s" % (app_id, name))
            line_list.append("N:%i.%i" % (app_id,
                                          self._next_choice_db[app_id]))
            line_list += ["C:%i.%i %s" % (app_id, choice_id, choice)
                          for choice_id, choice in choice_tuple]
        return "\n".join(line_list) + "\n"

    def _parse(self, text):
        """
        RETURN: None; the tables filled from 'text'.

        Raises TestIdFault naming the first fault. Versions 1 and 2
        (the coverage component's pair-interned tables, coverage
        RATIONALE D-9 and D-14) and version 3 (this register before
        it kept its marks, reusing ids) are refused by name.

        A MARK IS REQUIRED, for the directory and for every
        application, and every id read must lie below its scope's mark
        and below ID_LIMIT: a register that would re-issue is not read.
        """
        seen = False
        self._app_mark_seen = False
        for raw in text.splitlines():
            line = raw.strip()
            if not line: continue
            if line.startswith("##"):
                if line.startswith("##VUT-TEST-IDS"):
                    seen    = True
                    version = line[len("##VUT-TEST-IDS"):].strip()
                    if version != FORMAT_VERSION:
                        raise TestIdFault(
                            "register version '%s' is not read; this "
                            "build writes %s. Versions 1 and 2 were "
                            "the pair-interned tables; version 3 "
                            "re-used ids and kept no mark; version 4 "
                            "kept no generation."
                            % (version or "<none>", FORMAT_VERSION))
                continue
            head, _, name = line.partition(" ")
            if head.startswith("G:"):
                try:               self.generation = int(head[2:])
                except ValueError: raise TestIdFault(
                                       "'%s' spells no generation" % line)
                continue
            if head.startswith("N:"):
                self._parse_mark(head[2:], line)
                continue
            if not name:
                raise TestIdFault("register line '%s' names nothing"
                                  % line)
            if head.startswith("A:"):
                try:               app_id = int(head[2:])
                except ValueError:
                    raise TestIdFault("'%s' spells no app id" % head)
                if app_id in self._app_db:
                    raise TestIdFault("app id %i stands twice" % app_id)
                if app_id >= ID_LIMIT:
                    raise TestIdFault("app id %i lies beyond ID_LIMIT"
                                      % app_id)
                if name in self._app_id_db:
                    raise TestIdFault("app name '%s' stands twice"
                                      % name)
                self._app_db[app_id]    = name
                self._app_id_db[name]   = app_id
                self._choice_db[app_id] = {}
            elif head.startswith("C:"):
                pair = head[2:].split(".")
                try:
                    app_id, choice_id = int(pair[0]), int(pair[1])
                except (ValueError, IndexError):
                    raise TestIdFault("'%s' spells no app.choice id"
                                      % head)
                choice_db = self._choice_db.get(app_id)
                if choice_db is None:
                    raise TestIdFault("choice %s.%s names an app id "
                                      "that is not registered"
                                      % (app_id, choice_id))
                if choice_id in choice_db:
                    raise TestIdFault("run id %i.%i stands twice"
                                      % (app_id, choice_id))
                if name in choice_db.values():
                    raise TestIdFault("choice name '%s' stands twice "
                                      "under app %i" % (name, app_id))
                choice_db[choice_id] = name
            else:
                raise TestIdFault("unknown register line '%s'" % line)
        if not seen:
            raise TestIdFault("the register names no format version")
        if not self._app_mark_seen:
            raise TestIdFault("the register carries no app mark 'N:'")
        for app_id in self._app_db:
            if app_id >= self._next_app:
                raise TestIdFault("app id %i lies at or above the mark %i"
                                  % (app_id, self._next_app))
            mark = self._next_choice_db.get(app_id)
            if mark is None:
                raise TestIdFault("app %i carries no choice mark 'N:%i.'"
                                  % (app_id, app_id))
            for choice_id in self._choice_db[app_id]:
                if choice_id >= mark:
                    raise TestIdFault(
                        "run id %i.%i lies at or above the mark %i"
                        % (app_id, choice_id, mark))
        for app_id in self._next_choice_db:
            if app_id not in self._app_db:
                raise TestIdFault("choice mark 'N:%i.' names an app id "
                                  "that is not registered" % app_id)

    def _parse_mark(self, body, line):
        """
        RETURN: None; the app mark, or one application's choice mark,
                taken from 'body' ('5' or '0.3').

        Raises TestIdFault where it spells neither, stands twice, or
        lies beyond ID_LIMIT.
        """
        part_list = body.split(".")
        try:
            value_list = [int(p) for p in part_list]
        except ValueError:
            raise TestIdFault("'%s' spells no mark" % line)
        if any(v > ID_LIMIT for v in value_list):
            raise TestIdFault("mark '%s' lies beyond ID_LIMIT" % line)
        match value_list:
            case [mark]:
                if self._app_mark_seen:
                    raise TestIdFault("the app mark stands twice")
                self._app_mark_seen = True
                self._next_app      = mark
            case [app_id, mark]:
                if app_id in self._next_choice_db:
                    raise TestIdFault("the choice mark of app %i stands "
                                      "twice" % app_id)
                self._next_choice_db[app_id] = mark
            case _:
                raise TestIdFault("'%s' spells no mark" % line)

    def _save(self):
        """
        RETURN: None. The whole file, replaced atomically and left
                write-protected -- the result base's own treatment.
                The GENERATION is bumped first: every write is a
                mutation, and a snapshot must be able to tell them
                apart (coverage D-25).
        """
        self.generation += 1
        path = self.path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR
                           | stat.S_IRGRP | stat.S_IROTH)
        temporary = path.with_suffix(".dat.tmp")
        temporary.write_text(self.format(), encoding="utf-8")
        os.replace(temporary, path)
        os.chmod(path, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
