#! /usr/bin/env python3
# @hwut {
#     title    = "SIR epidemic (Kermack-McKendrick): the integrated curve keeps N, peaks on time, obeys the final-size relation"
#     choices {
#         rk4         { features = ["curves-drawn", "curve-recorded", "population-kept", "peak-on-time", "final-size"]
#                       tolerance { constraints = ["drift <= 1e-9", "s_min >= 0", "peak_shift <= 0.25 d", "final_size_err <= 1e-4"] } }
#         euler-daily { features = ["curves-drawn", "curve-recorded", "breach-shown"]
#                       tolerance { constraints = ["peak_shift > 0.25 d"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the epidemic curve S, I, R over 120 days that the integrator ../sir.c
         computes, and its four laws against an RK4 oracle
HISTORY  Kermack and McKendrick modelled an epidemic as three compartments,
susceptible S, infected I, recovered R, with dS/dt = -beta S I / N,
dI/dt = beta S I / N - gamma I, dR/dt = gamma I ("A contribution to the
mathematical theory of epidemics", Proc. R. Soc. Lond. A 115:700, 1927).
The model has no closed-form time course, but two exact facts: S + I + R
stays N, and the final size obeys S_end = S(0) exp(-R0 (R_end - R(0)) / N)
with the reproduction number R0 = beta / gamma (here the initial R(0) = 0).
Models stepped once per day with explicit Euler -- "the daily update" -- are a common shortcut; they keep N
exactly and still put the peak days late and too high.

REQUIREMENT  The integrator's curve (N = 1000, I0 = 1, beta = 0.5/day,
gamma = 0.2/day, R0 = 2.5, 120 days) keeps S + I + R = N, never lets S go
negative, puts the peak of I within 0.25 days of the true peak, and ends on
the final-size relation within 1e-4 N.

The unit is C, '../sir.c' (Euler or classic RK4, step and print interval
on the command line). The ORACLE is in the test: RK4 in Python at
dt = 0.01 day, an independent implementation. The test prints
    1. the CURVES S, I, R as an ASCII plot, one column per 2 days, one row
       per 62.5 persons (I drawn over S over R where they meet), in
       '##! verbatim';
    2. the I curve as a POINT CLOUD, '##! point-cloud limit=1.0':
       (day, infected per 1000) every 2 days. The GOOD is the RECORDED
       REFERENCE CURVE; a later run passes when every point has a recorded
       neighbour within distance 1.0 and vice versa. The distance is
       Euclidean over both columns, but the samples stand 2 days apart
       and the limit is 1.0: a point can only find its partner on the SAME
       day. So in effect the cloud is an ABSOLUTE band of +-1 per 1000 on I
       at every sampled day -- an absolute tolerance, which no other hwut
       word gives (numeric_ratio is relative). It lets libm, FMA
       contraction or another compiler move the curve in its last digits
       (-ffast-math stays inside); a curve that rises by 1 per 1000
       anywhere leaves it (beta + 1 % does, at day 12);
    3. the LAW TABLE with bindings: '((drift: x))' = max |S+I+R-N| / N,
       '((s_min: x))', '((peak_shift: x d))' against the oracle (peaks
       located by a parabola through the three highest samples),
       '((final_size_err: x))' = |S_end - S(0) exp(-R0 R_end/N)| / N.

CHOICES
    rk4          dt = 0.5 day: all four laws kept.
    euler-daily  the shortcut: explicit Euler, dt = 1 day. Conservation
                 holds EXACTLY (each Euler step moves what S loses into I
                 and R), S stays positive -- the conservation law cannot
                 see the error. The peak comes about 2.5 days late and
                 higher; the final-size relation is missed. Law
                 'peak_shift > 0.25 d'.

UNITS  The times are QUANTITIES in days, the unit of the model's rates
(beta, gamma per day): '((t_peak: 24.37 d))', '((peak_shift: 4.017e-03 d))',
judged by 'peak_shift <= 0.25 d'. A shift printed in another time unit is
converted (6 h is 0.25 d); one printed as a count or in any other dimension
breaks the law. Persons, ratios and drifts are plain numbers. The point
cloud's columns stay bare numbers: a region reads numbers, not quantities.

HWUT CONCEPTS  'point-cloud limit=' compares a curve with a recorded curve
by distance (MANUAL 11); constraints carry the laws; verbatim keeps the
plot's columns. A global numeric_ratio would not do here: it would
apply to every number of the output, days and counts alike.

READING THE GOOD  In the plot the I hump peaks near day 24; in the law
table every line says 'kept' (rk4).
______________________________________________________________________________
"""
import math
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
N, I0, BETA, GAMMA, DAYS = 1000.0, 1.0, 0.5, 0.2, 120
CHOICE_DB = {"rk4": ("rk4", 0.5), "euler-daily": ("euler", 1.0)}
LIMIT_DB = {"drift": "<= 1e-9", "s_min": ">= 0", "peak_shift": "<= 0.25", "final_size_err": "<= 1e-4"}
UNIT_DB = {"peak_shift": " d"}               # the law's unit; the others are numbers


def oracle(dt=0.01):
    def d(s, i):
        inf = BETA * s * i / N
        return -inf, inf - GAMMA * i
    s, i, t, out = N - I0, I0, 0.0, []
    for k in range(int(round(DAYS / dt)) + 1):
        out.append((k * dt, s, i, N - s - i))
        a = d(s, i)
        b = d(s + dt / 2 * a[0], i + dt / 2 * a[1])
        c = d(s + dt / 2 * b[0], i + dt / 2 * b[1])
        e = d(s + dt * c[0], i + dt * c[1])
        s += dt / 6 * (a[0] + 2 * b[0] + 2 * c[0] + e[0])
        i += dt / 6 * (a[1] + 2 * b[1] + 2 * c[1] + e[1])
    return out


def peak_time(rows):
    k = max(range(1, len(rows) - 1), key=lambda j: rows[j][2])
    (t0, _, a, _), (t1, _, b, _), (t2, _, c, _) = rows[k - 1:k + 2]
    h = t1 - t0
    return t1 + h / 2 * (a - c) / (a - 2 * b + c)


def run_unit(binary, method, dt, every):
    r = subprocess.run([binary, "%g" % N, "%g" % I0, "%g" % BETA, "%g" % GAMMA, str(DAYS), "%g" % dt, method, "%g" % every],
                       capture_output=True, text=True, check=True)
    return [tuple(float(x) for x in l.split()) for l in r.stdout.splitlines()]


def plot(rows):
    height = 16
    grid = [["." for _ in rows] for _ in range(height)]
    for col, (_, s, i, r) in enumerate(rows):
        for letter, v in (("R", r), ("S", s), ("I", i)):
            grid[min(height - 1, int(v / N * height))][col] = letter
    print("##! verbatim")
    for k in reversed(range(height)):
        print("  %4d |%s" % (round((k + 1) * N / height), "".join(grid[k])))
    print("       +" + "".join("+" if c % 10 == 0 else "-" for c in range(len(rows))))
    print("        " + "".join(str(c * 2).ljust(10) for c in range(0, len(rows), 10)).rstrip())
    print("####")


def main(choice):
    method, dt = CHOICE_DB[choice]
    build = tempfile.mkdtemp()
    try:
        binary = os.path.join(build, "sir")
        subprocess.run(["gcc", "-Wall", "-Werror", "-O2", "-o", binary, os.path.join(HERE, "..", "sir.c"), "-lm"], check=True)
        coarse = run_unit(binary, method, dt, 2.0)
        fine = run_unit(binary, method, dt, dt)
    finally:
        shutil.rmtree(build)
    ref = oracle()
    print("unit: sir.c %s, dt = %g day; N = %g, I0 = %g, beta = %g/day, gamma = %g/day, R0 = %g"
          % (method, dt, N, I0, BETA, GAMMA, BETA / GAMMA))
    print("oracle: RK4 in Python, dt = 0.01 day")
    print()
    print("CURVES  S susceptible, I infected, R recovered (persons; day on the axis)")
    plot(coarse)
    print()
    print("I CURVE  day, infected per 1000 -- compared with the recorded curve, distance <= 1.0")
    print("##! point-cloud limit=1.0")
    for t, s, i, r in coarse:
        print("%5.1f %8.3f" % (t, i / N * 1000))
    print("####")
    print()
    t_end, s_end, i_end, r_end = fine[-1]
    value_db = {
        "drift": max(abs(s + i + r - N) for _, s, i, r in fine) / N,
        "s_min": min(s for _, s, _, _ in fine),
        "peak_shift": abs(peak_time(fine) - peak_time(ref)),
        "final_size_err": abs(s_end - (N - I0) * math.exp(-BETA / GAMMA * r_end / N)) / N,
    }
    print("peak of I: unit ((t_peak: %.2f d)), ((i_peak: %.1f)) persons; oracle ((t_ref: %.2f d)), ((i_ref: %.1f)) persons"
          % (peak_time(fine), max(r[2] for r in fine), peak_time(ref), max(r[2] for r in ref)))
    print("LAWS")
    for name, value in value_db.items():
        unit = UNIT_DB.get(name, "")
        print("  %-15s ((%s: %.3e%s))   required %-8s  %s"
              % (name, name, value, unit, LIMIT_DB[name] + unit,
                 "kept" if eval("%r %s" % (value, LIMIT_DB[name])) else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
