"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.remove' COMMAND LINE -- a test, or one choice of it,
         FORGOTTEN: its nominals, its candidates, its book entry and
         its register id.

    hwut.remove          <test> [<test>...] [--yes] [--directory=<path>]
    hwut.remove-choice   <test> <choice> [...] [--yes] [--directory=<path>]

WHAT REMOVAL IS FOR. A test whose subject has genuinely changed has no
nominal worth keeping -- the old pole is not the centre of the new
cluster, it is a fact about a program that no longer exists. And a
STAINED test (a test that switched results, and is therefore not run at
all until proven steady) sometimes cannot wait for the proof. Removal
is the urgent way out: forget everything recorded, run afresh, accept
afresh. It says 'this test has no history', which is TRUE after it,
and never 'this test is fine', which nothing here can say.

WHAT IS FORGOTTEN, in this order, each step announced:

    NOMINALS     'GOOD/<key>' per subject -- the poles themselves.
    CANDIDATES   'TMP/store/<key>' and every sidecar beside it: the
                 freshness stamp, the raw stream, the cadence, the
                 coverage record.
    THE BOOK     'GOOD/result_db.csv': the recorded runs, the stderr
                 note, and THE STAIN with them.
    THE REGISTER the id, retired -- never reissued, so no later test
                 inherits an old test's coverage history.

WHAT IS NOT TOUCHED: the test application itself, its 'hwut.conf', and
anything under 'OUT/'. Removal forgets what the FRAMEWORK recorded; the
author's own files are the author's.

IT ASKS FIRST. What is removed cannot be recovered from here -- a
nominal is a blessed artefact and its loss is a real loss -- so the
whole list is shown and confirmed, unless '--yes' stands.

A TEST THAT IS NOT IN THE BOOK is not an error: there was nothing to
forget, and the face says so and moves on. Refusing would make removal
depend on the very history it exists to discard.

EXIT STATUS (E-1, services/_exit.py):
    0  everything named was forgotten, or had nothing to forget
    1  something named could not be removed
    2  the command line cannot be read
    3  the command line reads, and names nothing
______________________________________________________________________________
"""
import os
import sys

from   vut.engine.bookkeeper.api   import Bookkeeper
from   vut.engine.bookkeeper.api import Store
from   vut.engine.bookkeeper.api   import TestIdDb, TestIdFault
from   ._follow                           import labels_forgotten
from   ._exit                             import E_ExitCode

USAGE = ("usage: hwut.remove <test> [<test>...] [--yes] "
         "[--directory=<path>]\n"
         "       hwut.remove-choice <test> <choice> [<test> <choice>...] "
         "[--yes]\n"
         "                          [--directory=<path>]")

#  The licence line and the rule are the FILE's, not the face's.
HELP = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
       + "\n\n" + USAGE


def sidecar_path_tuple(store, test, choice, subject):
    """
    YIELD: [0] str  a path this key occupies, whether it stands or not

    THE STORE NAMES THEM, never this face: the candidate, its freshness
    stamp, the raw stream, the cadence. A caller filters for what
    exists; naming a path that does not stand is not an error here.
    """
    #  THE CANDIDATE STANDS IN 'OUT/'; ITS SIDECARS ON THE STORE'S
    #  GROUND. Each is asked of the bookkeeper, which is the one place
    #  a path is spelt -- a sidecar is no longer 'the candidate plus a
    #  suffix'.
    yield str(store.candidate_path(test, choice, subject))
    yield str(store.freshness_path(test, choice, subject))
    yield str(store.raw_path(test, choice, subject))
    yield str(store.timing_path(test, choice, subject))


def victim_tuple(store, test, choice, whole_test_f):
    """
    RETURN: tuple[str], every path the framework recorded for that key
            and that STANDS -- nominals, candidates, sidecars, and the
            coverage record. Sorted, so the announcement is stable.

    'whole_test_f' takes every choice the book knows of the test, not
    the one named: 'hwut.remove' forgets a test entire.

    The subjects are read from what LIES THERE, not from what a
    configuration says: removal must reach a subject whose declaration
    has since been edited away, or it leaves an orphan.
    """
    #  THROUGH THE DOOR: 'choices()' speaks None for the choiceless
    #  case; the book's key spelling is its own.
    if whole_test_f:
        choice_list = store.bookkeeper.choices(test)
        if not choice_list: choice_list = [choice]
    else:
        choice_list = [choice]

    found = set()
    for one in choice_list:
        witness = str(store.error_witness_path(test, one))
        if os.path.exists(witness): found.add(witness)
        for subject in ("stdout",):
            for path in sidecar_path_tuple(store, test, one, subject):
                if os.path.exists(path): found.add(path)
            nominal = str(store.nominal_path(test, one, subject))
            if os.path.exists(nominal): found.add(nominal)
        coverage = store.bookkeeper.coverage_path(test, one)
        if os.path.exists(coverage): found.add(str(coverage))
    return tuple(sorted(found))


def _shown(store, path):
    """RETURN: str, the path as it reads from the test directory --
    'GOOD/x.stdout' and 'TMP/store/x.stdout' are DIFFERENT files and
    a basename alone would print them alike."""
    try:    return os.path.relpath(path, str(store.directory))
    except ValueError: return path


def forget(store, test, choice, whole_test_f, write):
    """
    RETURN: bool, True where everything named was forgotten; False
            where a path stood and could not be unlinked -- announced
            by name, and the rest still attempted.

    THE ORDER IS THE DOCSTRING'S: artefacts first, then the book, then
    the register. A crash between steps leaves LESS history than
    before, never a book pointing at files that are gone.
    """
    good_f = True
    for path in victim_tuple(store, test, choice, whole_test_f):
        try:
            os.unlink(path)
            write("    forgotten: %s" % _shown(store, path))
        except OSError as error:
            write("    FAULT: %s -- %s" % (_shown(store, path), error))
            good_f = False

    if whole_test_f: gone = store.bookkeeper.remove_test(test)
    else:            gone = store.bookkeeper.remove_choice(test, choice)
    write("    book entry: %s" % ("removed" if gone is not None
                                  else "none stood"))

    id_db = TestIdDb(str(store.directory))
    try:
        if whole_test_f:
            run_id = id_db.run_id_of(test)
            app_id = None if run_id is None else run_id.app_id
            if app_id is not None:
                id_db.remove_app(app_id)
                write("    register: id retired")
            else:
                write("    register: not registered")
        else:
            run_id = id_db.run_id_of(test, choice)
            if run_id is not None:
                id_db.remove_choice(run_id.app_id, run_id.choice_id)
                write("    register: choice id retired")
            else:
                write("    register: not registered")
    except TestIdFault as error:
        write("    FAULT: register -- %s" % error)
        good_f = False

    #  THE BOUNDARY RECORDS FOLLOW LAST ('services/_follow.py'),
    #  symmetric with the book and the register (E-12): a crash above
    #  leaves an entry 'hwut.sanitize --orphans' can find -- never a
    #  record silently pointing at nothing.
    if not labels_forgotten(str(store.directory), test, choice,
                            whole_test_f, write):
        good_f = False
    return good_f


def main(argv=None, write=None, read_line=None, choice_form_f=False):
    """
    RETURN: E_ExitCode, the exit status (E-1): OK where everything
            named was forgotten or had nothing to forget, FAULT where
            a path stood and could not be unlinked, REFUSED where the
            command line cannot be read, EMPTY where it names nothing.

    'choice_form_f' reads the words in PAIRS -- '<test> <choice>' --
    which is 'hwut.remove-choice'. Two faces, one module: they differ
    in what a word means and in nothing else.
    """
    if write is None:     write     = print
    if read_line is None: read_line = sys.stdin.readline
    if argv is None:      argv      = sys.argv[1:]
    if "--help" in argv:
        write(HELP)
        return E_ExitCode.OK

    name        = "hwut.remove-choice" if choice_form_f else "hwut.remove"
    directory   = "."
    yes_f       = False
    word_list   = []
    unknown     = []
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
        write("EMPTY: '%s' names nothing to remove" % name)
        return E_ExitCode.EMPTY
    if choice_form_f and len(word_list) % 2 != 0:
        write("REFUSED: 'hwut.remove-choice' takes PAIRS -- "
              "<test> <choice> -- and %d word(s) stand"
              % len(word_list))
        write(USAGE)
        return E_ExitCode.REFUSED

    if choice_form_f:
        target_list = [(word_list[i], word_list[i + 1])
                       for i in range(0, len(word_list), 2)]
    else:
        target_list = [(word, None) for word in word_list]

    store = Store(Bookkeeper(directory))

    #  WHAT WILL BE LOST, SHOWN BEFORE IT IS. A nominal is a blessed
    #  artefact; its removal is a real loss and is never a surprise.
    write("TO BE FORGOTTEN, in '%s':" % directory)
    total_n = 0
    for test, choice in target_list:
        path_tuple = victim_tuple(store, test, choice, not choice_form_f)
        total_n   += len(path_tuple)
        write("  %s%s -- %d file(s), the book entry, the register id"
              % (test, "" if choice is None else " " + choice,
                 len(path_tuple)))
        for path in path_tuple:
            write("      %s" % _shown(store, path))
    if total_n == 0:
        write("  (no recorded artefact stands; the book and the "
              "register are still asked)")

    if not yes_f:
        write("")
        write("This cannot be undone here. Proceed? [y/N] ")
        answer = (read_line() or "").strip().lower()
        if answer not in ("y", "yes"):
            write("NOTE: nothing was removed")
            return E_ExitCode.OK

    good_f = True
    for test, choice in target_list:
        write("%s%s:" % (test, "" if choice is None else " " + choice))
        if not forget(store, test, choice, not choice_form_f, write):
            good_f = False
    return E_ExitCode.OK if good_f else E_ExitCode.FAULT


if __name__ == "__main__":
    sys.exit(main())
