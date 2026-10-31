#! /usr/bin/env python3
#
# @hwut {
#     title      = "space_iterator: every combination of a parameter basis"
#     choices {
#         product { features = ["space-product"] }
#         edges   { features = ["space-edges"] }
#     }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Pin 'space_iterator.do': the cartesian product of a basis, the
         RIGHTMOST dimension changing fastest, and its two edges.

CHOICES: product, edges;

    product   three dimensions of mixed values, every point in order; the
              count is the product of the dimensions' lengths.
    edges     an empty basis yields ONE point, the empty one; a basis with an
              empty dimension yields nothing; a single dimension yields its
              values one by one.

The Perl port ('perl/TEST/test-space-iterator.pl') prints the same, and is
held against these GOOD files by '.link'.
______________________________________________________________________________
"""
import sys
import config                                                       # noqa: F401

from hwut.test_writing_support.python.hwut_runner import HwutRunner
from hwut.test_writing_support.python             import space_iterator


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def points(basis):
    """RETURN: None. Every point of 'basis', one per line, then the count."""
    n = 0
    for point in space_iterator.do(basis):
        print("  (%s)" % ", ".join(str(value) for value in point))
        n += 1
    print("  %d point(s)" % n)


def run_product():
    """RETURN: None. Three dimensions; the rightmost changes fastest."""
    banner("[0, 2, 4] x [otto, heinz] x [1, 2] -- 3 * 2 * 2 points")
    points([[0, 2, 4], ["otto", "heinz"], [1, 2]])


def run_edges():
    """RETURN: None. The empty basis, an empty dimension, one dimension."""
    banner("an EMPTY basis -- one point, the empty one")
    points([])
    banner("a basis with an EMPTY dimension -- nothing")
    points([[1, 2], [], [3]])
    banner("ONE dimension -- its values one by one")
    points([["a", "b", "c"]])


HwutRunner(
    argv       = sys.argv,
    title      = "space_iterator: every combination of a parameter basis",
    choice_map = {
        "product": run_product,
        "edges":   run_edges,
    },
).run()
