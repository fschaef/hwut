#! /usr/bin/env python3
#
# @hwut {
#     title      = "Branch and MC/DC: measures registered beside the line axis"
#     choices    = ["branch", "faults", "in_record", "mcdc", "named",
#                   "points", "registration", "union"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE OTHER MEASUREMENTS -- branch, MC/DC, and the NAMED
         points -- and the registration that admits one more without
         touching the record.

CHOICES: registration, branch, mcdc, named, in_record, union,
         points, faults;

points   every measure as POINTS OF ITEMS -- (line, name, total, mask) --
         the one shape the output files gather (D-43), and back; a named
         point that counts items it does not name is refused.

DESCRIPTION:

registration  a measure owns its NAME and its record TAG, and a second
              measure claiming either is refused. Admitting a third is a
              'register' call and no change to 'record.py'.

branch        'of the arms leaving this decision, WHICH were taken' --
              a mask, bit i for arm i (D-43), delta coded per line, and
              a SECOND decision on one line refused, because branch
              data is reported per line.

named         the NAMED points -- 'toggle' and 'cover' -- carry the
              point's IDENTITY beside its line: a bit toggled in either
              run is toggled, by name. Totals that disagree on one
              named point are refused -- two records that do not
              describe one point.

mcdc          'of the conditions in this decision, WHICH had their
              INDEPENDENCE demonstrated'. Here a delta of ZERO IS
              admitted: 'if (a) if (b)' is one line and two decisions,
              and a line-keyed record could not otherwise say so. The
              FIRST delta must still advance -- there is no line zero.

in_record     a measure rides in its own line under its own tag. A file
              with no such measurement writes NO such line, so a record
              of line coverage alone is byte-identical to what it was
              before any measure existed.

union         WHY branch and MC/DC now merge. A mask carries WHICH arms
              were taken: run A takes arm 0, run B takes arm 1, and the
              union is the OR, 3 -- where a count (1 and 1) had no
              answer. A measure that cannot name its items still
              declares itself unmergeable and is refused by name.

faults        a point that spells no point, a delta that does not
              advance, a total of nothing, and a mask naming an item the
              decision does not have -- which is arithmetic, not
              measurement.
______________________________________________________________________________
"""
import sys
import config                                                   # noqa: F401

from vut.test_writing_support.python.hwut_runner import HwutRunner
from vut.engine.coverage.database.measure import (I_Measure, PointMeasure,
                                         NamedPointMeasure, register,
                                         measure_of, measure_of_tag,
                                         name_tuple, tag_tuple,
                                         MeasureFault, BRANCH, MCDC,
                                         TOGGLE, COVER, FUNCTION)
from vut.engine.coverage.database.record  import (ranges_of, FileCoverage,
                                         CoverageRecord, format_record,
                                         parse_record, merge,
                                         MeasureNotMergeable, RecordFault)
from vut.engine.bookkeeper.api import TestRunId


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


def record_with(measure_db):
    """RETURN: CoverageRecord of one file carrying those measures."""
    return CoverageRecord(
        language="c", tool="gcov", source="gcov-annotated", counts_f=False,
        run=frozenset([TestRunId(0, 0)]),
        file_db={"core.c": FileCoverage("core.c",
                                        ranges_of([1, 2, 3, 4]),
                                        ranges_of([1, 2, 4]),
                                        None, measure_db)})


# ---------------------------------------------------------------------------

def test_registration():
    """A measure owns a name and a tag; neither is shared."""
    banner("what is registered")
    for name in name_tuple():
        measure = measure_of(name)
        print("         %-8s tag '%s'   mergeable %s"
              % (name, measure.tag, measure.mergeable))

    banner("a second measure claiming a taken name, or a taken tag")
    print("         name 'branch' again -> %s"
          % raised(lambda: register(PointMeasure("branch", "XX"))))
    print("         tag 'BR' again      -> %s"
          % raised(lambda: register(PointMeasure("arms", "BR"))))

    ok = check([
        (name_tuple() == ("branch", "cover", "function", "mcdc", "toggle"),
         "five measures are registered, and the record writes them in "
         "this order so the bytes are stable"),
        (tag_tuple() == ("BR", "CP", "FN", "MC", "TG"),
         "each owns a record tag"),
        (measure_of("branch") is BRANCH and measure_of_tag("MC") is MCDC
         and measure_of("toggle") is TOGGLE
         and measure_of_tag("CP") is COVER,
         "and answers to both its name and its tag"),
        (measure_of("fsm") is None and measure_of_tag("ZZ") is None,
         "what is not registered answers None -- the caller decides "
         "whether that is a fault"),
        (raised(lambda: register(PointMeasure("branch", "XX")))
         == "MeasureFault",
         "a second measure of one NAME is refused"),
        (raised(lambda: register(PointMeasure("arms", "BR")))
         == "MeasureFault",
         "and a second behind one TAG: two truths, and the later import "
         "would win"),
    ])
    verdict(ok, "a measure is registered once, under one name and one "
                "tag.")


def test_branch():
    """Arms taken, per line."""
    entry = ((2, 1, 2), (10, 0, 2), (11, 7, 3))
    text  = BRANCH.encode(entry)
    banner("three decisions")
    print("INSPECT: %s" % (entry,))
    print("         -> '%s'" % text)
    print("         summary (covered, total) = %s" % (BRANCH.summary(entry),))

    banner("a second decision on ONE line is refused for branch")
    print("         raised %s" % raised(lambda: BRANCH.decode("2*1/2,0*1/2")))

    ok = check([
        (text == "2*1/2,8*0/2,1*7/3",
         "delta coded on the line, as the ranges are"),
        (BRANCH.decode(text) == entry,
         "decode inverts encode"),
        (BRANCH.summary(entry) == (4, 7),
         "the summary counts the arms taken and the arms there are; the "
         "ratio is DERIVED by whoever renders, and stored by nobody"),
        (BRANCH.encode(()) == "" and BRANCH.decode("") == (),
         "no decision encodes to the empty string, and back"),
        (raised(lambda: BRANCH.decode("2*1/2,0*1/2")) == "MeasureFault",
         "branch data is reported PER LINE, so a zero delta means "
         "nothing and is refused"),
        (BRANCH.mergeable is True,
         "and it declares itself mergeable: the mask says which arms"),
    ])
    verdict(ok, "branch coverage is a point measure on the line axis.")


def test_mcdc():
    """Independence demonstrated, per decision."""
    #  'if (a) if (b)' -- one line, two decisions.
    entry = ((4, 3, 3), (4, 7, 3), (9, 0, 2))
    text  = MCDC.encode(entry)
    banner("two decisions on line 4, one on line 9")
    print("INSPECT: %s" % (entry,))
    print("         -> '%s'" % text)
    print("         summary = %s" % (MCDC.summary(entry),))

    banner("the FIRST delta must still advance -- there is no line zero")
    print("         raised %s" % raised(lambda: MCDC.decode("0*1/2")))

    ok = check([
        (text == "4*3/3,0*7/3,5*0/2",
         "a delta of ZERO is a SECOND decision on the same line"),
        (MCDC.decode(text) == entry,
         "decode inverts encode, the zero delta included"),
        (MCDC.summary(entry) == (5, 8),
         "five conditions shown independent of eight"),
        (raised(lambda: MCDC.decode("0*1/2")) == "MeasureFault",
         "but the FIRST delta must advance: there is no line zero"),
        (MCDC.mergeable is True,
         "MC/DC declares itself mergeable: the mask says WHICH "
         "conditions, and two runs may demonstrate independence of "
         "different ones"),
    ])
    verdict(ok, "MC/DC is per DECISION, and a line may carry several.")


def test_named():
    """The named points: identity carried, so merge is honest."""
    entry = ((7, "count[0]", 1, 1), (7, "count[3]", 0, 1),
             (31, "cover", 1, 1))
    banner("encode, and read back")
    encoded = TOGGLE.encode(entry)
    print("         %s" % encoded)
    print("         summary: %i of %i" % TOGGLE.summary(entry))

    banner("the union of two runs")
    run_a = ((7, "count[0]", 1, 1), (7, "count[3]", 0, 1))
    run_b = ((7, "count[0]", 0, 1), (7, "count[3]", 1, 1))
    merged = TOGGLE.merge(run_a, run_b)
    print("         a: %s" % (TOGGLE.encode(run_a)))
    print("         b: %s" % (TOGGLE.encode(run_b)))
    print("         u: %s" % (TOGGLE.encode(merged)))

    banner("what is refused")
    print("         a name carrying '*'   -> %s"
          % raised(lambda: TOGGLE.encode(((3, "a*b", 1, 1),))))
    print("         totals that disagree  -> %s"
          % raised(lambda: TOGGLE.merge(((3, "s", 1, 1),),
                                        ((3, "s", 1, 2),))))
    print("         covered above total   -> %s"
          % raised(lambda: TOGGLE.decode("3*s*2/1")))

    ok = check([
        (TOGGLE.decode(encoded) == entry,
         "the encoding round-trips: '<delta>*<name>*<covered>/<total>', "
         "a zero delta admitting a second point on one line"),
        (TOGGLE.mergeable and COVER.mergeable,
         "both named measures declare mergeable -- the artifact names "
         "every point"),
        (merged == ((7, "count[0]", 1, 1), (7, "count[3]", 1, 1)),
         "a bit toggled in EITHER run is toggled, computed by name"),
        (TOGGLE.summary(merged) == (2, 2),
         "and the summary derives from the union, not from adding "
         "summaries"),
        (raised(lambda: TOGGLE.merge(((3, "s", 1, 1),),
                                     ((3, "s", 1, 2),)))
         == "MeasureFault",
         "one name, two totals: not one point, refused rather than "
         "adjudicated"),
    ])
    verdict(ok, "identity beside the count is what makes a union a "
                "measurement.")


def test_in_record():
    """A measure rides in its own line, and costs nothing when absent."""
    plain    = record_with({})
    measured = record_with({"branch": ((2, 1, 2),),
                            "mcdc":   ((4, 2, 3), (4, 3, 3))})

    banner("a record of line coverage alone")
    for line in format_record(plain).splitlines():
        print("         | %s" % line)

    banner("the same record, measured further")
    text = format_record(measured)
    for line in text.splitlines():
        print("         | %s" % line)

    back = parse_record(text)
    ok = check([
        ("BR:" not in format_record(plain)
         and "MC:" not in format_record(plain),
         "a file with no such measurement writes NO such line: a record "
         "of lines alone is what it was before any measure existed"),
        ("BR:2*1/2" in text and "MC:4*2/3,0*3/3" in text,
         "each measure rides under its own tag"),
        (text.index("BR:") < text.index("MC:"),
         "in registered-name order, so two runs of one test produce the "
         "same bytes"),
        (format_record(back) == text,
         "format(parse(format(x))) == format(x)"),
        (back.file_db["core.c"].measure_db["branch"] == ((2, 1, 2),)
         and back.file_db["core.c"].measure_db["mcdc"]
             == ((4, 2, 3), (4, 3, 3)),
         "and both survive the round trip"),
        (back.file_db["core.c"].covered == ((1, 3), (4, 5)),
         "while the line coverage is untouched by either"),
        (raised(lambda: parse_record(text.replace("BR:", "ZZ:")))
         == "RecordFault",
         "a tag no measure claims is refused, naming what IS claimed"),
    ])
    verdict(ok, "a measure is a line in the record and a lookup in the "
                "registry; the record knows what none of them mean.")


class OpaqueMeasure(PointMeasure):
    """A measure whose entry cannot name its items: a count. It declares
    itself unmergeable, as every measure that cannot say WHICH must."""

    def __init__(self):
        """RETURN: OpaqueMeasure, registered under tag 'ZQ'."""
        super().__init__("opaque", "ZQ")
        self.mergeable = False


def test_points():
    """The one shape the output files gather, and back."""
    banner("points of items")
    sample_db = {
        BRANCH:   ((3, 1, 2), (3, 6, 3), (9, 0, 2)),
        MCDC:     ((4, 3, 2), (4, 0, 3)),
        TOGGLE:   ((2, "clk", 1, 1), (2, "rst", 0, 1)),
        COVER:    ((5, "p", 1, 1),),
        FUNCTION: ((1, "main", 1, 1), (6, "f", 0, 1)),
    }
    result_list = []
    for measure, entry in sample_db.items():
        points = measure.point_list(entry)
        print("         %-9s %s" % (measure.name, points))
        result_list.append((measure.entry_of(points) == entry,
                            "'%s' goes to points and comes back"
                            % measure.name))
    result_list.append((
        raised(lambda: TOGGLE.point_list(((2, "bus", 3, 4),)))
        == "MeasureFault",
        "a count of 3 of 4 items names none: refused"))
    result_list.append((FUNCTION.tag == "FN" and FUNCTION.mergeable
                        and FUNCTION.named_f and not BRANCH.named_f,
                        "the function is a named point of one item"))
    ok = check(result_list)
    verdict(ok, "one shape for every measure.")


def test_union():
    """Why a mask merges where a count could not."""
    a = record_with({"branch": ((2, 1, 2),), "mcdc": ((4, 1, 3),)})
    b = record_with({"branch": ((2, 2, 2),), "mcdc": ((4, 2, 3),)})

    banner("two runs, one decision, DIFFERENT arms")
    print("         run A: line 2, arm 0 taken   (mask 1 of 2 arms)")
    print("         run B: line 2, arm 1 taken   (mask 2 of 2 arms)")
    merged = merge([a, b])
    for line in format_record(merged).splitlines():
        if line[:3] in ("BR:", "MC:"): print("         | %s" % line)
    print("         together the decision is FULLY covered: mask 3")

    banner("what is still refused")
    print("INSPECT: totals that disagree -> %s"
          % raised(lambda: merge([a, record_with(
              {"branch": ((2, 1, 3),)})])))
    register(OpaqueMeasure())
    opaque = record_with({"opaque": ((2, 1, 2),)})
    print("INSPECT: a measure that cannot name items -> %s"
          % raised(lambda: merge([opaque, opaque])))

    banner("the same records without the measure merge as ever")
    plain = merge([record_with({}), record_with({})])
    print("         %s" % (plain.file_db["core.c"].covered,))

    ok = check([
        (merged.file_db["core.c"].measure_db["branch"] == ((2, 3, 2),),
         "the union of masks is their OR: both arms taken"),
        (merged.file_db["core.c"].measure_db["mcdc"] == ((4, 3, 3),),
         "MC/DC likewise: independence shown of the conditions either "
         "run showed"),
        (BRANCH.summary(merged.file_db["core.c"].measure_db["branch"])
         == (2, 2),
         "and the summary derives from the union, not from adding "
         "summaries"),
        (raised(lambda: merge([a, record_with({"branch": ((2, 1, 3),)})]))
         == "MeasureFault",
         "one decision with two totals: not one decision, refused "
         "rather than adjudicated"),
        (raised(lambda: merge([opaque, opaque])) == "MeasureNotMergeable",
         "a measure that cannot say WHICH is refused BY NAME"),
        (issubclass(MeasureNotMergeable, RecordFault),
         "and a caller that does not distinguish still sees a "
         "RecordFault"),
        (plain.file_db["core.c"].covered == ((1, 3), (4, 5)),
         "a record carrying no measure merges exactly as before"),
        (merge([record_with({"branch": ()}),
                record_with({"mcdc": ()})]) is not None,
         "an EMPTY measure is not a measurement: it blocks no merge"),
    ])
    verdict(ok, "a mask is a measurement a union can answer.")


def test_faults():
    """Every unreadable point, refused by name."""
    case_list = [
        ("no ratio at all",          "2"),
        ("a delta that is no number", "x*1/2"),
        ("a mask that is no number", "2*x/2"),
        ("a delta that does not advance", "2*1/2,0*1/2"),
        ("a negative delta",         "2*1/2,-1*1/2"),
        ("a total of nothing",       "2*0/0"),
        ("a mask naming a missing arm", "2*4/2"),
    ]
    banner("branch")
    result_list = []
    for label, text in case_list:
        name = raised(lambda t=text: BRANCH.decode(t))
        print("         %-32s -> %s" % (label, name))
        result_list.append((name == "MeasureFault", "refused: %s" % label))

    banner("and the well-formed one still reads")
    print("         '2*1/2' -> %s" % (BRANCH.decode("2*1/2"),))

    ok = check(result_list + [
        (BRANCH.decode("2*1/2") == ((2, 1, 2),),
         "a well-formed point is read"),
    ])
    verdict(ok, "a point is read whole or refused by name; never half.")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Branch and MC/DC: measures registered beside the "
                     "line axis",
        choice_map = {
            "registration": test_registration,
            "branch":       test_branch,
            "mcdc":         test_mcdc,
            "named":        test_named,
            "in_record":    test_in_record,
            "union":        test_union,
            "points":       test_points,
            "faults":       test_faults,
        },
        happy      = "SUCCESS.*",
    ).run()
