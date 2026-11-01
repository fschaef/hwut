#! /usr/bin/env python3
# @hwut {
#     title    = "Year 2038: a clock in signed 32-bit seconds, across 2038-01-19 03:14:07 UTC"
#     choices {
#         int32 { features = ["boundary-table", "wrap-named"]
#                 tolerance { constraints = ["wrong > 0"] } }
#         int64 { features = ["boundary-table", "time-continues", "calendar-swept"]
#                 tolerance { constraints = ["wrong == 0", "sweep_wrong == 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the UTC instant a seconds-since-1970 clock shows for boundary
         instants around 2^31 - 1 and a calendar sweep
HISTORY  Unix time counts seconds since 1970-01-01 00:00:00 UTC. Where
time_t is a signed 32-bit integer, the last second it can hold is 2^31 - 1
= 2147483647, i.e. 2038-01-19 03:14:07 UTC; one second later it wraps to
-2^31, which reads as 1901-12-13 20:45:52. It is the best-known date bug
still ahead of us; programs that compute dates far ahead (30-year loans,
certificates, timeouts of 'about a billion seconds') met it early. Linux
added 64-bit time system calls for 32-bit architectures in kernel 5.6
(2020), and glibc 2.34 lets 32-bit programs choose '_TIME_BITS=64'.

REQUIREMENT  A clock advanced by d seconds shows the instant d seconds
             later, as UTC, also past 2038-01-19 03:14:07 -- time never
             runs backwards.

THE UNIT  '../clock.c': seconds in a variable of type TIME_T, advanced by a
delta, shown as UTC by its own calendar routine (so the libc's gmtime plays
no part). -DTIME_T=int32_t or int64_t; -fwrapv lets the 32-bit addition
wrap as the CPU does. The truth is Python's datetime (unbounded integers).

THE TABLE  rows chosen around the boundary: the epoch, 1 s before it, a
billion seconds, then 03:14:04 .. 03:14:10 on 2038-01-19 second by second,
and the boundary second plus a minute, a day, a year; then far instants
reached by one big delta from the epoch -- before 1901, 2^32 s (2106),
the century days 2100-02-28/03-01, 2400-02-29, 9999-12-31 -- which a
delta truncated to 32 bit or a calendar century slip would get wrong.
THE SWEEP  1619 instants (Feb 28, Feb 29 where it exists, Mar 1, Dec 31 at
noon, 1902 .. 2400) through the clock, against Python's datetime -- an
independent oracle for the hand-written calendar: '((sweep_wrong: N))',
law 'sweep_wrong == 0' for int64.

CHOICES
    int32   the historical clock: at +1 s past 03:14:07 the seconds turn
            negative and the date jumps back to 1901; every later row too.
    int64   the same code with a 64-bit time_t: every row right.

HOW TO READ THE GOOD  Column 'clock says' against 'true UTC'; a wrong row
carries '!!' and the clock's raw seconds show the sign flip. The table is
'##! verbatim' (it is a picture of columns); everything is exact. Verdict:
'((wrong: N))' -- law 'wrong == 0' for int64, 'wrong > 0' for int32.
______________________________________________________________________________
"""
import datetime
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TYPE_DB = {"int32": "int32_t", "int64": "int64_t"}
EDGE = 2**31 - 1
ROWS = [("epoch", 0, 0), ("epoch - 1 s", 0, -1), ("10^9 s", 10**9, 0)] \
     + [("edge %+d s" % d, EDGE, d) for d in range(-3, 4)] \
     + [("edge + 1 min", EDGE, 60), ("edge + 1 day", EDGE, 86400), ("edge + 365 days", EDGE, 365 * 86400)]
EPOCH = datetime.datetime(1970, 1, 1)


def seconds_of(*ymd_hms):
    return int((datetime.datetime(*ymd_hms) - EPOCH).total_seconds())


ROWS += [("-2^31 - 1 s", 0, -2**31 - 1), ("2^32 s", 0, 2**32),
         ("2100-02-28 noon", 0, seconds_of(2100, 2, 28, 12)), ("2100-03-01 noon", 0, seconds_of(2100, 3, 1, 12)),
         ("2400-02-29 noon", 0, seconds_of(2400, 2, 29, 12)), ("9999-12-31 end", 0, seconds_of(9999, 12, 31, 23, 59, 59))]
# the calendar sweep: around every year's end and February, 1902 .. 2400
SWEEP = [seconds_of(y, m, d, 12) for y in range(1902, 2401)
         for m, d in ((2, 28), (2, 29), (3, 1), (12, 31))
         if not (m == 2 and d == 29 and not (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)))]


def run_unit(time_t, pairs):
    build = tempfile.mkdtemp(prefix="y2038-")
    try:
        exe = os.path.join(build, "clock")
        subprocess.run(["gcc", "-O2", "-fwrapv", "-Wall", "-Werror", "-DTIME_T=" + time_t,
                        "-o", exe, os.path.join(HERE, "..", "clock.c")], check=True)
        text = "".join("%d %d\n" % pair for pair in pairs)
        out = subprocess.run([exe], input=text, capture_output=True, text=True, check=True).stdout
        return [l.split(None, 1) for l in out.splitlines()]
    finally:
        shutil.rmtree(build, True)


def main(choice):
    result = run_unit(TYPE_DB[choice], [(s, d) for _, s, d in ROWS])
    print("clock: seconds since 1970-01-01 UTC in %s; boundary 2^31-1 = %d" % (TYPE_DB[choice], EDGE))
    print()
    print("##! verbatim")
    print("%-16s %13s  %-19s  %-19s  %s" % ("instant", "clock seconds", "true UTC", "clock says", "verdict (clock - true)"))
    wrong = 0
    for (label, start, delta), (seconds, shown) in zip(ROWS, result):
        true = (EPOCH + datetime.timedelta(seconds=start + delta)).strftime("%Y-%m-%d %H:%M:%S")
        ok = shown == true
        wrong += not ok
        off = int(seconds) - (start + delta)
        print("%-16s %13s  %-19s  %-19s  %s" % (label, seconds, true, shown, "ok" if ok else
                                                 "!! wrong, %+.1f years" % (off / (365.25 * 86400)) if off else "!! wrong"))
    print("####")
    print("(years of 365.25 days)")
    print("rows the clock gets wrong: ((wrong: %d)) of %d   law == 0   %s" % (wrong, len(ROWS), "kept" if not wrong else "BROKEN"))
    swept = run_unit(TYPE_DB[choice], [(0, d) for d in SWEEP])
    bad = [(d, shown) for d, (_, shown) in zip(SWEEP, swept)
           if shown != (EPOCH + datetime.timedelta(seconds=d)).strftime("%Y-%m-%d %H:%M:%S")]
    print("calendar sweep, Feb 28/29, Mar 1 and Dec 31 at noon of 1902 .. 2400 (%d instants),"
          " clock against Python's datetime:" % len(SWEEP))
    print("    wrong ((sweep_wrong: %d))   law == 0   %s; first: %s" % (len(bad), "kept" if not bad else "BROKEN", "%s shown as %s" % (
        (EPOCH + datetime.timedelta(seconds=bad[0][0])).strftime("%Y-%m-%d %H:%M:%S"), bad[0][1]) if bad else "none"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in TYPE_DB:
        print("choices: %s" % ", ".join(TYPE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
