#! /usr/bin/env python3
#
# @hwut {
#     title      = "hwut.cov.conv.to_humans, to_lcov, to_html, hwut.cov.formats"
#     choices    = ["formats", "help", "html", "lcov", "refused", "to_humans"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE FACES BESIDE 'hwut.cov.run' (services E-133, coverage D-43,
         D-44): 'hwut.cov.conv.to_humans', 'hwut.cov.conv.to_lcov',
         'hwut.cov.conv.to_html' and 'hwut.cov.formats'; the run itself
         is 'test-cov_run.py'.

CHOICES: to_humans, lcov, html, formats, refused, help;

to_humans  a text record becomes binary and comes back byte-identical;
           the form is told by the file's first bytes, or stated; a
           record that reads in neither spelling is a FAULT, not an
           empty output.
lcov       an output directory of three runs over one source -- lines,
           branch arms, functions, toggle bits -- becomes one lcov
           tracefile: DA 1/0 over the union, BRDA per arm with '-'
           where the decision's line never ran, FN/FNDA, and the
           toggle bits dropped, exactly as the module says. Also what
           is refused: no marker, no directory.
html       the same output directory as pages: 'index.html' with one
           row per source and one column per measure, and the source's
           page with every line coloured, its points and the test runs
           that executed it -- read from the directory and shown whole.
formats    the table of tools and candidates is GENERATED from the
           registry -- this GOOD is the one place the table is written
           down (coverage RATIONALE D-13).
refused    an unknown option, a form that is not one, two files, an
           argument to 'formats': refused by name with the usage line.
help       the text of each face.
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from   vut.services.lib.cov.conv.to_humans import main as humans_main  # noqa E402
from   vut.services.lib.cov.conv.to_lcov   import main as lcov_main    # noqa E402
from   vut.services.lib.cov.conv.to_html   import main as html_main    # noqa E402
from   vut.services.lib.cov.formats        import main as formats_main # noqa E402
from   vut.engine.coverage.database.record import (CoverageRecord,     # noqa E402
                                                   FileCoverage)
from   vut.engine.coverage.database.binary import pack_record          # noqa E402
from   vut.engine.coverage.output          import gather, prepared     # noqa E402

RECORD_TEXT = ("##VUT-COVERAGE 4\n##run:      0.1,3\n##language: c\n"
               "##tool:     gcov\n##format:   gcov-annotated\n"
               "##counts:   no\nSF:parser/core.c\nEX:3+12,5+5\nCV:3+12\n"
               "BR:5*1/2\nSF:parser/table.c\nEX:\nCV:\n")

FACE_DB = {"to_humans": ("hwut.cov.conv.to_humans", humans_main, True),
           "to_lcov":   ("hwut.cov.conv.to_lcov",   lcov_main,   True),
           "to_html":   ("hwut.cov.conv.to_html",   html_main,   False),
           "formats":   ("hwut.cov.formats",        formats_main, False)}


def call(face, argument_list, directory):
    """
    RETURN: bytes, what the face wrote to stdout's buffer. Shows the
            command line, the lines the face writes, and the exit
            status; a path under the temporary directory is shown as
            '<dir>'.
    """
    name, main, bytes_f = FACE_DB[face]
    shown = [a.replace(directory or "\0", "<dir>") for a in argument_list]
    print("$ %s %s" % (name, " ".join(shown)) if shown else "$ %s" % name)
    line_list, chunk_list = [], []
    if bytes_f: status = main(argument_list, line_list.append, chunk_list.append)
    else:       status = main(argument_list, line_list.append)
    for line in line_list:
        for piece in str(line).replace(directory or "\0", "<dir>") \
                              .split("\n"):
            print("    %s" % piece if piece else "")
    data = b"".join(chunk_list)
    if data:
        #  LINES, not bytes: a tracefile carries the fixture's path,
        #  whose length is the machine's (O-30).
        print("    [%i line(s) written to stdout]" % data.count(b"\n"))
    print("    [status %d]" % status)
    return data


def check(pair_list):
    """RETURN: True, every claim held; False, at least one did not."""
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def verdict(ok, sentence):
    """RETURN: None. The one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


def test_to_humans():
    """Text to binary and back."""
    directory = tempfile.mkdtemp(prefix="vut_cov_")
    text_path = os.path.join(directory, "r.cover.txt")
    bin_path  = os.path.join(directory, "r.cover")
    with open(text_path, "w", encoding="utf-8") as fh: fh.write(RECORD_TEXT)

    binary = call("to_humans", [text_path], directory)
    with open(bin_path, "wb") as fh: fh.write(binary)
    back   = call("to_humans", [bin_path], directory)
    print("    the text that came back {")
    for line in back.decode().splitlines(): print("      %s" % line)
    print("    }")
    stated = call("to_humans", ["--from", "text", "--to", "text", text_path],
                  directory)
    with open(os.path.join(directory, "x"), "wb") as fh: fh.write(b"???")
    call("to_humans", [os.path.join(directory, "x")], directory)
    call("to_humans", [os.path.join(directory, "missing")], directory)

    ok = check([
        (binary[:1] == b"\x78", "the binary form is a zlib stream"),
        (back.decode() == RECORD_TEXT,
         "binary -> text is byte-identical to the text that went in"),
        (stated.decode() == RECORD_TEXT,
         "text -> text, stated, is the identity"),
    ])
    shutil.rmtree(directory)
    verdict(ok, "one record, two spellings; the face converts on demand.")


#  Three runs over 'src/a.c' (lines 1..9 executable). Decisions at line
#  3 (two arms) and 8 (two arms); line 8 is never executed by anyone,
#  so its arms read '-'. Two functions, one toggle bit.
LCOV_RUN_LIST = (
    ("t0", ((1, 5),), ((3, 1, 2), (8, 0, 2)),
     ((1, "main", 1, 1), (6, "f", 0, 1))),
    ("t1", ((1, 3),), ((3, 2, 2), (8, 0, 2)),
     ((1, "main", 1, 1), (6, "f", 0, 1))),
    ("t2", ((5, 6),), ((3, 0, 2), (8, 0, 2)),
     ((1, "main", 0, 1), (6, "f", 1, 1))),
)


def lcov_fixture():
    """RETURN: (root, output directory), an output directory gathered
    from the three runs above."""
    root = tempfile.mkdtemp(prefix="vut_cov_lcov_")
    item_list = []
    for number, (test, covered, branch, function) in enumerate(LCOV_RUN_LIST):
        record = CoverageRecord(
            language="c", tool="gcov", source="gcov", counts_f=False,
            file_db={"src/a.c": FileCoverage(
                "src/a.c", ((1, 10),), covered, None,
                {"branch": branch, "function": function,
                 "toggle": ((2, "clk", 1, 1),)})})
        path = os.path.join(root, "case-%i.rec" % number)
        with open(path, "wb") as fh: fh.write(pack_record(record))
        item_list.append((".", test, None, path))
    out = os.path.join(root, "out")
    prepared(out, root)
    gather(out, item_list)
    return root, out


def test_lcov():
    """An output directory as one lcov tracefile."""
    root, out = lcov_fixture()
    data = call("to_lcov", [out], root)
    print("    the tracefile {")
    for line in data.decode().splitlines():
        print("      %s" % line.replace(root, "<dir>"))
    print("    }")
    target = os.path.join(root, "cov.info")
    call("to_lcov", [out, "-o", target], root)
    written = open(target, "rb").read()
    plain = os.path.join(root, "plain")
    os.makedirs(plain)
    call("to_lcov", [plain], root)
    call("to_lcov", [os.path.join(root, "nowhere")], root)
    here = os.getcwd()
    try:
        os.chdir(root)
        call("to_lcov", [], root)
    finally:
        os.chdir(here)
    shutil.rmtree(root)

    text = data.decode()
    line_set = set(text.splitlines())
    ok = check([
        (written == data, "'-o FILE' writes what stdout would carry"),
        ("DA:4,1" in line_set and "DA:6,0" in line_set,
         "a line any run executed is 1, one no run did is 0"),
        ("LF:9" in line_set and "LH:5" in line_set,
         "LF counts the executable lines, LH the covered"),
        ("BRDA:3,0,0,1" in line_set and "BRDA:3,0,1,1" in line_set,
         "both arms of line 3 were taken, by different runs"),
        ("BRDA:8,0,0,-" in line_set and "BRDA:8,0,1,-" in line_set,
         "the arms of a line never executed read '-'"),
        ("BRF:4" in line_set and "BRH:2" in line_set,
         "BRF counts the arms, BRH the taken"),
        ("FNDA:1,main" in line_set and "FNDA:1,f" in line_set
         and "FNH:2" in line_set,
         "each function was entered by some run"),
        ("clk" not in text, "the toggle bit has no lcov line"),
    ])
    verdict(ok, "lcov for the tools that read lcov; the directory keeps "
                "what lcov cannot say.")


A_C = ("int main(void) {\n    int x = 1;\n    if (x) {\n        x = 2;\n"
       "        f();\n    } else {\n        x = 3;\n        if (x) f();\n"
       "    }\n    return 0;\n}\n")


def test_html():
    """An output directory as pages."""
    root, out = lcov_fixture()
    os.makedirs(os.path.join(root, "src"))
    with open(os.path.join(root, "src", "a.c"), "w") as fh: fh.write(A_C)
    call("to_html", [out], root)
    html_dir = os.path.join(out, "html")
    for name in ("index.html", os.path.join("src", "a.c.html")):
        print("    %s {" % name.replace(os.sep, "/"))
        with open(os.path.join(html_dir, name), encoding="utf-8") as fh:
            for line in fh.read().splitlines():
                print("      %s" % line.replace(root, "<dir>"))
        print("    }")
    #  A SOURCE THE ROOT NO LONGER HOLDS: the page stands, says so.
    os.remove(os.path.join(root, "src", "a.c"))
    elsewhere = os.path.join(root, "pages")
    call("to_html", [out, "-o", elsewhere], root)
    with open(os.path.join(elsewhere, "src", "a.c.html"), encoding="utf-8") as fh:
        gone = fh.read()
    with open(os.path.join(html_dir, "src", "a.c.html"), encoding="utf-8") as fh:
        page = fh.read()
    with open(os.path.join(html_dir, "index.html"), encoding="utf-8") as fh:
        index = fh.read()
    shutil.rmtree(root)
    ok = check([
        ("5/9" in index and "55.6%" in index,
         "the index says 5 of 9 lines, 55.6%"),
        ("branch arms" in index and "2/4" in index,
         "and 2 of 4 branch arms"),
        ("<td class=\"ln\">1</td><td class=\"txt\">int main(void) {</td>"
         "<td class=\"pts\">FN main</td><td class=\"runs\">t0, t1</td>" in page,
         "line 1 was run by t0 and t1, and holds the function point"),
        ("<tr class=\"cov\"><td class=\"ln\">3</td><td class=\"txt\">    if (x) {"
         "</td><td class=\"pts\">BR 2/2</td><td class=\"runs\">t0</td>" in page,
         "line 3 names the runs that executed it (t0) and the arms taken "
         "over EVERY run (2/2: the fixture's t1 reports the arm alone)"),
        ("<tr class=\"unc\"><td class=\"ln\">8</td>" in page
         and "BR 0/2" in page,
         "line 8 is uncovered with its two arms untaken"),
        ("<tr class=\"non\"><td class=\"ln\">10</td>" in page,
         "a line that is not executable is neither"),
        ("was not found" in gone and "<td class=\"ln\">8</td>" in gone,
         "a missing source keeps its lines and says the text is gone"),
    ])
    verdict(ok, "pages for people: the lines, the points, and who ran "
                "them.")


def test_formats():
    """The generated table."""
    call("formats", [], "")
    verdict(True, "the table has one author, the registry, and this is "
                  "its printout.")


def test_refused():
    """Refused by name."""
    directory = tempfile.mkdtemp(prefix="vut_cov_")
    p = os.path.join(directory, "a")
    with open(p, "w") as fh: fh.write(RECORD_TEXT)
    for face, argument_list in (("to_humans", ["--to", "yaml", p]),
                                ("to_humans", ["--bogus", p]),
                                ("to_humans", [p, p]),
                                ("to_humans", []),
                                ("to_lcov",   ["--sideways"]),
                                ("to_lcov",   [p, p]),
                                ("to_lcov",   ["-o"]),
                                ("to_html",   ["--sideways"]),
                                ("to_html",   [p, p]),
                                ("to_html",   [os.path.join(directory, "none")]),
                                ("formats",   ["extra"])):
        call(face, argument_list, directory)
    shutil.rmtree(directory)
    verdict(True, "each door refuses by name, with its usage line.")


def test_help():
    """The help text of each face."""
    for face in ("to_humans", "to_lcov", "to_html", "formats"):
        call(face, ["--help"], "")
    verdict(True, "help on request.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "hwut.cov.conv.to_humans, to_lcov, to_html, hwut.cov.formats",
        choice_map = {
            "to_humans": test_to_humans,
            "lcov":      test_lcov,
            "html":      test_html,
            "formats":   test_formats,
            "refused":   test_refused,
            "help":      test_help,
        },
        happy      = "SUCCESS.*",
    ).run()
