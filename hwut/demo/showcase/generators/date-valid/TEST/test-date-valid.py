#! /usr/bin/env python3
# @hwut {
#     title    = "Date validator (awk): the boundary space of year x month x day, as calendars"
#     features = ["month-lengths", "out-of-range"]
#     choices {
#         gregorian { features = ["month-lengths", "out-of-range", "leap-rule"]
#                     tolerance { constraints = ["disagreements == 0"] } }
#         four-only { features = ["month-lengths", "out-of-range", "wrong-named"]
#                     tolerance { constraints = ["disagreements > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the verdict of valid_date() (../valid_date*.awk) on every point of
         the year x month x day boundary space, as calendars against datetime
REQUIREMENT  valid_date(y, m, d) is 1 exactly for the dates of the Gregorian
             calendar: months 1..12, days 1..length of the month, February
             29 only in years divisible by 4 and not by 100, or by 400.

The unit is awk ('../valid_date.awk'; '../valid_date_4only.awk' is an older
script with the rule "every fourth year is a leap year"). The ORACLE is
Python's datetime.date, an independent implementation.

THE GENERATOR INSTRUCTION -- three lists:

    YEARS  = 2023 common | 2024 leap (/4) | 1900, 2100 not leap (/100)
             | 2000 leap (/400)
    MONTHS = 0 below | 1 .. 12 EVERY month | 13 above
    DAYS   = 0 below | 1 first | 28 29 30 31 the four possible month ends
             | 32 above every month
    space_iterator.do([YEARS, MONTHS, DAYS])  ->  5 x 14 x 7 = 490 points

YEARS and DAYS hold one representative per class and every edge where a
class changes: the leap rule is arithmetic, one year per class suffices.
MONTHS does not partition: the month lengths are a TABLE in the unit, and a
typo in a table (September left out of the 30-day list) splits a class
that the requirement treats as one. One 30-day month in the space would
miss it; twelve rows cost little. A reviewer judges the TEST by these three
lines and the picture.

gregorian  the five calendars agree with the oracle in all 490 points:
           law 'disagreements == 0'.
four-only  1900 and 2100 accept the 29th of February: two '!' cells, named
           below the picture; law 'disagreements > 0'.

HOW TO READ THE GOOD   One block per year, side by side: rows are months,
columns the days of DAYS; 'Y' valid, '.' invalid, '!' the unit disagrees
with the oracle. Read the February row across the years: 29 is 'Y' only for
2000 and 2024; read the column 31 down: '.' in months 2, 4, 6, 9, 11. The
picture is a '##! verbatim' region (a cell's column is its day). Everything
else is exact, except the binding '((disagreements: N))', judged by the law.
______________________________________________________________________________
"""
import datetime
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
import hwut.test_writing_support.python.space_iterator as space_iterator

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.join(HERE, "..")
YEARS = [1900, 2000, 2023, 2024, 2100]
MONTHS = list(range(0, 14))
DAYS = [0, 1, 28, 29, 30, 31, 32]
CHOICE_DB = {"gregorian": "valid_date.awk", "four-only": "valid_date_4only.awk"}


def oracle(y, m, d):
    try:
        datetime.date(y, m, d)
        return 1
    except ValueError:
        return 0


def main(choice):
    space = list(space_iterator.do([YEARS, MONTHS, DAYS]))
    text = "".join("%d %d %d\n" % p for p in space)
    out = subprocess.run(["awk", "-f", os.path.join(UNIT, CHOICE_DB[choice])],
                         input=text, capture_output=True, text=True, check=True).stdout
    unit = dict(((int(y), int(m), int(d)), int(v))
                for y, m, d, v in (line.split() for line in out.splitlines()))
    wrong = [p for p in space if unit[p] != oracle(*p)]

    def cell(p):
        return "!" if p in wrong else ("Y" if unit[p] else ".")

    print("unit:   ../%s        oracle: datetime.date" % CHOICE_DB[choice])
    print("basis:  YEARS  %s" % YEARS)
    print("        MONTHS %s" % MONTHS)
    print("        DAYS   %s" % DAYS)
    print("space:  %d x %d x %d = %d points" % (len(YEARS), len(MONTHS), len(DAYS), len(space)))
    print("cells:  'Y' valid   '.' invalid   '!' unit disagrees with the oracle")
    print()
    print("##! verbatim")
    print(("      " + "".join("  %-21s" % y for y in YEARS)).rstrip())
    print("  d:  " + "".join("  %-21s" % "".join("%3d" % d for d in DAYS) for _ in YEARS))
    for m in MONTHS:
        print("  m%-2d " % m + "".join("  " + "".join("%3s" % cell((y, m, d)) for d in DAYS)
                                     for y in YEARS))
    print("####")
    print()
    o_valid = sum(1 for p in space if oracle(*p))
    print("valid: %d (calendar: %d)   invalid: %d (calendar: %d)"
          % (sum(unit.values()), o_valid, len(space) - sum(unit.values()), len(space) - o_valid))
    for y, m, d in wrong:
        print("!! %04d-%02d-%02d: unit says %s, the calendar says %s"
              % (y, m, d, "valid" if unit[(y, m, d)] else "invalid",
                 "valid" if oracle(y, m, d) else "invalid"))
    print("points that differ from the calendar: ((disagreements: %d)) of %d   law == 0   %s"
          % (len(wrong), len(space), "kept" if not wrong else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
