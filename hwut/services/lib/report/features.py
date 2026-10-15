"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.report.features' COMMAND LINE -- print what the tree
         below a directory claims to do, and which test runs prove it, as
         'hwut-root-features.conf' groups it (spec 23 VERSION 10, R-96).

    hwut.report.features [--matrix] [--code] [--cov-dir=<dir>]
                         [--html=<file>] [--ods=<file>] [--cov-html=<dir>]
                         [--directory=<path>]

THE STATEMENTS READ

    <top>/hwut-root-features.conf         the ids, the tree of aggregates,
                                          the retired
    <dir>/TEST/hwut-features.conf         the features proven in that
                                          TEST directory
    a test's '@hwut { }' block            features = ["<name>", ...]

    Where no central file stands, nothing is reported => hwut.features.init.

THE PAGE

    AGGREGATE <tree path> -- <title>   <n> implemented, <n> open; <n> ok, <n> fail
        state      IMPLEMENTED ok | IMPLEMENTED fail | OPEN
        keys       <the keys it states; they travel downward>
        [IMPLEMENTED ok]   <external id> -- <title>
            internal    <directory id>:<name>  (<directory>)
            keys        <its own, its TEST file's, the aggregates'>
            [PASS] <path>/TEST/<test> [<choice>]
    UNPLACED        the leaves in no aggregate
    RETIRED         the claims of 'retired'

    A leaf is IMPLEMENTED where a test run is linked to it, else OPEN;
    the verdict beside it is ok where every linked run passes. OPEN is
    always fail; RETIRED has no verdict. An aggregate folds the states
    below it; one with nothing below is OPEN. Asked below the top, only
    the leaves whose directory stands below, under the aggregates that
    hold them. Every path is relative to where the face is called.

--matrix: THE LINKS AS A TABLE, one per TEST directory that carries a
feature file, in place of the tree -- a row per test run, a column per
feature, the run's verdict where it links:

    <path>/TEST                    #1    #2    #3
    test-pair.sh [plain]           PASS  .     .
    test-pair.sh [gap]             FAIL  FAIL  .
    test-pair.sh [odd]             .     .     .     <- NONSENSE?
                                               ^ no test run
      #1 line-pairing   IMPLEMENTED fail
      #2 missing-side   IMPLEMENTED fail
      #3 untested       OPEN

    '#<n>' counts the features of the file in order; it is a column,
    not an id. A column is named by its leaf's state, 'not registered'
    where the central file has no line for it. '--code' adds nothing to a
    table.

    An empty ROW is a test run that proves nothing stated; an empty
    COLUMN is a feature nobody proves. A link never leaves its TEST
    directory, so the tables are the whole of the relation.

--code: WHERE A FEATURE'S RUNS WENT IN THE CODE, from the output of a
'hwut.cov.run' -- '--cov-dir=<dir>', else the nearest 'hwut.coverage/'
from the directory upward. Under each leaf that has a linked run:

    code only    <source>: <lines>     executed by this feature's runs
                                       and by NO OTHER measured run
    code shared  <n> line(s) in <m> file(s)
                                       executed by its runs and others'
    code         <n> of <m> linked run(s) not measured

    A hint where to look, not a proof where the feature is implemented.
    The test applications' own lines are left out.

--html=<file>, --ods=<file>: THE FEATURE DOCUMENT, for somebody else to
open -- one self-contained HTML page, or an OpenDocument spreadsheet.
Four tabs:

    Matrix     a row per leaf: external id, brief (its title), state, and
               the test runs that implement it with their verdicts
    Tree       the aggregates and their leaves, each aggregate with its
               title, its state and the counts summed from below
    Features   a row per leaf: external id, name, title, doc, aggregate,
               state, internal id, keys
    Tests      a row per test application: file, title, 'doc', its test
               runs with their verdicts ('NONSENSE?' behind one that
               links to no feature), its features

    An id in 'Matrix' leads to its row in 'Features'; a test run leads to
    its test's row in 'Tests'. The file is written, one line says so, and
    the tree is not printed; both may be asked at once.

    WITH '--code' OR '--cov-dir=<dir>' the 'Features' tab carries, per
    feature, the source lines its test runs executed and no other
    measured run did. WITH '--cov-html=<dir>' -- the directory
    'hwut.cov.conv.to_html' wrote its pages into -- each such source is
    a link to its coverage page, at the first of those lines. The link
    is RELATIVE: the document and the pages travel together.

A FEATURE MAY NAME DOCUMENTS where more is said of it:

    forward { title     = "A CAN frame is forwarded to its MOST address."
              documents = ["../README.txt", "../spec/routing.txt#3"] }

    Paths from the file's directory ('#<anchor>' may follow), or URLs.
    The page prints each under the leaf as 'see <path>'; the feature
    document makes each a link.

OUTSIDE THE RELATION, named below the tree:

    a test run that names a feature its TEST directory does not define
    NONSENSE?  a test run that links to no feature, in a TEST
        directory that states features. No failure -- its verdict
        stands; 'hwut.help' says what the word means.
    a feature that names a document that does not stand
    what a feature file states that cannot be read
    a feature defined and not registered, and what the central file and
        the tree disagree on => hwut.features.register

The verdicts are those of 'GOOD/book.csv': nothing is run.

EXIT STATUS
    0    TEST directories stand, and the page was printed
    2    the command line cannot be read, no root bounds the tree, or no
         readable 'hwut-root-features.conf' stands at its top
    3    no TEST directory stands below the directory
______________________________________________________________________________
"""
import os
import sys
from   dataclasses import dataclass

from ..._exit import E_ExitCode
from ..face import Refused, Empty, answered
from   hwut.engine.orchestrator.exploration.tree_explorer \
                                 import RootConfMissing
from   hwut.engine.orchestrator.exploration.feature_relation \
                                 import document_place, TEST_NAME
from   hwut.engine.orchestrator.exploration.feature_registry \
                                 import IMPLEMENTED, OPEN, OK, FAIL
from   hwut.engine.orchestrator.exploration.feature_view \
                                 import view_of, ViewRefused
from   hwut.engine.orchestrator.exploration.finder \
                                 import FEATURE_FILE_NAME

USAGE = ("usage: hwut.report.features [--matrix] [--code] [--cov-dir=<dir>] "
         "[--html=<file>] [--ods=<file>] [--cov-html=<dir>] "
         "[--directory=<path>] [--help]")

_INDENT = "    "
_WIDTH  = 78


@dataclass(frozen=True)
class Request:
    """WHAT WAS ASKED of 'hwut.report.features': the directory whose
    tree is reported; 'matrix_f' the links as tables in place of the
    tree; 'code_f' the code each feature's runs went through, read from
    'cov_dir' or the nearest coverage output; 'html_path' and 'ods_path'
    the files the feature document is written to, in place of the
    page."""
    directory: str        = "."
    matrix_f:  bool       = False
    code_f:    bool       = False
    cov_dir:   str | None = None
    html_path: str | None = None
    ods_path:  str | None = None
    cov_html:  str | None = None     # where the coverage pages stand


@dataclass(frozen=True)
class Result:
    """WHAT HAPPENED: the page's lines, and how many leaves stand in each
    state below the directory -- (state, n): IMPLEMENTED, OPEN, OK, FAIL."""
    line_tuple:  tuple = ()
    count_tuple: tuple = ()


def run_text(path, test, choice):
    """RETURN: str, a test run as the page addresses it:
    '<path>/<test>' or '<path>/<test> [<choice>]'."""
    where = test if path == "." else "%s/%s" % (path, test)
    return where if choice is None else "%s [%s]" % (where, choice)


def _headed(head, tail, depth):
    """RETURN: str, 'head' at 'depth' and 'tail' flush right at the
    page's width; one blank between them at least."""
    left = _INDENT * depth + head
    return "%s %s" % (left, tail.rjust(max(_WIDTH - len(left) - 1,
                                           len(tail))))


def _statement_line_list(depth, doc=None, key_tuple=(), document_tuple=()):
    """RETURN: list[str], the sentences that stand for an aggregate: its
    'doc' (each of its lines), the 'keys' it states itself, and 'see' for
    each document it names."""
    line_list = []
    for label, text in (("doc", doc),
                        ("keys", ", ".join(key_tuple))):
        if not text: continue
        for i, line in enumerate(text.split("\n")):
            line_list.append(("%s%-10s %s" % (_INDENT * depth,
                                              label if i == 0 else "",
                                              line)).rstrip())
    line_list += ["%ssee        %s" % (_INDENT * depth, document)
                  for document in document_tuple]
    return line_list


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
                 for source, spans, _ in code.only_tuple]
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


def matrix_line_list(relation, path, state_of):
    """RETURN: list[str], the links of one TEST directory as a table:
    a row per test run, a column per feature ('#<n>', n counting the
    features in file order), the run's verdict where it links and '.'
    where it does not; '<- NONSENSE?' behind a run that links to none,
    '<- no feature defined' behind one that names only what the
    directory does not define, '^ no test run' under a feature nobody
    proves; then the features by column, name and state. Empty where
    the directory carries no feature file. 'state_of(path, name)' names a
    feature's state."""
    test_directory = relation.test_directory_db[path]
    if test_directory.feature_file is None: return []
    state_tuple = test_directory.state_tuple
    head_list   = ["#%i" % (column + 1) for column in range(len(state_tuple))]
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
                             else "  <- NONSENSE?"))
    if any(not each.run_tuple for each in state_tuple):
        line_list.append(row("", ["^" if not each.run_tuple else ""
                                  for each in state_tuple],
                             "  no test run"))
    name_width = max([len(feature_name(each.feature))
                      for each in state_tuple] + [1])
    head_width = max(len(head) for head in head_list) if head_list else 1
    for head, each in zip(head_list, state_tuple):
        state = state_of(path, each.feature.name)
        line_list.append("  %-*s %-*s  %s" % (head_width, head, name_width,
                                              feature_name(each.feature),
                                              state))
    return line_list


def feature_name(feature):
    """RETURN: str, the feature's name -- its key in 'childs'."""
    return feature.name


#  THE CODE OF THE FEATURES, where '--code' asked for it: read once by
#  'do' and looked up by the lines of each TEST directory.
relation_code_db = None

def _view_count_text(count_db):
    """RETURN: str, '<n> implemented, <n> open; <n> ok, <n> fail'."""
    return "%i implemented, %i open; %i ok, %i fail" % (
        count_db[IMPLEMENTED], count_db[OPEN], count_db[OK], count_db[FAIL])


def view_state_text(state):
    """RETURN: str, a claim's state on its two axes as the page writes it:
    'IMPLEMENTED ok', 'IMPLEMENTED fail', 'OPEN' (always fail), 'RETIRED'."""
    if state.verdict is None or state.implementation == OPEN:
        return state.implementation
    return "%s %s" % (state.implementation, state.verdict)


def _view_leaf_line_list(view, leaf_view, depth):
    """RETURN: list[str], one leaf: its state, external id and title; its
    internal id and directory; its effective keys; its linked runs; the
    documents it names; the code its runs reached."""
    feature = None if leaf_view.feature_state is None \
              else leaf_view.feature_state.feature
    title = "" if feature is None or feature.title is None \
            else " -- %s" % feature.title
    lead  = _INDENT * (depth + 1)
    line_list = ["%s%-18s %s%s" % (_INDENT * depth,
                                   "[%s]" % view_state_text(leaf_view.state),
                                   leaf_view.leaf.external, title)]
    line_list.append("%sinternal    %s  (%s)"
                     % (lead, leaf_view.leaf.internal,
                        leaf_view.directory_path or "no directory"))
    if feature is None:
        line_list.append("%s            defined in no TEST directory"
                         % lead)
    if leaf_view.key_tuple:
        line_list.append("%skeys        %s" % (lead,
                                               ", ".join(leaf_view.key_tuple)))
    if leaf_view.feature_state is not None:
        path = leaf_view.test_path
        line_list += ["%s[%s] %s" % (lead, run.verdict,
                                     run_text(path, run.test, run.choice))
                      for run in leaf_view.feature_state.run_tuple]
        line_list += ["%ssee          %s%s" % (lead, place, anchor)
                      for place, anchor, _ in (
                          document_place(path, document)
                          for document in feature.document_tuple)]
        line_list += _code_line_list(
            (relation_code_db or {}).get((path, feature.key)), depth + 1)
    return line_list


def _view_aggregate_line_list(view, aggregate_view, depth):
    """RETURN: list[str], one aggregate and everything below it: its head
    with the counts, its doc, keys and documents, then its claims in file
    order."""
    aggregate = aggregate_view.aggregate
    title = "" if aggregate.title is None else " -- %s" % aggregate.title
    line_list = [_headed("AGGREGATE %s%s" % (aggregate_view.tree_path, title),
                         _view_count_text(aggregate_view.count_db), depth)]
    line_list.append("%s%-10s %s%s" % (
        _INDENT * (depth + 1), "state", view_state_text(aggregate_view.state),
        "" if aggregate_view.child_tuple else "  (nothing below it)"))
    line_list += _statement_line_list(depth + 1, aggregate.doc,
                                      aggregate.key_tuple,
                                      aggregate.document_tuple)
    for each in aggregate_view.child_tuple:
        if hasattr(each, "aggregate"):
            line_list += _view_aggregate_line_list(view, each, depth + 1)
        else:
            line_list += _view_leaf_line_list(view, each, depth + 1)
    return line_list


def _view_retired_line_list(view):
    """RETURN: list[str], the RETIRED block: every claim of 'retired', a
    leaf with its internal id, an aggregate with how many leaves it took
    along; empty where none is."""
    def leaves(each):
        return 1 if each.leaf_f else sum(leaves(c) for c in each.child_tuple)

    def below_f(each):
        """RETURN: True, the retired claim has a leaf whose directory lies
        at or below the directory asked (always, asked at the top)."""
        if os.path.normpath(view.asked) == os.path.normpath(view.top):
            return True
        if not each.leaf_f: return any(below_f(c) for c in each.child_tuple)
        directory = view.registry.directory_of_id(
            each.internal.partition(":")[0])
        if directory is None: return False
        relative = os.path.relpath(os.path.join(view.top, directory.path,
                                                TEST_NAME), view.asked)
        return not (relative == ".." or relative.startswith(".." + os.sep))

    retired = [each for each in view.registry.retired_tuple if below_f(each)]
    if not retired: return []
    line_list = ["", _headed("RETIRED", "%i retired" % len(retired), 0)]
    for each in retired:
        line_list.append("%s[RETIRED]  %s  (%s)" % (
            _INDENT, each.name, each.internal if each.leaf_f
            else "aggregate, %i leaf/leaves" % leaves(each)))
    return line_list


def _view_outside_line_list(view):
    """RETURN: list[str], what stands outside the view, one block per kind:
    the links and documents as the relation finds them, the faults of the
    TEST files, the features defined and not registered, and what the
    detector finds of the central file against the tree."""
    from hwut.engine.orchestrator.exploration.feature_detector \
        import detect, unregistered_list
    relation = view.relation
    undefined, unlinked, fault, absent = [], [], [], []
    for path in sorted(relation.test_directory_db):
        each = relation.test_directory_db[path]
        if each.feature_file is not None:
            unlinked += [run_text(path, test, choice)
                         for test, choice in each.unlinked_tuple]
            for state in each.state_tuple:
                for document in state.feature.document_tuple:
                    place, _, url_f = document_place(path, document)
                    if url_f: continue
                    if not os.path.exists(os.path.join(view.asked, place)):
                        absent.append("%s/%s   '%s'"
                                      % (path, state.feature.name, document))
            fault += ["%s/%s" % (path, f) if path != "." else "%s" % f
                      for f in each.feature_file.fault_tuple]
        undefined += ["%s   '%s'" % (run_text(path, test, choice), name)
                      for test, choice, name in each.undefined_tuple]
    below = os.path.relpath(view.asked, view.top).replace(os.sep, "/")
    unregistered = ["%s   '%s'" % pair
                    for pair in unregistered_list(view.top, below)]
    finding = [each.text.strip() for each in (detect(view.top, below) or ())
               if not each.hint_f and each.kind not in ("leaf-new",
                                                         "dir-new")]
    line_list = []
    for head, entry_list in (
            ("test run, names a feature its TEST directory does not "
             "define", undefined),
            ("NONSENSE? test run, links to no feature => hwut.help",
             unlinked),
            ("claim, names a document that does not stand", absent),
            ("statement, not read", fault),
            ("feature, defined and not registered => "
             "hwut.features.register", unregistered),
            ("central file and tree, not as they should stand => "
             "hwut.features.register", finding)):
        if not entry_list: continue
        line_list.append("%s%s" % (_INDENT, head))
        line_list += ["%s%s" % (_INDENT * 2, entry) for entry in entry_list]
    if line_list:
        line_list = ["", "OUTSIDE THE RELATION"] + line_list
    return line_list


def _view_matrix_state(view):
    """RETURN: callable (test path, name) -> str, the state a feature's
    column is named with in a table: its leaf's, or 'not registered'."""
    def state_of(path, name):
        found = view.leaf_of_feature(path, name)
        return "not registered" if found is None \
               else view_state_text(found.state)
    return state_of


def _view_do(view, request, root):
    """RETURN: Result, the page of 'view' (see 'do')."""
    global relation_code_db
    count_db    = view.count_db()
    count_tuple = tuple((state, count_db[state])
                        for state in (IMPLEMENTED, OPEN, OK, FAIL))
    if request.html_path or request.ods_path:
        return Result(tuple(_document_written(view.relation, request, root,
                                              view)), count_tuple)
    note_list   = []
    relation_code_db = None
    if request.code_f or request.cov_dir:
        relation_code_db, note = _code_db(view.relation, root,
                                          request.cov_dir)
        if note: note_list.append(note)
    if request.matrix_f:
        line_list, state_of = [], _view_matrix_state(view)
        for path in sorted(view.relation.test_directory_db):
            found = matrix_line_list(view.relation, path, state_of)
            if found: line_list += found + [""]
        if line_list: line_list.pop()
        else:         line_list = ["no TEST directory carries '%s'"
                                   % FEATURE_FILE_NAME]
    else:
        line_list = []
        for each in view.top_tuple:
            line_list += _view_aggregate_line_list(view, each, 0)
        if view.unplaced:
            if line_list: line_list.append("")
            line_list.append(_headed("UNPLACED", "%i leaf/leaves"
                                     % len(view.unplaced), 0))
            for each in view.unplaced:
                line_list += _view_leaf_line_list(view, each, 1)
        line_list += _view_retired_line_list(view)
    line_list = note_list + line_list + _view_outside_line_list(view)
    relation_code_db = None
    return Result(tuple(line_list), count_tuple)


def do(request):
    """
    RETURN: Result, the page of the tree below 'request.directory' and
            the counts of its leaves by state.

    RAISES: Refused, where the directory does not stand, no root conf is
            above it, or no readable central file stands at its top;
            Empty, where no TEST directory stands below.

    IT NEVER PRINTS (E-101).
    """
    directory = request.directory or "."
    if not os.path.isdir(directory):
        raise Refused("REFUSED: the directory '%s' does not exist"
                      % directory)
    root = os.path.abspath(directory)
    try:
        view = view_of(root)
    except (RootConfMissing, ViewRefused) as error:
        raise Refused("REFUSED: %s" % error) from error
    if not view.relation.test_directory_db:
        raise Empty("EMPTY: no TEST directory below '%s'" % directory)
    return _view_do(view, request, root)


def _document_written(relation, request, root, view):
    """
    RETURN: list[str], one line per file of the feature document
            written: "'<file>' written -- <n> feature(s), <m> test(s)";
            before them the NOTE that says why no code is in it, where
            code was asked and no coverage output could be read

    RAISES: Refused, where a file cannot be written, or '--cov-html'
            names no directory.
    """
    from .feature_document import document_of_view, html_text, ods_bytes
    line_list, code_db = [], None
    if request.code_f or request.cov_dir or request.cov_html:
        code_db, note = _code_db(relation, root, request.cov_dir)
        if note: line_list.append(note)
    if request.cov_html and not os.path.isdir(request.cov_html):
        raise Refused("REFUSED: '%s' is no directory -- '--cov-html' names "
                      "where 'hwut.cov.conv.to_html' wrote its pages"
                      % request.cov_html)
    for path, content in ((request.html_path, html_text),
                          (request.ods_path,  ods_bytes)):
        if not path: continue
        #  THE WAY TO THE PAGES IS FROM WHERE THE DOCUMENT STANDS.
        page_base = None if not request.cov_html else os.path.relpath(
            os.path.abspath(request.cov_html),
            os.path.dirname(os.path.abspath(path))).replace(os.sep, "/") + "/"
        root_base = os.path.relpath(
            root, os.path.dirname(os.path.abspath(path))).replace(os.sep, "/")
        document = document_of_view(view, code_db, page_base,
                                    "" if root_base == "." else root_base + "/")
        found    = content(document)
        try:
            with open(path, "wb") as handle:
                handle.write(found if isinstance(found, bytes)
                             else found.encode("utf-8"))
        except OSError as error:
            raise Refused("REFUSED: '%s' cannot be written (%s)"
                          % (path, error.strerror)) from error
        line_list.append("'%s' written -- %i feature(s), %i test(s)"
                         % (path, len(document.feature_tuple),
                            len(document.test_tuple)))
    return line_list


def _code_db(relation, root, cov_dir):
    """
    RETURN: [0] dict, the code of the features
                ('feature_code.code_db_of'); None where no coverage
                output is found or it cannot be read
            [1] str, the NOTE that says why none is shown; None where
                one is
    """
    from ....engine.coverage.api import OutputRefused
    from ....engine.orchestrator.exploration.feature_code import code_db_of
    from .details import coverage_directory_of
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
    html_path, ods_path       = None, None
    cov_html                  = None
    for word in argv:
        if word == "--help":
            from ..._core import man_page
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
        elif word.startswith("--html=") and word[len("--html="):]:
            html_path = word[len("--html="):]
        elif word.startswith("--ods=") and word[len("--ods="):]:
            ods_path = word[len("--ods="):]
        elif word.startswith("--cov-html=") and word[len("--cov-html="):]:
            cov_html = word[len("--cov-html="):]
        else:
            write("REFUSED: 'hwut.report.features' does not take '%s'"
                  % word)
            write(USAGE)
            return E_ExitCode.REFUSED
    if cov_html and not (html_path or ods_path):
        write("REFUSED: '--cov-html' links the feature document to the "
              "coverage pages; name the document with '--html=<file>' or "
              "'--ods=<file>'")
        write(USAGE)
        return E_ExitCode.REFUSED
    return answered(do, Request(directory, matrix_f, code_f, cov_dir,
                                html_path, ods_path, cov_html),
                    write, printed, USAGE)


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded("hwut.report.features", main, sys.argv[1:]))
