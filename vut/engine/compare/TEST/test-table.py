#! /usr/bin/env python3
"""'table' region: every line is a row of columns.

Pins DOC/SEMANTICS.txt section 7.5 (TABLE): ordered/unordered/key-matched
rows, ignored columns, per-column relative numeric tolerance, custom
separators, the nominal-is-authoritative rule, the malformed-data
asymmetry, and the loud specification errors.
"""
import sys
import os
import io
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(sys.argv[0]), "../../../../"))

from vut.engine.compare.configuration   import Configuration      # noqa: E402
import vut.engine.compare.main          as     main               # noqa: E402
from vut.engine.compare.region.registry import RegionSyntaxError  # noqa: E402

if "--hwut-info" in sys.argv:
    print("Table Region: ordered, unordered, key, columns, errors;")
    print("CHOICES: modes, columns, key, errors;")
    sys.exit()

CONFIG = Configuration()


async def verdict_pair(subject_txt, nominal_txt):
    """RETURNS: (bool, bool), Judge and Lawyer verdict -- THE LAW requires
                agreement.
    """
    judge = await main.is_equivalent(CONFIG, io.StringIO(subject_txt),
                                             io.StringIO(nominal_txt))
    lawyer = await main.is_equivalent_by_association(
                                     CONFIG, io.StringIO(subject_txt),
                                             io.StringIO(nominal_txt))
    return judge, lawyer


def show(title, subject_txt, nominal_txt):
    judge, lawyer = asyncio.run(verdict_pair(subject_txt, nominal_txt))
    agree = "ok" if judge == lawyer else "LAW-BROKEN"
    print("%-42s judge: %-5s lawyer: %-5s [%s]"
          % (title + ":", judge, lawyer, agree))


def region(params, body):
    return "##! table %s\n%s####\n" % (params, body)


if "modes" in sys.argv:
    print("## Ordered (default) vs unordered (bag with bijective matching).")
    show("ordered equal",     region("", "a 1\nb 2\n"),
                              region("", "a 1\nb 2\n"))
    show("ordered swapped",   region("", "b 2\na 1\n"),
                              region("", "a 1\nb 2\n"))
    show("unordered swapped", region("unordered", "b 2\na 1\n"),
                              region("unordered", "a 1\nb 2\n"))
    show("row surplus",       region("", "a 1\nb 2\n"),
                              region("", "a 1\n"))
    show("row missing",       region("", "a 1\n"),
                              region("", "a 1\nb 2\n"))
    show("both empty",        region("", ""), region("", ""))
    print("## Malformed subject data is a test failure (red), not an error:")
    show("subject width clash", region("", "a 1 EXTRA\n"),
                                region("", "a 1\n"))

if "columns" in sys.argv:
    print("## ignore=<cols> and numeric={col:tol,...} (relative tolerance).")
    show("ignored column differs", region("ignore=1", "a 999\n"),
                                   region("ignore=1", "a 1\n"))
    show("numeric within 10%",  region("numeric={1:0.1}", "a 1.05\n"),
                                region("numeric={1:0.1}", "a 1.0\n"))
    show("numeric beyond 10%",  region("numeric={1:0.1}", "a 1.2\n"),
                                region("numeric={1:0.1}", "a 1.0\n"))
    show("two rules combined",  region("ignore=2 numeric={1:0.1}",
                                       "a 1.02 zzz\n"),
                                region("ignore=2 numeric={1:0.1}",
                                       "a 1.0 t0\n"))
    show("sep={;} splitting",   region("sep={;} ignore=1", "a; 42 ;x\n"),
                                region("sep={;} ignore=1", "a;13;x\n"))
    print("## Nominal is authoritative: the subject's params are ignored.")
    show("subject declares no rules", region("", "a 999\n"),
                                      region("ignore=1", "a 1\n"))

if "key" in sys.argv:
    print("## key=<col>: rows matched by key cell (implies unordered).")
    show("key-matched, reordered",
         region("key=0 ignore=2 numeric={1:0.1}", "b 2.05 xxx\na 1.0 yyy\n"),
         region("key=0 ignore=2 numeric={1:0.1}", "a 1.0 t1\nb 2.0 t2\n"))
    show("unknown subject key",
         region("key=0", "c 1\n"), region("key=0", "a 1\n"))
    show("nominal key uncovered",
         region("key=0", "a 1\n"), region("key=0", "a 1\nb 2\n"))
    show("duplicate subject key",
         region("key=0", "a 1\na 1\n"), region("key=0", "a 1\n"))

if "errors" in sys.argv:
    print("## Broken NOMINAL specifications fail LOUDLY.")
    bad = [
        ("nominal width clash",
         region("", "a 1\n"),              region("", "a 1\nb 2 3\n")),
        ("parameter column out of range",
         region("key=5", "a 1\n"),         region("key=5", "a 1\n")),
        ("duplicate nominal key",
         region("key=0", "a 1\n"),         region("key=0", "a 1\na 2\n")),
        ("nominal numeric cell not a number",
         region("numeric={1:0.1}", "a 1\n"),
         region("numeric={1:0.1}", "a xyz\n")),
        ("malformed numeric spec",
         region("numeric={1}", "a 1\n"),   region("numeric={1}", "a 1\n")),
        ("unknown parameter",
         region("frobnicate=1", "a 1\n"),  region("frobnicate=1", "a 1\n")),
    ]
    for name, subject_txt, nominal_txt in bad:
        try:
            asyncio.run(verdict_pair(subject_txt, nominal_txt))
            print("%-36s -> NO ERROR (unexpected!)" % name)
        except RegionSyntaxError as e:
            print("%-36s -> %s" % (name, e))
