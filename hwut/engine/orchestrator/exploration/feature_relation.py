"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE LINKS OF THE TEST RUNS TO THE FEATURES -- per TEST directory,
         knowing no forest above it (spec 43 section 4):

    a test's '@hwut { }' block       'features = [...]': the feature ids
                                     the test run proves

    relation_of_tree(root)           -> CRelation

WHAT A FEATURE IS AND WHERE IT STANDS is the forest's and the doc file's
('feature_forest', 'feature_doc'); a TEST directory defines nothing any
more (spec 43 section 0). 'feature_view' joins the three.

THE RELATION
    A test run is addressed as '<path>/<test> [<choice>]', the path
    RELATIVE to the root asked -- composed at the moment of asking, and
    stored nowhere. A link names a feature id, wherever the feature is
    documented and whichever directory the test stands in. The verdict of
    a run is what 'GOOD/book.csv' says: PASS, FAIL, the verdict's own
    name, NO VERDICT.
______________________________________________________________________________
"""
import os
import posixpath
from   dataclasses import dataclass

from ...bookkeeper.api import Bookkeeper
from .tree_explorer    import explore_tree_stream, forest_gate_of


#  WHAT THE BOOK SAYS OF A LINKED RUN, as the relation spells it.
PASS       = "PASS"
FAIL       = "FAIL"
NO_VERDICT = "NO VERDICT"

#  THE TEST DIRECTORY'S NAME.
TEST_NAME = "TEST"


@dataclass(frozen=True)
class CRun:
    """One linked test run, its TEST directory 'path' (as the relation
    addresses it), and what 'GOOD/book.csv' says of it: 'PASS', 'FAIL',
    'ASPIRANT' or 'NO VERDICT'."""
    test:    str
    choice:  str | None
    verdict: str
    path:    str = "."


@dataclass(frozen=True)
class CTestDirectory:
    """One TEST directory in the relation. 'link_tuple' holds every link
    of its runs, (test, choice, feature id), walk order; 'unlinked_tuple'
    the runs that link to no feature."""
    path:            str
    link_tuple:      tuple = ()        # of (test, choice, feature id)
    unlinked_tuple:  tuple = ()        # of (test, choice)
    run_tuple:       tuple = ()        # of (test, choice): EVERY run of
                                       #  the directory, walk order
    app_tuple:       tuple = ()        # of (test, title, doc): every
                                       #  application, walk order
    verdict_db:      dict  = None      # (test, choice) -> verdict text,
                                       #  for every run of the directory

    def linking_f(self):
        """RETURN: True, a run of the directory links a feature: it takes
        part in the relation, and a run beside it linking none is
        NONSENSE?; False else."""
        return bool(self.link_tuple)


@dataclass(frozen=True)
class CRelation:
    """The relation of one tree: its TEST directories by path, relative to
    the root asked, '/'-separated; '.' is the root itself."""
    test_directory_db: dict            # path -> CTestDirectory
    root_name:         str = ""        # the name of the directory asked

    def run_db(self):
        """RETURN: dict, feature id -> tuple of CRun, every run linking
        it, in walk order (directories sorted)."""
        result = {}
        for path in sorted(self.test_directory_db):
            each = self.test_directory_db[path]
            for test, choice, feature_id in each.link_tuple:
                result.setdefault(feature_id, []).append(
                    CRun(test, choice, each.verdict_db[(test, choice)], path))
        return {key: tuple(value) for key, value in result.items()}

def _verdict_text(bookkeeper, test, choice):
    """RETURN: str, what 'GOOD/book.csv' says of that run: 'PASS',
    'FAIL', the verdict's own name else ('ASPIRANT'), 'NO VERDICT'
    where the book holds none."""
    entry   = bookkeeper.result(test, choice)
    verdict = None if entry is None else entry.get("verdict")
    if verdict is None:    return NO_VERDICT
    if verdict.passed_f:   return PASS
    if verdict.failed_f:   return FAIL
    return verdict.name


def document_place(path, document):
    """
    RETURN: [0] str, where a feature's document stands, addressed from
                the directory the relation was asked in ('/' between);
                the document itself where it is a URL
            [1] str, its '#<anchor>', '' where it names none
            [2] bool, True where it is a URL ('<scheme>://...'), which
                nothing here looks up

    'path' is the directory whose file states the document, as the
    relation addresses it; 'document' what the file states, a path from
    that directory.
    """
    if "://" in document: return document, "", True
    name, mark, anchor = document.partition("#")
    place = posixpath.normpath(posixpath.join(path, name))
    return place, mark + anchor, False


def linked_name_tuple(parameters):
    """RETURN: tuple of str, the feature ids a test run with these
    'TestParameters' links to; empty where it links to none."""
    return tuple(parameters.features or ())


def test_directory_of(directory, path, app_set):
    """RETURN: CTestDirectory, the links inside one TEST directory:
    'directory' where it stands, 'path' how it is addressed, 'app_set'
    what exploration found there."""
    bookkeeper = Bookkeeper(directory)
    link_list, unlinked, every, app_list, verdict_db = [], [], [], [], {}
    for app in app_set:
        app_list.append((app.source_file, app.title,
                         getattr(app, "doc", None)))
        for choice, parameters in app.choice_db.items():
            every.append((app.source_file, choice))
            verdict_db[(app.source_file, choice)] = _verdict_text(
                bookkeeper, app.source_file, choice)
            name_tuple = linked_name_tuple(parameters)
            if not name_tuple:
                unlinked.append((app.source_file, choice))
            for name in name_tuple:
                link_list.append((app.source_file, choice, name))
    return CTestDirectory(path, tuple(link_list), tuple(unlinked),
                          tuple(every), tuple(app_list), verdict_db)


def relation_of_tree(root, interview_runner=None, fault_list=None):
    """
    RETURN: CRelation, every TEST directory below 'root' with its runs
            and their links -- a bubble below with no forest of its own
            entered (its configuration its own), one with a forest of its
            own not ('forest_gate_of').

    Raises RootConfMissing where no 'hwut-root.conf' bounds the tree.
    """
    return relation_of_exploration(
        root, explore_tree_stream(root, interview_runner, fault_list,
                                  boundary_f=False,
                                  bubble_gate=forest_gate_of(root)))


def relation_of_exploration(root, pair_iterable):
    """RETURN: CRelation, as 'relation_of_tree' answers it, from an
    exploration already made: 'pair_iterable' yields (TEST directory
    relative to 'root', ExplorationResult)."""
    root = os.path.abspath(root)
    test_directory_db = {}
    for relative, result in pair_iterable:
        path = relative.replace(os.sep, "/")
        test_directory_db[path] = test_directory_of(
            os.path.normpath(os.path.join(root, relative)), path,
            result.app_set)
    return CRelation(test_directory_db, os.path.basename(root))
