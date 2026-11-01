#! /usr/bin/env python3
#
# @hwut {
#     title   = "Invoice: VAT per line, exact to the cent, rounded half-up"
#     choices {
#         decimal   { features = ["exact-cents", "adds-up"]
#                     tolerance { constraints = ["cent_errors == 0",
#                                                "unbalanced == 0"] } }
#         awk-float { features = ["violation-shown"]
#                     tolerance { constraints = ["cent_errors > 0"] } }
#     }
# }
#
"""
______________________________________________________________________________
SUBJECT  the invoice lines (net, VAT, gross) an invoicing tool (../invoice.py
         or ../invoice.awk) computes from ../invoice.csv
REQUIREMENT. An invoice line is qty x price; net, VAT (on the rounded net)
and gross are each rounded to the cent HALF-UP ('kaufmaennische Rundung'),
and every printed line adds up: net + VAT = gross. Exact -- to the cent.

CHOICES -- the same invoice.csv, two tools:
    decimal    ../invoice.py, decimal arithmetic: matches the reference on
               every line, and on 20000 random lines per run.
    awk-float  ../invoice.awk, the legacy tool: binary floats, '%.2f'
               rounds. 2.675 is stored as 2.67499999..., so it prints 2.67;
               0.125 is exact in binary, and printf rounds the tie to EVEN,
               0.12. 'label tape' prints 5.00 + 0.95 = 5.96 -- the line does
               not add up. The random sweep counts the cent errors (> 0).

HWUT CONCEPTS. The amounts are compared EXACTLY: no numeric_ratio, on
purpose. A ratio of even 0.001 would let 2.67 pass for 2.68 on any amount
above 10 EUR -- one cent is a legal fact, not noise. The sweep is random
(seeded by the clock, the seed printed as a '##' comment, which takes no
part); its counts are constraint bindings '((cent_errors: n))', judged by
the choice's law, not by the recorded number. 20000 lines per run make a
tie (one line in a few hundred) certain to be drawn: one random line per
run would be a sampler that is green by luck.

READING THE GOOD. Each amount column shows the tool's value; where the
reference differs it follows in brackets: '2.67 [2.68]'. 'adds up' says
whether net + VAT = gross on the printed line. The '##' lines under a row
explain the tie that caused it.
______________________________________________________________________________
"""
import os
import random
import subprocess
import sys
import time

HERE  = os.path.dirname(os.path.abspath(__file__))
TOP   = os.path.join(HERE, "..")
TOOL_DB = {
    "decimal":   ["python3", os.path.join(TOP, "invoice.py")],
    "awk-float": ["awk", "-F;", "-f", os.path.join(TOP, "invoice.awk")],
}


def reference(qty, price, rate):
    """RETURN: (net, vat, gross) in integer cents, half-up, VAT on the rounded
    net. Integer arithmetic only: price in milli-euro, rate in percent."""
    milli = int(round(float(price) * 1000))
    assert "%d.%03d" % divmod(milli, 1000) == "%.3f" % float(price)
    net = (qty * milli + 5) // 10
    vat = (net * rate + 50) // 100
    return net, vat, net + vat


def run_tool(choice, csv_text):
    """RETURN: list of (item, net, vat, gross) as the tool printed them (str)."""
    out = subprocess.run(TOOL_DB[choice], input=csv_text, capture_output=True,
                         text=True, check=True).stdout
    return [tuple(line.split(";")) for line in out.splitlines()]


def euro(cents):
    return "%d.%02d" % divmod(cents, 100)


def rows_of(csv_text):
    for line in csv_text.splitlines():
        if line.startswith("#") or line.count(";") < 3:
            continue
        item, qty, price, rate = line.split(";")
        yield item, int(qty), price, int(rate)


def fixture(choice):
    with open(os.path.join(TOP, "invoice.csv")) as fh:
        csv_text = fh.read()
    printed = run_tool(choice, csv_text)
    print("tool: %s   input: invoice.csv" % os.path.basename(TOOL_DB[choice][-1]))
    print("cells: the tool's value, '[x]' the half-up value where the tool differs")
    print("%-21s %3s %6s %4s   %-13s %-13s %-13s %s"
          % ("item", "qty", "price", "rate", "net", "VAT", "gross", "adds up"))
    sums = [0, 0, 0]
    for (item, qty, price, rate), (_, net, vat, gross) in zip(rows_of(csv_text), printed):
        ref = reference(qty, price, rate)
        sums = [s + r for s, r in zip(sums, ref)]
        cell = [v if v == euro(r) else "%s [%s]" % (v, euro(r))
                for v, r in zip((net, vat, gross), ref)]
        adds = "yes" if round(float(net) * 100) + round(float(vat) * 100) == round(float(gross) * 100) else "NO"
        print("%-21s %3d %6s %3d%%   %-13s %-13s %-13s %s"
              % (item, qty, price, rate, cell[0], cell[1], cell[2], adds))
        exact = qty * int(round(float(price) * 1000))
        if exact % 10 == 5:
            print("##   net %d x %s = %d.%03d is a tie: half-up gives %s"
                  % (qty, price, exact // 1000, exact % 1000, euro(ref[0])))
    total = printed[-1]
    cell = [v if v == euro(r) else "%s [%s]" % (v, euro(r)) for v, r in zip(total[1:], sums)]
    print("%-21s %3s %6s %4s   %-13s %-13s %-13s %s" % ("TOTAL", "-", "-", "-", cell[0], cell[1], cell[2], "-"))


def sweep(choice, n=20000):
    seed = time.time_ns()
    random.seed(seed)
    item_list = [(random.randint(1, 12), "%.3f" % (random.randint(1, 99999) / 1000),
                  random.choice((7, 19))) for _ in range(n)]
    csv_text = "".join("item %d;%d;%s;%d\n" % (i, q, p, r) for i, (q, p, r) in enumerate(item_list))
    printed = run_tool(choice, csv_text)[:-1]
    err_n = unbalanced_n = 0
    for (qty, price, rate), (_, net, vat, gross) in zip(item_list, printed):
        if (net, vat, gross) != tuple(euro(c) for c in reference(qty, price, rate)):
            err_n += 1
        if round(float(net) * 100) + round(float(vat) * 100) != round(float(gross) * 100):
            unbalanced_n += 1
    print("## seed %d" % seed)
    err_n += n - len(printed)                  # a line the tool never printed is wrong too
    print("random sweep:   %d random lines, qty 1..12, price 0.001..99.999, 7%% or 19%%" % n)
    law = lambda n: "law == 0   %s" % ("kept" if n == 0 else "BROKEN")
    print("  lines with a wrong cent  ((cent_errors: %d))   %s" % (err_n, law(err_n)))
    print("  lines not adding up      ((unbalanced: %d))   %s" % (unbalanced_n, law(unbalanced_n)))


if len(sys.argv) < 2 or sys.argv[1] not in TOOL_DB:
    print("choices: %s" % ", ".join(TOOL_DB))
    sys.exit(1)
fixture(sys.argv[1])
sweep(sys.argv[1])
print("<hwut-end>")
