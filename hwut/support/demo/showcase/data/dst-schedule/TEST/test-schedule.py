#! /usr/bin/env python3
#
# @hwut {
#     title   = "Job schedule: local wall-clock times across DST and month ends"
#     choices {
#         zoneinfo { features = ["wall-time", "one-per-day", "month-end"]
#                    tolerance { constraints = ["breaches == 0"] } }
#         gnu-date { features = ["violation-shown"]
#                    tolerance { constraints = ["breaches > 0"] } }
#     }
# }
#
"""
______________________________________________________________________________
SUBJECT  the run times a scheduler (../schedule.py or ../schedule.sh) computes
         for 'daily at 02:30' and 'monthly on the 31st' across the 2025 DST
         changes and month ends
REQUIREMENT. A job scheduled 'daily at 02:30 Europe/Berlin' and 'monthly on
the 31st':
    R1  runs at 02:30 local wherever 02:30 exists; on the day the clock jumps
        from 02:00 to 03:00 it runs at 03:00, the first minute after the gap;
    R2  runs exactly once per local day -- on the day 02:30 happens twice,
        at the first one (CEST) -- so two runs are 23 to 25 h apart;
    R3  'monthly on the 31st' clamps to the month's last day: 29 Feb 2024,
        30 Apr, ... -- never spills into the next month.

CHOICES -- two implementations, the same questions:
    zoneinfo   ../schedule.py (Python zoneinfo): all three hold
               (law: breaches == 0).
    gnu-date   ../schedule.sh (bash, GNU date): 30 Mar 2025 02:30 is an
               'invalid date' (no run that day: R1, R2), on 26 Oct it takes
               the second 02:30 (CET), and '31 Jan +1 month' is 2 March (R3)
               (law: breaches > 0).

HWUT CONCEPT. Plain exact text: calendars are deterministic, and this is
where exactness pays -- every expected wall time is written down in the
test (EXPECTED_DB), not derived from a library that might share the bug.
The tool's stderr is captured and printed in the table ('tool said: ...'),
so a refusal is part of the accepted picture instead of a stain. The
number of BROKEN rows is a constraint binding '((breaches: n))', judged by
the choice's law.

READING THE GOOD. Two calendars mark the days the UTC offset changed ('*')
and the days the tool failed ('!'). In the tables, each run shows local
time, UTC, the hours since the previous run, and 'ok' or what is wrong.
______________________________________________________________________________
"""
import calendar
import os
import subprocess
import sys
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
TOP  = os.path.join(HERE, "..")
ZONE = "Europe/Berlin"
TOOL_DB = {"zoneinfo": [os.path.join(TOP, "schedule.py")],
           "gnu-date": [os.path.join(TOP, "schedule.sh")]}
# The requirement, written out for the days that matter (R1, R2).
EXPECTED_DB = {"2025-03-30": "03:00 CEST", "2025-10-26": "02:30 CEST"}
breach_n = 0                                    # rows with a BROKEN verdict


def tool(choice, *args):
    """RETURN: (runs, complaints): runs as lists of fields, stderr lines."""
    p = subprocess.run(TOOL_DB[choice] + list(args), capture_output=True, text=True,
                       env=dict(os.environ, LC_ALL="C"))
    return [l.split() for l in p.stdout.splitlines()], p.stderr.splitlines()


def daily_table(choice, first, n, mark_db):
    global breach_n
    runs, complaints = tool(choice, "daily", ZONE, first, str(n), "02:30")
    by_day = {r[0]: r for r in runs}
    print("%-14s %-16s %-18s %-8s %s" % ("day", "local run", "UTC", "since", "verdict"))
    prev = prev_offset = None
    for k in range(n):
        day = (date.fromisoformat(first) + timedelta(days=k)).isoformat()
        want = EXPECTED_DB.get(day, None)
        r = by_day.get(day)
        label = datetime.fromisoformat(day).strftime("%a %d %b")
        if r is None:
            mark_db[day] = "!"
            breach_n += 1
            print("%-14s %-16s %-18s %-8s %s" % (label, "(no run)", "-", "-", "BROKEN: no run this day"))
            continue
        local = "%s %s" % (r[1], r[2])
        utc = datetime.strptime(r[4], "%Y-%m-%dT%H:%MZ")
        since = "-" if prev is None else "%.1f h" % ((utc - prev).total_seconds() / 3600)
        verdict = "ok"
        if want and local != want:
            verdict = "BROKEN: want %s" % want
        elif not want and r[1] != "02:30":
            verdict = "BROKEN: want 02:30"
        elif prev is not None and not 23 <= (utc - prev).total_seconds() / 3600 <= 25:
            verdict = "BROKEN: gap"
        if prev_offset is not None and r[3] != prev_offset:
            mark_db.setdefault(day, "*")
        prev_offset = r[3]
        breach_n += verdict != "ok"
        print("%-14s %-16s %-18s %-8s %s" % (label, local + " " + r[3], r[4], since, verdict))
        prev = utc
    for line in complaints:
        print("  tool said: %s" % line)


def monthly_table(choice):
    global breach_n
    runs, complaints = tool(choice, "monthly", ZONE, "2024-01", "14", "31")
    print("%-10s %-12s %-12s %s" % ("month", "wanted", "tool", "verdict"))
    year, month = 2024, 1
    for k in range(14):
        want = date(year, month, calendar.monthrange(year, month)[1]).isoformat()
        got = runs[k][0] if k < len(runs) else "(none)"
        print("%-10s %-12s %-12s %s" % (date(year, month, 1).strftime("%b %Y"), want, got,
                                        "ok" if got == want else "BROKEN"))
        breach_n += got != want
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    for line in complaints:
        print("  tool said: %s" % line)


def calendars(mark_db):
    """Prints March and October 2025 side by side, marks after the day."""
    def lines(year, month):
        out = ["%s %d" % (calendar.month_name[month], year), "Mo  Tu  We  Th  Fr  Sa  Su "]
        for week in calendar.Calendar().monthdayscalendar(year, month):
            cells = []
            for d in week:
                if d == 0:
                    cells.append("    ")
                else:
                    mark = mark_db.get("%04d-%02d-%02d" % (year, month, d), " ")
                    cells.append("%2d%s " % (d, mark))
            out.append("".join(cells))
        return out
    left, right = lines(2025, 3), lines(2025, 10)
    while len(left) < len(right): left.append("")
    while len(right) < len(left): right.append("")
    print("##! verbatim")
    for a, b in zip(left, right):
        print("|  %-28s|  %-28s|" % (a, b))
    print("####")


def main(choice):
    mark_db = {}
    print("daily at 02:30 %s -- spring forward (02:00 -> 03:00 on 30 Mar 2025)" % ZONE)
    print("rule: no 02:30 that day -> run at 03:00; one run per day, 23 to 25 h apart")
    daily_table(choice, "2025-03-27", 6, mark_db)
    print("daily at 02:30 %s -- fall back (03:00 -> 02:00 on 26 Oct 2025)" % ZONE)
    print("rule: two 02:30s that day -> run at the first (CEST); one run per day, 23 to 25 h apart")
    daily_table(choice, "2025-10-23", 6, mark_db)
    print("calendar: '*' the UTC offset changed, '!' the tool gave no run")
    calendars(mark_db)
    print("monthly on the 31st, Jan 2024 .. Feb 2025 (2024 is a leap year)")
    print("rule: a month without a 31st -> its last day, never the next month")
    monthly_table(choice)
    print("rows BROKEN ((breaches: %d))   law == 0   %s" % (breach_n, "kept" if breach_n == 0 else "BROKEN"))


if len(sys.argv) < 2 or sys.argv[1] not in TOOL_DB:
    print("choices: %s" % ", ".join(TOOL_DB))
    sys.exit(1)
main(sys.argv[1])
print("<hwut-end>")
