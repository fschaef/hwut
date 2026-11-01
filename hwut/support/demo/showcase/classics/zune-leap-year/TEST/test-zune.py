#! /usr/bin/env python3
# @hwut {
#     title    = "Zune 30, 31 Dec 2008: the year loop that never ends on day 366 of a leap year"
#     choices {
#         shipped-2008 { features = ["loop-traced", "edge-days", "hang-named", "hwut-kills-it"]
#                        tolerance { constraints = ["hangs > 0", "wrong == 0"] } }
#         fixed        { features = ["loop-traced", "edge-days", "every-day-converts"]
#                        tolerance { constraints = ["hangs == 0", "wrong == 0"] } }
#     }
#     caps { timeout_sec = 60 }
# }
"""
______________________________________________________________________________
SUBJECT  the date ConvertDays() of the Zune RTC firmware gives for every day
         number of chosen years -- or that it hangs
HISTORY  On 31 December 2008 every Microsoft Zune 30 GB player froze at
boot. The cause, quickly found in the published driver source of the
Freescale MC13783 power-management chip, was ConvertDays() in the
real-time-clock code: a loop that subtracts whole years from a day count.
On day 366 of a leap year (2008 was one) neither branch changes the count,
and the loop spins forever. Microsoft's advice was to wait: on 1 January
2009, after the battery ran down, the player worked again.

REQUIREMENT  ConvertDays() turns every day number (1 = 1980-01-01) into its
             date, and it terminates for every day -- in particular for the
             last day of a leap year.

THE UNIT  '../rtc.c', C: the year loop as shipped (FIXED=0), or with
'else break;' when a leap year has exactly 366 days left (FIXED=1). With
argument 'trace' it prints one line per loop iteration: 'loop n year y
days d'.

HOW NON-TERMINATION IS DECIDED  The loop's whole state is (year, days); the
loop is deterministic. So when a state comes again, the loop is in a cycle
and cannot end -- a proof, not a timeout. The test reads the trace and stops
the process at the first repeated state. As a second, independent witness
it shows what HWUT ITSELF says: it builds a one-test device tree in its
scratch directory (TMPDIR), accepts the device test on the fixed firmware,
and runs it on the choice's firmware with 'caps { timeout_sec = 1 }'. The
procsitter's verdict, 'killed', and its HINTS line are printed (the time it
ran is cut off: it varies).

WHAT THE TEST PRINTS
  1. THE LOOP TRACE for day 10593 = 2008-12-31 (the iterations of the
     middle years elided, their number printed).
  2. EDGE DAYS 1980 .. 2040: per year Dec 30, Dec 31, Jan 1 of the next
     year and, in leap years, Feb 29 -- each converted in its own process.
     '.' right date, 'x' wrong date, 'H' hangs, '-' no such day.
  3. EVERY DAY of 2000 (a leap century), 2008, 2009 and 2100 (a common
     century), month by month: one cell per month -- '.' every day of it
     right, 'x' a wrong date, 'H' a hang; each wrong day is listed. The edge
     days alone would not see a wrong month table (June 31 / July 30 keeps
     the year's sum); every day does.
  4. HWUT'S VERDICT on the device test.

CHOICES
    shipped-2008  hangs on Dec 31 of EVERY leap year -- 1980 was the first,
                  but devices of that era were not built yet; all other
                  days are right (law 'wrong == 0' too). hwut kills it.
    fixed         every edge day right, no hang; hwut says ok.

HOW TO READ THE GOOD  In the trace, the line marked 'SAME STATE' is the
proof. In the strip the 'H' column pattern is every fourth year; in the
month table an 'H' stands only under December of the leap years. The
pictures stand in '##! verbatim'; all is exact. Bindings '((hangs: N))'
and '((wrong: N))' count DISTINCT days (2000-12-31 and 2008-12-31 stand in
both the edge strip and the month table, and count once): laws 'hangs > 0' for the shipped loop, 'hangs == 0'
for the fixed one, 'wrong == 0' for both.
______________________________________________________________________________
"""
import datetime
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
CHOICE_DB = {"shipped-2008": 0, "fixed": 1}
ORIGIN = datetime.date(1980, 1, 1)
YEARS = list(range(1980, 2041))


def build(fixed, scratch):
    exe = os.path.join(scratch, "zune-%d" % fixed)
    subprocess.run(["gcc", "-O2", "-Wall", "-Werror", "-DFIXED=%d" % fixed, "-o", exe,
                    os.path.join(HERE, "..", "rtc.c")], check=True)
    return exe


def day_number(date):
    return (date - ORIGIN).days + 1


def convert(exe, day):
    """RETURN: (date text or None for a hang, [trace lines])."""
    p = subprocess.Popen([exe, "trace"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    p.stdin.write("%d\n" % day)
    p.stdin.close()
    seen, trace = set(), []
    for line in p.stdout:
        trace.append(line.rstrip())
        if line.startswith("date"):
            p.wait()
            return line.split()[1], trace
        state = tuple(line.split()[3::2])          # (year, days)
        if state in seen or len(trace) > 1000:
            p.kill()
            p.wait()
            return None, trace
        seen.add(state)
    p.wait()
    return "?", trace


def convert_many(exe, day_list):
    """RETURN: {day: date text or None for a hang} -- one process for many
               days; after a hang (repeated loop state) a fresh process."""
    result, p = {}, None
    for day in day_list:
        if p is None:
            p = subprocess.Popen([exe, "trace"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        p.stdin.write("%d\n" % day)
        p.stdin.flush()
        seen = set()
        while True:
            line = p.stdout.readline()
            if line.startswith("date"):
                result[day] = line.split()[1]
                break
            state = tuple(line.split()[3::2])
            if not line or state in seen or len(seen) > 1000:
                result[day] = None
                p.kill()
                p.wait()
                p = None
                break
            seen.add(state)
    if p is not None:
        p.stdin.close()
        p.wait()
    return result


def hwut_verdict(firmware, fixed_firmware):
    """RETURN: the lines hwut prints about a device test run on 'firmware',
               its GOOD accepted on 'fixed_firmware'."""
    tree = tempfile.mkdtemp(prefix="device-tree-")
    try:
        os.makedirs(os.path.join(tree, "device", "TEST"))
        with open(os.path.join(tree, "hwut-root.conf"), "w") as fh:
            fh.write('hwut { language-setup { bash { extensions = [".sh"] interpreter = "bash" } } }\n')
        app = os.path.join(tree, "device", "TEST", "test-boot.sh")
        with open(app, "w") as fh:
            fh.write('#! /bin/bash\n'
                     '# @hwut {\n'
                     '#     title   = "the player boots on 2008-12-31"\n'
                     '#     choices { new-years-eve { caps { timeout_sec = 1 } } }\n'
                     '# }\n'
                     'echo %d | ../firmware\n'
                     'echo "<hwut-end>"\n' % day_number(datetime.date(2008, 12, 31)))
        os.chmod(app, 0o755)
        shutil.copy(fixed_firmware, os.path.join(tree, "device", "firmware"))
        quiet = dict(capture_output=True, text=True)
        subprocess.run(["hwut.play", "test-boot.sh", "new-years-eve", "--plain"],
                       cwd=os.path.dirname(app), **quiet)
        subprocess.run(["hwut.accept", "test-boot.sh", "--force"], cwd=os.path.dirname(app), **quiet)
        shutil.copy(firmware, os.path.join(tree, "device", "firmware"))
        out = subprocess.run(["hwut.run", "--plain"], cwd=tree, **quiet).stdout
    finally:
        shutil.rmtree(tree, True)
    result = []
    for line in out.splitlines():                  # drop what varies: times, '||n'
        if line.startswith("END"):
            result.append(" ".join(line.split()[:-1]))
        elif "cap exceeded" in line:
            result.append(line.strip().split(", ran")[0] + ")")
        elif line.startswith("RESULTS"):
            result.append(re.match(r"RESULTS: \d+ ok, \d+ fail", line).group(0))
    return result


def main(choice):
    scratch = tempfile.mkdtemp(prefix="zune-")
    try:
        exe = build(CHOICE_DB[choice], scratch)
        fixed_exe = build(1, scratch)
        print("firmware: rtc.c FIXED=%d (%s)   day 1 = 1980-01-01" % (CHOICE_DB[choice], choice))
        print()
        new_years_eve = day_number(datetime.date(2008, 12, 31))
        date, trace = convert(exe, new_years_eve)
        trace = [l for l in trace if l.startswith("loop")]
        print("1. THE LOOP TRACE for day %d = 2008-12-31" % new_years_eve)
        print("##! verbatim")
        seen = {}
        for i, line in enumerate(trace):
            if 2 <= i < len(trace) - 4:
                if i == 2:
                    print("   ... %d iterations elided, one per year ..." % (len(trace) - 6))
                continue
            note = ""
            if line.startswith("loop"):
                state = tuple(line.split()[3::2])
                if state in seen:
                    note = "   <- SAME STATE as loop %s: the loop cannot end" % seen[state]
                seen[state] = line.split()[1]
            print("   " + line + note)
        print("   => " + ("no date: the player hangs here" if date is None else "date " + date))
        print("####")
        print()

        hangs = wrong = 0
        hang_days, wrong_days = set(), set()
        rows = {"Dec 30": [], "Dec 31": [], "Jan 1+": [], "Feb 29": []}
        for y in YEARS:
            days = {"Dec 30": datetime.date(y, 12, 30), "Dec 31": datetime.date(y, 12, 31),
                    "Jan 1+": datetime.date(y + 1, 1, 1)}
            leap = y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)
            if leap:
                days["Feb 29"] = datetime.date(y, 2, 29)
            for name in rows:
                if name not in days:
                    rows[name].append("-")
                    continue
                got, _ = convert(exe, day_number(days[name]))
                if got is None:
                    hangs += 1
                    hang_days.add(days[name])
                    rows[name].append("H")
                elif got != days[name].isoformat():
                    wrong += 1
                    wrong_days.add(days[name])
                    rows[name].append("x")
                else:
                    rows[name].append(".")
        print("2. EDGE DAYS, one column per year (Jan 1+ = Jan 1 of the next year)")
        print("##! verbatim")
        print("year     " + "".join(str(y)[:4].ljust(10) if y % 10 == 0 else "" for y in YEARS).rstrip())
        for name, cells in rows.items():
            print("%-8s %s" % (name, "".join(cells)))
        print("####")
        print("('.' right  'x' wrong date  'H' hangs  '-' no such day)")
        print("edge days: hang %d   wrong %d" % (hangs, wrong))
        print()
        print("3. EVERY DAY of four years, one cell per month")
        sweep_years = (2000, 2008, 2009, 2100)
        all_days = [datetime.date(y, 1, 1) + datetime.timedelta(n) for y in sweep_years
                    for n in range((datetime.date(y + 1, 1, 1) - datetime.date(y, 1, 1)).days)]
        got_db = convert_many(exe, [day_number(d) for d in all_days])
        bad_list, cell_db = [], {}
        for d in all_days:
            got = got_db[day_number(d)]
            mark = "H" if got is None else "x" if got != d.isoformat() else "."
            if mark != ".":
                bad_list.append((d, got))
            old = cell_db.get((d.year, d.month), ".")
            cell_db[(d.year, d.month)] = max(old, mark, key=".xH".index)
        sweep_hangs = sum(1 for _, got in bad_list if got is None)
        sweep_wrong = len(bad_list) - sweep_hangs
        print("##! verbatim")
        print("year  J F M A M J J A S O N D")
        for y in sweep_years:
            print("%d  %s" % (y, " ".join(cell_db[(y, m)] for m in range(1, 13))))
        print("####")
        print("(a month's cell: '.' every day right, 'H' a day hangs, 'x' a day converted wrongly)")
        hung = [d.isoformat() for d, got in bad_list if got is None]
        print("all days: %d   hang %d%s   wrong %d%s" % (len(all_days), sweep_hangs, " (%s)" % ", ".join(hung) if hung else "",
                                                     sweep_wrong, "".join("  %s -> %s" % (d.isoformat(), got)
                                                                          for d, got in bad_list if got is not None)))
        for d, got in bad_list:
            (hang_days if got is None else wrong_days).add(d)
        print("in total, distinct days (a day in both sections counts once):")
        print("    days that hang ((hangs: %d))   law == 0   %s" % (len(hang_days), "kept" if not hang_days else "BROKEN"))
        print("    days converted wrongly ((wrong: %d))   law == 0   %s" % (len(wrong_days), "kept" if not wrong_days else "BROKEN"))
        print()
        print("4. HWUT'S VERDICT: device test accepted on the fixed firmware, run on this one,")
        print("   caps { timeout_sec = 1 }")
        for line in hwut_verdict(exe, fixed_exe):
            print("   " + line)
    finally:
        shutil.rmtree(scratch, True)


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
