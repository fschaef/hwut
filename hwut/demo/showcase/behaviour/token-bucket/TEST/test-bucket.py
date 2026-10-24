#! /usr/bin/env python3
# @hwut {
#     title    = "Token bucket (10/s, burst 5): what passes, what is dropped, the level over time"
#     choices {
#         steady      { features = ["under-rate-all-pass"]
#                       tolerance { constraints = ["breaches == 0"] } }
#         storm       { features = ["window-law", "burst-after-quiet"]
#                       tolerance { constraints = ["breaches == 0"] } }
#         storm-nocap { features = ["breach-named"]
#                       tolerance { constraints = ["breaches > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  what the token-bucket limiter passed and dropped of one traffic
         pattern, and its token level, per 100 ms
REQUIREMENT  The firmware log limiter passes at most 10 messages per second
             plus a burst of 5 saved up: in ANY window of one second, at most
             15 messages pass. Traffic below the rate is never dropped.

The unit is C ('../tb.c', integer milli-tokens), driven by '../drive.c' with
request times; between requests the test asks the level ('P' lines) at the
end of every 100 ms column, so the bucket can be drawn.

The picture, one column per 100 ms (digits count messages, '+' is ten or
more):
    arrived  messages offered       sent  passed       dropped  refused
    tok      a bar chart of the level at the end of the column, one row per
             token (5 at the top); '^' on top: more than 5 tokens saved
The GOOD repeats this legend under the picture. Under it, the busiest
one-second window, and the number of one-second windows (one starting at
each sent message) that pass more than 15: the breaches of the law.

steady       8 messages per second for 6 s: nothing dropped, the bucket
             stays near full.
storm        20/s for a second (the bucket drains, the rest is dropped at
             the rate), 3 s quiet (it refills to 5 and STOPS there), then 30
             messages in 0.3 s: 5 + what refills pass, the rest is dropped.
storm-nocap  the BROKEN FIXTURE '../tb_nocap.c' (no cap on the refill): the
             quiet spell saves up 30 tokens ('^' over the chart) and the
             storm passes whole. The GOOD file is the accepted violation:
             the '!!' line names the window and its count.

HWUT CONCEPTS  The picture stands in '##! verbatim' (columns are time): it
pins every column, so ANY change of the traffic or the unit turns the run
red, lawful or not. The constraint binding '((breaches: N))' carries the
law into hwut's own judgment: 'breaches == 0' for the choices that must
keep it, 'breaches > 0' for the broken one. At run time the picture fails
first; the law guards the RE-RECORDING -- 'hwut.accept' refuses a new
picture in which a window passes more than 15, and a 'fixed' nocap whose
violation report no longer shows one.
______________________________________________________________________________
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.join(HERE, "..")
RATE, BURST, COLUMN_MS, END_MS = 10, 5, 100, 6000


def every(start, stop, step):
    return list(range(start, stop, step))


TRAFFIC_DB = {
    "steady": every(0, END_MS, 125),
    "storm":  every(0, 1000, 50) + every(4000, 4300, 10) + every(4300, END_MS, 125),
}
TRAFFIC_TEXT = {"steady": "8 messages/s for 6 s",
                "storm": "20/s for 1 s; quiet; 100/s from 4.0 to 4.3 s; then 8/s"}
CHOICE_DB = {"steady": ("tb.c", "steady"), "storm": ("tb.c", "storm"),
             "storm-nocap": ("tb_nocap.c", "storm")}


def run_unit(unit, request_list):
    script = sorted([(t, 0, "R %d" % t) for t in request_list]
                    + [(c * COLUMN_MS + COLUMN_MS - 1, 1, "P %d" % (c * COLUMN_MS + COLUMN_MS - 1))
                       for c in range(END_MS // COLUMN_MS)])
    with tempfile.TemporaryDirectory() as build:
        exe = os.path.join(build, "drive")
        subprocess.check_call(["gcc", "-Wall", "-Werror", "-I", UNIT, "-o", exe,
                               os.path.join(UNIT, "drive.c"), os.path.join(UNIT, unit)])
        out = subprocess.run([exe, str(RATE), str(BURST)], capture_output=True, text=True, check=True,
                             input="\n".join(line for _, _, line in script)).stdout
    return [line.split() for line in out.splitlines()]


def digit(n):
    return "." if n == 0 else str(n) if n < 10 else "+"


def main(choice):
    unit, traffic = CHOICE_DB[choice]
    record_list = run_unit(unit, TRAFFIC_DB[traffic])
    col_n = END_MS // COLUMN_MS
    arrived, sent, dropped, level = [0] * col_n, [0] * col_n, [0] * col_n, [0] * col_n
    sent_times = []
    for kind, t, value in record_list:
        col = int(t) // COLUMN_MS
        if kind == "P":
            level[col] = int(value) / 1000.0
        else:
            arrived[col] += 1
            if value == "1":
                sent[col] += 1
                sent_times.append(int(t))
            else:
                dropped[col] += 1

    print("unit: %s, %d tokens/s, burst %d; traffic '%s': %s, %d messages"
          % (unit, RATE, BURST, traffic, TRAFFIC_TEXT[traffic], len(TRAFFIC_DB[traffic])))
    print()
    print("##! verbatim")
    print("s         %s" % "".join(("%.1f" % (c / 10)).ljust(10) for c in range(0, col_n, 10)).rstrip())
    print("arrived   %s" % "".join(map(digit, arrived)))
    print("sent      %s" % "".join(map(digit, sent)))
    print("dropped   %s" % "".join(map(digit, dropped)))
    print(" >5 tok   %s" % "".join("^" if v > BURST + 0.001 else "." for v in level))
    for row in range(BURST, 0, -1):
        print("  %d tok   %s" % (row, "".join("*" if v >= row else "." for v in level)))
    print("####")
    print("(one column per 100 ms; digits count messages, '+' ten or more;")
    print(" '*' a token in the bucket at the column's end, '^' more than %d)" % BURST)
    print()
    best, best_at, breaches = 0, 0, 0
    for t in sent_times:
        n = sum(1 for u in sent_times if t <= u < t + 1000)
        breaches += n > RATE + BURST
        if n > best:
            best, best_at = n, t
    print("messages: %d sent, %d dropped; highest level seen: %.1f tokens   cap %d   %s"
          % (sum(sent), sum(dropped), max(level), BURST, "kept" if max(level) <= BURST + 0.001 else "!! BROKEN"))
    print("busiest 1 s window: %d sent, from %.2f s   law <= %d   %s"
          % (best, best_at / 1000, RATE + BURST, "kept" if best <= RATE + BURST else "!! BROKEN"))
    if traffic == "steady":
        print("dropped of traffic below the rate: %d   law == 0   %s"
              % (sum(dropped), "kept" if not sum(dropped) else "!! BROKEN"))
    print("1 s windows with more than %d sent: ((breaches: %d))   law == 0   %s"
          % (RATE + BURST, breaches, "kept" if not breaches else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
