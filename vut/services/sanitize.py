"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.sanitize' COMMAND LINE -- what a tree accumulates,
         found and named; and removed only when asked.

IT REPORTS AND DOES NOT ACT. A bare 'hwut.sanitize' walks the tree and
SAYS what it found; nothing is removed, nothing is run. '--apply' is
the whole difference. THE DEFAULT IS THE SAFE ONE because the answers
here are irreversible: a GOOD file is an author's blessed work, and
one deleted by a tool that guessed is gone.

WHAT IT LOOKS FOR, each asked for by its own flag; NONE STATED MEANS
ALL OF THEM, because a wish that states nothing wants everything.

    --session   'TMP/session/' directories. A session's sinks are
                read on 'done' and deleted; a directory that survives
                the run is the wreckage of one that did not finish.
                ALWAYS SAFE TO REMOVE: nothing reads it between runs.

    --lock      'TMP/lock/' directories WHOSE HOLDER IS GONE. A LIVE
                LOCK IS NEVER TOUCHED, not even under '--apply' -- it
                is a running test's claim on its directory, and
                breaking it is how two runs come to write one store.
                The liveness is ASKED, by the mutex's own predicate,
                and where the platform cannot answer, THE LOCK STAYS:
                unknown is not dead.

    --out       'OUT/' directories. The application's product space,
                wiped and rewritten by the next run that uses it, and
                read as subjects only DURING that run. Between runs it
                is scratch.

    --books     THE TWO RECORDS OF ACCEPTANCE DISAGREE (E-41): a
                nominal whose test the book lacks; a book entry the
                book calls ASPIRANT while a nominal stands (B-14); a
                book entry with a nominal and no 'last_accept'. Named,
                and NEVER removed by '--apply': only a person can say
                which of the two is wrong ('hwut.accept',
                'hwut.remove'). A test in the book with no nominal is
                an ASPIRANT, not a disagreement.

    --orphans   RECORDS THAT NAME NOTHING: a nominal under 'GOOD/', a
                candidate under 'TMP/store/', an entry in the book
                ('GOOD/book.csv') or a register id whose
                (test, choice) NO LONGER EXISTS in the directory's
                configuration.

                WHERE THINGS LIVE, since every flag above names one:
                    GOOD/book.csv    THE BOOK: what the software
                                          IS -- verdicts, reports, the
                                          configuration that held.
                                          Versioned with the tests.
                    GOOD/<test>.txt       THE NOMINALS: the oracles.
                    TMP/store/            THE STORE: the recorded
                                          candidates, and the LOCAL
                                          DATABASE ('observations.bin')
                                          of what this machine saw --
                                          when, where, how long.
                Only the last is transient: a wiped 'TMP/' loses no
                verdict, because verdicts are the book's.

                THIS IS THE ONE THAT CAN LOSE WORK. A nominal is
                blessed; if exploration is wrong -- a header that
                stopped parsing, a directory the wish never reached --
                the file is not an orphan, it is unreachable, and
                deleting it destroys an acceptance. So an orphan is
                reported with the reason it is believed to be one, and
                a directory whose exploration RAISED A FAULT is
                REFUSED for orphan work entirely: a tree that cannot
                be read cannot be judged.

    --transient THE TWO TRANSIENT ROOTS WHOLE, 'OUT/' and 'TMP/', per
                directory (services E-24): what a run can make again.
                The tree-wide spelling of 'rm -rf OUT/ TMP/' -- one
                command where three hundred hands invite a mistyped
                glob that takes 'GOOD/' with it. NEVER IMPLIED by a bare
                command line: it takes the candidates with it, and a
                bare call asks about rubbish, not about everything.
                A DIRECTORY WHOSE 'TMP/lock/' NAMES A LIVE HOLDER IS
                REFUSED, named on stderr, and the walk continues: a hand
                typing 'rm -rf TMP/' in one directory has chosen; a tool
                sweeping the tree has not been asked about any one of
                them, and sweeping a live run's ground from under it is
                the failure that reproduces once a month under '--jobs'.
    --target <name>
                RUN A DIRECTORY'S OWN TARGET, e.g. 'clean'. The
                framework does not know what a project's rubbish is;
                the project does, and 'hwut.target' is where it says
                so (E-7). Several may stand; each runs in every
                directory that binds it, in walk order. A target that
                no directory binds is REFUSED BY NAME rather than
                passed over -- a misspelt 'clen' that quietly does
                nothing is worse than one that stops.

                UNDER '--apply' ONLY. A target is somebody's script and
                running it is an act.

THE WISH NARROWS THE WALK, so 'hwut.sanitize --glob "engine/*"' asks
about part of a tree. The wish selects DIRECTORIES here, through the
cases it selects: a directory is asked about where the wish selects
anything in it.

EXIT STATUS (E-1, services/_exit.py):
    0  the walk finished; what was found is reported, and under
       '--apply' was removed or run
    1  something could not be removed, or a target failed
    2  the command line cannot be read, or a target no directory binds
    3  the command line reads, and the wish selects nothing
______________________________________________________________________________
"""
import os
import shutil
import sys

from   vut.auxiliary.directory_mutex                 import (MkdirMutex,
                                                             LOCK_DIRECTORY_NAME)
from   vut.engine.bookkeeper.api              import (Bookkeeper, STORE_DIRECTORY_NAME,
                                                             GOOD_OWNED_FILE_TUPLE,
                                                             E_TestVerdict,
                                                             TestIdFault,
                                                             key_parts_of,
                                                             nominal_stands_f)
from   vut.engine.operations.run.multi_execute import SESSION_DIRECTORY_NAME
from   vut.engine.orchestrator.exploration.task_list import SelectionError
from   vut.engine.orchestrator.exploration.task_list_query \
                                                     import CTestTaskListQuery
from   vut.engine.orchestrator.exploration.tree_explorer \
                                                     import (explore_tree,
                                                             RootConfMissing)
from   vut.engine.orchestrator.plan.wish             import (HELP as WISH_HELP,
                                                             WishError,
                                                             parse_wish)
from   ._exit import E_ExitCode
from   vut.services.lib.cmdline import (face_parser, usage_of,
                                        parse_or_refuse)

#  A record's TEST PART ends in one of these: it is the source file
#  whole. The set is the languages a test application is written in;
#  a language absent here is one whose records this face passes over,
#  which is the safe way to be wrong.
SOURCE_EXTENSION_SET   = frozenset((
    "py", "sh", "bash", "lua", "pl", "rb", "c", "cpp", "cc", "bas",
    "exe", "bat", "ps1", "js", "ts", "vhd", "v", "sv"))

OUT_DIRECTORY_NAME     = "OUT"
TRANSIENT_ROOT_TUPLE   = ("OUT", "TMP")           # services E-24

#  What a bare command line asks about. Not the targets: running
#  somebody's script is never implied.
ASPECT_TUPLE = ("session", "lock", "out", "orphans", "books")
#  Asked for by name only; a bare call never takes the candidates.
EXPLICIT_ASPECT_TUPLE = ("transient",)

#  THE STANDARD READER (E-84). No positional: a bare word is refused as a
#  word this face does not take.
PARSER = face_parser("hwut.sanitize",
                     "Report -- and with '--apply' remove -- what a tree "
                     "leaves behind.")
PARSER.add_argument("--apply", action="store_true")
PARSER.add_argument("--target", action="append", default=[], metavar="name")
for _aspect in ASPECT_TUPLE + EXPLICIT_ASPECT_TUPLE:
    PARSER.add_argument("--" + _aspect, action="store_true")
PARSER.add_argument("--directory", default=None)
ARG_DB = {"--directory": True}
USAGE  = usage_of(PARSER, ARG_DB)

#  The licence line and the rule are the FILE's, not the face's.
HELP = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
       + "\n\n" + WISH_HELP + "\n" + USAGE


class CFinding:
    """ONE thing found, and what it would cost to remove.

    'kind'   the aspect that found it, as an author asked for it
    'path'   what stands, relative to the run's root
    'why'    the reason it is believed to be rubbish, in one line
    'bytes'  what it occupies; None where the question is meaningless
    """
    __slots__ = ("kind", "path", "why", "bytes")

    def __init__(self, kind, path, why, bytes_n=None):
        self.kind  = kind
        self.path  = path
        self.why   = why
        self.bytes = bytes_n


def size_of(path):
    """
    RETURN: int, the bytes a file or a directory tree occupies.
            0, where it cannot be measured -- a size is a courtesy and
            never a reason to fail.
    """
    if os.path.isfile(path):
        try:    return os.path.getsize(path)
        except OSError: return 0
    total = 0
    for base, _dirs, files in os.walk(path):
        for name in files:
            try:    total += os.path.getsize(os.path.join(base, name))
            except OSError: pass
    return total


def shown(root, path):
    """RETURN: str, the path as it reads from the run's root."""
    try:               return os.path.relpath(path, root)
    except ValueError: return path


def session_finding_list(root, directory):
    """
    YIELD: [0] CFinding  a 'TMP/session/' that survived its run.

    A session's sinks are read on 'done' and deleted; the directory
    leaves with the session. One that stands between runs is the
    wreckage of a session that did not finish, and NOTHING READS IT --
    the next run makes its own.
    """
    path = os.path.join(directory, SESSION_DIRECTORY_NAME)
    if not os.path.isdir(path): return
    n = len(os.listdir(path))
    yield CFinding("session", shown(root, path),
                   "a session that did not finish; %d sink file(s), "
                   "read by nobody" % n, size_of(path))


def lock_finding_list(root, directory):
    """
    YIELD: [0] CFinding  a 'TMP/lock/' WHOSE HOLDER IS GONE.

    A LIVE LOCK IS NEVER YIELDED. It is a running test's claim on its
    directory, and breaking it is how two runs come to write one
    store. The liveness is asked through the mutex's OWN predicate --
    the same one 'acquire' uses to decide it may break a lock -- so
    this face and the runner cannot disagree about who is alive.

    WHERE THE PLATFORM CANNOT ANSWER, THE LOCK STAYS. Unknown is not
    dead, and a face that removes on 'I could not tell' is worse than
    one that leaves rubbish.
    """
    path = os.path.join(directory, LOCK_DIRECTORY_NAME)
    if not os.path.isdir(path): return
    mutex  = MkdirMutex(directory)
    holder = mutex.holder()
    if not mutex._holder_is_gone(holder):
        return                                  # live, or unknowable
    age = mutex.holder_age_sec()
    yield CFinding("lock", shown(root, path),
                   "the holder (pid %s) is gone%s"
                   % ((holder or {}).get("pid", "?"),
                      "" if age is None else ", taken %.0f s ago" % age),
                   size_of(path))


def out_finding_list(root, directory):
    """
    YIELD: [0] CFinding  an 'OUT/' directory.

    The application's product space. It is read as subjects DURING a
    run and rewritten by the next one; between runs it is scratch.
    """
    path = os.path.join(directory, OUT_DIRECTORY_NAME)
    if not os.path.isdir(path): return
    n = sum(len(f) for _, _, f in os.walk(path))
    if n == 0: return
    yield CFinding("out", shown(root, path),
                   "the application's product space; %d file(s), "
                   "rewritten by the next run" % n, size_of(path))


def offered_key_set(app_set):
    """
    RETURN: set[(str, str|None)], every (test, choice) the directory's
            configuration OFFERS -- the test keyed as a record is
            (configuration.key_name: the source file WHOLE).

    This is the measure an orphan is judged against, so it is taken
    from EXPLORATION and never from the file system: what the
    framework would run is what the framework should keep.
    """
    result = set()
    for app in app_set:
        for choice in app.choice_db:
            result.add((app.source_file, choice))
    return result


def orphan_finding_list(root, directory, app_set):
    """
    YIELD: [0] CFinding  a record naming a (test, choice) the
                         configuration no longer offers.

    NOMINALS, CANDIDATES AND SIDECARS by their names; BOOK ENTRIES and
    REGISTER IDS by their keys.

    A RECORD IS NEVER AN ORPHAN WHERE EXPLORATION DOES NOT OFFER THE
    APPLICATION AND THE FILE STILL STANDS.

    THE GUARD IS NARROW ON PURPOSE. Where exploration DOES offer the
    application and simply has no such CHOICE, the record is a
    reliable orphan -- the configuration was read, it was understood,
    and it does not name that choice. Only the case where the
    framework cannot see an application AT ALL is unreliable, and only
    that case is spared. It is UNREACHABLE, which is a
    fault in the configuration and not rubbish on the disk -- and this
    tree proves the case: 'regression-1.py' and 'verify_signature.sh'
    are test applications that hwut 1.0 runs and VUT 2.0 does not yet
    see, because their 'hwut-info.dat' is unread (disc-6, r-2).
    Without this guard '--apply' would delete nine blessed nominals to
    tidy a directory.

    THE REASON IS ALWAYS SAID, because this is the aspect that can
    lose an acceptance: a nominal is blessed work, and a file that
    looks like an orphan because a header stopped parsing is not an
    orphan -- it is unreachable, and its test is what wants mending.
    The caller refuses this aspect outright for a directory whose
    exploration raised a fault; see 'directory_finding_list'.
    """
    offered = offered_key_set(app_set)
    if not offered: return              # nothing offered: judge nothing

    known_test_set = set(t for t, _ in offered)

    #  -- the files: GOOD/ and TMP/store/ ------------------------------
    for holder in ("GOOD", STORE_DIRECTORY_NAME):
        base = os.path.join(directory, holder)
        if not os.path.isdir(base): continue
        for name in sorted(os.listdir(base)):
            path = os.path.join(base, name)
            if not os.path.isfile(path):                  continue
            if name in GOOD_OWNED_FILE_TUPLE: continue   # the book's,
                                                        # asked, not listed
            key = record_key_of(name)
            if key is None:                               continue
            test, choice = key
            if test not in known_test_set \
               and os.path.exists(os.path.join(directory, test)):
                #  THE APPLICATION STILL STANDS AND EXPLORATION DOES
                #  NOT OFFER IT. Its record is NOT an
                #  orphan -- it is UNREACHABLE: exploration cannot see
                #  the file (an 'hwut-info.dat' it does not read, an
                #  'ignore' glob, a header that stopped parsing), and
                #  the mending is in the CONFIGURATION, not in the
                #  blessed work. Deleting it here would destroy an
                #  acceptance to tidy a directory.
                continue
            if test not in known_test_set:
                yield CFinding("orphans", shown(root, path),
                               "no application '%s' stands here" % test,
                               size_of(path))
            elif (test, choice) not in offered:
                yield CFinding("orphans", shown(root, path),
                               "'%s' offers no choice '%s'"
                               % (test, choice), size_of(path))

    #  -- the book -------------------------------------------------------
    bookkeeper = Bookkeeper(directory)
    #  THROUGH THE DOOR: what is recorded is 'tests()' and 'choices()';
    #  the book's own shape stays behind it.
    for test in bookkeeper.tests():
        for choice in bookkeeper.choices(test):
            if (test, choice) in offered: continue
            yield CFinding("orphans",
                           "%s: book %s%s"
                           % (shown(root, directory), test,
                              "" if choice is None else " " + choice),
                           "no such case is offered", None)


def record_key_of(name):
    """
    RETURN: (test, choice), the case a record file NAMES --
                'test-x.py--basic.txt'          -> ('test-x.py', 'basic')
                'test-x.py.stdout'              -> ('test-x.py', None)
                'test-x.py--basic.stdout.when'  -> ('test-x.py', 'basic')
            None, where the name is not a record's.

    THE GATE IS THAT THE TEST PART CARRIES A SOURCE EXTENSION. A record
    is keyed by the source file WHOLE (configuration.key_name), so
    'test-x.py' and 'regression-1.py' both qualify and 'notes.md' and
    'book.csv' do not. A PREFIX WOULD BE THE WRONG GATE: this
    tree holds applications named 'regression-1.py' and
    'verify_signature.sh', and a face that judged only 'test-*' would
    pass over their records in silence.

    A FILE IT CANNOT NAME IS SOMEBODY'S -- a note, a fixture, a
    checked-in artefact -- and is never offered for removal.
    """
    #  THE NAMING IS THE BOOKKEEPER'S: it wrote the key, it reads it
    #  back. This face adds only the gate it alone knows -- which
    #  extensions name a source file in this tree.
    parts = key_parts_of(name)
    if parts is None:                    return None   # no subject part
    test, choice, _subject = parts
    _, dot, extension = test.rpartition(".")
    if not dot or extension not in SOURCE_EXTENSION_SET:
        return None
    return test, choice


def transient_finding_list(root, directory):
    """
    YIELD: [0] CFinding  a transient root of the directory, 'OUT/' or
                         'TMP/', whole (E-24).

    Raises DirectoryLive where 'TMP/lock/' names a holder that is
    STILL ALIVE, or whose liveness the platform cannot tell: the
    directory is refused entire -- 'OUT/' included, since the live run
    reads it -- and the caller names it on stderr and walks on.
    """
    lock_path = os.path.join(directory, LOCK_DIRECTORY_NAME)
    if os.path.isdir(lock_path):
        mutex  = MkdirMutex(directory)
        holder = mutex.holder()
        if not mutex._holder_is_gone(holder):
            raise DirectoryLive("%s: 'TMP/lock' names a live holder "
                                "(pid %s); nothing here is touched"
                                % (shown(root, directory),
                                   (holder or {}).get("pid", "?")))
    for name in TRANSIENT_ROOT_TUPLE:
        path = os.path.join(directory, name)
        if not os.path.isdir(path): continue
        n = sum(len(f) for _, _, f in os.walk(path))
        yield CFinding("transient", shown(root, path),
                       "transient root; %d file(s), all of it a run can "
                       "make again" % n, size_of(path))


class DirectoryLive(Exception):
    """A directory whose lock names a live holder: refused whole."""
    pass


def books_finding_list(root, directory):
    """
    YIELD: [0] CFinding  one disagreement between the two records of
                         acceptance -- GOOD/ (the nominals) and
                         'book.csv' (the book, which is also the
                         register, B-13) -- named, and NEVER offered
                         for removal: a disagreement is mended by a
                         person ('hwut.accept', 'hwut.remove'), not by
                         unlink.

    THE TWO MUST AGREE (E-41). A nominal in GOOD/ is THE evidence of
    acceptance; the book's 'last_accept' is written at accept. A test
    in the book with NO nominal is not a disagreement: it is an
    ASPIRANT (B-14), known and not yet accepted, and it says so in its
    verdict. So:

        a nominal whose test the book lacks        -- book behind
        the book says ASPIRANT and a nominal       -- accepted outside
        stands                                        the book: stale
        a book entry with a nominal and no          -- accepted outside
        'last_accept'                                  the book

    A directory with none of them is not judged: nothing was ever
    accepted there, and there is nothing to disagree about.
    """
    good_dir = os.path.join(directory, "GOOD")
    if not os.path.isdir(good_dir): return
    where    = shown(root, directory)
    try:
        register = Bookkeeper(directory)
    except TestIdFault as error:
        yield CFinding("books", "%s: register" % where,
                       "cannot be read -- %s" % error, None)
        return
    nominal_test_set = set()
    for name in sorted(os.listdir(good_dir)):
        if name in GOOD_OWNED_FILE_TUPLE: continue
        key = record_key_of(name)
        if key is not None: nominal_test_set.add(key[0])
    registered_set = set(register.roster())
    for test in sorted(nominal_test_set - registered_set):
        yield CFinding("books", "%s: GOOD/ %s" % (where, test),
                       "a nominal stands, and the book lacks it",
                       None)
    bookkeeper = Bookkeeper(directory)
    for test in bookkeeper.tests():
        for choice in bookkeeper.choices(test):
            entry = bookkeeper.result(test, choice)
            if entry is None: continue
            label = "%s: book %s%s" % (where, test,
                                       "" if choice is None else " " + choice)
            stands_f = nominal_stands_f(directory, test, choice)
            if entry.get("verdict") is E_TestVerdict.ASPIRANT:
                if stands_f:
                    yield CFinding("books", label,
                                   "the book says aspirant, and a nominal "
                                   "stands -- accepted outside the book",
                                   None)
                continue
            if not stands_f or entry.get("last_accept"): continue
            yield CFinding("books", label,
                           "a nominal stands, and 'last_accept' is empty "
                           "-- accepted outside the book", None)


def directory_finding_list(root, directory, result, aspect_set, wanted_f):
    """
    RETURN: [0] list[CFinding], everything the asked-for aspects found
                in that directory.
            [1] list[str], the reasons an aspect was REFUSED here --
                an aspect refused is not an aspect that found nothing.

    'wanted_f' is False where the wish selects nothing in this
    directory: the session, lock and OUT aspects are still asked --
    they are the DIRECTORY'S rubbish, not a case's -- but ORPHANS are
    not, because an orphan is judged against the cases, and a wish
    that hid half of them would call the other half orphaned.
    """
    finding_list = []
    refusal_list = []

    if "session" in aspect_set:
        finding_list.extend(session_finding_list(root, directory))
    if "lock" in aspect_set:
        finding_list.extend(lock_finding_list(root, directory))
    if "out" in aspect_set:
        finding_list.extend(out_finding_list(root, directory))
    if "transient" in aspect_set:
        try:
            finding_list.extend(transient_finding_list(root, directory))
        except DirectoryLive as error:
            #  NAMED ON STDERR, not folded into the report: it is the
            #  one thing here a script must not miss.
            print("REFUSED: %s" % error, file=sys.stderr)
            refusal_list.append(str(error))

    if "books" in aspect_set:
        finding_list.extend(books_finding_list(root, directory))

    if "orphans" in aspect_set:
        if result.fault_list:
            #  A TREE THAT CANNOT BE READ CANNOT BE JUDGED. A header
            #  that stopped parsing makes its own records look
            #  orphaned, and they are not: they are UNREACHABLE, and
            #  the test is what wants mending.
            refusal_list.append(
                "%s: orphans not judged -- exploration reported %d "
                "fault(s), and a directory that cannot be read cannot "
                "say what it offers"
                % (shown(root, directory), len(result.fault_list)))
        elif not wanted_f:
            refusal_list.append(
                "%s: orphans not judged -- the wish hides cases here, "
                "and the hidden ones would look orphaned"
                % shown(root, directory))
        else:
            finding_list.extend(
                orphan_finding_list(root, directory, result.app_set))

    return finding_list, refusal_list


def removed(finding, root, write):
    """
    RETURN: bool, True where the thing named is gone.

    A BOOK ENTRY IS NOT A FILE: a finding whose path names one is
    forgotten through the bookkeeper, which keeps the base well-formed
    -- a JSON file edited by unlink would be a base nobody could read.

    A 'books' FINDING IS NEVER REMOVED: it names a disagreement between
    the nominals, the register and the book, and only a person can say
    which of them is wrong.
    """
    if finding.kind == "books":
        write("    kept: %s -- a disagreement is mended by hand"
              % finding.path)
        return False
    if ": book " in finding.path:
        where, _, rest = finding.path.partition(": book ")
        test, _, choice = rest.partition(" ")
        try:
            Bookkeeper(os.path.join(root, where)).remove_choice(
                test, choice or None)
            return True
        except Exception as error:
            write("    FAULT: %s -- %s" % (finding.path, error))
            return False

    path = os.path.join(root, finding.path)
    try:
        if os.path.isdir(path): shutil.rmtree(path)
        else:                   os.unlink(path)
        return True
    except OSError as error:
        write("    FAULT: %s -- %s" % (finding.path, error))
        return False


def target_line_tuple(root, target_tuple, apply_f, write):
    """
    RETURN: [0] bool, True where every target ran and none failed.
            [1] bool, True where some directory bound each target.

    THE FRAMEWORK DOES NOT KNOW WHAT A PROJECT'S RUBBISH IS. The
    project does, and 'hwut.target' (E-7) is where it says so. So this
    face does not clean a project's own leavings; it CALLS the verb
    the project bound, in every directory that bound it, in walk order.

    A TARGET NO DIRECTORY BINDS IS REFUSED BY NAME. A misspelt 'clen'
    that quietly does nothing is worse than one that stops: the author
    believes their tree was cleaned.
    """
    from . import target as target_service

    good_f  = True
    bound_f = True
    for name in target_tuple:
        argv = ["--directory=%s" % root, name]
        if not apply_f:
            write("  target '%s': would run in every directory that "
                  "binds it ('--apply' runs it)" % name)
            continue
        write("  target '%s':" % name)
        code = target_service.main(argv, write=lambda line:
                                   write("    " + str(line)))
        if code is E_ExitCode.EMPTY:
            write("    REFUSED: no directory binds a target '%s'" % name)
            bound_f = False
        elif code is not E_ExitCode.OK:
            good_f = False
    return good_f, bound_f


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (E-1): OK where the walk
            finished, FAULT where something could not be removed or a
            target failed, REFUSED where the command line cannot be
            read or names a target no directory binds, EMPTY where the
            wish selects nothing.

    A BARE COMMAND LINE REPORTS AND DOES NOT ACT. The answers here are
    irreversible -- a GOOD file is an author's blessed work -- so the
    default is the safe one and '--apply' is the whole difference.
    """
    if write is None: write = print
    if argv is None:  argv  = sys.argv[1:]
    if "--help" in argv:
        write(HELP)
        return E_ExitCode.OK

    try:
        wish, rest_list = parse_wish(argv)
    except WishError as error:
        write("REFUSED: %s" % error)
        write(USAGE)
        return E_ExitCode.REFUSED

    #  '--target' WITHOUT A NAME is refused in this face's words, before
    #  the parser would say it in its own.
    if rest_list and rest_list[-1] == "--target":
        write("REFUSED: '--target' stands without a name")
        write(USAGE)
        return E_ExitCode.REFUSED
    arguments, completion_f = parse_or_refuse(PARSER, rest_list, write,
                                              ARG_DB)
    if completion_f:      return E_ExitCode.OK
    if arguments is None:
        write(USAGE)
        return E_ExitCode.REFUSED
    directory   = arguments.directory or "."
    apply_f     = arguments.apply
    target_list = list(arguments.target)
    aspect_set  = {aspect for aspect in ASPECT_TUPLE + EXPLICIT_ASPECT_TUPLE
                   if getattr(arguments, aspect)}
    if not os.path.isdir(directory):
        write("REFUSED: the directory '%s' does not exist" % directory)
        write(USAGE)
        return E_ExitCode.REFUSED

    #  NONE STATED MEANS ALL OF THEM -- a wish that states nothing
    #  wants everything. The TARGETS are never implied: running
    #  somebody's script is an act nobody asked for.
    if not aspect_set: aspect_set = set(ASPECT_TUPLE)
    #  '--transient' TAKES THE OTHER ASPECTS WITH IT: a session, a stale
    #  lock, an 'OUT/' are all inside what it removes, and reporting
    #  them twice would count one directory's rubbish twice.
    if "transient" in aspect_set:
        aspect_set -= {"session", "lock", "out"}

    root = os.path.abspath(directory)
    try:
        exploration = explore_tree(root)
    except RootConfMissing as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED

    finding_list = []
    refusal_list = []
    app_path_list = []
    for where, result in exploration:
        whole = os.path.join(root, where)
        try:
            query = CTestTaskListQuery(wish, Bookkeeper(whole),
                                       directory=where, root=root)
            wanted_f = bool(query.get_test_cases(result.app_set))
        except SelectionError:
            wanted_f = False
        found, refused = directory_finding_list(root, whole, result,
                                                aspect_set, wanted_f)
        finding_list.extend(found)
        refusal_list.extend(refused)
        app_path_list.extend(os.path.join(whole, app.source_file)
                             for app in result.app_set)

    #  -- the report ------------------------------------------------------
    write("SANITIZE, in '%s': %s%s"
          % (directory, ", ".join(sorted(aspect_set)),
             "" if apply_f else "  (reporting only; '--apply' acts)"))
    write("")
    for reason in refusal_list: write("  NOTE: %s" % reason)
    if refusal_list: write("")

    total_bytes = 0
    for kind in ASPECT_TUPLE + EXPLICIT_ASPECT_TUPLE:
        of_kind = [f for f in finding_list if f.kind == kind]
        if not of_kind: continue
        write("  %s -- %d found:" % (kind, len(of_kind)))
        for finding in of_kind:
            total_bytes += finding.bytes or 0
            write("      %-52s %s" % (finding.path, finding.why))
        write("")

    if not finding_list:
        write("  nothing to sanitize")
    elif total_bytes:
        write("  %d item(s), %.1f kB" % (len(finding_list),
                                         total_bytes / 1024.0))

    good_f  = True
    bound_f = True
    if finding_list and apply_f:
        write("")
        write("REMOVING:")
        for finding in finding_list:
            if removed(finding, root, write):
                write("    gone: %s" % finding.path)
            elif finding.kind != "books":
                #  A 'books' finding is KEPT by design, and said so
                #  ('removed'); a kept disagreement is no fault of
                #  the removal.
                good_f = False

    #  THE RE-RUN TRIGGER (ruled 2026-09-05). A sanitize that ACTS has
    #  changed what the tree's recordings rest on; every recording is
    #  then suspect, and the channel's freshness is a comparison of
    #  modification times. So every test application is TOUCHED:
    #  younger than every recording, every refreshing face runs it
    #  next time it is asked, and no recording that predates this
    #  sanitize is presented as current.
    if apply_f and app_path_list:
        write("")
        write("TOUCHED (the re-run trigger): %d test application(s)"
              % len(app_path_list))
        for path in app_path_list:
            try:                os.utime(path, None)
            except OSError as error:
                write("    could not touch %s: %s" % (shown(root, path), error))
                good_f = False

    if target_list:
        write("")
        write("TARGETS:")
        target_good_f, bound_f = target_line_tuple(root, tuple(target_list),
                                                   apply_f, write)
        if not target_good_f: good_f = False

    if not bound_f:            return E_ExitCode.REFUSED
    if not good_f:             return E_ExitCode.FAULT
    return E_ExitCode.OK


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ._exit import guarded
    sys.exit(guarded("hwut.sanitize", main))
