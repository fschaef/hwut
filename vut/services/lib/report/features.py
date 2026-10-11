"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.report.features' COMMAND LINE -- print what the tree
         below a directory claims to do, and which test runs prove it:
         component -> part -> feature -> test runs and their verdicts.

    hwut.report.features [--matrix] [--code] [--cov-dir=<dir>]
                         [--directory=<path>]

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

--matrix: THE LINKS AS A TABLE, one per TEST directory that carries a
feature file, in place of the tree -- a row per test run, a column per
feature, the run's verdict where it links:

    <path>/TEST                    #1    #2    #3
    test-pair.sh [plain]           PASS  .     .
    test-pair.sh [gap]             FAIL  FAIL  .
    test-pair.sh [odd]             .     .     .     <- no feature
                                               ^ no test run
      #1 line-pairing   FAILING
      #2 missing-side   FAILING
      #3 untested       UNPROVEN

    '--code' adds nothing to a table.

    An empty ROW is a test run that proves nothing stated; an empty
    COLUMN is a feature nobody proves. A link never leaves its TEST
    directory, so the tables are the whole of the relation.

--code: WHERE A FEATURE'S RUNS WENT IN THE CODE, from the output of a
'hwut.cov.run' -- '--cov-dir=<dir>', else the nearest 'hwut.coverage/'
from the directory upward. Under each feature that has a linked run:

    code only    <source>: <lines>     executed by this feature's runs
                                       and by NO OTHER measured run
    code shared  <n> line(s) in <m> file(s)
                                       executed by its runs and others'
    code         <n> of <m> linked run(s) not measured

    A hint where to look, not a proof where the feature is implemented.
    The test applications' own lines are left out.

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
                                         id_relation_used_f, mismatch_list,
                                         relation_of_tree)

USAGE = ("usage: hwut.report.features [--matrix] [--code] [--cov-dir=<dir>] "
         "[--directory=<path>] [--help]")

_INDENT = "    "
_WIDTH  = 78


@dataclass(frozen=True)
class Request:
    """WHAT WAS ASKED of 'hwut.report.features': the directory whose
    tree is reported; 'matrix_f' the links as tables in place of the
    tree; 'code_f' the code each feature's runs went through, read from
    'cov_dir' or the nearest coverage output."""
    directory: str        = "."
    matrix_f:  bool       = False
    code_f:    bool       = False
    cov_dir:   str | None = None


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


def span_text(range_tuple):
    """RETURN: str, half-open line ranges as a reader counts them:
    'first..last', a single line alone, ', ' between."""
    return ", ".join("%i..%i" % (begin, end - 1) if end - begin > 1
                     else "%i" % begin for begin, end in range_tuple)


def _code_line_list(code, depth):
    """RETURN: list[str], where one feature's runs went in the code
    ('feature_code.CFeatureCode', or None where nothing is to say):
    'code only' per source, 'code shared' as a count, and the linked
    runs the coverage output does not hold."""
    if code is None: return []
    lead      = _INDENT * depth
    line_list = ["%scode only    %s: %s" % (lead, source, span_text(spans))
                 for source, spans in code.only_tuple]
    if code.shared_line_n:
        line_list.append("%scode shared  %i line(s) in %i file(s)"
                         % (lead, code.shared_line_n, code.shared_file_n))
    if code.measured_n and not code.only_tuple and not code.shared_line_n:
        line_list.append("%scode         none outside the TEST directories"
                         % lead)
    if code.unmeasured_n:
        line_list.append("%scode         %i of %i linked run(s) not measured"
                         % (lead, code.unmeasured_n,
                            code.unmeasured_n + code.measured_n))
    return line_list


def matrix_line_list(relation, path):
    """RETURN: list[str], the links of one TEST directory as a table:
    a row per test run, a column per feature ('#<number>', '#-' where
    it carries none), the run's verdict where it links and '.' where it
    does not; '<- no feature' behind a run that links to none, '<- no
    feature defined' behind one that names only what the directory does
    not define, '^ no test run' under a feature nobody proves; then the
    features by
    number, name and state. Empty where the directory carries no
    feature file."""
    test_directory = relation.test_directory_db[path]
    if test_directory.feature_file is None: return []
    state_tuple = test_directory.state_tuple
    head_list   = ["#%s" % ("-" if each.feature.number is None
                            else each.feature.number)
                   for each in state_tuple]
    cell_db     = {}               # (test, choice) -> {column: verdict}
    for column, each in enumerate(state_tuple):
        for run in each.run_tuple:
            cell_db.setdefault((run.test, run.choice), {})[column] = \
                run.verdict
    undefined = set((test, choice) for test, choice, _
                    in test_directory.undefined_tuple)
    name_list = [run_text(".", test, choice)
                 for test, choice in test_directory.run_tuple]
    width_0   = max([len(name) for name in name_list] + [len(path)])
    width     = max([len(head) for head in head_list]
                    + [len(verdict) for row in cell_db.values()
                       for verdict in row.values()] + [1])

    def row(first, cell_list, tail=""):
        """RETURN: str, one table row, cells left-aligned in columns."""
        return ("%-*s  %s%s" % (width_0, first,
                                "  ".join("%-*s" % (width, cell)
                                          for cell in cell_list),
                                tail)).rstrip()

    line_list = [row(path, head_list)]
    for name, key in zip(name_list, test_directory.run_tuple):
        linked = cell_db.get(key, {})
        line_list.append(row(name, [linked.get(column, ".")
                                    for column in range(len(state_tuple))],
                             "" if linked
                             else "  <- no feature defined"
                             if key in undefined
                             else "  <- no feature"))
    if any(not each.run_tuple for each in state_tuple):
        line_list.append(row("", ["^" if not each.run_tuple else ""
                                  for each in state_tuple],
                             "  no test run"))
    name_width = max([len(feature_name(each.feature))
                      for each in state_tuple] + [1])
    head_width = max(len(head) for head in head_list) if head_list else 1
    for head, each in zip(head_list, state_tuple):
        line_list.append("  %-*s %-*s  %s" % (head_width, head, name_width,
                                              feature_name(each.feature),
                                              each.state))
    return line_list


def feature_name(feature):
    """RETURN: str, the feature's name; its key where it states none."""
    return feature.key if feature.name is None else feature.name


#  THE CODE OF THE FEATURES, where '--code' asked for it: read once by
#  'do' and looked up by the lines of each TEST directory.
relation_code_db = None


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
        line_list += _code_line_list(
            (relation_code_db or {}).get((path, each.feature.key)),
            depth + 2)
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
            #  ITS TEST RUNS ARE COUNTED, not named: none of them can
            #  link, and a tree that states no features would name
            #  every test it has (E-144).
            bare_test.append("%s   %i test run(s)"
                             % (path, len(each.run_tuple)))
        else:
            unlinked += [run_text(path, test, choice)
                         for test, choice in each.unlinked_tuple]
            fault += ["%s/%s" % (path, f) if path != "." else "%s" % f
                      for f in each.feature_file.fault_tuple]
        undefined += ["%s   '%s'" % (run_text(path, test, choice), name)
                      for test, choice, name in each.undefined_tuple]
    composed_f = id_relation_used_f(relation)
    for path in sorted(relation.component_db):
        each = relation.component_db[path]
        if each.composition is None:
            #  NAMED ONLY WHERE THE TREE DESCRIBES COMPONENTS AT ALL:
            #  feature files alone are complete (E-144).
            if composed_f: bare_component.append(path)
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
    global relation_code_db
    directory = request.directory or "."
    if not os.path.isdir(directory):
        raise Refused("REFUSED: the directory '%s' does not exist"
                      % directory)
    root = os.path.abspath(directory)
    try:
        relation = relation_of_tree(root)
    except RootConfMissing as error:
        raise Refused("REFUSED: %s" % error) from error
    if not relation.test_directory_db:
        raise Empty("EMPTY: no TEST directory below '%s'" % directory)

    note_list        = []
    relation_code_db = None
    if request.code_f or request.cov_dir:
        relation_code_db, note = _code_db(relation, root, request.cov_dir)
        if note: note_list.append(note)

    if request.matrix_f:
        line_list = []
        for path in sorted(relation.test_directory_db):
            found = matrix_line_list(relation, path)
            if found: line_list += found + [""]
        if line_list: line_list.pop()
        else:         line_list = ["no TEST directory carries '%s'"
                                   % FEATURE_FILE_NAME]
    elif "." in relation.component_db:
        line_list = _component_line_list(relation, ".", 0)
    else:
        #  ASKED INSIDE A TEST DIRECTORY: it is the whole of the tree.
        line_list = _test_directory_line_list(relation, ".", 0)
    line_list  = note_list + line_list
    line_list += _outside_line_list(relation)
    relation_code_db = None

    count_db = dict.fromkeys(STATE_TUPLE, 0)
    for path in relation.test_directory_db:
        for state, n in relation.count_of(path).items():
            count_db[state] += n
    return Result(tuple(line_list),
                  tuple((state, count_db[state]) for state in STATE_TUPLE))


def _code_db(relation, root, cov_dir):
    """
    RETURN: [0] dict, the code of the features
                ('feature_code.code_db_of'); None where no coverage
                output is found or it cannot be read
            [1] str, the NOTE that says why none is shown; None where
                one is
    """
    from vut.engine.coverage.api import OutputRefused
    from vut.engine.orchestrator.exploration.feature_code import code_db_of
    from vut.services.lib.report.details import coverage_directory_of
    output_directory = coverage_directory_of(root, cov_dir)
    if output_directory is None or not os.path.isdir(output_directory):
        return None, ("NOTE: no coverage output found -- 'hwut.cov.run' "
                      "writes one, '--cov-dir=<dir>' names one; no code "
                      "shown")
    try:
        found = code_db_of(relation, root, output_directory)
    except OutputRefused as refusal:
        return None, "NOTE: %s; no code shown" % refusal
    if found is None:
        return None, ("NOTE: '%s' names no root it measured; no code shown"
                      % os.path.relpath(output_directory))
    return found, None


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
    matrix_f, code_f, cov_dir = False, False, None
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
        elif word == "--matrix":
            matrix_f = True
        elif word == "--code":
            code_f = True
        elif word.startswith("--cov-dir="):
            cov_dir = word[len("--cov-dir="):]
        else:
            write("REFUSED: 'hwut.report.features' does not take '%s'"
                  % word)
            write(USAGE)
            return E_ExitCode.REFUSED
    return answered(do, Request(directory, matrix_f, code_f, cov_dir),
                    write, printed, USAGE)


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from   vut.services._exit import guarded
    sys.exit(guarded("hwut.report.features", main, sys.argv[1:]))
