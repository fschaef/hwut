#! /usr/bin/env python3
# @hwut {
#     title    = "Vancouver Stock Exchange index (1982-83): truncated to three decimals on every trade, it lost half its value"
#     choices {
#         truncated-1982 { features = ["months-tabled", "drift-named"]
#                          tolerance { constraints = ["deviation > 1"] } }
#         rounded        { features = ["months-tabled", "drift-bounded"]
#                          tolerance { constraints = ["deviation <= 1"] } }
#     }
#     caps { timeout_sec = 60 }
# }
"""
______________________________________________________________________________
SUBJECT  the published index month by month over 22 months of trading,
         against the same index computed exactly, from the same trades

HISTORY  The Vancouver Stock Exchange started a new index in January 1982
at 1000.000. It was recomputed after every trade -- some 3000 times a day
-- and each time cut to three decimals: TRUNCATED, not rounded. Every
recomputation lost on average half a thousandth. By November 1983 the
index stood at 524.811, although the market had not fallen; recomputed
correctly it was 1098.892.

REQUIREMENT  The published index stays within 1 point of the index
             computed exactly from the same trades.

THE UNIT  '../index.py': one trade's step on the index in thousandths --
truncated (as in Vancouver), rounded, and an exact track with nine more
decimals. Integers throughout.

THE MODEL  23 months (January 1982 to November 1983) of 21 trading days,
3000 trades a day. Each trade moves the index by k ppm, k drawn in
[-150, +150] by DeterministicStream(1982), the same trades for every track.
The model knows nothing of Vancouver's actual trades: it shows the
mechanism, not the history -- its exact index wanders where the stream
takes it, and the truncated one loses about 0.0005 per trade, some 30
points a month.

WHAT THE TEST PRINTS  A table in '##! verbatim', one row per month end:
the exact index, the published one, their difference, and a bar of the
difference ('-' per 20 points below exact). Then the final deviation.

CHOICES
    truncated-1982  published truncated: the index falls ever further
                    below the exact one, by a fixed share each month.
    rounded         published rounded: the differences are a random walk
                    of rounding errors, a few tenths at most.

HOW TO READ THE GOOD  All is exact: the trades are the stream's, the
arithmetic integers. '((deviation: X))' is |published - exact| at the end,
in points; law 'deviation > 1' for the truncated index -- its GOOD is the
accepted violation report -- and 'deviation <= 1' for the rounded one.
______________________________________________________________________________
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
from hwut.test_writing_support.python.deterministic_random import DeterministicStream  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import index                                                     # noqa: E402

MONTH_N, DAY_N, TRADE_N = 23, 21, 3000
START = 1000000                                     # 1000.000 in thousandths
CHOICE_DB = {"truncated-1982": index.step_truncated, "rounded": index.step_rounded}


def month_label(m):
    """RETURN: str, 'YYYY-MM' of month 'm' counted from 0 = January 1982."""
    return "%d-%02d" % (1982 + m // 12, m % 12 + 1)


def main(choice):
    """RETURN: int, 0 once the table and the deviation are printed."""
    step = CHOICE_DB[choice]
    stream = DeterministicStream(1982)
    exact_e, published = START * index.EXTRA, START
    print("index published %s, every trade; 3000 trades a day, 21 days a month" % choice)
    print("##! verbatim")
    print("month     exact      published   published-exact")
    for month in range(MONTH_N):
        for _ in range(DAY_N * TRADE_N):
            k = stream.next_int(-150, 150)
            exact_e   = index.step_exact(exact_e, k)
            published = step(published, k)
        exact = exact_e / index.EXTRA / 1000.0
        shown = published / 1000.0
        diff  = shown - exact
        bar   = "-" * int(-diff // 20) if diff < 0 else ""
        print("%s  %9.3f  %9.3f  %+9.3f  %s" % (month_label(month), exact, shown, diff, bar))
    print("####")
    deviation = abs(published * index.EXTRA - exact_e) / index.EXTRA / 1000.0
    print("|published - exact| at the end ((deviation: %.3f)) points   law <= 1   %s"
          % (deviation, "kept" if deviation <= 1 else "BROKEN"))
    return 0


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
