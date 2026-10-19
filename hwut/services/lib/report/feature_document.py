"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FEATURE DOCUMENT -- the features of a tree as the central
         file groups them ('feature_view', R-96), as ONE file somebody
         else opens: HTML, or an OpenDocument spreadsheet.

    document_of_view(view)  -> CDocument     what the document says
    html_text(document)     -> str           one self-contained page
    ods_bytes(document)     -> bytes         one '.ods' file

FOUR TABS, and the ways between them:

    Matrix     one row per leaf: its external id, its brief (the title),
               its state, and what IMPLEMENTS it -- the linked test runs
               with their verdicts.
                   the external id    -> its place in 'Features'
                   a test run         -> its test's place in 'Tests'
    Features   one row per leaf: where it is EXPLAINED -- name, title,
               doc, the aggregate it stands in, its internal id.
    Tests      one row per test application: file, title, 'doc', its
               test runs with their verdicts -- 'NONSENSE?' behind a
               run that links to no feature -- and the features it
               links to; a name its TEST directory does not define is
               said.

    Tree       the aggregates and their leaves in file order -- each
               aggregate with its title, its state and its counts summed
               from below, each leaf leading to its row in 'Features';
               the unplaced last.
               INTERACTIVE: the page folds and unfolds every level,
               shows the features of chosen states, and those whose
               line holds a word; the spreadsheet carries the levels as
               row groups, folded at its margin.

A FEATURE'S DOCUMENTS ('documents' in the feature file) stand in
'Features', each a link from where the document is written. So do its
INTERNAL ID and the KEYS it carries -- its own, its TEST file's, the
aggregates' above it.

'Features' CARRIES THE CODE where a coverage output was read (services
E-147): per feature the source lines its test runs executed and no other
measured run did. Where the face names the directory of the coverage
pages ('hwut.cov.conv.to_html'), each source is a link to its page, at
the first of those lines.

Only TEST directories that state features are in the document: feature
files are not mandatory, and a directory without one says nothing here.

NOTHING IN THE DOCUMENT DEPENDS ON THE MACHINE OR THE HOUR: no date, no
absolute path; the '.ods' archive carries one fixed time stamp. The same
tree yields the same bytes.

BOTH FORMATS ARE WRITTEN WITH THE STANDARD LIBRARY: the page is text,
the spreadsheet a zip of three XML texts.
______________________________________________________________________________
"""
import io
import zipfile
from   dataclasses import dataclass
from   html        import escape

from   hwut.engine.orchestrator.exploration.feature_relation \
                                 import document_place

#  THE STATES A LEAF STANDS IN, as the page writes them (R-96).
STATE_TUPLE = ("IMPLEMENTED ok", "IMPLEMENTED fail", "IMPLEMENTED untested",
               "OPEN untested")

NONSENSE_WORD = "NONSENSE?"


@dataclass(frozen=True)
class CFeatureRow:
    """One feature. 'index' is its row in 'Features' and 'Matrix',
    counted from 0; 'run_tuple' holds (text, verdict, test index);
    'code_tuple' (text, link or None) -- a source with the lines only
    this feature's runs executed, then what is said without a link;
    'document_tuple' (text, link) -- the documents the feature names."""
    index:       int
    id_text:     str                   # the external id
    name:        str
    title:       str
    doc:         str
    component:   str                   # the aggregate's tree path
    state:       str
    run_tuple:   tuple = ()
    code_tuple:  tuple = ()
    document_tuple: tuple = ()
    published:   str = ""              # the internal id and its directory
    key_text:    str = ""              # the keys it carries, ', ' between


@dataclass(frozen=True)
class CTreeRow:
    """One line of the feature tree. 'kind' is 'component' (an aggregate)
    or 'feature' (a leaf); 'feature_index' the leaf's row, None for an
    aggregate."""
    depth:         int
    kind:          str
    label:         str
    detail:        str  = ""           # title, or what the component does
    state:         str  = ""           # counts, or a feature's state
    feature_index: int | None = None


@dataclass(frozen=True)
class CTestRow:
    """One test application. 'run_tuple' holds (choice text, verdict,
    nonsense flag -- the run links to no feature); 'feature_tuple'
    (feature id text, feature index); 'undefined_tuple' the feature
    names it links to that its TEST directory does not define."""
    index:         int
    path:          str                 # '<TEST directory>/<file>'
    title:         str
    doc:           str
    run_tuple:     tuple = ()
    feature_tuple: tuple = ()
    undefined_tuple: tuple = ()


@dataclass(frozen=True)
class CDocument:
    """What the feature document says."""
    title:        str
    feature_tuple: tuple = ()          # of CFeatureRow
    test_tuple:    tuple = ()          # of CTestRow
    count_tuple:   tuple = ()          # of (state, n), STATE_TUPLE order
    tree_tuple:    tuple = ()          # of CTreeRow
    code_f:        bool  = False       # a coverage output was read
    document_f:    bool  = False       # a feature names a document


def span_text(range_tuple):
    """RETURN: str, half-open line ranges as a reader counts them:
    'first..last', a single line alone, ', ' between."""
    return ", ".join("%i..%i" % (begin, end - 1) if end - begin > 1
                     else "%i" % begin for begin, end in range_tuple)


def _code_tuple(code, page_base):
    """RETURN: tuple of (text, link or None), what 'Features' says of
    one feature's code ('feature_code.CFeatureCode'; None gives ()):
    per source the lines only its runs executed -- a link to the
    source's coverage page at the first of them where 'page_base' names
    where the pages stand -- then the shared lines and the runs not
    measured, as counts."""
    if code is None: return ()
    found = []
    for source, spans, measured in code.only_tuple:
        link = None if page_base is None \
               else "%s%s.html#L%i" % (page_base, measured, spans[0][0])
        found.append(("%s: %s" % (source, span_text(spans)), link))
    if code.shared_line_n:
        found.append(("shared: %i line(s) in %i file(s)"
                      % (code.shared_line_n, code.shared_file_n), None))
    if code.unmeasured_n:
        found.append(("%i of %i linked run(s) not measured"
                      % (code.unmeasured_n,
                         code.unmeasured_n + code.measured_n), None))
    return tuple(found)


def document_of_view(view, code_db=None, page_base=None, root_base=""):
    """
    RETURN: CDocument, the features as the central file groups them
            ('feature_view.CView', R-96): a row per leaf -- the tree's in
            file order, then the unplaced -- its EXTERNAL id as its id, its
            aggregate's tree path, its internal id and directory, its state
            on two axes;
            the test applications of every TEST directory that states
            features; the tree of aggregates. 'code_db' is what
            'feature_code.code_db_of' found, None where no coverage output
            was read; 'page_base' the way from the document to the coverage
            pages, '/' at its end, None where they are not linked;
            'root_base' the way from the document to the directory asked,
            '/' at its end or '' -- what a feature's 'documents' are linked
            through. A feature its TEST directory defines and the
            central file does not register has no row ('hwut.report.features'
            names it).
    """
    from hwut.services.lib.report.features import view_state_text
    relation   = view.relation
    test_db    = {}                    # (test path, test) -> index
    for path in sorted(relation.test_directory_db):
        directory = relation.test_directory_db[path]
        #  A DIRECTORY THAT DEFINES NOTHING stands where its tests link
        #  features of others by internal id (the book's D-8).
        if directory.feature_file is None \
           and not directory.foreign_tuple: continue
        for test, _, _ in directory.app_tuple:
            test_db[(path, test)] = len(test_db)
    feature_list, linked_db, index_of_leaf = [], {}, {}
    for leaf_view in view.leaf_list():
        index   = len(feature_list)
        leaf    = leaf_view.leaf
        found   = leaf_view.feature_state
        feature = None if found is None else found.feature
        path    = leaf_view.test_path
        run_list = []
        for run in (() if found is None else found.run_tuple):
            test_index = test_db.get((run.path or path, run.test))
            if test_index is None: continue
            run_list.append((_run_text(run.test, run.choice), run.verdict,
                             test_index))
            linked = linked_db.setdefault(test_index, [])
            if (leaf.external, index) not in linked:
                linked.append((leaf.external, index))
        index_of_leaf[leaf.internal] = index
        feature_list.append(CFeatureRow(
            index, leaf.external, leaf.name,
            "" if feature is None else feature.title or "",
            "" if feature is None else feature.doc or "",
            leaf_view.tree_path or "(unplaced)",
            view_state_text(leaf_view.state), tuple(run_list),
            () if feature is None else _code_tuple(
                (code_db or {}).get((path, feature.key)), page_base),
            () if feature is None else tuple(
                (place + anchor,
                 place if url_f else root_base + place + anchor)
                for place, anchor, url_f in (
                    document_place(path, document)
                    for document in feature.document_tuple)),
            "%s  (%s)" % (leaf.internal,
                          leaf_view.directory_path or "no directory"),
            ", ".join(leaf_view.key_tuple)))
    test_list = []
    for path in sorted(relation.test_directory_db):
        directory = relation.test_directory_db[path]
        if directory.feature_file is None \
           and not directory.foreign_tuple: continue
        #  NONSENSE? only where the directory defines features (R-7).
        unlinked = set(directory.unlinked_tuple) \
                   if directory.feature_file is not None else set()
        for test, title, doc in directory.app_tuple:
            index = test_db[(path, test)]
            test_list.append(CTestRow(
                index, test if path == "." else "%s/%s" % (path, test),
                title or "", doc or "",
                tuple(("-" if choice is None else choice,
                       directory.verdict_db[(run_test, choice)],
                       (run_test, choice) in unlinked)
                      for run_test, choice in directory.run_tuple
                      if run_test == test),
                tuple(linked_db.get(index, ())),
                tuple(sorted(set(name for run_test, _, name
                                 in directory.undefined_tuple
                                 if run_test == test)))))
    return CDocument(
        "Features of '%s'" % relation.root_name,
        tuple(feature_list), tuple(test_list),
        tuple((state, sum(1 for row in feature_list if row.state == state))
              for state in STATE_TUPLE),
        _view_tree_tuple(view, index_of_leaf), code_db is not None,
        any(row.document_tuple for row in feature_list))


def _view_tree_tuple(view, index_of_leaf):
    """RETURN: tuple of CTreeRow, the aggregates and their leaves in file
    order, each aggregate with its title and counts, each leaf leading to its
    row; then the unplaced under '(unplaced)'."""
    from hwut.services.lib.report.features import (view_state_text,
                                                   _view_count_text)
    row_list = []

    def walk(child_tuple, depth):
        for each in child_tuple:
            if hasattr(each, "aggregate"):
                aggregate = each.aggregate
                row_list.append(CTreeRow(
                    depth, "component", aggregate.key,
                    " -- ".join(text for text in (aggregate.title,
                                                  aggregate.doc) if text),
                    "%s; %s" % (view_state_text(each.state),
                                _view_count_text(each.count_db))))
                walk(each.child_tuple, depth + 1)
            else:
                feature = None if each.feature_state is None \
                          else each.feature_state.feature
                row_list.append(CTreeRow(
                    depth, "feature", each.leaf.external,
                    "" if feature is None else feature.title or "",
                    view_state_text(each.state),
                    index_of_leaf[each.leaf.internal]))

    walk(view.top_tuple, 0)
    if view.unplaced:
        row_list.append(CTreeRow(0, "component", "(unplaced)", "",
                                 "%i leaf/leaves" % len(view.unplaced)))
        walk(view.unplaced, 1)
    return tuple(row_list)


def _run_text(test, choice):
    """RETURN: str, '<test>' or '<test> [<choice>]'."""
    return test if choice is None else "%s [%s]" % (test, choice)


# -- HTML ------------------------------------------------------------------

_STYLE = """
:root { --ground:#ffffff; --ink:#1b1f24; --dim:#5b6570; --line:#d5dae0;
        --band:#f2f4f7; --link:#0b57a4; --good:#1a7f37; --bad:#c62828;
        --none:#8a6d00; --mark:#fff3bf; }
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
        --ground:#14171b; --ink:#e6e9ed; --dim:#9aa4af; --line:#333a43;
        --band:#1d2228; --link:#7ab7ff; --good:#56d364; --bad:#ff7b72;
        --none:#e3b341; --mark:#4d4000; } }
:root[data-theme="dark"] {
        --ground:#14171b; --ink:#e6e9ed; --dim:#9aa4af; --line:#333a43;
        --band:#1d2228; --link:#7ab7ff; --good:#56d364; --bad:#ff7b72;
        --none:#e3b341; --mark:#4d4000; }
body { background:var(--ground); color:var(--ink); margin:0;
       font:15px/1.45 system-ui, sans-serif; }
header, main { padding:0 16px; max-width:1200px; margin:0 auto; }
h1 { font-size:20px; margin:18px 0 4px; }
p.count { color:var(--dim); margin:0 0 14px; }
nav { display:flex; gap:4px; border-bottom:1px solid var(--line);
      position:sticky; top:0; background:var(--ground); }
nav a { padding:8px 14px; text-decoration:none; color:var(--dim);
        border:1px solid transparent; border-bottom:none;
        border-radius:6px 6px 0 0; }
nav a.on { color:var(--ink); border-color:var(--line);
           background:var(--band); font-weight:600; }
section { padding:14px 0 40px; }
h2 { font-size:16px; margin:0 0 10px; }
.scroll { overflow-x:auto; }
table { border-collapse:collapse; width:100%; }
th, td { text-align:left; vertical-align:top; padding:6px 10px;
         border-bottom:1px solid var(--line); }
th { background:var(--band); font-weight:600; white-space:nowrap; }
td.id, td.path { font-family:ui-monospace, monospace; font-size:13px;
                 white-space:nowrap; }
a { color:var(--link); }
tr:target td { background:var(--mark); }
.PASS, .IMPLEMENTED-ok { color:var(--good); font-weight:600; }
.FAIL, .IMPLEMENTED-fail, .OPEN-fail { color:var(--bad); font-weight:600; }
.NONE, .IMPLEMENTED-untested, .OPEN-untested { color:var(--none); font-weight:600; }
ul { margin:0; padding:0; list-style:none; }
details { margin-left:18px; }
details.top { margin-left:0; }
summary { cursor:pointer; padding:3px 0; }
summary .path, .leaf .path { font-family:ui-monospace, monospace;
                             font-size:13px; }
.leaf { margin-left:36px; padding:2px 0; }
.count { color:var(--dim); font-size:13px; }
#tree-bar { display:flex; flex-wrap:wrap; gap:10px; align-items:center;
            margin:0 0 12px; }
#tree-bar[hidden] { display:none; }
#tree-bar button, #tree-bar input[type=search] {
    font:inherit; color:var(--ink); background:var(--band);
    border:1px solid var(--line); border-radius:6px; padding:4px 10px; }
#tree-bar label { white-space:nowrap; }
li { white-space:nowrap; }
pre { margin:0; white-space:pre-wrap; font:inherit; }
.dim { color:var(--dim); }
"""

_SCRIPT = """
(function () {
  var name = ["matrix", "tree", "features", "tests"];
  function show(which) {
    name.forEach(function (n) {
      document.getElementById(n).hidden = (n !== which);
      document.getElementById("tab-" + n).className =
          (n === which) ? "on" : "";
    });
  }
  function follow() {
    var id = location.hash.slice(1), which = "matrix";
    if (id.charAt(0) === "f" && id.charAt(1) === "-") which = "features";
    if (id === "tree") which = "tree";
    if (id.charAt(0) === "t" && id.charAt(1) === "-") which = "tests";
    if (name.indexOf(id) >= 0) which = id;
    show(which);
    var at = document.getElementById(id);
    if (at && name.indexOf(id) < 0) at.scrollIntoView({block: "center"});
  }
  window.addEventListener("hashchange", follow);
  follow();

  var bar = document.getElementById("tree-bar");
  var fold = document.querySelectorAll("#tree details");
  var leaf = document.querySelectorAll("#tree .leaf");
  function all(open) {
    fold.forEach(function (d) { if (!d.hidden) d.open = open; });
  }
  function sift() {
    var word = document.getElementById("tree-word").value.toLowerCase();
    var on = {};
    document.querySelectorAll(".tree-state").forEach(function (box) {
      on[box.value] = box.checked;
    });
    var shown = 0;
    leaf.forEach(function (l) {
      var keep = on[l.getAttribute("data-state")] &&
                 (!word || l.textContent.toLowerCase().indexOf(word) >= 0);
      l.hidden = !keep;
      if (keep) shown += 1;
    });
    fold.forEach(function (d) {
      d.hidden = !d.querySelector(".leaf:not([hidden])");
    });
    document.getElementById("tree-count").textContent =
        shown + " of " + leaf.length + " feature(s)";
    if (word) all(true);
  }
  bar.hidden = false;
  document.getElementById("tree-open").onclick = function () { all(true); };
  document.getElementById("tree-shut").onclick = function () { all(false); };
  document.getElementById("tree-word").oninput = sift;
  document.querySelectorAll(".tree-state").forEach(function (box) {
    box.onchange = sift;
  });
  sift();
})();
"""


_TREE_OPEN_MAX = 40                    # features shown unfolded at most


def _token(state):
    """RETURN: str, a state as a style class and a 'data-state' value: its
    words joined by '-' ('IMPLEMENTED ok' -> 'IMPLEMENTED-ok')."""
    return state.replace(" ", "-")


#  THE TREE'S CONTROLS: unfold, fold, show the features of chosen states,
#  and those whose line holds a word. They are script; without script
#  they stay hidden and the tree stands unfolded as written.
def _tree_bar():
    """RETURN: str, the tree's controls, a box per state."""
    return (
        '<div id="tree-bar" hidden>'
        '<button type="button" id="tree-open">Expand all</button>'
        '<button type="button" id="tree-shut">Collapse all</button>'
        + "".join('<label class="%s"><input type="checkbox" '
                  'class="tree-state" value="%s" checked> %s</label>'
                  % (_token(state), _token(state), state)
                  for state in STATE_TUPLE)
        + '<input type="search" id="tree-word" placeholder="filter features" '
          'aria-label="filter features">'
          '<span id="tree-count" class="count"></span></div>')


def _verdict_class(verdict):
    """RETURN: str, the style class of a verdict or a state."""
    if verdict in ("PASS", "FAIL"):  return verdict
    if verdict in STATE_TUPLE:       return _token(verdict)
    return "NONE"


def html_text(document):
    """
    RETURN: str, the feature document as ONE self-contained HTML page:
            four tabs -- Matrix, Tree, Features, Tests -- a feature's
            id leading to its row in 'Features', a test run to its
            test's row in 'Tests', a source of a feature's code to its
            coverage page. Without script every tab stands on the page,
            one below the other, and the links still land.
    """
    e = escape
    matrix, features, tests = [], [], []
    for row in document.feature_tuple:
        run_text = "".join(
            '<li><a href="#t-%i">%s</a> <span class="%s">%s</span></li>'
            % (index, e(text), _verdict_class(verdict), e(verdict))
            for text, verdict, index in row.run_tuple) \
            or '<li class="dim">no test run</li>'
        matrix.append(
            '<tr id="m-%i"><td class="id"><a href="#f-%i">%s</a></td>'
            '<td>%s</td><td class="%s">%s</td><td><ul>%s</ul></td></tr>'
            % (row.index, row.index, e(row.id_text),
               e(row.title or row.name), _token(row.state), e(row.state),
               run_text))
        code_text = ""
        if document.code_f:
            code_text = "<td><ul>%s</ul></td>" % "".join(
                '<li><a href="%s">%s</a></li>' % (e(link), e(text))
                if link else "<li>%s</li>" % e(text)
                for text, link in row.code_tuple)
        if document.document_f:
            code_text += "<td><ul>%s</ul></td>" % "".join(
                '<li><a href="%s">%s</a></li>' % (e(link), e(text))
                for text, link in row.document_tuple)
        features.append(
            '<tr id="f-%i"><td class="id"><a href="#m-%i">%s</a></td>'
            '<td>%s</td><td>%s</td><td><pre>%s</pre></td><td>%s</td>'
            '<td class="%s">%s</td><td class="id">%s</td><td>%s</td>%s</tr>'
            % (row.index, row.index, e(row.id_text), e(row.name),
               e(row.title), e(row.doc), e(row.component),
               _token(row.state), e(row.state), e(row.published),
               e(row.key_text),
               code_text))
    for row in document.test_tuple:
        run_text = "".join(
            '<li>%s <span class="%s">%s</span>%s</li>'
            % (e(choice), _verdict_class(verdict), e(verdict),
               ' <span class="NONE">%s</span>' % NONSENSE_WORD
               if nonsense_f else "")
            for choice, verdict, nonsense_f in row.run_tuple)
        feature_text = "".join(
            '<li><a href="#f-%i">%s</a></li>' % (index, e(text))
            for text, index in row.feature_tuple) + "".join(
            '<li class="NONE">\'%s\' not defined</li>' % e(name)
            for name in row.undefined_tuple)
        tests.append(
            '<tr id="t-%i"><td class="path">%s</td><td>%s</td>'
            '<td><pre>%s</pre></td><td><ul>%s</ul></td>'
            '<td><ul>%s</ul></td></tr>'
            % (row.index, e(row.path), e(row.title), e(row.doc),
               run_text, feature_text))

    #  THE TREE: a component and a TEST directory fold ('details'), a
    #  feature is a leaf. A row deeper than the one before opens under
    #  it; one less deep closes what stood between.
    #  A LARGE TREE OPENS FOLDED AT ITS TEST DIRECTORIES: the components
    #  are the map, and the features of one are a click away.
    tree, open_n = [], 0
    folded_f = len(document.feature_tuple) > _TREE_OPEN_MAX
    for row in document.tree_tuple:
        while open_n > row.depth:
            tree.append("</details>"); open_n -= 1
        if row.kind == "feature":
            tree.append(
                '<div class="leaf" data-state="%s"><a class="path" '
                'href="#f-%i">%s</a> %s <span class="%s">%s</span></div>'
                % (_token(row.state), row.feature_index, e(row.label),
                   e(row.detail), _token(row.state), e(row.state)))
            continue
        tree.append(
            '<details%s%s><summary><span class="path">%s%s</span>%s '
            '<span class="count">%s</span></summary>'
            % ("" if folded_f and row.kind == "features" else " open",
               ' class="top"' if row.depth == 0 else "",
               "" if row.kind == "component" else "FEATURES ",
               e(row.label), " %s" % e(row.detail) if row.detail else "",
               e(row.state)))
        open_n += 1
    tree += ["</details>"] * open_n

    def table(head_list, row_list):
        """RETURN: str, one table, scrolling sideways where it must."""
        return ('<div class="scroll"><table><thead><tr>%s</tr></thead>'
                '<tbody>\n%s\n</tbody></table></div>'
                % ("".join("<th>%s</th>" % head for head in head_list),
                   "\n".join(row_list)))

    count = ", ".join("%i %s" % (n, state.lower())
                      for state, n in document.count_tuple)
    return "\n".join([
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, '
        'initial-scale=1">',
        "<title>%s</title>" % e(document.title),
        "<style>%s</style></head><body>" % _STYLE,
        "<header><h1>%s</h1>" % e(document.title),
        '<p class="count">%i feature(s): %s &middot; %i test(s)</p>'
        % (len(document.feature_tuple), count, len(document.test_tuple)),
        '<nav><a id="tab-matrix" href="#matrix">Matrix</a>'
        '<a id="tab-tree" href="#tree">Tree</a>'
        '<a id="tab-features" href="#features">Features</a>'
        '<a id="tab-tests" href="#tests">Tests</a></nav></header><main>',
        '<section id="matrix"><h2>Matrix</h2>',
        table(("Feature", "Brief", "State", "Implemented by"), matrix),
        "</section>",
        '<section id="tree"><h2>Tree</h2>',
        _tree_bar(),
        "\n".join(tree),
        "</section>",
        '<section id="features"><h2>Features</h2>',
        table(("Feature", "Name", "Title", "Doc", "Aggregate",
               "State", "Internal id", "Keys")
              + (("Code only its runs reached",)
                           if document.code_f else ())
              + (("Documents",) if document.document_f else ()), features),
        "</section>",
        '<section id="tests"><h2>Tests</h2>',
        table(("Test", "Title", "Doc", "Test runs", "Features"), tests),
        "</section></main>",
        "<script>%s</script></body></html>" % _SCRIPT, ""])


# -- OpenDocument spreadsheet ----------------------------------------------

_ODS_MIME = "application/vnd.oasis.opendocument.spreadsheet"
_ODS_HEAD = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<office:document-content'
    ' xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"'
    ' xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"'
    ' xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"'
    ' xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"'
    ' xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:'
    'xsl-fo-compatible:1.0"'
    ' xmlns:xlink="http://www.w3.org/1999/xlink"'
    ' office:version="1.2">'
    '<office:automatic-styles>'
    '<style:style style:name="head" style:family="table-cell">'
    '<style:text-properties fo:font-weight="bold"/>'
    '<style:table-cell-properties fo:background-color="#e6e9ed"/>'
    '</style:style>'
    '<style:style style:name="wrap" style:family="table-cell">'
    '<style:table-cell-properties fo:wrap-option="wrap"'
    ' style:vertical-align="top"/></style:style>'
    '</office:automatic-styles>'
    '<office:body><office:spreadsheet>')
_ODS_TAIL = '</office:spreadsheet></office:body></office:document-content>\n'
_ODS_MANIFEST = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<manifest:manifest xmlns:manifest='
    '"urn:oasis:names:tc:opendocument:xmlns:manifest:1.0"'
    ' manifest:version="1.2">'
    '<manifest:file-entry manifest:full-path="/"'
    ' manifest:media-type="%s"/>'
    '<manifest:file-entry manifest:full-path="content.xml"'
    ' manifest:media-type="text/xml"/>'
    '</manifest:manifest>\n' % _ODS_MIME)
_ODS_STAMP = (2026, 1, 1, 0, 0, 0)     # one time stamp, whenever written


def _ods_cell(piece_list, style="wrap"):
    """RETURN: str, one cell holding one paragraph per piece; a piece is
    a str, or (text, target) for a link to '#<Sheet>.A<row>'."""
    if not piece_list:
        return '<table:table-cell table:style-name="%s"/>' % style
    def spaced(text):
        """RETURN: str, 'text' escaped, its leading blanks kept: a
        reader of the format drops blanks at a paragraph's beginning
        unless they are counted out."""
        bare = text.lstrip(" ")
        lead = len(text) - len(bare)
        return ('<text:s text:c="%i"/>' % lead if lead else "") \
               + escape(bare)

    paragraph_list = []
    for piece in piece_list:
        if isinstance(piece, tuple):
            text, target = piece
            bare = text.lstrip(" ")
            paragraph_list.append(
                '<text:p>%s<text:a xlink:type="simple" xlink:href="%s">%s'
                '</text:a></text:p>'
                % (spaced(text[:len(text) - len(bare)]), escape(target),
                   escape(bare)))
        else:
            for line in str(piece).split("\n"):
                paragraph_list.append("<text:p>%s</text:p>" % spaced(line))
    return ('<table:table-cell table:style-name="%s"'
            ' office:value-type="string">%s</table:table-cell>'
            % (style, "".join(paragraph_list)))


def _ods_table(name, head_list, row_list, depth_list=None):
    """RETURN: str, one sheet: the heads, then a row per cell list.
    'depth_list' gives each row a depth: the rows below a row, deeper
    than it, stand in a ROW GROUP -- the outline a spreadsheet folds
    and unfolds at its margin."""
    text = ['<table:table table:name="%s">' % escape(name),
            '<table:table-column table:number-columns-repeated="%i"/>'
            % len(head_list),
            "<table:table-row>%s</table:table-row>"
            % "".join(_ods_cell([head], "head") for head in head_list)]
    open_list = []                     # depths whose group stands open
    for i, cell_list in enumerate(row_list):
        depth = 0 if depth_list is None else depth_list[i]
        while open_list and open_list[-1] >= depth:
            text.append("</table:table-row-group>"); open_list.pop()
        text.append("<table:table-row>%s</table:table-row>"
                    % "".join(_ods_cell(cell) for cell in cell_list))
        if depth_list is not None and i + 1 < len(row_list) \
           and depth_list[i + 1] > depth:
            text.append("<table:table-row-group>"); open_list.append(depth)
    text.extend("</table:table-row-group>" for _ in open_list)
    text.append("</table:table>")
    return "".join(text)


def ods_bytes(document):
    """
    RETURN: bytes, the feature document as an OpenDocument spreadsheet
            ('.ods'): four sheets -- Matrix, Tree, Features, Tests -- a
            feature's id a link to its row in 'Features', a test run a
            link to its test's row in 'Tests', a source of a feature's
            code a link to its coverage page. The same document yields
            the same bytes.
    """
    def at(sheet, index):
        """RETURN: str, the link target of a row: '#<Sheet>.A<row>'."""
        return "#%s.A%i" % (sheet, index + 2)

    matrix = [[[(row.id_text, at("Features", row.index))],
               [row.title or row.name], [row.state],
               [("%s  %s" % (text, verdict), at("Tests", index))
                for text, verdict, index in row.run_tuple]
               or ["no test run"]]
              for row in document.feature_tuple]
    def outward(link):
        """RETURN: str, a link that leaves the spreadsheet. A relative
        reference in 'content.xml' is resolved from INSIDE the '.ods'
        archive, so the way to a file beside the document begins with
        '../'; a URL and an absolute path stand as they are."""
        if "://" in link or link.startswith("/"): return link
        return "../" + link

    features = [[[(row.id_text, at("Matrix", row.index))], [row.name],
                 [row.title], [row.doc] if row.doc else [],
                 [row.component] if row.component else [], [row.state],
                 [row.published] if row.published else [],
                 [row.key_text] if row.key_text else []]
                + ([[(text, outward(link)) if link else text
                     for text, link in row.code_tuple]]
                   if document.code_f else [])
                + ([[(text, outward(link))
                     for text, link in row.document_tuple]]
                   if document.document_f else [])
                for row in document.feature_tuple]
    tree = [[[("%s%s%s" % ("    " * row.depth,
                           "FEATURES " if row.kind == "features" else "",
                           row.label), at("Features", row.feature_index))
              if row.feature_index is not None
              else "%s%s%s" % ("    " * row.depth,
                               "FEATURES " if row.kind == "features" else "",
                               row.label)],
             [row.detail] if row.detail else [], [row.state]]
            for row in document.tree_tuple]
    tests = [[[row.path], [row.title], [row.doc] if row.doc else [],
              ["%s  %s%s" % (choice, verdict,
                             "  %s" % NONSENSE_WORD if nonsense_f else "")
               for choice, verdict, nonsense_f in row.run_tuple],
              [(text, at("Features", index))
               for text, index in row.feature_tuple]
              + ["'%s' not defined" % name
                 for name in row.undefined_tuple]]
             for row in document.test_tuple]
    content = "".join([
        _ODS_HEAD,
        _ods_table("Matrix", ("Feature", "Brief", "State",
                              "Implemented by"), matrix),
        _ods_table("Tree", ("Where", "What", "State"), tree,
                   [row.depth for row in document.tree_tuple]),
        _ods_table("Features", ("Feature", "Name", "Title", "Doc",
                                "Aggregate", "State",
                                "Internal id", "Keys")
                   + (("Code only its runs reached",)
                      if document.code_f else ())
                   + (("Documents",) if document.document_f else ()),
                   features),
        _ods_table("Tests", ("Test", "Title", "Doc", "Test runs",
                             "Features"), tests),
        _ODS_TAIL])
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        #  'mimetype' FIRST AND STORED: that is how a reader knows the
        #  archive for a spreadsheet without opening it.
        for name, text, method in (
                ("mimetype",              _ODS_MIME,     zipfile.ZIP_STORED),
                ("content.xml",           content,       zipfile.ZIP_DEFLATED),
                ("META-INF/manifest.xml", _ODS_MANIFEST, zipfile.ZIP_DEFLATED)):
            info = zipfile.ZipInfo(name, _ODS_STAMP)
            info.compress_type = method
            info.external_attr = 0o644 << 16
            archive.writestr(info, text.encode("utf-8"))
    return stream.getvalue()
