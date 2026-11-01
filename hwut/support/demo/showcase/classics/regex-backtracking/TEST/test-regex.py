#! /usr/bin/env python3
# @hwut {
#     title    = "Cloudflare, 2 July 2019: catastrophic backtracking -- runtime against input length, fitted"
#     choices {
#         deployed-2019 { features = ["same-answers", "growth-measured", "budget-broken-shown"]
#                         tolerance { constraints = ["disagree == 0", "exponent > 1.5"] } }
#         linear        { features = ["same-answers", "growth-measured", "within-budget"]
#                         tolerance { constraints = ["disagree == 0", "exponent <= 1.5", "slowest <= 1 ms"] } }
#     }
#     caps { timeout_sec = 60 }
# }
"""
______________________________________________________________________________
SUBJECT  the answers and the runtime growth of one WAF rule's regular
         expression under Python's backtracking engine
HISTORY  On 2 July 2019 Cloudflare's network served errors worldwide for
about 27 minutes: one new rule of its web application firewall, deployed
everywhere at once, contained a regular expression that backtracked
catastrophically and drove the CPUs that ran HTTP(S) handling to 100 %.
John Graham-Cumming's post-mortem ('Details of the Cloudflare outage on
July 2, 2019', 12 July 2019) explains the regex and singles out its end,
'.*(?:.*=.*)': two greedy '.*' before an '=' that never comes make a
backtracking engine try every split of the input between them, at every
start position -- cubic time in the input length.

REQUIREMENT  The rule decides 'match or not' for an input of n characters
             in time that grows at most linearly with n (fitted exponent
             k <= 1.5), and within 1 ms for any input up to 400 characters.
             A rewrite must give the SAME answers.

THE UNIT  '../waf_rule.py': the deployed tail '.*(?:.*=.*)' and the linear
'=' (as a yes/no test both mean 'there is an "="'), compiled by Python's
're' -- a backtracking engine, like the one the WAF used.

WHAT THE TEST DOES
  1. SAME ANSWERS: 400 inputs from deterministic_random (seed 2019; lengths
     0 .. 40 over 'x', '=', ';', '-', ' ', newline) -- the choice's pattern
     against the meaning '"=" in s'. '((disagree: N))', law 'disagree == 0'
     for both: the linear rule is a rewrite, not a different rule.
  2. RUNTIME TABLE: inputs 'x' * n without '=' (the worst case), n = 25 ..
     400, doubling. Each time is the fastest of 15 runs (a busy machine slows
     the median, not the minimum). The '##! table ignore=2,3' shows the
     microseconds and a log-scaled bar but does not judge them: they belong
     to the machine. Judged are n and the answer (exact), and, as
     constraints, the slope 'k' of log(time) over log(n) for n >= 50 (the
     smallest size is call overhead) -- '((exponent: k))', a number free of
     the machine's speed -- and the slowest call as a QUANTITY,
     '((slowest: 0.3 us))', measured in microseconds and judged against
     the requirement's 1 ms ('slowest <= 1 ms': the comparison converts).
  CAPS: n stops at 400 (the deployed tail takes some 15 ms there and 8x
  more per doubling); the test runs under 'caps { timeout_sec = 60 }' so a
  pattern that went exponential would end as 'killed', not hang the suite.

CHOICES
    deployed-2019  k about 3: each doubling of n costs about 8x. Law
                   'exponent > 1.5' -- the violation, stated as a law.
    linear         k about 0 to 1, well under a microsecond per call.
                   Laws 'exponent <= 1.5' and 'slowest <= 1 ms'. (The
                   deployed rule carries no time law: its 11 ms belong to
                   this machine; the exponent is its machine-free verdict.)
                   A slowest call printed without its unit breaks the law
                   by its dimension -- but a scale slip in the SAFE
                   direction (microseconds labelled 'ns') passes: a unit
                   check catches only what makes the number look worse.

HOW TO READ THE GOOD  The bar gains two '=' per doubling of the time: a
linear rule's bars barely grow, the deployed one's grow by about six per
row. The exponent line is the verdict; the table is the evidence.
______________________________________________________________________________
"""
import math
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
from hwut.test_writing_support.python.deterministic_random import DeterministicStream

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import waf_rule

SIZES = [25, 50, 100, 200, 400]
ALPHABET = "x=;- \n"


def fastest_us(rx, text, repeat=15):
    best = math.inf
    for _ in range(repeat):
        t0 = time.perf_counter()
        rx.search(text)
        best = min(best, time.perf_counter() - t0)
    return best * 1e6


def main(name):
    rx = waf_rule.compiled(name)
    print("rule: %-14s pattern %s   engine: Python re (backtracking)" % (name, waf_rule.RULE_DB[name]))
    rng = DeterministicStream(2019)
    disagree = 0
    for _ in range(400):
        text = "".join(rng.select(ALPHABET) for _ in range(rng.next_int(0, 40)))
        disagree += (rx.search(text) is not None) != ("=" in text)
    print("same answers as '\"=\" in s' on 400 random inputs (seed 2019): disagree ((disagree: %d))   law == 0   %s"
          % (disagree, "kept" if not disagree else "BROKEN"))
    print()
    print("##! table ignore=2,3")
    print("     n  match        us*  log-time*")
    us_db = {}
    for n in SIZES:
        text = "x" * n
        us_db[n] = fastest_us(rx, text)
        bar = "=" * max(1, round(2 * math.log2(max(us_db[n], 0.1) / 0.1)))
        print("%6d  %-5s %10.1f  %s" % (n, "yes" if rx.search(text) else "no", us_db[n], bar))
    print("####")
    print("(* not compared: they belong to the machine; log-time: one '=' per factor 1.41 (2 per doubling) above 0.1 us)")
    xs = [math.log2(n) for n in SIZES[1:]]
    ys = [math.log2(max(us_db[n], 0.01)) for n in SIZES[1:]]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    k = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    print("time ~ n^k, fitted over n = %s: k = ((exponent: %.2f))   law <= 1.5   %s"
          % (", ".join(map(str, SIZES[1:])), k, "kept" if k <= 1.5 else "BROKEN"))
    slowest = max(us_db.values())
    print("slowest call ((slowest: %.1f us)) at n <= %d   %s"
          % (slowest, SIZES[-1], ("law <= 1 ms   " + ("kept" if slowest <= 1000 else "BROKEN")) if name == "linear"
             else "(not judged: the time of this machine; the exponent is the verdict)"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in waf_rule.RULE_DB:
        print("choices: %s" % ", ".join(waf_rule.RULE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
