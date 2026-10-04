#! /usr/bin/env python3
#
# @hwut {
#     title      = "The gathered coverage of one source file"
#     choices    = ["faults", "measures", "same", "text"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE GATHERED COVERAGE OF ONE SOURCE FILE -- record version 3, what a
coverage run leaves in its output directory (coverage D-42, D-43): binary
on disk, text as the presentation, one content.

CHOICES: same, text, measures, faults;

same     pack then unpack, and format then parse, give back the SAME
         file: with the numbers that need the escape, a UTF-8 path, an
         empty 'EX', an identifier of the widest kind, and a reference
         that took items and ran no line.
text     the text spelling of a small file with its universes and its
         item lists, as 'hwut.cov.conv.to_humans' shows it -- the page the
         format is read from.
measures what a file says about a run: the universe once, the items of
         the references a run is in OR'd to the points the run took --
         the decision points, the named points, and a mask of 300 arms.
faults   what the readers refuse, by name: not a zlib stream, no magic,
         another version, a truncated buffer, bytes after the end,
         references that do not ascend, a measure no registry knows, a
         mask of an item the point lacks, an item under two references,
         an ordinal outside the universe; and in the text: no version
         line, a missing header key, an identifier of the wrong width, a
         line of no kind, items before their universe.
______________________________________________________________________________
"""
import dataclasses
import os
import sys
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.coverage.database.binary     import MAGIC      # noqa E402
from   vut.engine.coverage.database.gathered   import (          # noqa E402
           GatheredFile, binary_version, format_gathered, measure_db_of,
           pack_gathered, parse_gathered, unpack_gathered)
from   vut.engine.coverage.database.record     import RecordFault   # noqa E402


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


#  Two decisions on line 5 (one of 2 arms, one of 3), one on line 9; two
#  toggle bits of line 4. Reference 2 took arm 0 of the first and arms 0
#  and 2 of the second; reference 16 took arm 1 of the first and arm 1 of
#  the second and the bit 'clk'; reference 20 ran no line and took the
#  whole third decision and the bit 'rst'.
SMALL = GatheredFile(
    "engine/compare/core.py", "python", "coverage", "coverage.py-json", 2,
    ((3, 15), (20, 25)),
    ((2,  ((3, 7),),
      (("branch", ((1, 1), (2, 5))),)),
     (16, ((8, 15), (20, 25)),
      (("branch", ((1, 2), (2, 2))), ("toggle", ((1, 1),)))),
     (20, (),
      (("branch", ((3, 3),)), ("toggle", ((2, 1),))))),
    (("branch", ((5, "", 2), (5, "", 3), (9, "", 2))),
     ("toggle", ((4, "clk", 1), (4, "rst", 1)))))


def test_same():
    """RETURN: None. Both spellings give back the same file."""
    banner("one content, two spellings")
    wide = GatheredFile(
        "größe/ü.py", "python", "coverage", "x", 5,
        ((1, 2), (1000, 100000), (100400, 100401)),
        ((0, ((1, 2),), ()), (70000, ((1000, 100000),), ()),
         (1073741823, ((100400, 100401),), ())))
    empty = GatheredFile("e.py", "python", "coverage", "x", 1, (), ())
    #  300 arms: a 38-byte mask, and a point name that is UTF-8.
    huge = GatheredFile(
        "h.c", "c", "gcov", "x", 1, ((1, 2),),
        ((0, (), (("branch", ((1, 1 << 299 | 1),)),
                  ("function", ((1, 1),)))),),
        (("branch", ((1, "", 300), (400000, "", 2))),
         ("function", ((1, "größe", 1),))))
    result_list = []
    for label, gathered in (("a small file", SMALL),
                            ("escaped numbers, a UTF-8 path", wide),
                            ("no line and no reference", empty),
                            ("300 arms, a UTF-8 name", huge)):
        by_binary = unpack_gathered(pack_gathered(gathered)) == gathered
        by_text   = parse_gathered(format_gathered(gathered)) == gathered
        print("         %-34s binary %-5s text %s"
              % (label, by_binary, by_text))
        result_list.append((by_binary and by_text, label))
    result_list.append((binary_version(pack_gathered(SMALL)) == 3,
                        "the version byte reads 3"))
    result_list.append((binary_version(b"not zlib") is None,
                        "bytes that are no zlib stream have no version"))
    ok = check(result_list)
    verdict(ok, "the disk form and the presentation are one content.")


def test_measures():
    """RETURN: None. What a file says about the runs of its references."""
    banner("the measures a set of references stands for")
    runs = {"reference 2":          {2},
            "reference 16":         {16},
            "references 2 and 16":  {2, 16},
            "reference 20":         {20},
            "all three":            {2, 16, 20},
            "no reference":         set()}
    db = {label: measure_db_of(SMALL, reference_set)
          for label, reference_set in runs.items()}
    for label, entry_db in db.items():
        print("         %s" % label)
        for name in sorted(entry_db):
            print("             %-7s %s" % (name, entry_db[name]))

    huge = GatheredFile(
        "h.c", "c", "gcov", "x", 1, ((1, 2),),
        ((0, (), (("branch", ((1, 1 << 299 | 1),)),)),
         (1, (), (("branch", ((1, 2),)),))),
        (("branch", ((1, "", 300),)),))
    wide = measure_db_of(huge, {0, 1})["branch"]
    only = measure_db_of(huge, {0})["branch"]

    ok = check([
        (db["reference 2"]["branch"] == ((5, 1, 2), (5, 5, 3), (9, 0, 2)),
         "a run in reference 2 took arm 0 of the first decision and arms "
         "0 and 2 of the second, and nothing of the third"),
        (db["references 2 and 16"]["branch"]
         == ((5, 3, 2), (5, 7, 3), (9, 0, 2)),
         "a run in two references took the OR of both: every arm"),
        (db["all three"]["branch"] == ((5, 3, 2), (5, 7, 3), (9, 3, 2)),
         "and the reference that ran no line still counts for what it "
         "took"),
        (db["no reference"]["branch"] == ((5, 0, 2), (5, 0, 3), (9, 0, 2)),
         "a run in no reference took no item of any point: the universe "
         "stands, every mask empty"),
        (db["reference 16"]["toggle"] == ((4, "clk", 1, 1), (4, "rst", 0, 1)),
         "named points answer in the measure's own shape"),
        (db["reference 20"]["toggle"] == ((4, "clk", 0, 1), (4, "rst", 1, 1)),
         "each bit stands under the one reference that took it"),
        (wide == ((1, 1 << 299 | 3, 300),)
         and only == ((1, 1 << 299 | 1, 300),),
         "a mask of 300 arms is carried and OR'd whole"),
    ])
    verdict(ok, "the universe once, the items under the references, the "
                "runs from their union.")


def test_text():
    """RETURN: None. The text spelling of a small file."""
    banner("the text spelling")
    sys.stdout.write(format_gathered(SMALL))
    ok = check([(True, "printed")])
    verdict(ok, "the page the format is read from.")


def _replaced(gathered, index, item):
    """RETURN: GatheredFile, 'gathered' with the item list of ONE
    measure of reference number 'index' replaced by 'item' -- a
    (name, entries) pair, appended where that measure has none."""
    reference, spans, item_tuple = gathered.reference_list[index]
    kept = tuple(i for i in item_tuple if i[0] != item[0])
    new  = (reference, spans, tuple(sorted(kept + (item,))))
    return dataclasses.replace(
        gathered, reference_list=(gathered.reference_list[:index] + (new,)
                                  + gathered.reference_list[index + 1:]))


def _universe(gathered, universe):
    """RETURN: GatheredFile, 'gathered' with the universe of one measure
    replaced by 'universe' -- a (name, points) pair -- and the item
    lists left as they were."""
    kept = tuple(u for u in gathered.universe_tuple if u[0] != universe[0])
    return dataclasses.replace(
        gathered, universe_tuple=tuple(sorted(kept + (universe,))))


def test_faults():
    """RETURN: None. What the readers refuse, by name."""
    banner("what the readers refuse")
    good  = pack_gathered(SMALL)
    plain = zlib.decompress(good)

    def rezip(data): return zlib.compress(data, 6)

    case_list = [
        ("not a zlib stream",           lambda: unpack_gathered(b"nope")),
        ("no magic",                    lambda: unpack_gathered(
                                            rezip(b"XXXX" + plain[4:]))),
        ("version 1",                   lambda: unpack_gathered(
                                            rezip(MAGIC + b"\x01"
                                                  + plain[5:]))),
        ("a truncated buffer",          lambda: unpack_gathered(
                                            rezip(plain[:20]))),
        ("bytes after the last reference", lambda: unpack_gathered(
                                            rezip(plain + b"\x00"))),
        ("references that do not ascend", lambda: pack_gathered(
            GatheredFile("a.py", "p", "t", "f", 2, (),
                         ((5, (), ()), (5, (), ()))))),
        ("a universe under a tag nobody claims", lambda: unpack_gathered(
                                            rezip(plain.replace(b"BR",
                                                                b"ZZ")))),
        ("a mask of an item the point lacks", lambda: pack_gathered(
            _replaced(SMALL, 0, ("branch", ((1, 4),))))),
        ("a mask of no item",           lambda: pack_gathered(
            _replaced(SMALL, 0, ("branch", ((1, 0),))))),
        ("an ordinal outside the universe", lambda: pack_gathered(
            _replaced(SMALL, 0, ("branch", ((4, 1),))))),
        ("ordinals that do not ascend", lambda: pack_gathered(
            _replaced(SMALL, 0, ("branch", ((2, 1), (1, 1)))))),
        ("an item under two references", lambda: pack_gathered(
            _replaced(SMALL, 1, ("branch", ((1, 1),))))),
        ("items of a measure the universe lacks", lambda: pack_gathered(
            _replaced(SMALL, 0, ("function", ((1, 1),))))),
        ("a point of no item",          lambda: pack_gathered(
            _universe(SMALL, ("branch", ((5, "", 0),))))),
        ("a decision point with a name", lambda: pack_gathered(
            _universe(SMALL, ("branch", ((5, "x", 2),))))),
        ("a named point without a name", lambda: pack_gathered(
            _universe(SMALL, ("toggle", ((4, "", 1),))))),
        ("a measure nobody registered", lambda: pack_gathered(
            _universe(SMALL, ("fsm", ((4, "", 1),))))),
    ]
    text = format_gathered(SMALL)
    case_list += [
        ("text: no version line",       lambda: parse_gathered(
                                            text.split("\n", 1)[1])),
        ("text: a header key missing",  lambda: parse_gathered(
                                            text.replace("##tool:", "##tol:"))),
        ("text: identifier of the wrong width", lambda: parse_gathered(
                                            text.replace("CV@02", "CV@2"))),
        ("text: a line of no kind",     lambda: parse_gathered(
                                            text + "x:1\n")),
        ("text: a universe nobody claims", lambda: parse_gathered(
                                            text + "XX:1*1\n")),
        ("text: items before their universe", lambda: parse_gathered(
                                            text.replace("BR:", "BQ:", 1)
                                                .replace("BQ:5*2,0*3,4*2\n",
                                                         "", 1))),
        ("text: a universe twice",      lambda: parse_gathered(
                                            text + "BR:1*2\n")),
        ("text: a mask of an item the point lacks", lambda: parse_gathered(
                                            text.replace("BR@02:1*1,1*5",
                                                         "BR@02:1*1,1*8"))),
        ("text: items that do not advance", lambda: parse_gathered(
                                            text.replace("BR@02:1*1,1*5",
                                                         "BR@02:1*1,0*5"))),
        ("text: 'CV@' before 'EX'",     lambda: parse_gathered(
                                            text.replace("EX:3+12,5+5\n", "",
                                                         1))),
    ]
    result_list = []
    for label, action in case_list:
        name = raised(action)
        print("         %-40s -> %s" % (label, name))
        result_list.append((name == "RecordFault", "refused: %s" % label))
    ok = check(result_list)
    verdict(ok, "a file half read is a report that lies; nothing is "
                "half read.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The gathered coverage of one source file",
        choice_map = {
            "same":     test_same,
            "text":     test_text,
            "measures": test_measures,
            "faults":   test_faults,
        },
        happy      = "SUCCESS.*",
    ).run()
