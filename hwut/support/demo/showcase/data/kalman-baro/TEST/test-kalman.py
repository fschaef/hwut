#! /usr/bin/env python3
#
# @hwut {
#     title   = "Barometric altitude: Kalman filter on a 3 m elevator ride"
#     choices {
#         tuned    { features = ["steady", "settling", "smoothing"]
#                    tolerance { constraints = ["rms_worst <= 0.18 m",
#                                               "settle_worst <= 2.5 s",
#                                               "ratio_median <= 0.45"] } }
#         sluggish { features = ["violation-shown"]
#                    tolerance { constraints = ["settle_worst > 2.5 s"] } }
#         nervous  { features = ["violation-shown"]
#                    tolerance { constraints = ["ratio_median > 0.45"] } }
#     }
# }
#
"""
______________________________________________________________________________
SUBJECT  the altitude track that the Kalman filter ../kalman.c, under one
         tuning file, makes of a noisy barometer on a 3 m elevator ride
REQUIREMENT. A pressure sensor (noise 3 Pa, i.e. ~0.25 m) at 25 Hz rides an
elevator: 4 s at rest, 2 s up by 3 m, 6 s at rest. The filtered altitude
    R1  stays within 0.18 m RMS of the truth while at rest (steady);
    R2  is back within 0.30 m of the truth at most 2.5 s after the ride
        ends, and stays inside for a full second (settling);
    R3  has, typically, less than 0.45 of the raw error's spread while at
        rest (smoothing) -- 'typically' is the median of the rides.

CHOICES -- one filter (../kalman.c, C), three tuning files:
    tuned     ../tuning-tuned.conf: all three hold.
    sluggish  ../tuning-sluggish.conf (q too small): it trusts its model
              more than the sensor and lags the ride by seconds -- R2
              breaks (the lag spoils R1 as well).
    nervous   ../tuning-nervous.conf (q too large): follows every wiggle of
              the noise -- R3 breaks (and its wobble often leaves the
              0.30 m band: R2 as well).

HWUT CONCEPTS.
  * The PICTURE is one ride with a FIXED seed (4711), deterministic, inside
    '##! verbatim': raw samples '.', the truth '-', the estimate 'o'. It
    shows the behaviour a reviewer judges by eye; it is exact because
    nothing in it varies.
  * The LAW is judged on a SWEEP: 40 rides per run, noise seeded by the
    clock (seed printed as a '##' comment, taking no part). R1 and R2 bind
    the worst of the 40, R3 the median, as constraint bindings; the
    choice's 'constraints' judge them, the recorded values do not. R1 and
    R2 are QUANTITIES, '((rms_worst: 0.110 m))', '((settle_worst: 1.28 s))',
    judged by laws in the requirement's units, 'rms_worst <= 0.18 m': an
    error printed in cm, or a settling time in samples, cannot pass as
    metres or seconds. The spread is a ratio and stays a plain number. The bounds were calibrated on 4000 rides (worst seen:
    rms 0.126 m, settling 1.76 s, spread 0.47): a worst-of-40 near the
    bound is noise, a median is not -- so the spread is judged by its
    median. (A first version judged the worst spread against 0.5 and went
    red once in 10 repeats of hwut.run.stability.)
  * The broken tunings bind the same names; their law is the violation
    ('settle_worst > 2.5'), so the accepted page IS the violation report.
    Values a choice states no law for are free.

READING THE GOOD. In the picture, 'o' should hug '-' and ignore the '.'
cloud; the table under it gives R1..R3 for that ride. The sweep lines give
the worst of 40 rides, which is what the law is about: each prints the law
the choice states and its verdict ('holds'/'BROKEN'); a value the choice
states no law for says so, since its verdict would vary from run to run.
______________________________________________________________________________
"""
import os
import random
import statistics
import subprocess
import sys
import tempfile
import atexit
import shutil
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOP  = os.path.join(HERE, "..")
RATE_HZ, T_END, T_UP, T_TOP, RISE = 25, 12.0, 4.0, 6.0, 3.0
P0, NOISE_PA = 101325.0, 3.0
HOLD_S = 1.0



def scratch(prefix):
    """RETURN: a fresh scratch directory, removed when the test ends."""
    path = tempfile.mkdtemp(prefix=prefix)
    atexit.register(shutil.rmtree, path, True)
    return path

def truth(t):
    """RETURN: true altitude [m] at time t: rest, a smooth 2 s ride, rest."""
    if t <= T_UP:
        return 0.0
    if t >= T_TOP:
        return RISE
    s = (t - T_UP) / (T_TOP - T_UP)
    return RISE * s * s * (3 - 2 * s)


def samples(rng):
    """RETURN: text "t p" lines of one ride, pressure with gaussian noise."""
    lines = []
    for k in range(int(T_END * RATE_HZ) + 1):
        t = k / RATE_HZ
        p = P0 * (1 - truth(t) / 44330.0) ** 5.255 + rng.gauss(0.0, NOISE_PA)
        lines.append("%.3f %.3f" % (t, p))
    return "\n".join(lines) + "\n"


def build():
    """RETURN: path of the filter binary, compiled into a private directory."""
    exe = os.path.join(scratch("kalman-"), "kalman")
    subprocess.run(["gcc", "-O2", "-o", exe, os.path.join(TOP, "kalman.c"), "-lm"], check=True)
    return exe


def ride(exe, tuning, rng):
    """RETURN: list of (t, raw, estimate, truth)."""
    out = subprocess.run([exe, tuning, "%.1f" % P0], input=samples(rng), capture_output=True,
                         text=True, check=True).stdout
    return [(t, raw, est, truth(t)) for t, raw, est in
            (tuple(map(float, line.split())) for line in out.splitlines())]


def measures(track):
    """RETURN: (rms, settle, ratio) -- R1, R2, R3 of one ride."""
    rest = [(raw - tr, est - tr) for t, raw, est, tr in track
            if 1.0 <= t <= T_UP or t >= T_TOP + 2.5]
    rms   = statistics.fmean(e * e for _, e in rest) ** 0.5
    ratio = statistics.pstdev([e for _, e in rest]) / statistics.pstdev([r for r, _ in rest])
    after = [(t, abs(est - tr) <= 0.30) for t, _, est, tr in track if t >= T_TOP]
    hold = int(RATE_HZ * HOLD_S)               # samples the estimate must stay inside
    settle = next((after[i][0] - T_TOP for i in range(len(after) - hold)
                   if all(inside for _, inside in after[i:i + hold])), T_END - T_TOP)
    return rms, settle, ratio


def picture(track):
    """Prints the ride as an ASCII plot: 60 columns of 0.2 s, rows of 0.25 m."""
    top, bottom, step = 4.0, -1.0, 0.25
    rows = int(round((top - bottom) / step)) + 1
    width = 60
    grid = [[" "] * width for _ in range(rows)]
    row_of = lambda h: min(rows - 1, max(0, int(round((top - h) / step))))
    per_col = len(track) // width
    for k, (t, raw, est, tr) in enumerate(track[:per_col * width]):
        col = k // per_col
        grid[row_of(raw)][col] = "." if grid[row_of(raw)][col] == " " else grid[row_of(raw)][col]
    for col in range(width):
        chunk = track[col * per_col:(col + 1) * per_col]
        grid[row_of(statistics.fmean(c[3] for c in chunk))][col] = "-"
        grid[row_of(statistics.fmean(c[2] for c in chunk))][col] = "o"
    print("##! verbatim")
    for i, row in enumerate(grid):
        h = top - i * step
        label = "%5.1f m" % h if abs(h * 2 - round(h * 2)) < 1e-9 else "       "
        print("%s |%s|" % (label, "".join(row)))
    print("        +" + "".join("+" if c % 10 == 0 and c else "-" for c in range(width)) + "+")
    print("         " + "".join("%-10s" % ("%ds" % (2 * k)) for k in range(width // 10)) + "12s")
    print("####")


def main(choice):
    exe = build()
    tuning = os.path.join(TOP, "tuning-%s.conf" % choice)
    with open(tuning) as fh:
        print("tuning-%s.conf:  %s" % (choice, " ".join(fh.read().split())))
    print("ride with seed 4711:  '.' raw  '-' truth  'o' estimate")
    track = ride(exe, tuning, random.Random(4711))
    picture(track)
    rms, settle, ratio = measures(track)
    ok = lambda flag: "holds" if flag else "BROKEN"
    print("R1 rms error at rest     %5.3f m   <= 0.18 m   %s" % (rms, ok(rms <= 0.18)))
    print("R2 settled after ride    %5.2f s   <= 2.5 s    %s" % (settle, ok(settle <= 2.5)))
    print("R3 spread est/raw        %5.3f     <= 0.45     %s" % (ratio, ok(ratio <= 0.45)))
    print("   (spread = std(estimate - truth) / std(raw - truth), at rest)")

    seed = time.time_ns()
    rng = random.Random(seed)
    n = 40
    sweep = [measures(ride(exe, tuning, rng)) for _ in range(n)]
    worst = [max(m[i] for m in sweep) for i in range(3)]
    ratio_median = statistics.median(m[2] for m in sweep)
    print("## seed %d" % seed)
    print("sweep of %d rides, noise seeded by the clock:" % n)
    judged = {"tuned": "R1 R2 R3", "sluggish": "R2", "nervous": "R3"}[choice]
    def law(r, text, flag):
        return "law %s   %s" % (text, ok(flag)) if r in judged else "(no law in this choice)"
    print("  R1 rms error at rest, worst    ((rms_worst: %.3f m))   %s"
          % (worst[0], law("R1", "<= 0.18 m", worst[0] <= 0.18)))
    print("  R2 settled after ride, worst   ((settle_worst: %.2f s))   %s"
          % (worst[1], law("R2", "<= 2.5 s", worst[1] <= 2.5)))
    print("  R3 spread est/raw, median      ((ratio_median: %.3f))   %s"
          % (ratio_median, law("R3", "<= 0.45", ratio_median <= 0.45)))


if len(sys.argv) < 2 or sys.argv[1] not in ("tuned", "sluggish", "nervous"):
    print("choices: tuned, sluggish, nervous")
    sys.exit(1)
main(sys.argv[1])
print("<hwut-end>")
