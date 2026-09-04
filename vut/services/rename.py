"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.rename' COMMAND LINE -- a test, or one choice of it,
         RENAMED: its nominals, its candidates, its book entry and its
         register entry follow the new name.

    hwut.rename        <old> <new> [...] [--yes] [--directory=<path>]
    hwut.rename-choice <test> <old> <new> [...] [--yes]
                       [--directory=<path>]

NO RECORD CONTENT IS TOUCHED. Not one byte inside a nominal, a
candidate, a cadence or a coverage record changes: the files are MOVED
and the keys re-written, nothing more. A VUT-COVERAGE record refers to
its RUN ID, and the register keeps that id across a rename -- that is
what the register is for. So the history survives the new name whole.

A RENAME IS NOT A FRESH START. What the test did under its old name it
did, and the book entry moves with everything in it: the recorded runs,
the stderr note, and ANY STAIN. A test that switched results does not
launder itself by being called something else. ('hwut.remove' is the
verb for wanting no history -- it says 'this test has no history',
which is true after it.)

WHAT MOVES, each step announced:

    NOMINALS     'GOOD/<key>.<subject>' per subject
    CANDIDATES   'TMP/store/<key>.<subject>' and every sidecar
                 beside it -- the freshness stamp, the raw stream, the
                 cadence, the coverage record
    THE BOOK     'GOOD/result_db.csv': the entry re-keyed
    THE REGISTER the name beside the id; THE ID ITSELF IS UNCHANGED

WHAT IS NOT TOUCHED: the test application file itself. Renaming the
SOURCE is the author's act -- 'git mv' -- and this face follows it; it
does not perform it. A face that moved source would be editing the
author's tree, which the framework does not do.

'--directory=<path>' NAMES ONE DIRECTORY, both ends of the rename. A
test that has physically moved to a DIFFERENT directory's tree is not
reached by either face yet -- its old directory's book and register
keep the stale entry, and its new directory's book and register never
learn of it (services/DISCUSSIONS.txt todo-1).

IT REFUSES A COLLISION. Renaming onto a name that already stands would
swallow another test's history; it is refused at the door, by name,
and nothing is moved.

IT ASKS FIRST, showing every move, unless '--yes'.

A TEST THAT IS NOT IN THE BOOK is not an error: there is nothing to
follow, and the face says so.

EXIT STATUS (E-1, services/_exit.py):
    0  everything named was renamed, or had nothing to rename
    1  something named could not be moved
    2  the command line cannot be read, or a name collides
    3  the command line reads, and names nothing
______________________________________________________________________________
"""
import os
import sys

from   vut.engine.bookkeeper.api   import Bookkeeper
from   vut.engine.bookkeeper.api import Store
from   vut.engine.bookkeeper.api   import TestIdDb, TestIdFault
from   ._follow                           import labels_renamed
from   ._exit                             import E_ExitCode

USAGE = ("usage: hwut.rename <old> <new> [<old> <new>...] [--yes] "
         "[--directory=<path>]\n"
         "       hwut.rename-choice <test> <old> <new> [...] [--yes]\n"
         "                          [--directory=<path>]")

#  The licence line and the rule are the FILE's, not the face's.
HELP = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
       + "\n\n" + USAGE


def _shown(store, path):
    """RETURN: str, the path as it reads from the test directory --
    'GOOD/x.stdout' and 'TMP/store/x.stdout' are DIFFERENT files and
    a basename alone would print them alike."""
    try:               return os.path.relpath(path, str(store.directory))
    except ValueError: return path


def move_tuple(store, test, choice, fresh_test, fresh_choice,
               whole_test_f):
    """
    RETURN: tuple[(str, str)], (from, to) for every recorded artefact
            of that key that STANDS -- nominals, candidates, sidecars
            and the coverage record. Sorted by source, so the
            announcement is stable.

    'whole_test_f' follows EVERY choice the book knows of the test:
    'hwut.rename' renames a test entire.

    The subjects are read from what LIES THERE, not from what a
    configuration says: a rename must reach a subject whose
    declaration has since been edited away, or it leaves an orphan
    under the old name.
    """
    #  THROUGH THE DOOR: 'choices()' already speaks None for the
    #  choiceless case, so the key spelling is the book's own business.
    recorded_choice_list = store.bookkeeper.choices(test)
    if whole_test_f:
        pair_list = [(c, c) for c in recorded_choice_list]
        if not pair_list: pair_list = [(choice, choice)]
    else:
        pair_list = [(choice, fresh_choice)]

    found = []
    for old_choice, new_choice in pair_list:
        for subject in ("stdout", "stderr"):
            candidate = store.candidate_path(test, old_choice, subject)
            fresh     = store.candidate_path(fresh_test, new_choice,
                                             subject)
            for suffix in ("", ".when"):
                if os.path.exists(str(candidate) + suffix):
                    found.append((str(candidate) + suffix,
                                  str(fresh) + suffix))
            for verb in ("raw_path", "timing_path"):
                a = str(getattr(store, verb)(test, old_choice, subject))
                b = str(getattr(store, verb)(fresh_test, new_choice,
                                             subject))
                if os.path.exists(a): found.append((a, b))
            nominal = str(store.nominal_path(test, old_choice, subject))
            if os.path.exists(nominal):
                found.append((nominal,
                              str(store.nominal_path(fresh_test,
                                                     new_choice,
                                                     subject))))
        a = str(store.bookkeeper.coverage_path(test, old_choice))
        if os.path.exists(a):
            found.append((a, str(store.bookkeeper.coverage_path(
                                     fresh_test, new_choice))))
    return tuple(sorted(set(found)))


def follow(store, test, choice, fresh_test, fresh_choice, whole_test_f,
           write):
    """
    RETURN: bool, True where every move succeeded; False where one
            failed -- announced by name, and the rest still attempted.

    THE ORDER: artefacts first, then the book, then the register. A
    crash between steps leaves files under the new name and a book
    that still says the old one, which the next run reports as a
    missing GOOD -- loud, and mendable by re-running the rename.
    """
    good_f = True
    for source, target in move_tuple(store, test, choice, fresh_test,
                                     fresh_choice, whole_test_f):
        try:
            os.makedirs(os.path.dirname(target), exist_ok=True)
            os.rename(source, target)
            write("    %s -> %s" % (_shown(store, source),
                                    _shown(store, target)))
        except OSError as error:
            write("    FAULT: %s -- %s" % (_shown(store, source), error))
            good_f = False

    try:
        if whole_test_f:
            moved = store.bookkeeper.rename_test(test, fresh_test)
        else:
            moved = store.bookkeeper.rename_choice(test, choice,
                                                   fresh_choice)
        write("    book entry: %s" % ("re-keyed" if moved is not None
                                      else "none stood"))
    except KeyError as error:
        write("    FAULT: book -- %s" % error)
        return False

    id_db = TestIdDb(str(store.directory))
    try:
        if whole_test_f:
            run_id = id_db.run_id_of(test)
            if run_id is None: write("    register: not registered")
            else:
                id_db.rename_app(run_id.app_id, fresh_test)
                write("    register: name follows; the id stands")
        else:
            run_id = id_db.run_id_of(test, choice)
            if run_id is None: write("    register: not registered")
            else:
                id_db.rename_choice(run_id.app_id, run_id.choice_id,
                                    fresh_choice)
                write("    register: choice name follows; the id stands")
    except TestIdFault as error:
        write("    FAULT: register -- %s" % error)
        good_f = False

    #  THE BOUNDARY RECORDS FOLLOW LAST ('services/_follow.py'): a
    #  crash above leaves an entry naming the old name -- loud, and
    #  findable -- never a record silently pointing at nothing.
    if not labels_renamed(str(store.directory), test, choice,
                          fresh_test, fresh_choice, whole_test_f,
                          write):
        good_f = False
    return good_f


def main(argv=None, write=None, read_line=None, choice_form_f=False):
    """
    RETURN: E_ExitCode, the exit status (E-1): OK where everything
            named was renamed or had nothing to rename, FAULT where a
            move failed, REFUSED where the command line cannot be read
            or a name collides, EMPTY where it names nothing.

    'choice_form_f' reads the words in TRIPLES -- '<test> <old> <new>'
    -- which is 'hwut.rename-choice'.
    """
    if write is None:     write     = print
    if read_line is None: read_line = sys.stdin.readline
    if argv is None:      argv      = sys.argv[1:]
    if "--help" in argv:
        write(HELP)
        return E_ExitCode.OK

    name      = "hwut.rename-choice" if choice_form_f else "hwut.rename"
    step      = 3 if choice_form_f else 2
    directory = "."
    yes_f     = False
    word_list = []
    unknown   = []
    for argument in argv:
        if   argument.startswith("--directory="):
            directory = argument[len("--directory="):]
        elif argument == "--yes":      yes_f = True
        elif argument.startswith("-"): unknown.append(argument)
        else:                          word_list.append(argument)
    if unknown:
        write("REFUSED: '%s' does not take: %s"
              % (name, ", ".join(sorted(unknown))))
        write(USAGE)
        return E_ExitCode.REFUSED
    if not os.path.isdir(directory):
        write("REFUSED: the directory '%s' does not exist" % directory)
        write(USAGE)
        return E_ExitCode.REFUSED
    if not word_list:
        write("EMPTY: '%s' names nothing to rename" % name)
        return E_ExitCode.EMPTY
    if len(word_list) % step != 0:
        write("REFUSED: '%s' takes %s -- %s -- and %d word(s) stand"
              % (name, "TRIPLES" if choice_form_f else "PAIRS",
                 "<test> <old> <new>" if choice_form_f
                 else "<old> <new>", len(word_list)))
        write(USAGE)
        return E_ExitCode.REFUSED

    target_list = []
    for i in range(0, len(word_list), step):
        if choice_form_f:
            target_list.append((word_list[i], word_list[i + 1],
                                word_list[i], word_list[i + 2]))
        else:
            target_list.append((word_list[i], None,
                                word_list[i + 1], None))

    store = Store(Bookkeeper(directory))
    recorded_test_set = set(store.bookkeeper.tests())

    #  A COLLISION IS REFUSED BEFORE ANYTHING MOVES: half a rename
    #  onto a live name is worse than none.
    for test, choice, fresh_test, fresh_choice in target_list:
        if not choice_form_f and fresh_test in recorded_test_set \
           and fresh_test != test:
            write("REFUSED: '%s' already stands in the book -- a rename "
                  "onto it would swallow its history" % fresh_test)
            return E_ExitCode.REFUSED
        if choice_form_f:
            if fresh_choice in store.bookkeeper.choices(test) \
               and fresh_choice != choice:
                write("REFUSED: '%s' already stands among the choices "
                      "of '%s'" % (fresh_choice, test))
                return E_ExitCode.REFUSED

    write("TO FOLLOW THE NEW NAME, in '%s':" % directory)
    total_n = 0
    for test, choice, fresh_test, fresh_choice in target_list:
        pair_tuple = move_tuple(store, test, choice, fresh_test,
                                fresh_choice, not choice_form_f)
        total_n   += len(pair_tuple)
        write("  %s%s -> %s%s -- %d file(s), the book entry, the "
              "register name"
              % (test, "" if choice is None else " " + choice,
                 fresh_test, "" if fresh_choice is None
                 else " " + fresh_choice, len(pair_tuple)))
        for source, target in pair_tuple:
            write("      %s -> %s" % (_shown(store, source),
                                      _shown(store, target)))
    if total_n == 0:
        write("  (no recorded artefact stands; the book and the "
              "register are still asked)")

    if not yes_f:
        write("")
        write("Proceed? [y/N] ")
        answer = (read_line() or "").strip().lower()
        if answer not in ("y", "yes"):
            write("NOTE: nothing was renamed")
            return E_ExitCode.OK

    good_f = True
    for test, choice, fresh_test, fresh_choice in target_list:
        write("%s%s:" % (test, "" if choice is None else " " + choice))
        if not follow(store, test, choice, fresh_test, fresh_choice,
                      not choice_form_f, write):
            good_f = False
    return E_ExitCode.OK if good_f else E_ExitCode.FAULT


if __name__ == "__main__":
    sys.exit(main())
