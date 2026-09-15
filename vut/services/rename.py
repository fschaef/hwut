"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.rename' COMMAND LINE -- a test, or one choice of it,
         RENAMED, and a test CARRIED into another directory: its
         nominals, candidates, book entry, register entry, coverage
         records and labels follow the new name.

    hwut.rename <app> -to <app'>               [--dont-ask] [--directory=<path>]
    hwut.rename <app> <choice> -to <choice'>   [--dont-ask] [--directory=<path>]
    hwut.rename <app> -to <path>/<app'>        [--dont-ask] [--directory=<path>]
    hwut.move   <app> <app'>                   == hwut.rename <app> -to <app'>
                                               [--no-warning] [--silent]

'-to' IS A KEYWORD. One word before it names an app; two name an app
and one of its choices. One word follows it: the fresh name. A fresh
name carrying '/' names a DIRECTORY and a name; a fresh name that IS
an existing directory means INTO it, the app's name unchanged. The app
word may itself be a path ('a/TEST/app.sh', E-45); '--directory'
names the source directory, and a relative app path is read against
it. A choice
never crosses a directory.

NO RECORD CONTENT IS TOUCHED, save one: a coverage record carries its
RUN ID, and ids are the DIRECTORY'S. Within the directory the register
keeps the id and the record moves untouched. ACROSS a directory the
source register RETIRES the id, the target register ISSUES a fresh
one, and the record is RE-SEATED under it -- through coverage's own
seam, not by hand; moved unchanged it would decode in the target to
another test, or to nobody.

A RENAME IS NOT A FRESH START. What the test did under its old name it
did, and the book entry moves with everything in it: the recorded runs,
the stderr note, and ANY STAIN. A test that switched results does not
launder itself by being called something else, or by moving house.
('hwut.remove' is the verb for wanting no history.)

WHAT MOVES, each step announced:

    NOMINALS     'GOOD/<key>.<subject>' per subject
    CANDIDATES   'TMP/store/<key>.<subject>' and every sidecar --
                 the freshness stamp, the raw stream, the cadence, the
                 error witness, the coverage record
    THE BOOK     the entry re-keyed; across a directory: given up by
                 the source's book, adopted by the target's
    THE REGISTER within the directory the name follows and the id
                 stands; across, retired here and issued there
    THE LABELS   the boundary records, last ('services/_follow.py')

WHAT IS NOT TOUCHED: the test application file, its '@hwut' block,
and any 'hwut.conf' 'apps' section naming it. Renaming or moving the
SOURCE is the author's act -- 'git mv' -- and this face FOLLOWS it;
it does not perform it, and it edits no declaration (E-48). It READS
them and SAYS what disagrees, telegraphically, before asking:

    NOTE  application 'test-app.sh' stands under the OLD name -- git mv
    NOTE  '@hwut' declares 'one', not 'first' -- edit the block
    NOTE  hwut.conf apps section 'test-app.sh' -- rename it

'--no-warning' drops the notes; '--silent' drops everything but a
refusal or a fault. An application standing under BOTH names is
refused: which one is the test is the author's to decide first.

IT REFUSES A COLLISION. A fresh name that already stands in the target
book would swallow another test's history; it is refused at the door,
by name, and nothing is moved.

IT ASKS FIRST, showing every move, unless '--dont-ask'.

A TEST THAT IS NOT IN THE BOOK is not an error: there is nothing to
follow, and the face says so.

EXIT STATUS (E-1, services/_exit.py):
    0  the rename was made, or there was nothing to rename
    1  something could not be moved
    2  the command line cannot be read, or a name collides
    3  the command line reads, and names nothing
______________________________________________________________________________
"""
import os
import sys

from   vut.engine.bookkeeper.api import Bookkeeper, Store
from   vut.engine.bookkeeper.api import TestIdFault
from   vut.engine.bookkeeper.api import BOOK_FORBIDDEN_IN_NAME
from   vut.engine.coverage.api   import (pack_record, unpack_record,
                                         seated, RecordFault)
from   ._follow                  import labels_renamed
from   ._target                  import split_words, TargetError
from   ._exit                    import E_ExitCode
from   vut.engine.orchestrator.exploration.reader import (read_header,
                                                          read_conf)
from   vut.services.lib.cmdline import did_you_mean, option_tuple

KEYWORD = "-to"

USAGE = ("usage: hwut.rename <app> -to <app'>              [--dont-ask] "
         "[--directory=<path>] [--no-warning] [--silent]\n"
         "       hwut.rename <app> <choice> -to <choice'>  [--dont-ask] "
         "[--directory=<path>]\n"
         "       hwut.rename <app> -to <path>/<app'>       [--dont-ask] "
         "[--directory=<path>]\n"
         "       hwut.move   <app> <app'>          == hwut.rename "
         "<app> -to <app'>")

#  The licence line and the rule are the FILE's, not the face's.
HELP = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
       + "\n\n" + USAGE


def _shown(store, path):
    """RETURN: str, the path as it reads from the SOURCE test directory
    -- 'GOOD/x.stdout' and 'TMP/store/x.stdout' are DIFFERENT files and
    a basename alone would print them alike; a target in another
    directory reads with that directory in front."""
    try:               return os.path.relpath(path, str(store.directory))
    except ValueError: return path


def _same_place(a, b):
    """RETURN: bool, True where the two paths name one directory."""
    return os.path.normcase(os.path.abspath(a)) \
           == os.path.normcase(os.path.abspath(b))


class Rename:
    """ONE rename, read off the command line: what stands where, and
    what is to stand where.

        test, choice       the source key; 'choice' None for an app
        fresh_test         the name the app is to bear
        fresh_choice       the name the choice is to bear; None for an app
        source, target     the two Stores; the SAME object within one
                           directory
        whole_test_f       True for the app form
    """
    __slots__ = ("test", "choice", "fresh_test", "fresh_choice",
                 "source", "target", "whole_test_f")

    def __init__(self, test, choice, fresh_test, fresh_choice,
                 source, target, whole_test_f):
        self.test = test;             self.choice       = choice
        self.fresh_test = fresh_test; self.fresh_choice = fresh_choice
        self.source = source;         self.target       = target
        self.whole_test_f = whole_test_f

    @property
    def across_f(self):
        """RETURN: bool, True where source and target are two
        directories."""
        return self.source is not self.target

    def text(self):
        """RETURN: str, 'app [choice] -> [dir/]app' [choice]', as
        announced."""
        head = self.test if self.choice is None \
               else "%s %s" % (self.test, self.choice)
        if self.whole_test_f:
            tail = self.fresh_test if not self.across_f \
                   else os.path.join(str(self.target.directory),
                                     self.fresh_test)
        else:
            tail = "%s %s" % (self.test, self.fresh_choice)
        return "%s -> %s" % (head, tail)


def move_tuple(rename):
    """
    RETURN: tuple[(str, str)], (from, to) for every recorded artefact
            of that key that STANDS -- nominals, candidates, sidecars,
            the error witness and the coverage record; 'to' on the
            TARGET store's ground. Sorted by source, so the
            announcement is stable.

    The app form follows EVERY choice the book knows of the test.

    The subjects are read from what LIES THERE, not from what a
    configuration says: a rename must reach a subject whose
    declaration has since been edited away, or it leaves an orphan
    under the old name.
    """
    source, target = rename.source, rename.target
    found = []
    for old_choice, new_choice in _choice_pair_list(rename):
        #  THE ERROR WITNESS FOLLOWS THE NAME like the rest of the
        #  run's product; it is asked for by name, not as a subject.
        a = str(source.error_witness_path(rename.test, old_choice))
        b = str(target.error_witness_path(rename.fresh_test, new_choice))
        if os.path.exists(a): found.append((a, b))
        for subject in ("stdout",):
            for verb in ("candidate_path", "freshness_path", "raw_path",
                         "timing_path", "nominal_path"):
                a = str(getattr(source, verb)(rename.test, old_choice,
                                              subject))
                b = str(getattr(target, verb)(rename.fresh_test,
                                              new_choice, subject))
                if os.path.exists(a): found.append((a, b))
        a = str(source.bookkeeper.coverage_path(rename.test, old_choice))
        if os.path.exists(a):
            found.append((a, str(target.bookkeeper.coverage_path(
                                     rename.fresh_test, new_choice))))
    return tuple(sorted(set(found)))


def _choice_pair_list(rename):
    """RETURN: list[(choice, fresh choice)], every choice the rename
    touches: all of the test's for the app form (its choiceless key
    where the book knows none), the one for the choice form."""
    if rename.whole_test_f:
        pair_list = [(c, c) for c in
                     rename.source.bookkeeper.choices(rename.test)]
        return pair_list or [(rename.choice, rename.choice)]
    return [(rename.choice, rename.fresh_choice)]


def follow(rename, write):
    """
    RETURN: bool, True where every step succeeded; False where one
            failed -- announced by name, and the rest still attempted.

    THE ORDER: artefacts first, then the book, then the register, then
    the coverage records' seats, then the labels. A crash between
    steps leaves files under the new name and a book that still says
    the old one, which the next run reports as a missing GOOD -- loud,
    and mendable by re-running the rename.
    """
    #  THE CHOICES ARE READ BEFORE THE BOOK GIVES THE ENTRY UP: after
    #  that step the source book knows none of them.
    choice_list = [c for _, c in _choice_pair_list(rename)]
    good_f = _files_followed(rename, write)
    if not _book_followed(rename, write): return False
    run_db = _register_followed(rename, choice_list, write)
    if run_db is None: good_f = False
    elif rename.across_f and not _records_reseated(rename, run_db,
                                                   write):
        good_f = False
    #  THE BOUNDARY RECORDS FOLLOW LAST ('services/_follow.py'): a
    #  crash above leaves an entry naming the old name -- loud, and
    #  findable -- never a record silently pointing at nothing.
    if not labels_renamed(str(rename.source.directory), rename.test,
                          rename.choice, rename.fresh_test,
                          rename.fresh_choice, rename.whole_test_f,
                          write,
                          target_directory=str(rename.target.directory)):
        good_f = False
    return good_f


def _files_followed(rename, write):
    """RETURN: bool, True where every artefact moved."""
    good_f = True
    for source, target in move_tuple(rename):
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            os.rename(source, target)
            write("    %s -> %s" % (_shown(rename.source, source),
                                    _shown(rename.source, target)))
        except OSError as error:
            write("    FAULT: %s -- %s" % (_shown(rename.source, source),
                                           error))
            good_f = False
    return good_f


def _book_followed(rename, write):
    """RETURN: bool, True where the book entry re-keyed, moved, or
    never stood; False on a fault, announced."""
    book = rename.source.bookkeeper
    try:
        if not rename.whole_test_f:
            moved = book.rename_choice(rename.test, rename.choice,
                                       rename.fresh_choice)
        elif not rename.across_f:
            moved = book.rename_test(rename.test, rename.fresh_test)
        else:
            entry = book.remove_test(rename.test)
            moved = None
            if entry is not None:
                try:
                    moved = rename.target.bookkeeper.adopt(
                                rename.fresh_test, entry)
                except KeyError:
                    #  THE SOURCE TAKES ITS OWN ENTRY BACK: half a
                    #  move of a history is worse than none.
                    book.adopt(rename.test, entry)
                    raise
        write("    book entry: %s"
              % ("none stood" if moved is None
                 else "adopted by '%s'" % rename.target.directory
                 if rename.across_f else "re-keyed"))
        return True
    except KeyError as error:
        write("    FAULT: book -- %s" % error)
        return False


def _register_followed(rename, choice_list, write):
    """
    RETURN: dict, choice name -> TestRunId the moved run bears NOW --
            the standing id within a directory, the fresh id across
            one; empty where the test was never registered.
            None, on a register fault, announced.

    THE REGISTER MOVED IN THE BOOK'S OWN ACT (B-9): 'rename_test' and
    'rename_choice' re-keyed it, 'remove_test' retired the source's
    id, 'adopt' issued the target's. This step READS and SAYS.
    'choice_list' names the choices whose fresh ids the re-seat needs,
    read from the source book before it gave the entry up.
    """
    try:
        target = rename.target.bookkeeper
        if not rename.whole_test_f:
            run_id = target.run_id_of(rename.test, rename.fresh_choice)
            if run_id is None:
                write("    register: not registered"); return {}
            write("    register: choice name follows; the id stands")
            return {rename.fresh_choice: run_id}
        if not rename.across_f:
            run_id = target.run_id_of(rename.fresh_test)
            if run_id is None:
                write("    register: not registered"); return {}
            write("    register: name follows; the id stands")
            return {}
        run_db = {}
        for choice in choice_list:
            run_id = target.run_id_of(rename.fresh_test, choice)
            if run_id is not None: run_db[choice] = run_id
        if not run_db:
            write("    register: not registered"); return {}
        write("    register: retired here; issued %s there"
              % ", ".join(str(r) for r in sorted(run_db.values())))
        return run_db
    except TestIdFault as error:
        write("    FAULT: register -- %s" % error)
        return None


def _records_reseated(rename, run_db, write):
    """RETURN: bool, True where every coverage record that travelled
    now names its fresh run id; False on a fault, announced."""
    good_f = True
    for choice, run_id in run_db.items():
        path = str(rename.target.bookkeeper.coverage_path(
                       rename.fresh_test, choice))
        if not os.path.exists(path): continue
        try:
            with open(path, "rb") as fh: record = unpack_record(fh.read())
            data = pack_record(seated(record, run_id))
            with open(path, "wb") as fh: fh.write(data)
            write("    coverage record: re-seated under %s" % run_id)
        except (OSError, RecordFault) as error:
            write("    FAULT: coverage record %s -- %s"
                  % (_shown(rename.source, path), error))
            good_f = False
    return good_f


def situation_notes(rename):
    """
    RETURN: [0] list[str], telegraphic NOTE lines: the application's
                whereabouts, the '@hwut' block's choices, any
                'hwut.conf' apps section -- each only where it
                DISAGREES with the rename, or where nothing could be
                read. Empty where everything agrees.
            [1] str, a refusal where the application stands under BOTH
                names; None otherwise.

    READ AND SAY, NEVER EDIT (E-48): the source and the declarations
    are the author's; the face names what he has to touch.
    """
    note_list = []
    src_dir, dst_dir = str(rename.source.directory), str(rename.target.directory)
    old_path = os.path.join(src_dir, rename.test)
    new_path = os.path.join(dst_dir, rename.fresh_test)
    old_f, new_f = os.path.isfile(old_path), os.path.isfile(new_path)
    if rename.whole_test_f:
        if old_f and new_f:
            return note_list, ("application stands under BOTH names: '%s' "
                               "and '%s' -- decide which is the test first"
                               % (_shown(rename.source, old_path),
                                  _shown(rename.source, new_path)))
        if old_f:
            note_list.append("NOTE  application '%s' stands under the OLD "
                             "name -- git mv %s %s (E-16)"
                             % (rename.test, _shown(rename.source, old_path),
                                _shown(rename.source, new_path)))
        elif not new_f:
            note_list.append("NOTE  application stands under NEITHER name "
                             "-- nothing to run under '%s'" % rename.fresh_test)
    else:
        #  A CHOICE RENAME: the file is the same; its '@hwut' block
        #  names the choices.
        path = old_path if old_f else None
        if path is None:
            note_list.append("NOTE  application '%s' not found -- the "
                             "'@hwut' block cannot be read" % rename.test)
        else:
            try:
                spec, _ = read_header(open(path, encoding="utf-8").read(),
                                      path)
            except (OSError, UnicodeDecodeError):
                spec = None
            if spec is None:
                note_list.append("NOTE  no '@hwut' block read in '%s'"
                                 % rename.test)
            elif rename.fresh_choice not in spec.choice_db:
                note_list.append("NOTE  '@hwut' declares %s -- edit the "
                                 "block: '%s' -> '%s'"
                                 % (", ".join("'%s'" % c for c in
                                              spec.choice_db if c),
                                    rename.choice, rename.fresh_choice))
    #  hwut.conf 'apps' SECTIONS: the source's names the old name, the
    #  target's may name the new one already.
    for where, name, verb in ((src_dir, rename.test, "rename it"),):
        conf = os.path.join(where, "hwut.conf")
        if not os.path.isfile(conf): continue
        try:
            _, app_db, _ = read_conf(open(conf, encoding="utf-8").read(),
                                     conf)
        except (OSError, UnicodeDecodeError):
            continue
        entry = app_db.get(name)
        if entry is None: continue
        if rename.whole_test_f:
            note_list.append("NOTE  hwut.conf apps section '%s' in %s -- "
                             "%s%s" % (name, _shown(rename.source, conf),
                                       verb, " / carry it" if rename.across_f
                                       else ""))
        elif rename.choice in entry.choice_db \
             and rename.fresh_choice not in entry.choice_db:
            note_list.append("NOTE  hwut.conf apps section '%s' in %s "
                             "declares '%s' -- edit it"
                             % (name, _shown(rename.source, conf),
                                rename.choice))
    return note_list, None


def _read(argv, write):
    """
    RETURN: [0] Rename  what the words ask for
                None    they cannot be read -- refused aloud, with the
                        usage
                ()      they name nothing
            [1] bool    '--dont-ask' was said
    """
    directory = "."
    yes_f     = False
    word_list = []
    unknown   = []
    for argument in argv:
        if   argument.startswith("--directory="):
            directory = argument[len("--directory="):]
        elif argument == "--dont-ask":      yes_f = True
        elif argument == "--yes":
            #  E-68: "yes to what?" -- on the command line, before the
            #  question exists, the word names an answer to nothing.
            #  Refused BY NAME so a script that still says it is told.
            write("REFUSED: '--yes' is gone (E-68) -- '--dont-ask' is "
                  "the one word for 'do not ask'")
            return None, yes_f
        elif argument in ("--no-warning", "--silent"): pass
        elif argument == KEYWORD:      word_list.append(argument)
        elif argument.startswith("-"): unknown.append(argument)
        else:                          word_list.append(argument)
    if unknown:
        write("REFUSED: 'hwut.rename' does not take: %s"
              % ", ".join(sorted(unknown))
              + did_you_mean(unknown[0], option_tuple(USAGE)))
        write(USAGE)
        return None, yes_f
    if not os.path.isdir(directory):
        write("REFUSED: the directory '%s' does not exist" % directory)
        write(USAGE)
        return None, yes_f
    if not word_list:
        write("EMPTY: 'hwut.rename' names nothing to rename")
        return (), yes_f
    if word_list.count(KEYWORD) != 1:
        write("REFUSED: 'hwut.rename' takes '<words> %s <fresh>' -- "
              "'%s' must stand once" % (KEYWORD, KEYWORD))
        write(USAGE)
        return None, yes_f
    at     = word_list.index(KEYWORD)
    before = word_list[:at]
    after  = word_list[at + 1:]
    if len(before) not in (1, 2) or len(after) != 1:
        write("REFUSED: 'hwut.rename' takes '<app> %s <app'>' or "
              "'<app> <choice> %s <choice'>' -- %d word(s) before, "
              "%d after" % (KEYWORD, KEYWORD, len(before), len(after)))
        write(USAGE)
        return None, yes_f
    try:
        source_dir, before = split_words(before, directory)
    except TargetError as error:
        write("REFUSED: %s" % error)
        write(USAGE)
        return None, yes_f
    test   = before[0]
    choice = before[1] if len(before) == 2 else None
    fresh  = after[0]
    whole_test_f = choice is None

    if whole_test_f:
        if os.path.isdir(fresh) or fresh.endswith(os.sep):
            target_dir, fresh_test = fresh.rstrip(os.sep) or os.sep, test
        elif os.sep in fresh:
            target_dir, fresh_test = os.path.split(fresh)
            target_dir = target_dir or "."
        else:
            target_dir, fresh_test = source_dir, fresh
        fresh_choice = None
        if not os.path.isdir(target_dir):
            write("REFUSED: the target directory '%s' does not exist"
                  % target_dir)
            return None, yes_f
    else:
        if os.sep in fresh:
            write("REFUSED: a choice never crosses a directory -- "
                  "'%s' carries a path" % fresh)
            write(USAGE)
            return None, yes_f
        target_dir, fresh_test, fresh_choice = source_dir, test, fresh
    for forbidden in BOOK_FORBIDDEN_IN_NAME:
        if forbidden in (fresh_test if whole_test_f else fresh_choice):
            write("REFUSED: '%s' cannot stand in a name" % forbidden)
            return None, yes_f

    source = Store(Bookkeeper(source_dir))
    target = source if _same_place(source_dir, target_dir) \
             else Store(Bookkeeper(target_dir))
    if target is source and fresh_test == test \
       and (whole_test_f or fresh_choice == choice):
        write("REFUSED: '%s' is the name it already bears"
              % (fresh_test if whole_test_f else fresh_choice))
        return None, yes_f
    return Rename(test, choice, fresh_test, fresh_choice, source, target,
                  whole_test_f), yes_f


def main(argv=None, write=None, read_line=None):
    """
    RETURN: E_ExitCode, the exit status (E-1): OK where the rename was
            made or there was nothing to rename, FAULT where a step
            failed, REFUSED where the command line cannot be read or a
            name collides, EMPTY where it names nothing.
    """
    if write is None:     write     = print
    if read_line is None: read_line = sys.stdin.readline
    if argv is None:      argv      = sys.argv[1:]
    if "--help" in argv:
        write(HELP)
        return E_ExitCode.OK

    warning_f = "--no-warning" not in argv and "--silent" not in argv
    if "--silent" in argv:
        loud = write
        def write(text, _loud=loud):
            """RETURN: None. Under '--silent' only a refusal or a fault
            is said."""
            if text.startswith(("REFUSED", "EMPTY")) or "FAULT" in text:
                _loud(text)
    rename, yes_f = _read(argv, write)
    if rename is None: return E_ExitCode.REFUSED
    if rename == ():   return E_ExitCode.EMPTY

    note_list, refusal = situation_notes(rename)
    if refusal is not None:
        write("REFUSED: %s" % refusal)
        return E_ExitCode.REFUSED

    #  A COLLISION IS REFUSED BEFORE ANYTHING MOVES: half a rename
    #  onto a live name is worse than none.
    if rename.whole_test_f:
        #  THE BOOK AND THE REGISTER ARE BOTH ASKED: a name standing
        #  only in the register still owns an id, and the fresh name
        #  would be issued THAT id -- another test's.
        for where, standing in (
                ("book",     set(rename.target.bookkeeper.tests())),
                ("register", set(rename.target.bookkeeper.roster()))):
            if rename.fresh_test in standing and not (
                    not rename.across_f and rename.fresh_test == rename.test):
                write("REFUSED: '%s' already stands in the %s of '%s' -- "
                      "a rename onto it would swallow its history"
                      % (rename.fresh_test, where, rename.target.directory))
                return E_ExitCode.REFUSED
    elif rename.fresh_choice in rename.source.bookkeeper.choices(
                                    rename.test):
        write("REFUSED: '%s' already stands among the choices of '%s'"
              % (rename.fresh_choice, rename.test))
        return E_ExitCode.REFUSED

    write("TO FOLLOW THE NEW NAME, in '%s':" % rename.source.directory)
    pair_tuple = move_tuple(rename)
    write("  %s -- %d file(s), the book entry, the register %s"
          % (rename.text(), len(pair_tuple),
             "id, the coverage seats" if rename.across_f else "name"))
    for source, target in pair_tuple:
        write("      %s -> %s" % (_shown(rename.source, source),
                                  _shown(rename.source, target)))
    if not pair_tuple:
        write("  (no recorded artefact stands; the book and the "
              "register are still asked)")
    if warning_f:
        for note in note_list: write(note)

    if not yes_f:
        write("")
        write("Proceed? [y/N] ")
        answer = (read_line() or "").strip().lower()
        if answer not in ("y", "yes"):
            write("NOTE: nothing was renamed")
            return E_ExitCode.OK

    write("%s:" % rename.text())
    return E_ExitCode.OK if follow(rename, write) else E_ExitCode.FAULT


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ._exit import guarded
    sys.exit(guarded("hwut.rename", main))
