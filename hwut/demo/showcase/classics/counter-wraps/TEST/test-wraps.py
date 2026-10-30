#! /usr/bin/env python3
# @hwut {
#     title    = "Counter wraps (Boeing 787 2015, GPS week 2019, Y2K): a fixed-width counter runs out, time runs backwards"
#     choices {
#         boeing787-2015 { features = ["wrap-tabled", "gcu-wrap-named"]
#                          tolerance { constraints = ["backwards > 0"] } }
#         gps-week-2019  { features = ["wrap-tabled", "gps-wrap-named"]
#                          tolerance { constraints = ["backwards > 0"] } }
#         y2k-1999       { features = ["wrap-tabled", "y2k-wrap-named"]
#                          tolerance { constraints = ["backwards > 0"] } }
#         widened        { features = ["wrap-tabled", "time-monotonic"]
#                          tolerance { constraints = ["backwards == 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  what three fixed-width time counters decode, sample by sample,
         around the moment each one runs out of bits

HISTORY  One shape, three times:
  * Boeing 787 (FAA airworthiness directive 2015-09-07): the generator
    control units count time in centiseconds in a signed 32-bit integer.
    After 2^31 cs = 248.55 days of continuous power the counter overflows,
    and all four GCUs go into fail-safe at once: the aircraft loses its AC
    electric power. The directive's remedy until the software fix: switch
    the power off before 248 days.
  * GPS week number: the broadcast week is 10 bits wide and rolls over
    every 1024 weeks -- on 21/22 August 1999 and on 6/7 April 2019. A
    receiver that takes the week at face value jumps back by 19.6 years.
  * Y2K: a year stored as two digits; after 99 comes 00, read as 1900.

REQUIREMENT  The time a counter decodes never runs backwards: every later
             sample decodes to a later (or equal) time than the one before.

THE UNIT  '../counters.c', C, compiled per run: it stores a true value
into the counter as the device does and prints the raw counter and what it
decodes. WIDE=0 is the counter as deployed (int32 centiseconds, 10-bit week,
two-digit year); WIDE=1 the widened one (int64, 13-bit week as in the
modernised CNAV message, four digits).

WHAT THE TEST PRINTS  Per counter a table in '##! verbatim', one row per
sample around its wrap: the true time, the raw counter, the decoded time,
and '<- BACKWARDS' where the decoded time is earlier than the row before
('fail-safe' where the GCU counter is negative). Then the count.

CHOICES
    boeing787-2015  the GCU counter, deployed: the row after 2^31 cs
                    decodes to minus 248 days.
    gps-week-2019   the GPS week, deployed: 6 April 2019 decodes to
                    21 August 1999.
    y2k-1999        the two-digit year, deployed: 2000 decodes to 1900.
    widened         all three, widened: nothing runs backwards.

HOW TO READ THE GOOD  All is exact. '((backwards: N))' counts the rows
marked BACKWARDS over the tables of the choice; law 'backwards > 0' for a
deployed counter -- the GOOD is the accepted violation report -- and
'backwards == 0' for the widened ones.
______________________________________________________________________________
"""
import datetime
import os
import subprocess
import sys
import tempfile

HERE      = os.path.dirname(os.path.abspath(__file__))
GPS_EPOCH = datetime.date(1980, 1, 6)
CS_PER_DAY = 100 * 86400

#  The samples: kind -> list of (label of the true time, true value).
GCU_SAMPLE_LIST = [("%s" % label, value) for label, value in [
    ("day   0",                  0),
    ("day 100",                  100 * CS_PER_DAY),
    ("day 248",                  248 * CS_PER_DAY),
    ("2^31 cs - 1 s",            2**31 - 100),
    ("2^31 cs - 1 cs",           2**31 - 1),
    ("2^31 cs",                  2**31),
    ("2^31 cs + 1 s",            2**31 + 100),
    ("day 249",                  249 * CS_PER_DAY),
    ("day 300",                  300 * CS_PER_DAY)]]
GPS_WEEK_LIST   = [0, 1022, 1023, 1024, 1025, 2046, 2047, 2048, 2049]
Y2K_YEAR_LIST   = [1997, 1998, 1999, 2000, 2001, 2002]
CHOICE_DB = {"boeing787-2015": (0, ("gcu",)),
             "gps-week-2019":  (0, ("gps",)),
             "y2k-1999":       (0, ("y2k",)),
             "widened":        (1, ("gcu", "gps", "y2k"))}


def decoded_of(wide, line_list):
    """
    RETURN: list of (raw counter, decoded), one per input line, as
            '../counters.c' built with WIDE='wide' answers them.
    """
    with tempfile.TemporaryDirectory() as build:
        exe = os.path.join(build, "counters")
        subprocess.check_call(["gcc", "-O1", "-Wall", "-Werror", "-DWIDE=%d" % wide,
                               "-o", exe, os.path.join(HERE, "..", "counters.c")])
        out = subprocess.run([exe], input="".join(l + "\n" for l in line_list),
                             capture_output=True, text=True, check=True).stdout
    return [tuple(int(x) for x in line.split()[1:]) for line in out.splitlines()]


def table(kind, wide):
    """
    RETURN: [0] list of str, the table's rows for counter 'kind';
            [1] int, the number of rows whose decoded time is earlier than
                the row before.
    """
    if kind == "gcu":
        sample_list = GCU_SAMPLE_LIST
        head = "true time of power   raw counter (cs)   decoded uptime"
    elif kind == "gps":
        sample_list = [((GPS_EPOCH + datetime.timedelta(weeks=w)).isoformat(), w)
                       for w in GPS_WEEK_LIST]
        head = "true date   raw week   decoded date"
    else:
        sample_list = [(str(y), y) for y in Y2K_YEAR_LIST]
        head = "true year   raw field   decoded year"
    pair_list = decoded_of(wide, ["%s %d" % (kind, v) for _, v in sample_list])
    row_list, backwards, last = [head], 0, None
    for (label, _), (raw, decoded) in zip(sample_list, pair_list):
        mark = ""
        if last is not None and decoded < last:
            mark, backwards = "   <- BACKWARDS", backwards + 1
        if kind == "gcu":
            if raw < 0: mark += " (fail-safe)"
            text = "%-20s %18d   %10.2f days" % (label, raw, decoded / 86400.0)
        elif kind == "gps":
            text = "%-11s %8d   %s" % (label, raw,
                                       (GPS_EPOCH + datetime.timedelta(weeks=decoded)).isoformat())
        else:
            text = "%-11s %9s   %d" % (label, ("%02d" % raw) if not wide else raw, decoded)
        row_list.append(text + mark)
        last = decoded
    return row_list, backwards


TITLE_DB = {"gcu": "BOEING 787 GENERATOR CONTROL UNIT, centiseconds of power",
            "gps": "GPS WEEK NUMBER, weeks since 1980-01-06",
            "y2k": "YEAR FIELD"}


def main(choice):
    """RETURN: int, 0 once every table of 'choice' is printed."""
    wide, kind_tuple = CHOICE_DB[choice]
    print("counters: %s   (counters.c WIDE=%d)" % ("widened" if wide else "as deployed", wide))
    total = 0
    for kind in kind_tuple:
        row_list, backwards = table(kind, wide)
        print()
        print("%s" % TITLE_DB[kind])
        print("##! verbatim")
        for row in row_list: print(row)
        print("####")
        print("rows running backwards: %d" % backwards)
        total += backwards
    print()
    print("decoded time ran backwards ((backwards: %d))   law == 0   %s"
          % (total, "kept" if total == 0 else "BROKEN"))
    return 0


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
