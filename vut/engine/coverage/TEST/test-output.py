#! /usr/bin/env python3
#
# @hwut {
#     title      = "The output directory carries every measure"
#     choices    = ["carry", "refused", "rebased"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE OUTPUT DIRECTORY CARRIES EVERY MEASURE (coverage D-42, D-43):
         what each test run reported beside the lines -- branch arms,
         toggle bits, functions -- is gathered with the lines and comes
         back out, per run, as it went in.

CHOICES: carry, rebased, refused;

carry    three per-case records of ONE source, each with branch, toggle
         and function points, are gathered. The page is the coverage
         file in its text spelling: the universes once, and every item
         under the ONE reference (a run, or a group of runs) that took it.
         Then each run's measures are read back from the directory and
         compared with what the run reported.
rebased  a record written in a test directory ('x/TEST') names its
         source relative to it ('../../src/a.c'); gathered, the source
         stands under the run's root and its measures come with it.
refused  what cannot be gathered, by name: two runs that disagree on the
         number of arms of one decision, and a named point that counts
         items it does not name.
______________________________________________________________________________
"""
import os
import shutil
import sys
import tempfile

import config                                                   # noqa: F401

from vut.test_writing_support.python.hwut_runner import HwutRunner
from vut.engine.coverage.database.record import (CoverageRecord,
                                                 FileCoverage)
from vut.engine.coverage.database.binary import pack_record
from vut.engine.coverage.database.gathered import format_gathered
from vut.engine.coverage.output import (Output, OutputRefused, gather,
                                        prepared, coverage_path)
from vut.engine.coverage.database.gathered import unpack_gathered

SOURCE = "src/a.c"


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


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


#  What each run reported for SOURCE. The decision on line 3 has two
#  arms, the one after it three; line 8 has two.
RUN_LIST = (
    ("t0", dict(covered=((1, 5),),
                branch=((3, 1, 2), (3, 3, 3), (8, 0, 2)),
                toggle=((2, "clk", 1, 1), (2, "rst", 0, 1)),
                function=((1, "main", 1, 1), (6, "f", 0, 1)))),
    ("t1", dict(covered=((1, 3),),
                branch=((3, 2, 2), (3, 3, 3), (8, 1, 2)),
                toggle=((2, "clk", 1, 1), (2, "rst", 1, 1)),
                function=((1, "main", 1, 1), (6, "f", 1, 1)))),
    ("t2", dict(covered=((8, 9),),
                branch=((3, 0, 2), (3, 4, 3), (8, 1, 2)),
                toggle=((2, "clk", 0, 1), (2, "rst", 0, 1)),
                function=((1, "main", 0, 1), (6, "f", 0, 1)))),
)


def fixture(run_list, directory=".", source=SOURCE):
    """
    RETURN: [0] str, a fresh directory
            [1] list of (directory, test, choice, record path), what
                'gather' is handed

    The runs left their records in 'directory' naming 'source' relative
    to it.
    """
    root = tempfile.mkdtemp(prefix="vut_output_")
    item_list = []
    for number, (test, shape) in enumerate(run_list):
        measure_db = {name: shape[name]
                      for name in ("branch", "toggle", "function")
                      if name in shape}
        record = CoverageRecord(
            language="c", tool="gcov", source="gcov", counts_f=False,
            file_db={source: FileCoverage(source, ((1, 10),),
                                          shape["covered"], None,
                                          measure_db)})
        path = os.path.join(root, "case-%i.rec" % number)
        with open(path, "wb") as handle: handle.write(pack_record(record))
        item_list.append((directory, test, None, path))
    return root, item_list


def test_carry():
    """RETURN: None. Gather, show the file, read every run back."""
    banner("the coverage file of one source, three runs")
    root, item_list = fixture(RUN_LIST)
    out = os.path.join(root, "out")
    prepared(out, root)
    gather(out, item_list)
    with open(coverage_path(out, SOURCE), "rb") as handle:
        sys.stdout.write(format_gathered(unpack_gathered(handle.read())))

    banner("what each run took, read back from the directory")
    output = Output(out)
    result_list = []
    for test, shape in RUN_LIST:
        found = dict(output.measures_of_run(".", test, None))
        back  = found[SOURCE]
        same  = all(back[name] == shape[name]
                    for name in ("branch", "toggle", "function"))
        print("         %-3s branch %s" % (test, back["branch"]))
        result_list.append((same, "%s gets back exactly what it reported"
                                  % test))
    result_list.append((output.measures_of_run(".", "nobody", None) is None,
                        "a run the output does not name has no measures"))
    shutil.rmtree(root)
    ok = check(result_list)
    verdict(ok, "nothing a run reported beside the lines is lost.")


def test_rebased():
    """RETURN: None. Records of a test directory, gathered at the root."""
    banner("a record of x/TEST naming ../../src/a.c")
    root, item_list = fixture(RUN_LIST, "x/TEST", "../../" + SOURCE)
    out = os.path.join(root, "out")
    prepared(out, root)
    gather(out, item_list)
    output = Output(out)
    found  = dict(output.measures_of_run("x/TEST", "t1", None) or ())
    print("         sources: %s" % sorted(found))
    shutil.rmtree(root)
    ok = check([
        (list(found) == [SOURCE], "the source stands under the root"),
        (found.get(SOURCE, {}).get("branch") == RUN_LIST[1][1]["branch"],
         "and carries what the run took"),
    ])
    verdict(ok, "a measure follows its source to the root.")


def test_refused():
    """RETURN: None. What cannot be gathered, by name."""
    banner("a decision of two sizes")
    clash = (("a", dict(covered=((1, 2),), branch=((3, 1, 2),))),
             ("b", dict(covered=((1, 2),), branch=((3, 1, 3),))))
    count = (("a", dict(covered=((1, 2),),
                        toggle=((2, "bus", 3, 4),))),)
    result_list = []
    for label, run_list in (("two sizes", clash), ("a count", count)):
        root, item_list = fixture(run_list)
        out = os.path.join(root, "out")
        prepared(out, root)
        try:
            gather(out, item_list)
            name, text = "nothing", ""
        except OutputRefused as fault:
            name, text = "OutputRefused", str(fault)
        print("         %-9s -> %s: %s" % (label, name, text))
        result_list.append((name == "OutputRefused", "refused: %s" % label))
        shutil.rmtree(root)
    ok = check(result_list)
    verdict(ok, "a measure that cannot name its items is not gathered.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The output directory carries every measure",
        choice_map = {
            "carry":   test_carry,
            "rebased": test_rebased,
            "refused": test_refused,
        },
        happy      = "SUCCESS.*",
    ).run()
