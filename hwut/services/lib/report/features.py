"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.report.features' COMMAND LINE -- print what the tree
         below a directory claims to do, and which test runs prove it:
         component -> part -> feature -> test runs and their verdicts.

    hwut.report.features [--matrix] [--code] [--cov-dir=<dir>]
                         [--html=<file>] [--ods=<file>] [--cov-html=<dir>]
                         [--directory=<path>]

THE STATEMENTS READ

    <component>/hwut-features.conf        what the component does, and the
                                          directories below it that are
                                          its parts
    <component>/TEST/hwut-features.conf   the features proven in that
                                          TEST directory
    <top>/hwut-feature-map.conf           the published ids
    a test's '@hwut { }' block            features = ["<name>", ...]

THE PAGE

    COMPONENT <path> (<id>) -- <title>     <n> proven, <n> failing, <n> unproven
        doc        <what the component does>
        keys       <the keys it states itself; they travel downward>
        FEATURES <path>/TEST (<id>)        <n> proven, <n> failing, <n> unproven
            [PROVEN]   <full id> -- <title>
                published   <the published id, where it differs>
                keys        <the keys the feature carries, its own and
                             those of everything above it>
                [PASS] <path>/TEST/<test> [<choice>]
        COMPONENT <path>/<part> ...

    The ID of a feature is the chain of keys from the top of the tree,
    '.' between: the key a file gives a directory in its 'childs', the
    directory's name where it gives none, the feature's name last.

    state of a feature
        PROVEN     one linked test run or more; all of them pass
        FAILING    one linked test run or more; one of them does not
                   pass, or has no verdict in 'GOOD/book.csv'
        UNPROVEN   no linked test run
    RETIRED, a published id bound to none, is listed after the tree.

    A component's counts are its features in each state, summed over
    its parts. Every path is relative to where the face is called.

--matrix: THE LINKS AS A TABLE, one per TEST directory that carries a
feature file, in place of the tree -- a row per test run, a column per
feature, the run's verdict where it links:

    <path>/TEST                    #1    #2    #3
    test-pair.sh [plain]           PASS  .     .
    test-pair.sh [gap]             FAIL  FAIL  .
    test-pair.sh [odd]             .     .     .     <- NONSENSE?
                                               ^ no test run
      #1 line-pairing   FAILING
      #2 missing-side   FAILING
      #3 untested       UNPROVEN

    '#<n>' counts the features of the file in order; it is a column,
    not an id.

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

--html=<file>, --ods=<file>: THE FEATURE DOCUMENT, for somebody else to
open -- one self-contained HTML page, or an OpenDocument spreadsheet.
Four tabs:

    Matrix     a row per feature: id, brief (its title), state, and the
               test runs that implement it with their verdicts
    Tree       the features where they stand: component, the components
               below it, its TEST directory, the features; a component
               with its title and the counts summed from below
    Features   a row per feature: name, title, doc, component
    Tests      a row per test application: file, title, 'doc', its test
               runs with their verdicts ('NONSENSE?' behind one that
               links to no feature), its features

    A feature's id in 'Matrix' leads to its row in 'Features'; a test
    run leads to its test's row in 'Tests'. Only TEST directories that
    state features are in it. The file is written, one line says so, and
    the tree is not printed; both may be asked at once.

    WITH '--code' OR '--cov-dir=<dir>' the 'Features' tab carries, per
    feature, the source lines its test runs executed and no other
    measured run did. WITH '--cov-html=<dir>' -- the directory
    'hwut.cov.conv.to_html' wrote its pages into -- each such source is
    a link to its coverage page, at the first of those lines. The link
    is RELATIVE: the document and the pages travel together.

A FEATURE, A COMPONENT MAY NAME DOCUMENTS where more is said of it:

    forward { title     = "A CAN frame is forwarded to its MOST address."
              documents = ["../README.txt", "../spec/routing.txt#3"] }

    Paths from the file's directory ('#<anchor>' may follow), or URLs.
    The page prints each under the claim as 'see <path>'; the feature
    document makes each a link.

OUTSIDE THE RELATION, named below the tree:

    a test run that names a feature its TEST directory does not define
    NONSENSE?  a test run that links to no feature, in a TEST
        directory that states features. No failure -- its verdict
        stands; 'hwut.help' says what the word means.
    a claim whose 'documents' names a file that does not stand
    files, directories and the map that disagree: a component without
        its file, a file the one above does not list, a listed directory
        where nothing stands, a feature no published id names, a
        published id bound to a feature that is gone => hwut.sanitize
    what a feature file, a component's file or the map states that
        cannot be read

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

from ..._exit import E_ExitCode
from ..face import Refused, Empty, answered
from   hwut.engine.orchestrator.exploration.tree_explorer \
                                 import RootConfMissing
from   hwut.engine.orchestrator.exploration.feature_relation \
                                 import (FEATURE_FILE_NAME, MAP_FILE_NAME,
                                         STATE_TUPLE, DANGLING, MAP_CLASH,
                                         MAP_GONE, MAP_TWIN, MOVED, NO_FILE,
                                         NO_MAP, TWIN, UNLISTED, UNMAPPED,
                                         document_place, mismatch_list,
                                         relation_of_tree)

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
    """WHAT HAPPENED: the page's lines, and how many features stand in
    each state below the directory -- (state, n) in STATE_TUPLE order."""
    line_tuple:  tuple = ()
    count_tuple: tuple = ()


def run_text(path, test, choice):
    """RETURN: str, a test run as the page addresses it:
    '<path>/<test>' or '<path>/<test> [<choice>]'."""
    where = test if path == "." else "%s/%s" % (path, test)
    return where if choice is None else "%s [%s]" % (where, choice)


def feature_text(relation, path, feature):
    """RETURN: str, a feature as the page addresses it: its full id, the
    keys of the chain to its component and its name, joined by '.'."""
    return relation.id_of(path, feature.name)


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


def _statement_line_list(relation, path, depth, doc=None, key_tuple=(),
                         document_tuple=()):
    """RETURN: list[str], the sentences that stand for the component at
    'path': its 'doc' (each of its lines), the 'keys' it states itself,
    and 'see' for each document it names. Nothing for a TEST directory:
    its features belong to its component (exploration R-93)."""
    line_list = []
    for label, text in (("doc", doc),
                        ("keys", ", ".join(key_tuple))):
        if not text: continue
        for i, line in enumerate(text.split("\n")):
            line_list.append(("%s%-10s %s" % (_INDENT * depth,
                                              label if i == 0 else "",
                                              line)).rstrip())
    line_list += ["%ssee        %s%s" % (_INDENT * depth, place, anchor)
                  for place, anchor, _ in (
                      document_place(path, document)
                      for document in document_tuple)]
    return line_list


def _id_text(relation, path):
    """RETURN: str, ' (<id>)' of the component at 'path' -- the chain of
    keys from the top of the tree down to it; for a TEST directory its
    component's. '' for the top itself."""
    chain = ".".join(relation.chain_tuple(path))
    return " (%s)" % chain if chain else ""


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


def matrix_line_list(relation, path):
    """RETURN: list[str], the links of one TEST directory as a table:
    a row per test run, a column per feature ('#<n>', n counting the
    features in file order), the run's verdict where it links and '.'
    where it does not; '<- NONSENSE?' behind a run that links to none,
    '<- no feature defined' behind one that names only what the
    directory does not define, '^ no test run' under a feature nobody
    proves; then the features by column, name and state. Empty where
    the directory carries no feature file."""
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
        line_list.append("  %-*s %-*s  %s" % (head_width, head, name_width,
                                              feature_name(each.feature),
                                              each.state))
    return line_list


def feature_name(feature):
    """RETURN: str, the feature's name -- its key in 'childs'."""
    return feature.name


#  THE CODE OF THE FEATURES, where '--code' asked for it: read once by
#  'do' and looked up by the lines of each TEST directory.
relation_code_db = None
#  THE DIRECTORY THE RELATION WAS ASKED IN, for the documents a feature
#  names: set and cleared by 'do'.
relation_root    = None


def _test_directory_line_list(relation, path, depth):
    """RETURN: list[str], one TEST directory: its head with the counts,
    every feature with its state, and below each the linked test runs
    with their verdicts."""
    test_directory = relation.test_directory_db[path]
    line_list = [_headed("FEATURES %s%s" % (path, _id_text(relation, path)),
                         _count_text(relation.count_of(path)), depth)]
    for each in test_directory.state_tuple:
        title = "" if each.feature.title is None \
                else " -- %s" % each.feature.title
        full_id = feature_text(relation, path, each.feature)
        line_list.append("%s%-10s %s%s"
                         % (_INDENT * (depth + 1), "[%s]" % each.state,
                            full_id, title))
        published = relation.published_of(full_id)
        if published is not None and published != full_id:
            line_list.append("%spublished   %s"
                             % (_INDENT * (depth + 2), published))
        key_tuple = relation.effective_key_tuple(path, each.feature)
        if key_tuple:
            line_list.append("%skeys        %s"
                             % (_INDENT * (depth + 2), ", ".join(key_tuple)))
        line_list += ["%s[%s] %s" % (_INDENT * (depth + 2), run.verdict,
                                     run_text(path, run.test, run.choice))
                      for run in each.run_tuple]
        line_list += ["%ssee          %s%s"
                      % (_INDENT * (depth + 2), place, anchor)
                      for place, anchor, _ in (
                          document_place(path, document)
                          for document in each.feature.document_tuple)]
        line_list += _code_line_list(
            (relation_code_db or {}).get((path, each.feature.key)),
            depth + 2)
    return line_list


def _component_line_list(relation, path, depth):
    """RETURN: list[str], one component and everything below it: its
    head with the counts, its statements, its own TEST directory, then
    its parts in sorted order."""
    component = relation.component_db[path]
    claim     = component.claim
    title = "" if claim is None or claim.title is None \
            else " -- %s" % claim.title
    line_list = [_headed("COMPONENT %s%s%s" % (path, _id_text(relation, path),
                                               title),
                         _count_text(relation.count_of(path)), depth)]
    if claim is not None:
        line_list += _statement_line_list(
            relation, path, depth + 1, claim.doc, claim.key_tuple,
            claim.document_tuple)
    if component.test_directory is not None:
        line_list += _test_directory_line_list(
            relation, component.test_directory, depth + 1)
    for part in component.part_tuple:
        line_list += _component_line_list(relation, part, depth + 1)
    return line_list


def mismatch_text(mismatch):
    """RETURN: str, one disagreement between the files, the directories
    and the map, telegraphic: the directory, then what disagrees."""
    return {
        NO_FILE:   "%(path)s   states no '" + FEATURE_FILE_NAME + "'",
        UNLISTED:  "%(path)s   not in the 'childs' of the directory above",
        MOVED:     "%(path)s   moved here from %(from_path)s",
        DANGLING:  "%(path)s   'childs' lists '%(id)s'; no component "
                   "stands there",
        TWIN:      "%(path)s   'childs' lists '%(id)s' under two keys",
        NO_MAP:    "%(path)s   features stand; no '" + MAP_FILE_NAME + "'",
        UNMAPPED:  "%(path)s   no published id names %(id)s",
        MAP_GONE:  "%(path)s   '%(id)s' is bound to a feature that "
                   "stands no more",
        MAP_TWIN:  "%(path)s   two published ids name %(id)s",
        MAP_CLASH: "%(path)s   '%(id)s' is retired, and a feature has "
                   "that very id",
    }[mismatch.kind] % {"path": mismatch.path, "id": mismatch.id,
                        "from_path": mismatch.from_path}


def _outside_line_list(relation):
    """RETURN: list[str], what stands outside the relation, one block
    per kind, a kind with nothing to name left out; empty where
    everything stands inside."""
    undefined, unlinked, fault = [], [], []
    absent = []
    for path in sorted(relation.test_directory_db):
        each = relation.test_directory_db[path]
        #  A TEST DIRECTORY WITHOUT A FEATURE FILE IS NOT NAMED: feature
        #  files are not mandatory (ruled 2026-10-11, E-144).
        if each.feature_file is not None:
            unlinked += [run_text(path, test, choice)
                         for test, choice in each.unlinked_tuple]
            for state in each.state_tuple:
                for document in state.feature.document_tuple:
                    place, _, url_f = document_place(path, document)
                    if url_f or relation_root is None: continue
                    if not os.path.exists(os.path.join(relation_root,
                                                       place)):
                        absent.append("%s   '%s'"
                                      % (feature_text(relation, path,
                                                      state.feature),
                                         document))
            fault += ["%s/%s" % (path, f) if path != "." else "%s" % f
                      for f in each.feature_file.fault_tuple]
        undefined += ["%s   '%s'" % (run_text(path, test, choice), name)
                      for test, choice, name in each.undefined_tuple]
    for path in sorted(relation.component_db):
        each = relation.component_db[path]
        if each.claim is None: continue
        fault += ["%s/%s" % (path, f) if path != "." else "%s" % f
                  for f in each.claim.fault_tuple]
        for document in each.claim.document_tuple:
            place, _, url_f = document_place(path, document)
            if url_f or relation_root is None: continue
            if not os.path.exists(os.path.join(relation_root, place)):
                absent.append("%s   '%s'" % (path, document))
    if relation.feature_map is not None:
        fault += ["%s: %s" % (MAP_FILE_NAME, f)
                  for f in relation.feature_map.fault_tuple]
    line_list = []
    for head, entry_list in (
            ("test run, names a feature its TEST directory does not "
             "define", undefined),
            ("NONSENSE? test run, links to no feature => hwut.help",
             unlinked),
            ("claim, names a document that does not stand", absent),
            ("statement, not read", fault),
            ("files, directories and map, not as they should stand => "
             "hwut.sanitize.propose --relations",
             [mismatch_text(each) for each in mismatch_list(relation)])):
        if not entry_list: continue
        line_list.append("%s%s" % (_INDENT, head))
        line_list += ["%s%s" % (_INDENT * 2, entry) for entry in entry_list]
    if line_list:
        line_list = ["", "OUTSIDE THE RELATION"] + line_list
    return line_list


def _retired_line_list(relation):
    """RETURN: list[str], the RETIRED block: the published ids the map
    binds to none -- features no longer claimed; empty where there are
    none."""
    retired = relation.retired_tuple()
    if not retired: return []
    return ["", _headed("RETIRED", "%i retired" % len(retired), 0)] \
           + ["%s[RETIRED]  %s" % (_INDENT, each) for each in retired]


def do(request):
    """
    RETURN: Result, the page of the tree below 'request.directory' and
            the counts of its features by state.

    RAISES: Refused, where the directory does not stand or no root conf
            is above it; Empty, where no TEST directory stands below.

    IT NEVER PRINTS (E-101).
    """
    global relation_code_db, relation_root
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

    count_db = dict.fromkeys(STATE_TUPLE, 0)
    for path in relation.test_directory_db:
        for state, n in relation.count_of(path).items():
            count_db[state] += n
    count_tuple = tuple((state, count_db[state]) for state in STATE_TUPLE)

    if request.html_path or request.ods_path:
        return Result(tuple(_document_written(relation, request, root)),
                      count_tuple)
    relation_root = root

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
    if not request.matrix_f: line_list += _retired_line_list(relation)
    line_list += _outside_line_list(relation)
    relation_code_db = None
    relation_root    = None
    return Result(tuple(line_list), count_tuple)


def _document_written(relation, request, root):
    """
    RETURN: list[str], one line per file of the feature document
            written: "'<file>' written -- <n> feature(s), <m> test(s)";
            before them the NOTE that says why no code is in it, where
            code was asked and no coverage output could be read

    RAISES: Refused, where a file cannot be written, or '--cov-html'
            names no directory.
    """
    from .feature_document import (document_of,
                                                          html_text,
                                                          ods_bytes)
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
        document = document_of(relation, code_db, page_base,
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
