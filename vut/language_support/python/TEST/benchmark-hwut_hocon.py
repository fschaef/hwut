#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Measure the specification parser under whatever interpreter runs
         it, so CPython and PyPy can be compared on the same input.

    python3 benchmark-hwut_hocon.py
    pypy3   benchmark-hwut_hocon.py

Reports the interpreter, the cost of one parse of a full header, and the
cost of a directory's worth of them. Runs a warm-up round first: PyPy's
JIT needs one, and reporting a number it never got is how a comparison
lies.

NOT a HWUT test application: it is a measurement, and its output is a
number that differs per machine. It answers '--hwut-info' with nothing.
______________________________________________________________________________
"""
import sys
import time
import platform

import config                                                   # noqa: F401

from vut.language_support.python.hwut_hocon import parse, SourceLine


HEADER = '''@hwut {
    title       = "Parser corner cases"
    build       { framework = "make"  executable = "special.exe" }
    caps        { timeout_sec = 30  network = false  memory_mb = 512 }
    pype        = "strip.pype"
    numeric     = 0.01
    eq-pattern  = ["bonjour|hello", "v[0-9.]+-build[0-9]+"]
    nothing     = ["_"]
    analogy     = ["((", "))"]
    constraints = ["x < y + 2", "abs(z) < epsilon"]
    comment     = "##"
    slash_eqv   = yes
    mask        = 0xDEAD_BEEF
    pattern     = 0b0111_11_01
    choices {
        one { }
        two { numeric = 0.05  caps { timeout_sec = 5 } }
        three { pype = "other.pype" }
    }
}
'''

SHORT = '''# @hwut {
#     title   = "A modest header"
#     choices = ["one", "two"]
# }
'''


def line_list_of(text):
    """RETURN: list[SourceLine], the text as the parser reads it."""
    return [SourceLine(line, i, 0)
            for i, line in enumerate(text.split("\n"), start=1)]


def measure(line_list, round_n):
    """
    RETURN: float, seconds per parse, the best of three rounds.

    The BEST, not the mean: the machine's other business only ever adds
    time, so the fastest round is the one least polluted by it.
    """
    best = None
    for _ in range(3):
        begin = time.perf_counter()
        for _ in range(round_n):
            parse(line_list, "benchmark")
        span = (time.perf_counter() - begin) / round_n
        best = span if best is None else min(best, span)
    return best


def main():
    """RETURN: None. Prints the interpreter and the measurements."""
    print("interpreter   %s %s (%s)"
          % (platform.python_implementation(),
             platform.python_version(), platform.machine()))

    full  = line_list_of(HEADER)
    short = line_list_of(SHORT)

    document, fault_list = parse(full, "benchmark")
    if fault_list:
        for fault in fault_list: print("FAULT %s" % fault)
        sys.exit(1)

    #  WARM-UP. PyPy's JIT compiles what it has seen run often; a number
    #  taken before it has is a number about the interpreter's cold start.
    measure(full, 2000)

    for label, line_list, round_n in (("full header  (%2d lines)"
                                       % len(full),  full,  5000),
                                      ("short header (%2d lines)"
                                       % len(short), short, 20000)):
        span = measure(line_list, round_n)
        print("%s   %7.1f us per parse   %6.1f ms per 1000 files"
              % (label, span * 1e6, span * 1000 * 1e3))


if __name__ == "__main__":
    if "--hwut-info" in sys.argv:
        sys.exit(0)
    main()
