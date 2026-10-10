"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.sanitize' COMMAND LINE -- one sanitize command, done.

    hwut.sanitize <command> <concerned entity> [--directory=<path>]

THE COMMANDS ARE THE LINES OF A PROPOSAL (services E-125). What
'hwut.sanitize.propose' writes, line by line, this face does one at a
time, and 'hwut.sanitize.apply <file>' does for every line a file
still holds. The verb names the ACT; the entity names what it acts on,
relative to '--directory' (the current directory where none is given):

    remove <dir>/TMP/session     a session's wreckage
    remove <dir>/TMP/lock        a lock whose holder is gone
    remove <dir>/OUT             the application's product space
    remove <dir>/TMP             the transient root whole (E-24)
    forget <dir>/<test> [<choice>]
                                 an ORPHAN: every record of a case the
                                 configuration no longer offers --
                                 nominals, candidates, book entry,
                                 register id -- through 'hwut.remove'
    move   <dir>/<test> <new-dir>
                                 an orphan whose application stands in
                                 <new-dir> now, with nothing recorded of
                                 it there: its records carried after it,
                                 through 'hwut.move' (E-131)
    book   <dir>/<test> [<choice>]
                                 a nominal stands and the book
                                 disagrees: the standing nominal is
                                 entered as accepted; nothing runs,
                                 nothing in GOOD/ moves
    remark <dir>/<test> [<choice>]
                                 a nominal breaks its own constraints
                                 (E-123): the findings are written into
                                 it where they were made, and the book
                                 is stained 'constraint'
    run    <dir> <target>        the project's own verb (E-7), through
                                 'hwut.execute', in <dir> and below
    relate <dir>                 the statement file of <dir> --
                                 'hwut-composition.conf', or the
                                 'hwut-features.conf' of a TEST
                                 directory -- disagrees with where the
                                 directory stands: it is ADAPTED. An
                                 'id' where it gives itself none (the
                                 directory's name); 'parent' set to the
                                 id of the directory above; its id
                                 entered in the 'childs' above -- CARRIED
                                 there, sentence and all, from the
                                 'childs' that still lists it where the
                                 directory was MOVED
    unrelate <dir> <id>          'childs' of <dir> lists an id nothing
                                 below it carries: the entry is removed
    root   [<dir>]               no 'hwut-root.conf' stands in or above
                                 <dir>: the file is written there, with
                                 its 'language-setup' table (E-25).
                                 WITH NO <dir> IT ASKS: a menu of the
                                 repository roots at or above (git,
                                 mercurial, svn, jujutsu, bazaar, darcs,
                                 pijul, fossil), the current directory,
                                 and 'q' to quit

EVERY COMMAND JUDGES AGAIN BEFORE IT ACTS. The entity says WHAT; the
tree at this moment says WHETHER. A command whose entity sanitize would
not propose now is REFUSED, by name and reason: a lock whose holder
lives, a record whose case is offered, an application that stands and
cannot be explored (UNREACHABLE, not orphaned), a directory whose
exploration faults, a disagreement that is no longer one. A thing that
no longer stands at all is NOTHING TO DO, not a fault. What 'remove'
takes is decided by the path: a path that is none of the four is
refused -- this face is not 'rm'.

THE RE-RUN TRIGGER (ruled 2026-09-05). A command that ACTED has changed
what the recordings of its directory rest on, so every test application
there is TOUCHED: younger than every recording, every refreshing face
runs it next time it is asked. 'run' touches every directory below its
own.

EXIT STATUS (E-1, services/_exit.py):
    0  done, or nothing to do
    1  the command was refused by the tree, or failed while acting
    2  the command line cannot be read
______________________________________________________________________________
"""
import os
import sys
from   dataclasses import dataclass, field

from   vut.auxiliary.directory_mutex                 import (MkdirMutex,
                                                             LOCK_DIRECTORY_NAME)
from   vut.engine.bookkeeper.api              import (Bookkeeper, STORE_DIRECTORY_NAME,
                                                             GOOD_OWNED_FILE_TUPLE,
                                                             E_TestVerdict,
                                                             TestIdFault,
                                                             key_parts_of,
                                                             nominal_stands_f)
from   vut.engine.operations.run.multi_execute import SESSION_DIRECTORY_NAME
from   ._exit import E_ExitCode

#  A record's TEST PART ends in one of these: it is the source file
#  whole. The set is the languages a test application is written in;
#  a language absent here is one whose records this face passes over,
#  which is the safe way to be wrong.
SOURCE_EXTENSION_SET   = frozenset((
    "py", "sh", "bash", "lua", "pl", "rb", "c", "cpp", "cc", "bas",
    "exe", "bat", "ps1", "js", "ts", "vhd", "v", "sv"))

#  THE TWO GROUNDS' NAMES ARE 'auxiliary/no_entry.py's, referred to.
from   vut.auxiliary.no_entry import (OUT_DIRECTORY_NAME,       # noqa: E402,F401
                                      TRANSIENT_DIRECTORY_NAME,
                                      OWN_GROUND_NAME_TUPLE)
TRANSIENT_ROOT_TUPLE   = OWN_GROUND_NAME_TUPLE    # services E-24

#  What a bare proposal asks about. Not the targets: running somebody's
#  script is never implied.
ASPECT_TUPLE = ("session", "lock", "out", "orphans", "books", "constraints",
                "relations")
#  Asked for by name only; a bare proposal never takes the candidates.
EXPLICIT_ASPECT_TUPLE = ("transient",)


@dataclass(frozen=True)
class CIssueKind:
    """ONE KIND OF INSANITY: its name, the command that heals it, and
    the comment a proposal writes above its block -- the problem, then
    what the command heals."""
    name:         str
    verb:         str
    comment_list: tuple


#  THE KINDS, IN THE ORDER A PROPOSAL WRITES THEIR BLOCKS. One kind, one
#  block, one comment (E-125): issues of a kind stand in adjacent lines.
ISSUE_KIND_TUPLE = (
    CIssueKind("session", "remove", (
        "SESSION WRECKAGE: a 'TMP/session/' outlived its run; nothing reads",
        "it between runs, and the next run makes its own.",
        "'remove' deletes the directory.")),
    CIssueKind("lock", "remove", (
        "DEAD LOCK: a 'TMP/lock/' whose holder is gone, or which cannot",
        "name its holder; honoured, it blocks the directory for ever.",
        "'remove' deletes it. A holder alive by then is refused.")),
    CIssueKind("out", "remove", (
        "PRODUCT SPACE: 'OUT/' is the application's scratch, rewritten by",
        "the next run that uses it.",
        "'remove' deletes it. A directory a live run holds is refused.")),
    CIssueKind("transient", "remove", (
        "TRANSIENT ROOT: 'OUT/' or 'TMP/' whole, the candidates with them",
        "-- all of it a run can make again (E-24).",
        "'remove' deletes it. A directory a live run holds is refused.")),
    CIssueKind("orphan-moved", "move", (
        "ORPHAN, APPLICATION MOVED: records name a test application that",
        "stands in ANOTHER directory now, where nothing is recorded of it.",
        "'move' carries every record after it -- nominals, candidates, book",
        "entry -- through 'hwut.move'; nothing is lost. To drop the records",
        "instead, write 'forget <dir>/<test>'.")),
    CIssueKind("orphan-test", "forget", (
        "ORPHAN, APPLICATION GONE: records name a test application that no",
        "longer stands in its directory. Where it stands elsewhere and is",
        "RECORDED there already, or stands in several places, the line",
        "says so.",
        "'forget' drops every record of the test: nominals, candidates,",
        "book entry, register id.")),
    CIssueKind("orphan-choice", "forget", (
        "ORPHAN, CHOICE NOT OFFERED: the application stands and is",
        "understood, and does not name that choice.",
        "'forget' drops every record of the choice: nominals, candidates,",
        "book entry, register id.")),
    CIssueKind("book-lacks", "book", (
        "BOOK BEHIND: a nominal stands in GOOD/, and the book has no entry",
        "for the case (E-41).",
        "'book' enters the standing nominal as accepted; nothing runs,",
        "nothing in GOOD/ moves.")),
    CIssueKind("book-aspirant", "book", (
        "BOOK STALE: the book says aspirant, and a nominal stands -- it was",
        "accepted outside the book (B-14).",
        "'book' enters the standing nominal as accepted; nothing runs,",
        "nothing in GOOD/ moves.")),
    CIssueKind("constraint", "remark", (
        "CONSTRAINT BROKEN: a nominal held against itself breaks its",
        "constraints, or never binds a variable they name (E-123).",
        "'remark' writes each finding into the nominal after the line that",
        "caused it -- a variable never bound at the head -- and stains the",
        "book 'constraint'. Nothing is removed; mend the nominal.")),
    CIssueKind("relation-id", "relate", (
        "NO ID: a 'hwut-composition.conf' or 'hwut-features.conf' gives",
        "itself no 'id'; nothing can name it as parent or child.",
        "'relate' writes 'id = \"<the directory's name>\"' -- rename it",
        "afterwards, here and where it is listed -- and relates it to the",
        "directory above.")),
    CIssueKind("relation-moved", "relate", (
        "DETECTED MOVE: a directory stands below one component, and its",
        "statement file and the 'childs' it came from still say another.",
        "'relate' sets 'parent' to the id of the directory above and",
        "carries the 'childs' entry, with its sentence, from the old",
        "parent's file to the new one's.")),
    CIssueKind("relation-parent", "relate", (
        "PARENT AND CHILDS DISAGREE WITH THE DIRECTORIES: 'parent' is not",
        "the id of the directory above, or the directory above does not",
        "list the id in its 'childs'.",
        "'relate' sets 'parent', and enters the id in the 'childs' above",
        "with an EMPTY sentence -- write it.")),
    CIssueKind("relation-gone", "unrelate", (
        "CHILD GONE: 'childs' lists an id that nothing directly below",
        "carries, and that no moved directory took with it.",
        "'unrelate' removes the entry, its sentence with it.")),
    CIssueKind("target", "run", (
        "TARGET: the project's own verb, asked for by '--target' (E-7).",
        "'run' calls it through 'hwut.execute' in the directory and every",
        "directory below that binds it.")),
    CIssueKind("root", "root", (
        "NO BOUNDARY: no 'hwut-root.conf' stands in or above this directory.",
        "A tree needs one: it is the root every path is relative to, and",
        "the place 'hwut-root.labels' stands (E-25).",
        "'root' writes the file, with its 'language-setup' table, into the",
        "directory named. ONE line stands; to place it elsewhere, comment",
        "that line and uncomment another -- or name any directory.")),
)
ISSUE_KIND_DB = {kind.name: kind for kind in ISSUE_KIND_TUPLE}

#  The verbs, each once, in the order their first kind stands.
VERB_TUPLE = tuple(dict.fromkeys(kind.verb for kind in ISSUE_KIND_TUPLE))


@dataclass(frozen=True)
class CIssue:
    """
    ONE INSANITY FOUND: its kind, the directory it stands in (absolute),
    and the words that name it there -- ('TMP/session',) for a path,
    (test,) or (test, choice) for a case, (target,) for a target.
    'payload' is what the healing needs and the naming does not -- the
    placed remarks of a 'constraint' -- and takes no part in equality.
    'note' is what a reader of the proposal should know about this ONE
    line -- "possibly moved to ..." -- written after it as '# <note>'
    and ignored by every reader of commands (E-130).
    """
    kind:      str
    directory: str
    word_tuple: tuple
    payload:   object = field(default=None, compare=False)
    note:      object = field(default=None, compare=False)
    #  AN ALTERNATIVE, NOT THE PROPOSAL: written with '#' before it, so
    #  it is not done unless the reader uncomments it (the 'root'
    #  candidates).
    commented_f: bool = field(default=False, compare=False)

    def verb(self):
        """RETURN: str, the command that heals this issue."""
        return ISSUE_KIND_DB[self.kind].verb

    def entity(self, base):
        """
        RETURN: str, the concerned entity as a command line spells it,
                relative to 'base':
                    remove  <dir>/TMP/session
                    forget  <dir>/<test> [<choice>]
                    move    <dir>/<test> <new-dir>
                    run     <dir> <target>
                    relate  <dir>
                    unrelate <dir> <id>
                    root    <dir>
        """
        where = shown(base, self.directory).replace(os.sep, "/")
        if self.verb() in ("root", "relate"):
            return where
        if self.verb() in ("run", "unrelate"):
            return "%s %s" % (where, self.word_tuple[0])
        if self.verb() == "move":
            head = self.word_tuple[0] if where == "." \
                   else "%s/%s" % (where, self.word_tuple[0])
            return "%s %s" % (head, shown(base, self.word_tuple[1])
                                    .replace(os.sep, "/"))
        head = self.word_tuple[0] if where == "." \
               else "%s/%s" % (where, self.word_tuple[0])
        return " ".join((head,) + tuple(self.word_tuple[1:]))

    def line(self, base):
        """RETURN: str, the proposal's line: '<command> <entity>', and
                   '  # <note>' after it where the issue carries one."""
        text = "%s %s" % (self.verb(), self.entity(base))
        if self.note: text += "  # %s" % self.note
        if self.commented_f: text = "# " + text
        return text


def root_issue_list(directory):
    """
    RETURN: list[CIssue], one 'root' issue per place a boundary is
            offered at ('_boundary.candidate_list'): the repository
            roots at or above 'directory', then 'directory' itself.
            THE FIRST THAT CAN BE WRITTEN IN is the proposal; the
            others are COMMENTED alternatives, and one that cannot be
            written in says so.
    """
    from vut.services._boundary import candidate_list, writeable_f
    candidate = candidate_list(directory)
    chosen    = next((path for path, _ in candidate if writeable_f(path)),
                     None)
    return [CIssue("root", path, (),
                   note=what if writeable_f(path)
                        else "%s; no write access" % what,
                   commented_f=(path != chosen))
            for path, what in candidate]


def root_asked(directory, write, ask):
    """
    RETURN: str, the directory the person chose for the boundary, as
                 the command 'root <dir>' takes it -- relative to
                 'directory'
            None, where they quit: nothing is to be written

    THE MENU OF 'hwut.sanitize root' WITH NO DIRECTORY (ruled
    2026-10-08): the repository roots at or above, the current
    directory, and 'q'. It speaks the checklist's idiom: a number in
    brackets picks, the prompt is '> ', an answer that picks nothing is
    said and asked again. 'ask' reads one answer after a prompt and
    raises EOFError where nobody can answer -- which quits.
    """
    from vut.services._boundary import (candidate_list, writeable_f,
                                        ROOT_CONF_NAME)
    candidate = candidate_list(directory)
    write("no '%s' stands in or above '%s'. Where shall it go?"
          % (ROOT_CONF_NAME, directory))
    width = max(len(shown(directory, path)) for path, _ in candidate)
    for n, (path, what) in enumerate(candidate, 1):
        write("  [%d]  %-*s  %s%s"
              % (n, width, shown(directory, path), what,
                 "" if writeable_f(path) else " -- no write access"))
    write("  [q]  quit -- nothing is written")
    allowed = [str(n) for n in range(1, len(candidate) + 1)] + ["q"]
    while True:
        try:
            answer = ask("> ").strip()
        except (EOFError, KeyboardInterrupt):
            write("")
            return None
        if answer in allowed: break
        write("  (not one of %s: '%s')"
              % (", ".join("[%s]" % a for a in allowed), answer))
    if answer == "q": return None
    return shown(directory, candidate[int(answer) - 1][0])


class DirectoryLive(Exception):
    """A directory whose lock names a live holder: refused whole."""
    pass


def shown(root, path):
    """RETURN: str, the path as it reads from the run's root."""
    try:               return os.path.relpath(path, root)
    except ValueError: return path


def live_holder_of(directory):
    """
    RETURN: dict, the holder 'TMP/lock/' names, where it is STILL ALIVE
                  or its liveness cannot be told -- unknown is not dead.
            None, where no lock stands or its holder is gone.

    The liveness is asked through the mutex's OWN predicate -- the same
    one 'acquire' uses to decide it may break a lock -- so this face and
    the runner cannot disagree about who is alive.
    """
    if not os.path.isdir(os.path.join(directory, LOCK_DIRECTORY_NAME)):
        return None
    mutex  = MkdirMutex(directory)
    holder = mutex.holder()
    if mutex._holder_is_gone(holder): return None
    return holder or {}


def refuse_live(root, directory):
    """RETURN: None. Raises DirectoryLive where a live run holds
               'directory': nothing there is touched."""
    holder = live_holder_of(directory)
    if holder is None: return
    raise DirectoryLive("%s: 'TMP/lock' names a live holder (pid %s); "
                        "nothing here is touched"
                        % (shown(root, directory), holder.get("pid", "?")))


def file_n_of(path):
    """RETURN: int, the files below 'path'."""
    return sum(len(f) for _, _, f in os.walk(path))


# -- THE JUDGEMENT: one function per aspect --------------------------------
def session_issue_list(directory):
    """
    RETURN: list[CIssue], the 'TMP/session/' that survived its run -- or
            none.

    A session's sinks are read on 'done' and deleted; the directory
    leaves with the session. One that stands between runs is the
    wreckage of a session that did not finish, and NOTHING READS IT --
    the next run makes its own.
    """
    if not os.path.isdir(os.path.join(directory, SESSION_DIRECTORY_NAME)):
        return []
    return [CIssue("session", directory, (SESSION_DIRECTORY_NAME,))]


def lock_issue_list(directory):
    """
    RETURN: list[CIssue], a 'TMP/lock/' WHOSE HOLDER IS GONE -- or none.

    A LIVE LOCK IS NEVER NAMED. It is a running test's claim on its
    directory, and breaking it is how two runs come to write one
    store. WHERE THE PLATFORM CANNOT ANSWER, THE LOCK STAYS: unknown is
    not dead, and a face that removes on 'I could not tell' is worse
    than one that leaves rubbish. A claim that cannot name its claimant
    at all is gone: honoured, it would block the directory for ever.
    """
    if not os.path.isdir(os.path.join(directory, LOCK_DIRECTORY_NAME)):
        return []
    if live_holder_of(directory) is not None: return []
    return [CIssue("lock", directory, (LOCK_DIRECTORY_NAME,))]


def out_issue_list(root, directory):
    """
    RETURN: list[CIssue], an 'OUT/' that holds files -- or none.

    Raises DirectoryLive where a live run holds the directory: it reads
    'OUT/' as its subjects DURING the run. Between runs it is scratch.
    """
    path = os.path.join(directory, OUT_DIRECTORY_NAME)
    if not os.path.isdir(path) or file_n_of(path) == 0: return []
    refuse_live(root, directory)
    return [CIssue("out", directory, (OUT_DIRECTORY_NAME,))]


def transient_issue_list(root, directory):
    """
    RETURN: list[CIssue], each transient root of the directory, 'OUT/'
            and 'TMP/', whole (E-24).

    Raises DirectoryLive where 'TMP/lock/' names a holder that is STILL
    ALIVE, or whose liveness cannot be told: the directory is refused
    entire -- 'OUT/' included, since the live run reads it.
    """
    refuse_live(root, directory)
    return [CIssue("transient", directory, (name,))
            for name in TRANSIENT_ROOT_TUPLE
            if os.path.isdir(os.path.join(directory, name))]


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


def orphan_issue_list(directory, app_set):
    """
    RETURN: [0] list[CIssue], every case recorded here -- by a nominal
                under 'GOOD/', a candidate under 'TMP/store/', or an
                entry in the book -- that the configuration no longer
                offers: 'orphan-test' (test,) where the application is
                gone, once per test; 'orphan-choice' (test, choice)
                where the application stands and names no such choice.
            [1] list[str], the cases found and NOT proposed, with why.

    A RECORD IS NEVER AN ORPHAN WHERE EXPLORATION DOES NOT OFFER THE
    APPLICATION AND THE FILE STILL STANDS. Only the case where the
    framework cannot see an application AT ALL is spared: it is
    UNREACHABLE, which is a fault in the configuration and not rubbish
    on the disk. Where exploration DOES offer the application and has
    no such CHOICE, the record is a reliable orphan -- the configuration
    was read, it was understood, and it does not name that choice.

    A CHOICE-LESS RECORD OF A TEST THAT STANDS cannot be named: 'forget
    <test>' is the whole test, and would take the offered choices with
    it. It is said, not proposed.

    The caller refuses this aspect outright for a directory whose
    exploration raised a fault: a tree that cannot be read cannot be
    judged.
    """
    offered = offered_key_set(app_set)
    if not offered: return [], []       # nothing offered: judge nothing
    known_test_set = set(t for t, _ in offered)

    case_set = set()
    for holder in ("GOOD", STORE_DIRECTORY_NAME):
        base = os.path.join(directory, holder)
        if not os.path.isdir(base): continue
        for name in sorted(os.listdir(base)):
            if name in GOOD_OWNED_FILE_TUPLE: continue    # the book's
            if not os.path.isfile(os.path.join(base, name)): continue
            key = record_key_of(name)
            if key is not None: case_set.add(key)
    bookkeeper = Bookkeeper(directory)
    #  THROUGH THE DOOR: what is recorded is 'tests()' and 'choices()';
    #  the book's own shape stays behind it.
    for test in bookkeeper.tests():
        for choice in bookkeeper.choices(test):
            case_set.add((test, choice))

    issue_db  = {}
    note_list = []
    for test, choice in sorted(case_set, key=lambda k: (k[0], k[1] or "")):
        if (test, choice) in offered: continue
        if test not in known_test_set:
            #  THE APPLICATION STILL STANDS AND EXPLORATION DOES NOT
            #  OFFER IT: unreachable. Deleting its records would destroy
            #  an acceptance to tidy a directory.
            if os.path.exists(os.path.join(directory, test)): continue
            issue_db.setdefault((test,), CIssue("orphan-test", directory,
                                                (test,)))
        elif choice is None:
            note_list.append("%s: the choice-less records of '%s' name no "
                             "offered case; forgetting '%s' alone would "
                             "take the whole test -- not proposed"
                             % (directory, test, test))
        else:
            issue_db[(test, choice)] = CIssue("orphan-choice", directory,
                                              (test, choice))
    return [issue_db[k] for k in sorted(issue_db)], note_list


def recorded_f(directory, test):
    """
    RETURN: bool, whether anything is recorded of 'test' in that test
            directory -- a nominal of any choice in GOOD/, or a row in
            'GOOD/book.csv'.
    """
    good = os.path.join(directory, "GOOD")
    if os.path.isdir(good) and any(
            record_key_of(name) is not None
            and record_key_of(name)[0] == test
            for name in os.listdir(good)
            if name not in GOOD_OWNED_FILE_TUPLE):
        return True
    try:
        return test in Bookkeeper(directory).book()
    except TestIdFault:
        return True


def moved_issue_of(issue, home_list, root):
    """
    RETURN: CIssue, what to propose for an orphan whose application is
            gone from its directory, given 'home_list' -- the OTHER test
            directories (absolute) an application of that name stands
            in, named in a note as they read from 'root':

                none                     the issue as it is: 'forget'
                ONE, nothing recorded    'orphan-moved': 'move' the
                there                    records after the application
                ONE or more, recorded    'forget', noted 'recorded anew
                there                    in <dir>': the move was an add
                                         and a remove, and the add is done
                several, else            'forget', noted 'possibly moved
                                         to <dir>, ...': which, nobody
                                         can know

    A MOVE IS AN ADD PLUS A REMOVE (E-131): where the other side already
    holds its own records, only the remove is left.
    """
    if not home_list: return issue
    test = issue.word_tuple[0]
    recorded_list = [d for d in home_list if recorded_f(d, test)]
    if len(home_list) == 1 and not recorded_list:
        return CIssue("orphan-moved", issue.directory, (test, home_list[0]))
    if recorded_list:
        note = "recorded anew in %s" % ", ".join(
                   shown(root, d).replace(os.sep, "/") for d in recorded_list)
    else:
        note = "possibly moved to %s" % ", ".join(
                   shown(root, d).replace(os.sep, "/") for d in home_list)
    return CIssue(issue.kind, issue.directory, issue.word_tuple,
                  payload=issue.payload, note=note)


def relation_issue_list(root, relation):
    """
    RETURN: [0] list[CIssue], one 'relate' per directory whose statement
                file disagrees with where it stands -- noted 'moved
                from <dir>' where the move was detected -- and one
                'unrelate' per 'childs' entry nothing carries; parents
                before their childs.
            [1] list[str], what is found and NOT proposed: two childs
                of one parent carrying one id, and a directory that
                cannot be related because the directory above gives
                itself no id.

    'relation' is the feature relation of the tree below 'root'
    ('feature_relation.relation_of_exploration').
    """
    from vut.engine.orchestrator.exploration import feature_relation as fr
    kind_db   = {fr.MOVED: "relation-moved", fr.NO_ID: "relation-id",
                 fr.PARENT: "relation-parent", fr.UNLISTED: "relation-parent"}
    rank_list = [fr.MOVED, fr.NO_ID, fr.PARENT, fr.UNLISTED]
    issue_list, note_list, chosen_db = [], [], {}
    for mismatch in fr.mismatch_list(relation):
        directory = os.path.normpath(os.path.join(root, mismatch.path))
        if mismatch.kind == fr.TWIN:
            note_list.append("%s: two childs carry the id '%s' -- rename one"
                             % (mismatch.path, mismatch.id))
        elif mismatch.kind == fr.UNJUDGED:
            note_list.append("%s: not related -- the directory above gives "
                             "itself no id" % mismatch.path)
        elif mismatch.kind == fr.GONE:
            issue_list.append(CIssue("relation-gone", directory,
                                     (mismatch.id,)))
        else:
            standing = chosen_db.get(directory)
            if standing is not None and rank_list.index(standing.kind) \
                                        <= rank_list.index(mismatch.kind):
                continue
            chosen_db[directory] = mismatch
    relate_list = []
    for directory, mismatch in chosen_db.items():
        note = None if mismatch.from_path is None \
               else "moved from %s" % mismatch.from_path
        relate_list.append(CIssue(kind_db[mismatch.kind], directory, (),
                                  note=note))
    return relate_list + issue_list, note_list


def books_issue_list(directory, app_set):
    """
    RETURN: [0] list[CIssue], every OFFERED case where the two records of
                acceptance disagree -- GOOD/ (the nominals) and the book
                (which is also the register, B-13) -- each healed by
                'book':
                    'book-lacks'     a nominal stands; the book has no
                                     entry for the case
                    'book-aspirant'  the book says ASPIRANT; a nominal
                                     stands
            [1] list[str], what could not be judged: a register that
                cannot be read.

    THE TWO MUST AGREE (E-41). A nominal in GOOD/ is THE evidence of
    acceptance; the book's row is written at accept. A case in
    the book with NO nominal is not a disagreement: it is an ASPIRANT
    (B-14), known and not yet accepted, and it says so in its verdict.

    ONLY WHAT THE CONFIGURATION OFFERS IS JUDGED. The nominal of a case
    no longer offered is an orphan's ('forget'), and booking it would
    heal the record of a test that does not exist.
    """
    if not os.path.isdir(os.path.join(directory, "GOOD")): return [], []
    try:
        bookkeeper = Bookkeeper(directory)
        bookkeeper.roster()
    except TestIdFault as error:
        return [], ["%s: the register cannot be read -- %s"
                    % (directory, error)]
    result = []
    for test, choice in sorted(offered_key_set(app_set),
                               key=lambda k: (k[0], k[1] or "")):
        if not nominal_stands_f(directory, test, choice): continue
        words = (test,) if choice is None else (test, choice)
        entry = bookkeeper.result(test, choice)
        if entry is None:
            result.append(CIssue("book-lacks", directory, words))
        elif entry.get("verdict") is E_TestVerdict.ASPIRANT:
            result.append(CIssue("book-aspirant", directory, words))
    return result, []


def constraint_issue_list(directory, result):
    """
    RETURN: list[CIssue], one per standing stdout nominal that, held
            against itself under its choice's constraints (E-123),
            breaks them -- 'payload' the (line_n, remark) of every
            finding NOT yet written into it. Found, never run.

    A finding already written into the nominal where it was found is not
    named again; a nominal whose findings are all written is not named.
    """
    from vut.engine.orchestrator.run.adapter import test_configuration_of
    from vut.services.lib.accept.constraint import own_finding_list
    language_setup = result.app_set.directory_spec.language_setup
    bookkeeper     = Bookkeeper(directory)
    issue_list     = []
    for name in sorted(result.app_set.app_db):
        app = result.app_set.app_db[name]
        try:
            configuration = test_configuration_of(app, directory,
                                                  language_setup=language_setup)
        except Exception:                                  # noqa: BLE001
            continue
        for choice in sorted(app.choice_db, key=lambda c: c or ""):
            try:
                setup = configuration.choice_configuration(choice).compare
            except (KeyError, AttributeError):
                continue
            if setup is None or not setup.constraint_db: continue
            path = bookkeeper.nominal_path(name, choice, "stdout")
            if not path.exists(): continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            present     = set(line.strip() for line in text.splitlines())
            placed_list = []
            for finding in own_finding_list(setup, text):
                if isinstance(finding, str): continue  # does not compile
                #  ALREADY WRITTEN where it was found: nothing to sanitize.
                if "## %s" % finding.remark() in present: continue
                placed_list.append((finding.line_n, finding.remark()))
            if not placed_list: continue
            issue_list.append(CIssue("constraint", directory,
                                     (name,) if choice is None
                                     else (name, choice),
                                     payload=tuple(placed_list)))
    return issue_list


def directory_issue_list(root, directory, result, aspect_set, wanted_f):
    """
    RETURN: [0] list[CIssue], everything the asked-for aspects found in
                that directory.
            [1] list[str], the reasons an aspect was REFUSED here, or a
                case was found and not proposed -- an aspect refused is
                not an aspect that found nothing.

    'wanted_f' is False where the wish selects nothing in this
    directory: the session, lock and OUT aspects are still asked --
    they are the DIRECTORY'S rubbish, not a case's -- but ORPHANS are
    not, because an orphan is judged against the cases, and a wish
    that hid half of them would call the other half orphaned.
    """
    issue_list = []
    note_list  = []
    where      = shown(root, directory)

    if "session" in aspect_set:
        issue_list.extend(session_issue_list(directory))
    if "lock" in aspect_set:
        issue_list.extend(lock_issue_list(directory))
    for aspect, judge in (("out", out_issue_list),
                          ("transient", transient_issue_list)):
        if aspect not in aspect_set: continue
        try:
            issue_list.extend(judge(root, directory))
        except DirectoryLive as error:
            note_list.append(str(error))

    if "books" in aspect_set and not result.fault_list:
        found, refused = books_issue_list(directory, result.app_set)
        issue_list.extend(found)
        note_list.extend(r.replace(directory, where, 1) for r in refused)
    if "constraints" in aspect_set and not result.fault_list:
        issue_list.extend(constraint_issue_list(directory, result))

    if "orphans" in aspect_set:
        if result.fault_list:
            #  A TREE THAT CANNOT BE READ CANNOT BE JUDGED. A header
            #  that stopped parsing makes its own records look
            #  orphaned, and they are not: they are UNREACHABLE, and
            #  the test is what wants mending.
            note_list.append(
                "%s: orphans not judged -- exploration reported %d "
                "fault(s), and a directory that cannot be read cannot "
                "say what it offers" % (where, len(result.fault_list)))
        elif not wanted_f:
            note_list.append(
                "%s: orphans not judged -- the wish hides cases here, "
                "and the hidden ones would look orphaned" % where)
        else:
            found, refused = orphan_issue_list(directory, result.app_set)
            issue_list.extend(found)
            note_list.extend(r.replace(directory, where, 1) for r in refused)

    return issue_list, note_list


# -- THE FACE: one command ---------------------------------------------------
HELP  = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip()
USAGE = "usage: hwut.sanitize <command> <concerned entity> " \
        "[--directory=<path>]\n" \
        "       commands: %s; a whole proposal: " \
        "'hwut.sanitize.propose', 'hwut.sanitize.apply'" \
        % ", ".join(VERB_TUPLE)


def main(argv=None, write=None, ask=None):
    """
    RETURN: E_ExitCode, the exit status (E-1): OK where the command was
            done or had nothing to do, FAULT where the tree refused it
            or acting failed, REFUSED where the command line cannot be
            read.

    'ask' reads one answer after a prompt -- only 'root' with no
    directory asks; 'input' where none is given, and NOT CALLED where
    the input is no terminal: a question nobody can hear is a hang.

    THE FACE IS A SPELLING of one line of a proposal: the words are
    read by the same reader 'hwut.sanitize.apply' reads a file with,
    and done by the same command.
    """
    from vut.services.lib.sanitize.command import (CContext, line_of_words,
                                                   done_line_list)
    if write is None: write = print
    if argv is None:  argv  = sys.argv[1:]
    if "--help" in argv:
        from vut.services._core import man_page
        write(man_page("hwut.sanitize", HELP,
                       usage=USAGE.split("\n")[0]))
        return E_ExitCode.OK

    base, word_list = ".", []
    for argument in argv:
        if argument.startswith("--directory="):
            base = argument[len("--directory="):]
        elif argument.startswith("-"):
            write("REFUSED: 'hwut.sanitize' does not take: %s" % argument)
            write(USAGE)
            return E_ExitCode.REFUSED
        else:
            word_list.append(argument)
    if not os.path.isdir(base):
        write("REFUSED: the directory '%s' does not exist" % base)
        write(USAGE)
        return E_ExitCode.REFUSED
    if word_list == ["root"]:
        #  'root' ALONE ASKS WHERE (ruled 2026-10-08). A boundary that
        #  stands is said before anything is asked.
        from vut.services._boundary import ROOT_CONF_NAME
        from vut.engine.orchestrator.exploration.tree_explorer \
                               import RootConfMissing, root_conf_directory
        try:
            standing = root_conf_directory(base)
        except RootConfMissing:
            standing = None
        if standing is not None:
            write("nothing to do: a boundary stands: '%s'"
                  % os.path.join(shown(base, standing), ROOT_CONF_NAME))
            return E_ExitCode.OK
        if ask is None:
            if not sys.stdin.isatty():
                write("REFUSED: 'root' with no directory asks where, and "
                      "nobody can answer -- name it: 'hwut.sanitize root "
                      "<dir>'")
                return E_ExitCode.REFUSED
            ask = input
        chosen = root_asked(base, write, ask)
        if chosen is None:
            write("nothing written.")
            return E_ExitCode.OK
        word_list = ["root", chosen]
    command = line_of_words(word_list)
    if isinstance(command, str):
        write("REFUSED: %s" % command)
        write(USAGE)
        return E_ExitCode.REFUSED

    context = CContext(base)
    done    = context.execute(command)
    for line in done_line_list(command, done):
        write(line)
    for line in context.touch():
        write(line)
    return E_ExitCode.OK if done.good_f() else E_ExitCode.FAULT


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ._exit import guarded
    sys.exit(guarded("hwut.sanitize", main))
