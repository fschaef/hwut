#! /usr/bin/env python3
#
# @hwut {
#     title      = "The binary spelling of the coverage record"
#     choices    = ["faults", "large", "measures", "witnessed"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE BINARY SPELLING OF THE RECORD -- one record, two codecs, one truth.

CHOICES: witnessed, measures, large, faults;

witnessed  every witnessed artifact of 'test-readers.py', harvested by
           its reader, packed and unpacked: the record that comes back
           is the SAME record -- proven by the text spelling of both
           being byte-identical, since the text is the spec.
measures   a record carrying every registered measure, hit counts, a
           UTF-8 path, a name with a non-ASCII character, and numbers
           that need the escape: all of it survives.
large      a record of a hundred thousand ranges: the escape path and
           the fast path meet; size and time are printed as they are
           measured, in coarse units so the GOOD stays machine-free.
faults     what the reader refuses, by name: no magic, an unknown
           version, a truncated buffer, a stream that does not
           advance, a tag no measure claims, bytes after the end.
______________________________________________________________________________
"""
import os
import struct
import sys
import time
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.coverage.record  import (CoverageRecord,       # noqa E402
                                           FileCoverage, ranges_of,
                                           format_record, seated)
from   vut.engine.coverage.binary  import (pack_record,          # noqa E402
                                           unpack_record, MAGIC,
                                           FORMAT_VERSION, ESCAPE)
from   vut.engine.bookkeeper.api import TestRunId        # noqa E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib                                                 # noqa E402
_readers = importlib.import_module("test-readers")


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


def raised(action):
    """RETURN: str, the exception's name; 'nothing' where none."""
    try:               action()
    except Exception as fault: return type(fault).__name__
    return "nothing"


def same(record):
    """RETURN: True, pack then unpack yields a record whose TEXT SPELLING
    is byte-identical to the original's -- the text is the spec."""
    return format_record(unpack_record(pack_record(record))) \
           == format_record(record)


#  ------------------------------------------------------------- choices

WITNESS_LIST = (
    ("coverage",  [("coverage.json",      _readers.COVERAGE_JSON)]),
    ("lcov",      [("run.info",           _readers.COVERAGE_LCOV)]),
    ("gcov",      [("prog.c.gcov",        _readers.PROG_GCOV)]),
    ("cobertura", [("cov.xml",            _readers.COBERTURA_XML)]),
    ("luacov",    [("luacov.report.out",  _readers.LUACOV_REPORT)]),
    ("jacoco",    [("jacoco.xml",         _readers.JACOCO_WITNESSED_XML)]),
    ("verilator", [("coverage.dat",       _readers.VERILATOR_DAT)]),
    ("ghdl",      [("psl.json",           _readers.PSL_JSON)]),
    ("ucis",      [("ucis.xml",           _readers.UCIS_XML)]),
)


def test_witnessed():
    """Every witnessed artifact, through its reader, through both codecs."""
    result_list = []
    banner("witnessed artifacts, packed and unpacked")
    for tool, pair_list in WITNESS_LIST:
        record = _readers.harvested(tool, pair_list)
        if record is None:
            print("         %-10s (the reader found no artifact)" % tool)
            continue
        record = seated(record, TestRunId(0, 0))
        packed = pack_record(record)
        n_ranges = sum(len(f.executable) + len(f.covered)
                       for f in record.file_db.values())
        measures = sorted({m for f in record.file_db.values()
                             for m in (f.measure_db or ())})
        print("         %-10s files %2i  ranges %4i  measures %-22s "
              "identical: %s"
              % (tool, len(record.file_db), n_ranges,
                 ",".join(measures) or "-", same(record)))
        result_list.append((same(record),
                            "%s: the record survives both codecs" % tool))
    ok = check(result_list)
    verdict(ok, "one record, two spellings, one truth.")


def test_measures():
    """Everything the format can carry, in one record."""
    record = CoverageRecord(
        "vhdl", "gcov", "gcov-annotated", counts_f=True,
        run=frozenset([TestRunId(3, 4), TestRunId(7)]),
        file_db={
            "src/blinker.vhdl": FileCoverage(
                "src/blinker.vhdl",
                executable=ranges_of([1, 2, 3, 10, 300, 301, 70000]),
                covered=ranges_of([1, 2, 300]),
                counts=(5, 70000),
                measure_db={
                    "branch": ((5, 1, 2), (9, 2, 2)),
                    "mcdc":   ((4, 2, 3), (4, 3, 3)),
                    "toggle": ((12, "data[0]", 1, 1), (12, "daté[1]", 0, 1)),
                    "cover":  ((3, "p_ok", 1, 1),)}),
            "src/leer/ü.vhdl": FileCoverage("src/leer/ü.vhdl")})
    packed = pack_record(record)
    back   = unpack_record(packed)

    banner("the text of what came back")
    for line in format_record(back).splitlines():
        print("         | %s" % line)

    ok = check([
        (same(record), "every measure, counts, two run ids, UTF-8 "
                       "paths and names: byte-identical text"),
        (back.run == frozenset([TestRunId(3, 4), TestRunId(7)]),
         "the run set survives, the choice-less id among it"),
        (back.file_db["src/blinker.vhdl"].counts == (5, 70000),
         "a count above 254 took the escape and came back"),
        (back.file_db["src/blinker.vhdl"].executable[-1] == (70000, 70001),
         "a range delta above 254 took the escape and came back"),
        (back.file_db["src/leer/ü.vhdl"].executable == (),
         "an empty block is an empty block, not a missing one"),
        (packed[:2] == b"\\x78\\x9c" or packed[0] == 0x78,
         "the file is a zlib stream -- fixed layer, no flag"),
    ])
    verdict(ok, "what the text can say, the bytes can say.")


def test_large():
    """A hundred thousand ranges."""
    file_db = {}
    for f in range(200):
        line_list = []
        line = 1
        for i in range(500):
            line += 1 + (i * 7 + f) % 5
            line_list.append(line)
        covered = [l for i, l in enumerate(line_list) if (i * 3 + f) % 4]
        path = "pkg/mod_%03i.py" % f
        file_db[path] = FileCoverage(path, ranges_of(line_list),
                                     ranges_of(covered))
    record = CoverageRecord("python", "coverage", "coverage.py-json",
                            file_db=file_db, run=frozenset([TestRunId(0)]))
    n_ranges = sum(len(f.executable) + len(f.covered)
                   for f in file_db.values())
    text = format_record(record)
    t0 = time.perf_counter(); packed = pack_record(record)
    t1 = time.perf_counter(); back   = unpack_record(packed)
    t2 = time.perf_counter()
    ratio = len(packed) / len(text)

    banner("size and time")
    print("INSPECT: ranges %i" % n_ranges)
    print("         binary/text size ratio below one half: %s"
          % (ratio < 0.5))
    print("         unpack under one second: %s" % (t2 - t1 < 1.0))
    ok = check([
        (n_ranges > 100000, "more than a hundred thousand ranges"),
        (format_record(back) == text, "byte-identical text after the "
                                      "round trip"),
        (ratio < 0.5, "the bytes are less than half the text"),
        (t2 - t1 < 1.0, "unpacked in under a second"),
    ])
    verdict(ok, "the fast path carries a large record.")


def test_faults():
    """Refused by name."""
    record = CoverageRecord("c", "gcov", "gcov-annotated",
                            file_db={"a.c": FileCoverage(
                                "a.c", ranges_of([1, 2]), ranges_of([1]))})
    good  = pack_record(record)
    plain = zlib.decompress(good)

    def rezip(data): return zlib.compress(data, 6)

    version_at = len(MAGIC)
    case_list = [
        ("not a zlib stream",       b"not zlib at all"),
        ("no magic",                rezip(b"XXXX" + plain[4:])),
        ("a version this build does not read",
                                    rezip(plain[:version_at] + bytes([9])
                                          + plain[version_at + 1:])),
        ("truncated after the header",
                                    rezip(plain[:len(MAGIC) + 1 + 4 + 12])),
        ("bytes after the last file", rezip(plain + b"\\x00")),
        ("a range delta of zero",
                                    rezip(plain.replace(
                                        b"a.c\x02\x00\x00\x00\x01\x02",
                                        b"a.c\x02\x00\x00\x00\x00\x02", 1))),
        ("a tag no measure claims",  None),
    ]
    banner("what the reader refuses")
    result_list = []
    for label, data in case_list:
        if data is None:
            #  Build a record with one measure, then rename its tag.
            with_measure = CoverageRecord(
                "c", "gcov", "gcov-annotated",
                file_db={"a.c": FileCoverage(
                    "a.c", ranges_of([1]), ranges_of([1]),
                    measure_db={"branch": ((1, 1, 2),)})})
            data = rezip(zlib.decompress(pack_record(with_measure))
                         .replace(b"BR", b"ZZ"))
        name = raised(lambda d=data: unpack_record(d))
        print("         %-40s -> %s" % (label, name))
        result_list.append((name == "RecordFault", "refused: %s" % label))
    ok = check(result_list)
    verdict(ok, "a record half read is a report that lies; nothing is "
                "half read.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The binary spelling of the coverage record",
        choice_map = {
            "witnessed": test_witnessed,
            "measures":  test_measures,
            "large":     test_large,
            "faults":    test_faults,
        },
        happy      = "SUCCESS.*",
    ).run()
