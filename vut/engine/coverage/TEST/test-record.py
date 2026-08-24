#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: The homogeneous coverage record -- the one part of this
         component that is NOT language-specific, and therefore the
         fixed target every later reader is measured against.

CHOICES: intervals, encoding, roundtrip, merge, faults, election;

DESCRIPTION:

intervals  the half-open interval algebra: adjacent line numbers fold
           into ranges, 'union' is the merge, 'subtract' is what makes
           'EX - CV' the uncovered set the pack shows. A file with no
           executable line has NO ratio -- 1.0 would be a lie told in
           the green direction.

encoding   the delta coding: 'd+L' per range, 'd' alone where a range
           is one line, 'd+L*C' where counts are recorded. Encode and
           decode are inverse over every shape, the empty one included.

roundtrip  a whole record through 'format_record' and back: header
           provenance (language, tool, format, counts) survives, file
           blocks survive, and the bytes are stable because files are
           written sorted.

merge      the union across records: associative and commutative, so an
           aggregate does not depend on the order it walked. Provenance
           that AGREES is carried; provenance that DIFFERS is joined, so
           a non-uniform aggregate shows that it is one.

faults     what a record must never be read as: an unstated version, a
           missing header field, a block without 'EX' or 'CV', a delta
           that walks backwards, counts promised and absent. Every one
           is refused BY NAME -- a coverage record half-read is a
           coverage report that lies.

election   the language derived from an extension where none is stated,
           the candidate list matched by glob, the FIRST available
           candidate elected, and the three refusals: no derivation, no
           configured tool, no available candidate.
______________________________________________________________________________
"""
import sys
import config                                                   # noqa: F401

from vut.language_support.python.hwut_runner import HwutRunner
from vut.engine.coverage.record       import (ranges_of, union, subtract,
                                              line_n, encode, decode,
                                              FileCoverage, CoverageRecord,
                                              format_record, parse_record,
                                              merge, RecordFault,
                                              CountsNotMergeable)
from vut.engine.coverage.configuration import CoverageConfig, CoverageRefused
from vut.engine.coverage.registry      import (language_of,
                                               candidate_tuple_of, elect)


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def check(pair_list):
    """
    RETURN: True,  every claim held; prints OK/FAIL per line.
            False, else.
    """
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def verdict(ok, sentence):
    """RETURN: None. The one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


def raised(action):
    """
    RETURN: str, the name of the exception 'action' raised.
            'nothing', if it raised none.
    """
    try:
        action()
    except Exception as x:
        return type(x).__name__
    return "nothing"


# ---------------------------------------------------------------------------

def test_intervals():
    """The half-open interval algebra everything else stands on."""
    banner("adjacent lines fold into ranges")
    folded = ranges_of([3, 4, 5, 6, 9, 20, 21])
    print("INSPECT: %s" % (folded,))
    print("         out of order, with duplicates -> %s"
          % (ranges_of([9, 3, 4, 9, 5, 6, 21, 20]),))
    print("         nothing -> %s" % (ranges_of([]),))

    banner("union is the merge")
    a = ranges_of([1, 2, 3, 10])
    b = ranges_of([3, 4, 5, 11])
    print("INSPECT: %s U %s = %s" % (a, b, union(a, b)))
    print("         order does not matter: %s" % (union(b, a) == union(a, b),))

    banner("subtract: EX - CV is what the pack shows")
    executable = ranges_of(range(1, 21))
    covered    = ranges_of(list(range(1, 6)) + list(range(15, 21)))
    print("INSPECT: EX = %s" % (executable,))
    print("         CV = %s" % (covered,))
    print("         uncovered = %s" % (subtract(executable, covered),))

    banner("a file with no executable line has NO ratio")
    empty = FileCoverage("nothing.py")
    whole = FileCoverage("whole.py", executable, covered)
    print("INSPECT: empty.ratio = %s" % (empty.ratio,))
    print("         whole.ratio = %.4f" % whole.ratio)

    ok = check([
        (folded == ((3, 7), (9, 10), (20, 22)),
         "adjacent lines fold; a lone line is a range of one"),
        (ranges_of([9, 3, 4, 9, 5, 6, 21, 20]) == ((3, 7), (9, 10), (20, 22)),
         "unsorted input with duplicates folds identically"),
        (ranges_of([]) == (),
         "no line folds to no range"),
        (union(a, b) == ((1, 6), (10, 12)),
         "union merges overlapping AND adjacent ranges"),
        (union(a, b) == union(b, a),
         "union is commutative"),
        (union(union(a, b), ranges_of([30])) ==
         union(a, union(b, ranges_of([30]))),
         "union is associative -- an aggregate ignores its walk order"),
        (subtract(executable, covered) == ((6, 15),),
         "EX - CV is the uncovered set"),
        (subtract(executable, ()) == executable,
         "subtracting nothing changes nothing"),
        (subtract(executable, executable) == (),
         "subtracting everything leaves nothing"),
        (line_n(executable) == 20 and line_n(()) == 0,
         "line_n counts lines, not ranges"),
        (empty.ratio is None,
         "no executable line -> ratio None, never 1.0"),
        (abs(whole.ratio - 0.55) < 1e-9,
         "11 of 20 lines covered -> 0.55"),
    ])
    verdict(ok, "the interval algebra holds, and absence is not zero.")


def test_encoding():
    """The delta coding, and its inverse."""
    banner("delta coding: 'd+L', and 'd' alone for one line")
    scattered = ranges_of([3, 7, 40])
    runs      = ranges_of(list(range(3, 15)) + list(range(20, 25)))
    print("INSPECT: %s -> '%s'" % (scattered, encode(scattered)))
    print("         %s -> '%s'" % (runs, encode(runs)))
    print("         () -> '%s'" % encode(()))

    banner("with hit counts")
    counted = encode(runs, (4, 1))
    print("INSPECT: '%s'" % counted)

    banner("decode is the inverse")
    for label, range_tuple in (("scattered", scattered), ("runs", runs),
                               ("empty", ())):
        text  = encode(range_tuple)
        back, count_tuple = decode(text)
        print("         %-9s '%s' -> %s" % (label, text, back))

    back_counted, count_tuple = decode(counted, counts_f=True)
    print("         counted   '%s' -> %s counts %s"
          % (counted, back_counted, count_tuple))

    ok = check([
        (encode(scattered) == "3,3,32",
         "a one-line range is written as its delta alone"),
        (encode(runs) == "3+12,5+5",
         "a run carries its length, and the delta is the GAP"),
        (encode(()) == "",
         "no range encodes to the empty string"),
        (decode(encode(scattered))[0] == scattered,
         "decode inverts encode -- scattered"),
        (decode(encode(runs))[0] == runs,
         "decode inverts encode -- runs"),
        (decode("")[0] == (),
         "the empty string decodes to no range"),
        (decode("")[1] is None,
         "and to no counts, since none were promised"),
        (counted == "3+12*4,5+5*1",
         "a counted range carries its count after '*'"),
        (back_counted == runs and count_tuple == (4, 1),
         "counts survive the round trip"),
        (len(encode(ranges_of(range(1, 5001)))) < 10,
         "5000 contiguous lines encode to under ten characters"),
    ])
    verdict(ok, "delta coding is compact, and exactly invertible.")


def test_roundtrip():
    """A whole record, out and back."""
    record = CoverageRecord(
        test     = "test-parse.py",
        choice   = "basic",
        language = "python",
        tool     = "coverage",
        source   = "coverage.py-json",
        counts_f = False,
        file_db  = {
            "parser/core.py":    FileCoverage("parser/core.py",
                                              ranges_of(range(3, 15)),
                                              ranges_of(range(3, 10))),
            "parser/grammar.py": FileCoverage("parser/grammar.py",
                                              ranges_of([1, 2, 3]),
                                              ranges_of([1, 2, 3])),
            "nothing.py":        FileCoverage("nothing.py"),
        })
    text = format_record(record)
    banner("the stored form")
    for line in text.splitlines():
        print("    | %s" % line)

    back = parse_record(text)
    banner("read back")
    print("INSPECT: test=%s choice=%s" % (back.test, back.choice))
    print("         language=%s tool=%s format=%s counts=%s"
          % (back.language, back.tool, back.source, back.counts_f))
    for path in sorted(back.file_db):
        entry = back.file_db[path]
        ratio = "none" if entry.ratio is None else "%.3f" % entry.ratio
        print("         %-20s EX=%s CV=%s uncovered=%s ratio=%s"
              % (path, entry.executable, entry.covered,
                 entry.uncovered, ratio))

    ok = check([
        (format_record(back) == text,
         "format(parse(format(x))) == format(x) -- the bytes are stable"),
        (back.test == "test-parse.py" and back.choice == "basic",
         "the header names the RUN this record is of"),
        (back.language == "python" and back.tool == "coverage"
         and back.source == "coverage.py-json",
         "the header's provenance survives: language, tool, format"),
        (back.counts_f is False,
         "and whether counts were recorded"),
        (sorted(back.file_db) == ["nothing.py", "parser/core.py",
                                  "parser/grammar.py"],
         "every source file survives"),
        ("nothing.py" in back.file_db
         and back.file_db["nothing.py"].executable == (),
         "a MEASURED file with no executable line keeps its block: "
         "absent and empty do not collapse"),
        (back.file_db["parser/core.py"].uncovered == ((10, 15),),
         "the uncovered ranges are derived, never stored"),
    ])
    verdict(ok, "a record survives the round trip, provenance included.")


def test_merge():
    """The union across records -- the aggregate."""
    def made_by(tool, path, executable, covered):
        """RETURN: CoverageRecord, one file, one tool."""
        return CoverageRecord("python", tool, "coverage.py-json", False,
                              {path: FileCoverage(path,
                                                  ranges_of(executable),
                                                  ranges_of(covered))})

    a = made_by("coverage", "core.py", range(1, 21), range(1, 6))
    b = made_by("coverage", "core.py", range(1, 21), range(15, 21))
    c = made_by("coverage", "other.py", range(1, 5), range(1, 3))

    banner("two runs of one file")
    both = merge([a, b])
    entry = both.file_db["core.py"]
    print("INSPECT: CV(a) = %s" % (a.file_db["core.py"].covered,))
    print("         CV(b) = %s" % (b.file_db["core.py"].covered,))
    print("         CV(merged) = %s" % (entry.covered,))
    print("         uncovered  = %s" % (entry.uncovered,))

    banner("order does not matter")
    print("INSPECT: merge(a,b) == merge(b,a) -> %s"
          % (format_record(merge([a, b])) == format_record(merge([b, a]))))

    banner("provenance that differs is JOINED, so it is visible")
    mixed = merge([a, made_by("trace", "core.py", range(1, 21), [7])])
    print("INSPECT: tool = '%s'" % mixed.tool)

    banner("counts refuse to merge")
    counted = CoverageRecord("python", "coverage", "coverage.py-json", True,
                             {"core.py": FileCoverage("core.py",
                                                      ranges_of([1, 2]),
                                                      ranges_of([1]),
                                                      (3,))})
    print("INSPECT: raised %s" % raised(lambda: merge([a, counted])))

    banner("an aggregate over nothing is not an empty aggregate")
    print("INSPECT: merge([]) -> %s" % merge([]))

    ok = check([
        (entry.covered == ((1, 6), (15, 21)),
         "the merged covered set is the union of both runs"),
        (entry.uncovered == ((6, 15),),
         "and the uncovered set shrinks accordingly"),
        (format_record(merge([a, b])) == format_record(merge([b, a])),
         "merge is commutative -- byte for byte"),
        (format_record(merge([merge([a, b]), c]))
         == format_record(merge([a, merge([b, c])])),
         "merge is associative -- byte for byte"),
        (mixed.tool == "coverage,trace",
         "a non-uniform aggregate SHOWS that it is one"),
        (merge([a, a]).file_db["core.py"].covered
         == a.file_db["core.py"].covered,
         "merge is idempotent: a record merged with itself is itself"),
        (raised(lambda: merge([a, counted])) == "CountsNotMergeable",
         "hit counts are refused by name, not resolved by an unasked rule"),
        (merge([]) is None,
         "no record aggregates to None, never to an empty record"),
    ])
    verdict(ok, "the aggregate is order-free, and says when it is mixed.")


def test_faults():
    """What a record must never be read as."""
    good = ("##VUT-COVERAGE 1\n##test:     a\n##choice:   basic\n"
            "##language: python\n##tool:     coverage\n"
            "##format:   coverage.py-json\n##counts:   no\n"
            "SF:a.py\nEX:1+3\nCV:1\n")

    case_list = [
        ("no version",
         good.replace("##VUT-COVERAGE 1\n", "")),
        ("a version this reader does not know",
         good.replace("VUT-COVERAGE 1", "VUT-COVERAGE 7")),
        ("no 'tool' in the header",
         good.replace("##tool:     coverage\n", "")),
        ("no 'test' in the header -- the run would be anonymous",
         good.replace("##test:     a\n", "")),
        ("no 'choice' in the header",
         good.replace("##choice:   basic\n", "")),
        ("a block without 'CV'",
         good.replace("CV:1\n", "")),
        ("'EX' before any 'SF'",
         "##VUT-COVERAGE 1\n##test: a\n##choice: -\n##language: python\n"
         "##tool: coverage\n##format: x\n##counts: no\nEX:1\n"),
        ("a delta that does not advance",
         good.replace("CV:1", "CV:0")),
        ("a range that spells no number",
         good.replace("EX:1+3", "EX:one+3")),
        ("counts promised, none given",
         good.replace("##counts:   no", "##counts:   yes")),
        ("counts given, none promised",
         good.replace("CV:1", "CV:1*4")),
        ("an unknown record line",
         good + "ZZ:1\n"),
    ]
    banner("every fault, refused by name")
    result_list = []
    for label, text in case_list:
        name = raised(lambda t=text: parse_record(t))
        print("         %-38s -> %s" % (label, name))
        result_list.append((name in ("RecordFault", "CountsNotMergeable"),
                            "refused: %s" % label))

    banner("and the good one is read")
    record = parse_record(good)
    print("INSPECT: a.py EX=%s CV=%s"
          % (record.file_db["a.py"].executable,
             record.file_db["a.py"].covered))

    ok = check(result_list + [
        (record.file_db["a.py"].executable == ((1, 4),),
         "the well-formed record still reads"),
        (record.test == "a" and record.choice == "basic",
         "and it names the run it is of"),
    ])
    verdict(ok, "a record is read whole or refused by name; never half.")


def test_election():
    """Language, candidates, and the three refusals."""
    machine = {"coverage", "gcov"}

    def available(tool):
        """RETURN: True, the stated machine has 'tool'."""
        return tool in machine

    banner("the language is derived where it is not stated")
    print("INSPECT: 'test-parse.py'  -> %s" % language_of("test-parse.py"))
    print("         'engine.cpp'     -> %s" % language_of("engine.cpp"))
    print("         stated wins      -> %s"
          % language_of("test-parse.py", "lua"))

    banner("candidates by glob, in preference order")
    print("INSPECT: python  -> %s" % (candidate_tuple_of("python"),))
    print("         python3 -> %s" % (candidate_tuple_of("python3"),))
    print("         c++     -> %s" % (candidate_tuple_of("c++"),))

    banner("the FIRST available candidate is elected")
    print("INSPECT: python on this stated machine -> %s"
          % elect("python", available=available))
    print("         c      on this stated machine -> %s"
          % elect("c", available=available))

    banner("the three refusals")
    print("         no derivation   -> %s"
          % raised(lambda: language_of("mystery")))
    print("         no tool for it  -> %s"
          % raised(lambda: candidate_tuple_of("brainfuck")))
    print("         none available  -> %s"
          % raised(lambda: elect("lua", available=available)))

    ok = check([
        (language_of("test-parse.py") == "python",
         "'.py' derives python"),
        (language_of("engine.cpp") == "c++",
         "'.cpp' derives c++"),
        (language_of("test-parse.py", "lua") == "lua",
         "a stated language wins over the derivation"),
        (candidate_tuple_of("python")[0] == "coverage",
         "the glob 'python*' answers for 'python', readable tool first"),
        (candidate_tuple_of("python3") == candidate_tuple_of("python"),
         "and for 'python3' -- one language under two names"),
        (candidate_tuple_of("vhdl")[0] == "gcov",
         "vhdl reaches gcov, because GHDL's gcc backend writes it -- a "
         "language served by a table entry and no code"),
        (candidate_tuple_of("pascal") == (),
         "and a language this build vouches for no tool on has an EMPTY "
         "list: saying so beats inventing a default"),
        (elect("python", available=available) == "coverage",
         "the first available candidate is elected"),
        (elect("c", available=available) == "gcov",
         "and the preference order decides which"),
        (raised(lambda: language_of("mystery")) == "CoverageRefused",
         "an underivable language is refused, never guessed"),
        (raised(lambda: candidate_tuple_of("brainfuck")) == "CoverageRefused",
         "a language with no configured tool is refused"),
        (raised(lambda: elect("lua", available=available)) == "CoverageRefused",
         "a machine with no candidate is refused, not silently skipped"),
    ])
    verdict(ok, "election is stated at every step, and refuses rather "
                "than guesses.")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The homogeneous coverage record: intervals, delta "
                     "coding, merge, election",
        choice_map = {
            "intervals": test_intervals,
            "encoding":  test_encoding,
            "roundtrip": test_roundtrip,
            "merge":     test_merge,
            "faults":    test_faults,
            "election":  test_election,
        },
        happy      = "SUCCESS.*",
    ).run()
