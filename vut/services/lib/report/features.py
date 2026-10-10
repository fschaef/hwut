"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.report.features' COMMAND LINE -- print what the tree
         below a directory claims to do, and which test runs prove it:
         component -> part -> feature -> test runs and their verdicts.

    hwut.report.features [--directory=<path>]

THE THREE STATEMENTS READ

    <component>/hwut-composition.conf     what the component does, and
                                          what each part contributes
    <component>/TEST/hwut-features.conf   the features proven in that
                                          TEST directory
    a test's '@hwut { }' block            features = ["<name>", ...]

THE PAGE

    COMPONENT <path> (<id>) -- <title>     <n> proven, <n> failing, <n> unproven
        does       <what the component does>
        serves     <how it serves its parent: its 'parent' sentence>
        as child   <what its parent's 'childs' says it contributes>
        FEATURES <path>/TEST (<id>)        <n> proven, <n> failing, <n> unproven
            [PROVEN]   <path>/TEST#<number> <name> -- <title>
                [PASS] <path>/TEST/<test> [<choice>]
        COMPONENT <path>/<part> ...

    The tree is the DIRECTORIES'. The ids, 'parent' and 'childs' are
    the statement files'; where the two disagree the page says so and
    'hwut.sanitize.propose --relations' proposes the adaption.

    state of a feature
        PROVEN     one linked test run or more; all of them pass
        FAILING    one linked test run or more; one of them does not
                   pass, or has no verdict in 'GOOD/book.csv'
        UNPROVEN   no linked test run

    A component's counts are its features in each state, summed over
    its parts. Every path is relative to where the face is called.

OUTSIDE THE RELATION, named below the tree:

    a test run that names a feature its TEST directory does not define
    a test run that links to no feature, in a TEST directory that
        carries a feature file
    a TEST directory without 'hwut-features.conf'
    a component without 'hwut-composition.conf'
    'parent' and 'childs' that disagree with where a directory stands
    what a feature or composition file states that cannot be read

The verdicts are those of 'GOOD/book.csv': nothing is run.

EXIT STATUS
    0    TEST directories stand, and the page was printed
    2    the command line cannot be read, or no root bounds the tree
    3    no TEST directory stands below the directory
______________________________________________________________________________
"""
import os
import sys
from   dataclasses import dataclass

from   vut.services._exit        import E_ExitCode
from   vut.services.lib.face     import Refused, Empty, answered
from   vut.engine.orchestrator.exploration.tree_explorer \
                                 import RootConfMissing
from   vut.engine.orchestrator.exploration.feature_relation \
                                 import (COMPOSITION_FILE_NAME,
                                         FEATURE_FILE_NAME, STATE_TUPLE,
                                         GONE, MOVED, NO_ID, PARENT, TWIN,
                                         UNJUDGED, UNLISTED,
                                         mismatch_list, relation_of_tree)

USAGE = "usage: hwut.report.features [--directory=<path>] [--help]"

_INDENT = "    "
_WIDTH  = 78


@dataclass(frozen=True)
class Request:
    """WHAT WAS ASKED of 'hwut.report.features': the directory whose
    tree is reported."""
    directory: str = "."


@dataclass(frozen=True)
class Result:
    """WHAT HAPPENED: the page's lines, and how many features stand in
    each state below the directory -- (state, n) in STATE_TUPLE order."""
    line_tuple:  tuple = ()
    count_tuple: tuple = ()


def run_text(path, test, choice):
    """RETURN: str, a test run as the page addresses it:
    '<path>/<test>' or '<path>/<test> [<choice>]'."""
    where = test if path == "." else "%s/%s" % (path, test)
    return where if choice is None else "%s [%s]" % (where, choice)


def feature_text(path, feature):
    """RETURN: str, a feature as the page addresses it:
    '<path>#<number> <name>'; '#-' where it carries no number, its key
    where it states no name."""
    number = "-" if feature.number is None else "%i" % feature.number
    return "%s#%s %s" % (path, number,
                         feature.key if feature.name is None
                         else feature.name)


def _count_text(count_db):
    """RETURN: str, '<n> proven, <n> failing, <n> unproven'."""
    return ", ".join("%i %s" % (count_db[state], state.lower())
                     for state in STATE_TUPLE)


def _headed(head, tail, depth):
    """RETURN: str, 'head' at 'depth' and 'tail' flush right at the
    page's width; one blank between them at least."""
    left = _INDENT * depth + head
    return "%s %s" % (left, tail.rjust(max(_WIDTH - len(left) - 1,
                                           len(tail))))


def _statement_line_list(relation, path, depth, does=None):
    """RETURN: list[str], the sentences that stand for the directory at
    'path', one per line: 'does', 'serves' (its own 'parent' sentence)
    and 'as child' (what the 'childs' of the directory above says of
    its id)."""
    statement = relation.statement_of(path)
    above     = relation.statement_above(path)
    serves    = None if statement is None else statement.parent_text
    as_child  = None
    if statement is not None and statement.id is not None \
       and above is not None:
        as_child = above.child_text(statement.id)
    return ["%s%-10s %s" % (_INDENT * depth, label, text)
            for label, text in (("does", does), ("serves", serves),
                                ("as child", as_child))
            if text]


def _id_text(relation, path):
    """RETURN: str, ' (<id>)' of the statement at 'path'; '' where it
    gives itself none or no statement stands."""
    statement = relation.statement_of(path)
    if statement is None or statement.id is None: return ""
    return " (%s)" % statement.id


def _test_directory_line_list(relation, path, depth):
    """RETURN: list[str], one TEST directory: its head with the counts,
    its statements, every feature with its state, and below each the
    linked test runs with their verdicts."""
    test_directory = relation.test_directory_db[path]
    line_list = [_headed("FEATURES %s%s" % (path, _id_text(relation, path)),
                         _count_text(relation.count_of(path)), depth)]
    line_list += _statement_line_list(relation, path, depth + 1)
    for each in test_directory.state_tuple:
        title = "" if each.feature.title is None \
                else " -- %s" % each.feature.title
        line_list.append("%s%-10s %s%s"
                         % (_INDENT * (depth + 1), "[%s]" % each.state,
                            feature_text(path, each.feature), title))
        line_list += ["%s[%s] %s" % (_INDENT * (depth + 2), run.verdict,
                                     run_text(path, run.test, run.choice))
                      for run in each.run_tuple]
    return line_list


def _component_line_list(relation, path, depth):
    """RETURN: list[str], one component and everything below it: its
    head with the counts, its statements, its own TEST directory, then
    its parts in sorted order."""
    component   = relation.component_db[path]
    composition = component.composition
    title = "" if composition is None or composition.title is None \
            else " -- %s" % composition.title
    line_list = [_headed("COMPONENT %s%s%s" % (path, _id_text(relation, path),
                                               title),
                         _count_text(relation.count_of(path)), depth)]
    line_list += _statement_line_list(
        relation, path, depth + 1,
        None if composition is None else composition.does)
    if component.test_directory is not None:
        line_list += _test_directory_line_list(
            relation, component.test_directory, depth + 1)
    for part in component.part_tuple:
        line_list += _component_line_list(relation, part, depth + 1)
    return line_list


def mismatch_text(mismatch):
    """RETURN: str, one disagreement between the statements and the
    directories, telegraphic: the directory, then what disagrees."""
    return {
        NO_ID:    "%(path)s   no 'id'",
        MOVED:    "%(path)s   '%(id)s' moved here from %(from_path)s",
        PARENT:   "%(path)s   'parent' is not the id of the directory above",
        UNLISTED: "%(path)s   '%(id)s' not in the 'childs' of the "
                  "directory above",
        GONE:     "%(path)s   'childs' lists '%(id)s'; nothing below "
                  "carries it",
        TWIN:     "%(path)s   two childs carry the id '%(id)s'",
        UNJUDGED: "%(path)s   the directory above gives itself no id",
    }[mismatch.kind] % {"path": mismatch.path, "id": mismatch.id,
                        "from_path": mismatch.from_path}


def _outside_line_list(relation):
    """RETURN: list[str], what stands outside the relation, one block
    per kind, a kind with nothing to name left out; empty where
    everything stands inside."""
    undefined, unlinked, bare_test, bare_component, fault = [], [], [], [], []
    for path in sorted(relation.test_directory_db):
        each = relation.test_directory_db[path]
        if each.feature_file is None:
            bare_test.append(path)
        else:
            unlinked += [run_text(path, test, choice)
                         for test, choice in each.unlinked_tuple]
            fault += ["%s/%s" % (path, f) if path != "." else "%s" % f
                      for f in each.feature_file.fault_tuple]
        undefined += ["%s   '%s'" % (run_text(path, test, choice), name)
                      for test, choice, name in each.undefined_tuple]
    for path in sorted(relation.component_db):
        each = relation.component_db[path]
        if each.composition is None:
            bare_component.append(path)
        else:
            fault += ["%s/%s" % (path, f) if path != "." else "%s" % f
                      for f in each.composition.fault_tuple]
    line_list = []
    for head, entry_list in (
            ("test run, names a feature its TEST directory does not "
             "define", undefined),
            ("test run, links to no feature", unlinked),
            ("TEST directory, no '%s'" % FEATURE_FILE_NAME, bare_test),
            ("component, no '%s'" % COMPOSITION_FILE_NAME, bare_component),
            ("statement, not read", fault),
            ("'parent' and 'childs', not as the directories stand => "
             "hwut.sanitize.propose --relations",
             [mismatch_text(each) for each in mismatch_list(relation)])):
        if not entry_list: continue
        line_list.append("%s%s" % (_INDENT, head))
        line_list += ["%s%s" % (_INDENT * 2, entry) for entry in entry_list]
    if line_list:
        line_list = ["", "OUTSIDE THE RELATION"] + line_list
    return line_list


def do(request):
    """
    RETURN: Result, the page of the tree below 'request.directory' and
            the counts of its features by state.

    RAISES: Refused, where the directory does not stand or no root conf
            is above it; Empty, where no TEST directory stands below.

    IT NEVER PRINTS (E-101).
    """
    directory = request.directory or "."
    if not os.path.isdir(directory):
        raise Refused("REFUSED: the directory '%s' does not exist"
                      % directory)
    try:
        relation = relation_of_tree(os.path.abspath(directory))
    except RootConfMissing as error:
        raise Refused("REFUSED: %s" % error) from error
    if not relation.test_directory_db:
        raise Empty("EMPTY: no TEST directory below '%s'" % directory)

    if "." in relation.component_db:
        line_list = _component_line_list(relation, ".", 0)
    else:
        #  ASKED INSIDE A TEST DIRECTORY: it is the whole of the tree.
        line_list = _test_directory_line_list(relation, ".", 0)
    line_list += _outside_line_list(relation)

    count_db = dict.fromkeys(STATE_TUPLE, 0)
    for path in relation.test_directory_db:
        for state, n in relation.count_of(path).items():
            count_db[state] += n
    return Result(tuple(line_list),
                  tuple((state, count_db[state]) for state in STATE_TUPLE))


def printed(result, write):
    """RETURN: E_ExitCode, OK. The page's lines, as 'do' answered them."""
    for line in result.line_tuple: write(line)
    return E_ExitCode.OK


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode -- OK where TEST directories stand (the page
            printed), EMPTY where none does, REFUSED where the command
            line cannot be read or no root bounds the tree.
    """
    if write is None: write = print
    if argv  is None: argv  = sys.argv[1:]
    directory = "."
    for word in argv:
        if word == "--help":
            from vut.services._core import man_page
            write(man_page("hwut.report.features",
                           __doc__.split("PURPOSE:", 1)[1]
                           .rsplit("_" * 10, 1)[0].rstrip(),
                           usage=USAGE))
            return E_ExitCode.OK
        elif word.startswith("--directory="):
            directory = word[len("--directory="):]
        else:
            write("REFUSED: 'hwut.report.features' does not take '%s'"
                  % word)
            write(USAGE)
            return E_ExitCode.REFUSED
    return answered(do, Request(directory), write, printed, USAGE)


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from   vut.services._exit import guarded
    sys.exit(guarded("hwut.report.features", main, sys.argv[1:]))
