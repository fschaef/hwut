# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
"""
______________________________________________________________________________
PURPOSE: THE CASES A WISH SELECTS, WITH THEIR STREAMS -- the one block
         every store-reading face runs between its words and its work
         ('hwut.accept', 'hwut.accept.interactive', 'hwut.diff'; E-50,
         E-51).

    entered path -> directory exists -> the climb (ascended_spec)
      -> the wish with its targets -> the labels view -> selection
      (one directory under '--directory', the tree otherwise)
      -> the cases grouped by the directory they were found in

'differing_keys' then measures, per (test, choice), whether the stdout
candidate and the nominal are EQUIVALENT under the choice's own compare
setup -- the engine's verdict, taken NOW, not the book's memory -- and
returns the keys that differ, with both texts in hand.
______________________________________________________________________________
"""
import io
import os
import asyncio

from   vut.engine.orchestrator.exploration.tree_explorer import (
                                                    RootConfMissing,
                                                    ascended_spec)
from   vut.engine.orchestrator.exploration.task_list   import SelectionError
from   vut.engine.orchestrator.exploration            import selection
from   vut.engine.orchestrator.plan.wish               import with_targets
from   vut.engine.orchestrator.run.adapter             import \
                                                       test_configuration_of
from   vut.engine.bookkeeper.api                      import Store
from   vut.services.lib.labels                        import view_at
from   vut.services.lib.labels._file                  import LabelFileError
from   ._target                                       import entered
from   ._exit                                         import E_ExitCode


class Selected:
    """What a wish selected, ready to be read.

        directory    absolute; the one entered or said
        where_list   the directories cases were found in, walk order,
                     relative to 'directory'
        case_db      where -> [case]      (exploration's CTestCase)
        found        the selection itself (result_db, bookkeeper_db)
    """
    __slots__ = ("directory", "where_list", "case_db", "found")

    def __init__(self, directory, where_list, case_db, found):
        self.directory  = directory
        self.where_list = where_list
        self.case_db    = case_db
        self.found      = found

    def store_of(self, where):
        """RETURN: Store, over the bookkeeper of that directory; None
        where the selection has none for it."""
        bookkeeper = self.found.bookkeeper_db.get(where)
        return None if bookkeeper is None else Store(bookkeeper)

    def whole(self, where):
        """RETURN: str, the directory's absolute path."""
        return os.path.normpath(os.path.join(self.directory, where))


def select(wish, word_list, directory, directory_said_f, write, usage):
    """
    RETURN: [0] Selected, what the wish and the words name.
                None, where they refuse to be read or the selection
                cannot be made -- the refusal is written.
            [1] E_ExitCode, REFUSED or FAULT where [0] is None; OK else.
    """
    found = entered(word_list, directory, write, usage)
    if found is None: return None, E_ExitCode.REFUSED
    directory, word_list = found
    if not os.path.isdir(directory):
        write("REFUSED: the directory '%s' does not exist" % directory)
        write(usage)
        return None, E_ExitCode.REFUSED
    try:
        inherited, ascent_fault_list = ascended_spec(directory)
    except RootConfMissing as error:
        write("REFUSED: %s" % error)
        return None, E_ExitCode.REFUSED
    for fault in ascent_fault_list:
        write(str(fault))
    wish      = with_targets(wish, word_list)
    directory = os.path.abspath(directory)
    try:
        label_view = view_at(directory)
    except LabelFileError as error:
        write("FAULT: %s" % error)
        return None, E_ExitCode.FAULT
    try:
        if directory_said_f:
            found = selection.of_directory(directory, wish, label_view,
                                           inherited=inherited,
                                           base_f=True)
        else:
            found = selection.of_tree(directory, wish, label_view,
                                      base_f=True)
        for fault in found.fault_tuple:  write("FAULT: %s" % fault)
        for text in found.warning_tuple: write(text)
    except SelectionError as error:
        write("REFUSED: %s" % error)
        return None, E_ExitCode.REFUSED
    where_list, case_db = [], {}
    for entry in found.case_list:
        where = entry.directory
        if where not in case_db:
            where_list.append(where); case_db[where] = []
        case_db[where].append(entry.case)
    return Selected(directory, where_list, case_db, found), E_ExitCode.OK


class DifferingKey:
    """One (test, choice) whose stdout candidate is NOT equivalent to
    its nominal -- with both texts, the compare setup that judged them,
    and where they stand."""
    __slots__ = ("where", "test", "choice", "subject_text",
                 "nominal_text", "setup", "candidate_path",
                 "nominal_path")

    def __init__(self, where, test, choice, subject_text, nominal_text,
                 setup, candidate_path, nominal_path):
        self.where = where;               self.test = test
        self.choice = choice;             self.subject_text = subject_text
        self.nominal_text = nominal_text; self.setup = setup
        self.candidate_path = candidate_path
        self.nominal_path   = nominal_path

    @property
    def name(self):
        """RETURN: str, 'test [choice]' as the eye reads it."""
        return self.test if self.choice is None \
               else "%s %s" % (self.test, self.choice)

    @property
    def label(self):
        """RETURN: str, the name with its directory where the selection
        spans more than one."""
        return self.name if self.where in (".", "") \
               else "%s/%s" % (self.where, self.name)


def differing_keys(selected, write):
    """
    RETURN: [0] list[DifferingKey], every selected (test, choice) whose
                stdout candidate stands, whose nominal stands, and
                which compare's engine judges NOT equivalent under the
                choice's setup; walk order.
            [1] int, how many selected cases had BOTH streams and were
                judged -- so a caller can say 'n of m differ'.

    A case without a candidate (never run) or without a nominal
    (never accepted) is not a difference to show; it is skipped, and
    the skip is said once per kind.
    """
    from vut.engine.compare.api import is_equivalent, Configuration
    key_list  = []
    judged_n  = 0
    no_run_n  = 0
    no_nom_n  = 0
    for where in selected.where_list:
        result = selected.found.result_db.get(where)
        store  = selected.store_of(where)
        if result is None or store is None: continue
        whole  = selected.whole(where)
        language_setup = result.app_set.directory_spec.language_setup
        config_db = {}
        for name, app in result.app_set.app_db.items():
            try:
                config_db[name] = test_configuration_of(
                                      app, whole, language_setup=language_setup)
            except Exception:
                config_db[name] = None
        for case in selected.case_db[where]:
            test, choice = case.source_file, case.choice
            out_path  = store.bookkeeper.candidate_path(test, choice, "stdout")
            good_path = store.bookkeeper.nominal_path(test, choice, "stdout")
            if not out_path.exists():  no_run_n += 1; continue
            if not good_path.exists(): no_nom_n += 1; continue
            try:
                subject_text = io.open(str(out_path),  encoding="utf-8").read()
                nominal_text = io.open(str(good_path), encoding="utf-8").read()
            except (OSError, UnicodeDecodeError):
                continue
            configuration = config_db.get(test)
            setup = None
            if configuration is not None:
                try:
                    setup = configuration.choice_configuration(choice).compare
                except (KeyError, AttributeError):
                    setup = None
            if setup is None: setup = Configuration()
            judged_n += 1
            equivalent_f = asyncio.run(is_equivalent(
                               setup, io.StringIO(subject_text),
                               io.StringIO(nominal_text)))
            if equivalent_f: continue
            key_list.append(DifferingKey(where, test, choice, subject_text,
                                         nominal_text, setup,
                                         str(out_path), str(good_path)))
    if no_run_n: write("NOTE: %d selected case(s) never ran -- no "
                       "candidate stands" % no_run_n)
    if no_nom_n: write("NOTE: %d selected case(s) have no nominal -- "
                       "'hwut.accept' first" % no_nom_n)
    return key_list, judged_n


def choose(key_list, write, read_line, all_f=False, yes_f=False):
    """
    RETURN: list[DifferingKey], the keys the author marked -- every key
            where there is one, or '--all'/'--yes' was said; an empty
            list where the author took none ('q', EOF).

    THE MENU, in the terminal, no dependency: every key starts marked;
    a number toggles it; Enter takes the marked set; 'a' marks all,
    'n' none, 'q' takes none.

        differing cases -- toggle with a number, Enter to go, q to quit
          [X]  1  test-a.sh one
          [X]  2  test-a.sh two
          [ ]  3  test-b.sh
        >
    """
    if len(key_list) <= 1 or all_f or yes_f: return list(key_list)
    marked = [True] * len(key_list)
    while True:
        write("differing cases -- toggle with a number, Enter to go, "
              "q to quit")
        for n, (key, mark_f) in enumerate(zip(key_list, marked), start=1):
            write("  [%s] %2d  %s" % ("X" if mark_f else " ", n, key.label))
        write("> ")
        try:
            answer = (read_line() or "").strip().lower()
        except EOFError:
            answer = "q"
        if answer == "":  break
        if answer == "q": return []
        if answer == "a": marked = [True]  * len(key_list); continue
        if answer == "n": marked = [False] * len(key_list); continue
        for word in answer.replace(",", " ").split():
            if word.isdigit() and 1 <= int(word) <= len(key_list):
                marked[int(word) - 1] = not marked[int(word) - 1]
            else:
                write("  (not a number in 1..%d: '%s')" % (len(key_list), word))
    return [key for key, mark_f in zip(key_list, marked) if mark_f]
