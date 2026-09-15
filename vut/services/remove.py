"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.remove' COMMAND LINE -- a test, or one choice of it,
         FORGOTTEN: its nominals, its candidates, its book entry and
         its register id.

    hwut.remove <test>            [--dont-ask] [--directory=<path>]
    hwut.remove <test> <choice>   [--dont-ask] [--directory=<path>]

THE WORDS ARE EVERY FACE'S (E-53): one word names a test, two name a
test and one of its choices, and a word carrying a path enters its
directory (E-47) -- as on 'hwut.rename', 'hwut.diff', 'hwut.report.details'.
'hwut.remove-choice' is gone: it existed only because this face read a
LIST OF TESTS, so 'hwut.remove a.sh one' meant two tests where every
other face means a test and a choice. MANY AT ONCE is
'hwut.remove.propose' and 'hwut.remove.apply', which is what that pair
is for.

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
    THE BOOK     'GOOD/book.csv': the recorded runs, the stderr
                 note, and THE STAIN with them.
    THE REGISTER the id, retired -- never reissued, so no later test
                 inherits an old test's coverage history.

WHAT IS NOT TOUCHED: the test application itself, its 'hwut.conf', and
anything under 'OUT/'. Removal forgets what the FRAMEWORK recorded; the
author's own files are the author's.

IT ASKS FIRST. What is removed cannot be recovered from here -- a
nominal is a blessed artefact and its loss is a real loss -- so the
whole list is shown and confirmed, unless '--dont-ask' stands.

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
from   ._follow                           import labels_forgotten
from   ._exit                             import E_ExitCode
from   ._target                           import split_words, TargetError

USAGE = ("usage: hwut.remove <test> [<choice>] [--dont-ask] "
         "[--directory=<path>]")

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

    #  THE BOOK AND THE REGISTER IN ONE ACT (B-9): the bookkeeper
    #  forgets the entry and retires the id under one lock; the face
    #  reads first, so it can say what stood.
    registered_f = store.bookkeeper.run_id_of(
                       test, None if whole_test_f else choice) is not None
    if whole_test_f: gone = store.bookkeeper.remove_test(test)
    else:            gone = store.bookkeeper.remove_choice(test, choice)
    write("    book entry: %s" % ("removed" if gone is not None
                                  else "none stood"))
    write("    register: %s" % (("id retired" if whole_test_f
                                 else "choice id retired")
                                if registered_f else "not registered"))

    #  THE BOUNDARY RECORDS FOLLOW LAST ('services/_follow.py'),
    #  symmetric with the book and the register (E-12): a crash above
    #  leaves an entry 'hwut.sanitize --orphans' can find -- never a
    #  record silently pointing at nothing.
    if not labels_forgotten(str(store.directory), test, choice,
                            whole_test_f, write):
        good_f = False
    return good_f


def main(argv=None, write=None, read_line=None):
    """
    RETURN: E_ExitCode, the exit status (E-1): OK where everything
            named was forgotten or had nothing to forget, FAULT where
            a path stood and could not be unlinked, REFUSED where the
            command line cannot be read, EMPTY where it names nothing.

    ONE WORD is a test, TWO are a test and one of its choices (E-53);
    a third is refused, and several tests are 'hwut.remove.propose'
    and 'hwut.remove.apply'.
    """
    if write is None:     write     = print
    if read_line is None: read_line = sys.stdin.readline
    if argv is None:      argv      = sys.argv[1:]
    if "--help" in argv:
        write(HELP)
        return E_ExitCode.OK

    name        = "hwut.remove"
    directory   = "."
    yes_f       = False
    word_list   = []
    unknown     = []
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
            return E_ExitCode.REFUSED
        elif argument.startswith("-"): unknown.append(argument)
        else:                          word_list.append(argument)
    if unknown:
        write("REFUSED: '%s' does not take: %s"
              % (name, ", ".join(sorted(unknown))))
        write(USAGE)
        return E_ExitCode.REFUSED
    #  A TEST NAMED BY PATH stands in the directory the path names
    #  ('services/_target.py'): 'a/TEST/keep.sh' is 'keep.sh' in
    #  'a/TEST', on this face as on every other.
    try:
        directory, word_list = split_words(word_list, directory)
    except TargetError as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    if not os.path.isdir(directory):
        write("REFUSED: the directory '%s' does not exist" % directory)
        write(USAGE)
        return E_ExitCode.REFUSED
    if not word_list:
        write("EMPTY: '%s' names nothing to remove" % name)
        return E_ExitCode.EMPTY
    #  ONE WORD IS A TEST, TWO ARE A TEST AND A CHOICE (E-53). A third
    #  is refused by name rather than read as another test: that
    #  reading is what 'hwut.remove-choice' existed to work around,
    #  and what forgot a whole test where one choice was meant.
    if len(word_list) > 2:
        write("REFUSED: 'hwut.remove' takes '<test>' or "
              "'<test> <choice>' -- %d words stand. For several tests: "
              "'hwut.remove.propose', then 'hwut.remove.apply'"
              % len(word_list))
        write(USAGE)
        return E_ExitCode.REFUSED

    choice_form_f = len(word_list) == 2
    target_list   = [(word_list[0],
                      word_list[1] if choice_form_f else None)]

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
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ._exit import guarded
    sys.exit(guarded("hwut.remove", main))
