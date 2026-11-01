#! /usr/bin/env python3
# @hwut {
#     title    = "Leap second (Cloudflare, 1 Jan 2017): a duration from the wall clock goes negative, and the back-off panics"
#     choices {
#         wall-clock-2017 { features = ["queries-tabled", "negative-named", "panic-named"]
#                           tolerance { constraints = ["negative > 0", "panics > 0"] } }
#         monotonic       { features = ["queries-tabled", "durations-positive"]
#                           tolerance { constraints = ["negative == 0", "panics == 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the round-trip time a DNS forwarder measures for each of seven
         upstream queries around the leap second 2016-12-31 23:59:60 UTC,
         and the back-off it draws from that time

HISTORY  At 00:00 UTC on 1 January 2017 a leap second was inserted.
Cloudflare's DNS service (RRDNS, written in Go) measured upstream response
times as the difference of two wall-clock readings. Across the inserted
second the wall clock stepped back, a measured duration came out NEGATIVE,
and the value went into Go's 'rand.Int63n', which panics on an argument
<= 0. Part of Cloudflare's DNS resolution failed until the code was fixed:
durations are measured on a monotonic clock now (Go 1.9 later made
'time.Now()' carry a monotonic reading for exactly this).

REQUIREMENT  Every measured round-trip time is positive, whatever the wall
             clock does; no query makes the forwarder panic.

THE UNIT  '../rrdns.py': the two clocks (the wall clock reading one second
behind from the leap on, the monotonic clock never stepping), the
measurement 'end - start', and 'int63n' which panics as Go's does.

WHAT THE TEST PRINTS  A table in '##! verbatim', one row per query: its
true start and end -- 23:59:60 is the inserted second -- what the chosen
clock read at both, the measured round-trip time and the outcome:
'backoff N ms', or 'PANIC' with the panic's message. Then the counts.

The monotonic clock's readings are shown as seconds since boot: it knows no
time of day, and needs none to measure a duration.

CHOICES
    wall-clock-2017  the forwarder reads the wall clock: the two queries
                     that straddle the leap measure -100 ms and -500 ms,
                     and both panic.
    monotonic        the forwarder reads the monotonic clock: every time
                     is the true one, positive; no panic.

HOW TO READ THE GOOD  All is exact: the times are given, not drawn.
'((negative: N))' counts the measured times <= 0, '((panics: N))' the
panics; laws '> 0' for the wall clock -- its GOOD is the accepted violation
report -- and '== 0' for the monotonic one.
______________________________________________________________________________
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import rrdns                                                     # noqa: E402

#  True time in seconds from 2016-12-31 23:59:58.0 UTC; the inserted
#  second 23:59:60 spans [2.0, 3.0).
LEAP_T = 2.0
QUERY_LIST = [(0.4, 0.6), (1.2, 2.1), (1.8, 2.3), (2.3, 2.7),
              (2.6, 3.2), (3.4, 3.7), (4.1, 4.3)]
CHOICE_DB = {"wall-clock-2017": rrdns.wall_clock, "monotonic": rrdns.monotonic}


def utc_of_true(t):
    """RETURN: str, the UTC label of true time 't', '23:59:60.x' inside the
    inserted second."""
    if t < LEAP_T:     return "23:59:%04.1f" % (58 + t)
    if t < LEAP_T + 1: return "23:59:%04.1f" % (60 + t - LEAP_T)
    return "00:00:%04.1f" % (t - LEAP_T - 1)


BOOT_S = 1000.0                 # the monotonic clock: seconds since boot


def label_of_reading(choice, r):
    """RETURN: str, a clock reading 'r' (seconds from 23:59:58.0) as the
    clock shows it: UTC for the wall clock (no 23:59:60 in a reading),
    seconds since boot for the monotonic clock."""
    if choice == "monotonic": return "%.1f s" % (BOOT_S + r)
    if r < 2.0:               return "23:59:%04.1f" % (58 + r)
    return "00:00:%04.1f" % (r - 2.0)


def main(choice):
    """RETURN: int, 0 once the table and the counts are printed."""
    clock = CHOICE_DB[choice]
    print("clock read: %s   leap second inserted 2016-12-31 23:59:60 UTC" % choice)
    print("##! verbatim")
    print(" #  true start   true end     read start   read end      rtt      outcome")
    negative = panics = 0
    for n, (start, end) in enumerate(QUERY_LIST, 1):
        try:
            rtt_ms, backoff = rrdns.query(start, end, LEAP_T, clock)
            outcome = "backoff %d ms" % backoff
        except rrdns.Panic as error:
            rtt_ms = (clock(end, LEAP_T) - clock(start, LEAP_T)) * 1000.0
            outcome, panics = "PANIC: %s" % error, panics + 1
        if rtt_ms <= 0: negative += 1
        print("%2d  %-11s  %-11s  %-11s  %-11s %+6.0f ms  %s"
              % (n, utc_of_true(start), utc_of_true(end),
                 label_of_reading(choice, clock(start, LEAP_T)),
                 label_of_reading(choice, clock(end, LEAP_T)),
                 rtt_ms, outcome))
    print("####")
    print("round-trip times <= 0 ((negative: %d))   law == 0   %s"
          % (negative, "kept" if negative == 0 else "BROKEN"))
    print("queries that panicked ((panics: %d))   law == 0   %s"
          % (panics, "kept" if panics == 0 else "BROKEN"))
    return 0


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
