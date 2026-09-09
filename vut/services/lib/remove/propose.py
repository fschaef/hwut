# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
"""
hwut.remove.propose -- the test runs that have lost their ground, as a
file to read and hand back.

    hwut.remove.propose -o <file> [--directory=<path>]

REMOVES NOTHING. Walks the tree -- one directory with
'--directory=<path>' -- and writes, for every test run whose record no
longer has a test behind it:

    # app absent
    <dir>/<test-app> <choice>

    # choice not offered
    <dir>/<test-app> <choice>

    # nominal absent, book entry stands
    <dir>/<test-app> <choice>

The comment is TELEGRAPHIC: the reason in a few words, since fifty of
them are read as a list. Delete or '#' out what you want to keep, then

    hwut.remove.apply <file>

-------------------------------------------------------------------
WHAT IS PROPOSED
-------------------------------------------------------------------
    APP ABSENT          a nominal, candidate or book entry names a
                        test application that does not stand in the
                        directory. Its history is history of a program
                        that no longer exists -- OR THAT MOVED. Where
                        an application of that name stands elsewhere
                        in the tree, the reason says so:

                            # app absent, possibly moved to x/y/TEST

                        Then the record is not rubbish but STRANDED,
                        and 'adm/rescue_goods.py' writes the 'git mv'
                        to carry its nominal after the test. Delete
                        that line from the proposal; do not apply it.
    CHOICE NOT OFFERED  the application stands and is understood, and
                        does not name that choice. A reliable orphan:
                        the configuration was read.
    NOMINAL ABSENT      the book records the case but no nominal
                        stands for it -- a run without a pole. The
                        entry is bookkeeping about nothing.

WHAT IS NEVER PROPOSED. An application that STANDS but exploration
cannot see -- a header that stopped parsing, an 'hwut-info.dat' it
does not read, an 'ignore' glob -- is UNREACHABLE, not orphaned. Its
records are blessed work and the mending is in the configuration.
'hwut.sanitize' draws that line and this face keeps it ('orphans').

'-o <file>' IS REQUIRED: what cannot be judged -- a directory whose
exploration faulted -- goes to STDOUT, one line each, and never into
the file.

EXIT: OK where something was proposed, EMPTY where nothing has lost
its ground, REFUSED where '-o' is missing.
"""
import os
import sys

from vut.services._exit                       import E_ExitCode
from vut.services.sanitize                    import (offered_key_set,
                                                      record_key_of)
from vut.engine.bookkeeper.api                import (Bookkeeper,
                                                      GOOD_OWNED_FILE_TUPLE,
                                                      STORE_DIRECTORY_NAME,
                                                      nominal_stands_f)
from vut.engine.orchestrator.exploration      import selection
from vut.engine.orchestrator.exploration.task_list import SelectionError
from vut.engine.orchestrator.plan.wish        import parse_wish


def application_home_db(found):
    """
    RETURN: dict, BASE NAME of a test application -> list of the
            directories (relative to the run's root) exploration found
            it in. One walk of the selection already made. A name in
            several directories lists them all.

    THE INFRASTRUCTURE OF 'adm/rescue_goods.py', one level up: there
    the base names of GOOD files were mapped to their paths to find a
    nominal a directory split had stranded; here the base names of
    APPLICATIONS are, to tell a test that MOVED from one that DIED.
    """
    home_db = {}
    for where, result in found.result_db.items():
        for name in result.app_set.app_db:
            home_db.setdefault(name, []).append(where)
    return home_db


def lost_case_list(directory, app_set, home_db=None, here=None):
    """
    RETURN: list of (test, choice, reason) -- every case recorded under
            'directory' that has LOST ITS GROUND, each once, with the
            reason in a few words. 'choice' is None for a choice-less
            test.

    THE JUDGEMENT IS SANITIZE'S. 'offered_key_set' says what exploration
    offers; 'record_key_of' says what a file records. A case found on
    disk or in the book and not offered is lost -- UNLESS its
    application still stands, in which case it is unreachable, not
    orphaned, and is left alone (the guard 'hwut.sanitize' keeps for
    the same reason).

    A MOVE IS NAMED. Where the absent application stands in ANOTHER
    directory of the tree ('home_db'), the reason says so:

        # app absent, possibly moved to engine/coverage/readers/TEST

    -- and the reader decides between forgetting the record and
    carrying it after its test ('adm/rescue_goods.py' writes the
    'git mv' for the nominal). The proposal itself still proposes
    removal: it cannot know the move was meant.
    """
    offered = offered_key_set(app_set)
    if not offered: return []                 # nothing offered: judge nothing
    known_test_set = {test for test, _ in offered}
    found = {}

    def absent_reason(test):
        """RETURN: str, 'app absent', naming where else it stands."""
        elsewhere = [w for w in (home_db or {}).get(test, ())
                     if os.path.normpath(w) != os.path.normpath(here or "")]
        if not elsewhere: return "app absent"
        return "app absent, possibly moved to %s" % ", ".join(
                   sorted(os.path.normpath(w) for w in elsewhere))

    def note(test, choice, reason):
        """RETURN: None. First reason wins; a case is proposed once."""
        found.setdefault((test, choice), reason)

    #  -- the files ----------------------------------------------------
    for holder in ("GOOD", STORE_DIRECTORY_NAME, "OUT"):
        base = os.path.join(directory, holder)
        if not os.path.isdir(base): continue
        for name in sorted(os.listdir(base)):
            if name in GOOD_OWNED_FILE_TUPLE: continue
            key = record_key_of(name)
            if key is None: continue
            test, choice = key
            if test not in known_test_set:
                if os.path.exists(os.path.join(directory, test)):
                    continue                  # stands, unseen: unreachable
                note(test, choice, absent_reason(test))
            elif (test, choice) not in offered:
                note(test, choice, "choice not offered")

    #  -- the book -----------------------------------------------------
    bookkeeper = Bookkeeper(directory)
    for test in bookkeeper.tests():
        for choice in bookkeeper.choices(test):
            if test not in known_test_set:
                if os.path.exists(os.path.join(directory, test)): continue
                note(test, choice, absent_reason(test))
            elif (test, choice) not in offered:
                note(test, choice, "choice not offered")
            elif not nominal_stands_f(directory, test, choice):
                note(test, choice, "nominal absent, book entry stands")

    return sorted((test, choice, reason)
                  for (test, choice), reason in found.items())


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (see the module purpose).
    """
    if argv is None:  argv  = sys.argv[1:]
    if write is None: write = print
    if "--help" in argv:
        write(__doc__.strip())
        return E_ExitCode.OK

    file_name, directory = None, None
    skip_f = False
    for index, argument in enumerate(argv):
        if skip_f: skip_f = False; continue
        if argument in ("-o", "--output"):
            if index + 1 >= len(argv):
                write("REFUSED: '%s' wants a file name" % argument)
                return E_ExitCode.REFUSED
            file_name = argv[index + 1]; skip_f = True
        elif argument.startswith("--output="):
            file_name = argument[len("--output="):]
        elif argument.startswith("--directory="):
            directory = argument[len("--directory="):]
        else:
            write("REFUSED: 'hwut.remove.propose' does not take: %s"
                  % argument)
            return E_ExitCode.REFUSED
    if file_name is None:
        write("REFUSED: '-o <file>' is required -- the proposal is "
              "written there;")
        write("         what cannot be judged is written to stdout.")
        return E_ExitCode.REFUSED

    #  ONE FACE, BOTH DOORS: the tree by default, one directory named.
    wish, _ = parse_wish([])
    try:
        if directory is not None:
            found = selection.of_directory(directory, wish, None, base_f=True)
            root  = directory
        else:
            found = selection.of_tree(".", wish, None, base_f=True)
            root  = "."
    except SelectionError as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED

    #  WHERE ELSE A TEST OF THIS NAME STANDS: built once, over the
    #  whole selection, and asked per lost case.
    where_db = application_home_db(found)
    said_n = 0
    try:
        with open(file_name, "w", encoding="utf-8") as handle:
            def put(text):
                """RETURN: None. One line into the proposal file."""
                handle.write(text + "\n")
            put("#  proposal -- delete or '#' out what you want to KEEP, "
                "then hand it back:")
            put("#      hwut.remove.apply <this file>")
            put("")
            for where, result in found.result_db.items():
                whole = os.path.normpath(os.path.join(root, where))
                shown = os.path.relpath(whole, os.getcwd())
                if result.fault_list:
                    #  A DIRECTORY THAT WOULD NOT EXPLORE CANNOT BE
                    #  JUDGED: nothing in it is offered, so everything
                    #  would look lost. Said on stdout, never proposed.
                    write("FAULT(%s) exploration failed -- not judged"
                          % shown)
                    continue
                for test, choice, reason in lost_case_list(whole,
                                                           result.app_set,
                                                           where_db, where):
                    put("# %s" % reason)
                    put("%s%s" % (os.path.join(shown, test),
                                  "" if choice is None else " " + choice))
                    put("")
                    said_n += 1
            if said_n == 0:
                put("#  nothing to propose: every recorded case has a "
                    "test behind it")
    except OSError as error:
        write("REFUSED: %s" % error)
        return E_ExitCode.REFUSED
    return E_ExitCode.OK if said_n else E_ExitCode.EMPTY


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded("hwut.remove.propose", main))
