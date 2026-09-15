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
    and where they stand.

    'aspirant_f' is B-14's standing, MEASURED off 'GOOD/' and not
    remembered: True where no nominal stood, so the nominal text is the
    opening mirror and a commit is a FIRST BLESSING (E-51/E-59), never
    a merge.
    """
    __slots__ = ("where", "test", "choice", "subject_text",
                 "nominal_text", "setup", "candidate_path",
                 "nominal_path", "aspirant_f")

    def __init__(self, where, test, choice, subject_text, nominal_text,
                 setup, candidate_path, nominal_path, aspirant_f=False):
        self.where = where;               self.test = test
        self.choice = choice;             self.subject_text = subject_text
        self.nominal_text = nominal_text; self.setup = setup
        self.candidate_path = candidate_path
        self.nominal_path   = nominal_path
        self.aspirant_f     = aspirant_f

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

    ASPIRANTS STAND FIRST in [0] (B-14), walk order within the group.

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
            if not out_path.exists() and not good_path.exists():
                #  A FIRST ACCEPTANCE HAS NO CANDIDATE YET: 'hwut.run'
                #  refuses to run what nobody accepted, so the candidate
                #  is made HERE, the way 'hwut.accept' refreshes (E-40)
                #  -- through provision, held, recorded and booked as a
                #  run books it.
                configuration = config_db.get(test)
                if configuration is not None:
                    from vut.engine.operations         import subject_provision
                    from vut.engine.operations.session import run_test, Request
                    try:
                        _, decision = subject_provision.provider_of(
                                          configuration, store, choice,
                                          refresh=True, force_run=False)
                        if decision.what is subject_provision.E_Decision.PROVIDE:
                            asyncio.run(run_test(configuration,
                                                 Request(choice=choice, record=True),
                                                 bookkeeper=store.bookkeeper))
                    except Exception:                          # noqa: BLE001
                        pass
            if not out_path.exists():  no_run_n += 1; continue
            try:
                subject_text = io.open(str(out_path),  encoding="utf-8").read()
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
            aspirant_f = not good_path.exists()
            if good_path.exists():
                try:
                    nominal_text = io.open(str(good_path), encoding="utf-8").read()
                except (OSError, UnicodeDecodeError):
                    continue
            else:
                #  NO NOMINAL STANDS: A FIRST ACCEPTANCE (E-60). The
                #  session opens on the candidate's SHAPE with nothing
                #  decided -- the mirror 'accept_first' builds -- and
                #  every take lifts a decision out of it. Skipping the
                #  case here was the old 'hwut.accept first' rule.
                from vut.services.accept_first import opening_nominal
                nominal_text = opening_nominal(setup, subject_text, force_f=False)
                if nominal_text is None: no_nom_n += 1; continue
            judged_n += 1
            equivalent_f = asyncio.run(is_equivalent(
                               setup, io.StringIO(subject_text),
                               io.StringIO(nominal_text)))
            if equivalent_f: continue
            key_list.append(DifferingKey(where, test, choice, subject_text,
                                         nominal_text, setup,
                                         str(out_path), str(good_path),
                                         aspirant_f=aspirant_f))
    #  ASPIRANTS FIRST (B-14). A test the book knows and nobody has
    #  accepted is playable, not runnable; its accept is the act that
    #  makes it a member, and a person working a list wants the
    #  first blessings before the changes. Walk order is kept WITHIN
    #  each group, so nothing else is reordered.
    key_list = [k for k in key_list if k.aspirant_f] \
             + [k for k in key_list if not k.aspirant_f]
    if no_run_n: write("NOTE: %d selected case(s) never ran -- no "
                       "candidate stands" % no_run_n)
    if no_nom_n: write("NOTE: %d selected case(s) never COMPLETED -- no "
                       "'<hwut-end>' -- and cannot be accepted" % no_nom_n)
    return key_list, judged_n


#  'choose' moved to 'services/lib/checklist.py' (E-67): one menu,
#  one behaviour, shared by every face that offers a list.
