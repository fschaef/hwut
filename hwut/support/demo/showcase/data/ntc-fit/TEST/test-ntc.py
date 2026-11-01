#! /usr/bin/env python3
#
# @hwut {
#     title   = "NTC calibration: a Steinhart-Hart fit within 0.15 K"
#     choices {
#         datasheet { features = ["fit-within-spec"]
#                     tolerance { constraints = ["abs(worst) <= 0.15 K"] } }
#         lab       { features = ["fit-within-spec", "noise-tolerated"]
#                     tolerance { constraints = ["abs(worst) <= 0.15 K"] } }
#         typo      { features = ["violation-shown"]
#                     tolerance { constraints = ["abs(worst) > 0.15 K"] } }
#     }
# }
#
"""
______________________________________________________________________________
SUBJECT  the Steinhart-Hart fit that ../shfit.awk makes of one NTC calibration
         table: coefficients, fitted temperature and residual per point
REQUIREMENT. ../shfit.awk fits 1/T = a + b ln R + c (ln R)^3 to an NTC
calibration table (-20..100 degC, 13 points):
    R1  every calibration point lies within 0.15 K of the fitted curve;
    R2  the fit is the fit: the same table gives the same coefficients, and
        a re-measured table (resistance noise 0.05 %) gives coefficients
        and temperatures within the stated bands.

CHOICES
    datasheet  ../ntc-datasheet.txt (3 significant digits): holds; the
               residuals are the datasheet's rounding, up to 0.06 K.
    lab        the same table re-measured: every run draws new noise (clock
               seed). Holds -- by tolerance, not by luck (below).
    typo       ../ntc-typo.txt: the 40 degC row carries the resistance of
               45 degC. One slip tilts the whole fit: every residual grows,
               40 degC is off by 4.2 K. R1 breaks.

HWUT CONCEPTS -- one region per kind of number. The fixed tables
(datasheet, typo) give the same numbers on every run: coefficients and
fitted temperatures are compared EXACTLY. Only 'lab' needs bands:
  * '##! table numeric={0:0.011, 1:0.008, 2:0.04}' for the coefficients
    a, b, c: one band per coefficient. The three trade off against each
    other -- a noisy table moves c by 0.46 % (sigma), a by 0.13 %, b by
    0.09 %, while the curve stays put -- so no band on a single coefficient
    can be tight: 1.1 % of a is still ~1 K of curve. The coefficient row
    catches a fit gone wild; the temperature table below is what holds
    the curve to 0.15 K.
  * '##! table numeric={2:0.0005}' for the fitted temperatures, printed in
    KELVIN: a relative band needs a value far from zero -- 0.02 degC
    against 0.03 degC is 50 %, 273.17 K against 273.18 K is 0.004 %.
    0.0005 of 300 K is 0.15 K, the spec.
  * Calibration (20000 simulated re-measurements): the lab GOOD is itself a
    noisy run, so a band must cover the GOOD's own deviation plus the
    run's. Each band is >= 8.5 sigma of its number (the temperatures
    >= 10 sigma): a GOOD 4 sigma off and a run 4.5 sigma the other way
    still pass -- a correct fit fails far less than once in 10^4 runs.
  * '##! point-cloud constraint={abs(y) <= 0.15}' for the residuals
    (x = degC, y = residual): the GOOD states the spec, not a recording.
  * The bar chart is exact for the fixed tables and stands in
    '##! ignore' for the lab table: there it is a picture of this run.
  * For 'typo' the residuals are a plain exact table (a point-cloud law
    would be red); the R1 line names the breach, and its binding
    '((worst: v K))' is judged by the choice's rule (> 0.15 K for typo).
  * UNITS: the worst residual is a QUANTITY, '((worst: -0.059 K))', and the
    law is written as the spec states it, 'abs(worst) <= 0.15 K'. It is
    printed in K, never in degC, on purpose: a residual is a temperature
    DIFFERENCE, and degC is an offset unit -- '-0.059 degC' converts to the
    absolute temperature 273.091 K and breaks the law although the fit is
    right ('delta_degC' would be the other correct spelling). The datasheet
    rows stay in degC: they are absolute temperatures and plain text.

READING THE GOOD. In the bars, '|' is zero, each '*' is 0.01 K, '[' and ']'
are the spec limits -0.15 / +0.15 K; '<' or '>' means beyond the limit;
'<- worst' marks the row the R1 line names (in 'typo' every bar is clipped,
the mark finds the culprit). In 'lab' the ohm column reads '~': the noisy
resistances differ per run and are not printed.
______________________________________________________________________________
"""
import os
import random
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOP  = os.path.join(HERE, "..")
SPEC = 0.15


def table(choice):
    """RETURN: the calibration table as text, and a note on where it came from."""
    name = "ntc-typo.txt" if choice == "typo" else "ntc-datasheet.txt"
    with open(os.path.join(TOP, name)) as fh:
        text = fh.read()
    if choice != "lab":
        return text, name
    seed = time.time_ns()
    rng = random.Random(seed)
    rows = [l.split() for l in text.splitlines() if not l.startswith("#")]
    print("## seed %d" % seed)
    return "".join("%s %.0f\n" % (t, float(r) * (1 + rng.gauss(0, 0.0005))) for t, r in rows), \
        name + " re-measured, resistance noise 0.05 %"


def bar(res):
    """RETURN: a bar centred on '|', one '*' per 0.01 K, '[' ']' at the spec."""
    w = int(SPEC * 100)
    k = round(res * 100)
    neg, pos = min(w, max(0, -k)), min(w, max(0, k))
    left, right = " " * (w - neg) + "*" * neg, "*" * pos + " " * (w - pos)
    if k < -w: left = "<" + left[1:]
    if k > w:  right = right[:-1] + ">"
    return "[" + left + "|" + right + "]"


def main(choice):
    text, note = table(choice)
    out = subprocess.run(["awk", "-f", os.path.join(TOP, "shfit.awk")], input=text,
                         capture_output=True, text=True, check=True).stdout.splitlines()
    print("table: %s" % note)
    lab = choice == "lab"
    print("coefficients: a b c")
    if lab: print("##! table numeric={0:0.011, 1:0.008, 2:0.04}")
    print("  " + "  ".join(line.split()[1] for line in out[:3]))
    if lab: print("####")
    rows = [l.split() for l in out[3:]]
    print("fit per point: degC ohm fitted_K%s" % ("   ('~' the ohms are this run's noise, not printed)" if lab else ""))
    if lab: print("##! table numeric={2:0.0005}")
    for t, r, fit, _ in rows:
        print("  %4s %6s %8.3f" % (t, r if not lab else "~", float(fit) + 273.15))
    if lab: print("####")
    print("residual per point: degC K, spec |r| <= %.2f K" % SPEC)
    print("##! table" if choice == "typo" else "##! point-cloud constraint={abs(y) <= 0.15}")
    for t, _, _, res in rows:
        print("  %4s %+.3f" % (t, float(res)))
    print("####")
    print("residual bars, '*' = 0.01 K:")
    print("##! ignore" if choice == "lab" else "##! verbatim")
    print("        %-16s0%16s" % ("-0.15 K", "+0.15 K"))
    worst = max(rows, key=lambda r: abs(float(r[3])))
    for t, _, _, res in rows:
        print("  %4s  %s%s" % (t, bar(float(res)), "  <- worst" if t == worst[0] else ""))
    print("####")
    where = "" if choice == "lab" else " at %s degC" % worst[0]
    print("R1 worst residual ((worst: %.3f K))%s   law |r| <= 0.15 K   %s" % (float(worst[3]), where,
          "holds" if abs(float(worst[3])) <= SPEC else "BROKEN"))


if len(sys.argv) < 2 or sys.argv[1] not in ("datasheet", "lab", "typo"):
    print("choices: datasheet, lab, typo")
    sys.exit(1)
main(sys.argv[1])
print("<hwut-end>")
