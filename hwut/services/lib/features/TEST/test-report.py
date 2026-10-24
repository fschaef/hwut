#! /usr/bin/env python3
#
# @hwut {
#     title      = "hwut.report.features where the central file stands: aggregates, leaves, runs, states"
#     choices {
#         tree    { features = ["report-reads-registry"] }
#         below   { features = ["report-reads-registry"] }
#         matrix  { features = ["report-reads-registry"] }
#         outside { features = ["report-reads-registry"] }
#         document { features = ["document-reads-registry"] }
#     }
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'hwut.report.features' WHERE 'hwut-root-features.conf' STANDS
         (spec 23 VERSION 10 sections 5, 6; R-96): the tree of the central
         file -- aggregates, leaves with their state on two axes, the runs
         that prove them -- the unplaced leaves, the retired claims, and what
         stands outside. A scratch tree outside every other, run and accepted
         by the launchers; then one run changed so that it fails.

CHOICES: tree, below, matrix, outside;

tree     at the top: every aggregate with its counts, an empty aggregate
         OPEN, each leaf IMPLEMENTED ok / IMPLEMENTED fail / OPEN with its
         internal id and effective keys (its own, its TEST file's, the
         aggregates'), its runs; UNPLACED; RETIRED.

below    asked in a directory below: only its leaves, under the aggregates
         that hold them; the retired of that directory only.

matrix   the tables per TEST directory, each column named with its leaf's
         state, 'not registered' where it has no line.

document '--html' and '--ods': the rows that carry content -- the count
         line, the state boxes of the tree, the Matrix, Features and Tree
         rows of the page; each sheet's heads and first column of the
         spreadsheet. A leaf's id is its external id, its internal id stands
         where the published id stood, its tree path where the component.

outside  a link to a name not defined, a run linking nothing, a feature
         defined and not registered, a directory moved: named below the
         tree.
______________________________________________________________________________
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

HERE = os.path.dirname(os.path.abspath(__file__))
BIN  = os.path.normpath(os.path.join(HERE, "../../../../bin"))

ROUTER = """features {
  keys = ["routing"]
  childs {
    forward    { title = "A frame is forwarded."  keys = ["latency"] }
    keep-order { title = "Frames keep their order." }
    drop       { title = "A frame without route is dropped." }
  }
}
"""

CAN = """features {
  childs {
    decode { title = "A frame is decoded." }
  }
}
"""

CENTRAL = """features {
    directory_map {
        "Aaaaaaa1" = "gw/can"
        "Bbbbbbb2" = "gw/router"
    }
    tree {
        gateway {
            title = "CAN-MOST gateway"
            keys  = ["product"]
            childs {
                forwarding {
                    title = "Frames reach their destination."
                    childs {
                        "router.forward"    = "Bbbbbbb2:forward"
                        "router.keep-order" = "Bbbbbbb2:keep-order"
                    }
                }
                buses {
                    title = "Both buses are served."
                    childs { "can.decode" = "Aaaaaaa1:decode" }
                }
                later { title = "Nothing below yet." }
            }
        }
        "router.drop" = "Bbbbbbb2:drop"
    }
    retired {
        "can.old"    { id = "Aaaaaaa1:old"  title = "Gone." }
        "router.old" { id = "Bbbbbbb2:old"  title = "Gone too." }
    }
}
"""


def banner(label):
    """RETURN: None. Section heading."""
    print("--- %s " % label + "-" * (60 - len(label)))


def _write(root, path, text, mode=None):
    """RETURN: None. Writes 'text' to 'root/path', directories made."""
    full = os.path.join(root, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as fh:
        fh.write(text)
    if mode is not None: os.chmod(full, mode)


def _test(root, path, title, block, said):
    """RETURN: None. A shell test at 'root/path' with the block lines
    'block', printing 'said'."""
    _write(root, path, "#! /bin/bash\n# @hwut {\n#     title = \"%s\"\n%s# }\n"
           "echo \"%s $1\"\necho \"<hwut-end>\"\n"
           % (title, "".join("#     %s\n" % line for line in block), said),
           0o755)


def _launch(root, *argv, cwd=None):
    """RETURN: str, what the launcher 'argv[0]' wrote, stdout then stderr,
    the scratch root written '<root>'."""
    done = subprocess.run([os.path.join(BIN, argv[0])] + list(argv[1:]),
                          cwd=cwd or root, capture_output=True, text=True,
                          env=dict(os.environ, PYTHONPATH=""),
                          stdin=subprocess.DEVNULL)
    text = done.stdout + done.stderr
    return text.replace(root, "<root>").replace(os.path.realpath(root),
                                                "<root>"), done.returncode


def _tree():
    """RETURN: str, a scratch tree, its runs accepted; then 'test-frame.sh'
    changed, so its next run fails."""
    root = tempfile.mkdtemp(prefix="hwut-features-", dir="/tmp")
    _write(root, "hwut-root.conf",
           'hwut {\n    language-setup { bash { extensions = [".sh"] '
           'interpreter = "bash" } }\n}\n')
    _write(root, "gw/router/TEST/hwut-features.conf", ROUTER)
    _write(root, "gw/can/TEST/hwut-features.conf", CAN)
    _test(root, "gw/router/TEST/test-route.sh", "route",
          ['features = ["forward"]',
           'choices { single { }  burst { features = ["forward", '
           '"keep-order"] } }'], "routed")
    _test(root, "gw/router/TEST/test-restart.sh", "restart", [], "restarted")
    _test(root, "gw/can/TEST/test-frame.sh", "frame",
          ['features = ["decode"]'], "decoded")
    _launch(root, "hwut.run", "--silent")
    #  THE RECORDINGS ARE PLAY'S (services E-165), directory by directory.
    for where in ("gw/router/TEST", "gw/can/TEST"):
        _launch(root, "hwut.play", "--all", "--plain",
                cwd=os.path.join(root, where))
    _launch(root, "hwut.accept", "--force")
    _test(root, "gw/can/TEST/test-frame.sh", "frame",
          ['features = ["decode"]'], "changed")
    _launch(root, "hwut.run", "--silent")
    _write(root, "hwut-root-features.conf", CENTRAL)
    return root


def _show(root, label, *argv, cwd=None):
    """RETURN: None. Prints what 'hwut.report.features <argv>' wrote, and
    its exit status. Timings and dates do not occur on the page."""
    text, code = _launch(root, "hwut.report.features", *argv, cwd=cwd)
    print(">>> %s" % label)
    for line in text.rstrip("\n").split("\n"):
        print("    " + re.sub(r"\s+$", "", line))
    print("    exit %d" % code)


def test_tree():
    """RETURN: None. Prints the page at the top."""
    root = _tree()
    try:
        _show(root, "hwut.report.features")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_below():
    """RETURN: None. Prints the page asked below the top."""
    root = _tree()
    try:
        _show(root, "in gw/can", cwd=os.path.join(root, "gw/can"))
        _show(root, "--directory=gw/router", "--directory=gw/router")
        _show(root, "in gw/router/TEST",
              cwd=os.path.join(root, "gw/router/TEST"))
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_matrix():
    """RETURN: None. Prints the tables."""
    root = _tree()
    try:
        _show(root, "--matrix", "--matrix")
        _write(root, "gw/can/TEST/hwut-features.conf",
               CAN.replace("  }\n}", "    encode { title = \"A frame is encoded.\" }\n  }\n}"))
        _show(root, "--matrix, a feature not registered", "--matrix",
              "--directory=gw/can")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_outside():
    """RETURN: None. Prints what stands outside."""
    root = _tree()
    try:
        _test(root, "gw/can/TEST/test-frame.sh", "frame",
              ['features = ["decode", "nothing"]'], "changed")
        _write(root, "gw/can/TEST/hwut-features.conf",
               CAN.replace("  }\n}", "    encode { title = \"A frame is encoded.\" }\n  }\n}"))
        os.makedirs(os.path.join(root, "other"))
        os.rename(os.path.join(root, "gw/router"),
                  os.path.join(root, "other/router"))
        _show(root, "an undefined name, a feature not registered, a "
              "directory moved")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_document():
    """RETURN: None. Prints what the feature document holds."""
    import html as html_module
    import zipfile
    root = _tree()
    try:
        text, code = _launch(root, "hwut.report.features",
                             "--html=features.html", "--ods=features.ods")
        print(">>> --html=features.html --ods=features.ods")
        for line in text.rstrip("\n").split("\n"):
            print("    " + line)
        print("    exit %d" % code)
        with open(os.path.join(root, "features.html")) as fh:
            page = fh.read()
        banner("the page")
        for line in page.split("\n"):
            if re.search(r'class="count"|tree-state|id="[mf]-\d|class="leaf"'
                         r'|<summary>|<details|IMPLEMENTED-ok \{', line):
                plain = html_module.unescape(re.sub(r"<[^>]+>", " | ", line))
                print("    " + re.sub(r"(\s*\|\s*)+", " | ", plain)
                      .strip(" |"))
        banner("the spreadsheet")
        with zipfile.ZipFile(os.path.join(root, "features.ods")) as archive:
            content = archive.read("content.xml").decode("utf-8")
        for sheet in re.findall(r'<table:table table:name="[^"]+">.*?'
                                r'</table:table>', content):
            name = re.search(r'table:name="([^"]+)"', sheet).group(1)
            row_list = re.findall(r"<table:table-row>(.*?)</table:table-row>",
                                  sheet)
            head = [html_module.unescape(re.sub(r"<[^>]+>", "", cell))
                    for cell in re.findall(r"<table:table-cell[^>]*>(.*?)"
                                           r"</table:table-cell>",
                                           row_list[0])]
            print("    %s: %s" % (name, " | ".join(head)))
            for row in row_list[1:]:
                cell = re.search(r"<table:table-cell[^>]*?(?:/>|>(.*?)"
                                 r"</table:table-cell>)", row)
                first = html_module.unescape(re.sub(r"<[^>]+>", "",
                                                    cell.group(1) or ""))
                print("        %s" % first.rstrip())
    finally:
        shutil.rmtree(root, ignore_errors=True)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "hwut.report.features where the central file stands: "
                     "aggregates, leaves, runs, states",
        choice_map = {
            "tree":    test_tree,
            "below":   test_below,
            "matrix":  test_matrix,
            "outside": test_outside,
            "document": test_document,
        },
    ).run()
