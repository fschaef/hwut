"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.report.features' COMMAND LINE -- print what the tree
         claims to do, and which test runs prove it, as the forest groups
         it (spec 43 sections 4, 5).

    hwut.report.features [<id>]... [--matrix] [--code] [--cov-dir=<dir>]
                         [--html=<file>] [--ods=<file>] [--cov-html=<dir>]
                         [--directory=<path>]

THE STATEMENTS READ, beside the 'hwut-root.conf' that begins the features:

    hwut-feature-forest.csv         the place: '<id> : <child>, ...'
    hwut-feature-doc.dat            the explanation: '[[<id>]]' blocks,
                                    the retired, the audiences
    hwut-feature-external-map.csv   the outside's names, where it stands
    a test's '@hwut { }' block      features = ["<id>", ...]

    Where no forest stands, nothing is reported => hwut.features.init.

THE PAGE

    AGGREGATE <tree path> -- <title>   <n> implemented, <n> open; <n> ok, <n> fail, <n> untested
        state      IMPLEMENTED ok | IMPLEMENTED fail | IMPLEMENTED untested
                   | OPEN fail | OPEN untested
        doc        <the rest of its block>
        [IMPLEMENTED ok]   <id> -- <title>
            audience    <whom it concerns>
            names       <the outside's names for it>
            [PASS] <path>/TEST/<test> [<choice>]
    UNPLACED        the documented features in no forest line
    RETIRED         the retired blocks

    A feature with children is an AGGREGATE line; every feature folds ITS
    OWN RUNS AND ITS CHILDREN'S (T-n): IMPLEMENTED where it has runs or
    children and no child is OPEN, else OPEN; its verdict the worst below
    it -- fail, then untested, then ok. One with neither is OPEN untested.
    RETIRED has no verdict. The counts are those of the features with no
    children. The whole tree below the top is read whichever directory the
    face is called in; every path is written from there.

<id>...: A BARE FEATURE ID CUTS THE PAGE (T-u): the subtree of that id, the
features above it as headers, folded and counted over what is kept; several
ids are a union; no RETIRED, no OUTSIDE THE RELATION. An id the forest and
the doc file do not hold is refused by name, with 'did you mean'; a retired
one likewise. '--matrix' is refused beside an id.

--matrix: THE LINKS AS A TABLE, one per TEST directory whose runs link a
feature, in place of the tree -- a row per test run, a column per feature
linked there, the run's verdict where it links:

    <path>/TEST                    #1    #2
    test-pair.sh [plain]           PASS  .
    test-pair.sh [gap]             FAIL  FAIL
    test-pair.sh [odd]             .     .     <- NONSENSE?
      #1 line-pairing   IMPLEMENTED fail
      #2 missing-side   IMPLEMENTED fail

    '#<n>' counts the features in the order the directory first links
    them; it is a column, not an id. A column is named by the feature's
    state, 'stands nowhere' or 'retired' where it has none. '--code' adds
    nothing to a table.

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

--html=<file>, --ods=<file>: THE FEATURE DOCUMENT, for somebody else to
open -- one self-contained HTML page, or an OpenDocument spreadsheet.
Four tabs:

    Matrix     a row per feature: id, brief (its title), state, and the
               test runs that implement it with their verdicts
    Tree       the forest, each feature with children with its title, its
               state and the counts summed from below
    Features   a row per feature: id, title, doc, the feature above it,
               state, the outside's names, its audiences
    Tests      a row per test application: file, title, 'doc', its test
               runs with their verdicts ('NONSENSE?' behind one that
               links to no feature), its features

    A row is a feature with no children, or one with runs of its own. An
    id in 'Matrix' leads to its row in 'Features'; a test run leads to its
    test's row in 'Tests'. The file is written, one line says so, and the
    tree is not printed; both may be asked at once.

    WITH '--code' OR '--cov-dir=<dir>' the 'Features' tab carries, per
    feature, the source lines its test runs executed and no other
    measured run did. WITH '--cov-html=<dir>' -- the directory
    'hwut.cov.conv.to_html' wrote its pages into -- each such source is
    a link to its coverage page, at the first of those lines. The link
    is RELATIVE: the document and the pages travel together.

A FEATURE MAY NAME DOCUMENTS where more is said of it, on the first line of
its block:

    [[forward]]
    documents: router/README.txt, spec/routing.txt#3
    A CAN frame is forwarded to its MOST address.

    Paths from the doc file's directory ('#<anchor>' may follow), or URLs.
    The page prints each under the feature as 'see <path>'; the feature
    document makes each a link.

OUTSIDE THE RELATION, named below the tree:

    a test run that links an id standing in no forest line and no block
    a test run that links a retired feature
    NONSENSE?  a test run that links to no feature, in a TEST directory
        whose other runs link one. No failure -- its verdict stands;
        'hwut.help' says what the word means.
    a feature that names a document that does not stand
    what the files disagree on => hwut.features.register

The verdicts are those of 'GOOD/book.csv': nothing is run.

EXIT STATUS
    0    TEST directories stand, and the page was printed
    2    the command line cannot be read, no root bounds the tree, no
         readable forest stands at its top, or an id cuts nothing
    3    no TEST directory stands below the top
______________________________________________________________________________
"""
import os
import sys
from   dataclasses import dataclass

from ..._exit import E_ExitCode
from ..face import Refused, Empty, answered, write_refusal
from   hwut.engine.orchestrator.exploration.tree_explorer \
                                 import RootConfMissing
from   hwut.engine.orchestrator.exploration.feature_relation \
                                 import document_place
from   hwut.engine.orchestrator.exploration.feature_view \
                                 import (view_of, view_kept, ViewRefused,
                                         IMPLEMENTED, OPEN, OK, FAIL,
                                         UNTESTED)
from   ..cmdline import did_you_mean

USAGE = ("usage: hwut.report.features [<id>]... [--matrix] [--code] "
         "[--cov-dir=<dir>] [--html=<file>] [--ods=<file>] "
         "[--cov-html=<dir>] [--directory=<path>] [--help]")

_INDENT = "    "
_WIDTH  = 78


@dataclass(frozen=True)
class Request:
    """WHAT WAS ASKED of 'hwut.report.features': the directory the tree is
    read from; 'id_tuple' the feature ids that cut the page (T-u), empty:
    all; 'matrix_f' the links as tables in place of the tree; 'code_f' the
    code each feature's runs went through, read from 'cov_dir' or the
    nearest coverage output; 'html_path' and 'ods_path' the files the
    feature document is written to, in place of the page."""
    directory: str        = "."
    matrix_f:  bool       = False
    code_f:    bool       = False
    cov_dir:   str | None = None
    html_path: str | None = None
    ods_path:  str | None = None
    cov_html:  str | None = None     # where the coverage pages stand
    id_tuple:  tuple      = ()


@dataclass(frozen=True)
class Result:
    """WHAT HAPPENED: the page's lines, and how many leaves stand in each
    state below the directory -- (state, n): IMPLEMENTED, OPEN, OK, FAIL,
    UNTESTED."""
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


def matrix_line_list(view, path):
    """RETURN: list[str], the links of one TEST directory as a table: a
    row per test run, a column per feature its runs link ('#<n>', n
    counting the features in the order the directory first links them),
    the run's verdict where it links and '.' where it does not;
    '<- NONSENSE?' behind a run that links to none; then the features by
    column, id and state -- 'stands nowhere' or 'retired' where the
    feature has none. Empty where no run of the directory links one."""
    test_directory = view.relation.test_directory_db[path]
    if not test_directory.linking_f(): return []
    column_list = []
    for _, _, feature_id in test_directory.link_tuple:
        if feature_id not in column_list: column_list.append(feature_id)
    head_list = ["#%i" % (column + 1) for column in range(len(column_list))]
    cell_db   = {}               # (test, choice) -> {column: verdict}
    for test, choice, feature_id in test_directory.link_tuple:
        cell_db.setdefault((test, choice), {})[
            column_list.index(feature_id)] = \
            test_directory.verdict_db[(test, choice)]
    shown     = view.run_path(_CRunAt(path))
    name_list = [run_text(".", test, choice)
                 for test, choice in test_directory.run_tuple]
    width_0   = max([len(name) for name in name_list] + [len(shown)])
    width     = max([len(head) for head in head_list]
                    + [len(verdict) for row in cell_db.values()
                       for verdict in row.values()] + [1])

    def row(first, cell_list, tail=""):
        """RETURN: str, one table row, cells left-aligned in columns."""
        return ("%-*s  %s%s" % (width_0, first,
                                "  ".join("%-*s" % (width, cell)
                                          for cell in cell_list),
                                tail)).rstrip()

    line_list = [row(shown, head_list)]
    for name, key in zip(name_list, test_directory.run_tuple):
        linked = cell_db.get(key, {})
        line_list.append(row(name, [linked.get(column, ".")
                                    for column in range(len(column_list))],
                             "" if linked else "  <- NONSENSE?"))
    retired    = view.features.retired_set()
    name_width = max(len(each) for each in column_list)
    head_width = max(len(head) for head in head_list)
    for head, feature_id in zip(head_list, column_list):
        node  = view.node_of(feature_id)
        state = view_state_text(node.state) if node is not None \
                else "retired" if feature_id in retired else "stands nowhere"
        line_list.append("  %-*s %-*s  %s" % (head_width, head, name_width,
                                              feature_id, state))
    return line_list


@dataclass(frozen=True)
class _CRunAt:
    """A place for 'CView.run_path': a TEST directory as the relation
    addresses it."""
    path: str


#  THE CODE OF THE FEATURES, where '--code' asked for it: read once by
#  'do' and looked up by each feature's lines.
relation_code_db = None


def _view_count_text(count_db):
    """RETURN: str, '<n> implemented, <n> open; <n> ok, <n> fail, <n>
    untested' -- the implementation axis, then the verdict axis."""
    return "%i implemented, %i open; %i ok, %i fail, %i untested" % (
        count_db[IMPLEMENTED], count_db[OPEN], count_db[OK], count_db[FAIL],
        count_db[UNTESTED])


def view_state_text(state):
    """RETURN: str, a claim's state on its two axes as the page writes it:
    '<IMPLEMENTED|OPEN> <ok|fail|untested>'; 'RETIRED' alone."""
    if state.verdict is None:
        return state.implementation
    return "%s %s" % (state.implementation, state.verdict)


def _node_detail_line_list(view, node, depth, width=11):
    """RETURN: list[str], what stands under a feature at 'depth': its
    audiences, the outside's names ('width' the column of their label),
    its own linked runs, the documents it names, the code its runs
    reached."""
    lead      = _INDENT * depth
    line_list = []
    if node.audience_tuple:
        line_list.append("%s%-*s %s" % (lead, width, "audience",
                                        ", ".join(node.audience_tuple)))
    if node.external_tuple:
        line_list.append("%s%-*s %s" % (lead, width, "names",
                                        ", ".join(node.external_tuple)))
    line_list += ["%s[%s] %s" % (lead, run.verdict,
                                 run_text(view.run_path(run), run.test,
                                          run.choice))
                  for run in node.run_tuple]
    if node.entry is not None:
        doc_path = os.path.relpath(view.top, view.asked).replace(os.sep, "/")
        #  'see' as the page always wrote it: a column wider under a
        #  feature than under an aggregate.
        see = "see".ljust(width + 1 if width == 11 else width)
        line_list += ["%s%s %s%s" % (lead, see, place, anchor)
                      for place, anchor, _ in (
                          document_place(doc_path, document)
                          for document in node.entry.document_tuple)]
    line_list += _code_line_list((relation_code_db or {}).get(node.id),
                                 depth)
    return line_list


def _view_leaf_line_list(view, node, depth):
    """RETURN: list[str], one feature with no children: its state, id and
    title, then its details."""
    title = "" if node.entry is None or not node.entry.title \
            else " -- %s" % node.entry.title
    return ["%s%-18s %s%s" % (_INDENT * depth,
                              "[%s]" % view_state_text(node.state),
                              node.id, title)] \
           + _node_detail_line_list(view, node, depth + 1)


def _view_aggregate_line_list(view, node, depth):
    """RETURN: list[str], one feature with children and everything below
    it: its head with the counts, its state, its doc, its details, then
    its children in forest order."""
    entry = node.entry
    title = "" if entry is None or not entry.title else " -- %s" % entry.title
    line_list = [_headed("AGGREGATE %s%s" % (node.tree_path, title),
                         _view_count_text(node.count_db), depth)]
    line_list.append("%s%-10s %s" % (_INDENT * (depth + 1), "state",
                                     view_state_text(node.state)))
    line_list += _statement_line_list(depth + 1,
                                      None if entry is None else entry.doc)
    line_list += _node_detail_line_list(view, node, depth + 1, 10)
    for each in node.child_tuple:
        if each.child_tuple:
            line_list += _view_aggregate_line_list(view, each, depth + 1)
        else:
            line_list += _view_leaf_line_list(view, each, depth + 1)
    return line_list


def _view_retired_line_list(view):
    """RETURN: list[str], the RETIRED block: every retired doc block by
    its id; empty where none is."""
    if not view.retired_tuple: return []
    line_list = ["", _headed("RETIRED", "%i retired"
                             % len(view.retired_tuple), 0)]
    for each in view.retired_tuple:
        line_list.append("%s[RETIRED]  %s%s" % (
            _INDENT, each.id, " -- %s" % each.title if each.title else ""))
    return line_list


def _view_outside_line_list(view):
    """RETURN: list[str], what stands outside the relation, one block per
    kind: the links to what stands nowhere or is retired, the runs that
    link nothing beside runs that do, the documents that do not stand,
    and what the detector finds of the files."""
    from hwut.engine.orchestrator.exploration.feature_detector \
        import detect, UNPLACED, OUTSIDE
    from hwut.engine.orchestrator.exploration.feature_view \
        import OUTSIDE_RETIRED
    relation = view.relation
    nowhere, retired, unlinked, absent = [], [], [], []
    for path, test, choice, feature_id, why in view.outside_tuple:
        entry = "%s   '%s'" % (run_text(view.run_path(_CRunAt(path)), test,
                                         choice), feature_id)
        if why == OUTSIDE_RETIRED: retired.append(entry)
        else:                      nowhere.append(entry + why[len(
            "stands in no forest line and no doc block"):])
    for path in sorted(relation.test_directory_db):
        each = relation.test_directory_db[path]
        if each.linking_f():
            unlinked += [run_text(view.run_path(_CRunAt(path)), test,
                                  choice)
                         for test, choice in each.unlinked_tuple]
    doc_path = os.path.relpath(view.top, view.asked).replace(os.sep, "/")
    for node in view.node_list():
        if node.entry is None: continue
        for document in node.entry.document_tuple:
            place, _, url_f = document_place(doc_path, document)
            if url_f: continue
            if not os.path.exists(os.path.join(view.asked, place)):
                absent.append("%s   '%s'" % (node.id, document))
    finding = [each.text[len("NOTE  "):] for each in detect(view)
               if each.kind not in (UNPLACED, OUTSIDE)]
    line_list = []
    for head, entry_list in (
            ("test run, links an id that stands in no forest line and no "
             "doc block", nowhere),
            ("test run, links a retired feature", retired),
            ("NONSENSE? test run, links to no feature => hwut.help",
             unlinked),
            ("claim, names a document that does not stand", absent),
            ("feature files, not as they should stand => "
             "hwut.features.register", finding)):
        if not entry_list: continue
        line_list.append("%s%s" % (_INDENT, head))
        line_list += ["%s%s" % (_INDENT * 2, entry) for entry in entry_list]
    if line_list:
        line_list = ["", "OUTSIDE THE RELATION"] + line_list
    return line_list


def _view_do(view, request, root):
    """RETURN: Result, the page of 'view' (see 'do')."""
    global relation_code_db
    count_db    = view.count_db()
    count_tuple = tuple((state, count_db[state])
                        for state in (IMPLEMENTED, OPEN, OK, FAIL,
                                      UNTESTED))
    if request.html_path or request.ods_path:
        return Result(tuple(_document_written(view.relation, request, root,
                                              view)), count_tuple)
    note_list   = []
    relation_code_db = None
    if request.code_f or request.cov_dir:
        relation_code_db, note = _code_db(view, root, request.cov_dir)
        if note: note_list.append(note)
    if request.matrix_f:
        line_list = []
        for path in sorted(view.relation.test_directory_db):
            found = matrix_line_list(view, path)
            if found: line_list += found + [""]
        if line_list: line_list.pop()
        else:         line_list = ["no test run links a feature"]
    else:
        line_list = []
        for each in view.root_tuple:
            line_list += _view_aggregate_line_list(view, each, 0) \
                         if each.child_tuple \
                         else _view_leaf_line_list(view, each, 0)
        if view.unplaced:
            if line_list: line_list.append("")
            line_list.append(_headed("UNPLACED", "%i feature(s)"
                                     % len(view.unplaced), 0))
            for each in view.unplaced:
                line_list += _view_leaf_line_list(view, each, 1)
        line_list += _view_retired_line_list(view)
    #  A CUT SHOWS THE FEATURES ASKED FOR: what stands outside the
    #  relation is the whole tree's matter, not theirs.
    line_list = note_list + line_list \
                + ([] if request.id_tuple else _view_outside_line_list(view))
    relation_code_db = None
    return Result(tuple(line_list), count_tuple)


def do(request):
    """
    RETURN: Result, the page of the tree 'request.directory' stands in and
            the counts of its features by state.

    RAISES: Refused, where the directory does not stand, no root conf is
            above it, no readable forest stands at its top, or an id of
            'request.id_tuple' cuts nothing; Empty, where no TEST
            directory stands below the top.

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
    if request.id_tuple:
        known   = view.features.known_set()
        retired = view.features.retired_set()
        for feature_id in request.id_tuple:
            if feature_id in retired:
                raise Refused("REFUSED: '%s' is a RETIRED feature: it "
                              "stands in no forest line" % feature_id)
            if feature_id not in known:
                raise Refused("REFUSED: '%s' stands in no forest line and "
                              "no doc block%s" % (feature_id, did_you_mean(
                                  feature_id, sorted(known))))
        view = view_kept(view, set(request.id_tuple))
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
        code_db, note = _code_db(view, root, request.cov_dir)
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


def _code_db(view, root, cov_dir):
    """
    RETURN: [0] dict, the code of the features
                ('feature_code.code_db_of', feature id -> CFeatureCode);
                None where no coverage output is found or it cannot be
                read
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
        relation = view.relation
        top_rel  = os.path.relpath(view.top, root)
        run_db   = {node.id: tuple(
                        type(run)(run.test, run.choice, run.verdict,
                                  os.path.normpath(os.path.join(
                                      top_rel, run.path)).replace(os.sep,
                                                                  "/"))
                        for run in node.run_tuple)
                    for node in view.node_list() if node.run_tuple}
        found = code_db_of(_relation_from(relation, top_rel), root,
                           output_directory, run_db)
    except OutputRefused as refusal:
        return None, "NOTE: %s; no code shown" % refusal
    if found is None:
        return None, ("NOTE: '%s' names no root it measured; no code shown"
                      % os.path.relpath(output_directory))
    return found, None


def _relation_from(relation, top_rel):
    """RETURN: CRelation, 'relation' (asked at the top) with its TEST
    directories addressed from the directory asked ('top_rel' the way
    from there to the top)."""
    from dataclasses import replace
    return replace(relation, test_directory_db={
        os.path.normpath(os.path.join(top_rel, path)).replace(os.sep, "/"):
        each for path, each in relation.test_directory_db.items()})


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
    id_list                   = []
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
        elif word in ("-F", "--feature", "-e", "--feature-ext", "-k",
                      "--keys") or word.startswith(("--feature=",
                                                    "--feature-ext=",
                                                    "--keys=")):
            from ....engine.orchestrator.plan.wish import \
                _feature_retired_text
            write_refusal(write, "REFUSED: %s -- here a bare id cuts the "
                          "page: 'hwut.report.features <id>'"
                          % _feature_retired_text(word).split(" =>")[0],
                          USAGE)
            return E_ExitCode.REFUSED
        elif not word.startswith("-"):
            if word not in id_list: id_list.append(word)
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
    if matrix_f and id_list:
        write("REFUSED: '--matrix' shows every link of each TEST directory; "
              "an id cuts the tree => without '--matrix'")
        return E_ExitCode.REFUSED
    return answered(do, Request(directory, matrix_f, code_f, cov_dir,
                                html_path, ods_path, cov_html,
                                tuple(id_list)),
                    write, printed, USAGE)


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ..._exit import guarded
    sys.exit(guarded("hwut.report.features", main, sys.argv[1:]))
