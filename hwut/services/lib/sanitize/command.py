# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
"""
______________________________________________________________________________
PURPOSE: THE SANITIZE COMMANDS (services E-125) -- one line of a proposal,
         read, judged again, and done.

    line_of_text(text)        one line of a proposal file, read
    line_of_words(word_list)  the same, from a command line's words
    CContext(base).execute(command)
                              judge again, then act; the outcome as data
    CContext.touch()          the re-run trigger, for every directory
                              that was acted on

THE FILE SAYS WHAT; THE TREE SAYS WHETHER. A proposal may be hours old
and edited by hand. So no command trusts it: each asks the aspect that
proposes it -- the same function, 'services/sanitize.py' -- whether the
entity is still insane, and acts only where the answer is yes. Where the
entity no longer stands at all, there is NOTHING TO DO; where it stands
and the judgement disagrees, the command is REFUSED with the reason.

THE ACTING IS SPLIT FROM THE SAYING (E-103): 'execute' answers a CDone
and prints nothing; the faces turn it into lines.
______________________________________________________________________________
"""
import re
import os
import shutil
from   dataclasses import dataclass, field

from ....auxiliary.directory_mutex import LOCK_DIRECTORY_NAME
from ....engine.bookkeeper.api import (Bookkeeper,
                                               GOOD_OWNED_FILE_TUPLE,
                                               STAIN_CONSTRAINT_WORD,
                                               carries_unaccepted_f,
                                               nominal_stands_f)
from   hwut.engine.operations.run.multi_execute \
                                       import SESSION_DIRECTORY_NAME
from   hwut.engine.orchestrator.exploration.tree_explorer \
                                       import (test_directory_f, ascended_spec,
                                               RootConfMissing,
                                               explore_tree_stream,
                                               root_conf_directory)
from ... import sanitize
from ..cmdline import did_you_mean


class E_Done:
    """WHAT BECAME OF ONE COMMAND -- plain words, so a CDone is a plain
    record (E-103): what a report prints between the brackets."""
    DONE    = "DONE"       # judged insane, and healed
    NOTHING = "NOTHING"    # nothing stands to heal: gone, or agrees
    REFUSED = "REFUSED"    # stands, and the judgement says: not insane
    FAULT   = "ERROR"      # judged insane, and the act failed


@dataclass(frozen=True)
class CCommand:
    """One command: its verb and the words of its entity."""
    verb:       str
    word_tuple: tuple

    def text(self):
        """RETURN: str, the command as a line spells it."""
        return " ".join((self.verb,) + self.word_tuple)


@dataclass(frozen=True)
class CDone:
    """WHAT BECAME OF ONE COMMAND, as data: the outcome, the reason in
    one line (empty where it was done), and what an act SAID on its way
    -- a target's own output."""
    outcome:   str                 # an E_Done word
    reason:    str   = ""
    said_list: tuple = field(default=())

    def good_f(self):
        """RETURN: bool, True where it was done or had nothing to do."""
        return self.outcome in (E_Done.DONE, E_Done.NOTHING)


#  verb -> (the least, the most words its entity takes, how they read)
ARITY_DB = {
    "remove": (1, 1, "<dir>/TMP/session | <dir>/TMP/lock | <dir>/OUT | "
                     "<dir>/TMP"),
    "forget": (1, 2, "<dir>/<test> [<choice>]"),
    "move":   (2, 2, "<dir>/<test> <new-dir>"),
    "book":   (1, 2, "<dir>/<test> [<choice>]"),
    "remark": (1, 2, "<dir>/<test> [<choice>]"),
    "unlink": (1, 1, "<dir>/GOOD/<case>.link"),
    "run":    (2, 2, "<dir> <target>"),
    "register": (1, 1, "<dir>"),
    "redirect": (2, 2, "<id> <path below the root>"),
    "repoint":  (2, 2, "<external id> <internal id>"),
    "fold":     (2, 2, "<id> <first id>"),
    "root":   (1, 1, "<dir>"),
    "sub-root": (1, 1, "<dir>"),
}
assert set(ARITY_DB) == set(sanitize.VERB_TUPLE)

#  WHAT 'remove' TAKES, by the path's tail -- and nothing else.
REMOVE_TAIL_TUPLE = (SESSION_DIRECTORY_NAME, LOCK_DIRECTORY_NAME,
                     sanitize.OUT_DIRECTORY_NAME,
                     sanitize.TRANSIENT_DIRECTORY_NAME)


#  THE NOTE BEHIND A COMMAND (E-130): a blank, '#', a blank, and
#  whatever follows. An entity never holds ' # '.
NOTE_RE = re.compile(r"\s+#\s.*$")


def line_of_words(word_list):
    """
    RETURN: CCommand, the command the words spell.
            str,      why they spell none -- an unknown verb (with a
                      suggestion), or an entity of the wrong length.
    """
    if not word_list:
        return "no command -- one of %s" % ", ".join(sanitize.VERB_TUPLE)
    verb, entity = word_list[0], tuple(word_list[1:])
    if verb not in ARITY_DB:
        return "unknown command '%s'%s" \
               % (verb, did_you_mean(verb, sanitize.VERB_TUPLE))
    least_n, most_n, form = ARITY_DB[verb]
    if not least_n <= len(entity) <= most_n:
        return "'%s' takes %s" % (verb, form)
    return CCommand(verb, entity)


def line_of_text(text):
    """
    RETURN: CCommand, the command one line of a proposal holds.
            None,     the line is a comment or blank -- THE VETO: a
                      line that starts '#' is not done.
            str,      why the line spells no command.

    A NOTE AFTER THE COMMAND IS NOT READ (E-130): from a '#' that stands
    after a blank to the line's end -- "  # possibly moved to ...".
    """
    stripped = text.strip()
    if not stripped or stripped.startswith("#"): return None
    stripped = NOTE_RE.sub("", stripped)
    return line_of_words(stripped.split())


class CContext:
    """
    ONE SITTING OF COMMANDS against one tree: where the entities are read
    from ('base'), what exploration found (asked once per directory),
    and the directories acted on (for the re-run trigger).
    """

    def __init__(self, base):
        """RETURN: CContext, entities read relative to 'base'."""
        self.base         = os.path.abspath(base)
        self._result_db   = {}
        self._touch_set   = set()     # directories whose apps are touched
        self._below_set   = set()     # ... and every test directory below

    # -- exploration, asked once ------------------------------------------
    def result_of(self, directory):
        """
        RETURN: ExplorationResult, what the test directory offers.
                None, where it is no test directory hwut explores.
        """
        directory = os.path.normpath(directory)
        if directory in self._result_db: return self._result_db[directory]
        found = None
        try:
            if test_directory_f(directory, ascended_spec(directory)[0]):
                found = next((r for w, r in explore_tree_stream(directory)
                              if w == "."), None)
            else:
                root  = root_conf_directory(directory)
                found = next((r for w, r in explore_tree_stream(root)
                              if os.path.normpath(os.path.join(root, w))
                                 == directory), None)
        except (RootConfMissing, OSError):
            found = None
        self._result_db[directory] = found
        return found

    # -- the entity ---------------------------------------------------------
    def path_of(self, word):
        """RETURN: str, 'word' as an absolute, normalised path."""
        return os.path.normpath(os.path.join(self.base, word))

    def case_of(self, word_tuple):
        """RETURN: (directory, test, choice) of '<dir>/<test> [<choice>]'
                   -- 'choice' None where none is written."""
        where, _, test = word_tuple[0].rpartition("/")
        choice = word_tuple[1] if len(word_tuple) > 1 else None
        return self.path_of(where or "."), test, choice

    # -- the commands -------------------------------------------------------
    def execute(self, command):
        """
        RETURN: CDone, what became of 'command' -- judged again, and
                done only where the judgement still finds it insane.
        """
        try:
            return getattr(self, "_do_" + command.verb.replace("-", "_"))(
                command.word_tuple)
        except Exception as error:                         # noqa: BLE001
            return CDone(E_Done.FAULT, "%s: %s" % (type(error).__name__,
                                                   error))

    def _do_root(self, word_tuple):
        """RETURN: CDone -- 'hwut-root.conf' written into the directory
                   named; NOTHING where a boundary already stands in or
                   above it, REFUSED where it is no directory or cannot
                   be written in."""
        from ... import _boundary
        directory = self.path_of(word_tuple[0])
        if not os.path.isdir(directory):
            return CDone(E_Done.REFUSED, "no such directory")
        try:
            standing = root_conf_directory(directory)
        except RootConfMissing:
            standing = None
        if standing is not None:
            where = os.path.join(sanitize.shown(self.base, standing),
                                 _boundary.ROOT_CONF_NAME)
            if os.path.normpath(standing) == directory:
                return CDone(E_Done.NOTHING, "a bubble stands: '%s'" % where)
            #  BELOW A ROOT (RQ-1, ruled 2026-10-24): an inner root cuts a
            #  project out of the tree -- done only when asked by its name.
            return CDone(E_Done.REFUSED,
                         "a bubble stands above: '%s' => a bubble of "
                         "its own here: 'hwut.sanitize sub-root %s'"
                         % (where, word_tuple[0]))
        return self._root_written(directory)

    def _do_sub_root(self, word_tuple):
        """RETURN: CDone -- 'hwut-root.conf' written into the directory
                   named, a project of its own inside a tree (RQ-1): a
                   walk from above stops there; NOTHING where the
                   directory is a root already, REFUSED where no tree
                   stands above it ('root' is the verb then), it is no
                   directory, or it cannot be written in."""
        from ... import _boundary
        directory = self.path_of(word_tuple[0])
        if not os.path.isdir(directory):
            return CDone(E_Done.REFUSED, "no such directory")
        try:
            standing = root_conf_directory(directory)
        except RootConfMissing:
            standing = None
        if standing is None:
            return CDone(E_Done.REFUSED,
                         "no tree stands above => 'hwut.sanitize root %s'"
                         % word_tuple[0])
        if os.path.normpath(standing) == directory:
            return CDone(E_Done.NOTHING, "a bubble stands: '%s'"
                         % os.path.join(sanitize.shown(self.base, standing),
                                        _boundary.ROOT_CONF_NAME))
        return self._root_written(directory)

    def _root_written(self, directory):
        """RETURN: CDone, DONE where the template 'hwut-root.conf' was
                   written into 'directory'; REFUSED where it cannot be
                   written in, FAULT where writing failed."""
        from ... import _boundary
        if not _boundary.writeable_f(directory):
            return CDone(E_Done.REFUSED, "no write access")
        try:
            _boundary.written(directory)
        except OSError as error:
            return CDone(E_Done.FAULT, str(error))
        return CDone(E_Done.DONE)

    def _relation_root(self, directory):
        """
        RETURN: [0] str, the root of the tree 'directory' stands in --
                    where a detected move is looked for
                [1] CDone, the refusal where no tree bounds it, or it
                    is no directory; None else
        """
        if not os.path.isdir(directory):
            return None, CDone(E_Done.NOTHING, "nothing stands there")
        try:
            return root_conf_directory(directory), None
        except RootConfMissing:
            return None, CDone(E_Done.REFUSED,
                               "no 'hwut-root.conf' stands in or above it: "
                               "not a tree of hwut's")

    def _do_register(self, word_tuple):
        """RETURN: CDone -- what the directory defines added to the central
                   file ('feature_registry_act.register'): an id, a line per
                   feature; NOTHING where all of it is registered, REFUSED
                   where no central file stands or the edit would leave a
                   fault."""
        from ....engine.orchestrator.exploration import feature_registry_act
        directory     = self.path_of(word_tuple[0])
        root, refusal = self._relation_root(directory)
        if refusal is not None: return refusal
        below = os.path.relpath(directory, root).replace(os.sep, "/")
        try:
            directory_list, leaf_list, _ = feature_registry_act.register(
                root, below)
        except feature_registry_act.ActRefused as error:
            return CDone(E_Done.REFUSED, str(error).split("\n")[0])
        said = tuple("registered  %s  %s" % (p, i) for i, p in directory_list) \
               + tuple("registered  %s = %s" % pair for pair in leaf_list)
        if said: return CDone(E_Done.DONE, "", said)
        return CDone(E_Done.NOTHING, "everything below it is registered")

    def _registry_proposal(self, verb, word_tuple):
        """RETURN: CDone -- the detector's proposal '<verb> <words>' done
                   ('feature_registry_act.apply_proposal'), judged again
                   first: NOTHING where it is proposed no more, REFUSED
                   where no central file stands or the edit would leave a
                   fault."""
        from ....engine.orchestrator.exploration import feature_registry_act
        root, refusal = self._relation_root(self.base)
        if refusal is not None: return refusal
        try:
            said = feature_registry_act.apply_proposal(root, verb,
                                                       word_tuple)
        except feature_registry_act.ActRefused as error:
            return CDone(E_Done.REFUSED, str(error).split("\n")[0])
        if said is None:
            return CDone(E_Done.NOTHING, "not proposed now: the detector "
                                         "proposes no such line")
        return CDone(E_Done.DONE, "", tuple(said))

    def _do_redirect(self, word_tuple):
        """RETURN: CDone -- a directory id pointed at where it moved."""
        return self._registry_proposal("redirect", word_tuple)

    def _do_repoint(self, word_tuple):
        """RETURN: CDone -- an external id bound to the feature it became."""
        return self._registry_proposal("repoint", word_tuple)

    def _do_fold(self, word_tuple):
        """RETURN: CDone -- a twin id folded into the first."""
        return self._registry_proposal("fold", word_tuple)

    def _do_remove(self, word_tuple):
        """RETURN: CDone -- a session, a dead lock, 'OUT/' or 'TMP/' gone."""
        path = self.path_of(word_tuple[0])
        tail = next((t for t in REMOVE_TAIL_TUPLE
                     if path.endswith(os.sep + t.replace("/", os.sep))),
                    None)
        if tail is None:
            return CDone(E_Done.REFUSED,
                         "'remove' takes %s -- nothing else"
                         % ARITY_DB["remove"][2])
        directory = path[:-len(tail) - 1]
        try:
            root_conf_directory(directory)
        except RootConfMissing:
            return CDone(E_Done.REFUSED, "no 'hwut-root.conf' stands in or "
                                         "above it: not a tree of hwut's")
        if not os.path.isdir(path):
            return CDone(E_Done.NOTHING, "nothing stands there")
        try:
            if tail == SESSION_DIRECTORY_NAME:
                found_f = bool(sanitize.session_issue_list(directory))
            elif tail == LOCK_DIRECTORY_NAME:
                found_f = bool(sanitize.lock_issue_list(directory))
                if not found_f:
                    holder = sanitize.live_holder_of(directory) or {}
                    return CDone(E_Done.REFUSED,
                                 "the holder (pid %s) lives, or cannot be "
                                 "told" % holder.get("pid", "?"))
            else:
                #  'OUT/' AND 'TMP/' ARE READ BY A LIVE RUN: refused whole.
                sanitize.refuse_live(self.base, directory)
                found_f = True
        except sanitize.DirectoryLive as error:
            return CDone(E_Done.REFUSED, str(error).partition(": ")[2])
        if not found_f:
            return CDone(E_Done.NOTHING, "nothing stands there")
        try:
            shutil.rmtree(path)
        except OSError as error:
            return CDone(E_Done.FAULT, str(error))
        self._touch_set.add(directory)
        return CDone(E_Done.DONE)

    def _explored(self, directory):
        """RETURN: [0] ExplorationResult, or None;
                   [1] CDone, the refusal where it cannot be judged."""
        result = self.result_of(directory)
        if result is None:
            return None, CDone(E_Done.REFUSED,
                               "not a test directory hwut explores")
        if result.fault_list:
            return None, CDone(E_Done.REFUSED,
                               "exploration reported %d fault(s): a "
                               "directory that cannot be read cannot be "
                               "judged" % len(result.fault_list))
        return result, None

    def _do_forget(self, word_tuple):
        """RETURN: CDone -- an orphan's every record gone, through
                   'hwut.remove'."""
        from ... import remove
        directory, test, choice = self.case_of(word_tuple)
        result, refusal = self._explored(directory)
        if refusal is not None: return refusal
        issue_list, _ = sanitize.orphan_issue_list(directory, result.app_set)
        word_set = set(issue.word_tuple for issue in issue_list)
        #  A TEST THAT IS GONE is an orphan in every choice.
        if (test,) not in word_set and (test, choice) not in word_set:
            offered = sanitize.offered_key_set(result.app_set)
            if (test, choice) in offered \
               or (choice is None and any(t == test for t, _ in offered)):
                return CDone(E_Done.REFUSED, "the case is offered: not an orphan")
            if os.path.exists(os.path.join(directory, test)):
                return CDone(E_Done.REFUSED,
                             "the application stands and exploration "
                             "cannot see it: unreachable, not orphaned")
            return CDone(E_Done.NOTHING, "nothing is recorded of it")
        said = []
        argv = ["--directory=%s" % directory, "--dont-ask", test] \
               + ([] if choice is None else [choice])
        code = remove.main(argv, write=said.append)
        if code.name not in ("OK", "EMPTY"):
            return CDone(E_Done.FAULT,
                         next((line.strip() for line in said
                               if line.startswith(("REFUSED", "FAULT"))),
                              "not forgotten"))
        self._touch_set.add(directory)
        return CDone(E_Done.DONE)

    def _do_move(self, word_tuple):
        """RETURN: CDone -- an orphan's every record carried after its
                   application into the directory it stands in now,
                   through 'hwut.move' (E-131)."""
        from ... import move
        directory, test, _ = self.case_of(word_tuple[:1])
        target = self.path_of(word_tuple[1])
        result, refusal = self._explored(directory)
        if refusal is not None: return refusal
        issue_list, _ = sanitize.orphan_issue_list(directory, result.app_set)
        if (test,) not in set(issue.word_tuple for issue in issue_list):
            if os.path.exists(os.path.join(directory, test)):
                return CDone(E_Done.REFUSED,
                             "the application stands here: nothing moved")
            return CDone(E_Done.NOTHING, "nothing is recorded of it")
        if not os.path.exists(os.path.join(target, test)):
            return CDone(E_Done.REFUSED,
                         "the application does not stand in the directory "
                         "named")
        if sanitize.recorded_f(target, test):
            return CDone(E_Done.REFUSED,
                         "it is recorded there already: 'forget' the "
                         "records here instead")
        said = []
        code = move.main([os.path.join(directory, test), target,
                          "--dont-ask"], write=said.append)
        if code.name != "OK":
            return CDone(E_Done.FAULT,
                         next((line.strip() for line in said
                               if line.startswith(("REFUSED", "FAULT"))),
                              "not moved"))
        self._touch_set.add(directory)
        self._touch_set.add(target)
        return CDone(E_Done.DONE)

    def _do_book(self, word_tuple):
        """RETURN: CDone -- the standing nominal entered as accepted."""
        directory, test, choice = self.case_of(word_tuple)
        if not nominal_stands_f(directory, test, choice):
            return CDone(E_Done.REFUSED,
                         "no nominal stands: nothing to book "
                         "('hwut.accept' makes one)")
        result, refusal = self._explored(directory)
        if refusal is not None: return refusal
        issue_list, refused = sanitize.books_issue_list(directory,
                                                        result.app_set)
        if refused:
            return CDone(E_Done.REFUSED, refused[0].partition(": ")[2])
        words = (test,) if choice is None else (test, choice)
        if words not in set(issue.word_tuple for issue in issue_list):
            return CDone(E_Done.NOTHING, "the book agrees with GOOD/")
        #  AN INCOMPLETE ACCEPTANCE IS BOOKED AS ONE (B-16): a nominal
        #  carrying '##! unaccepted' makes the case an ASPIRANT.
        aspirant_f = any(carries_unaccepted_f(path)
                         for path in nominal_path_list(directory, test,
                                                       choice))
        Bookkeeper(directory).note_accept(test, choice,
                                          aspirant_f=aspirant_f)
        self._touch_set.add(directory)
        return CDone(E_Done.DONE)

    def _do_unlink(self, word_tuple):
        """RETURN: CDone -- the '.link' gone (bookkeeper B-32); the text it
                   named is never touched."""
        path = self.path_of(word_tuple[0])
        if not path.endswith(".link") \
           or os.path.basename(os.path.dirname(path)) != "GOOD":
            return CDone(E_Done.REFUSED, "'unlink' takes %s -- nothing else"
                                         % ARITY_DB["unlink"][2])
        if not os.path.isfile(path):
            return CDone(E_Done.NOTHING, "nothing stands there")
        #  JUDGED AGAIN BEFORE IT ACTS: a sound link alone in its case is
        #  the case's GOOD, and is not sanitize's to take.
        directory  = os.path.dirname(os.path.dirname(path))
        insane_set = set(issue.word_tuple[0] for issue
                         in sanitize.link_issue_list(directory))
        if "GOOD/%s" % os.path.basename(path) not in insane_set:
            return CDone(E_Done.REFUSED, "the link is sound and the case's "
                                         "only GOOD => 'hwut.good.isolate' "
                                         "gives the case its own file")
        try:
            os.unlink(path)
        except OSError as error:
            return CDone(E_Done.FAULT, str(error))
        self._touch_set.add(directory)
        return CDone(E_Done.DONE)

    def _do_remark(self, word_tuple):
        """RETURN: CDone -- the constraint findings written into the
                   nominal, the book stained."""
        directory, test, choice = self.case_of(word_tuple)
        result, refusal = self._explored(directory)
        if refusal is not None: return refusal
        words = (test,) if choice is None else (test, choice)
        issue = next((i for i in sanitize.constraint_issue_list(directory,
                                                                result)
                      if i.word_tuple == words), None)
        if issue is None:
            return CDone(E_Done.NOTHING, "no finding stands unwritten")
        bookkeeper = Bookkeeper(directory)
        bookkeeper.note_stain_keyword(test, choice, STAIN_CONSTRAINT_WORD,
                                      True)
        #  WHERE IT WAS FOUND: after the line, a variable never bound at
        #  the head -- as a run writes it.
        bookkeeper.note_nominal_remark(test, choice, "stdout",
                                       list(issue.payload))
        self._touch_set.add(directory)
        return CDone(E_Done.DONE)

    def _do_run(self, word_tuple):
        """RETURN: CDone -- the project's target run, through
                   'hwut.execute', in the directory and below."""
        from ... import execute
        directory, target = self.path_of(word_tuple[0]), word_tuple[1]
        if not os.path.isdir(directory):
            return CDone(E_Done.REFUSED, "no such directory")
        said = []
        code = execute.main(["--directory=%s" % directory, target],
                            write=lambda line: said.append(str(line)))
        if code.name == "EMPTY":
            return CDone(E_Done.REFUSED,
                         "no directory binds a target '%s'" % target,
                         tuple(said))
        self._below_set.add(directory)
        if code.name != "OK":
            return CDone(E_Done.FAULT, "the target failed", tuple(said))
        return CDone(E_Done.DONE, "", tuple(said))

    # -- the re-run trigger -------------------------------------------------
    def touch(self):
        """
        RETURN: list[str], what the re-run trigger says -- nothing where
                nothing was acted on.

        THE RE-RUN TRIGGER (ruled 2026-09-05). A command that ACTED has
        changed what its directory's recordings rest on; every recording
        there is suspect, and the channel's freshness is a comparison of
        modification times. So every test application there is TOUCHED:
        younger than every recording, every refreshing face runs it next
        time it is asked.
        """
        path_set = set()
        for directory in self._touch_set:
            result = self.result_of(directory)
            if result is None: continue
            path_set.update(os.path.join(directory, app.source_file)
                            for app in result.app_set)
        for directory in self._below_set:
            try:
                for where, result in explore_tree_stream(directory):
                    whole = os.path.join(directory, where)
                    path_set.update(os.path.join(whole, app.source_file)
                                    for app in result.app_set)
            except (RootConfMissing, OSError):
                continue
        if not path_set: return []
        line_list = ["TOUCHED (the re-run trigger): %d test application(s)"
                     % len(path_set)]
        for path in sorted(path_set):
            try:
                os.utime(path, None)
            except OSError as error:
                line_list.append("    could not touch %s: %s"
                                 % (sanitize.shown(self.base, path), error))
        return line_list


def nominal_path_list(directory, test, choice):
    """RETURN: list[str], every nominal in GOOD/ that stands for (test,
               choice) -- its own, and the choice-less one it shares."""
    good_dir = os.path.join(directory, "GOOD")
    if not os.path.isdir(good_dir): return []
    wanted = {(test, choice), (test, None)}
    return [os.path.join(good_dir, name)
            for name in sorted(os.listdir(good_dir))
            if name not in GOOD_OWNED_FILE_TUPLE
            and sanitize.record_key_of(name) in wanted]


def done_line_list(command, done):
    """
    RETURN: list[str], what the one-command face says of 'done':

                done: remove suite/TEST/TMP/session
                nothing to do: book suite/TEST/test-a.sh -- the book agrees
                REFUSED: remove suite/TEST/TMP/lock -- the holder lives
                ERROR: forget suite/TEST/test-x.sh -- <why>

            then whatever the act said, indented.
    """
    head = {E_Done.DONE:    "done: %s",
            E_Done.NOTHING: "nothing to do: %s",
            E_Done.REFUSED: "REFUSED: %s",
            E_Done.FAULT:   "ERROR: %s"}[done.outcome] % command.text()
    if done.reason: head += " -- %s" % done.reason
    return [head] + ["    %s" % line for line in done.said_list]
