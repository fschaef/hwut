#! /usr/bin/env python3
#  @hwut {
#    title   = "hwut.report.features"
#    features = ["report-features-tree"]
#    choices {
#        code           { features = ["report-features-code"] }
#        document       { features = ["report-features-document", "report-features-document-tree", "report-features-document-coverage", "report-features-test-doc", "report-features-documents"] }
#        empty          { features = ["face-empty-said"] }
#        matrix         { features = ["report-features-matrix", "report-features-nonsense"] }
#        outside        { features = ["report-features-alone-complete"] }
#        refused        { features = ["face-refusal-by-name", "tree-boundary-refused"] }
#        test_directory { }
#        tree           { features = ["report-features-tree", "report-features-components", "report-features-outside", "report-features-nonsense", "report-features-documents"] }
#    }
#  }
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.report.features' -- the page of a tree: component, part,
         feature, test runs and their verdicts.

CHOICES: tree, test_directory, matrix, code, document, outside, empty,
         refused;

DESCRIPTION:

    tree            called at the root: every component with its id,
                    counts and statements, every feature with its state
                    and its linked runs, and the documents it names
                    ('see'); then what stands outside -- a document
                    that does not stand, 'documents' that is no list,
                    where 'parent' and 'childs' disagree with the
                    directories included.
    test_directory  called inside a TEST directory: that directory is
                    the whole page, addressed as '.'.
    matrix          '--matrix': a table per TEST directory that carries
                    a feature file -- test runs down, features across,
                    the verdict where a run links; the run without a
                    feature and the feature without a run marked. A
                    tree where no directory states features says so.
    code            '--code': under each feature the lines its runs
                    executed and no other run did, the lines it shares
                    as a count, the linked runs not measured. The
                    coverage output is a written one: five runs, one of
                    them reaching a file of the neighbour component and
                    one a file in its own TEST directory, which is left
                    out. Then: no output found, and a directory that is
                    none.
    document        '--html=<file>' and '--ods=<file>': the feature
                    document. The face says what it wrote; the page's
                    rows are shown tab by tab, tags as they stand -- a
                    feature's id leads to '#f-<n>', a test run to
                    '#t-<n>'; the spreadsheet's three sheets are shown
                    cell by cell with the targets of their links. A
                    test's 'doc', written in triple quotes, stands in
                    'Tests'. The 'Tree' tab holds the components, their
                    TEST directories and the features, folded. Written
                    twice, the bytes are the same. A file that cannot be
                    written is refused.
                    A feature's 'documents' stand in 'Features' as
                    links from where the document is written; the tree
                    carries its controls, the spreadsheet its row
                    groups.
                    WITH A COVERAGE OUTPUT ('--code') the 'Features' tab
                    gains the code only a feature's runs reached; with
                    '--cov-html=<dir>' each source is a link to its
                    coverage page, RELATIVE to where the document
                    stands -- '../' before it in the spreadsheet, whose
                    links are resolved inside the archive. '--cov-html'
                    without a document, and one that names no
                    directory, are refused.
    outside         a tree where nothing is linked and no statement
                    stands: no feature, every TEST directory named with
                    the count of its test runs. Then a feature file
                    ALONE: complete as it stands -- no id asked for, no
                    component named as undescribed (book work
                    2026-10-11, A-2, A-3); and the same file stating a
                    'parent', which brings the judgement of ids back.
    empty           a tree without a TEST directory: said as EMPTY,
                    status 3.
    refused         a directory that does not stand, a tree no root
                    bounds, and an unknown word.

NOTHING IS RUN. The fixture's verdicts are written by the bookkeeper,
so the page measures the reading of 'GOOD/book.csv' and nothing about
the machine.
______________________________________________________________________________
"""
import os
import re
import sys
import shutil
import tempfile
import zipfile
from   xml.dom import minidom

import config                                                       # noqa: F401

from   vut.engine.bookkeeper.api         import Bookkeeper
from   vut.engine.coverage.api           import gather, prepared
from   vut.engine.coverage.database.binary import pack_record
from   vut.engine.coverage.database.record import (CoverageRecord,
                                                   FileCoverage)
from   vut.services.lib.report           import features
from   vut.services.lib.face             import record_check
from   vut.test_writing_support.python.hwut_runner import HwutRunner


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def _write(root, path, text):
    """RETURN: None. Writes 'text' to 'root/path', directories made."""
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as handle:
        handle.write(text)


def _test(root, path, body):
    """RETURN: None. Writes a shell test at 'root/path' whose block
    holds the lines of 'body'."""
    _write(root, path, "#! /bin/sh\n# @hwut {\n%s\n# }\necho x\n"
           % "\n".join("#     " + line for line in body))
    os.chmod(os.path.join(root, path), 0o755)


def fixture(root):
    """RETURN: None. A tree of two components with statements, one
    without, and the verdicts of their runs."""
    _write(root, "hwut-root.conf", "hwut {\n}\n")
    _write(root, "hwut-composition.conf",
           'component {\n'
           '    id     = "all"\n'
           '    title  = "All"\n'
           '    childs { eng = "Runs and judges."  old = "Was here once." }\n'
           '}\n')
    _write(root, "engine/hwut-composition.conf",
           'component {\n'
           '    id     = "eng"\n'
           '    title  = "Engine"\n'
           '    does   = "Runs tests and judges them."\n'
           '    parent = "all"\n'
           '    childs { cmp = "Gives the verdict." }\n'
           '}\n')
    _write(root, "engine/compare/hwut-composition.conf",
           'component {\n'
           '    id     = "cmp"\n'
           '    title  = "Compare"\n'
           '    does   = "Decides whether an output is equivalent to its nominal."\n'
           '    parent { eng = "The engine\'s verdict rests on it." }\n'
           '    childs {\n'
           '        core      = "Aligns two streams line by line."\n'
           '        cmp-proof = "Proves the whole comparison on real pages."\n'
           '    }\n'
           '}\n')
    _write(root, "engine/compare/core/hwut-composition.conf",
           'component {\n'
           '    id     = "core"\n'
           '    title  = "Core"\n'
           '    does   = "Pairs lines."\n'
           '    parent { cmp = "Alignment is what compare shows." }\n'
           '    owner  = "nobody"\n'
           '}\n')
    _write(root, "engine/compare/core/TEST/hwut-features.conf",
           'features {\n'
           '    parent { core = "What \'core\' promises, proven." }\n'
           '    issued = 3\n'
           '    1 { name  = "line-pairing"\n'
           '        title = "Two streams are aligned line by line."\n'
           '        documents = ["../README.txt#pairing",\n'
           '                     "https://example.org/pairing",\n'
           '                     "../absent.txt"] }\n'
           '    2 { name  = "missing-side"\n'
           '        title = "A line present on one side only is shown whole." }\n'
           '    3 { name  = "untested"  documents = "README.txt" }\n'
           '    fresh { name = "not-numbered" }\n'
           '}\n')
    _write(root, "engine/compare/TEST/hwut-features.conf",
           'features {\n'
           '    id     = "cmp-proof"\n'
           '    parent = "cmp"\n'
           '    issued = 2\n'
           '    1 { name = "whole-page"  title = "A whole page is judged." }\n'
           '    2 { name = "never-run"   title = "Linked, and not in the book." }\n'
           '}\n')
    _write(root, "engine/compare/core/README.txt", "Pairing.\n")
    _test(root, "engine/compare/core/TEST/test-pair.sh",
          ['title    = "Pairing"', 'features = ["line-pairing"]',
           'choices {', '    plain { }',
           '    gap   { features = ["line-pairing", "missing-side"] }',
           '    odd   { features = [] }', '}'])
    _test(root, "engine/compare/core/TEST/test-stray.sh",
          ['title    = "Stray"', 'features = ["no-such"]'])
    _test(root, "engine/compare/TEST/test-pages.sh",
          ['title    = "Pages"',
           'doc      = """',
           '    Judges whole pages, a small one and a large one.',
           '',
           '      "large" holds a thousand lines.',
           '    """',
           'features = ["whole-page"]',
           'choices = ["small", "large"]'])
    _test(root, "engine/compare/TEST/test-fresh.sh",
          ['title    = "Fresh"', 'features = ["never-run"]'])
    _test(root, "engine/plain/TEST/test-plain.sh", ['title = "Plain"'])

    core = Bookkeeper(os.path.join(root, "engine/compare/core/TEST"))
    core.note_accept("test-pair.sh", "plain")
    core.note_accept("test-pair.sh", "gap", equivalent_f=False)
    page = Bookkeeper(os.path.join(root, "engine/compare/TEST"))
    page.note_accept("test-pages.sh", "small")
    page.note_accept("test-pages.sh", "large")


def _in_tree(build, function):
    """RETURN: None. Calls 'function()' with the cwd at the root of a
    fresh tree that 'build(root)' filled; removes the tree afterwards."""
    ground = tempfile.mkdtemp(prefix="hwut-features-")
    root   = os.path.join(ground, "tree")
    here   = os.getcwd()
    try:
        os.makedirs(root)
        build(root)
        os.chdir(root)
        function()
    finally:
        os.chdir(here)
        shutil.rmtree(ground, ignore_errors=True)


def _page(argv):
    """RETURN: None. Prints the face's page for 'argv', and its
    status."""
    status = features.main(argv, write=lambda text: print("    %s" % text))
    print("status: %s" % status.name)


def run_tree():
    """RETURN: None. The page of the whole tree, and its record."""
    def body():
        banner("hwut.report.features")
        _page([])
        banner("the same tree, as a record")
        result = features.do(features.Request("."))
        print("    counts: %s" % ", ".join("%s=%i" % pair
                                         for pair in result.count_tuple))
        print("    not plain: %s" % (record_check(result) or "nothing"))
        banner("--directory=engine/compare: paths from there")
        _page(["--directory=engine/compare"])
    _in_tree(fixture, body)


def run_test_directory():
    """RETURN: None. The page asked inside one TEST directory."""
    def body():
        os.chdir("engine/compare/core/TEST")
        banner("called inside engine/compare/core/TEST")
        _page([])
    _in_tree(fixture, body)


def run_matrix():
    """RETURN: None. The links as tables."""
    def body():
        banner("hwut.report.features --matrix")
        _page(["--matrix"])
        banner("--matrix inside engine/compare/core/TEST")
        os.chdir("engine/compare/core/TEST")
        _page(["--matrix"])
    _in_tree(fixture, body)
    def bare(root):
        _write(root, "hwut-root.conf", "hwut {\n}\n")
        _test(root, "a/TEST/test-a.sh", ['title = "A"'])
    def unstated():
        banner("--matrix where no TEST directory states features")
        _page(["--matrix"])
    _in_tree(bare, unstated)


#  WHAT EACH MEASURED RUN EXECUTED: (directory, test, choice,
#  {source as the run names it: covered ranges}). 'test-pages.sh large'
#  and 'test-fresh.sh' are linked and NOT measured.
CORE_TEST = "engine/compare/core/TEST"
PAGE_TEST = "engine/compare/TEST"
MEASURED  = (
    (CORE_TEST, "test-pair.sh",  "plain", {"../pair.c": ((1, 5),),
                                           "helper.c":  ((1, 4),)}),
    (CORE_TEST, "test-pair.sh",  "gap",   {"../pair.c": ((1, 5), (10, 14))}),
    (CORE_TEST, "test-pair.sh",  "odd",   {"../pair.c": ((1, 3), (20, 22))}),
    (CORE_TEST, "test-stray.sh", None,    {"../pair.c": ((1, 3),)}),
    (PAGE_TEST, "test-pages.sh", "small", {"../page.c":      ((1, 8),),
                                           "../core/pair.c": ((1, 3),)}),
)


def coverage_written(root, output_directory):
    """RETURN: None. Writes at 'output_directory' the coverage output of
    a run over 'root' that measured MEASURED."""
    record_directory = os.path.join(os.path.dirname(root), "records")
    os.makedirs(record_directory, exist_ok=True)
    run_list = []
    for number, (directory, test, choice, source_db) in enumerate(MEASURED):
        record = CoverageRecord(
            language="c", tool="gcov", source="gcov", counts_f=False,
            file_db={source: FileCoverage(source, ((1, 30),), covered,
                                          None, {})
                     for source, covered in source_db.items()})
        path = os.path.join(record_directory, "case-%i.rec" % number)
        with open(path, "wb") as handle: handle.write(pack_record(record))
        run_list.append((directory, test, choice, path))
    prepared(output_directory, root)
    gather(output_directory, run_list)


def run_code():
    """RETURN: None. The code each feature's runs went through."""
    def body():
        banner("--code, and no coverage output anywhere")
        _page(["--code", "--directory=engine/compare/core"])
        coverage_written(os.getcwd(), "hwut.coverage")
        banner("--code, 'hwut.coverage/' at the root")
        _page(["--code"])
        banner("--code inside engine/compare/core/TEST: the nearest output")
        here = os.getcwd()
        os.chdir(CORE_TEST)
        _page(["--code"])
        os.chdir(here)
        banner("--matrix --code: the table has no place for code")
        _page(["--matrix", "--code", "--directory=engine/compare/core"])
        banner("--cov-dir names a directory no coverage run made")
        os.makedirs("elsewhere")
        _page(["--cov-dir=elsewhere", "--directory=engine/compare/core"])
        banner("--cov-dir names the output")
        os.rename("hwut.coverage", "measured")
        _page(["--cov-dir=measured", "--directory=engine/compare/core"])
    _in_tree(fixture, body)


def _sheet_shown(content, name):
    """RETURN: None. Prints one sheet of a spreadsheet's 'content.xml':
    a row per line, cells between '|', a link as 'text -> target'."""
    for table in content.getElementsByTagName("table:table"):
        if table.getAttribute("table:name") != name: continue
        print("    [%s]" % name)
        for row in table.getElementsByTagName("table:table-row"):
            cell_list = []
            for cell in row.getElementsByTagName("table:table-cell"):
                piece_list = []
                for paragraph in cell.getElementsByTagName("text:p"):
                    text = "".join(node.data for node
                                   in _text_nodes(paragraph))
                    link = paragraph.getElementsByTagName("text:a")
                    if link:
                        text += " -> %s" % link[0].getAttribute("xlink:href")
                    piece_list.append(text)
                cell_list.append(" / ".join(piece_list))
            print("    %s" % " | ".join(cell_list))


def _text_nodes(node):
    """RETURN: list, every text node below 'node', document order."""
    found = []
    for child in node.childNodes:
        if child.nodeType == child.TEXT_NODE: found.append(child)
        else:                                 found += _text_nodes(child)
    return found


def _code_shown(html_name, ods_name):
    """RETURN: None. Prints the code and document cells of the page's
    'Features' tab -- heads and one line per feature that has any -- and, where
    'ods_name' is given, the same cells of the spreadsheet."""
    with open(html_name, encoding="utf-8") as handle:
        section = re.search(r'<section id="features">(.*?)</section>',
                            handle.read(), re.S).group(1)
    head_list = re.findall(r"<th>(.*?)</th>", section)[6:]
    print("    [features] %s" % " | ".join(head_list))
    for row in re.findall(r"<tr id=.*?</tr>", section, re.S):
        cell_list = re.findall(r"<td>(<ul>.*?</ul>)</td>", row,
                               re.S)[-len(head_list):]
        if any(cell != "<ul></ul>" for cell in cell_list):
            print("    %s  %s" % (re.search(r'id="(f-\d+)"', row).group(1),
                                  " | ".join(cell_list)))
    if ods_name is None: return
    with zipfile.ZipFile(ods_name) as archive:
        content = minidom.parseString(archive.read("content.xml"))
    for table in content.getElementsByTagName("table:table"):
        if table.getAttribute("table:name") != "Features": continue
        print("    [Features] links: %s" % ", ".join(
            link.getAttribute("xlink:href")
            for link in table.getElementsByTagName("text:a")
            if not link.getAttribute("xlink:href").startswith("#")))


def run_document():
    """RETURN: None. The feature document, as a page and as a
    spreadsheet."""
    def body():
        banner("--html=features.html --ods=features.ods")
        _page(["--html=features.html", "--ods=features.ods"])
        with open("features.html", encoding="utf-8") as handle:
            page = handle.read()
        banner("the page: tabs, and the rows of each")
        print("    %s" % re.search(r"<nav>.*?</nav>", page).group(0))
        print("    %s" % re.search(r'<p class="count">.*?</p>',
                                   page).group(0))
        section = re.search(r'<section id="tree">(.*?)</section>',
                            page, re.S).group(1)
        print("    [tree]")
        for line in section.split("\n")[1:]:
            if line.startswith('<div id="tree-bar"'):
                print("    controls: %s" % ", ".join(
                    re.findall(r'id="(tree-[a-z]+)"', line)
                    + re.findall(r'class="tree-state" value="(\w+)"', line)))
                continue
            if line: print("    %s" % line)
        for name in ("matrix", "features", "tests"):
            section = re.search(r'<section id="%s">(.*?)</section>' % name,
                                page, re.S).group(1)
            print("    [%s] %s" % (name, " | ".join(
                re.findall(r"<th>(.*?)</th>", section))))
            for row in re.findall(r"<tr id=.*?</tr>", section, re.S):
                print("    %s" % row.replace("\n", "\\n"))
        banner("the spreadsheet: three sheets, cell by cell")
        with zipfile.ZipFile("features.ods") as archive:
            print("    %s; mimetype: %s"
                  % (", ".join(archive.namelist()),
                     archive.read("mimetype").decode()))
            content = minidom.parseString(archive.read("content.xml"))
        for name in ("Matrix", "Tree", "Features", "Tests"):
            _sheet_shown(content, name)
        print("    row groups in 'Tree': %i"
              % len(content.getElementsByTagName("table:table-row-group")))
        banner("written twice: the same bytes")
        before = [open(name, "rb").read()
                  for name in ("features.html", "features.ods")]
        features.main(["--html=features.html", "--ods=features.ods"],
                      write=lambda text: None)
        after  = [open(name, "rb").read()
                  for name in ("features.html", "features.ods")]
        print("    page: %s   spreadsheet: %s"
              % tuple("same" if a == b else "DIFFERS"
                      for a, b in zip(before, after)))
        banner("--code: the 'Features' tab carries the code; no links")
        coverage_written(os.getcwd(), "hwut.coverage")
        _page(["--html=features.html", "--code"])
        _code_shown("features.html", None)
        banner("--cov-html=pages: each source a link, from where the "
               "document stands")
        os.makedirs("pages"); os.makedirs("out/deep")
        _page(["--html=out/deep/features.html", "--ods=features.ods",
               "--cov-html=pages"])
        _code_shown("out/deep/features.html", "features.ods")
        banner("--cov-html without a document; naming no directory")
        _page(["--cov-html=pages"])
        _page(["--html=features.html", "--cov-html=nowhere"])
        banner("inside a TEST directory; a file that cannot be written")
        os.chdir("engine/compare/TEST")
        _page(["--html=own.html"])
        _page(["--html=no/such/directory/x.html"])
        banner("'--html=' names no file")
        _page(["--html="])
    _in_tree(fixture, body)


def run_outside():
    """RETURN: None. A tree with tests and no statement at all."""
    def build(root):
        _write(root, "hwut-root.conf", "hwut {\n}\n")
        _test(root, "a/TEST/test-a.sh", ['title = "A"'])
        _test(root, "a/b/TEST/test-b.sh",
              ['title = "B"', 'features = ["wanted"]'])
    def body():
        banner("no feature file, no composition file")
        _page([])
    _in_tree(build, body)
    def alone(root):
        build(root)
        _write(root, "a/b/TEST/hwut-features.conf",
               'features {\n    1 { name = "wanted" }\n}\n')
    def complete():
        banner("a feature file alone: no id is asked for, no component "
               "named")
        _page([])
        banner("the same file stating a parent: the relation by ids is "
               "in use")
        _write(".", "a/b/TEST/hwut-features.conf",
               'features {\n    parent = "b"\n    1 { name = "wanted" }\n}\n')
        _page([])
    _in_tree(alone, complete)


def run_empty():
    """RETURN: None. A tree that holds no TEST directory."""
    def build(root):
        _write(root, "hwut-root.conf", "hwut {\n}\n")
        _write(root, "a/hwut-composition.conf",
               'component { title = "A" }\n')
    def body():
        banner("no TEST directory below")
        _page([])
    _in_tree(build, body)


def run_refused():
    """RETURN: None. What the face does not take."""
    def body():
        banner("a directory that does not stand")
        _page(["--directory=nowhere"])
        banner("an unknown word")
        _page(["--verbose"])
    _in_tree(fixture, body)
    def rootless(root):
        _test(root, "a/TEST/test-a.sh", ['title = "A"'])
    def unbounded():
        banner("a tree no 'hwut-root.conf' bounds")
        status = features.main([], write=lambda text: print(
            "    %s" % text.replace(os.getcwd(), "<tree>")))
        print("status: %s" % status.name)
    _in_tree(rootless, unbounded)


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "hwut.report.features",
        choice_map = {
            "tree":           run_tree,
            "test_directory": run_test_directory,
            "matrix":         run_matrix,
            "document":       run_document,
            "code":           run_code,
            "outside":        run_outside,
            "empty":          run_empty,
            "refused":        run_refused,
        },
    ).run()
